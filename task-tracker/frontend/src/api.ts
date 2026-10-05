import { UserManager } from 'oidc-client-ts';

export type Json = Record<string, unknown>;
export type Item = {
  id: string; type: string; title: string; description: string; statusId: string; priorityId: string;
  assigneeId: string | null; startDate: string | null; dueDate: string | null;
  plannedHours: number; actualHours: number; remainingHours: number; unestimatedLeaves: number;
  parentId: string | null; iterationId: string | null; version: number;
  children: Array<{ id: string; type: string; title: string }>;
};
export type Iteration = {
  id: string; name: string; description: string; startDate: string; endDate: string; state: string;
  items: Item[]; statusCounts: Record<string, number>; plannedHours: number; actualHours: number; remainingHours: number;
  capacity: Array<{ userId: string; availableHours: number; plannedHours: number; actualHours: number; reserveHours: number; overloaded: boolean }>;
  teamCapacityHours: number; teamReserveHours: number; completionFraction: number; completedCount: number; warnings: string[];
  baseline: Json; result: Json;
};
export type Status = { id: string; name: string; boardOrder: number; active: boolean; boardVisible: boolean; category: string };
export type Priority = { id: string; name: string; sortOrder: number; active: boolean; code: string | null };
export type User = { id: string; name: string; teamId: string | null; departmentId: string | null; active: boolean };

const authority = import.meta.env.VITE_OIDC_AUTHORITY || 'http://localhost:8081/realms/arch-info-system';
export const auth = new UserManager({
  authority,
  client_id: import.meta.env.VITE_OIDC_CLIENT_ID || 'task-tracker',
  redirect_uri: `${window.location.origin}/auth/callback`,
  post_logout_redirect_uri: window.location.origin,
  response_type: 'code',
  scope: 'openid profile',
});

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const user = await auth.getUser();
  const headers = new Headers(init.headers);
  if (user?.access_token) headers.set('Authorization', `Bearer ${user.access_token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api/v1${path}`, { ...init, headers });
  if (response.status === 401) { await auth.signinRedirect(); throw new Error('Требуется вход'); }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const details = body?.errors?.map((error: { row?: number; field: string; reason: string }) => `${error.row ? `Строка ${error.row}, ` : ''}${error.field}: ${error.reason}`).join('; ');
    throw new Error(details || `Ошибка запроса ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  if (response.headers.get('content-type')?.includes('application/vnd.openxmlformats')) return (await response.blob()) as T;
  return response.json() as Promise<T>;
}
export const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });
export const date = (value: unknown): string => value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeZone: 'Europe/Moscow' }).format(new Date(String(value))) : '—';
export const dateTime = (value: unknown): string => value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short', timeZone: 'Europe/Moscow' }).format(new Date(String(value))) : '—';
export const hours = (value: unknown): string => `${Number(value ?? 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ч`;
export const typeName = (type: string): string => ({ PROJECT: 'Проект', EPIC: 'Эпик', TASK: 'Задача', BUG: 'Ошибка', SUBTASK: 'Подзадача' }[type] || type);
