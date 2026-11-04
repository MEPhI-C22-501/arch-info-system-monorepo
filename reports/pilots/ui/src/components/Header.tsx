import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { logout } from '../auth';
import { abilities, useSession } from '../session';

export function Header({ unread }: { unread: number }) {
  const session = useSession();
  const can = abilities(session);
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return (
    <header className="header">
      <a className="skip-link" href="#main">Перейти к содержимому</a>
      <NavLink to="/" className="brand" onClick={close}>Reports</NavLink>
      <button type="button" className="menu-toggle" aria-expanded={open} aria-controls="main-nav" onClick={() => setOpen(!open)}>
        Меню
      </button>
      <nav id="main-nav" aria-label="Основная навигация" className={open ? 'nav nav-open' : 'nav'}>
        {can.reports && <NavLink to="/" end onClick={close}>Каталог</NavLink>}
        {can.reports && <NavLink to="/dashboards" onClick={close}>Дашборды</NavLink>}
        {can.reports && <NavLink to="/exports" onClick={close}>Выгрузки</NavLink>}
        {can.subscriptions && <NavLink to="/subscriptions" onClick={close}>Подписки</NavLink>}
        <NavLink to="/freshness" onClick={close}>Актуальность</NavLink>
        {can.audit && <NavLink to="/audit" onClick={close}>Аудит</NavLink>}
        <NavLink to="/notifications" onClick={close} aria-label={unread ? `Уведомления, непрочитанных: ${unread}` : 'Уведомления'}>
          Уведомления{unread > 0 && <span className="badge" aria-hidden="true">{unread}</span>}
        </NavLink>
      </nav>
      <div className="profile">
        <span className="user" title={session.subject}>{session.name}</span>
        <button type="button" className="secondary" onClick={logout}>Выйти</button>
      </div>
    </header>
  );
}
