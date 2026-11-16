// Authorization Code + PKCE (S256) against Keycloak with the public client reports-ui.
// The access token stays in memory only; sessionStorage holds just the one-time
// state/verifier and the page to return to, removed right after the callback.

export const ISSUER = import.meta.env.VITE_OIDC_ISSUER || 'http://localhost:8180/realms/reports-pilot';
export const CLIENT_ID = import.meta.env.VITE_OIDC_CLIENT_ID || 'reports-ui';
const PENDING = 'reports.pkce';

export const ROLES = {
  projectManager: 'reports-project-manager',
  teamLead: 'reports-team-lead',
  qaLead: 'reports-qa-lead',
  member: 'reports-member',
  analyst: 'reports-analyst',
  admin: 'reports-admin',
} as const;

export interface Session {
  token: string;
  subject: string;
  name: string;
  roles: Set<string>;
  expiresAt: number;
  refreshToken?: string;
}

function randomHex(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(32)), (v) => v.toString(16).padStart(2, '0')).join('');
}

function base64Url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
}

function redirectUri(): string {
  return window.location.origin + '/ui/callback';
}

export async function login(returnTo: string): Promise<void> {
  const state = randomHex();
  const verifier = randomHex();
  sessionStorage.setItem(PENDING, JSON.stringify({ state, verifier, returnTo }));
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  const query = new URLSearchParams({
    client_id: CLIENT_ID, redirect_uri: redirectUri(), response_type: 'code', scope: 'openid profile email',
    state, code_challenge: base64Url(new Uint8Array(digest)), code_challenge_method: 'S256',
  });
  window.location.assign(ISSUER + '/protocol/openid-connect/auth?' + query.toString());
}

export function decodeSession(token: string): Session {
  const part = token.split('.')[1] ?? '';
  const json = atob(part.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(part.length / 4) * 4, '='));
  const claims = JSON.parse(new TextDecoder().decode(Uint8Array.from(json, (c) => c.charCodeAt(0))));
  const roles: unknown = claims?.resource_access?.reports?.roles;
  return {
    token,
    subject: String(claims.sub),
    name: String(claims.preferred_username ?? claims.name ?? claims.sub),
    roles: new Set(Array.isArray(roles) && roles.every(role => typeof role === 'string') ? roles : []),
    expiresAt: Number(claims.exp) * 1000,
  };
}

/** Completes the redirect from Keycloak. Returns the session and the page to open, or null when this is not a callback. */
export async function completeLogin(): Promise<{ session: Session; returnTo: string } | null> {
  if (!window.location.pathname.endsWith('/callback')) return null;
  const params = new URLSearchParams(window.location.search);
  const saved = JSON.parse(sessionStorage.getItem(PENDING) ?? 'null');
  sessionStorage.removeItem(PENDING);
  window.history.replaceState({}, '', '/ui/');
  if (!saved || saved.state !== params.get('state') || !params.get('code')) {
    throw new Error('Не удалось подтвердить вход. Повторите вход.');
  }
  const response = await fetch(ISSUER + '/protocol/openid-connect/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code', client_id: CLIENT_ID, redirect_uri: redirectUri(),
      code: params.get('code') ?? '', code_verifier: saved.verifier,
    }),
  });
  if (!response.ok) throw new Error('Вход не выполнен.');
  const value = await response.json();
  const returnTo = typeof saved.returnTo === 'string' && saved.returnTo.startsWith('/') ? saved.returnTo : '/';
  return { session: { ...decodeSession(value.access_token), refreshToken: value.refresh_token }, returnTo };
}

export async function renewSession(session: Session): Promise<Session> {
  const response = await fetch(ISSUER + '/protocol/openid-connect/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'refresh_token', client_id: CLIENT_ID, refresh_token: session.refreshToken ?? '',
    }),
  });
  if (!response.ok) throw new Error('Сеанс завершён.');
  const value = await response.json();
  return { ...decodeSession(value.access_token), refreshToken: value.refresh_token };
}

export function logout(): void {
  sessionStorage.removeItem(PENDING);
  const query = new URLSearchParams({ client_id: CLIENT_ID, post_logout_redirect_uri: window.location.origin + '/ui/' });
  window.location.assign(ISSUER + '/protocol/openid-connect/logout?' + query.toString());
}

export function hasAny(session: Session, ...roles: string[]): boolean {
  return roles.some((role) => session.roles.has(role));
}
