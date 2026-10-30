import { cleanup, render } from '@testing-library/react';
import { ReactElement } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, vi } from 'vitest';
import { ToastProvider } from '../components/Toast';
import { Role, Session, SessionContext, saveSession } from '../session';

afterEach(() => {
  cleanup();
  localStorage.clear();
});

export type Call = { method: string; url: string; body: unknown; headers: Record<string, string> };
type Reply = { status?: number; body?: unknown };
type Handler = (call: Call) => Reply | undefined;

// Подменяет fetch: первый обработчик, вернувший ответ, отвечает; неизвестный запрос — 404.
export function mockFetch(handler: Handler): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const call: Call = {
      method: init.method ?? 'GET',
      url,
      body: init.body ? JSON.parse(init.body as string) : undefined,
      headers: init.headers as Record<string, string>,
    };
    calls.push(call);
    const reply = handler(call);
    const status = reply?.status ?? (reply ? 200 : 404);
    const body = reply ? reply.body : { code: 'NOT_FOUND', message: `нет обработчика ${call.method} ${url}`, errors: [] };
    return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  }));
  return calls;
}

export const page = <T,>(items: T[]) => ({ body: { items, page: 1, pageSize: 50, totalPages: items.length ? 1 : 0 } });

export function renderScreen(element: ReactElement, options: { role?: Role; name?: string; path?: string; pattern?: string } = {}) {
  const session: Session = { role: options.role ?? 'qa-lead', name: options.name ?? 'ivanov' };
  saveSession(session);
  return render(
    <MemoryRouter initialEntries={[options.path ?? '/']}>
      <SessionContext.Provider value={session}>
        <ToastProvider>
          <Routes>
            <Route path={options.pattern ?? '/'} element={element} />
            <Route path="*" element={<div>другой экран</div>} />
          </Routes>
        </ToastProvider>
      </SessionContext.Provider>
    </MemoryRouter>,
  );
}
