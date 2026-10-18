// in-memory stand-in for the service: same methods, parameters, records and google.rpc.Status errors as document 130
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./catalogs.js'), require('./filter.js'), require('./xlsx.js'), require('./mock-data.js'));
  } else {
    (root.RM = root.RM || {}).mockApi = factory(root.RM.catalogs, root.RM.filter, root.RM.xlsx, root.RM.mockData);
  }
})(globalThis, function (catalogs, filterLib, xlsx, seed) {
  'use strict';

  const { CATALOGS, DATE_RE, can, storedFields, queryFields, refTarget } = catalogs;

  const HTTP = {
    INVALID_ARGUMENT: 400,
    FAILED_PRECONDITION: 400,
    UNAUTHENTICATED: 401,
    PERMISSION_DENIED: 403,
    NOT_FOUND: 404,
    ALREADY_EXISTS: 409,
    ABORTED: 409,
    UNAVAILABLE: 503,
  };
  const TYPE_BAD_REQUEST = 'type.googleapis.com/google.rpc.BadRequest';
  const TYPE_ERROR_INFO = 'type.googleapis.com/google.rpc.ErrorInfo';
  const TYPE_REQUEST_INFO = 'type.googleapis.com/google.rpc.RequestInfo';
  const DOMAIN = 'reference-manager.erp';
  const ACCOUNT_FIELDS = new Set(CATALOGS.employees.fields.filter((f) => f.account).map((f) => f.name));
  const EMPLOYEE_STATE_FIELDS = ['employment_state', 'dismissal_date', 'account_state', 'account_user_id'];

  function randomId() {
    return Math.random().toString(16).slice(2, 10);
  }

  function uuid() {
    if (globalThis.crypto && typeof globalThis.crypto.randomUUID === 'function') return globalThis.crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = Math.floor(Math.random() * 16);
      return (c === 'x' ? r : (r % 4) + 8).toString(16);
    });
  }

  // the error object the service returns, shaped as google.rpc.Status (AIP-193)
  class ApiError extends Error {
    constructor(status, message, details) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.code = HTTP[status];
      this.details = [...(details || []), { '@type': TYPE_REQUEST_INFO, requestId: randomId() }];
    }

    get fieldViolations() {
      const detail = this.details.find((d) => d['@type'] === TYPE_BAD_REQUEST);
      return detail ? detail.fieldViolations : [];
    }

    get reason() {
      const detail = this.details.find((d) => d['@type'] === TYPE_ERROR_INFO);
      return detail ? detail.reason : null;
    }

    get metadata() {
      const detail = this.details.find((d) => d['@type'] === TYPE_ERROR_INFO);
      return detail ? detail.metadata : {};
    }

    get requestId() {
      return this.details.find((d) => d['@type'] === TYPE_REQUEST_INFO).requestId;
    }

    toJSON() {
      return { error: { code: this.code, message: this.message, status: this.status, details: this.details } };
    }
  }

  class KeycloakUnavailable extends Error {}
  class KeycloakConflict extends Error {}

  function badRequest(violations) {
    const fields = violations.map((v) => v.field).join(', ');
    return new ApiError('INVALID_ARGUMENT', `${violations.length} invalid field(s): ${fields}`, [{ '@type': TYPE_BAD_REQUEST, fieldViolations: violations }]);
  }

  function withReason(status, message, reason, metadata) {
    return new ApiError(status, message, [{ '@type': TYPE_ERROR_INFO, reason, domain: DOMAIN, metadata: metadata || {} }]);
  }

  function notFound(collection, id) {
    return withReason('NOT_FOUND', `${collection}/${id} does not exist`, 'RECORD_NOT_FOUND', { name: `${collection}/${id}` });
  }

  function isDate(value) {
    if (typeof value !== 'string' || !DATE_RE.test(value)) return false;
    const date = new Date(`${value}T00:00:00Z`);
    return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
  }

  function isEmpty(value) {
    return value === null || value === undefined || value === '';
  }

  function encodeToken(payload) {
    return btoa(encodeURIComponent(JSON.stringify(payload)));
  }

  function decodeToken(token) {
    try {
      return JSON.parse(decodeURIComponent(atob(token)));
    } catch (e) {
      return null;
    }
  }

  function compareValues(a, b) {
    const aEmpty = isEmpty(a);
    const bEmpty = isEmpty(b);
    if (aEmpty && bEmpty) return 0;
    if (aEmpty) return 1;
    if (bEmpty) return -1;
    if (typeof a === 'number' && typeof b === 'number') return a - b;
    return String(a).localeCompare(String(b), 'ru', { numeric: true });
  }

  function diff(before, after) {
    const changes = [];
    for (const field of Object.keys(after)) {
      const oldValue = before[field] === undefined ? null : before[field];
      const newValue = after[field] === undefined ? null : after[field];
      if (JSON.stringify(oldValue) !== JSON.stringify(newValue)) changes.push({ field, old_value: oldValue, new_value: newValue });
    }
    return changes;
  }

  // the Keycloak Admin REST API as the service sees it: accounts, idempotent operations, an availability switch
  function createKeycloak(config) {
    let users = new Map();

    function ensureAvailable() {
      if (!config.keycloakAvailable) throw new KeycloakUnavailable('keycloak admin api is unavailable');
    }

    function byUsername(username) {
      return [...users.values()].find((u) => u.username === username) || null;
    }

    function byOperation(operationId) {
      return [...users.values()].find((u) => u.attributes.operation_id === operationId) || null;
    }

    return {
      reset() {
        users = new Map();
      },
      list() {
        return [...users.values()];
      },
      seedUser(user) {
        users.set(user.id, { enabled: true, requiredActions: [], attributes: {}, ...user });
      },
      createUser(operationId, payload) {
        ensureAvailable();
        const done = byOperation(operationId);
        if (done) return done;
        const same = byUsername(payload.username);
        if (same) {
          if (same.attributes.employee === payload.employee) return same;
          throw new KeycloakConflict(`username "${payload.username}" belongs to another account`);
        }
        const user = {
          id: uuid(),
          username: payload.username,
          email: payload.email,
          firstName: payload.firstName,
          lastName: payload.lastName,
          enabled: true,
          requiredActions: ['UPDATE_PASSWORD'],
          attributes: { employee: payload.employee, operation_id: operationId },
        };
        users.set(user.id, user);
        return user;
      },
      updateUser(operationId, id, payload) {
        ensureAvailable();
        const user = users.get(id);
        if (!user) throw new KeycloakConflict(`account ${id} does not exist`);
        Object.assign(user, { email: payload.email, firstName: payload.firstName, lastName: payload.lastName });
        user.attributes.operation_id = operationId;
        return user;
      },
      disableUser(operationId, id) {
        ensureAvailable();
        const user = users.get(id);
        if (!user) throw new KeycloakConflict(`account ${id} does not exist`);
        user.enabled = false;
        user.attributes.operation_id = operationId;
        return user;
      },
    };
  }

  function createApi(options) {
    const config = Object.assign({
      exportLimit: 50,
      defaultPageSize: 20,
      maxPageSize: 200,
      keycloakAvailable: true,
      latency: 0,
      now: () => new Date(),
    }, options || {});

    const tables = {};
    const revisions = {};
    const keycloak = createKeycloak(config);
    let sequence = 0;
    let etagSequence = 0;

    function newEtag() {
      etagSequence += 1;
      return `"${etagSequence.toString(16).padStart(4, '0')}"`;
    }

    function nowIso() {
      return config.now().toISOString();
    }

    function today() {
      return nowIso().slice(0, 10);
    }

    function delay() {
      return config.latency ? new Promise((resolve) => setTimeout(resolve, config.latency)) : Promise.resolve();
    }

    function recordName(collection, id) {
      return `${collection}/${id}`;
    }

    // the fields a revision tracks: stored fields plus the employee state fields
    function snapshot(collection, rec) {
      const out = {};
      for (const field of storedFields(collection)) out[field] = rec[field] === undefined ? null : rec[field];
      if (collection === 'employees') for (const field of EMPLOYEE_STATE_FIELDS) out[field] = rec[field] === undefined ? null : rec[field];
      return out;
    }

    function pushRevision(collection, id, action, author, createTime, changes) {
      const list = revisions[collection].get(id) || [];
      list.push({
        name: `${recordName(collection, id)}/revisions/${list.length + 1}`,
        action,
        author,
        create_time: createTime,
        request_id: randomId(),
        changes,
      });
      revisions[collection].set(id, list);
    }

    function addRevision(collection, rec, action, user, changes) {
      pushRevision(collection, rec.id, action, user.username, nowIso(), changes);
    }

    function load() {
      for (const collection of Object.keys(CATALOGS)) {
        tables[collection] = new Map();
        revisions[collection] = new Map();
      }
      keycloak.reset();
      let maxId = 0;
      for (const [collection, rows] of Object.entries(seed.records)) {
        for (const row of rows) {
          const rec = { ...row, delete_time: row.delete_time || null, etag: newEtag() };
          tables[collection].set(rec.id, rec);
          if (CATALOGS[collection].dated) maxId = Math.max(maxId, Number(rec.id));
          const later = seed.history.filter((h) => h.name === recordName(collection, rec.id));
          const initial = snapshot(collection, rec);
          for (const revision of [...later].reverse()) {
            for (const change of revision.changes) if (change.field in initial) initial[change.field] = change.old_value;
          }
          const created = Object.entries(initial)
            .filter(([, value]) => !isEmpty(value))
            .map(([field, value]) => ({ field, old_value: null, new_value: value }));
          pushRevision(collection, rec.id, 'CREATED', seed.SEED_AUTHOR, seed.SEED_TIME, created);
          for (const revision of later) pushRevision(collection, rec.id, revision.action, revision.author, revision.create_time, revision.changes);
          if (collection === 'employees' && rec.account_user_id) {
            keycloak.seedUser({
              id: rec.account_user_id,
              username: rec.username,
              email: rec.email,
              firstName: rec.given_name,
              lastName: rec.family_name,
              enabled: rec.account_state === 'ENABLED',
              attributes: { employee: recordName('employees', rec.id) },
            });
          }
        }
      }
      sequence = Math.max(maxId, 100);
    }

    function requireCatalog(collection) {
      const cat = CATALOGS[collection];
      if (!cat) throw withReason('NOT_FOUND', `collection ${collection} does not exist`, 'COLLECTION_NOT_FOUND', { collection: String(collection) });
      return cat;
    }

    function authorize(user, collection, level) {
      if (!user || user.anonymous) throw withReason('UNAUTHENTICATED', 'request carries no valid token', 'TOKEN_MISSING', {});
      if (!can(user, collection, level)) {
        const group = CATALOGS[collection].group;
        throw withReason('PERMISSION_DENIED', `level ${level} on ${collection} (group ${group}) needs a role the token does not carry`, 'ROLE_MISSING', { collection, level, group });
      }
    }

    function assignmentInEffect(employeeId, date) {
      const name = recordName('employees', employeeId);
      for (const row of tables.assignments.values()) {
        if (row.delete_time || row.employee !== name) continue;
        if (row.start_date <= date && (!row.end_date || row.end_date >= date)) return row;
      }
      return null;
    }

    function toRecord(collection, rec) {
      const cat = CATALOGS[collection];
      const out = { name: recordName(collection, rec.id) };
      if (cat.displayName) out.display_name = rec.display_name;
      out.state = rec.delete_time ? 'DELETED' : 'ACTIVE';
      out.etag = rec.etag;
      out.delete_time = rec.delete_time;
      for (const field of cat.fields) out[field.name] = rec[field.name] === undefined ? null : rec[field.name];
      if (collection === 'employees') {
        const assignment = assignmentInEffect(rec.id, today());
        out.employment_state = rec.employment_state;
        out.dismissal_date = rec.dismissal_date;
        out.org_unit = assignment ? assignment.org_unit : null;
        out.position = assignment ? assignment.position : null;
        out.account_state = rec.account_state;
        out.account_user_id = rec.account_user_id;
      }
      return out;
    }

    // keeps only the stored fields of the body and converts numeric strings for number fields
    function pickInput(cat, body) {
      const values = {};
      const source = body || {};
      if (cat.displayName) values.display_name = isEmpty(source.display_name) ? null : String(source.display_name).trim();
      for (const field of cat.fields) {
        let value = source[field.name];
        if (isEmpty(value)) value = null;
        else if (field.type === 'number' && typeof value === 'string' && value.trim() !== '' && !Number.isNaN(Number(value))) value = Number(value);
        else if (typeof value === 'string') value = value.trim();
        values[field.name] = value;
      }
      return values;
    }

    function datedRules(collection, values, context, push) {
      const start = values.start_date;
      const end = values.end_date;
      if (start && end && end < start) push('end_date', 'must not be earlier than start_date');
      const target = refTarget(values.employee);
      const employee = target ? tables.employees.get(target.id) : null;
      if (context.isNew && employee && employee.employment_state === 'DISMISSED') push('employee', `${values.employee} is dismissed`);
      if (collection !== 'assignments' && collection !== 'salaries') return;
      for (const other of tables[collection].values()) {
        if (other.id === context.id || other.delete_time || other.employee !== values.employee) continue;
        const overlaps = (!end || other.start_date <= end) && (!other.end_date || other.end_date >= start);
        if (!overlaps) continue;
        const period = `${other.start_date} - ${other.end_date || '...'}`;
        push('start_date', `period overlaps ${recordName(collection, other.id)} (${period})`);
        push('end_date', `period overlaps ${recordName(collection, other.id)} (${period})`);
        return;
      }
    }

    function parentRules(values, context, push) {
      if (!values.parent) return;
      const seen = new Set();
      let current = refTarget(values.parent).id;
      while (current) {
        if (current === context.id) { push('parent', 'reference forms a cycle'); return; }
        if (seen.has(current)) return;
        seen.add(current);
        const parent = tables.org_units.get(current);
        current = parent && parent.parent ? refTarget(parent.parent).id : null;
      }
    }

    // context: { isNew, id, fields } where fields limits the checked stored fields (update_mask)
    function validate(collection, values, context) {
      const cat = CATALOGS[collection];
      const violations = [];
      const push = (field, description) => violations.push({ field, description });
      const names = context.fields || storedFields(collection);

      if (names.includes('display_name')) {
        const value = values.display_name;
        if (isEmpty(value) || !String(value).trim()) push('display_name', 'required');
        else if (String(value).length > 255) push('display_name', 'at most 255 characters');
      }
      for (const field of cat.fields) {
        if (!names.includes(field.name)) continue;
        const value = values[field.name];
        if (isEmpty(value)) {
          if (field.required) push(field.name, 'required');
          continue;
        }
        switch (field.type) {
          case 'number':
            if (typeof value !== 'number' || !Number.isFinite(value)) push(field.name, 'must be a number');
            else if (field.integer && !Number.isInteger(value)) push(field.name, field.err);
            else if ((field.min !== undefined && value < field.min) || (field.max !== undefined && value > field.max)) push(field.name, field.err || 'out of range');
            break;
          case 'date':
            if (!isDate(value)) push(field.name, 'date in the form YYYY-MM-DD');
            break;
          case 'enum':
            if (!field.values.includes(value)) push(field.name, `one of ${field.values.join(', ')}`);
            break;
          case 'ref': {
            const target = refTarget(value);
            if (!target || target.collection !== field.ref) { push(field.name, `name of a ${field.ref} record, for example ${field.ref}/{id}`); break; }
            const record = tables[field.ref].get(target.id);
            if (!record) push(field.name, `${value} does not exist`);
            else if (record.delete_time) push(field.name, `${value} is deleted`);
            break;
          }
          default:
            if (typeof value !== 'string') push(field.name, 'must be a string');
            else if (field.re && !field.re.test(value)) push(field.name, field.err || 'invalid format');
            else if (field.maxLen && value.length > field.maxLen) push(field.name, `at most ${field.maxLen} characters`);
        }
        if (field.unique) {
          for (const other of tables[collection].values()) {
            if (other.id !== context.id && String(other[field.name]) === String(value)) {
              push(field.name, `already used by ${recordName(collection, other.id)}`);
              break;
            }
          }
        }
      }
      if (violations.length) return violations;
      if (cat.dated) datedRules(collection, values, context, push);
      if (collection === 'org_units') parentRules(values, context, push);
      return violations;
    }

    function parseMask(updateMask, collection) {
      const names = String(updateMask || '').split(',').map((s) => s.trim()).filter(Boolean);
      if (!names.length) throw badRequest([{ field: 'update_mask', description: 'required: list the fields to change' }]);
      const stored = storedFields(collection);
      for (const name of names) {
        if (!stored.includes(name)) throw badRequest([{ field: 'update_mask', description: `unknown or read-only field "${name}"` }]);
      }
      return names;
    }

    function parseOrderBy(orderBy, collection) {
      const allowed = queryFields(collection);
      const keys = String(orderBy || '').split(',').map((s) => s.trim()).filter(Boolean).map((s) => {
        const [field, direction] = s.split(/\s+/);
        return { field, desc: (direction || '').toLowerCase() === 'desc' };
      });
      for (const key of keys) {
        if (!allowed.includes(key.field)) throw badRequest([{ field: 'order_by', description: `unknown field "${key.field}"` }]);
      }
      if (!keys.length) keys.push({ field: 'name', desc: false });
      return keys;
    }

    function accountPayload(rec) {
      return { username: rec.username, email: rec.email, firstName: rec.given_name, lastName: rec.family_name, employee: recordName('employees', rec.id) };
    }

    // the call to Keycloak runs after the record is saved: a failure leaves the record PENDING and answers UNAVAILABLE
    async function runAccountOperation(user, rec) {
      const operation = rec.account_operation;
      const operationId = rec.account_operation_id;
      const name = recordName('employees', rec.id);
      let account;
      try {
        if (operation === 'CREATE') account = keycloak.createUser(operationId, accountPayload(rec));
        else if (operation === 'UPDATE') account = keycloak.updateUser(operationId, rec.account_user_id, accountPayload(rec));
        else account = keycloak.disableUser(operationId, rec.account_user_id);
      } catch (e) {
        if (e instanceof KeycloakUnavailable) {
          throw withReason('UNAVAILABLE', `${name} is saved, account operation ${operation} is pending; retry with :syncAccount`, 'ACCOUNT_PENDING', { name, operation });
        }
        if (e instanceof KeycloakConflict) {
          throw withReason('FAILED_PRECONDITION', `${name}: ${e.message}; account operation ${operation} stays pending`, 'ACCOUNT_CONFLICT', { name, operation });
        }
        throw e;
      }
      const before = snapshot('employees', rec);
      rec.account_user_id = account.id;
      rec.account_state = operation === 'DISABLE' ? 'DISABLED' : 'ENABLED';
      rec.account_operation = null;
      rec.account_operation_id = null;
      rec.etag = newEtag();
      addRevision('employees', rec, 'UPDATED', user, diff(before, snapshot('employees', rec)));
    }

    function selectRows(user, collection, params) {
      authorize(user, collection, 'R');
      let rows = [...tables[collection].values()].map((rec) => toRecord(collection, rec));
      if (!params.showDeleted) rows = rows.filter((row) => row.state === 'ACTIVE');
      let predicate;
      try {
        predicate = filterLib.compile(params.filter || '', queryFields(collection));
      } catch (e) {
        if (e instanceof filterLib.FilterError) throw badRequest([{ field: 'filter', description: e.message }]);
        throw e;
      }
      rows = rows.filter(predicate);
      const keys = parseOrderBy(params.orderBy, collection);
      rows.sort((a, b) => {
        for (const key of keys) {
          const order = compareValues(a[key.field], b[key.field]);
          if (order !== 0) return key.desc ? -order : order;
        }
        return 0;
      });
      return rows;
    }

    async function list(user, collection, params) {
      await delay();
      requireCatalog(collection);
      const query = params || {};
      const rows = selectRows(user, collection, query);
      let pageSize = Number(query.pageSize) || config.defaultPageSize;
      if (pageSize < 1 || pageSize > config.maxPageSize) throw badRequest([{ field: 'page_size', description: `from 1 to ${config.maxPageSize}` }]);
      pageSize = Math.floor(pageSize);
      const key = JSON.stringify([query.filter || '', query.orderBy || '', Boolean(query.showDeleted), pageSize]);
      let offset = 0;
      if (query.pageToken) {
        const token = decodeToken(query.pageToken);
        if (!token || token.key !== key) throw badRequest([{ field: 'page_token', description: 'page_token does not match the query parameters' }]);
        offset = token.offset;
      }
      const page = rows.slice(offset, offset + pageSize);
      const nextOffset = offset + pageSize;
      return {
        [collection]: page,
        next_page_token: nextOffset < rows.length ? encodeToken({ key, offset: nextOffset }) : '',
        total_size: rows.length,
      };
    }

    async function get(user, collection, id) {
      await delay();
      requireCatalog(collection);
      authorize(user, collection, 'R');
      const rec = tables[collection].get(String(id));
      if (!rec) throw notFound(collection, id);
      return toRecord(collection, rec);
    }

    async function create(user, collection, body, id) {
      await delay();
      const cat = requireCatalog(collection);
      authorize(user, collection, 'C');
      const violations = [];
      let recordId = id;
      if (cat.dated) {
        sequence += 1;
        recordId = String(sequence);
      } else if (isEmpty(recordId)) {
        violations.push({ field: cat.idParam, description: 'required' });
      } else if (!cat.idRe.test(String(recordId))) {
        violations.push({ field: cat.idParam, description: cat.idHint });
      } else if (tables[collection].has(String(recordId))) {
        const existing = tables[collection].get(String(recordId));
        const state = existing.delete_time ? 'DELETED' : 'ACTIVE';
        throw withReason('ALREADY_EXISTS', `${recordName(collection, recordId)} already exists in state ${state}${existing.delete_time ? ', undelete it' : ''}`, 'RECORD_EXISTS', { name: recordName(collection, recordId), state });
      }
      const values = pickInput(cat, body);
      violations.push(...validate(collection, values, { isNew: true, id: String(recordId) }));
      if (violations.length) {
        if (cat.dated) sequence -= 1;
        throw badRequest(violations);
      }
      const rec = { id: String(recordId), ...values, delete_time: null, etag: newEtag() };
      if (collection === 'employees') {
        Object.assign(rec, {
          employment_state: 'EMPLOYED',
          dismissal_date: null,
          account_state: 'PENDING',
          account_user_id: null,
          account_operation: 'CREATE',
          account_operation_id: uuid(),
        });
      }
      tables[collection].set(rec.id, rec);
      addRevision(collection, rec, 'CREATED', user, diff({}, snapshot(collection, rec)));
      if (collection === 'employees') await runAccountOperation(user, rec);
      return toRecord(collection, rec);
    }

    async function update(user, collection, id, body, updateMask) {
      await delay();
      const cat = requireCatalog(collection);
      authorize(user, collection, 'U');
      const rec = tables[collection].get(String(id));
      if (!rec) throw notFound(collection, id);
      const name = recordName(collection, rec.id);
      if (rec.delete_time) throw withReason('FAILED_PRECONDITION', `${name} is deleted, undelete it first`, 'RECORD_DELETED', { name });
      const mask = parseMask(updateMask, collection);
      const input = pickInput(cat, body);
      const violations = [];
      for (const fieldName of mask) {
        const field = cat.fields.find((f) => f.name === fieldName);
        if (field && field.immutable && JSON.stringify(input[fieldName]) !== JSON.stringify(rec[fieldName] === undefined ? null : rec[fieldName])) {
          violations.push({ field: fieldName, description: 'cannot be changed after creation' });
        }
      }
      if (violations.length) throw badRequest(violations);
      const merged = { ...rec };
      for (const fieldName of mask) merged[fieldName] = input[fieldName];
      const problems = validate(collection, merged, { isNew: false, id: rec.id, fields: mask });
      if (problems.length) throw badRequest(problems);
      const before = snapshot(collection, rec);
      const changes = diff(before, snapshot(collection, merged));
      if (!changes.length) return toRecord(collection, rec);
      for (const fieldName of mask) rec[fieldName] = merged[fieldName];
      rec.etag = newEtag();
      let syncAccount = false;
      if (collection === 'employees' && rec.employment_state === 'EMPLOYED' && rec.account_state === 'ENABLED'
        && changes.some((change) => ACCOUNT_FIELDS.has(change.field))) {
        rec.account_state = 'PENDING';
        rec.account_operation = 'UPDATE';
        rec.account_operation_id = uuid();
        changes.push({ field: 'account_state', old_value: 'ENABLED', new_value: 'PENDING' });
        syncAccount = true;
      }
      addRevision(collection, rec, 'UPDATED', user, changes);
      if (syncAccount) await runAccountOperation(user, rec);
      return toRecord(collection, rec);
    }

    async function remove(user, collection, id) {
      await delay();
      requireCatalog(collection);
      authorize(user, collection, 'D');
      const rec = tables[collection].get(String(id));
      if (!rec) throw notFound(collection, id);
      const name = recordName(collection, rec.id);
      if (rec.delete_time) throw withReason('FAILED_PRECONDITION', `${name} is already deleted`, 'RECORD_DELETED', { name });
      if (collection === 'employees' && rec.employment_state === 'EMPLOYED') {
        throw withReason('FAILED_PRECONDITION', `${name} is employed and has an account, call :dismiss first`, 'EMPLOYEE_ACTIVE', { name });
      }
      const before = { state: 'ACTIVE', delete_time: null };
      rec.delete_time = nowIso();
      rec.etag = newEtag();
      addRevision(collection, rec, 'DELETED', user, diff(before, { state: 'DELETED', delete_time: rec.delete_time }));
      return toRecord(collection, rec);
    }

    async function undelete(user, collection, id) {
      await delay();
      requireCatalog(collection);
      authorize(user, collection, 'U');
      const rec = tables[collection].get(String(id));
      if (!rec) throw notFound(collection, id);
      const name = recordName(collection, rec.id);
      if (!rec.delete_time) throw withReason('FAILED_PRECONDITION', `${name} is not deleted`, 'RECORD_ACTIVE', { name });
      const before = { state: 'DELETED', delete_time: rec.delete_time };
      rec.delete_time = null;
      rec.etag = newEtag();
      addRevision(collection, rec, 'UNDELETED', user, diff(before, { state: 'ACTIVE', delete_time: null }));
      return toRecord(collection, rec);
    }

    async function listRevisions(user, collection, id) {
      await delay();
      requireCatalog(collection);
      authorize(user, collection, 'R');
      if (!tables[collection].has(String(id))) throw notFound(collection, id);
      const list = revisions[collection].get(String(id)) || [];
      return { revisions: [...list].reverse(), next_page_token: '', total_size: list.length };
    }

    // the record as it was after revision number n, folded from the stored differences
    async function getAtRevision(user, collection, id, number) {
      await delay();
      requireCatalog(collection);
      authorize(user, collection, 'R');
      const list = revisions[collection].get(String(id));
      if (!list || number < 1 || number > list.length) throw notFound(collection, `${id}/revisions/${number}`);
      const state = { name: recordName(collection, id), state: 'ACTIVE' };
      for (const revision of list.slice(0, number)) for (const change of revision.changes) state[change.field] = change.new_value;
      return state;
    }

    function exportColumns(collection) {
      const cat = CATALOGS[collection];
      return ['name', ...(cat.displayName ? ['display_name'] : []), 'state', 'delete_time', ...cat.fields.map((f) => f.name), ...(cat.readOnly || []).map((f) => f.name)];
    }

    // List with Accept for .xlsx: the same selection, the whole result in one file, a limit from the configuration
    async function exportList(user, collection, params) {
      await delay();
      requireCatalog(collection);
      authorize(user, collection, 'X');
      const rows = selectRows(user, collection, params || {});
      if (rows.length > config.exportLimit) {
        throw withReason('FAILED_PRECONDITION', `${rows.length} records selected, the export limit is ${config.exportLimit}; narrow the filter`, 'EXPORT_TOO_LARGE', { selected: String(rows.length), limit: String(config.exportLimit) });
      }
      const header = exportColumns(collection);
      const data = rows.map((row) => header.map((column) => (row[column] === undefined ? null : row[column])));
      return { filename: `${collection}.xlsx`, contentType: xlsx.MIME, bytes: xlsx.build(collection, header, data, config.now()), rows: rows.length };
    }

    async function dismiss(user, id, body) {
      await delay();
      authorize(user, 'employees', 'U');
      const rec = tables.employees.get(String(id));
      if (!rec) throw notFound('employees', id);
      const name = recordName('employees', rec.id);
      const date = body ? body.dismissal_date : null;
      if (!isDate(date)) throw badRequest([{ field: 'dismissal_date', description: 'date in the form YYYY-MM-DD' }]);
      if (rec.delete_time) throw withReason('FAILED_PRECONDITION', `${name} is deleted`, 'RECORD_DELETED', { name });
      if (rec.employment_state === 'DISMISSED') throw withReason('FAILED_PRECONDITION', `${name} is already dismissed on ${rec.dismissal_date}`, 'ALREADY_DISMISSED', { name });
      if (date < rec.hire_date) throw badRequest([{ field: 'dismissal_date', description: `must not be earlier than hire_date ${rec.hire_date}` }]);
      if (rec.account_state === 'PENDING') {
        throw withReason('FAILED_PRECONDITION', `${name}: account operation ${rec.account_operation} is pending, call :syncAccount first`, 'ACCOUNT_PENDING', { name, operation: rec.account_operation });
      }
      const before = snapshot('employees', rec);
      rec.employment_state = 'DISMISSED';
      rec.dismissal_date = date;
      rec.account_state = 'PENDING';
      rec.account_operation = 'DISABLE';
      rec.account_operation_id = uuid();
      rec.etag = newEtag();
      addRevision('employees', rec, 'UPDATED', user, diff(before, snapshot('employees', rec)));
      for (const collection of ['assignments', 'salaries']) {
        for (const row of tables[collection].values()) {
          if (row.delete_time || row.employee !== name) continue;
          if (row.start_date <= date && (!row.end_date || row.end_date > date)) {
            const rowBefore = snapshot(collection, row);
            row.end_date = date;
            row.etag = newEtag();
            addRevision(collection, row, 'UPDATED', user, diff(rowBefore, snapshot(collection, row)));
          }
        }
      }
      await runAccountOperation(user, rec);
      return toRecord('employees', rec);
    }

    async function syncAccount(user, id) {
      await delay();
      authorize(user, 'employees', 'U');
      const rec = tables.employees.get(String(id));
      if (!rec) throw notFound('employees', id);
      if (rec.account_operation) await runAccountOperation(user, rec);
      return toRecord('employees', rec);
    }

    load();

    return {
      config,
      keycloak,
      reset: load,
      list,
      get,
      create,
      update,
      remove,
      undelete,
      listRevisions,
      getAtRevision,
      exportList,
      exportColumns,
      dismiss,
      syncAccount,
    };
  }

  return { createApi, ApiError, uuid };
});
