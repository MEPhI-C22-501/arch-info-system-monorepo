import { Link } from 'react-router-dom';
import { api, errorMessage } from '../api';
import { Empty, Failure, Loading } from '../components/State';
import { abilities, useSession } from '../session';
import type { Page, ReportDefinition } from '../types';
import { useLoad } from '../useLoad';

export const SUPERSET = 'http://localhost:8088';

// A dashboard is shown when the user may read its main report; the API checks every block again.
const DASHBOARDS = [
  { path: 'iteration', report: 'R-03', title: 'Оперативный дашборд итерации', text: 'Задачи по статусам, просрочка, остаток часов и завершения по неделям.' },
  { path: 'plan-fact', report: 'R-06', title: 'План-факт', text: 'План, факт, остаток и прогноз проекта, часы по неделям и сотрудникам.' },
  { path: 'quality', report: 'R-07', title: 'Качество', text: 'Pass rate, выполнение тест-плана, плотность и переоткрытия дефектов, динамика дефектов.' },
];

export function Dashboards() {
  const session = useSession();
  const catalog = useLoad(() => api<Page<ReportDefinition>>(session.token, 'reports'), [session.token]);
  if (catalog.loading) return <Loading />;
  if (catalog.error) return <Failure message={errorMessage(catalog.error)} onRetry={catalog.reload} />;
  const available = new Set(catalog.data!.items.map((r) => r.reportId));
  const shown = DASHBOARDS.filter((d) => available.has(d.report));
  return (
    <>
      <h1>Дашборды</h1>
      {!shown.length ? <Empty>Для вашей роли дашбордов нет.</Empty> : (
        <ul className="card-grid">
          {shown.map((d) => (
            <li key={d.path} className="card">
              <Link to={'/dashboards/' + d.path} className="card-title">{d.title}</Link>
              <p className="muted">{d.text}</p>
            </li>
          ))}
        </ul>
      )}
      {abilities(session).explore && (
        <section aria-labelledby="explore-title">
          {/* SCR-07: Superset is the analyst's channel (ADR-019); other roles do not sign in there. */}
          <h2 id="explore-title">Исследование куба в Superset</h2>
          <p className="muted">Для аналитика: свободный выбор мер, измерений и фильтров. Вход тем же пользователем Keycloak.</p>
          <ul className="button-row">
            <li><a className="button" href={SUPERSET + '/chart/add'} target="_blank" rel="noopener noreferrer">Новый срез куба</a></li>
            <li><a className="button secondary" href={SUPERSET + '/superset/dashboard/reports-r06/'} target="_blank" rel="noopener noreferrer">Дашборд R-06 в Superset</a></li>
          </ul>
        </section>
      )}
    </>
  );
}
