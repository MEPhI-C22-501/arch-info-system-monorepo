import type { Priority, Status, User } from './api';

export type Context = {
  statuses: Status[]; priorities: Priority[]; users: User[]; roles: string[]; userId: string;
  permissions: string[]; types: Array<{ type: string; enabled: boolean }>;
};

export const emptyContext: Context = { statuses: [], priorities: [], users: [], roles: [], userId: '', permissions: [], types: [] };

export const can = (context: Context, permission: string) => context.permissions.includes(permission);

export const selectName = (rows: Array<{ id: string; name: string }>, id: string | null) => rows.find(row => row.id === id)?.name || '—';

export const selectPerson = (rows: User[], id: string | null) => id
  ? rows.find(row => row.id === id)?.name || `Профиль не найден (${id})` : '—';
