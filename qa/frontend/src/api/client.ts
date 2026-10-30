import { SESSION_EXPIRED_EVENT, clearSession, loadSession, tokenOf } from '../session';
import type { components } from './schema';

const BASE = '/api/v1';

export type ErrorItem = { field?: string; reason?: string };
export type Page<T> = { items: T[]; page: number; pageSize: number; totalPages: number };
export type QueryValue = string | number | boolean | null | undefined;
export type Severity = components['schemas']['Severity'];

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly errors: ErrorItem[];
  readonly correlationId?: string;

  constructor(status: number, code: string, message: string, errors: ErrorItem[] = [], correlationId?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.errors = errors;
    this.correlationId = correlationId;
  }
}

async function errorFrom(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => null);
  if (body && typeof body.code === 'string') {
    return new ApiError(response.status, body.code, String(body.message ?? ''), Array.isArray(body.errors) ? body.errors : [], body.correlationId);
  }
  return new ApiError(response.status, `HTTP_${response.status}`, 'Сервер вернул неожиданный ответ');
}

export async function request<T>(method: string, path: string, body?: unknown, headers?: Record<string, string>): Promise<T> {
  const session = loadSession();
  const init: RequestInit = {
    method,
    headers: {
      ...(session ? { Authorization: `Bearer ${tokenOf(session)}` } : {}),
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  };
  let response: Response;
  try {
    response = await fetch(BASE + path, init);
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'Сервер недоступен');
  }
  if (!response.ok) {
    const error = await errorFrom(response);
    if (response.status === 401) {
      clearSession();
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    throw error;
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export function withQuery(path: string, query: Record<string, QueryValue>): string {
  const params = new URLSearchParams();
  for (const [name, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') params.set(name, String(value));
  }
  const text = params.toString();
  return text ? `${path}?${text}` : path;
}

export const MAX_PAGE_SIZE = 200;

// Все страницы справочного списка: для выпадающих списков и поиска результата прогона.
export async function loadAll<T>(fetchPage: (page: number) => Promise<Page<T>>): Promise<T[]> {
  const items: T[] = [];
  for (let page = 1; ; page++) {
    const result = await fetchPage(page);
    items.push(...result.items);
    if (page >= result.totalPages) return items;
  }
}
