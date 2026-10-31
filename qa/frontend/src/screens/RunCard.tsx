import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { getPlan } from '../api/plans';
import { RunAction, RunResult, changeRunStatus, deleteRun, getRun, listRunResults } from '../api/runs';
import { getSuite } from '../api/suites';
import { Column, DataTable } from '../components/DataTable';
import { ErrorMessage } from '../components/ErrorMessage';
import { FilterBar } from '../components/FilterBar';
import { Pagination } from '../components/Pagination';
import { StatusBadge } from '../components/StatusBadge';
import { useToast } from '../components/Toast';
import { RESULT_STATUSES, formatDateTime, statusLabel } from '../labels';
import { canDeleteRun, canRecordResult, runActions } from '../permissions';
import { useSession } from '../session';
import { useListParams } from '../useListParams';
import { useLoad } from '../useLoad';

const ACTION_LABELS: Record<RunAction, string> = { start: 'Запустить', complete: 'Завершить', abort: 'Прервать' };
const ACTION_DONE: Record<RunAction, string> = { start: 'Прогон запущен', complete: 'Прогон завершён, результаты больше не изменяются', abort: 'Прогон прерван' };
const CONFIRM: Partial<Record<RunAction, string>> = {
  complete: 'Завершить прогон? После этого результаты не изменить.',
  abort: 'Прервать прогон? Невыполненные кейсы останутся «Не выполнен».',
};
const REFRESH_MS = 10_000;

export function RunCard() {
  const { id = '' } = useParams();
  const session = useSession();
  const navigate = useNavigate();
  const toast = useToast();
  const { values, page, setFilter, setPage } = useListParams();
  const run = useLoad(() => getRun(id), [id]);
  const results = useLoad(() => listRunResults(id, { status: values.status, page }), [id, values.status, page]);
  const suite = useLoad(async () => (run.data?.suiteId ? getSuite(run.data.suiteId) : null), [run.data?.suiteId]);
  const plan = useLoad(async () => (run.data?.planId ? getPlan(run.data.planId) : null), [run.data?.planId]);
  const [error, setError] = useState<unknown>(null);
  const live = run.data?.status === 'IN_PROGRESS';
  const reloadRun = run.reload;
  const reloadResults = results.reload;

  // Выполняется — счётчики обновляются (110): кейсы могут записывать другие тестировщики.
  useEffect(() => {
    if (!live) return;
    const timer = setInterval(() => { reloadRun(); reloadResults(); }, REFRESH_MS);
    return () => clearInterval(timer);
  }, [live, reloadRun, reloadResults]);

  if (!run.data) return run.error ? <ErrorMessage error={run.error} onRetry={run.reload} /> : <p className="muted" aria-busy="true">Загрузка…</p>;
  const current = run.data;
  const { summary } = current;

  const act = async (action: RunAction) => {
    const question = CONFIRM[action];
    if (question && !window.confirm(question)) return;
    setError(null);
    try {
      run.setData(await changeRunStatus(id, action));
      toast(ACTION_DONE[action]);
      results.reload();
    } catch (failure) {
      setError(failure);
    }
  };

  const remove = async () => {
    if (!window.confirm(`Удалить прогон ${current.key}? Это действие нельзя отменить.`)) return;
    setError(null);
    try {
      await deleteRun(id);
      toast(`Прогон ${current.key} удалён`);
      navigate('/runs');
    } catch (failure) {
      setError(failure);
    }
  };

  const columns: Column<RunResult>[] = [
    { header: 'Кейс', render: (row) => <>{row.testCaseKey}<div className="muted">{row.title}</div></> },
    { header: 'Версия', render: (row) => row.caseVersion },
    { header: 'Исполнитель', render: (row) => row.executedBy ?? row.assignee ?? '—' },
    { header: 'Результат', render: (row) => <><StatusBadge status={row.status} />{row.failedStepPosition ? <div className="muted">шаг {row.failedStepPosition}</div> : null}</> },
    { header: 'Фактический результат', render: (row) => row.actualResult ?? '' },
    { header: 'Дефект', render: (row) => (row.defect ? <Link to={`/defects/${row.defect.id}`}>{row.defect.key}</Link> : '') },
    {
      header: '',
      render: (row) => canRecordResult(session, current.status, row) && (
        <Link className="btn" to={`/runs/${id}/results/${row.id}`}>Выполнить</Link>
      ),
    },
  ];

  const source = suite.data
    ? <>Набор <Link to={`/suites/${suite.data.id}`}>«{suite.data.name}»</Link></>
    : plan.data
      ? <>План <Link to={`/plans/${plan.data.id}`}>{plan.data.key}</Link></>
      : '—';

  return (
    <>
      <div className="bar"><Link className="btn" to="/runs">← К списку</Link></div>
      <h2>{current.key} · {current.environment} <StatusBadge status={current.status} /></h2>
      <p className="muted">
        {source} · запустил {current.startedBy} · создан {formatDateTime(current.createdAt)}
        {current.finishedAt ? ` · завершён ${formatDateTime(current.finishedAt)}` : ''}
      </p>
      <div className="grid">
        <div className="stat"><b>{summary.total}</b>Всего</div>
        <div className="stat"><b className="PASSED">{summary.passed}</b>Пройдено</div>
        <div className="stat"><b className="FAILED">{summary.failed}</b>Провалено</div>
        <div className="stat"><b className="BLOCKED">{summary.blocked}</b>Заблокировано</div>
        <div className="stat"><b className="NOT_RUN">{summary.notRun}</b>Не выполнено</div>
        <div className="stat"><b className="SKIPPED">{summary.skipped}</b>Пропущено</div>
      </div>
      <div className="bar">
        {runActions(session.role, current.status).map((action) => (
          <button key={action} type="button" className={action === 'start' ? 'primary' : undefined} onClick={() => act(action)}>{ACTION_LABELS[action]}</button>
        ))}
        {canDeleteRun(session.role, current) && <button type="button" onClick={remove}>Удалить</button>}
        {suite.data?.purpose === 'SMOKE' && current.smokeVerdict && <span>Вердикт: <StatusBadge status={current.smokeVerdict} /></span>}
        {current.verdict && <span>Вердикт приёмки: <StatusBadge status={current.verdict} /></span>}
      </div>
      <ErrorMessage error={error} />
      {current.status === 'CREATED' && <div className="notice">Прогон ещё не запущен: результаты записываются после запуска.</div>}
      {(current.status === 'COMPLETED' || current.status === 'ABORTED') && <div className="notice">Прогон закрыт: результаты только для чтения.</div>}
      <FilterBar
        fields={[{ name: 'status', label: 'Результат', type: 'select', emptyLabel: 'Все', options: RESULT_STATUSES.map((value) => ({ value, label: statusLabel(value) })) }]}
        values={values}
        onChange={setFilter}
      />
      <div className="panel">
        <DataTable
          columns={columns}
          rows={results.data?.items}
          rowKey={(row) => row.id}
          onOpen={(row) => navigate(`/runs/${id}/results/${row.id}`)}
          loading={results.loading}
          error={results.error}
          onRetry={results.reload}
          emptyText="По фильтру результатов нет"
        />
        {results.data && <Pagination page={page} totalPages={results.data.totalPages} onChange={setPage} />}
      </div>
    </>
  );
}
