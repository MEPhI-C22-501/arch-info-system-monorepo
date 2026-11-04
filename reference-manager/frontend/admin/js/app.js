// screens S-01..S-05 of document 110 on top of the service API, the route lives in the path under /admin/
(function () {
  'use strict';

  const { el, replace, clear, $ } = RM.dom;
  const { CATALOGS, GROUPS, COMMON, can, hasAnyRole, fieldByName, queryFields, fieldLabel, listColumns, recordLabel, shortLabel, toBody, updateMask, normalize } = RM.catalogs;
  const { ApiError } = RM.api;
  const { stateAt, fieldOf } = RM.jsonpatch;
  const fmt = RM.format;
  const views = RM.views;

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
    return el('time', { datetime: iso, title: `${iso} (UTC)` }, fmt.dateTime(iso));
  }

  function fmtDate(value) {
    if (fmt.isEmpty(value)) return fmtValue(value);
    return el('time', { datetime: String(value) }, fmt.date(value));
  }

  // a value of a catalog field as text: dates and money in Russian notation, the rest as is
  function fmtField(collection, name, value) {
    const model = views.cell(collection, name, value);
    if (model.kind === 'empty') return fmtValue(value);
    if (model.kind === 'date') return fmtDate(value);
    if (model.kind === 'time') return fmtTime(value);
    if (model.kind === 'state' || model.kind === 'id') return fmtValue(value);
    return model.text;
  }

  function banner(kind, ...content) {
    return el('div', { class: `banner banner-${kind}`, role: kind === 'error' ? 'alert' : 'status' }, ...content);
  }

  function explain(error) {
    if (!(error instanceof ApiError)) return `${views.errorState(error).title}: ${error && error.message ? error.message : error}`;
    const hint = STATUS_HINTS[error.status] || '';
    return `${error.status}: ${error.message}. ${hint}`.trim();
  }

  function errorBanner(error, extra, onRetry) {
    const retry = onRetry ? el('button', { type: 'button', on: { click: onRetry } }, 'Повторить') : null;
    if (!(error instanceof ApiError)) {
      console.error(error);
      const state = views.errorState(error);
      return banner('error', el('b', {}, state.title), '. ', state.text, retry);
    }
    const details = error.details.filter((d) => !d.field).map((d) => d.message);
    return banner('error',
      el('b', {}, `${error.status}`), ' ', error.message, details.length ? ` ${details.join('. ')}` : '',
      el('div', { class: 'hint' }, STATUS_HINTS[error.status] || '', ' ', error.traceId ? el('span', { class: 'mono' }, `trace: ${error.traceId}`) : null),
      extra || null, retry);
  }

  // a whole screen or block that failed: what happened, the trace for the team and the way out
  function stateCard(error, options) {
    const opts = options || {};
    if (!(error instanceof ApiError)) console.error(error);
    const state = views.errorState(error);
    const actions = el('div', { class: 'toolbar' });
    if (state.retry && opts.onRetry) actions.appendChild(el('button', { type: 'button', class: 'primary', on: { click: opts.onRetry } }, 'Повторить'));
    if (opts.backHref) actions.appendChild(el('a', { class: 'button', href: opts.backHref }, opts.backLabel || 'К списку справочников'));
    const heading = opts.level === 3 ? 'h3' : 'h2';
    return el('div', { class: 'card state state-error', role: 'alert' },
      el(heading, {}, state.title),
      el('p', {}, state.text),
      error instanceof ApiError && error.traceId ? el('p', { class: 'hint mono' }, `trace: ${error.traceId}`) : null,
      actions.childNodes.length ? actions : null);
  }

  function loadingBlock(text) {
    return el('div', { class: 'loading', role: 'status' }, el('span', { class: 'spinner', 'aria-hidden': 'true' }), ' ', text || 'Загрузка…');
  }

  // the state of an empty page: an empty catalog or a selection without records
  function emptyBlock(state, links) {
    const actions = el('div', { class: 'toolbar' });
    if (state.action === 'create' && links.create) actions.appendChild(el('a', { class: 'button primary', href: links.create }, 'Создать запись'));
    if (state.action === 'reset' && links.reset) actions.appendChild(el('a', { class: 'button', href: links.reset }, 'Сбросить отбор'));
    return el('div', { class: 'card state', role: 'status' },
      el('h3', {}, state.title),
      el('p', {}, state.text),
      actions.childNodes.length ? actions : null);
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
    const list = el('ol', {}, parts.map(([label, target], index) => el('li', {},
      target ? el('a', { href: target }, label) : el('span', { 'aria-current': index === parts.length - 1 ? 'page' : null }, label))));
    replace(nav, list);
  }

  // a modal confirmation, the safe answer has the focus
  function confirmDialog(text, title) {
    return new Promise((resolve) => {
      const dialog = $('#confirm');
      $('#confirmTitle').textContent = title || 'Подтвердите действие';
      $('#confirmText').textContent = text;
      dialog.returnValue = '';
      $('#confirmYes').onclick = () => dialog.close('yes');
      $('#confirmNo').onclick = () => dialog.close('no');
      dialog.addEventListener('close', () => resolve(dialog.returnValue === 'yes'), { once: true });
      dialog.showModal();
      $('#confirmNo').focus();
    });
  }

  // a table with a caption for screen readers, every cell carries its column name for the card layout of a narrow screen
  function table(headers, rows, caption) {
    const body = el('tbody', {}, rows);
    for (const row of body.rows) {
      [...row.cells].forEach((cell, index) => {
        if (!cell.hasAttribute('colspan') && headers[index]) cell.dataset.label = headers[index].label;
      });
    }
    return el('table', { class: 'responsive' },
      caption ? el('caption', { class: 'sr-only' }, caption) : null,
      el('thead', {}, el('tr', {}, headers.map((h) => el('th', { scope: 'col', class: h.class || null }, h.label || el('span', { class: 'sr-only' }, h.srLabel || ''))))),
      body);
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
          // the short names of table cells ride along with the full labels of forms and hints
          map.short = new Map();
          for (const item of items) {
            map.set(String(item.id), recordLabel(collection, item));
            map.short.set(String(item.id), shortLabel(collection, item));
          }
          return map;
        })
        .catch((error) => {
          // the names are a convenience, the cells keep the identifiers, the cause goes to the console
          console.error(`names of ${collection}`, error);
          return Object.assign(new Map(), { short: new Map() });
        });
    }
    return session.labels[collection];
  }

  function forgetLabels(collection) {
    delete session.labels[collection];
  }

  // a link to the referenced record: the full label in forms and cards, the short name in table cells
  async function refCell(field, value, compact) {
    if (value === null || value === undefined) return fmtValue(value);
    const labels = await labelsOf(field.ref);
    const label = labels.get(String(value));
    const text = compact ? labels.short.get(String(value)) : label;
    return el('a', { href: recordHref(field.ref, value), title: compact && label ? label : null }, text ? `${text} ` : '', el('span', { class: 'mono muted small' }, `#${value}`));
  }

  // ---- rendering ----

  async function render() {
    renderSequence += 1;
    const sequence = renderSequence;
    const view = $('#view');
    showFlash();
    const current = route();
    view.setAttribute('aria-busy', 'true');
    // a slow screen shows the loading state, a fast one replaces the previous screen at once
    const loadingTimer = setTimeout(() => { if (sequence === renderSequence) replace(view, loadingBlock()); }, 200);
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
      node = stateCard(error, { onRetry: render, backHref: error instanceof ApiError && error.status === 401 ? null : href('/') });
    }
    clearTimeout(loadingTimer);
    if (sequence !== renderSequence) return;
    replace(view, node);
    view.setAttribute('aria-busy', 'false');
    window.scrollTo(0, 0);
    // after a transition the heading of the new screen takes the focus, so that a screen reader announces it
    if (session.rendered) {
      const heading = view.querySelector('h2');
      if (heading) {
        heading.setAttribute('tabindex', '-1');
        heading.focus({ preventScroll: true });
      }
    }
    session.rendered = true;
  }

  function screenUnknown(collection) {
    crumbs([['Справочники', href('/')], [collection, null]]);
    return el('div', { class: 'card state' }, el('h2', {}, 'Нет такого справочника'),
      el('p', {}, 'Коллекции ', el('code', {}, `/v1/${collection}/`), ' нет в спецификации.'),
      el('div', { class: 'toolbar' }, el('a', { class: 'button', href: href('/') }, 'К списку справочников')));
  }

  // S-04: a signed-in user without a role of the service
  function screenNoAccess() {
    crumbs([['Нет доступа', null]]);
    return el('div', { class: 'card state state-error', role: 'alert' },
      el('h2', {}, 'Нет доступа'),
      el('p', {}, 'Учётная запись ', el('b', {}, session.user ? session.user.username : ''), ' вошла, но у неё нет роли сервиса справочников. Роли: reference-reader, reference-hr-reader, reference-admin, reference-hr-admin. Обратитесь к команде справочников.'),
      el('div', { class: 'toolbar' }, el('button', { type: 'button', on: { click: () => auth.logout() } }, 'Выйти и войти другой учётной записью')));
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
        const count = el('td', { class: 'num', 'aria-busy': 'true' }, el('span', { class: 'loading inline' }, el('span', { class: 'spinner', 'aria-hidden': 'true' }), el('span', { class: 'sr-only' }, 'загрузка')));
        api.list(collection, { pageSize: 100 })
          .then((page) => { replace(count, `${page.items.length}${page.nextPageToken ? '+' : ''}`); })
          .catch((error) => { replace(count, el('span', { class: 'muted', title: views.errorState(error).title }, '-')); })
          .finally(() => count.setAttribute('aria-busy', 'false'));
        return el('tr', { class: 'clickable', dataset: { title: cat.title.toLowerCase(), href: href(`/${collection}`) } },
          el('td', {}, el('a', { href: href(`/${collection}`) }, cat.title)),
          el('td', {}, el('span', { class: 'mono muted' }, `/v1/${collection}/`)),
          count);
      });
      sections.push(el('section', { class: 'card', 'aria-labelledby': `group-${groupId}` },
        el('h2', { id: `group-${groupId}` }, group.title, ' ', el('span', { class: 'muted small' }, groupId)),
        table([{ label: 'Справочник' }, { label: 'Коллекция' }, { label: 'Активных записей', class: 'num' }], rows, `${group.title}: справочники и число активных записей`)));
    }
    const nothing = el('div', { class: 'card state', role: 'status', hidden: true }, el('h3', {}, 'Ничего не найдено'), el('p', {}, 'Нет справочника с таким названием. Измените строку поиска.'));
    const root = el('div', {},
      el('div', { class: 'toolbar', role: 'search' }, el('label', { for: 'catalogSearch' }, 'Поиск справочника'), search),
      sections,
      nothing,
      el('p', { class: 'hint' }, 'Справочники salaries и absences видны только ролям reference-hr-reader и reference-hr-admin. Число записей считается по первой странице, "100+" означает, что страниц больше.'));
    search.addEventListener('input', () => {
      const needle = search.value.trim().toLowerCase();
      let shown = 0;
      for (const row of root.querySelectorAll('tbody tr')) {
        row.hidden = needle !== '' && !row.dataset.title.includes(needle);
        if (!row.hidden) shown += 1;
      }
      nothing.hidden = shown > 0;
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
      readTime: query.get('readTime') || '',
      pageSize: Number(query.get('pageSize')) || 20,
      pageToken: query.get('pageToken') || '',
    };
  }

  function tableHref(collection, params, pageToken) {
    return href(`/${collection}`, {
      filter: params.filter,
      order_by: params.orderBy,
      allowDeleted: params.allowDeleted,
      readTime: params.readTime,
      pageSize: params.pageSize === 20 ? '' : params.pageSize,
      pageToken: pageToken || '',
    });
  }

  // the value of a datetime-local input for a moment: the local time of the browser to the minute
  function localInputValue(iso) {
    if (!iso) return '';
    const moment = new Date(iso);
    if (Number.isNaN(moment.getTime())) return '';
    const pad = (n) => String(n).padStart(2, '0');
    return `${moment.getFullYear()}-${pad(moment.getMonth() + 1)}-${pad(moment.getDate())}T${pad(moment.getHours())}:${pad(moment.getMinutes())}`;
  }

  function cellFor(collection, rec, column) {
    const value = rec[column];
    const model = views.cell(collection, column, value);
    switch (model.kind) {
      case 'id':
        return el('td', { class: 'nowrap' }, el('a', { href: recordHref(collection, rec.id), class: 'mono' }, model.text));
      case 'state':
        return el('td', { class: 'nowrap' }, stateBadge(rec));
      case 'enum':
        return el('td', { class: 'nowrap' }, badge(value));
      case 'ref': {
        const cell = el('td', {}, el('span', { class: 'mono muted small' }, model.text));
        refCell(fieldByName(collection, column), value, true).then((node) => replace(cell, node));
        return cell;
      }
      case 'num':
        return el('td', { class: 'num' }, model.text);
      case 'date':
        return el('td', { class: 'nowrap' }, fmtDate(value));
      case 'time':
        return el('td', { class: 'nowrap' }, fmtTime(value));
      case 'empty':
        return el('td', {}, fmtValue(value));
      default:
        return el('td', {}, model.text);
    }
  }

  async function screenTable(current) {
    const collection = current.collection;
    const cat = CATALOGS[collection];
    const user = session.user;
    const params = tableParams(current.query);
    crumbs([['Справочники', href('/')], [cat.title, null]]);

    const filterInput = el('input', { type: 'text', id: 'filter', name: 'filter', class: 'mono wide', value: params.filter, placeholder: filterPlaceholder(collection), 'aria-describedby': 'filterHint filterError' });
    const filterError = el('div', { id: 'filterError', class: 'error', role: 'alert' });
    const orderSelect = el('select', { id: 'orderBy', name: 'order_by' }, orderOptions(collection, params.orderBy));
    const allowDeleted = el('input', { type: 'checkbox', id: 'allowDeleted', checked: params.allowDeleted });
    const readTime = el('input', { type: 'datetime-local', id: 'readTime', value: localInputValue(params.readTime), 'aria-describedby': 'readTimeHint' });
    const pageSize = el('select', { id: 'pageSize' }, PAGE_SIZES.map((n) => el('option', { value: n, selected: n === params.pageSize }, `${n} на странице`)));
    const form = el('form', {
      class: 'toolbar',
      role: 'search',
      'aria-label': `Отбор записей: ${cat.title}`,
      on: {
        submit: (event) => {
          event.preventDefault();
          session.pager[collection] = [];
          const moment = readTime.value ? new Date(readTime.value).toISOString() : '';
          go(tableHref(collection, { filter: filterInput.value.trim(), orderBy: orderSelect.value, allowDeleted: allowDeleted.checked, readTime: moment, pageSize: Number(pageSize.value) }, ''));
        },
      },
    },
    el('label', { for: 'filter' }, 'Фильтр'), filterInput,
    el('label', { for: 'orderBy' }, 'Сортировка'), orderSelect,
    el('span', { class: 'check' }, allowDeleted, el('label', { for: 'allowDeleted' }, 'Показывать удалённые')),
    el('label', { for: 'readTime' }, 'На момент'), readTime,
    el('label', { for: 'pageSize', class: 'sr-only' }, 'Размер страницы'), pageSize,
    el('button', { type: 'submit', class: 'primary' }, 'Применить'),
    views.hasSelection(params) || params.orderBy || params.readTime ? el('a', { class: 'button', href: href(`/${collection}`) }, 'Сбросить') : null);

    const resultBox = el('div', { id: 'tableBanner' });
    const actions = el('div', { class: 'toolbar' });
    const narrowed = Boolean(params.filter || params.orderBy || params.readTime);
    if (can(user, collection, 'X')) {
      actions.appendChild(el('button', { type: 'button', id: 'export', on: { click: () => exportCatalog(collection, params, resultBox) } },
        narrowed ? 'Выгрузить отобранное в Excel' : 'Выгрузить в Excel'));
    }
    if (can(user, collection, 'C') && !params.readTime) actions.appendChild(el('a', { class: 'button primary', id: 'create', href: href(`/${collection}/new`) }, 'Создать запись'));
    const hint = el('p', { class: 'hint', id: 'filterHint' },
      'Поля фильтра (параметр filter): ', queryFields(collection).join(', '), '. Синтаксис AIP-160: =, !=, :, <, <=, >, >=, AND, OR, NOT, скобки, поле:* (есть значение), строки в кавычках. Сортировка (параметр order_by): поле или "поле desc". Выгрузка содержит неудалённые записи текущего отбора без истории.');
    const readTimeHint = el('p', { class: 'hint', id: 'readTimeHint' },
      '"На момент" (параметр readTime) показывает записи в состоянии на выбранный момент, восстановленном из ревизий: запись, созданная позже, не видна, изменения после момента не учтены.');

    const root = el('div', {},
      el('h2', {}, cat.title, ' ', el('span', { class: 'muted mono small' }, `/v1/${collection}/`)),
      resultBox, form, filterError, hint, readTimeHint, actions);

    if (params.readTime) {
      const derived = collection === 'employees' ? ' Подразделение и должность сотрудника в срезе не заполняются, их даёт срез назначений.' : '';
      root.insertBefore(banner('warn', el('b', {}, `Срез на ${fmt.dateTime(params.readTime)}. `), `Записи показаны в состоянии на этот момент, восстановленном из ревизий.${derived}`), form);
    }

    let page;
    try {
      page = await api.list(collection, params);
    } catch (error) {
      if (error instanceof ApiError && error.status === 400) {
        const reason = error.fieldErrors.filter || error.message;
        if (error.fieldErrors.filter || /filter/i.test(error.message)) {
          filterInput.classList.add('invalid');
          filterInput.setAttribute('aria-invalid', 'true');
          filterError.textContent = reason;
        }
        root.appendChild(errorBanner(error));
        return root;
      }
      if (error instanceof ApiError && error.status === 403) {
        root.appendChild(stateCard(error, { backHref: href('/'), level: 3 }));
        return root;
      }
      throw error;
    }

    // the state column says only ACTIVE until deleted rows are shown
    const columns = listColumns(collection).filter((column) => column !== 'is_deleted' || params.allowDeleted);
    const rows = page.items;
    if (!rows.length && !params.pageToken) {
      root.appendChild(emptyBlock(views.emptyState(collection, user, params), { create: params.readTime ? null : href(`/${collection}/new`), reset: href(`/${collection}`) }));
      return root;
    }
    const body = rows.map((rec) => el('tr', { class: rec.is_deleted ? 'clickable deleted' : 'clickable', dataset: { href: recordHref(collection, rec.id) } },
      columns.map((column) => cellFor(collection, rec, column))));
    root.appendChild(el('div', { class: 'table-wrap', role: 'region', 'aria-label': `Записи: ${cat.title}` },
      table(columns.map((c) => ({ label: fieldLabel(collection, c) })), body, `${cat.title}: ${views.selectionText(params)}`)));

    const stack = session.pager[collection] || [];
    const pager = el('nav', { class: 'pager', 'aria-label': 'Страницы' },
      el('span', { class: 'muted', role: 'status' }, `На странице: ${rows.length}, размер страницы: ${params.pageSize}`),
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

  // the export of the current selection: filter, order and moment of the table, never the deleted records
  async function exportCatalog(collection, params, box) {
    replace(box, el('div', { class: 'banner banner-ok', role: 'status' }, loadingBlock('Выгрузка выполняется…')));
    const selection = { filter: params.filter, orderBy: params.orderBy, readTime: params.readTime };
    try {
      const file = await api.exportFile(collection, selection);
      download(file.blob, file.filename);
      replace(box, banner('ok', `Файл ${file.filename} получен (${fmt.integer(file.blob.size)} байт): ${views.selectionText(selection)}.`));
    } catch (error) {
      replace(box, errorBanner(error, null, () => exportCatalog(collection, params, box)));
    }
  }

  // ---- S-03: the record form with the details and the history panel ----

  function fieldInput(collection, field, value, locked) {
    const inputId = `f-${field.name}`;
    const describedBy = field.type === 'ref' ? `${inputId}-hint ${inputId}-ref ${inputId}-error` : `${inputId}-hint ${inputId}-error`;
    const common = { id: inputId, name: field.name, 'aria-describedby': describedBy, 'aria-required': field.required ? 'true' : null };
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
        const chosen = el('span', { class: 'hint ref-label', id: `${inputId}-ref`, 'aria-live': 'polite' });
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

  // one field of the form: the label above, the hint and the error below, both linked to the input for screen readers
  function fieldBox(label, name, note, control, required) {
    const input = control.matches('input, select') ? control : control.querySelector('input, select');
    return el('div', { class: 'field', dataset: { field: name } },
      el('label', { for: input.id }, label, required ? el('span', { class: 'required-mark', 'aria-hidden': 'true' }, ' *') : null),
      control,
      el('div', { class: 'hint', id: `${input.id}-hint` }, note),
      el('div', { class: 'error', id: `${input.id}-error` }));
  }

  // builds the form card: used standalone on S-03 and inside the employee card S-05
  function buildFormPanel(collection, rec, query, backTo) {
    const cat = CATALOGS[collection];
    const model = views.formModel(collection, rec, session.user, query);
    const { isNew, editable } = model;
    const draftKey = `rm.draft:${collection}:${isNew ? 'new' : rec.id}`;
    const draft = editable ? safeJson(storageGet(draftKey)) : null;
    const inputs = {};
    const boxes = {};

    const initial = (name) => {
      if (draft && name in draft) return draft[name];
      if (isNew && query && query.has(name)) return query.get(name);
      return rec ? rec[name] : '';
    };

    const formBanner = el('div', { role: 'status' });
    const fields = [];
    for (const item of model.fields) {
      const control = fieldInput(collection, item.field, initial(item.name), item.locked);
      const input = control.matches('input, select') ? control : control.querySelector('input, select');
      inputs[item.name] = input;
      boxes[item.name] = fieldBox(item.label, item.name, item.notes, control, item.required && !item.locked);
      fields.push(boxes[item.name]);
    }

    const clearErrors = () => {
      for (const [name, box] of Object.entries(boxes)) {
        box.classList.remove('invalid');
        box.querySelector('.error').textContent = '';
        inputs[name].removeAttribute('aria-invalid');
      }
      clear(formBanner);
    };

    const showFieldErrors = (error) => {
      const errors = error.fieldErrors;
      let first = null;
      for (const [field, message] of Object.entries(errors)) {
        const box = boxes[field];
        if (!box) continue;
        box.classList.add('invalid');
        box.querySelector('.error').textContent = message;
        inputs[field].setAttribute('aria-invalid', 'true');
        if (!first) first = inputs[field];
      }
      const rest = Object.entries(errors).filter(([field]) => !boxes[field]).map(([field, message]) => `${field}: ${message}`);
      replace(formBanner, banner('error', el('b', {}, `400 ${error.message}`), first ? ', см. подписи у полей.' : '.', rest.length ? ` ${rest.join('. ')}` : ''));
      if (first) first.focus();
    };

    const actions = el('div', { class: 'toolbar' });
    const busy = (state) => {
      for (const button of actions.querySelectorAll('button')) button.disabled = state;
      form.setAttribute('aria-busy', state ? 'true' : 'false');
    };
    if (model.actions.includes('save')) actions.appendChild(el('button', { type: 'submit', class: 'primary', id: 'save' }, 'Сохранить'));
    if (model.actions.includes('delete')) {
      actions.appendChild(el('button', {
        type: 'button',
        class: 'danger',
        id: 'delete',
        on: {
          click: async () => {
            if (!await confirmDialog(`Удалить ${recordLabel(collection, rec)} (#${rec.id})? Запись перейдёт в состояние DELETED, идентификатор останется занятым, восстановления нет: удалённая по ошибке запись создаётся заново.`, 'Удалить запись?')) return;
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
    if (model.actions.includes('purge')) {
      actions.appendChild(el('button', {
        type: 'button',
        class: 'danger',
        id: 'purge',
        on: {
          click: async () => {
            if (!await confirmDialog(`Удалить ${recordLabel(collection, rec)} (#${rec.id}) окончательно вместе с историей? Это действие нельзя отменить.`, 'Удалить окончательно?')) return;
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

    const form = el('form', { class: 'record-form', autocomplete: 'off', novalidate: true, 'aria-label': isNew ? `Новая запись: ${cat.title}` : `Запись ${recordLabel(collection, rec)}` },
      editable ? el('p', { class: 'hint' }, 'Поля со знаком * обязательны.') : null, fields, actions);
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
      model.readOnlyReason ? el('p', { class: 'hint', role: 'note' }, model.readOnlyReason === 'deleted' ? 'Запись удалена: поля только для чтения, восстановления нет.' : 'Только чтение: у роли нет нужного уровня на эту группу справочников.') : null,
      form);

    // a new dated record is checked against the record still in effect for the same employee
    if (isNew && cat.dated && collection !== 'absences' && inputs.employee_id && inputs.employee_id.value) {
      api.list(collection, { filter: `employee_id = ${Number(inputs.employee_id.value)} AND NOT end_date:*`, pageSize: 1 })
        .then((page) => {
          const open = page.items[0];
          if (!open) return;
          formBanner.appendChild(banner('warn', `Действующая запись #${open.id} с ${fmt.date(open.start_date)} не закрыта. Сначала закройте её датой на карточке сотрудника, иначе периоды пересекутся и запрос будет отклонён.`));
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
        el('dl', { class: 'meta compact' }, Object.entries(state).map(([key, value]) => [el('dt', {}, fieldLabel(collection, key), ' ', el('span', { class: 'mono muted small' }, key)), el('dd', {}, fmtField(collection, key, value))]))));
    };
    for (const revision of revisions) {
      box.appendChild(el('div', { class: 'revision' },
        el('div', { class: 'revision-head' },
          el('b', {}, `${revision.revision_number}`), ' ', badge(revisionKind(revision)), ' ', fmtTime(revision.changed_at), ' ',
          el('span', { class: 'muted mono small' }, revision.changed_by), ' ',
          el('button', { type: 'button', class: 'link', on: { click: () => showAsOf(revision.revision_number) } }, 'на ревизию')),
        el('ul', { class: 'changes' }, (revision.change || []).map((op) => el('li', {}, el('code', {}, `${op.op} ${fieldOf(op)}`), ': ', fmtField(collection, fieldOf(op), op.value))))));
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
    const left = el('div', {}, panel, collection === 'org_units' && !rec.is_deleted ? groupOpsCard(rec) : null);
    return el('div', { class: 'layout' }, left, el('div', {}, metaCard(collection, rec), await historyCard(collection, rec)));
  }

  // ---- group operations of an org unit (FR-RM-63, FR-RM-64): a check returns the plan, the run applies it ----

  // a small labelled input of a group operation form, its error line is filled from the details of a 400 answer
  function opField(form, name, label, control, hint) {
    const input = control.matches('input, select') ? control : control.querySelector('input, select');
    input.id = `${form}-${name}`;
    input.name = name;
    input.setAttribute('aria-describedby', `${input.id}-hint ${input.id}-error`);
    return el('div', { class: 'field', dataset: { field: name } },
      el('label', { for: input.id }, label),
      control,
      el('div', { class: 'hint', id: `${input.id}-hint` }, hint || ''),
      el('div', { class: 'error', id: `${input.id}-error` }));
  }

  function refInput(collection, placeholder) {
    const listId = `dl-op-${collection}-${Math.random().toString(36).slice(2, 8)}`;
    const input = el('input', { type: 'text', class: 'mono', list: listId, placeholder, inputmode: 'numeric', autocomplete: 'off' });
    const datalist = el('datalist', { id: listId });
    const chosen = el('span', { class: 'hint ref-label', 'aria-live': 'polite' });
    const show = async () => {
      const labels = await labelsOf(collection);
      const value = input.value.trim();
      chosen.textContent = value ? (labels.get(value) || 'записи с таким идентификатором нет') : '';
    };
    labelsOf(collection).then((labels) => replace(datalist, [...labels.entries()].map(([id, label]) => el('option', { value: id }, label))));
    input.addEventListener('input', show);
    return el('span', { class: 'ref' }, input, datalist, chosen);
  }

  // runs a check or the operation, shows the plan or the result, marks the fields of a 400 answer
  async function runGroupOp(box, form, call, body, validateOnly, describe) {
    for (const field of form.querySelectorAll('.field')) {
      field.classList.remove('invalid');
      field.querySelector('.error').textContent = '';
      const input = field.querySelector('input, select');
      if (input) input.removeAttribute('aria-invalid');
    }
    replace(box, loadingBlock(validateOnly ? 'Проверка…' : 'Выполнение…'));
    try {
      const result = await call({ ...body, validate_only: validateOnly });
      replace(box, describe(result));
      if (!validateOnly) forgetLabels('employees');
    } catch (error) {
      if (error instanceof ApiError && error.status === 400) {
        let marked = false;
        for (const [name, message] of Object.entries(error.fieldErrors)) {
          const field = form.querySelector(`.field[data-field="${name}"]`);
          if (!field) continue;
          field.classList.add('invalid');
          field.querySelector('.error').textContent = message;
          const input = field.querySelector('input, select');
          if (input) input.setAttribute('aria-invalid', 'true');
          marked = true;
        }
        replace(box, banner('error', el('b', {}, `400 ${error.message}`), marked ? ', см. подписи у полей.' : '.'));
        return;
      }
      replace(box, errorBanner(error, null, () => runGroupOp(box, form, call, body, validateOnly, describe)));
    }
  }

  function skippedList(skipped) {
    if (!skipped.length) return null;
    return el('div', {},
      el('h4', {}, `Пропущены: ${skipped.length}`),
      el('ul', {}, skipped.map((s) => el('li', {}, el('a', { href: recordHref('employees', s.employee_id) }, `#${s.employee_id}`), ': ', s.reason))));
  }

  function employeeLink(id) {
    const link = el('a', { href: recordHref('employees', id) }, `#${id}`);
    labelsOf('employees').then((labels) => { if (labels.get(String(id))) replace(link, `${labels.get(String(id))} #${id}`); });
    return link;
  }

  function groupOpsCard(rec) {
    const user = session.user;
    const canRevise = can(user, 'salaries', 'C') && can(user, 'salaries', 'U');
    const canTransfer = can(user, 'assignments', 'C') && can(user, 'assignments', 'U');
    if (!canRevise && !canTransfer) return null;

    const card = el('section', { class: 'card', 'aria-labelledby': 'groupOpsTitle' },
      el('h3', { id: 'groupOpsTitle' }, 'Групповые операции подразделения'),
      el('p', { class: 'hint' }, 'Операция затрагивает сотрудников, назначенных в подразделение на выбранную дату. Действующая запись каждого закрывается днём раньше, новая начинается с даты. "Проверить" показывает план и ничего не меняет, "Выполнить" применяет его целиком или не применяет совсем.'));

    if (canRevise) {
      const date = el('input', { type: 'date', value: todayIso() });
      const mode = el('select', {}, el('option', { value: 'percent' }, 'на процент'), el('option', { value: 'amount' }, 'новая сумма'));
      const percent = el('input', { type: 'number', step: '0.01', value: '10' });
      const amount = el('input', { type: 'number', step: '0.01', min: '0.01' });
      const currency = refInput('currencies', 'валюта текущего оклада');
      const subunits = el('input', { type: 'checkbox' });
      const box = el('div', { class: 'preview', 'aria-live': 'polite' });
      const form = el('form', { class: 'group-op', id: 'reviseForm', novalidate: true },
        el('h4', {}, 'Новые оклады с даты'),
        opField('revise', 'start_date', 'Дата начала новых окладов', date),
        opField('revise', 'mode', 'Изменение', mode),
        opField('revise', 'percent', 'Процент', percent, 'например 10 или -5, сумма округляется до копеек'),
        opField('revise', 'amount', 'Новая сумма', amount),
        opField('revise', 'currency_id', 'Валюта новой суммы', currency, 'пусто: валюта текущего оклада'),
        el('span', { class: 'check' }, subunits, el('label', { for: 'revise-subunits' }, 'Включая вложенные подразделения')));
      subunits.id = 'revise-subunits';
      const toggle = () => {
        const byPercent = mode.value === 'percent';
        form.querySelector('[data-field="percent"]').hidden = !byPercent;
        form.querySelector('[data-field="amount"]').hidden = byPercent;
        form.querySelector('[data-field="currency_id"]').hidden = byPercent;
      };
      mode.addEventListener('change', toggle);
      toggle();
      const body = () => {
        const b = { org_unit_id: rec.id, start_date: date.value, include_subunits: subunits.checked };
        if (mode.value === 'percent') b.percent = Number(percent.value);
        else {
          b.amount = Number(amount.value);
          const cur = currency.querySelector('input').value.trim();
          if (cur) b.currency_id = Number(cur);
        }
        return b;
      };
      const describe = (result) => el('div', {},
        banner(result.validate_only ? 'warn' : 'ok', result.validate_only ? `План: изменится окладов ${result.items.length}, ничего не сохранено.` : `Сохранено: новых окладов ${result.items.length}.`),
        result.items.length ? table(
          [{ label: 'Сотрудник' }, { label: 'Было', class: 'num' }, { label: 'Стало', class: 'num' }, { label: 'Период' }, { label: 'Запись' }],
          result.items.map((item) => el('tr', { class: 'clickable', dataset: { href: recordHref('employees', item.employee_id) } },
            el('td', {}, employeeLink(item.employee_id)),
            el('td', { class: 'num' }, item.previous_amount === undefined ? '-' : fmt.money(item.previous_amount)),
            el('td', { class: 'num' }, fmt.money(item.amount)),
            el('td', {}, fmt.period(item.start_date, item.end_date)),
            el('td', {}, item.salary_id ? el('a', { href: recordHref('salaries', item.salary_id), class: 'mono' }, `#${item.salary_id}`) : el('span', { class: 'muted' }, 'после выполнения')))),
          'Новые оклады сотрудников подразделения') : null,
        skippedList(result.skipped));
      form.appendChild(el('div', { class: 'toolbar' },
        el('button', { type: 'button', id: 'reviseCheck', on: { click: () => runGroupOp(box, form, api.reviseSalaries, body(), true, describe) } }, 'Проверить'),
        el('button', { type: 'button', class: 'primary', id: 'reviseRun', on: { click: async () => {
          if (!await confirmDialog(`Назначить новые оклады сотрудникам подразделения ${recordLabel('org_units', rec)} с ${fmt.date(date.value)}? Действующие оклады закроются днём раньше.`, 'Выполнить групповую операцию?')) return;
          runGroupOp(box, form, api.reviseSalaries, body(), false, describe);
        } } }, 'Выполнить')));
      form.appendChild(box);
      card.appendChild(form);
    }

    if (canTransfer) {
      const target = refInput('org_units', 'идентификатор подразделения');
      const date = el('input', { type: 'date', value: todayIso() });
      const position = refInput('positions', 'текущая должность');
      const subunits = el('input', { type: 'checkbox', id: 'transfer-subunits' });
      const box = el('div', { class: 'preview', 'aria-live': 'polite' });
      const form = el('form', { class: 'group-op', id: 'transferForm', novalidate: true },
        el('h4', {}, 'Перевод сотрудников в другое подразделение'),
        opField('transfer', 'target_org_unit_id', 'Подразделение назначения', target),
        opField('transfer', 'start_date', 'Дата перевода', date),
        opField('transfer', 'position_id', 'Должность в новом подразделении', position, 'пусто: должность сохраняется'),
        el('span', { class: 'check' }, subunits, el('label', { for: 'transfer-subunits' }, 'Включая вложенные подразделения')));
      const body = () => {
        const b = { org_unit_id: rec.id, target_org_unit_id: Number(target.querySelector('input').value.trim()) || 0, start_date: date.value, include_subunits: subunits.checked };
        const pos = position.querySelector('input').value.trim();
        if (pos) b.position_id = Number(pos);
        return b;
      };
      const describe = (result) => el('div', {},
        banner(result.validate_only ? 'warn' : 'ok', result.validate_only ? `План: переводятся сотрудников ${result.items.length}, ничего не сохранено.` : `Сохранено: переведено сотрудников ${result.items.length}.`),
        result.items.length ? table(
          [{ label: 'Сотрудник' }, { label: 'Из' }, { label: 'В' }, { label: 'Период' }, { label: 'Запись' }],
          result.items.map((item) => {
            const from = el('td', {}, `#${item.org_unit_id}`);
            const to = el('td', {}, `#${item.target_org_unit_id}`);
            refCell(fieldByName('assignments', 'org_unit_id'), item.org_unit_id).then((node) => replace(from, node));
            refCell(fieldByName('assignments', 'org_unit_id'), item.target_org_unit_id).then((node) => replace(to, node));
            return el('tr', { class: 'clickable', dataset: { href: recordHref('employees', item.employee_id) } },
              el('td', {}, employeeLink(item.employee_id)), from, to,
              el('td', {}, fmt.period(item.start_date, item.end_date)),
              el('td', {}, item.assignment_id ? el('a', { href: recordHref('assignments', item.assignment_id), class: 'mono' }, `#${item.assignment_id}`) : el('span', { class: 'muted' }, 'после выполнения')));
          }),
          'Переводы сотрудников подразделения') : null,
        skippedList(result.skipped));
      form.appendChild(el('div', { class: 'toolbar' },
        el('button', { type: 'button', id: 'transferCheck', on: { click: () => runGroupOp(box, form, api.transferAssignments, body(), true, describe) } }, 'Проверить'),
        el('button', { type: 'button', class: 'primary', id: 'transferRun', on: { click: async () => {
          if (!await confirmDialog(`Перевести сотрудников подразделения ${recordLabel('org_units', rec)} с ${fmt.date(date.value)}? Действующие назначения закроются днём раньше.`, 'Выполнить групповую операцию?')) return;
          runGroupOp(box, form, api.transferAssignments, body(), false, describe);
        } } }, 'Выполнить')));
      form.appendChild(box);
      card.appendChild(form);
    }
    return card;
  }

  // ---- S-05: the employee card ----

  function statusCard(rec) {
    const user = session.user;
    const manage = can(user, 'employees', 'U');
    const card = el('div', { class: 'card' },
      el('h2', {}, recordLabel('employees', rec), ' ', el('span', { class: 'muted mono small' }, `/v1/employees/${rec.id}`)),
      el('dl', { class: 'meta columns' },
        el('dt', {}, 'Состояние занятости ', el('span', { class: 'mono muted small' }, 'employment_state')), el('dd', {}, badge(rec.employment_state)),
        el('dt', {}, 'Дата приёма ', el('span', { class: 'mono muted small' }, 'hire_date')), el('dd', {}, fmtDate(rec.hire_date)),
        el('dt', {}, 'Дата увольнения ', el('span', { class: 'mono muted small' }, 'dismissal_date')), el('dd', {}, fmtDate(rec.dismissal_date)),
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
        if (salary) text = el('span', {}, `${fmt.money(salary.amount)} `, await refCell(fieldByName('salaries', 'currency_id'), salary.currency_id), ' ', el('span', { class: 'muted' }, `с ${fmt.date(salary.start_date)}`));
      } catch (error) {
        text = errorBanner(error);
      }
      rows.push(el('dt', {}, 'Оклад'), el('dd', {}, text));
    }
    return el('div', { class: 'card' }, el('h3', {}, 'Действующие значения'), el('p', { class: 'hint' }, `на ${fmt.date(today)}, из назначения и оклада с периодом действия`), el('dl', { class: 'meta' }, rows));
  }

  function periodLabel(row) {
    return fmt.period(row.start_date, row.end_date);
  }

  async function periodDetails(collection, row) {
    if (collection === 'assignments') return el('span', {}, await refCell(fieldByName('assignments', 'org_unit_id'), row.org_unit_id), ', ', await refCell(fieldByName('assignments', 'position_id'), row.position_id));
    if (collection === 'salaries') return el('span', {}, `${fmt.money(row.amount)} `, await refCell(fieldByName('salaries', 'currency_id'), row.currency_id));
    return badge(row.kind);
  }

  async function periodsCard(rec, requested) {
    const user = session.user;
    const tabs = DATED_TABS.filter(([collection]) => can(user, collection, 'R'));
    const active = tabs.some(([collection]) => collection === requested) ? requested : tabs[0][0];
    const nav = el('div', { class: 'tabs', role: 'tablist', 'aria-label': 'Периоды сотрудника' }, tabs.map(([collection, label]) => el('a', {
      role: 'tab', class: 'tab', id: `tab-${collection}`, 'aria-controls': 'periods-panel', 'aria-selected': collection === active ? 'true' : 'false', href: recordHref('employees', rec.id, { tab: collection }),
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
      body.push(el('tr', { class: 'clickable', dataset: { href: recordHref(active, row.id, { back: backTo }) } }, cells));
    }
    const title = DATED_TABS.find(([collection]) => collection === active)[1];
    card.appendChild(el('div', { role: 'tabpanel', id: 'periods-panel', 'aria-labelledby': `tab-${active}` },
      body.length
        ? table([{ label: 'Запись' }, { label: 'Период' }, { label: 'Значение' }, { label: '', srLabel: 'Действие' }], body, `${title} сотрудника ${recordLabel('employees', rec)}`)
        : el('div', { class: 'state', role: 'status' }, el('p', {}, `${title}: записей нет.`))));
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

  // a click anywhere on a row with data-href opens it like its link: the controls inside the row keep their own
  // clicks, a selected text is not a click, ctrl, meta or the middle button open a new tab; the keyboard path stays
  // the link in the first cell
  function rowTarget(event) {
    const row = event.target.closest('tr[data-href]');
    if (!row || event.target.closest('a, button, input, select, textarea, label, summary, form')) return null;
    const selection = window.getSelection ? String(window.getSelection()) : '';
    if (selection && row.contains(window.getSelection().anchorNode)) return null;
    return row.dataset.href;
  }

  function interceptRows() {
    document.addEventListener('click', (event) => {
      if (event.button !== 0) return;
      const target = rowTarget(event);
      if (!target) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey) window.open(target, '_blank', 'noopener');
      else go(target);
    });
    document.addEventListener('auxclick', (event) => {
      if (event.button !== 1) return;
      const target = rowTarget(event);
      if (target) window.open(target, '_blank', 'noopener');
    });
  }

  // the sticky header of a table sits under the top bar, whose height changes with the width of the window
  function trackTopbar() {
    const topbar = $('.topbar');
    const update = () => document.documentElement.style.setProperty('--topbar-height', `${topbar.offsetHeight}px`);
    update();
    if (window.ResizeObserver) new ResizeObserver(update).observe(topbar);
    else window.addEventListener('resize', update);
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
    interceptRows();
    trackTopbar();
    window.addEventListener('popstate', render);
    render();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
