import { useNavigate } from 'react-router';
import { Defect, listDefects } from '../api/defects';
import { Column, DataTable } from '../components/DataTable';
import { FilterBar } from '../components/FilterBar';
import { Pagination } from '../components/Pagination';
import { StatusBadge } from '../components/StatusBadge';
import { DEFECT_STATUSES, SEVERITIES, statusLabel } from '../labels';
import { useListParams } from '../useListParams';
import { useLoad } from '../useLoad';

const COLUMNS: Column<Defect>[] = [
  { header: 'Ключ', render: (row) => row.key },
  { header: 'Заголовок', render: (row) => row.title },
  { header: 'Серьёзность', render: (row) => <StatusBadge status={row.severity} /> },
  { header: 'Кейс', render: (row) => row.testCaseKey ?? '—' },
  { header: 'Прогонов', render: (row) => row.runIds.length },
  { header: 'Task Tracker', render: (row) => row.trackerWorkItemId ?? <StatusBadge status={row.trackerSyncState} /> },
  { header: 'Статус', render: (row) => <><StatusBadge status={row.status} kind="defect" />{row.trackerMismatch && <div className="muted">статусы систем расходятся</div>}</> },
  { header: 'Статус «Ошибки»', render: (row) => row.trackerStatus ?? '—' },
];

export function DefectsList() {
  const navigate = useNavigate();
  const { values, page, setFilter, setPage, reset } = useListParams();
  const defects = useLoad(() => listDefects({ ...values, page }), [values, page]);

  return (
    <>
      <h2>Дефекты</h2>
      <FilterBar
        fields={[
          { name: 'status', label: 'Статус', type: 'select', emptyLabel: 'Все', options: DEFECT_STATUSES.map((value) => ({ value, label: statusLabel(value, 'defect') })) },
          { name: 'severity', label: 'Серьёзность', type: 'select', emptyLabel: 'Любая', options: SEVERITIES.map((value) => ({ value, label: value })) },
          { name: 'author', label: 'Автор', type: 'text' },
          { name: 'trackerMismatch', label: 'Расхождение с трекером', type: 'select', emptyLabel: 'Все', options: [{ value: 'true', label: 'Есть' }, { value: 'false', label: 'Нет' }] },
          { name: 'planningProjectId', label: 'Проект', type: 'text' },
          { name: 'planningReleaseId', label: 'Релиз', type: 'text' },
          { name: 'trackerIterationId', label: 'Итерация', type: 'text' },
        ]}
        values={values}
        onChange={setFilter}
        onReset={reset}
      />
      <div className="panel">
        <DataTable
          columns={COLUMNS}
          rows={defects.data?.items}
          rowKey={(row) => row.id}
          onOpen={(row) => navigate(`/defects/${row.id}`)}
          loading={defects.loading}
          error={defects.error}
          onRetry={defects.reload}
          emptyText="Дефектов нет. Они появятся после первого провала в прогоне."
        />
        {defects.data && <Pagination page={page} totalPages={defects.data.totalPages} onChange={setPage} />}
      </div>
    </>
  );
}
