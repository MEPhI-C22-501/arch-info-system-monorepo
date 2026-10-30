import { createContext, useContext } from 'react';

// Демо-вход: пока Keycloak не подключён (TECH-09), токен собирается из роли и имени.
export const ROLES = ['qa-lead', 'qa-tester', 'qa-automation', 'qa-viewer', 'qa-admin'] as const;
export type Role = (typeof ROLES)[number];
export type Session = { role: Role; name: string };

const STORAGE_KEY = 'qa.session';
// Токен уходит в заголовок: fetch не принимает в нём кириллицу, а «@» разделяет роль и имя.
const NAME_PATTERN = /^[A-Za-z0-9._-]{1,64}$/;
export const SESSION_EXPIRED_EVENT = 'qa:session-expired';

export function isValidName(name: string): boolean {
  return NAME_PATTERN.test(name);
}

export function tokenOf(session: Session): string {
  return `demo-${session.role}@${session.name}`;
}

export function loadSession(): Session | null {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null') as Session | null;
    return saved && ROLES.includes(saved.role) && isValidName(saved.name) ? saved : null;
  } catch {
    return null;
  }
}

export function saveSession(session: Session): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error('Нет сессии: компонент вне входа');
  return session;
}
