import { Link, useNavigate, useParams } from 'react-router';
import { TestCase, listCases } from '../api/cases';
import { getSuite } from '../api/suites';
import { describeCaseFilter } from '../caseFilter';
import { Column, DataTable } from '../components/DataTable';
import { ErrorMessage } from '../components/ErrorMessage';
import { Prop } from '../components/Field';
import { Pagination } from '../components/Pagination';
import { StatusBadge } from '../components/StatusBadge';
import { KIND_LABELS, PURPOSE_LABELS } from '../labels';
import { canCreateRun } from '../permissions';
import { useSession } from '../session';
import { useListParams } from '../useListParams';
import { useLoad } from '../useLoad';
import { SMOKE_EMPTY_HINT, isEmptySmoke } from './SuitesList';

const COLUMNS: Column<TestCase>[] = [
  { header: 'Ключ', render: (row) => row.key },
  { header: 'Название', render: (row) => row.title },
  { header: 'Вид', render: (row) => (row.automated ? 'Авто' : 'Ручной') },
  { header: 'Статус', render: (row) => <StatusBadge status={row.status} /> },
];

export function SuiteCard() {
  const { id = '' } = useParams();
  const { role } = useSession();
  const navigate = useNavigate();
  const { page, setPage } = useListParams();
  const suite = useLoad(() => getSuite(id), [id]);
  const cases = useLoad(() => listCases({ suiteId: id, page }), [id, page]);

  if (!suite.data) return suite.error ? <ErrorMessage error={suite.error} onRetry={suite.reload} /> : <p className="muted" aria-busy="true">Загрузка…</p>;
  const current = suite.data;

  return (
    <>
      <div className="bar"><Link className="btn" to="/suites">← К списку</Link></div>
      <h2>{current.name} <StatusBadge status={current.status} /></h2>
      {current.status === 'ACTIVE' && canCreateRun(role) && (
        <div className="bar"><Link className="btn primary" to={`/runs/new?suiteId=${current.id}`}>Создать прогон</Link></div>
      )}
      <div className="panel">
        <dl className="props">
          <Prop name="Вид">{KIND_LABELS[current.kind]}</Prop>
          <Prop name="Назначение">{PURPOSE_LABELS[current.purpose]}</Prop>
          <Prop name="Владелец">{current.owner}</Prop>
          {current.kind === 'FILTER' && <Prop name="Условие">{describeCaseFilter(current.filter)}</Prop>}
          <Prop name="Кейсов сейчас">{String(current.caseCount)}</Prop>
        </dl>
      </div>
      <div className="panel">
        <h3>Состав</h3>
        <DataTable
          columns={COLUMNS}
          rows={cases.data?.items}
          rowKey={(row) => row.id}
          onOpen={(row) => navigate(`/test-cases/${row.id}`)}
          loading={cases.loading}
          error={cases.error}
          onRetry={cases.reload}
          emptyText={isEmptySmoke(current) ? SMOKE_EMPTY_HINT : 'В наборе нет кейсов'}
        />
        {cases.data && <Pagination page={page} totalPages={cases.data.totalPages} onChange={setPage} />}
      </div>
    </>
  );
}
