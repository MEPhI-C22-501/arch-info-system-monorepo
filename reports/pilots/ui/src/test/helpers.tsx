import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi } from 'vitest';
import type { Session } from '../auth';
import { SessionContext } from '../session';

export function session(roles: string[], subject = '11111111-1111-4111-8111-111111111111'): Session {
  return { token: 'test-token', subject, name: 'tester', roles: new Set(roles), expiresAt: Date.now() + 3600_000 };
}

/** Fake Reports API: 'METHOD path' or path (without /api/v1/) -> [status, body]. Unknown paths answer 404. */
export function mockApi(routes: Record<string, [number, unknown]>) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = String(input).replace('/api/v1/', '').split('?')[0];
    const [status, body] = routes[`${init?.method ?? 'GET'} ${path}`] ?? routes[path] ?? [404, { code: 'NOT_FOUND' }];
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  });
}

export function renderAt(element: ReactElement, roles: string[], path = '/', pattern = '*') {
  return render(
    <SessionContext.Provider value={session(roles)}>
      <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes><Route path={pattern} element={element} /></Routes>
      </MemoryRouter>
    </SessionContext.Provider>,
  );
}
