import { Link, useNavigate } from 'react-router';
import { listAllPlans } from '../api/plans';
import { Run, listRuns } from '../api/runs';
import { listAllSuites } from '../api/suites';
import { Column, DataTable } from '../components/DataTable';
import { FilterBar } from '../components/FilterBar';
import { Pagination } from '../components/Pagination';
import { StatusBadge } from '../components/StatusBadge';
import { RUN_STATUSES, statusLabel } from '../labels';
import { canCreateRun } from '../permissions';
import { useSession } from '../session';
import { useListParams } from '../useListParams';
import { useLoad } from '../useLoad';

export function RunsList() {
  const { role } = useSession();
  const navigate = useNavigate();
  const { values, page, setFilter, setPage, reset } = useListParams();
  const runs = useLoad(() => listRuns({ ...values, page }), [values, page]);
  // В прогоне только идентификаторы источника; названия берутся из списков наборов и планов.
  const suites = useLoad(() => listAllSuites(), ['suites']);
  const plans = useLoad(() => listAllPlans(), ['plans']);

  const sourceOf = (run: Run) => {
    if (run.suiteId) return `Набор «${suites.data?.find((suite) => suite.id === run.suiteId)?.name ?? '…'}»`;
    if (run.planId) return `План ${plans.data?.find((plan) => plan.id === run.planId)?.key ?? '…'}`;
    return '—';
  };

  const columns: Column<Run>[] = [
    { header: 'Ключ', render: (row) => row.key },
    { header: 'Источник', render: sourceOf },
    { header: 'Окружение', render: (row) => row.environment },
    { header: 'Запуск', render: (row) => `${row.trigger} · ${row.startedBy}` },
    { header: 'Пройдено', render: (row) => row.summary.passed },
    { header: 'Провалено', render: (row) => row.summary.failed },
    { header: 'Осталось', render: (row) => row.summary.notRun },
    { header: 'Статус', render: (row) => <StatusBadge status={row.status} /> },
  ];

  return (
    <>
      <h2>Прогоны</h2>
      <FilterBar
        fields={[
          { name: 'status', label: 'Статус', type: 'select', emptyLabel: 'Все', options: RUN_STATUSES.map((value) => ({ value, label: statusLabel(value) })) },
          { name: 'suiteId', label: 'Набор', type: 'select', emptyLabel: 'Все', options: (suites.data ?? []).map((suite) => ({ value: suite.id, label: suite.name })) },
          { name: 'planId', label: 'План', type: 'select', emptyLabel: 'Все', options: (plans.data ?? []).map((plan) => ({ value: plan.id, label: `${plan.key} ${plan.name}` })) },
        ]}
        values={values}
        onChange={setFilter}
        onReset={reset}
      />
      {canCreateRun(role) && <div className="bar"><Link className="btn primary" to="/runs/new">Создать прогон</Link></div>}
      <div className="panel">
        <DataTable
          columns={columns}
          rows={runs.data?.items}
          rowKey={(row) => row.id}
          onOpen={(row) => navigate(`/runs/${row.id}`)}
          loading={runs.loading}
          error={runs.error}
          onRetry={runs.reload}
          emptyText="Прогонов пока нет. Создайте прогон из плана или набора."
        />
        {runs.data && <Pagination page={page} totalPages={runs.data.totalPages} onChange={setPage} />}
      </div>
    </>
  );
}
