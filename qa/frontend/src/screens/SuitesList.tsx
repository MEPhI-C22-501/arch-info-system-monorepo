import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { Suite, changeSuiteStatus, listSuites } from '../api/suites';
import { Column, DataTable } from '../components/DataTable';
import { ErrorMessage } from '../components/ErrorMessage';
import { FilterBar } from '../components/FilterBar';
import { Pagination } from '../components/Pagination';
import { StatusBadge } from '../components/StatusBadge';
import { useToast } from '../components/Toast';
import { KIND_LABELS, PURPOSE_LABELS } from '../labels';
import { canArchiveSuite, canCreateRun, canManageSuites } from '../permissions';
import { useSession } from '../session';
import { useListParams } from '../useListParams';
import { useLoad } from '../useLoad';

export const SMOKE_EMPTY_HINT = 'В «Smoke» попадают только автоматизированные кейсы, а автотестов пока нет.';

export function isEmptySmoke(suite: Pick<Suite, 'purpose' | 'caseCount'>): boolean {
  return suite.purpose === 'SMOKE' && suite.caseCount === 0;
}

export function SuitesList() {
  const session = useSession();
  const navigate = useNavigate();
  const toast = useToast();
  const { values, page, setFilter, setPage, reset } = useListParams();
  const suites = useLoad(() => listSuites({ ...values, page }), [values, page]);
  const [error, setError] = useState<unknown>(null);

  const change = async (suite: Suite, action: 'archive' | 'restore') => {
    setError(null);
    try {
      await changeSuiteStatus(suite.id, action);
      toast(action === 'archive' ? `Набор «${suite.name}» в архиве` : `Набор «${suite.name}» возвращён`);
      suites.reload();
    } catch (failure) {
      setError(failure);
    }
  };

  const columns: Column<Suite>[] = [
    {
      header: 'Набор',
      render: (row) => (
        <>
          {row.name}
          {isEmptySmoke(row) && <div className="muted">{SMOKE_EMPTY_HINT}</div>}
        </>
      ),
    },
    { header: 'Вид', render: (row) => KIND_LABELS[row.kind] },
    { header: 'Назначение', render: (row) => PURPOSE_LABELS[row.purpose] },
    { header: 'Кейсов', render: (row) => row.caseCount },
    { header: 'Владелец', render: (row) => row.owner },
    { header: 'Статус', render: (row) => <StatusBadge status={row.status} /> },
    {
      header: 'Действия',
      render: (row) => (
        <div className="bar" style={{ marginBottom: 0 }}>
          {row.status === 'ACTIVE' && canCreateRun(session.role) && <Link className="btn" to={`/runs/new?suiteId=${row.id}`}>Создать прогон</Link>}
          {canArchiveSuite(session, row) && (row.status === 'ACTIVE'
            ? <button type="button" onClick={() => change(row, 'archive')}>В архив</button>
            : <button type="button" onClick={() => change(row, 'restore')}>Вернуть</button>)}
        </div>
      ),
    },
  ];

  return (
    <>
      <h2>Наборы</h2>
      <FilterBar
        fields={[
          { name: 'status', label: 'Статус', type: 'select', emptyLabel: 'Все', options: [{ value: 'ACTIVE', label: 'Активен' }, { value: 'ARCHIVED', label: 'В архиве' }] },
          { name: 'kind', label: 'Вид', type: 'select', emptyLabel: 'Все', options: Object.entries(KIND_LABELS).map(([value, label]) => ({ value, label })) },
          { name: 'purpose', label: 'Назначение', type: 'select', emptyLabel: 'Все', options: Object.entries(PURPOSE_LABELS).map(([value, label]) => ({ value, label })) },
        ]}
        values={values}
        onChange={setFilter}
        onReset={reset}
      />
      {canManageSuites(session.role) && <div className="bar"><Link className="btn primary" to="/suites/new">Создать набор</Link></div>}
      <ErrorMessage error={error} />
      <div className="panel">
        <DataTable
          columns={columns}
          rows={suites.data?.items}
          rowKey={(row) => row.id}
          onOpen={(row) => navigate(`/suites/${row.id}`)}
          loading={suites.loading}
          error={suites.error}
          onRetry={suites.reload}
          emptyText="Наборов нет"
        />
        {suites.data && <Pagination page={page} totalPages={suites.data.totalPages} onChange={setPage} />}
      </div>
    </>
  );
}
