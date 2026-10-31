// client of the service API (document 130, ADR-022) on top of fetch: the same origin, a bearer token on every request,
// errors as {message, details[{field, message}]} with the trace of the response
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else (root.RM = root.RM || {}).api = factory();
})(globalThis, function () {
  'use strict';

  const MAX_RETRIES = 3;
  const MAX_PAGES = 20;

  class ApiError extends Error {
    constructor(status, message, details, traceId) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.details = details || [];
      this.traceId = traceId || '';
    }

    // {field: message} for the errors the service attributes to fields
    get fieldErrors() {
      const errors = {};
      for (const detail of this.details) if (detail && detail.field) errors[detail.field] = detail.message;
      return errors;
    }
  }

  function buildQuery(params) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params || {})) {
      if (value === undefined || value === null || value === '' || value === false) continue;
      query.set(key, String(value));
    }
    const text = query.toString();
    return text ? `?${text}` : '';
  }

  // the file name of a Content-Disposition header, the given fallback otherwise
  function parseFilename(header, fallback) {
    const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(header || '');
    return match ? decodeURIComponent(match[1]) : fallback;
  }

  function sleep(ms) {
    return new Promise((resolve) => { setTimeout(resolve, ms); });
  }

  // options: base (path of the API), token (async () => access token or null), onUnauthenticated (called on 401),
  // fetch (the fetch to use, window.fetch by default)
  function createApi(options) {
    const base = String(options.base || '/v1').replace(/\/+$/, '');
    const doFetch = options.fetch || ((...args) => globalThis.fetch(...args));

    async function request(method, path, { query, body, blob } = {}) {
      const url = `${base}${path}${buildQuery(query)}`;
      for (let attempt = 0; ; attempt += 1) {
        const token = await options.token();
        const headers = { Accept: blob ? '*/*' : 'application/json' };
        if (token) headers.Authorization = `Bearer ${token}`;
        if (body !== undefined) headers['Content-Type'] = 'application/json';
        const response = await doFetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });

        if (response.status === 429 && attempt < MAX_RETRIES) {
          const seconds = Number(response.headers.get('Retry-After')) || 1;
          await sleep(seconds * 1000);
          continue;
        }

        const traceId = response.headers.get('X-Trace-Id') || '';
        if (!response.ok) {
          let payload = null;
          try { payload = await response.json(); } catch (e) { payload = null; }
          const message = (payload && payload.message) || `${method} ${path} answered ${response.status}`;
          const error = new ApiError(response.status, message, payload && payload.details, traceId);
          if (response.status === 401 && options.onUnauthenticated) options.onUnauthenticated(error);
          throw error;
        }

        if (blob) {
          return { blob: await response.blob(), filename: parseFilename(response.headers.get('Content-Disposition'), blob) };
        }
        if (response.status === 204) return null;
        const text = await response.text();
        return text ? JSON.parse(text) : null;
      }
    }

    const recordPath = (collection, id) => `/${collection}/${encodeURIComponent(String(id))}`;

    // list(collection, {filter, orderBy, pageSize, pageToken, allowDeleted}) -> {items, nextPageToken}
    async function list(collection, params) {
      const p = params || {};
      const page = await request('GET', `/${collection}/`, {
        query: { filter: p.filter, order_by: p.orderBy, pageSize: p.pageSize, pageToken: p.pageToken, allowDeleted: p.allowDeleted },
      });
      return { items: (page && page[collection]) || [], nextPageToken: (page && page.nextPageToken) || '' };
    }

    // every page of a selection, for reference lists and the history
    async function listAll(collection, params) {
      const items = [];
      let pageToken = '';
      for (let i = 0; i < MAX_PAGES; i += 1) {
        const page = await list(collection, { ...(params || {}), pageSize: 100, pageToken });
        items.push(...page.items);
        if (!page.nextPageToken) break;
        pageToken = page.nextPageToken;
      }
      return items;
    }

    function get(collection, id, allowDeleted) {
      return request('GET', recordPath(collection, id), { query: { allowDeleted } });
    }

    function create(collection, body) {
      return request('POST', `/${collection}/`, { body });
    }

    function update(collection, id, body, mask) {
      return request('PATCH', recordPath(collection, id), { query: { updateMask: mask }, body });
    }

    function remove(collection, id, force) {
      return request('DELETE', recordPath(collection, id), { query: { force } });
    }

    function exportFile(collection) {
      return request('POST', `/${collection}/export`, { blob: `${collection}.xlsx` });
    }

    async function listRevisions(collection, id, params) {
      const p = params || {};
      const page = await request('GET', `${recordPath(collection, id)}/revisions`, {
        query: { pageSize: p.pageSize, pageToken: p.pageToken, allowDeleted: p.allowDeleted },
      });
      return { revisions: (page && page.revisions) || [], nextPageToken: (page && page.nextPageToken) || '' };
    }

    async function allRevisions(collection, id, allowDeleted) {
      const revisions = [];
      let pageToken = '';
      for (let i = 0; i < MAX_PAGES; i += 1) {
        const page = await listRevisions(collection, id, { pageSize: 100, pageToken, allowDeleted });
        revisions.push(...page.revisions);
        if (!page.nextPageToken) break;
        pageToken = page.nextPageToken;
      }
      return revisions;
    }

    function getRevision(collection, id, number, allowDeleted) {
      return request('GET', `${recordPath(collection, id)}/revisions/${number}`, { query: { allowDeleted } });
    }

    function dismiss(id, dismissalDate) {
      return request('POST', `${recordPath('employees', id)}/dismiss`, { body: { dismissal_date: dismissalDate } });
    }

    function syncAccount(id) {
      return request('POST', `${recordPath('employees', id)}/syncAccount`);
    }

    return { request, list, listAll, get, create, update, remove, exportFile, listRevisions, allRevisions, getRevision, dismiss, syncAccount };
  }

  return { createApi, ApiError, buildQuery, parseFilename };
});
