// screens S-01..S-05 of document 110 on top of the service API, the route lives in the path under /admin/
(function () {
  'use strict';

  const { el, replace, clear, $ } = RM.dom;
  const { CATALOGS, GROUPS, COMMON, can, hasAnyRole, inputFields, readOnlyFields, fieldByName, queryFields, fieldLabel, listColumns, recordLabel, toBody, updateMask, normalize } = RM.catalogs;
  const { ApiError } = RM.api;
  const { stateAt, fieldOf } = RM.jsonpatch;

  const config = window.RM_CONFIG || { apiBase: '/v1', keycloak: {} };
  const auth = RM.auth.createAuth(config.keycloak, sessionStorage, window);
  const api = RM.api.createApi({ base: config.apiBase, token: () => auth.token(), onUnauthenticated: () => relogin() });

  const PREFIX = '/admin';
  const PAGE_SIZES = [10, 20, 50, 100];
  const DATED_TABS = [['assignments', 'Назначения'], ['salaries', 'Оклады'], ['absences', 'Отсутствия']];
  const ZERO_TIME = '0001-01-01T00:00:00Z';
  const STATUS_HINTS = {
    400: 'Запрос отклонён: проверьте поля или состояние записи.',
    401: 'Сессия истекла, выполняется повторный вход.',
    403: 'Нет доступа: у роли нет нужного уровня на эту группу справочников.',
    404: 'Запись не найдена.',
    409: 'Запись изменена параллельно или такая запись уже есть: перечитайте и повторите.',
    503: 'Keycloak не подтвердил операцию: запись сохранена, учётная запись в состоянии PENDING. Повторите операцию позже.',
  };

  const session = { user: null, flash: null, pager: {}, labels: {} };
  let renderSequence = 0;

  // ---- storage of per-browser conveniences: unsent drafts ----

  function storageGet(key) {
    try { return sessionStorage.getItem(key); } catch (e) { return null; }
  }

  function storageSet(key, value) {
    try {
      if (value === null) sessionStorage.removeItem(key);
      else sessionStorage.setItem(key, value);
    } catch (e) {
      // a private window may refuse storage, the page works without it
    }
  }

  function safeJson(text) {
    try { return text ? JSON.parse(text) : null; } catch (e) { return null; }
  }

  // ---- routes: /admin/, /admin/{collection}?filter=..., /admin/{collection}/{id}, /admin/{collection}/new ----

  function route() {
    const path = location.pathname.startsWith(PREFIX) ? location.pathname.slice(PREFIX.length) : location.pathname;
    const parts = path.split('/').filter(Boolean);
    return {
      collection: parts[0] || null,
      id: parts[1] ? decodeURIComponent(parts[1]) : null,
      query: new URLSearchParams(location.search),
    };
  }

  function href(path, params) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params || {})) {
      if (value !== undefined && value !== null && value !== '' && value !== false) query.set(key, String(value));
    }
    const text = query.toString();
    return `${PREFIX}${path === '/' ? '/' : path}${text ? `?${text}` : ''}`;
  }

  function go(target) {
    if (`${location.pathname}${location.search}` !== target) history.pushState(null, '', target);
    render();
  }

  function recordHref(collection, id, params) {
    return href(`/${collection}/${encodeURIComponent(String(id))}`, params);
  }

  function relogin() {
    auth.forget();
    auth.login(`${location.pathname}${location.search}`);
  }

  // ---- small presentational helpers ----

  function badge(value) {
    return el('span', { class: `badge badge-${String(value)}` }, String(value));
  }

  function stateBadge(rec) {
    return badge(rec.is_deleted ? 'DELETED' : 'ACTIVE');
  }

  function fmtValue(value) {
    if (value === null || value === undefined || value === '') return el('span', { class: 'muted' }, 'пусто');
    if (typeof value === 'boolean') return value ? 'да' : 'нет';
    return String(value);
  }

  function fmtTime(iso) {
    if (!iso || iso === ZERO_TIME) return el('span', { class: 'muted' }, '-');
    return el('time', { datetime: iso, title: `${iso} (UTC)` }, new Date(iso).toLocaleString('ru-RU'));
  }

  function banner(kind, ...content) {
    return el('div', { class: `banner banner-${kind}`, role: kind === 'error' ? 'alert' : 'status' }, ...content);
  }

  function explain(error) {
    if (!(error instanceof ApiError)) return `Ошибка интерфейса: ${error && error.message ? error.message : error}`;
    const hint = STATUS_HINTS[error.status] || '';
    return `${error.status}: ${error.message}. ${hint}`.trim();
  }

  function errorBanner(error, extra) {
    if (!(error instanceof ApiError)) {
      console.error(error);
      return banner('error', explain(error));
    }
    const details = error.details.filter((d) => !d.field).map((d) => d.message);
    return banner('error',
      el('b', {}, `${error.status}`), ' ', error.message, details.length ? ` ${details.join('. ')}` : '',
      el('div', { class: 'hint' }, STATUS_HINTS[error.status] || '', ' ', error.traceId ? el('span', { class: 'mono' }, `trace: ${error.traceId}`) : null),
      extra || null);
  }

  function flash(kind, text) {
    session.flash = { kind, text };
  }

  function showFlash() {
    const box = $('#flash');
    clear(box);
    if (!session.flash) return;
    box.appendChild(banner(session.flash.kind, session.flash.text));
    session.flash = null;
  }

  function crumbs(parts) {
    const nav = $('#crumbs');
    clear(nav);
    parts.forEach(([label, target], index) => {
      if (index) nav.appendChild(document.createTextNode(' / '));
      nav.appendChild(target ? el('a', { href: target }, label) : el('span', {}, label));
    });
  }

  function confirmDialog(text) {
    return new Promise((resolve) => {
      const dialog = $('#confirm');
      $('#confirmText').textContent = text;
      dialog.returnValue = '';
      $('#confirmYes').onclick = () => dialog.close('yes');
      $('#confirmNo').onclick = () => dialog.close('no');
      dialog.addEventListener('close', () => resolve(dialog.returnValue === 'yes'), { once: true });
      dialog.showModal();
    });
  }

  function table(headers, rows) {
    return el('table', {},
      el('thead', {}, el('tr', {}, headers.map((h) => el('th', { scope: 'col', class: h.class || null }, h.label)))),
      el('tbody', {}, rows));
  }

  function todayIso() {
    return new Date().toISOString().slice(0, 10);
  }

  // ---- names of referenced records: one list per catalog, cached for the page ----

  async function labelsOf(collection) {
    if (!session.labels[collection]) {
      session.labels[collection] = api.listAll(collection, { allowDeleted: true })
        .then((items) => {
          const map = new Map();
          for (const item of items) map.set(String(item.id), recordLabel(collection, item));
          return map;
        })
        .catch(() => new Map());
    }
    return session.labels[collection];
  }

  function forgetLabels(collection) {
    delete session.labels[collection];
  }

  async function refCell(field, value) {
    if (value === null || value === undefined) return fmtValue(value);
    const labels = await labelsOf(field.ref);
    const label = labels.get(String(value));
    return el('a', { href: recordHref(field.ref, value) }, label ? `${label} ` : '', el('span', { class: 'mono muted small' }, `#${value}`));
  }

  // ---- rendering ----

  async function render() {
    renderSequence += 1;
    const sequence = renderSequence;
    const view = $('#view');
    showFlash();
    const current = route();
    let node;
    try {
      if (!hasAnyRole(session.user)) node = screenNoAccess();
      else if (!current.collection) node = await screenCatalogs();
      else if (!CATALOGS[current.collection]) node = screenUnknown(current.collection);
      else if (!current.id) node = await screenTable(current);
      else if (current.id === 'new') node = await screenForm(current.collection, null, current.query);
      else if (CATALOGS[current.collection].card) node = await screenCard(current);
      else node = await screenForm(current.collection, current.id, current.query);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) node = el('div', { class: 'card' }, el('p', {}, 'Сессия истекла, выполняется повторный вход…'));
      else node = el('div', {}, errorBanner(error), el('p', {}, el('a', { href: href('/') }, 'К списку справочников')));
    }
    if (sequence !== renderSequence) return;
    replace(view, node);
    window.scrollTo(0, 0);
  }

  function screenUnknown(collection) {
    crumbs([['Справочники', href('/')], [collection, null]]);
    return el('div', { class: 'card' }, el('h2', {}, 'Нет такого справочника'),
      el('p', {}, 'Коллекции ', el('code', {}, `/v1/${collection}/`), ' нет в спецификации. ', el('a', { href: href('/') }, 'К списку справочников')));
  }

  // S-04: a signed-in user without a role of the service
  function screenNoAccess() {
    crumbs([['Нет доступа', null]]);
    return el('div', { class: 'card' },
      el('h2', {}, 'Нет доступа'),
      el('p', {}, 'Учётная запись ', el('b', {}, session.user ? session.user.username : ''), ' вошла, но у неё нет роли сервиса справочников. Роли: reference-reader, reference-hr-reader, reference-admin, reference-hr-admin. Обратитесь к команде справочников.'),
      el('p', {}, el('button', { type: 'button', on: { click: () => auth.logout() } }, 'Выйти и войти другой учётной записью')));
  }

  // S-01: catalogs by group with the number of active records
  async function screenCatalogs() {
    crumbs([['Справочники', null]]);
    const search = el('input', { type: 'search', id: 'catalogSearch', placeholder: 'Название справочника' });
    const sections = [];
    for (const [groupId, group] of Object.entries(GROUPS)) {
      const collections = group.collections.filter((c) => can(session.user, c, 'R'));
      if (!collections.length) continue;
      const rows = collections.map((collection) => {
        const cat = CATALOGS[collection];
        const count = el('td', { class: 'num' }, '…');
        api.list(collection, { pageSize: 100 })
          .then((page) => { count.textContent = `${page.items.length}${page.nextPageToken ? '+' : ''}`; })
          .catch(() => { count.textContent = '-'; });
        return el('tr', { dataset: { title: cat.title.toLowerCase() } },
          el('td', {}, el('a', { href: href(`/${collection}`) }, cat.title)),
          el('td', {}, el('span', { class: 'mono muted' }, `/v1/${collection}/`)),
          count);
      });
      sections.push(el('section', { class: 'card' },
        el('h2', {}, group.title, ' ', el('span', { class: 'muted small' }, groupId)),
        table([{ label: 'Справочник' }, { label: 'Коллекция' }, { label: 'Активных записей', class: 'num' }], rows)));
    }
    const root = el('div', {},
      el('div', { class: 'toolbar' }, el('label', { for: 'catalogSearch' }, 'Поиск'), search),
      sections,
      el('p', { class: 'hint' }, 'Справочники salaries и absences видны только ролям reference-hr-reader и reference-hr-admin. Число записей считается по первой странице, "100+" означает, что страниц больше.'));
    search.addEventListener('input', () => {
      const needle = search.value.trim().toLowerCase();
      for (const row of root.querySelectorAll('tbody tr')) row.hidden = needle !== '' && !row.dataset.title.includes(needle);
    });
    return root;
  }

  // ---- S-02: the table of one catalog ----

  function filterPlaceholder(collection) {
    const examples = {
      employees: 'employment_state = "EMPLOYED" AND org_unit_id = 2',
      org_units: 'kind = "TEAM" AND parent_id = 1',
      assignments: 'employee_id = 1 AND NOT end_date:*',
      salaries: 'amount >= 150000',
      absences: 'kind = "VACATION" AND start_date >= "2026-07-01"',
      countries: 'name:"Р" AND currency_id = 1',
    };
    return examples[collection] || 'name:"евро"';
  }

  function orderOptions(collection, selected) {
    const options = [];
    for (const field of queryFields(collection)) options.push(field, `${field} desc`);
    return [el('option', { value: '', selected: !selected }, 'порядок создания'), ...options.map((o) => el('option', { value: o, selected: o === selected }, o))];
  }

  function tableParams(query) {
    return {
      filter: query.get('filter') || '',
      orderBy: query.get('order_by') || '',
      allowDeleted: query.get('allowDeleted') === 'true',
      pageSize: Number(query.get('pageSize')) || 20,
      pageToken: query.get('pageToken') || '',
    };
  }

  function tableHref(collection, params, pageToken) {
    return href(`/${collection}`, {
      filter: params.filter,
      order_by: params.orderBy,
      allowDeleted: params.allowDeleted,
      pageSize: params.pageSize === 20 ? '' : params.pageSize,
      pageToken: pageToken || '',
    });
  }

  function cellFor(collection, rec, column) {
    const value = rec[column];
    const field = fieldByName(collection, column);
    if (column === 'id') return el('td', {}, el('a', { href: recordHref(collection, rec.id), class: 'mono' }, `#${rec.id}`));
    if (column === 'is_deleted') return el('td', {}, stateBadge(rec));
    if (field && field.type === 'enum') return el('td', {}, value ? badge(value) : fmtValue(value));
    if (field && field.type === 'ref') {
      const cell = el('td', {}, fmtValue(value));
      refCell(field, value).then((node) => replace(cell, node));
      return cell;
    }
    if (typeof value === 'number') return el('td', { class: 'num' }, String(value));
    if (column === 'created_at' || column === 'updated_at' || column === 'deleted_at') return el('td', {}, fmtTime(value));
    return el('td', {}, fmtValue(value));
  }

  async function screenTable(current) {
    const collection = current.collection;
    const cat = CATALOGS[collection];
    const user = session.user;
    const params = tableParams(current.query);
    crumbs([['Справочники', href('/')], [cat.title, null]]);

    const filterInput = el('input', { type: 'text', id: 'filter', class: 'mono wide', value: params.filter, placeholder: filterPlaceholder(collection), 'aria-describedby': 'filterHint' });
    const orderSelect = el('select', { id: 'orderBy', 'aria-label': 'Сортировка' }, orderOptions(collection, params.orderBy));
    const allowDeleted = el('input', { type: 'checkbox', id: 'allowDeleted', checked: params.allowDeleted });
    const pageSize = el('select', { id: 'pageSize', 'aria-label': 'Размер страницы' }, PAGE_SIZES.map((n) => el('option', { value: n, selected: n === params.pageSize }, `${n} на странице`)));
    const form = el('form', {
      class: 'toolbar',
      on: {
        submit: (event) => {
          event.preventDefault();
          session.pager[collection] = [];
          go(tableHref(collection, { filter: filterInput.value.trim(), orderBy: orderSelect.value, allowDeleted: allowDeleted.checked, pageSize: Number(pageSize.value) }, ''));
        },
      },
    },
    el('label', { for: 'filter' }, 'filter'), filterInput,
    el('label', { for: 'orderBy' }, 'order_by'), orderSelect,
    el('label', {}, allowDeleted, ' allowDeleted'),
    pageSize,
    el('button', { type: 'submit', class: 'primary' }, 'Применить'));

    const resultBox = el('div', { id: 'tableBanner' });
    const actions = el('div', { class: 'toolbar' });
    if (can(user, collection, 'X')) actions.appendChild(el('button', { type: 'button', id: 'export', on: { click: () => exportCatalog(collection, resultBox) } }, 'Выгрузить в Excel'));
    if (can(user, collection, 'C')) actions.appendChild(el('a', { class: 'button primary', id: 'create', href: href(`/${collection}/new`) }, 'Создать запись'));
    const hint = el('p', { class: 'hint', id: 'filterHint' },
      'Поля фильтра: ', queryFields(collection).join(', '), '. Синтаксис AIP-160: =, !=, :, <, <=, >, >=, AND, OR, NOT, скобки, поле:* (есть значение), строки в кавычках. Сортировка: поле или "поле desc". Выгрузка содержит все неудалённые записи справочника без истории.');

    const root = el('div', {},
      el('h2', {}, cat.title, ' ', el('span', { class: 'muted mono small' }, `/v1/${collection}/`)),
      resultBox, form, hint, actions);

    let page;
    try {
      page = await api.list(collection, params);
    } catch (error) {
      if (error instanceof ApiError && error.status === 400) {
        const errors = error.fieldErrors;
        if (errors.filter || /filter/i.test(error.message)) filterInput.classList.add('invalid');
        root.appendChild(errorBanner(error));
        return root;
      }
      throw error;
    }

    const columns = listColumns(collection);
    const rows = page.items;
    const body = rows.length
      ? rows.map((rec) => el('tr', { class: rec.is_deleted ? 'deleted' : null }, columns.map((column) => cellFor(collection, rec, column))))
      : [el('tr', {}, el('td', { colspan: columns.length, class: 'muted' }, 'Записей нет', can(user, collection, 'C') ? ', создайте первую' : '', '.'))];
    root.appendChild(el('div', { class: 'table-wrap' }, table(columns.map((c) => ({ label: fieldLabel(collection, c) })), body)));

    const stack = session.pager[collection] || [];
    const pager = el('div', { class: 'pager' },
      el('span', { class: 'muted' }, `на странице: ${rows.length}, pageSize: ${params.pageSize}`),
      el('button', {
        type: 'button',
        disabled: !stack.length,
        on: { click: () => { const token = stack.pop(); session.pager[collection] = stack; go(tableHref(collection, params, token)); } },
      }, 'Назад'),
      el('button', {
        type: 'button',
        disabled: !page.nextPageToken,
        on: { click: () => { stack.push(params.pageToken); session.pager[collection] = stack; go(tableHref(collection, params, page.nextPageToken)); } },
      }, 'Вперёд'));
    root.appendChild(pager);
    return root;
  }

  function download(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = el('a', { href: url, download: filename });
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function exportCatalog(collection, box) {
    replace(box, banner('ok', 'Выгрузка выполняется…'));
    try {
      const file = await api.exportFile(collection);
      download(file.blob, file.filename);
      replace(box, banner('ok', `Файл ${file.filename} получен (${file.blob.size} байт). Запрос: POST /v1/${collection}/export.`));
    } catch (error) {
      replace(box, errorBanner(error));
    }
  }

  // ---- S-03: the record form with the details and the history panel ----

  function fieldInput(collection, field, value, locked) {
    const inputId = `f-${field.name}`;
    const common = { id: inputId, name: field.name };
    switch (field.type) {
      case 'enum':
        return el('select', { ...common, disabled: locked },
          el('option', { value: '' }, '-'),
          field.values.map((v) => el('option', { value: v, selected: v === value }, v)));
      case 'integer':
        return el('input', { ...common, type: 'number', step: '1', min: field.min, max: field.max, value: normalize(value), readOnly: locked });
      case 'money':
        return el('input', { ...common, type: 'number', step: '0.01', min: field.min, value: normalize(value), readOnly: locked });
      case 'date':
        return el('input', { ...common, type: 'date', value: normalize(value), readOnly: locked });
      case 'email':
        return el('input', { ...common, type: 'email', value: normalize(value), readOnly: locked, autocomplete: 'off' });
      case 'ref': {
        const listId = `dl-${collection}-${field.name}`;
        const input = el('input', { ...common, type: 'text', class: 'mono', value: normalize(value), readOnly: locked, list: listId, placeholder: 'идентификатор', autocomplete: 'off', inputmode: 'numeric' });
        const datalist = el('datalist', { id: listId });
        const chosen = el('span', { class: 'hint ref-label' });
        const showLabel = async () => {
          const labels = await labelsOf(field.ref);
          const label = labels.get(String(input.value.trim()));
          chosen.textContent = input.value.trim() ? (label ? `${CATALOGS[field.ref].title}: ${label}` : 'записи с таким идентификатором нет') : '';
        };
        labelsOf(field.ref).then((labels) => {
          replace(datalist, [...labels.entries()].map(([id, label]) => el('option', { value: id }, label)));
          showLabel();
        });
        input.addEventListener('input', showLabel);
        return el('span', { class: 'ref' }, input, datalist, chosen);
      }
      default:
        return el('input', { ...common, type: 'text', value: normalize(value), readOnly: locked, autocomplete: 'off', maxlength: field.maxLen || null });
    }
  }

  function fieldBox(label, name, note, control) {
    const input = control.matches('input, select') ? control : control.querySelector('input, select');
    return el('div', { class: 'field', dataset: { field: name } },
      el('label', { for: input.id }, label, ' ', el('span', { class: 'muted small' }, note)),
      control,
      el('div', { class: 'error', id: `${input.id}-error` }));
  }

  // builds the form card: used standalone on S-03 and inside the employee card S-05
  function buildFormPanel(collection, rec, query, backTo) {
    const cat = CATALOGS[collection];
    const user = session.user;
    const isNew = !rec;
    const editable = isNew ? can(user, collection, 'C') : can(user, collection, 'U') && !rec.is_deleted;
    const draftKey = `rm.draft:${collection}:${isNew ? 'new' : rec.id}`;
    const draft = editable ? safeJson(storageGet(draftKey)) : null;
    const inputs = {};
    const boxes = {};

    const initial = (name) => {
      if (draft && name in draft) return draft[name];
      if (isNew && query && query.has(name)) return query.get(name);
      return rec ? rec[name] : '';
    };

    const formBanner = el('div', {});
    const fields = [];
    for (const field of inputFields(collection)) {
      const locked = !editable || (field.immutable && !isNew) || (isNew && field.immutable && query && query.has(field.name));
      const control = fieldInput(collection, field, initial(field.name), locked);
      const input = control.matches('input, select') ? control : control.querySelector('input, select');
      inputs[field.name] = input;
      const notes = [field.name];
      if (field.required) notes.push('обязательно');
      if (field.immutable && !isNew) notes.push('не меняется');
      if (field.hint) notes.push(field.hint);
      if (field.type === 'ref') notes.push(`идентификатор записи ${field.ref}`);
      boxes[field.name] = fieldBox(field.label, field.name, notes.join(', '), control);
      fields.push(boxes[field.name]);
    }

    const clearErrors = () => {
      for (const box of Object.values(boxes)) { box.classList.remove('invalid'); box.querySelector('.error').textContent = ''; }
      clear(formBanner);
    };

    const showFieldErrors = (error) => {
      const errors = error.fieldErrors;
      let marked = 0;
      for (const [field, message] of Object.entries(errors)) {
        const box = boxes[field];
        if (!box) continue;
        box.classList.add('invalid');
        box.querySelector('.error').textContent = message;
        marked += 1;
      }
      const rest = Object.entries(errors).filter(([field]) => !boxes[field]).map(([field, message]) => `${field}: ${message}`);
      replace(formBanner, banner('error', el('b', {}, `400 ${error.message}`), marked ? ', см. подписи у полей.' : '.', rest.length ? ` ${rest.join('. ')}` : ''));
    };

    const actions = el('div', { class: 'toolbar' });
    const busy = (state) => { for (const button of actions.querySelectorAll('button')) button.disabled = state; };
    if (editable) actions.appendChild(el('button', { type: 'submit', class: 'primary', id: 'save' }, 'Сохранить'));
    if (!isNew && can(user, collection, 'D') && !rec.is_deleted) {
      actions.appendChild(el('button', {
        type: 'button',
        class: 'danger',
        id: 'delete',
        on: {
          click: async () => {
            if (!await confirmDialog(`Удалить ${recordLabel(collection, rec)} (#${rec.id})? Запись перейдёт в состояние DELETED, идентификатор останется занятым, восстановления нет: удалённая по ошибке запись создаётся заново.`)) return;
            busy(true);
            try {
              await api.remove(collection, rec.id);
              forgetLabels(collection);
              flash('ok', `Запись #${rec.id} удалена: is_deleted = true, новая ревизия.`);
              render();
            } catch (error) { replace(formBanner, errorBanner(error)); busy(false); }
          },
        },
      }, 'Удалить'));
    }
    if (!isNew && can(user, collection, 'D') && rec.is_deleted) {
      actions.appendChild(el('button', {
        type: 'button',
        class: 'danger',
        id: 'purge',
        on: {
          click: async () => {
            if (!await confirmDialog(`Удалить ${recordLabel(collection, rec)} (#${rec.id}) окончательно вместе с историей? Это действие нельзя отменить.`)) return;
            busy(true);
            try {
              await api.remove(collection, rec.id, true);
              forgetLabels(collection);
              flash('ok', `Запись #${rec.id} удалена окончательно вместе с ревизиями (force=true).`);
              go(href(`/${collection}`));
            } catch (error) { replace(formBanner, errorBanner(error)); busy(false); }
          },
        },
      }, 'Удалить окончательно'));
    }
    actions.appendChild(el('a', { class: 'button', href: backTo }, 'Назад'));

    const form = el('form', { class: 'record-form', autocomplete: 'off' }, fields, actions);
    if (editable) {
      form.addEventListener('input', () => {
        const values = {};
        for (const [name, input] of Object.entries(inputs)) values[name] = input.value;
        storageSet(draftKey, JSON.stringify(values));
      });
    }
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      clearErrors();
      const values = {};
      for (const [name, input] of Object.entries(inputs)) values[name] = input.value;
      busy(true);
      try {
        if (isNew) {
          const created = await api.create(collection, toBody(collection, values));
          storageSet(draftKey, null);
          forgetLabels(collection);
          const note = collection === 'employees' ? ` Учётная запись в Keycloak: ${created.account_state}.` : '';
          flash('ok', `Создана запись #${created.id} (${recordLabel(collection, created)}), ревизия 1.${note}`);
          go(query && query.get('back') ? query.get('back') : recordHref(collection, created.id));
        } else {
          const mask = updateMask(collection, rec, values);
          if (!mask.length) { replace(formBanner, banner('warn', 'Изменений нет: updateMask пуст, запрос не отправлен.')); busy(false); return; }
          const updated = await api.update(collection, rec.id, toBody(collection, values), mask.join(','));
          storageSet(draftKey, null);
          forgetLabels(collection);
          const note = collection === 'employees' && mask.some((n) => (fieldByName(collection, n) || {}).account) ? ` Изменение передано в учётную запись: ${updated.account_state}.` : '';
          flash('ok', `Сохранено: updateMask = ${mask.join(', ')}, ревизия ${updated.revision}.${note}`);
          render();
        }
      } catch (error) {
        busy(false);
        if (error instanceof ApiError && error.status === 400 && Object.keys(error.fieldErrors).length) { showFieldErrors(error); return; }
        if (error instanceof ApiError && error.status === 503 && collection === 'employees') {
          storageSet(draftKey, null);
          flash('warn', explain(error));
          await openPendingEmployee(values.username, rec ? rec.id : null);
          return;
        }
        if (error instanceof ApiError && error.status === 409 && !isNew) {
          replace(formBanner, errorBanner(error, el('button', { type: 'button', on: { click: () => { storageSet(draftKey, null); render(); } } }, 'Перечитать запись')));
          return;
        }
        replace(formBanner, errorBanner(error));
      }
    });

    const title = isNew ? `Новая запись: ${cat.title}` : `${recordLabel(collection, rec)}`;
    const card = el('div', { class: 'card' },
      el('h2', {}, title, ' ', el('span', { class: 'muted mono small' }, isNew ? `POST /v1/${collection}/` : `/v1/${collection}/${rec.id}`)),
      formBanner,
      draft ? banner('warn', 'Восстановлен черновик формы из этого окна браузера.') : null,
      !editable && !isNew ? el('p', { class: 'hint' }, rec.is_deleted ? 'Запись удалена: поля только для чтения, восстановления нет.' : 'Только чтение: у роли нет уровня update на эту группу справочников.') : null,
      form);

    // a new dated record is checked against the record still in effect for the same employee
    if (isNew && cat.dated && collection !== 'absences' && inputs.employee_id && inputs.employee_id.value) {
      api.list(collection, { filter: `employee_id = ${Number(inputs.employee_id.value)} AND NOT end_date:*`, pageSize: 1 })
        .then((page) => {
          const open = page.items[0];
          if (!open) return;
          formBanner.appendChild(banner('warn', `Действующая запись #${open.id} с ${open.start_date} не закрыта. Сначала закройте её датой на карточке сотрудника, иначе периоды пересекутся и запрос будет отклонён.`));
        })
        .catch(() => {});
    }
    return card;
  }

  // after UNAVAILABLE the profile is stored with PENDING: the card is opened by the login of the employee
  async function openPendingEmployee(username, knownId) {
    if (knownId) { go(recordHref('employees', knownId)); return; }
    try {
      const page = await api.list('employees', { filter: `username = "${username}"`, pageSize: 1 });
      if (page.items[0]) { go(recordHref('employees', page.items[0].id)); return; }
    } catch (e) {
      // the list is only a convenience, the flash already explains the state
    }
    go(href('/employees'));
  }

  function metaCard(collection, rec) {
    const rows = [];
    for (const field of COMMON) {
      let value;
      if (field.name === 'is_deleted') value = stateBadge(rec);
      else if (field.name === 'created_at' || field.name === 'updated_at' || field.name === 'deleted_at') value = fmtTime(rec[field.name]);
      else if (field.name === 'last_changer') value = el('span', { class: 'mono' }, rec.last_changer);
      else value = fmtValue(rec[field.name]);
      rows.push(el('dt', {}, field.label, ' ', el('span', { class: 'mono muted small' }, field.name)), el('dd', {}, value));
    }
    return el('div', { class: 'card' }, el('h3', {}, 'Сведения'), el('dl', { class: 'meta' }, rows));
  }

  function revisionKind(revision) {
    if (revision.revision_number === 1) return 'CREATED';
    if ((revision.change || []).some((op) => op.path === '/is_deleted' && op.value === true)) return 'DELETED';
    return 'UPDATED';
  }

  async function historyCard(collection, rec) {
    const box = el('div', { class: 'card' },
      el('h3', {}, 'История'),
      el('p', { class: 'hint mono' }, `GET /v1/${collection}/${rec.id}/revisions`, ' ', el('span', { class: 'sans' }, 'от новой к старой, операции JSON Patch')));
    let revisions;
    try {
      revisions = await api.allRevisions(collection, rec.id, rec.is_deleted);
    } catch (error) {
      box.appendChild(errorBanner(error));
      return box;
    }
    revisions.sort((a, b) => b.revision_number - a.revision_number);
    const asOf = el('div', {});
    const showAsOf = (number) => {
      const state = stateAt(revisions, number);
      replace(asOf, el('div', { class: 'banner banner-warn' },
        el('b', {}, `Состояние на ревизию ${number}`), ' ', el('span', { class: 'hint' }, 'собрано из операций ревизий 1..', String(number)),
        el('dl', { class: 'meta compact' }, Object.entries(state).map(([key, value]) => [el('dt', {}, fieldLabel(collection, key), ' ', el('span', { class: 'mono muted small' }, key)), el('dd', {}, fmtValue(value))]))));
    };
    for (const revision of revisions) {
      box.appendChild(el('div', { class: 'revision' },
        el('div', { class: 'revision-head' },
          el('b', {}, `${revision.revision_number}`), ' ', badge(revisionKind(revision)), ' ', fmtTime(revision.changed_at), ' ',
          el('span', { class: 'muted mono small' }, revision.changed_by), ' ',
          el('button', { type: 'button', class: 'link', on: { click: () => showAsOf(revision.revision_number) } }, 'на ревизию')),
        el('ul', { class: 'changes' }, (revision.change || []).map((op) => el('li', {}, el('code', {}, `${op.op} ${fieldOf(op)}`), ': ', fmtValue(op.value))))));
    }
    if (!revisions.length) box.appendChild(el('p', { class: 'muted' }, 'Ревизий нет.'));
    box.appendChild(asOf);
    return box;
  }

  async function screenForm(collection, id, query) {
    const cat = CATALOGS[collection];
    const isNew = id === null;
    const rec = isNew ? null : await api.get(collection, id, true);
    let backTo = query.get('back') || href(`/${collection}`);
    if (!query.get('back') && rec && cat.dated && rec.employee_id) backTo = recordHref('employees', rec.employee_id, { tab: collection });
    crumbs([['Справочники', href('/')], [cat.title, href(`/${collection}`)], [isNew ? 'Новая запись' : `#${rec.id}`, null]]);
    const panel = buildFormPanel(collection, rec, query, backTo);
    if (isNew) return el('div', { class: 'layout' }, panel, el('div', {}, el('div', { class: 'card' }, el('h3', {}, 'Сведения'), el('p', { class: 'muted' }, 'Идентификатор назначит сервис, первая ревизия появится после сохранения.'))));
    return el('div', { class: 'layout' }, panel, el('div', {}, metaCard(collection, rec), await historyCard(collection, rec)));
  }

  // ---- S-05: the employee card ----

  function statusCard(rec) {
    const user = session.user;
    const manage = can(user, 'employees', 'U');
    const card = el('div', { class: 'card' },
      el('h2', {}, recordLabel('employees', rec), ' ', el('span', { class: 'muted mono small' }, `/v1/employees/${rec.id}`)),
      el('dl', { class: 'meta columns' },
        el('dt', {}, 'Состояние занятости ', el('span', { class: 'mono muted small' }, 'employment_state')), el('dd', {}, badge(rec.employment_state)),
        el('dt', {}, 'Дата приёма ', el('span', { class: 'mono muted small' }, 'hire_date')), el('dd', {}, rec.hire_date),
        el('dt', {}, 'Дата увольнения ', el('span', { class: 'mono muted small' }, 'dismissal_date')), el('dd', {}, fmtValue(rec.dismissal_date)),
        el('dt', {}, 'Учётная запись ', el('span', { class: 'mono muted small' }, 'account_state')), el('dd', {}, badge(rec.account_state)),
        el('dt', {}, 'Идентификатор учётной записи ', el('span', { class: 'mono muted small' }, 'account_user_id')), el('dd', { class: 'mono' }, fmtValue(rec.account_user_id)),
        el('dt', {}, 'Запись'), el('dd', {}, stateBadge(rec))));
    if (rec.account_state === 'PENDING') {
      card.appendChild(banner('warn',
        'Операция с учётной записью не завершена: запись сохранена, Keycloak её ещё не подтвердил. ',
        manage ? el('button', {
          type: 'button',
          id: 'syncAccount',
          on: {
            click: async () => {
              try {
                const synced = await api.syncAccount(rec.id);
                flash('ok', `Операция с учётной записью завершена: account_state = ${synced.account_state}. Запрос: POST /v1/employees/${rec.id}/syncAccount.`);
              } catch (error) {
                flash(error instanceof ApiError && error.status === 503 ? 'warn' : 'error', explain(error));
              }
              render();
            },
          },
        }, 'Повторить операцию с учётной записью') : null));
    }
    if (manage && rec.employment_state === 'EMPLOYED' && !rec.is_deleted) {
      const date = el('input', { type: 'date', id: 'dismissalDate', value: todayIso() });
      const error = el('div', { class: 'error' });
      card.appendChild(el('form', {
        class: 'toolbar dismiss',
        on: {
          submit: async (event) => {
            event.preventDefault();
            error.textContent = '';
            if (!await confirmDialog(`Уволить ${recordLabel('employees', rec)} с ${date.value}? Вход сотрудника будет закрыт, действующие назначение и оклад будут закрыты этой датой.`)) return;
            try {
              await api.dismiss(rec.id, date.value);
              flash('ok', `Сотрудник уволен с ${date.value}: назначение и оклад закрыты этой датой, учётная запись заблокирована. Запрос: POST /v1/employees/${rec.id}/dismiss.`);
            } catch (err) {
              if (err instanceof ApiError && err.status === 400 && Object.keys(err.fieldErrors).length) { error.textContent = Object.entries(err.fieldErrors).map(([f, m]) => `${f}: ${m}`).join('. '); return; }
              flash(err instanceof ApiError && err.status === 503 ? 'warn' : 'error', explain(err));
            }
            forgetLabels('employees');
            render();
          },
        },
      },
      el('label', { for: 'dismissalDate' }, 'Дата увольнения'), date,
      el('button', { type: 'submit', class: 'danger', id: 'dismiss' }, 'Уволить'),
      error));
    }
    return card;
  }

  async function currentValuesCard(rec) {
    const today = todayIso();
    const rows = [
      el('dt', {}, 'Подразделение'), el('dd', {}, await refCell(fieldByName('employees', 'org_unit_id'), rec.org_unit_id)),
      el('dt', {}, 'Должность'), el('dd', {}, await refCell(fieldByName('employees', 'position_id'), rec.position_id)),
    ];
    if (can(session.user, 'salaries', 'R')) {
      let text = el('span', { class: 'muted' }, 'нет действующего оклада');
      try {
        const page = await api.list('salaries', { filter: `employee_id = ${rec.id} AND start_date <= "${today}" AND (end_date >= "${today}" OR NOT end_date:*)`, pageSize: 1 });
        const salary = page.items[0];
        if (salary) text = el('span', {}, `${salary.amount} `, await refCell(fieldByName('salaries', 'currency_id'), salary.currency_id), ' ', el('span', { class: 'muted' }, `с ${salary.start_date}`));
      } catch (error) {
        text = errorBanner(error);
      }
      rows.push(el('dt', {}, 'Оклад'), el('dd', {}, text));
    }
    return el('div', { class: 'card' }, el('h3', {}, 'Действующие значения'), el('p', { class: 'hint' }, `на ${today}, из назначения и оклада с периодом действия`), el('dl', { class: 'meta' }, rows));
  }

  function periodLabel(row) {
    return `${row.start_date} - ${row.end_date || 'сейчас'}`;
  }

  async function periodDetails(collection, row) {
    if (collection === 'assignments') return el('span', {}, await refCell(fieldByName('assignments', 'org_unit_id'), row.org_unit_id), ', ', await refCell(fieldByName('assignments', 'position_id'), row.position_id));
    if (collection === 'salaries') return el('span', {}, `${row.amount} `, await refCell(fieldByName('salaries', 'currency_id'), row.currency_id));
    return badge(row.kind);
  }

  async function periodsCard(rec, requested) {
    const user = session.user;
    const tabs = DATED_TABS.filter(([collection]) => can(user, collection, 'R'));
    const active = tabs.some(([collection]) => collection === requested) ? requested : tabs[0][0];
    const nav = el('div', { class: 'tabs', role: 'tablist' }, tabs.map(([collection, label]) => el('a', {
      role: 'tab', class: 'tab', 'aria-selected': collection === active ? 'true' : 'false', href: recordHref('employees', rec.id, { tab: collection }),
    }, label)));
    const card = el('div', { class: 'card' }, el('h3', {}, 'Периоды'), nav);
    let rows;
    try {
      rows = await api.listAll(active, { filter: `employee_id = ${rec.id}`, orderBy: 'start_date desc' });
    } catch (error) {
      card.appendChild(errorBanner(error));
      return card;
    }
    const backTo = recordHref('employees', rec.id, { tab: active });
    const openRow = rows.find((row) => !row.end_date);
    const body = [];
    for (const row of rows) {
      const cells = [
        el('td', {}, el('a', { href: recordHref(active, row.id, { back: backTo }), class: 'mono' }, `#${row.id}`)),
        el('td', {}, periodLabel(row)),
        el('td', {}, await periodDetails(active, row)),
      ];
      const actionCell = el('td', {});
      if (!row.end_date && can(user, active, 'U') && rec.employment_state === 'EMPLOYED') {
        const date = el('input', { type: 'date', value: todayIso(), 'aria-label': `Дата окончания #${row.id}` });
        actionCell.appendChild(el('form', {
          class: 'inline',
          on: {
            submit: async (event) => {
              event.preventDefault();
              try {
                await api.update(active, row.id, toBody(active, { ...row, end_date: date.value }), 'end_date');
                flash('ok', `Запись #${row.id} закрыта датой ${date.value}: updateMask = end_date.`);
              } catch (error) {
                flash('error', explain(error));
              }
              render();
            },
          },
        }, date, el('button', { type: 'submit' }, 'Закрыть датой')));
      }
      cells.push(actionCell);
      body.push(el('tr', {}, cells));
    }
    card.appendChild(table([{ label: 'Запись' }, { label: 'Период' }, { label: 'Значение' }, { label: '' }],
      body.length ? body : [el('tr', {}, el('td', { colspan: 4, class: 'muted' }, 'Записей нет.'))]));
    const actions = el('div', { class: 'toolbar' });
    if (can(user, active, 'C') && rec.employment_state === 'EMPLOYED') {
      actions.appendChild(el('a', { class: 'button primary', href: href(`/${active}/new`, { employee_id: rec.id, back: backTo }) }, 'Добавить'));
    }
    if (openRow && active !== 'absences' && can(user, active, 'C') && rec.employment_state === 'EMPLOYED') {
      actions.appendChild(el('span', { class: 'hint' }, `Действующая запись #${openRow.id} не закрыта: перед добавлением новой закройте её датой, иначе периоды пересекутся.`));
    }
    card.appendChild(actions);
    return card;
  }

  async function screenCard(current) {
    const rec = await api.get('employees', current.id, true);
    crumbs([['Справочники', href('/')], ['Сотрудники', href('/employees')], [recordLabel('employees', rec), null]]);
    const left = el('div', {}, statusCard(rec), buildFormPanel('employees', rec, current.query, href('/employees')));
    const right = el('div', {}, await currentValuesCard(rec), await periodsCard(rec, current.query.get('tab') || 'assignments'), await historyCard('employees', rec));
    return el('div', { class: 'layout' }, left, right);
  }

  // ---- start: the login comes first, the screens need a user ----

  function showHeader() {
    const user = session.user;
    replace($('#who'), user ? [el('b', {}, user.username), ' ', el('span', { class: 'muted' }, user.roles.filter((r) => r.startsWith('reference-')).join(', ') || 'без ролей сервиса')] : '');
    $('#logout').hidden = !user;
  }

  function interceptLinks() {
    document.addEventListener('click', (event) => {
      const link = event.target.closest('a[href]');
      if (!link || link.target || link.hasAttribute('download') || event.metaKey || event.ctrlKey || event.shiftKey) return;
      const url = new URL(link.href, location.href);
      if (url.origin !== location.origin || !url.pathname.startsWith(PREFIX)) return;
      event.preventDefault();
      go(`${url.pathname}${url.search}`);
    });
  }

  async function init() {
    const view = $('#view');
    $('#logout').addEventListener('click', () => auth.logout());
    try {
      const returnTo = await auth.handleRedirect();
      if (returnTo) history.replaceState(null, '', returnTo);
    } catch (error) {
      replace(view, el('div', { class: 'card' }, banner('error', `Вход не выполнен: ${error.message}`),
        el('button', { type: 'button', on: { click: () => auth.login(href('/')) } }, 'Войти снова')));
      return;
    }
    const token = await auth.token();
    if (!token) {
      replace(view, el('div', { class: 'card' }, el('p', {}, 'Перенаправление на вход в Keycloak…')));
      await auth.login();
      return;
    }
    session.user = auth.user();
    showHeader();
    interceptLinks();
    window.addEventListener('popstate', render);
    render();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
