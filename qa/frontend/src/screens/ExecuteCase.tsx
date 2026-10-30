import { FormEvent, useState } from 'react';
import { Link, useParams } from 'react-router';
import { getCase } from '../api/cases';
import { ApiError } from '../api/client';
import { ResultStatus, Run, RunResult, findRunResult, getRun, recordResult } from '../api/runs';
import { FieldErrors, fieldErrorsOf } from '../caseForm';
import { ErrorMessage } from '../components/ErrorMessage';
import { Field } from '../components/Field';
import { StatusBadge } from '../components/StatusBadge';
import { useToast } from '../components/Toast';
import { RESULT_STATUSES, statusLabel } from '../labels';
import { canRecordResult } from '../permissions';
import { ResultFormValues, defectMessage, deriveStatus, finalStatus, resultFormOf, toResultInput, validateResult } from '../resultForm';
import { useSession } from '../session';
import { useLoad } from '../useLoad';

type Saved = { text: string; defectId: string; defectKey: string };

const CASE_RESULT_OPTIONS = ['PASSED', 'FAILED', 'BLOCKED', 'SKIPPED'] as const;

export function ResultForm({ run, result, onSaved }: { run: Run; result: RunResult; onSaved: (result: RunResult) => void }) {
  const toast = useToast();
  const [values, setValues] = useState<ResultFormValues>(() => resultFormOf(result));
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState<Saved | null>(null);
  const [saving, setSaving] = useState(false);

  const setStep = (index: number, patch: Partial<ResultFormValues['steps'][number]>) => {
    setValues({ ...values, steps: values.steps.map((step, i) => (i === index ? { ...step, ...patch } : step)) });
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found = validateResult(values);
    setErrors(found);
    setError(null);
    setSaved(null);
    if (Object.keys(found).length) return;
    setSaving(true);
    try {
      const response = await recordResult(run.id, result.id, toResultInput(values));
      const message = defectMessage(response);
      setSaved(message && response.defect ? { text: message, defectId: response.defect.id, defectKey: response.defect.key } : null);
      toast(message ? `Провал записан: ${message}` : `Результат записан: ${statusLabel(response.status)}`);
      onSaved(response);
    } catch (failure) {
      setError(failure);
      if (failure instanceof ApiError && failure.code === 'VALIDATION_FAILED') setErrors(fieldErrorsOf(failure.errors));
    } finally {
      setSaving(false);
    }
  };

  const derived = deriveStatus(values.steps);
  const status = finalStatus(values);
  const hasFailedStep = derived === 'FAILED';

  return (
    <form onSubmit={submit}>
      <ErrorMessage error={error} />
      {saved && (
        <div className="notice warn" role="status">
          Провал записан: {saved.text.replace(saved.defectKey, '')}<Link to={`/defects/${saved.defectId}`}>{saved.defectKey}</Link>
        </div>
      )}
      <div className="panel">
        <table>
          <thead><tr><th>№</th><th>Действие</th><th>Ожидаемый результат</th><th>Статус</th><th>Фактический результат</th></tr></thead>
          <tbody>
            {values.steps.length === 0 && <tr><td colSpan={5} className="muted">В зафиксированной версии нет шагов: выберите итог кейса.</td></tr>}
            {values.steps.map((step, index) => {
              const actualError = errors[`steps.${index}.actualResult`];
              return (
                <tr key={step.stepId}>
                  <td>{step.position}</td>
                  <td><pre>{step.action}</pre></td>
                  <td><pre>{step.expectedResult}</pre></td>
                  <td>
                    <select aria-label={`Статус шага ${step.position}`} value={step.status} onChange={(event) => setStep(index, { status: event.target.value as ResultStatus })}>
                      {RESULT_STATUSES.map((value) => <option key={value} value={value}>{statusLabel(value)}</option>)}
                    </select>
                  </td>
                  <td>
                    {(step.status === 'FAILED' || step.actualResult) && (
                      <textarea rows={2} aria-label={`Фактический результат шага ${step.position}`} className={actualError ? 'invalid' : undefined} value={step.actualResult} onChange={(event) => setStep(index, { actualResult: event.target.value })} />
                    )}
                    {actualError && <span className="field-error" role="alert">{actualError}</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="panel">
        <div className="fields">
          <Field label="Итог кейса" error={errors.status}>
            <select className="wide" disabled={hasFailedStep} value={hasFailedStep ? 'FAILED' : values.chosenStatus} onChange={(event) => setValues({ ...values, chosenStatus: event.target.value as ResultStatus | '' })}>
              {!hasFailedStep && <option value="">По шагам: {statusLabel(derived)}</option>}
              {CASE_RESULT_OPTIONS.map((value) => <option key={value} value={value}>{statusLabel(value)}</option>)}
            </select>
          </Field>
          {(status === 'BLOCKED' || status === 'SKIPPED') && (
            <Field label="Причина"><input type="text" value={values.failureReason} onChange={(event) => setValues({ ...values, failureReason: event.target.value })} /></Field>
          )}
        </div>
        {status === 'FAILED' && !hasFailedStep && (
          <Field label="Фактический результат" error={errors.actualResult}>
            <textarea rows={2} value={values.actualResult} onChange={(event) => setValues({ ...values, actualResult: event.target.value })} />
          </Field>
        )}
        <Field label="Комментарий"><textarea rows={2} value={values.comment} onChange={(event) => setValues({ ...values, comment: event.target.value })} /></Field>
        <button type="submit" className="primary" disabled={saving}>Сохранить результат</button>
      </div>
    </form>
  );
}

function ReadOnlyResult({ result }: { result: RunResult }) {
  return (
    <div className="panel">
      <table>
        <thead><tr><th>№</th><th>Действие</th><th>Ожидаемый результат</th><th>Статус</th><th>Фактический результат</th></tr></thead>
        <tbody>
          {result.steps.map((step) => (
            <tr key={step.stepId}>
              <td>{step.position}</td>
              <td><pre>{step.action}</pre></td>
              <td><pre>{step.expectedResult}</pre></td>
              <td><StatusBadge status={step.status} /></td>
              <td>{step.actualResult}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {result.actualResult && <p>Фактический результат: {result.actualResult}</p>}
      {result.failureReason && <p>Причина: {result.failureReason}</p>}
      {result.comment && <p>Комментарий: {result.comment}</p>}
    </div>
  );
}

function readOnlyReason(run: Run, result: RunResult, name: string): string {
  if (run.status === 'CREATED') return 'Прогон ещё не запущен: результат записывается после запуска.';
  if (run.status !== 'IN_PROGRESS') return 'Прогон закрыт: результат только для чтения.';
  if (result.assignee && result.assignee !== name) return `Кейс назначен: ${result.assignee}. Только чтение.`;
  return 'Для вашей роли запись результата недоступна.';
}

export function ExecuteCase() {
  const { id = '', resultId = '' } = useParams();
  const session = useSession();
  const run = useLoad(() => getRun(id), [id]);
  const result = useLoad(() => findRunResult(id, resultId), [id, resultId]);
  const testCaseId = result.data?.testCaseId;
  const caseVersion = result.data?.caseVersion;
  const testCase = useLoad(async () => (testCaseId ? getCase(testCaseId, caseVersion) : null), [testCaseId, caseVersion]);

  if (run.error || result.error) return <ErrorMessage error={run.error ?? result.error} onRetry={() => { run.reload(); result.reload(); }} />;
  if (!run.data || (result.loading && !result.data)) return <p className="muted" aria-busy="true">Загрузка…</p>;
  if (!result.data) return <div className="panel"><div className="empty">Результат не найден в этом прогоне</div></div>;
  const current = result.data;
  const editable = canRecordResult(session, run.data.status, current);

  return (
    <>
      <div className="bar"><Link className="btn" to={`/runs/${id}`}>← К прогону {run.data.key}</Link></div>
      <h2>{current.testCaseKey} · {current.title} <StatusBadge status={current.status} /></h2>
      <p className="muted">
        Прогон {run.data.key} · окружение {run.data.environment} · <Link to={`/test-cases/${current.testCaseId}`}>карточка кейса</Link>
        {' · '}в прогоне версия {current.caseVersion}
        {testCase.data?.currentVersion && testCase.data.currentVersion > current.caseVersion ? ` (текущая версия кейса — ${testCase.data.currentVersion})` : ''}
      </p>
      {testCase.data?.preconditions && <p>Предусловия: {testCase.data.preconditions}</p>}
      {current.defect && current.status !== 'FAILED' && <p>Связанный дефект: <Link to={`/defects/${current.defect.id}`}>{current.defect.key}</Link></p>}
      {editable ? (
        <ResultForm run={run.data} result={current} onSaved={(saved) => { result.setData(saved); run.reload(); }} />
      ) : (
        <>
          <div className="notice">{readOnlyReason(run.data, current, session.name)}</div>
          {current.defect && current.status === 'FAILED' && <p>Дефект: <Link to={`/defects/${current.defect.id}`}>{current.defect.key}</Link></p>}
          <ReadOnlyResult result={current} />
        </>
      )}
    </>
  );
}
