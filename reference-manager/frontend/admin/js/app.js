// screens S-01..S-05 of document 110 on top of the mock API, the route lives in the location hash
(function () {
  'use strict';

  const { el, replace, clear, $ } = RM.dom;
  const { CATALOGS, GROUPS, USERS, can, storedFields, queryFields, refTarget } = RM.catalogs;
  const { ApiError } = RM.mockApi;
  const api = RM.mockApi.createApi();

  const PAGE_SIZES = [10, 20, 50, 100];
  const DATED_TABS = [['assignments', 'Назначения'], ['salaries', 'Оклады'], ['absences', 'Отсутствия']];
  const STATUS_HINTS = {
    INVALID_ARGUMENT: 'Запрос отклонён: проверьте отмеченные поля.',
    FAILED_PRECONDITION: 'Действие невозможно в текущем состоянии записи.',
    NOT_FOUND: 'Запись не найдена.',
    ALREADY_EXISTS: 'Запись с таким идентификатором уже есть.',
    PERMISSION_DENIED: 'Нет доступа: у роли нет нужного уровня на эту группу справочников.',
    UNAUTHENTICATED: 'Требуется вход: запрос пришёл без токена.',
    UNAVAILABLE: 'Keycloak не подтвердил операцию: профиль сохранён, состояние учётной записи PENDING. Повторите операцию позже.',
  };
  const REASON_HINTS = {
    EXPORT_TOO_LARGE: 'Сузьте отбор фильтром и повторите выгрузку.',
    ACCOUNT_CONFLICT: 'Логин занят чужой учётной записью в Keycloak. Нужен администратор Keycloak.',
    EMPLOYEE_ACTIVE: 'Сначала уволите сотрудника.',
    RECORD_DELETED: 'Сначала восстановите запись.',
    RECORD_EXISTS: 'Выберите другой идентификатор или восстановите удалённую запись.',
    ALREADY_DISMISSED: 'Сотрудник уже уволен.',
    ACCOUNT_PENDING: 'Повторите операцию с учётной записью, когда Keycloak будет доступен.',
  };

  const session = { user: USERS[0], flash: null, pager: {} };
  let renderSequence = 0;

  // ---- storage of per-browser conveniences: the chosen role and unsent drafts ----

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

  function setUser(key) {
    session.user = USERS.find((u) => u.key === key) || USERS[0];
    storageSet('rm.user', session.user.key);
    $('#who').textContent = session.user.username || 'нет токена';
  }

  // ---- routes: #/{collection}?filter=..., #/{collection}/{id}, #/{collection}/new ----

  function route() {
    const hash = location.hash.replace(/^#/, '') || '/';
    const [path, query] = hash.split('?');
    const parts = path.split('/').filter(Boolean);
    return {
      collection: parts[0] || null,
      id: parts[1] ? decodeURIComponent(parts[1]) : null,
      query: new URLSearchParams(query || ''),
    };
  }

  function href(path, params) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params || {})) {
      if (value !== undefined && value !== null && value !== '' && value !== false) query.set(key, String(value));
    }
    const text = query.toString();
    return `#${path}${text ? `?${text}` : ''}`;
  }

  function go(target) {
    if (location.hash === target) render();
    else location.hash = target;
  }

  function idOf(name) {
    return name.split('/').pop();
  }

  function recordHref(name) {
    const target = refTarget(name);
    return target ? href(`/${target.collection}/${encodeURIComponent(target.id)}`) : '#/';
  }

  // ---- small presentational helpers ----

  function badge(value) {
    return el('span', { class: `badge badge-${String(value)}` }, String(value));
  }

  function fmtValue(value) {
    if (value === null || value === undefined || value === '') return el('span', { class: 'muted' }, 'пусто');
    return String(value);
  }

  function fmtTime(iso) {
    if (!iso) return el('span', { class: 'muted' }, '-');
    return el('time', { datetime: iso, title: `${iso} (UTC)` }, new Date(iso).toLocaleString('ru-RU'));
  }

  function refLink(value) {
    const target = refTarget(value);
    if (!target || !CATALOGS[target.collection]) return fmtValue(value);
    return el('a', { href: recordHref(value), class: 'mono' }, value);
  }

  function banner(kind, ...content) {
    return el('div', { class: `banner banner-${kind}`, role: kind === 'error' ? 'alert' : 'status' }, ...content);
  }

  function explain(error) {
    if (!(error instanceof ApiError)) return `Ошибка интерфейса: ${error && error.message ? error.message : error}`;
    const hint = REASON_HINTS[error.reason] || STATUS_HINTS[error.status] || '';
    return `${error.status} (${error.code}): ${error.message}. ${hint}`.trim();
  }

  function errorBanner(error) {
    if (!(error instanceof ApiError)) {
      console.error(error);
      return banner('error', explain(error));
    }
    const hint = REASON_HINTS[error.reason] || STATUS_HINTS[error.status] || '';
    return banner('error',
      el('b', {}, `${error.status} ${error.code}`), ' ', error.message,
      el('div', { class: 'hint' }, hint, ' ', el('span', { class: 'mono' }, `request_id: ${error.requestId}`)));
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

  // ---- rendering ----

  async function render() {
    renderSequence += 1;
    const sequence = renderSequence;
    const view = $('#view');
    showFlash();
    const current = route();
    let node;
    try {
      if (session.user.anonymous) node = screenNoAccess('UNAUTHENTICATED');
      else if (!current.collection) node = await screenCatalogs();
      else if (!CATALOGS[current.collection]) node = screenUnknown(current.collection);
      else if (!current.id) node = await screenTable(current);
      else if (current.id === 'new') node = await screenForm(current.collection, null, current.query);
      else if (CATALOGS[current.collection].card) node = await screenCard(current);
      else node = await screenForm(current.collection, current.id, current.query);
    } catch (error) {
      if (error instanceof ApiError && (error.status === 'PERMISSION_DENIED' || error.status === 'UNAUTHENTICATED')) node = screenNoAccess(error.status, error);
      else node = el('div', {}, errorBanner(error), el('p', {}, el('a', { href: href('/') }, 'К списку справочников')));
    }
    if (sequence !== renderSequence) return;
    replace(view, node);
    window.scrollTo(0, 0);
  }

  function screenUnknown(collection) {
    crumbs([['Справочники', href('/')], [collection, null]]);
    return el('div', { class: 'card' }, el('h2', {}, 'Нет такого справочника'),
      el('p', {}, 'Коллекции ', el('code', {}, `/v1/${collection}`), ' нет в спецификации. ', el('a', { href: href('/') }, 'К списку справочников')));
  }

  // S-04: the screen for a token without roles and for a request without a token
  function screenNoAccess(status, error) {
    crumbs([['Нет доступа', null]]);
    if (status === 'UNAUTHENTICATED') {
      return el('div', { class: 'card' },
        el('h2', {}, 'Требуется вход'),
        el('p', {}, 'Запрос без токена отклонён (UNAUTHENTICATED). В интерфейсе, подключённом к API, здесь происходит перенаправление в Keycloak (Authorization Code с PKCE) и возврат на прежний экран. На шаге 1 выберите роль в шапке.'),
        error ? errorBanner(error) : null);
    }
    return el('div', { class: 'card' },
      el('h2', {}, 'Нет доступа'),
      el('p', {}, 'У учётной записи нет роли с нужным уровнем доступа (PERMISSION_DENIED). Роли сервиса: reference-reader, reference-hr-reader, reference-admin, reference-hr-admin. Обратитесь к команде справочников.'),
      error ? errorBanner(error) : null,
      el('p', {}, el('a', { href: href('/') }, 'К списку справочников')));
  }

  // S-01: catalogs by group with the number of active records
  async function screenCatalogs() {
    crumbs([['Справочники', null]]);
    if (!session.user.roles.length) return screenNoAccess('PERMISSION_DENIED');
    const search = el('input', { type: 'search', id: 'catalogSearch', placeholder: 'Название справочника' });
    const sections = [];
    for (const [groupId, group] of Object.entries(GROUPS)) {
      const collections = group.collections.filter((c) => can(session.user, c, 'R'));
      if (!collections.length) continue;
      const rows = collections.map((collection) => {
        const cat = CATALOGS[collection];
        const count = el('td', { class: 'num' }, '…');
        api.list(session.user, collection, { pageSize: 1 })
          .then((page) => { count.textContent = String(page.total_size); })
          .catch(() => { count.textContent = '-'; });
        return el('tr', { dataset: { title: cat.title.toLowerCase() } },
          el('td', {}, el('a', { href: href(`/${collection}`), class: 'mono' }, `/v1/${collection}`)),
          el('td', {}, cat.title),
          count);
      });
      sections.push(el('section', { class: 'card' },
        el('h2', {}, group.title, ' ', el('span', { class: 'muted small' }, groupId)),
        table([{ label: 'Коллекция' }, { label: 'Название' }, { label: 'Активных записей', class: 'num' }], rows)));
    }
    const root = el('div', {},
      el('div', { class: 'toolbar' }, el('label', { for: 'catalogSearch' }, 'Поиск'), search),
      sections,
      el('p', { class: 'hint' }, 'Справочники salaries и absences видны только ролям reference-hr-reader и reference-hr-admin. В интерфейсе, подключённом к API, перечень коллекций берётся из спецификации OpenAPI.'));
    search.addEventListener('input', () => {
      const needle = search.value.trim().toLowerCase();
      for (const row of root.querySelectorAll('tbody tr')) row.hidden = needle !== '' && !row.dataset.title.includes(needle);
    });
    return root;
  }

  // ---- S-02: the table of one catalog ----

  function listColumns(collection) {
    const cat = CATALOGS[collection];
    if (collection === 'employees') return ['name', 'display_name', 'username', 'hire_date', 'org_unit', 'position', 'employment_state', 'account_state', 'state'];
    return ['name', ...(cat.displayName ? ['display_name'] : []), 'state', ...cat.fields.map((f) => f.name)];
  }

  function filterPlaceholder(collection) {
    const examples = {
      employees: 'employment_state = EMPLOYED AND org_unit = "org_units/dev-backend"',
      org_units: 'kind = TEAM AND parent = "org_units/dev"',
      assignments: 'employee = "employees/1001" AND NOT end_date:*',
      salaries: 'amount >= 150000',
      absences: 'kind = VACATION AND start_date >= "2026-07-01"',
      countries: 'state = ACTIVE AND display_name:"Р"',
    };
    return examples[collection] || 'state = ACTIVE AND display_name:"евро"';
  }

  function orderOptions(collection, selected) {
    const options = [];
    for (const field of queryFields(collection)) {
      if (field === 'etag') continue;
      options.push(field, `${field} desc`);
    }
    return options.map((o) => el('option', { value: o, selected: o === selected || (o === 'name' && !selected) }, o));
  }

  function tableParams(query) {
    return {
      filter: query.get('filter') || '',
      orderBy: query.get('order_by') || '',
      showDeleted: query.get('show_deleted') === 'true',
      pageSize: Number(query.get('page_size')) || api.config.defaultPageSize,
      pageToken: query.get('page_token') || '',
    };
  }

  function tableHref(collection, params, pageToken) {
    return href(`/${collection}`, {
      filter: params.filter,
      order_by: params.orderBy,
      show_deleted: params.showDeleted,
      page_size: params.pageSize,
      page_token: pageToken || '',
    });
  }

  function cellFor(collection, rec, column) {
    const value = rec[column];
    if (column === 'name') return el('td', {}, el('a', { href: recordHref(rec.name), class: 'mono' }, rec.name));
    if (column === 'state' || column === 'employment_state' || column === 'account_state') return el('td', {}, value ? badge(value) : fmtValue(value));
    if (typeof value === 'number') return el('td', { class: 'num' }, String(value));
    if (typeof value === 'string' && refTarget(value) && CATALOGS[refTarget(value).collection]) return el('td', {}, refLink(value));
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
    const showDeleted = el('input', { type: 'checkbox', id: 'showDeleted', checked: params.showDeleted });
    const pageSize = el('select', { id: 'pageSize', 'aria-label': 'Размер страницы' }, PAGE_SIZES.map((n) => el('option', { value: n, selected: n === params.pageSize }, `${n} на странице`)));
    const form = el('form', {
      class: 'toolbar',
      on: {
        submit: (event) => {
          event.preventDefault();
          session.pager[collection] = [];
          go(tableHref(collection, { filter: filterInput.value.trim(), orderBy: orderSelect.value, showDeleted: showDeleted.checked, pageSize: Number(pageSize.value) }, ''));
        },
      },
    },
    el('label', { for: 'filter' }, 'filter'), filterInput,
    el('label', { for: 'orderBy' }, 'order_by'), orderSelect,
    el('label', {}, showDeleted, ' show_deleted'),
    pageSize,
    el('button', { type: 'submit', class: 'primary' }, 'Применить'));

    const resultBox = el('div', { id: 'tableBanner' });
    const actions = el('div', { class: 'toolbar' });
    if (can(user, collection, 'X')) actions.appendChild(el('button', { type: 'button', on: { click: () => exportCurrent(collection, params, resultBox) } }, 'Выгрузить в Excel'));
    if (can(user, collection, 'C')) actions.appendChild(el('a', { class: 'button primary', href: href(`/${collection}/new`) }, 'Создать запись'));
    const hint = el('p', { class: 'hint', id: 'filterHint' },
      'Поля фильтра: ', queryFields(collection).join(', '), '. Операторы: =, !=, : (вхождение), <, <=, >, >=, AND, OR, NOT, скобки, поле:* (есть значение). Сортировка: поле или "поле desc".');

    const root = el('div', {},
      el('h2', {}, cat.title, ' ', el('span', { class: 'muted mono small' }, `/v1/${collection}`)),
      resultBox, form, hint, actions);

    let page;
    try {
      page = await api.list(user, collection, params);
    } catch (error) {
      if (error instanceof ApiError && error.status === 'INVALID_ARGUMENT') {
        const violations = error.fieldViolations;
        if (violations.some((v) => v.field === 'filter')) filterInput.classList.add('invalid');
        root.appendChild(banner('error', el('b', {}, 'INVALID_ARGUMENT'), ' ', violations.map((v) => `${v.field}: ${v.description}`).join('. ')));
        return root;
      }
      throw error;
    }

    const columns = listColumns(collection);
    const rows = page[collection];
    const body = rows.length
      ? rows.map((rec) => el('tr', { class: rec.state === 'DELETED' ? 'deleted' : null }, columns.map((column) => cellFor(collection, rec, rec[column] === undefined ? null : column))))
      : [el('tr', {}, el('td', { colspan: columns.length, class: 'muted' }, 'Записей нет', can(user, collection, 'C') ? ', создайте первую' : '', '.'))];
    root.appendChild(el('div', { class: 'table-wrap' }, table(columns.map((c) => ({ label: c, class: c === 'name' ? null : null })), body)));

    const stack = session.pager[collection] || [];
    const pager = el('div', { class: 'pager' },
      el('span', { class: 'muted' }, `на странице: ${rows.length}, total_size: ${page.total_size}, page_size: ${params.pageSize}`),
      el('button', {
        type: 'button',
        disabled: !stack.length,
        on: { click: () => { const token = stack.pop(); session.pager[collection] = stack; go(tableHref(collection, params, token)); } },
      }, 'Назад'),
      el('button', {
        type: 'button',
        disabled: !page.next_page_token,
        on: { click: () => { stack.push(params.pageToken); session.pager[collection] = stack; go(tableHref(collection, params, page.next_page_token)); } },
      }, 'Вперёд'));
    root.appendChild(pager);
    return root;
  }

  function download(file) {
    const blob = new Blob([file.bytes], { type: file.contentType });
    const url = URL.createObjectURL(blob);
    const link = el('a', { href: url, download: file.filename });
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function exportCurrent(collection, params, box) {
    replace(box, banner('ok', 'Выгрузка выполняется…'));
    try {
      const file = await api.exportList(session.user, collection, params);
      download(file);
      replace(box, banner('ok', `Выгружено записей: ${file.rows}, файл ${file.filename}. Запрос: GET /v1/${collection} с текущим отбором и Accept: ${file.contentType}.`));
    } catch (error) {
      replace(box, errorBanner(error));
    }
  }

  // ---- S-03: the record form with the details and the history panel ----

  function normalize(value) {
    return value === null || value === undefined ? '' : String(value);
  }

  function fieldInput(collection, field, value, locked) {
    const inputId = `f-${field.name}`;
    const common = { id: inputId, name: field.name };
    switch (field.type) {
      case 'enum':
        return el('select', { ...common, disabled: locked },
          el('option', { value: '' }, '-'),
          field.values.map((v) => el('option', { value: v, selected: v === value }, v)));
      case 'number':
        return el('input', { ...common, type: 'number', step: field.integer ? '1' : 'any', value: normalize(value), readOnly: locked });
      case 'date':
        return el('input', { ...common, type: 'date', value: normalize(value), readOnly: locked });
      case 'email':
        return el('input', { ...common, type: 'email', value: normalize(value), readOnly: locked, autocomplete: 'off' });
      case 'ref': {
        const listId = `dl-${collection}-${field.name}`;
        const input = el('input', { ...common, type: 'text', class: 'mono', value: normalize(value), readOnly: locked, list: listId, placeholder: `${field.ref}/{id}`, autocomplete: 'off' });
        const datalist = el('datalist', { id: listId });
        api.list(session.user, field.ref, { pageSize: 200, orderBy: 'name' })
          .then((page) => replace(datalist, page[field.ref].map((r) => el('option', { value: r.name }, r.display_name || ''))))
          .catch(() => {});
        return el('span', { class: 'ref' }, input, datalist);
      }
      default:
        return el('input', { ...common, type: 'text', value: normalize(value), readOnly: locked, autocomplete: 'off' });
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
    const editable = isNew ? can(user, collection, 'C') : can(user, collection, 'U') && rec.state === 'ACTIVE';
    const draftKey = `rm.draft:${collection}:${isNew ? 'new' : rec.name}`;
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
    if (isNew && !cat.dated) {
      const input = el('input', { id: 'f-id', name: cat.idParam, type: 'text', class: 'mono', value: initial(cat.idParam), autocomplete: 'off' });
      inputs[cat.idParam] = input;
      boxes[cat.idParam] = fieldBox('Идентификатор', cat.idParam, `${cat.idParam}, обязательно: ${cat.idHint}`, input);
      fields.push(boxes[cat.idParam]);
    }
    if (cat.displayName) {
      const input = el('input', { id: 'f-display_name', name: 'display_name', type: 'text', value: normalize(initial('display_name')), readOnly: !editable, autocomplete: 'off' });
      inputs.display_name = input;
      boxes.display_name = fieldBox('Наименование', 'display_name', 'display_name, обязательно', input);
      fields.push(boxes.display_name);
    }
    for (const field of cat.fields) {
      const locked = !editable || (field.immutable && !isNew) || (isNew && field.immutable && query && query.has(field.name));
      const control = fieldInput(collection, field, initial(field.name), locked);
      const input = control.matches('input, select') ? control : control.querySelector('input, select');
      inputs[field.name] = input;
      const notes = [field.name];
      if (field.required) notes.push('обязательно');
      if (field.immutable && !isNew) notes.push('не меняется');
      if (field.hint) notes.push(field.hint);
      if (field.type === 'ref') notes.push(`имя записи ${field.ref}/*`);
      boxes[field.name] = fieldBox(field.label, field.name, notes.join(', '), control);
      fields.push(boxes[field.name]);
    }

    // the employee's display name follows the name parts until it is edited by hand
    if (collection === 'employees' && editable) {
      let generated = inputs.display_name.value;
      const refresh = () => {
        const parts = ['family_name', 'given_name', 'middle_name'].map((n) => inputs[n].value.trim()).filter(Boolean);
        const next = parts.join(' ');
        if (inputs.display_name.value === generated || inputs.display_name.value === '') { inputs.display_name.value = next; generated = next; }
      };
      for (const name of ['family_name', 'given_name', 'middle_name']) inputs[name].addEventListener('input', refresh);
    }

    const clearErrors = () => {
      for (const box of Object.values(boxes)) { box.classList.remove('invalid'); box.querySelector('.error').textContent = ''; }
      clear(formBanner);
    };

    const showFieldErrors = (error) => {
      const violations = error.fieldViolations;
      let marked = 0;
      for (const violation of violations) {
        const box = boxes[violation.field];
        if (!box) continue;
        box.classList.add('invalid');
        box.querySelector('.error').textContent = violation.description;
        marked += 1;
      }
      const rest = violations.filter((v) => !boxes[v.field]).map((v) => `${v.field}: ${v.description}`);
      replace(formBanner, banner('error', el('b', {}, `INVALID_ARGUMENT ${error.code}`), ` неверных полей: ${violations.length}${marked ? ', см. подписи у полей' : ''}.`, rest.length ? ` ${rest.join('. ')}` : ''));
    };

    const actions = el('div', { class: 'toolbar' });
    const busy = (state) => { for (const button of actions.querySelectorAll('button')) button.disabled = state; };
    if (editable) actions.appendChild(el('button', { type: 'submit', class: 'primary' }, 'Сохранить'));
    if (!isNew && can(user, collection, 'D') && rec.state === 'ACTIVE') {
      actions.appendChild(el('button', {
        type: 'button',
        class: 'danger',
        on: {
          click: async () => {
            const title = rec.display_name ? `${rec.name} "${rec.display_name}"` : rec.name;
            if (!await confirmDialog(`Удалить ${title}? Запись перейдёт в состояние DELETED, идентификатор останется занятым, ссылки на запись продолжат работать.`)) return;
            busy(true);
            try {
              await api.remove(user, collection, idOf(rec.name));
              flash('ok', `Запись ${rec.name} удалена: state = DELETED, новая ревизия DELETED.`);
              render();
            } catch (error) { replace(formBanner, errorBanner(error)); busy(false); }
          },
        },
      }, 'Удалить'));
    }
    if (!isNew && can(user, collection, 'U') && rec.state === 'DELETED') {
      actions.appendChild(el('button', {
        type: 'button',
        on: {
          click: async () => {
            if (!await confirmDialog(`Восстановить ${rec.name}?`)) return;
            busy(true);
            try {
              await api.undelete(user, collection, idOf(rec.name));
              flash('ok', `Запись ${rec.name} восстановлена: state = ACTIVE, новая ревизия UNDELETED.`);
              render();
            } catch (error) { replace(formBanner, errorBanner(error)); busy(false); }
          },
        },
      }, 'Восстановить'));
    }
    actions.appendChild(el('a', { class: 'button', href: `#${backTo}` }, 'Назад'));

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
      const body = {};
      for (const name of storedFields(collection)) if (inputs[name]) body[name] = inputs[name].value;
      busy(true);
      try {
        if (isNew) {
          const id = inputs[cat.idParam] ? inputs[cat.idParam].value.trim() : undefined;
          const created = await api.create(user, collection, body, id);
          storageSet(draftKey, null);
          const note = collection === 'employees' ? ` Учётная запись создана и включена: account_state = ${created.account_state}.` : '';
          flash('ok', `Создано ${created.name}, ревизия #1 CREATED.${note}`);
          go(cat.dated && query && query.get('back') ? `#${query.get('back')}` : recordHref(created.name));
        } else {
          const mask = storedFields(collection).filter((name) => inputs[name] && !inputs[name].readOnly && !inputs[name].disabled && normalize(inputs[name].value) !== normalize(rec[name]));
          if (!mask.length) { replace(formBanner, banner('warn', 'Изменений нет: update_mask пуст, запрос не отправлен.')); busy(false); return; }
          const updated = await api.update(user, collection, idOf(rec.name), body, mask.join(','));
          storageSet(draftKey, null);
          const note = collection === 'employees' && mask.some((n) => CATALOGS.employees.fields.find((f) => f.name === n && f.account)) ? ` Изменение передано в учётную запись: account_state = ${updated.account_state}.` : '';
          flash('ok', `Сохранено ${updated.name}: update_mask = ${mask.join(', ')}, новая ревизия UPDATED.${note}`);
          render();
        }
      } catch (error) {
        busy(false);
        if (error instanceof ApiError && error.status === 'INVALID_ARGUMENT') { showFieldErrors(error); return; }
        if (error instanceof ApiError && error.status === 'UNAVAILABLE') {
          storageSet(draftKey, null);
          flash('warn', explain(error));
          go(error.metadata.name ? recordHref(error.metadata.name) : location.hash);
          return;
        }
        replace(formBanner, errorBanner(error));
      }
    });

    const title = isNew ? `Новая запись: ${cat.title}` : (rec.display_name || rec.name);
    const card = el('div', { class: 'card' },
      el('h2', {}, title, ' ', el('span', { class: 'muted mono small' }, isNew ? `POST /v1/${collection}` : rec.name)),
      formBanner,
      draft ? banner('warn', 'Восстановлен черновик формы из этого окна браузера.') : null,
      !editable && !isNew ? el('p', { class: 'hint' }, rec.state === 'DELETED' ? 'Запись удалена: поля только для чтения, доступно восстановление.' : 'Только чтение: у роли нет уровня update на эту группу справочников.') : null,
      form);

    // a new dated record is checked against the record still in effect for the same employee
    if (isNew && cat.dated && collection !== 'absences' && inputs.employee && inputs.employee.value) {
      api.list(user, collection, { filter: `employee = "${inputs.employee.value}" AND NOT end_date:*`, pageSize: 1 })
        .then((page) => {
          const open = page[collection][0];
          if (!open) return;
          formBanner.appendChild(banner('warn', `Действующая запись ${open.name} с ${open.start_date} не закрыта. Сначала закройте её датой на карточке сотрудника, иначе периоды пересекутся и запрос будет отклонён.`));
        })
        .catch(() => {});
    }
    return card;
  }

  function metaCard(rec) {
    return el('div', { class: 'card' },
      el('h3', {}, 'Сведения'),
      el('dl', { class: 'meta' },
        el('dt', {}, 'name'), el('dd', { class: 'mono' }, rec.name),
        el('dt', {}, 'state'), el('dd', {}, badge(rec.state)),
        el('dt', {}, 'etag'), el('dd', { class: 'mono' }, rec.etag),
        el('dt', {}, 'delete_time'), el('dd', {}, fmtTime(rec.delete_time))));
  }

  async function historyCard(collection, id) {
    const box = el('div', { class: 'card' },
      el('h3', {}, 'История'),
      el('p', { class: 'hint mono' }, `GET /v1/${collection}/${id}/revisions`, ' ', el('span', { class: 'sans' }, 'от новой к старой')));
    let page;
    try {
      page = await api.listRevisions(session.user, collection, id);
    } catch (error) {
      box.appendChild(errorBanner(error));
      return box;
    }
    const asOf = el('div', {});
    const showAsOf = async (number) => {
      try {
        const state = await api.getAtRevision(session.user, collection, id, number);
        replace(asOf, el('div', { class: 'banner banner-warn' },
          el('b', {}, `Состояние на ревизию #${number}`), ' ', el('span', { class: 'hint mono' }, `GET /v1/${collection}/${id}?revision=${number}`),
          el('dl', { class: 'meta compact' }, Object.entries(state).map(([key, value]) => [el('dt', {}, key), el('dd', {}, fmtValue(value))]))));
      } catch (error) {
        replace(asOf, errorBanner(error));
      }
    };
    for (const revision of page.revisions) {
      const number = Number(revision.name.split('/').pop());
      box.appendChild(el('div', { class: 'revision' },
        el('div', { class: 'revision-head' },
          el('b', {}, `#${number}`), ' ', badge(revision.action), ' ', fmtTime(revision.create_time), ' ',
          el('span', { class: 'muted' }, revision.author), ' ',
          el('span', { class: 'muted mono small' }, `request_id ${revision.request_id}`), ' ',
          el('button', { type: 'button', class: 'link', on: { click: () => showAsOf(number) } }, 'на ревизию')),
        el('ul', { class: 'changes' }, revision.changes.map((change) => el('li', {}, el('code', {}, change.field), ': ', fmtValue(change.old_value), ' → ', fmtValue(change.new_value))))));
    }
    if (!page.revisions.length) box.appendChild(el('p', { class: 'muted' }, 'Ревизий нет.'));
    box.appendChild(asOf);
    return box;
  }

  async function screenForm(collection, id, query) {
    const cat = CATALOGS[collection];
    const isNew = id === null;
    const rec = isNew ? null : await api.get(session.user, collection, id);
    let backTo = query.get('back') || `/${collection}`;
    if (!query.get('back') && rec && cat.dated && rec.employee) backTo = `/employees/${idOf(rec.employee)}?tab=${collection}`;
    crumbs([['Справочники', href('/')], [cat.title, href(`/${collection}`)], [isNew ? 'Новая запись' : rec.name, null]]);
    const panel = buildFormPanel(collection, rec, query, backTo);
    if (isNew) return el('div', { class: 'layout' }, panel, el('div', {}, el('div', { class: 'card' }, el('h3', {}, 'Сведения'), el('p', { class: 'muted' }, cat.dated ? 'Идентификатор назначит сервис.' : 'Имя записи появится после сохранения.'))));
    return el('div', { class: 'layout' }, panel, el('div', {}, metaCard(rec), await historyCard(collection, id)));
  }

  // ---- S-05: the employee card ----

  function todayIso() {
    return api.config.now().toISOString().slice(0, 10);
  }

  function statusCard(rec) {
    const user = session.user;
    const manage = can(user, 'employees', 'U');
    const id = idOf(rec.name);
    const card = el('div', { class: 'card' },
      el('h2', {}, rec.display_name, ' ', el('span', { class: 'muted mono small' }, rec.name)),
      el('dl', { class: 'meta columns' },
        el('dt', {}, 'employment_state'), el('dd', {}, badge(rec.employment_state)),
        el('dt', {}, 'hire_date'), el('dd', {}, rec.hire_date),
        el('dt', {}, 'dismissal_date'), el('dd', {}, fmtValue(rec.dismissal_date)),
        el('dt', {}, 'account_state'), el('dd', {}, badge(rec.account_state)),
        el('dt', {}, 'account_user_id'), el('dd', { class: 'mono' }, fmtValue(rec.account_user_id)),
        el('dt', {}, 'state'), el('dd', {}, badge(rec.state))));
    if (rec.account_state === 'PENDING') {
      card.appendChild(banner('warn',
        'Операция с учётной записью не завершена: профиль сохранён, Keycloak её ещё не подтвердил. ',
        manage ? el('button', {
          type: 'button',
          on: {
            click: async () => {
              try {
                const synced = await api.syncAccount(user, id);
                flash('ok', `Операция с учётной записью завершена: account_state = ${synced.account_state}. Запрос: POST /v1/employees/${id}:syncAccount.`);
              } catch (error) {
                flash(error instanceof ApiError && error.status === 'UNAVAILABLE' ? 'warn' : 'error', explain(error));
              }
              render();
            },
          },
        }, 'Повторить операцию с учётной записью') : null));
    }
    if (manage && rec.employment_state === 'EMPLOYED' && rec.state === 'ACTIVE') {
      const date = el('input', { type: 'date', id: 'dismissalDate', value: todayIso() });
      const error = el('div', { class: 'error' });
      card.appendChild(el('form', {
        class: 'toolbar dismiss',
        on: {
          submit: async (event) => {
            event.preventDefault();
            error.textContent = '';
            if (!await confirmDialog(`Уволить ${rec.display_name} с ${date.value}? Вход сотрудника будет закрыт, действующие назначение и оклад будут закрыты этой датой.`)) return;
            try {
              await api.dismiss(user, id, { dismissal_date: date.value });
              flash('ok', `Сотрудник уволен с ${date.value}: назначение и оклад закрыты этой датой, учётная запись заблокирована. Запрос: POST /v1/employees/${id}:dismiss.`);
            } catch (err) {
              if (err instanceof ApiError && err.status === 'INVALID_ARGUMENT') { error.textContent = err.fieldViolations.map((v) => `${v.field}: ${v.description}`).join('. '); return; }
              flash(err instanceof ApiError && err.status === 'UNAVAILABLE' ? 'warn' : 'error', explain(err));
            }
            render();
          },
        },
      },
      el('label', { for: 'dismissalDate' }, 'Дата увольнения'), date,
      el('button', { type: 'submit', class: 'danger' }, 'Уволить'),
      error));
    }
    return card;
  }

  async function nameOf(value) {
    const target = refTarget(value);
    if (!target) return fmtValue(value);
    try {
      const rec = await api.get(session.user, target.collection, target.id);
      return el('span', {}, rec.display_name || rec.name, ' ', refLink(value));
    } catch (error) {
      return refLink(value);
    }
  }

  async function currentValuesCard(rec) {
    const today = todayIso();
    const rows = [
      el('dt', {}, 'Подразделение'), el('dd', {}, await nameOf(rec.org_unit)),
      el('dt', {}, 'Должность'), el('dd', {}, await nameOf(rec.position)),
    ];
    if (can(session.user, 'salaries', 'R')) {
      let text = el('span', { class: 'muted' }, 'нет действующего оклада');
      try {
        const page = await api.list(session.user, 'salaries', { filter: `employee = "${rec.name}" AND start_date <= "${today}" AND (end_date >= "${today}" OR NOT end_date:*)`, pageSize: 1 });
        const salary = page.salaries[0];
        if (salary) text = el('span', {}, `${salary.amount} `, refLink(salary.currency), ' ', el('span', { class: 'muted' }, `с ${salary.start_date}`));
      } catch (error) {
        text = errorBanner(error);
      }
      rows.push(el('dt', {}, 'Оклад'), el('dd', {}, text));
    }
    return el('div', { class: 'card' }, el('h3', {}, 'Действующие значения'), el('p', { class: 'hint' }, `на ${today}, из записей с периодом действия`), el('dl', { class: 'meta' }, rows));
  }

  function periodLabel(row) {
    return `${row.start_date} - ${row.end_date || 'сейчас'}`;
  }

  function periodDetails(collection, row) {
    if (collection === 'assignments') return el('span', {}, refLink(row.org_unit), ', ', refLink(row.position));
    if (collection === 'salaries') return el('span', {}, `${row.amount} `, refLink(row.currency));
    return el('span', {}, row.kind);
  }

  async function periodsCard(rec, requested) {
    const user = session.user;
    const id = idOf(rec.name);
    const tabs = DATED_TABS.filter(([collection]) => can(user, collection, 'R'));
    const active = tabs.some(([collection]) => collection === requested) ? requested : tabs[0][0];
    const nav = el('div', { class: 'tabs', role: 'tablist' }, tabs.map(([collection, label]) => el('a', {
      role: 'tab', class: 'tab', 'aria-selected': collection === active ? 'true' : 'false', href: href(`/employees/${id}`, { tab: collection }),
    }, label)));
    const card = el('div', { class: 'card' }, el('h3', {}, 'Периоды'), nav);
    let page;
    try {
      page = await api.list(user, active, { filter: `employee = "${rec.name}"`, orderBy: 'start_date desc', pageSize: 200 });
    } catch (error) {
      card.appendChild(errorBanner(error));
      return card;
    }
    const rows = page[active];
    const backTo = `/employees/${id}?tab=${active}`;
    const openRow = rows.find((row) => !row.end_date);
    const body = rows.map((row) => {
      const cells = [
        el('td', {}, el('a', { href: href(`/${active}/${idOf(row.name)}`, { back: backTo }), class: 'mono' }, row.name)),
        el('td', {}, periodLabel(row)),
        el('td', {}, periodDetails(active, row)),
      ];
      const actionCell = el('td', {});
      if (!row.end_date && can(user, active, 'U') && rec.employment_state === 'EMPLOYED') {
        const date = el('input', { type: 'date', value: todayIso(), 'aria-label': `Дата окончания ${row.name}` });
        actionCell.appendChild(el('form', {
          class: 'inline',
          on: {
            submit: async (event) => {
              event.preventDefault();
              try {
                await api.update(user, active, idOf(row.name), { end_date: date.value }, 'end_date');
                flash('ok', `Запись ${row.name} закрыта датой ${date.value}: update_mask = end_date.`);
              } catch (error) {
                flash('error', explain(error));
              }
              render();
            },
          },
        }, date, el('button', { type: 'submit' }, 'Закрыть датой')));
      }
      cells.push(actionCell);
      return el('tr', {}, cells);
    });
    card.appendChild(table([{ label: 'name' }, { label: 'Период' }, { label: 'Значение' }, { label: '' }],
      body.length ? body : [el('tr', {}, el('td', { colspan: 4, class: 'muted' }, 'Записей нет.'))]));
    const actions = el('div', { class: 'toolbar' });
    if (can(user, active, 'C') && rec.employment_state === 'EMPLOYED') {
      actions.appendChild(el('a', { class: 'button primary', href: href(`/${active}/new`, { employee: rec.name, back: backTo }) }, 'Добавить'));
    }
    if (openRow && active !== 'absences') {
      actions.appendChild(el('span', { class: 'hint' }, `Действующая запись ${openRow.name} не закрыта: перед добавлением новой закройте её датой, иначе периоды пересекутся.`));
    }
    card.appendChild(actions);
    return card;
  }

  async function screenCard(current) {
    const id = current.id;
    const rec = await api.get(session.user, 'employees', id);
    crumbs([['Справочники', href('/')], ['Сотрудники', href('/employees')], [rec.display_name, null]]);
    const left = el('div', {}, statusCard(rec), buildFormPanel('employees', rec, current.query, '/employees'));
    const right = el('div', {}, await currentValuesCard(rec), await periodsCard(rec, current.query.get('tab') || 'assignments'), await historyCard('employees', id));
    return el('div', { class: 'layout' }, left, right);
  }

  // ---- start ----

  function init() {
    const select = $('#role');
    replace(select, USERS.map((u) => el('option', { value: u.key }, u.label)));
    setUser(storageGet('rm.user') || 'admin');
    select.value = session.user.key;
    select.addEventListener('change', () => { setUser(select.value); session.pager = {}; render(); });

    const keycloak = $('#kc');
    keycloak.checked = api.config.keycloakAvailable;
    keycloak.addEventListener('change', () => { api.config.keycloakAvailable = keycloak.checked; });

    const limit = $('#exportLimit');
    limit.value = api.config.exportLimit;
    limit.addEventListener('change', () => {
      const value = Math.floor(Number(limit.value));
      if (value >= 1) api.config.exportLimit = value;
      else limit.value = api.config.exportLimit;
    });

    $('#reset').addEventListener('click', () => {
      api.reset();
      session.pager = {};
      flash('ok', 'Данные имитации возвращены к исходным.');
      render();
    });

    window.addEventListener('hashchange', render);
    render();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
