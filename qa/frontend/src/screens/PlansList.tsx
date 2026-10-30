import { Link, useNavigate } from 'react-router';
import { TestPlan, listPlans } from '../api/plans';
import { Column, DataTable } from '../components/DataTable';
import { FilterBar } from '../components/FilterBar';
import { Pagination } from '../components/Pagination';
import { StatusBadge } from '../components/StatusBadge';
import { PLAN_STATUSES, SCOPE_LABELS, statusLabel } from '../labels';
import { canManagePlans } from '../permissions';
import { useSession } from '../session';
import { useListParams } from '../useListParams';
import { useLoad } from '../useLoad';

const COLUMNS: Column<TestPlan>[] = [
  { header: 'Ключ', render: (row) => row.key },
  { header: 'План', render: (row) => row.name },
  { header: 'Область', render: (row) => SCOPE_LABELS[row.scopeKind] },
  { header: 'Релиз', render: (row) => (row.planningReleaseId ? <>{row.planningReleaseId}{!row.refsVerified && <div className="muted">не проверена</div>}</> : '—') },
  { header: 'Итерация', render: (row) => row.trackerIterationId ?? '—' },
  { header: 'Сроки', render: (row) => `${row.startDate} — ${row.endDate}` },
  { header: 'Кейсов', render: (row) => row.caseCount },
  { header: 'Статус', render: (row) => <StatusBadge status={row.status} /> },
];

export function PlansList() {
  const { role } = useSession();
  const navigate = useNavigate();
  const { values, page, setFilter, setPage, reset } = useListParams();
  const plans = useLoad(() => listPlans({ ...values, page }), [values, page]);

  return (
    <>
      <h2>Планы</h2>
      <FilterBar
        fields={[
          { name: 'status', label: 'Статус', type: 'select', emptyLabel: 'Все', options: PLAN_STATUSES.map((value) => ({ value, label: statusLabel(value) })) },
          { name: 'planningProjectId', label: 'Проект', type: 'text' },
          { name: 'planningReleaseId', label: 'Релиз', type: 'text' },
          { name: 'trackerIterationId', label: 'Итерация', type: 'text' },
        ]}
        values={values}
        onChange={setFilter}
        onReset={reset}
      />
      {canManagePlans(role) && <div className="bar"><Link className="btn primary" to="/plans/new">Создать план</Link></div>}
      <div className="panel">
        <DataTable
          columns={COLUMNS}
          rows={plans.data?.items}
          rowKey={(row) => row.id}
          onOpen={(row) => navigate(`/plans/${row.id}`)}
          loading={plans.loading}
          error={plans.error}
          onRetry={plans.reload}
          emptyText="Планов нет"
        />
        {plans.data && <Pagination page={page} totalPages={plans.data.totalPages} onChange={setPage} />}
      </div>
    </>
  );
}
