import { useEffect, useState } from 'react';
import { UserManager, type User } from 'oidc-client-ts';
import { BrowserRouter, NavLink, Navigate, Route, Routes, useNavigate } from 'react-router';
import { ToastProvider } from './components/Toast';
import { ROLE_LABELS } from './labels';
import { isRouteAllowed, menuFor, routes, startPath } from './routes';
import { Login } from './screens/Login';
import { ROLES, SESSION_EXPIRED_EVENT, Session, SessionContext, clearSession, loadSession, sessionRoles, setOidcSession } from './session';

function Shell({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const navigate = useNavigate();
  const roles = sessionRoles(session);
  return (
    <>
      <nav className="side" aria-label="Разделы">
        <h1>QA System</h1>
        <small>{roles.map(role => ROLE_LABELS[role]).join(', ')} · {session.name}</small>
        {roles.length > 0 && menuFor(roles).map((item) => <NavLink key={item.path} to={item.path}>{item.label}</NavLink>)}
        <button type="button" onClick={() => { onLogout(); navigate('/'); }}>Выйти</button>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to={startPath(roles)} replace />} />
          {routes.map((route) => (
            <Route
              key={route.path}
              path={route.path}
              element={roles.length > 0 && isRouteAllowed(route, roles) ? route.element : <p className="error" role="alert">Раздел недоступен для вашей роли</p>}
            />
          ))}
          <Route path="*" element={<p className="empty">Страница не найдена</p>} />
        </Routes>
      </main>
    </>
  );
}

function fromUser(user: User) {
  const payload = user.access_token.split('.')[1];
  const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
  const claims = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(base64), c => c.charCodeAt(0))));
  const values: unknown = claims.resource_access?.['qa-system']?.roles;
  const roles = Array.isArray(values) && values.every(role => typeof role === 'string')
    ? ROLES.filter(role => values.includes(role)) : [];
  return { roles, subject: user.profile.sub, accessToken: user.access_token, name: user.profile.sub };
}

export function App() {
  const [profile, setProfile] = useState<{ accountUserId: string; displayName: string }>();
  const [session, setSession] = useState<Session | null>(null);
  const [manager, setManager] = useState<UserManager | null>(null);
  const [demo, setDemo] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    let oidc: UserManager | undefined;
    const expire = () => { clearSession(); setSession(null); };
    const loadUser = (user: User) => {
      if (!active) return;
      const next = fromUser(user);
      setOidcSession(next);
      setSession(next);
      if (next.roles.length) void fetch('/api/v1/profile', { headers: { Authorization: 'Bearer ' + next.accessToken } })
        .then(result => result.ok ? result.json() : null)
        .then(value => { if (active && value?.accountUserId === next.subject) setProfile(value); })
        .catch(() => {});
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, expire);
    const start = async () => {
      const response = await fetch('/api/v1/auth/config');
      if (!response.ok) throw new Error('Не удалось получить настройки входа.');
      const config = await response.json();
      if (!active) return;
      if (config.mode === 'demo') {
        setDemo(true);
        setSession(loadSession());
        return;
      }
      if (config.mode !== 'keycloak') throw new Error('Неизвестный режим входа.');
      clearSession();
      oidc = new UserManager({
        authority: config.issuer,
        client_id: config.clientId,
        redirect_uri: location.origin + '/auth/callback',
        response_type: 'code',
        scope: 'openid profile email',
        automaticSilentRenew: true,
        loadUserInfo: false,
      });
      oidc.events.addUserLoaded(loadUser);
      oidc.events.addAccessTokenExpired(expire);
      if (location.pathname === '/auth/callback') {
        const user = await oidc.signinRedirectCallback();
        const returnTo = typeof user.state === 'string' && /^\/(?!\/)/.test(user.state) ? user.state : '/';
        history.replaceState(null, '', returnTo);
        loadUser(user);
      } else {
        const user = await oidc.getUser();
        if (user && !user.expired) loadUser(user);
      }
      if (active) setManager(oidc);
    };
    void start().catch(() => { if (active) setError('Не удалось войти через Keycloak. Обновите страницу.'); });
    return () => {
      active = false;
      oidc?.stopSilentRenew();
      oidc?.events.removeUserLoaded(loadUser);
      oidc?.events.removeAccessTokenExpired(expire);
      window.removeEventListener(SESSION_EXPIRED_EVENT, expire);
    };
  }, []);

  function logout() {
    clearSession();
    setSession(null);
    if (manager) void manager.signoutRedirect().catch(() => setError('Не удалось завершить сессию Keycloak.'));
  }

  return (
    <BrowserRouter>
      <ToastProvider>
        {error && <p className="error" role="alert">{error}</p>}
        {session ? (
          <SessionContext.Provider value={session}>
            <Shell session={'subject' in session && profile?.accountUserId === session.subject ? { ...session, name: profile.displayName } : session} onLogout={logout} />
          </SessionContext.Provider>
        ) : demo ? (
          <Login onLogin={setSession} />
        ) : manager ? (
          <main><h1>QA System</h1><button type="button" onClick={() => void manager.signinRedirect({
            state: location.pathname + location.search,
          }).catch(() => setError('Keycloak недоступен.'))}>Войти через Keycloak</button></main>
        ) : !error && <p role="status">Загрузка настроек входа…</p>}
      </ToastProvider>
    </BrowserRouter>
  );
}
