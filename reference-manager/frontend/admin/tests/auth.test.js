const test = require('node:test');
const assert = require('node:assert/strict');
const auth = require('../js/auth.js');

function jwt(payload) {
  const part = (value) => Buffer.from(JSON.stringify(value)).toString('base64url');
  return `${part({ alg: 'RS256' })}.${part(payload)}.signature`;
}

class MemoryStorage {
  constructor() { this.map = new Map(); }
  getItem(key) { return this.map.has(key) ? this.map.get(key) : null; }
  setItem(key, value) { this.map.set(key, String(value)); }
  removeItem(key) { this.map.delete(key); }
}

const CONFIG = { url: 'http://kc.local:8180/', realm: 'arch-info-system', clientId: 'reference-manager-ui', rolesClient: 'reference-manager' };

function fakeWindow(url, fetchImpl) {
  const location = new URL(url);
  return {
    location: {
      origin: location.origin,
      pathname: location.pathname,
      search: location.search,
      assigned: null,
      assign(target) { this.assigned = target; },
    },
    fetch: fetchImpl || (() => { throw new Error('fetch not expected'); }),
  };
}

test('the PKCE challenge matches the RFC 7636 example', async () => {
  assert.equal(await auth.challengeOf('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'), 'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM');
  assert.match(auth.randomString(48), /^[A-Za-z0-9_-]{64}$/);
});

test('the user comes from the token: name, realm roles and the roles of the audience client', () => {
  const claims = auth.decodeJwt(jwt({ sub: 'u-1', preferred_username: 'hr-admin', realm_access: { roles: ['reference-hr-admin', 'offline_access'] }, resource_access: { 'reference-manager': { roles: ['reference-reader'] }, other: { roles: ['x'] } } }));
  assert.equal(claims.preferred_username, 'hr-admin');
  assert.deepEqual(auth.rolesOf(claims, 'reference-manager'), ['offline_access', 'reference-hr-admin', 'reference-reader']);
  assert.equal(auth.decodeJwt('not-a-token'), null);
});

test('login stores the verifier and sends the browser to Keycloak with S256', async () => {
  const storage = new MemoryStorage();
  const win = fakeWindow('http://localhost:8081/admin/employees?filter=x');
  const session = auth.createAuth(CONFIG, storage, win);
  await session.login();
  const target = new URL(win.location.assigned);
  assert.equal(`${target.origin}${target.pathname}`, 'http://kc.local:8180/realms/arch-info-system/protocol/openid-connect/auth');
  assert.equal(target.searchParams.get('client_id'), 'reference-manager-ui');
  assert.equal(target.searchParams.get('redirect_uri'), 'http://localhost:8081/admin/');
  assert.equal(target.searchParams.get('code_challenge_method'), 'S256');
  const pending = JSON.parse(storage.getItem('rm.auth.pending'));
  assert.equal(pending.state, target.searchParams.get('state'));
  assert.equal(pending.returnTo, '/admin/employees?filter=x');
  assert.equal(target.searchParams.get('code_challenge'), await auth.challengeOf(pending.verifier));
});

test('the return from Keycloak exchanges the code with the verifier, then the token is served and refreshed', async () => {
  const storage = new MemoryStorage();
  storage.setItem('rm.auth.pending', JSON.stringify({ state: 's1', verifier: 'v1', returnTo: '/admin/countries' }));
  const calls = [];
  const fetchImpl = async (url, options) => {
    const form = new URLSearchParams(options.body);
    calls.push({ url, form: Object.fromEntries(form) });
    const access = jwt({ sub: 'u-1', preferred_username: 'admin', realm_access: { roles: ['reference-admin'] }, exp: 1 });
    const expiresIn = form.get('grant_type') === 'refresh_token' ? 300 : 10;
    return { ok: true, status: 200, json: async () => ({ access_token: access, refresh_token: 'r1', id_token: 'id1', expires_in: expiresIn }) };
  };
  const win = fakeWindow('http://localhost:8081/admin/?code=c1&state=s1', fetchImpl);
  const session = auth.createAuth(CONFIG, storage, win);
  assert.equal(await session.handleRedirect(), '/admin/countries');
  assert.equal(calls[0].url, 'http://kc.local:8180/realms/arch-info-system/protocol/openid-connect/token');
  assert.deepEqual(calls[0].form, { grant_type: 'authorization_code', client_id: 'reference-manager-ui', code: 'c1', redirect_uri: 'http://localhost:8081/admin/', code_verifier: 'v1' });
  assert.equal(storage.getItem('rm.auth.pending'), null, 'the pending login is consumed');
  assert.deepEqual(session.user(), { id: 'u-1', username: 'admin', roles: ['reference-admin'] });

  // a token that expires in 10 seconds is inside the refresh margin, so the next token() refreshes it
  const token = await session.token();
  assert.ok(token);
  assert.equal(calls.length, 2);
  assert.equal(calls[1].form.grant_type, 'refresh_token');
  assert.equal(calls[1].form.refresh_token, 'r1');
  assert.equal(await session.token(), token, 'a fresh token is served from storage');
  assert.equal(calls.length, 2);
});

test('a mismatched state is refused, a return without a code is not a login', async () => {
  const storage = new MemoryStorage();
  storage.setItem('rm.auth.pending', JSON.stringify({ state: 's1', verifier: 'v1' }));
  const session = auth.createAuth(CONFIG, storage, fakeWindow('http://localhost:8081/admin/?code=c1&state=other'));
  await assert.rejects(session.handleRedirect(), /state mismatch/);
  const plain = auth.createAuth(CONFIG, new MemoryStorage(), fakeWindow('http://localhost:8081/admin/countries'));
  assert.equal(await plain.handleRedirect(), null);
  assert.equal(await plain.token(), null);
  assert.equal(plain.user(), null);
});

test('logout forgets the tokens and sends the browser to the end session endpoint', () => {
  const storage = new MemoryStorage();
  storage.setItem('rm.auth.tokens', JSON.stringify({ access_token: 'a', id_token: 'id1', expires_at: Date.now() + 100000 }));
  const win = fakeWindow('http://localhost:8081/admin/');
  const session = auth.createAuth(CONFIG, storage, win);
  session.logout();
  const target = new URL(win.location.assigned);
  assert.equal(target.pathname, '/realms/arch-info-system/protocol/openid-connect/logout');
  assert.equal(target.searchParams.get('id_token_hint'), 'id1');
  assert.equal(target.searchParams.get('post_logout_redirect_uri'), 'http://localhost:8081/admin/');
  assert.equal(storage.getItem('rm.auth.tokens'), null);
});
