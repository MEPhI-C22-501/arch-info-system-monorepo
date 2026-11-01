import type { Priority, Status, User } from './api';

export type Context = {
  statuses: Status[]; priorities: Priority[]; users: User[]; role: string; userId: string;
  permissions: string[]; types: Array<{ type: string; enabled: boolean }>;
};

export const emptyContext: Context = { statuses: [], priorities: [], users: [], role: '', userId: '', permissions: [], types: [] };

export const can = (context: Context, permission: string) => context.permissions.includes(permission);

export const selectName = (rows: Array<{ id: string; name: string }>, id: string | null) => rows.find(row => row.id === id)?.name || '—';
