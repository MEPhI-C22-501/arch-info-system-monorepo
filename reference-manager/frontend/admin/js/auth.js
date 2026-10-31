// login through Keycloak: Authorization Code with PKCE, tokens kept in the session storage of the tab,
// refreshed before they expire, the user and the roles come from the access token (S-04 of document 110)
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('node:crypto').webcrypto);
  else (root.RM = root.RM || {}).auth = factory(root.crypto);
})(globalThis, function (webcrypto) {
  'use strict';

  const PENDING_KEY = 'rm.auth.pending';
  const TOKENS_KEY = 'rm.auth.tokens';
  // a token this close to its expiration is refreshed before the request
  const REFRESH_MARGIN_SECONDS = 30;

  function base64url(bytes) {
    let text = '';
    for (const byte of bytes) text += String.fromCharCode(byte);
    return btoa(text).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  function randomString(length) {
    const bytes = new Uint8Array(length);
    webcrypto.getRandomValues(bytes);
    return base64url(bytes);
  }

  async function challengeOf(verifier) {
    const digest = await webcrypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
    return base64url(new Uint8Array(digest));
  }

  // the payload of a JWT without verification: the service verifies the token, the page only reads the claims
  function decodeJwt(token) {
    const parts = String(token || '').split('.');
    if (parts.length < 2) return null;
    try {
      const json = atob(parts[1].replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(parts[1].length / 4) * 4, '='));
      return JSON.parse(decodeURIComponent(Array.from(json, (c) => `%${c.charCodeAt(0).toString(16).padStart(2, '0')}`).join('')));
    } catch (e) {
      return null;
    }
  }

  function rolesOf(claims, rolesClient) {
    const roles = new Set((claims && claims.realm_access && claims.realm_access.roles) || []);
    const resource = claims && claims.resource_access && claims.resource_access[rolesClient];
    for (const role of (resource && resource.roles) || []) roles.add(role);
    return [...roles].sort();
  }

  // storage: sessionStorage-like object, win: window-like object with location, history, fetch
  function createAuth(config, storage, win) {
    const base = `${String(config.url).replace(/\/+$/, '')}/realms/${encodeURIComponent(config.realm)}/protocol/openid-connect`;
    const redirectUri = `${win.location.origin}/admin/`;

    function read(key) {
      try { return JSON.parse(storage.getItem(key) || 'null'); } catch (e) { return null; }
    }

    function write(key, value) {
      try {
        if (value === null) storage.removeItem(key);
        else storage.setItem(key, JSON.stringify(value));
      } catch (e) {
        // a private window may refuse storage, the login then lasts one page view
      }
    }

    function storeTokens(response, now) {
      const tokens = {
        access_token: response.access_token,
        refresh_token: response.refresh_token || null,
        id_token: response.id_token || null,
        expires_at: now + Number(response.expires_in || 0) * 1000,
      };
      write(TOKENS_KEY, tokens);
      return tokens;
    }

    async function tokenRequest(form) {
      const response = await win.fetch(`${base}/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams(form).toString(),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.error_description || body.error || `token endpoint answered ${response.status}`);
      return body;
    }

    // starts the login: the current path is restored after the return from Keycloak
    async function login(returnTo) {
      const verifier = randomString(48);
      const state = randomString(24);
      write(PENDING_KEY, { state, verifier, returnTo: returnTo || `${win.location.pathname}${win.location.search}` });
      const query = new URLSearchParams({
        response_type: 'code',
        client_id: config.clientId,
        redirect_uri: redirectUri,
        scope: 'openid',
        state,
        code_challenge: await challengeOf(verifier),
        code_challenge_method: 'S256',
      });
      win.location.assign(`${base}/auth?${query.toString()}`);
    }

    // finishes the login when the page is opened with the code from Keycloak, returns the path to show
    async function handleRedirect() {
      const params = new URLSearchParams(win.location.search);
      if (!params.has('code') || !params.has('state')) {
        if (params.has('error')) throw new Error(params.get('error_description') || params.get('error'));
        return null;
      }
      const pending = read(PENDING_KEY);
      write(PENDING_KEY, null);
      if (!pending || pending.state !== params.get('state')) throw new Error('login state mismatch, start the login again');
      const response = await tokenRequest({
        grant_type: 'authorization_code',
        client_id: config.clientId,
        code: params.get('code'),
        redirect_uri: redirectUri,
        code_verifier: pending.verifier,
      });
      storeTokens(response, Date.now());
      return pending.returnTo || '/admin/';
    }

    async function refresh(tokens) {
      if (!tokens.refresh_token) return null;
      try {
        const response = await tokenRequest({
          grant_type: 'refresh_token',
          client_id: config.clientId,
          refresh_token: tokens.refresh_token,
        });
        return storeTokens(response, Date.now());
      } catch (e) {
        write(TOKENS_KEY, null);
        return null;
      }
    }

    // the access token for a request, refreshed when it is about to expire, null when the user has to log in
    async function token() {
      let tokens = read(TOKENS_KEY);
      if (!tokens || !tokens.access_token) return null;
      if (tokens.expires_at - Date.now() < REFRESH_MARGIN_SECONDS * 1000) tokens = await refresh(tokens);
      return tokens ? tokens.access_token : null;
    }

    function user() {
      const tokens = read(TOKENS_KEY);
      const claims = tokens ? decodeJwt(tokens.access_token) : null;
      if (!claims) return null;
      return {
        id: claims.sub,
        username: claims.preferred_username || claims.sub,
        roles: rolesOf(claims, config.rolesClient),
      };
    }

    function forget() {
      write(TOKENS_KEY, null);
      write(PENDING_KEY, null);
    }

    // ends the session in Keycloak as well and comes back to the panel
    function logout() {
      const tokens = read(TOKENS_KEY);
      forget();
      const query = new URLSearchParams({ client_id: config.clientId, post_logout_redirect_uri: redirectUri });
      if (tokens && tokens.id_token) query.set('id_token_hint', tokens.id_token);
      win.location.assign(`${base}/logout?${query.toString()}`);
    }

    return { login, handleRedirect, token, user, forget, logout, redirectUri };
  }

  return { createAuth, challengeOf, decodeJwt, rolesOf, base64url, randomString };
});
