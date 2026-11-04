import { useEffect, useState } from 'react';
import { Route, Routes } from 'react-router-dom';
import { api, downloadBlob, errorMessage, setUnauthorizedHandler } from './api';
import { login, type Session } from './auth';
import { Header } from './components/Header';
import { Failure } from './components/State';
import { Audit } from './pages/Audit';
import { Catalog } from './pages/Catalog';
import { Exports } from './pages/Exports';
import { Freshness } from './pages/Freshness';
import { Notifications } from './pages/Notifications';
import { ReportPage } from './pages/ReportPage';
import { Subscriptions } from './pages/Subscriptions';
import { abilities, SessionContext, useSession } from './session';
import type { ExportJob, Notification } from './types';
import { useLoad } from './useLoad';

export const SNAPSHOT = 'reports.snapshot';

/** The login callback is completed in main.tsx before the router starts, so the router sees the final address. */
export function App({ initialSession, initialError }: { initialSession: Session | null; initialError: string }) {
  const [session, setSession] = useState<Session | null>(initialSession);
  useEffect(() => setUnauthorizedHandler(() => setSession(null)), []);

  if (!session) {
    const returnTo = window.location.pathname.replace(/^\/ui/, '') + window.location.search;
    return (
      <main id="main" className="login">
        <h1>Reports</h1>
        <p>Отчёты по трудозатратам, срокам, ресурсам и качеству. Доступ определяется вашей ролью.</p>
        {initialError && <Failure message={initialError} />}
        <button type="button" onClick={() => login(returnTo || '/')}>Войти через Keycloak</button>
      </main>
    );
  }
  return (
    <SessionContext.Provider value={session}>
      <Shell />
    </SessionContext.Provider>
  );
}

function Shell() {
  const session = useSession();
  const can = abilities(session);
  const notifications = useLoad(() => api<{ items: Notification[] }>(session.token, 'notifications'), [session.token]);
  const unread = (notifications.data?.items ?? []).filter((n) => !n.readAt).length;
  const [snapshotError, setSnapshotError] = useState('');

  useEffect(() => {
    const timer = setInterval(notifications.reload, 60000);
    return () => clearInterval(timer);
  }, [notifications]);

  // A /snapshots/<id> link from a scheduled-report event downloads the file after login.
  useEffect(() => {
    const id = sessionStorage.getItem(SNAPSHOT);
    if (!id) return;
    sessionStorage.removeItem(SNAPSHOT);
    api<ExportJob>(session.token, 'exports/' + id)
      .then(async (job) => downloadBlob(await api<Blob>(session.token, `exports/${id}/file`), `${job.reportId}-${id}.${job.format}`))
      .catch((e) => setSnapshotError(errorMessage(e)));
  }, [session.token]);

  return (
    <>
      <Header unread={unread} />
      <main id="main" tabIndex={-1}>
        {snapshotError && <Failure message={'Файл регламентного отчёта недоступен. ' + snapshotError} />}
        {!can.reports && !can.audit && <Failure message="У вашей учётной записи нет роли Reports. Обратитесь к администратору." />}
        <Routes>
          {/* RL-06 has no catalog (110, section 4); its start screen is data freshness. */}
          <Route path="/" element={can.reports ? <Catalog /> : <Freshness />} />
          <Route path="/reports/:reportId" element={<ReportPage />} />
          <Route path="/exports" element={<Exports />} />
          <Route path="/subscriptions" element={<Subscriptions />} />
          <Route path="/notifications" element={<Notifications notifications={notifications} />} />
          <Route path="/freshness" element={<Freshness />} />
          <Route path="/audit" element={<Audit />} />
          <Route path="*" element={<Failure message="Страница не найдена." />} />
        </Routes>
      </main>
    </>
  );
}
