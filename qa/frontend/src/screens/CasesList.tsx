import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { TestCase, copyCases, listCases } from '../api/cases';
import { caseFilterFields } from '../caseFilter';
import { Column, DataTable } from '../components/DataTable';
import { ErrorMessage } from '../components/ErrorMessage';
import { FilterBar } from '../components/FilterBar';
import { Pagination } from '../components/Pagination';
import { StatusBadge } from '../components/StatusBadge';
import { useToast } from '../components/Toast';
import { canEditCase } from '../permissions';
import { useSession } from '../session';
import { useListParams } from '../useListParams';
import { useLoad } from '../useLoad';
import { useClassifiers } from '../useReferenceData';

const COLUMNS: Column<TestCase>[] = [
  { header: 'Ключ', render: (row) => row.key },
  { header: 'Название', render: (row) => row.title },
  { header: 'Тип', render: (row) => row.type },
  { header: 'Серьёзность', render: (row) => <StatusBadge status={row.severity} /> },
  { header: 'Вид', render: (row) => (row.automated ? 'Авто' : 'Ручной') },
  { header: 'Версия', render: (row) => row.version },
  { header: 'Статус', render: (row) => <StatusBadge status={row.status} /> },
];

export function CasesList() {
  const { role } = useSession();
  const navigate = useNavigate();
  const toast = useToast();
  const { values, page, setFilter, setPage, reset } = useListParams();
  const classifiers = useClassifiers();
  const cases = useLoad(() => listCases({ ...values, page }), [values, page]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [copyError, setCopyError] = useState<unknown>(null);
  const [copying, setCopying] = useState(false);
  const editable = canEditCase(role);

  const copy = async () => {
    setCopying(true);
    setCopyError(null);
    try {
      const copies = await copyCases([...selected]);
      toast(`Созданы копии: ${copies.items.map((item) => item.key).join(', ')}`);
      setSelected(new Set());
      cases.reload();
    } catch (error) {
      setCopyError(error);
    } finally {
      setCopying(false);
    }
  };

  return (
    <>
      <h2>Тест-кейсы</h2>
      <FilterBar fields={caseFilterFields(classifiers.data)} values={values} onChange={setFilter} onReset={reset} />
      {editable && (
        <div className="bar">
          <Link className="btn primary" to="/test-cases/new">Создать кейс</Link>
          <button type="button" disabled={!selected.size || copying} onClick={copy}>Копировать выбранные ({selected.size})</button>
        </div>
      )}
      <ErrorMessage error={copyError} />
      <div className="panel">
        <DataTable
          columns={COLUMNS}
          rows={cases.data?.items}
          rowKey={(row) => row.id}
          onOpen={(row) => navigate(`/test-cases/${row.id}`)}
          loading={cases.loading}
          error={cases.error}
          onRetry={cases.reload}
          emptyText="По фильтру кейсов нет"
          selection={editable ? { selected, onChange: setSelected } : undefined}
        />
        {cases.data && <p className="muted" style={{ margin: '8px 0 0' }}>На странице: {cases.data.items.length}</p>}
        {cases.data && <Pagination page={page} totalPages={cases.data.totalPages} onChange={setPage} />}
      </div>
    </>
  );
}
