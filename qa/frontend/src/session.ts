import { createContext, useContext } from 'react';

// Демо-сессия используется на изолированном стенде.
export const ROLES = ['qa-lead', 'qa-tester', 'qa-automation', 'qa-viewer', 'qa-admin'] as const;
export type Role = (typeof ROLES)[number];
type DemoSession = { role: Role; name: string };
export type OidcSession = { roles: Role[]; name: string; subject: string; accessToken: string };
export type Session = DemoSession | OidcSession;
export type RoleSelection = Role | readonly Role[];

export function hasRole(roles: RoleSelection, ...wanted: Role[]): boolean {
  return Array.isArray(roles) ? wanted.some(role => roles.includes(role)) : wanted.some(role => role === roles);
}

export function sessionRoles(session: Session): Role[] {
  return 'roles' in session ? session.roles : [session.role];
}

export function sessionSubject(session: Session): string {
  return 'subject' in session ? session.subject : session.name;
}

let oidcSession: OidcSession | null = null;

export function setOidcSession(session: OidcSession | null): void {
  oidcSession = session;
}

const STORAGE_KEY = 'qa.session';
// Токен уходит в заголовок: fetch не принимает в нём кириллицу, а «@» разделяет роль и имя.
const NAME_PATTERN = /^[A-Za-z0-9._-]{1,64}$/;
export const SESSION_EXPIRED_EVENT = 'qa:session-expired';

export function isValidName(name: string): boolean {
  return NAME_PATTERN.test(name);
}

export function tokenOf(session: Session): string {
  return 'accessToken' in session ? session.accessToken : `demo-${session.role}@${session.name}`;
}

export function loadSession(): Session | null {
  if (oidcSession) return oidcSession;
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null') as DemoSession | null;
    return saved && ROLES.includes(saved.role) && isValidName(saved.name) ? saved : null;
  } catch {
    return null;
  }
}

export function saveSession(session: DemoSession): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  oidcSession = null;
  localStorage.removeItem(STORAGE_KEY);
}

export const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error('Нет сессии: компонент вне входа');
  return session;
}
