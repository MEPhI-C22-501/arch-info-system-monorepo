import { useCallback, useEffect, useState } from 'react';
import { auth, date, request } from './api';
import type { Status, Priority, User } from './api';
import { can, emptyContext, selectName } from './context';
import type { Context } from './context';
import { Backlog } from './screens/Backlog';
import { Board } from './screens/Board';
import { Iterations } from './screens/Iterations/Iterations';
import { Notifications } from './screens/Notifications';
import { Admin } from './screens/Admin';
import { ItemDialog } from './screens/ItemDialog/ItemDialog';

type Screen = 'backlog' | 'board' | 'iterations' | 'notifications' | 'admin';
const getError = (e: unknown): string => (e instanceof Error ? e.message : 'Неизвестная ошибка');

export function App() {
  const [ready, setReady] = useState(false);
  const [context, setContext] = useState<Context>(emptyContext);
  const [screen, setScreen] = useState<Screen>('backlog');
  const [selected, setSelected] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState('');
  const refresh = useCallback(() => setRevision(value => value + 1), []);
  const reloadContext = useCallback(async () => {
    const [me, statuses, priorities, users, types] = await Promise.all([
      request<{ role: string; userId: string; permissions: string[] }>('/me'), request<Status[]>('/statuses'),
      request<Priority[]>('/priorities'), request<User[]>('/users'), request<Context['types']>('/types'),
    ]);
    setContext({ ...me, statuses, priorities, users, types });
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        if (location.pathname === '/auth/callback') {
          await auth.signinRedirectCallback();
          history.replaceState({}, '', '/');
        }
        const user = await auth.getUser();
        if (!user || user.expired) { await auth.signinRedirect(); return; }
        await reloadContext();
        if (!cancelled) setReady(true);
      } catch (e) { if (!cancelled) setError(getError(e)); }
    })();
    return () => { cancelled = true; };
  }, [reloadContext]);

  if (!ready) {
    return <main className="startup"><div className="spinner" /><h1>Task Tracker</h1><p>{error || 'Загрузка рабочего пространства…'}</p>
      {error && <button onClick={() => void auth.signinRedirect()}>Войти снова</button>}</main>;
  }

  const titles: Record<Screen, string> = { backlog: 'Бэклог', board: 'Канбан-доска', iterations: 'Итерации', notifications: 'Уведомления', admin: 'Администрирование' };
  const nav: Array<[Screen, string]> = [['backlog', '▤'], ['board', '▥'], ['iterations', '◷'], ['notifications', '◉'], ['admin', '⚙']];
  const visible = ([key]: [Screen, string]) => key === 'admin'
    ? ['access.admin', 'status.admin', 'priority.admin', 'type.admin', 'directory.admin'].some(permission => can(context, permission))
    : key === 'iterations' ? can(context, 'iteration.read')
    : key === 'notifications' ? can(context, 'notifications.read')
    : can(context, 'item.read');

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-icon">T</span><div><strong>Task Tracker</strong><small>Рабочее пространство</small></div></div>
      <nav aria-label="Основная навигация">{nav.filter(visible).map(([key, icon]) =>
        <button key={key} className={`nav-link ${screen === key ? 'active' : ''}`} onClick={() => { setScreen(key); setSelected(null); }}><span>{icon}</span>{titles[key]}</button>)}</nav>
      <div className="sidebar-footer"><div className="avatar">{context.role.charAt(0)}</div><div><strong>{selectName(context.users, context.userId)}</strong><small>{context.role}</small></div>
        <button title="Выйти" onClick={() => void auth.signoutRedirect()}>↗</button></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><span className="eyebrow">КОМАНДНАЯ РАБОТА</span><h1>{titles[screen]}</h1></div><span className="today">{date(new Date().toISOString())}</span></header>
      {screen === 'backlog' && <Backlog context={context} revision={revision} open={setSelected} refresh={refresh} />}
      {screen === 'board' && <Board context={context} revision={revision} open={setSelected} refresh={refresh} />}
      {screen === 'iterations' && <Iterations context={context} revision={revision} open={setSelected} refresh={refresh} />}
      {screen === 'notifications' && <Notifications open={setSelected} revision={revision} refresh={refresh} />}
      {screen === 'admin' && <Admin context={context} refreshAll={() => { void reloadContext(); refresh(); }} />}
    </main>
    {selected && <ItemDialog id={selected} context={context} close={() => setSelected(null)} open={setSelected} refresh={refresh} />}
  </div>;
}
