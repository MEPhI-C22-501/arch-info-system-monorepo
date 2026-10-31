import { FormEvent, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { ApiError } from '../api/client';
import { LastResult, TestCase, TestCaseStatus, TestCaseVersionInfo, changeCaseStatus, copyCases, deleteCase, getCase, listCaseVersions, updateCase } from '../api/cases';
import { CaseFormValues, FieldErrors, caseFormOf, fieldErrorsOf, saveOutcome, toUpdateInput, validateCase } from '../caseForm';
import { Column, DataTable } from '../components/DataTable';
import { ErrorMessage } from '../components/ErrorMessage';
import { StatusBadge } from '../components/StatusBadge';
import { useToast } from '../components/Toast';
import { formatDateTime, statusLabel } from '../labels';
import { canDeleteCase, canEditAutotest, canEditCase, caseTransitions, isCaseReadOnly } from '../permissions';
import { useSession } from '../session';
import { useLoad } from '../useLoad';
import { useClassifiers } from '../useReferenceData';
import { CaseFields } from './CaseFields';

const STATUS_ACTIONS: Record<TestCaseStatus, string> = {
  DRAFT: 'В черновик',
  ACTUAL: 'Сделать актуальным',
  NEEDS_UPDATE: 'На доработку',
  ARCHIVED: 'В архив',
};

const VERSION_COLUMNS: Column<TestCaseVersionInfo>[] = [
  { header: 'Версия', render: (row) => row.version },
  { header: 'Автор', render: (row) => row.author },
  { header: 'Дата', render: (row) => formatDateTime(row.createdAt) },
  { header: 'Изменено', render: (row) => row.changedFields.join(', ') || 'создание' },
];

function LastResultPanel({ result }: { result?: LastResult | null }) {
  return (
    <div className="panel">
      <h3>Последний результат <span className="muted">(только чтение)</span></h3>
      {result ? (
        <>
          <p>
            <StatusBadge status={result.status} /> · прогон <Link to={`/runs/${result.runId}`}>{result.runKey}</Link>
            {' · '}окружение {result.environment} · версия кейса {result.caseVersion}
            {result.failedStepPosition ? ` · упал шаг ${result.failedStepPosition}` : ''} · {formatDateTime(result.finishedAt)}
          </p>
          {result.actualResult && <p>Фактический результат: {result.actualResult}</p>}
        </>
      ) : (
        <div className="empty">Кейс ещё не выполнялся</div>
      )}
      <p className="muted" style={{ marginBottom: 0 }}>Фактический результат записывается в прогоне, а не в карточке кейса (ADR-014).</p>
    </div>
  );
}

type FormProps = {
  testCase: TestCase;
  onSaved: (saved: TestCase) => void;
  onOpenLatest: () => void;
};

function CaseEditor({ testCase, onSaved, onOpenLatest }: FormProps) {
  const { role } = useSession();
  const toast = useToast();
  const classifiers = useClassifiers();
  const [values, setValues] = useState<CaseFormValues>(() => caseFormOf(testCase));
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  const viewingOld = testCase.version !== testCase.currentVersion;
  const readOnly = isCaseReadOnly(role, testCase.status) || viewingOld;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found = validateCase(values, { isNew: false, requireSteps: testCase.status === 'ACTUAL' });
    setErrors(found);
    setError(null);
    if (Object.keys(found).length) return;
    setSaving(true);
    try {
      const saved = await updateCase(testCase.id, toUpdateInput(values, testCase));
      const outcome = saveOutcome(testCase, saved);
      if (outcome === 'new-version') toast(`Создана версия ${saved.version}`);
      else if (outcome === 'refs-only') toast('Ссылки сохранены, версия не создана');
      else toast('Изменений нет — версия не создана');
      onSaved(saved);
    } catch (failure) {
      setError(failure);
      if (failure instanceof ApiError && failure.code === 'VALIDATION_FAILED') setErrors(fieldErrorsOf(failure.errors));
    } finally {
      setSaving(false);
    }
  };

  const conflict = error instanceof ApiError && error.code === 'VERSION_CONFLICT';
  return (
    <form className="panel" onSubmit={submit}>
      <ErrorMessage error={error} />
      {conflict && (
        <div className="notice warn">
          Кейс уже сохранён другим пользователем, ваши правки не записаны.{' '}
          <button type="button" onClick={onOpenLatest}>Открыть последнюю версию</button>
        </div>
      )}
      <CaseFields values={values} onChange={setValues} errors={errors} classifiers={classifiers.data} readOnly={readOnly} autotestEditable={canEditAutotest(role)} />
      {!readOnly && (
        <div className="bar" style={{ marginTop: 12, marginBottom: 0 }}>
          <button type="submit" className="primary" disabled={saving}>Сохранить версию</button>
        </div>
      )}
    </form>
  );
}

export function CaseCard() {
  const { id = '' } = useParams();
  const session = useSession();
  const { role } = session;
  const navigate = useNavigate();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const requested = Number(params.get('version')) || undefined;
  const testCase = useLoad(() => getCase(id, requested), [id, requested]);
  const versions = useLoad(() => listCaseVersions(id), [id]);
  const [actionError, setActionError] = useState<unknown>(null);

  if (!testCase.data) {
    return testCase.error ? <ErrorMessage error={testCase.error} onRetry={testCase.reload} /> : <p className="muted" aria-busy="true">Загрузка…</p>;
  }
  const current = testCase.data;
  const viewingOld = current.version !== current.currentVersion;

  const changeStatus = async (status: TestCaseStatus) => {
    if (status === 'ARCHIVED' && !window.confirm(`Перевести кейс ${current.key} в архив?`)) return;
    setActionError(null);
    try {
      testCase.setData(await changeCaseStatus(id, status));
      toast(`Статус: ${statusLabel(status)}`);
    } catch (error) {
      setActionError(error);
    }
  };

  const copy = async () => {
    setActionError(null);
    try {
      const copies = await copyCases([id]);
      toast(`Создана копия ${copies.items[0].key}`);
      navigate(`/test-cases/${copies.items[0].id}`);
    } catch (error) {
      setActionError(error);
    }
  };

  const remove = async () => {
    if (!window.confirm(`Удалить черновик ${current.key}? Это действие нельзя отменить.`)) return;
    setActionError(null);
    try {
      await deleteCase(id);
      toast(`Кейс ${current.key} удалён`);
      navigate('/test-cases');
    } catch (error) {
      setActionError(error);
    }
  };

  const showVersion = (version: number) => {
    setParams(version === current.currentVersion ? {} : { version: String(version) });
  };

  return (
    <>
      <div className="bar"><Link className="btn" to="/test-cases">← К списку</Link></div>
      <h2>{current.key} · {current.title} <StatusBadge status={current.status} /></h2>
      {!viewingOld && (
        <div className="bar">
          {caseTransitions(role, current.status).map((status) => (
            <button key={status} type="button" onClick={() => changeStatus(status)}>
              {current.status === 'ARCHIVED' ? 'Вернуть в работу' : STATUS_ACTIONS[status]}
            </button>
          ))}
          {canEditCase(role) && <button type="button" onClick={copy}>Копировать</button>}
          {canDeleteCase(session, current) && <button type="button" onClick={remove}>Удалить</button>}
        </div>
      )}
      <ErrorMessage error={actionError} />
      {viewingOld && (
        <div className="notice">
          Просмотр версии {current.version}, только чтение. Текущая версия — {current.currentVersion}.{' '}
          <button type="button" onClick={() => showVersion(current.currentVersion ?? current.version)}>К текущей версии</button>
        </div>
      )}
      {!viewingOld && current.status === 'ARCHIVED' && (
        <div className="notice warn">Кейс в архиве: только чтение. Чтобы изменить, верните его в работу.</div>
      )}
      <CaseEditor
        key={`${current.id}:${current.version}`}
        testCase={current}
        onSaved={(saved) => { testCase.setData(saved); versions.reload(); }}
        onOpenLatest={() => { testCase.reload(); versions.reload(); }}
      />
      <LastResultPanel result={current.lastResult} />
      <div className="panel">
        <h3>История версий</h3>
        <DataTable
          columns={VERSION_COLUMNS}
          rows={versions.data?.items}
          rowKey={(row) => String(row.version)}
          onOpen={(row) => showVersion(row.version)}
          isCurrent={(row) => row.version === current.version}
          loading={versions.loading}
          error={versions.error}
          onRetry={versions.reload}
          emptyText="Версий нет"
        />
      </div>
    </>
  );
}
