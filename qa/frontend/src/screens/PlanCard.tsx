import { FormEvent, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { PlanAction, PlanSummary, addPlanCases, changePlanStatus, getPlan, getPlanSummary, removePlanCase } from '../api/plans';
import { Run, listRuns } from '../api/runs';
import { caseFilterFields, toCaseFilter } from '../caseFilter';
import { CasePicker } from '../components/CasePicker';
import { Column, DataTable } from '../components/DataTable';
import { ErrorMessage } from '../components/ErrorMessage';
import { Field, Prop } from '../components/Field';
import { FilterBar } from '../components/FilterBar';
import { StatusBadge } from '../components/StatusBadge';
import { useToast } from '../components/Toast';
import { SCOPE_LABELS } from '../labels';
import { canCreateRun, canManagePlans, isPlanOpen, planActions } from '../permissions';
import { useSession } from '../session';
import { useLoad } from '../useLoad';
import { useClassifiers } from '../useReferenceData';

const ACTION_LABELS: Record<PlanAction, string> = { activate: 'Запустить план', complete: 'Завершить план', cancel: 'Отменить план' };
const ACTION_DONE: Record<PlanAction, string> = { activate: 'План запущен', complete: 'План завершён', cancel: 'План отменён, незавершённые прогоны прерваны' };

type SummaryCase = PlanSummary['cases'][number];

const RUN_COLUMNS: Column<Run>[] = [
  { header: 'Прогон', render: (row) => row.key },
  { header: 'Окружение', render: (row) => row.environment },
  { header: 'Пройдено', render: (row) => row.summary.passed },
  { header: 'Провалено', render: (row) => row.summary.failed },
  { header: 'Осталось', render: (row) => row.summary.notRun },
  { header: 'Статус', render: (row) => <StatusBadge status={row.status} /> },
];

export function SummaryCounters({ counters }: { counters: PlanSummary['counters'] }) {
  const items: [string, string, number][] = [
    ['PASSED', 'Пройдено', counters.passed],
    ['FAILED', 'Провалено', counters.failed],
    ['BLOCKED', 'Заблокировано', counters.blocked],
    ['SKIPPED', 'Пропущено', counters.skipped],
    ['NOT_RUN', 'Не выполнено', counters.notRun],
  ];
  return (
    <div className="grid">
      <div className="stat"><b>{counters.total}</b>Всего кейсов</div>
      {items.map(([code, label, value]) => <div key={code} className="stat"><b className={code}>{value}</b>{label}</div>)}
    </div>
  );
}

function AddCases({ planId, caseCount, onAdded }: { planId: string; caseCount: number; onAdded: () => void }) {
  const toast = useToast();
  const classifiers = useClassifiers();
  const [mode, setMode] = useState<'manual' | 'filter'>('manual');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // Без статуса фильтр отбирает и черновики, а их сервер в план не примет (130).
  const [filter, setFilter] = useState<Record<string, string>>({ status: 'ACTUAL' });
  const [suiteName, setSuiteName] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const plan = await addPlanCases(planId, mode === 'manual'
        ? { ids: [...selected] }
        : { filter: toCaseFilter(filter), saveAsSuite: suiteName.trim() || undefined });
      toast(`В план добавлено кейсов: ${plan.caseCount - caseCount}${mode === 'filter' && suiteName.trim() ? `, фильтр сохранён набором «${suiteName.trim()}»` : ''}`);
      setSelected(new Set());
      setSuiteName('');
      onAdded();
    } catch (failure) {
      setError(failure);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="panel" onSubmit={submit}>
      <h3>Добавить кейсы</h3>
      <div className="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={mode === 'manual'} onClick={() => setMode('manual')}>Вручную</button>
        <button type="button" role="tab" aria-selected={mode === 'filter'} onClick={() => setMode('filter')}>Фильтром</button>
      </div>
      <ErrorMessage error={error} />
      {mode === 'manual' ? (
        <CasePicker selected={selected} onChange={setSelected} />
      ) : (
        <>
          <FilterBar fields={caseFilterFields(classifiers.data)} values={filter} onChange={(name, value) => setFilter({ ...filter, [name]: value })} />
          <Field label="Сохранить как набор (необязательно)">
            <input type="text" value={suiteName} onChange={(event) => setSuiteName(event.target.value)} placeholder="Название нового набора по этому фильтру" />
          </Field>
        </>
      )}
      <div className="bar" style={{ marginTop: 12, marginBottom: 0 }}>
        <button type="submit" className="primary" disabled={saving || (mode === 'manual' && !selected.size)}>Добавить в план</button>
      </div>
    </form>
  );
}

export function PlanCard() {
  const { id = '' } = useParams();
  const { role } = useSession();
  const navigate = useNavigate();
  const toast = useToast();
  const plan = useLoad(() => getPlan(id), [id]);
  const summary = useLoad(() => getPlanSummary(id), [id]);
  const runs = useLoad(() => listRuns({ planId: id }), [id]);
  const [error, setError] = useState<unknown>(null);

  if (!plan.data) return plan.error ? <ErrorMessage error={plan.error} onRetry={plan.reload} /> : <p className="muted" aria-busy="true">Загрузка…</p>;
  const current = plan.data;
  const editable = canManagePlans(role) && isPlanOpen(current.status);
  const refresh = () => { plan.reload(); summary.reload(); runs.reload(); };

  const act = async (action: PlanAction) => {
    if (action === 'cancel' && !window.confirm(`Отменить план ${current.key}? Незавершённые прогоны будут прерваны.`)) return;
    setError(null);
    try {
      plan.setData(await changePlanStatus(id, action));
      toast(ACTION_DONE[action]);
      refresh();
    } catch (failure) {
      setError(failure);
    }
  };

  const remove = async (row: SummaryCase) => {
    setError(null);
    try {
      await removePlanCase(id, row.testCaseId);
      toast(`Кейс ${row.testCaseKey} убран из плана`);
      refresh();
    } catch (failure) {
      setError(failure);
    }
  };

  const caseColumns: Column<SummaryCase>[] = [
    { header: 'Ключ', render: (row) => row.testCaseKey },
    { header: 'Название', render: (row) => row.title },
    { header: 'Статус', render: (row) => <StatusBadge status={row.status} /> },
    { header: 'Последний результат', render: (row) => (row.lastResult ? <><StatusBadge status={row.lastResult.status} /> <Link to={`/runs/${row.lastResult.runId}`}>{row.lastResult.runKey}</Link></> : <StatusBadge status="NOT_RUN" />) },
    ...(editable ? [{ header: '', render: (row: SummaryCase) => <button type="button" aria-label={`Убрать ${row.testCaseKey}`} onClick={() => remove(row)}>Убрать</button> }] : []),
  ];

  return (
    <>
      <div className="bar"><Link className="btn" to="/plans">← К списку</Link></div>
      <h2>{current.key} · {current.name} <StatusBadge status={current.status} /></h2>
      <div className="bar">
        {current.status === 'ACTIVE' && canCreateRun(role) && <Link className="btn primary" to={`/runs/new?planId=${current.id}`}>Создать прогон</Link>}
        {planActions(role, current.status).map((action) => <button key={action} type="button" onClick={() => act(action)}>{ACTION_LABELS[action]}</button>)}
      </div>
      <ErrorMessage error={error} />
      {!current.refsVerified && (current.planningReleaseId || current.trackerIterationId || current.planningMilestoneId) && (
        <div className="notice warn">Ссылки на релиз, веху и итерацию не проверены: справочника Planning System и Task Tracker пока нет.</div>
      )}
      <div className="panel">
        <dl className="props">
          <Prop name="Область">{SCOPE_LABELS[current.scopeKind]}{current.scopeRef ? `: ${current.scopeRef}` : ''}</Prop>
          <Prop name="Ответственный">{current.owner}</Prop>
          <Prop name="Команда">{current.teamRef}</Prop>
          <Prop name="Сроки">{current.startDate} — {current.endDate}</Prop>
          <Prop name="Проект">{current.planningProjectId}</Prop>
          <Prop name="Релиз">{current.planningReleaseId}</Prop>
          <Prop name="Веха">{current.planningMilestoneId}</Prop>
          <Prop name="Итерация">{current.trackerIterationId}</Prop>
        </dl>
      </div>
      <h3>Сводка по последним результатам</h3>
      <ErrorMessage error={summary.error} onRetry={summary.reload} />
      {summary.data && <SummaryCounters counters={summary.data.counters} />}
      <div className="panel">
        <h3>Состав плана</h3>
        <DataTable
          columns={caseColumns}
          rows={summary.data?.cases}
          rowKey={(row) => row.testCaseId}
          onOpen={(row) => navigate(`/test-cases/${row.testCaseId}`)}
          loading={summary.loading}
          emptyText="В плане нет кейсов"
        />
      </div>
      {editable && <AddCases planId={id} caseCount={current.caseCount} onAdded={refresh} />}
      <div className="panel">
        <h3>Прогоны плана</h3>
        <DataTable
          columns={RUN_COLUMNS}
          rows={runs.data?.items}
          rowKey={(row) => row.id}
          onOpen={(row) => navigate(`/runs/${row.id}`)}
          loading={runs.loading}
          error={runs.error}
          onRetry={runs.reload}
          emptyText="По плану ещё нет прогонов"
        />
      </div>
    </>
  );
}
