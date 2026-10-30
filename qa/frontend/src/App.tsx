import { useEffect, useState } from 'react';
import { BrowserRouter, NavLink, Navigate, Route, Routes, useNavigate } from 'react-router';
import { ToastProvider } from './components/Toast';
import { ROLE_LABELS } from './labels';
import { isRouteAllowed, menuFor, routes, startPath } from './routes';
import { Login } from './screens/Login';
import { SESSION_EXPIRED_EVENT, Session, SessionContext, clearSession, loadSession } from './session';

function Shell({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const navigate = useNavigate();
  return (
    <>
      <nav className="side" aria-label="Разделы">
        <h1>QA System</h1>
        <small>{ROLE_LABELS[session.role]} · {session.name}</small>
        {menuFor(session.role).map((item) => <NavLink key={item.path} to={item.path}>{item.label}</NavLink>)}
        <button type="button" onClick={() => { onLogout(); navigate('/'); }}>Выйти</button>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to={startPath(session.role)} replace />} />
          {routes.map((route) => (
            <Route
              key={route.path}
              path={route.path}
              element={isRouteAllowed(route, session.role) ? route.element : <p className="error" role="alert">Раздел недоступен для вашей роли</p>}
            />
          ))}
          <Route path="*" element={<p className="empty">Страница не найдена</p>} />
        </Routes>
      </main>
    </>
  );
}

export function App() {
  const [session, setSession] = useState<Session | null>(loadSession);

  useEffect(() => {
    const expire = () => setSession(null);
    window.addEventListener(SESSION_EXPIRED_EVENT, expire);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expire);
  }, []);

  return (
    <BrowserRouter>
      <ToastProvider>
        {session ? (
          <SessionContext.Provider value={session}>
            <Shell key={`${session.role}@${session.name}`} session={session} onLogout={() => { clearSession(); setSession(null); }} />
          </SessionContext.Provider>
        ) : (
          <Login onLogin={setSession} />
        )}
      </ToastProvider>
    </BrowserRouter>
  );
}
