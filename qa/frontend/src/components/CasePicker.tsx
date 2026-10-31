import { TestCase, listCases } from '../api/cases';
import { useState } from 'react';
import { useLoad } from '../useLoad';
import { Column, DataTable } from './DataTable';
import { FilterBar } from './FilterBar';
import { Pagination } from './Pagination';
import { StatusBadge } from './StatusBadge';
import { MODULE_OPTIONS } from '../labels';

const COLUMNS: Column<TestCase>[] = [
  { header: 'Ключ', render: (row) => row.key },
  { header: 'Название', render: (row) => row.title },
  { header: 'Статус', render: (row) => <StatusBadge status={row.status} /> },
];

const PICKER_PAGE_SIZE = 10;

// Выбор кейсов вручную. В наборы и планы добавляются только актуальные (050, раздел 3).
export function CasePicker({ selected, onChange }: { selected: Set<string>; onChange: (selected: Set<string>) => void }) {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [page, setPage] = useState(1);
  const cases = useLoad(() => listCases({ ...filters, status: 'ACTUAL', page, pageSize: PICKER_PAGE_SIZE }), [filters, page]);

  return (
    <>
      <FilterBar
        fields={[
          { name: 'q', label: 'Поиск', type: 'text', placeholder: 'Ключ или название' },
          { name: 'module', label: 'Модуль', type: 'select', emptyLabel: 'Все модули', options: MODULE_OPTIONS },
        ]}
        values={filters}
        onChange={(name, value) => { setFilters({ ...filters, [name]: value }); setPage(1); }}
      />
      <DataTable
        columns={COLUMNS}
        rows={cases.data?.items}
        rowKey={(row) => row.id}
        loading={cases.loading}
        error={cases.error}
        onRetry={cases.reload}
        emptyText="Актуальных кейсов по фильтру нет"
        selection={{ selected, onChange }}
      />
      {cases.data && <Pagination page={page} totalPages={cases.data.totalPages} onChange={setPage} />}
      <p className="muted" style={{ marginBottom: 0 }}>Выбрано: {selected.size}</p>
    </>
  );
}
