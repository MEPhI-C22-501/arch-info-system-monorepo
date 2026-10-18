// catalog schemas, catalog groups and roles of the first version (documents 070, 120, 130)
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else (root.RM = root.RM || {}).catalogs = factory();
})(globalThis, function () {
  'use strict';

  const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
  const SLUG_RE = /^[a-z][a-z0-9-]{1,63}$/;
  const SLUG_HINT = 'строчные латинские буквы, цифры и дефис, от 2 до 64 символов';

  // the order of groups is the order of sections on the catalog list screen
  const GROUPS = {
    'G-2': { title: 'Кадровые справочники', collections: ['employees', 'org_units', 'positions', 'assignments'] },
    'G-3': { title: 'Оклады и отсутствия', collections: ['salaries', 'absences'] },
    'G-1': { title: 'Общие классификаторы', collections: ['currencies', 'countries', 'project_roles', 'grades'] },
  };

  // access levels per group, letters as in document 070: C create, R read, U update, X export, D delete
  const ROLES = {
    'reference-reader': { 'G-1': 'RX', 'G-2': 'RX' },
    'reference-hr-reader': { 'G-1': 'RX', 'G-2': 'RX', 'G-3': 'RX' },
    'reference-admin': { 'G-1': 'CRUXD', 'G-2': 'RX' },
    'reference-hr-admin': { 'G-1': 'RX', 'G-2': 'CRUXD', 'G-3': 'CRUXD' },
  };

  // step 1 has no login: the role switcher stands in for the token
  const USERS = [
    { key: 'admin', label: 'admin - reference-admin', username: 'admin@erp', roles: ['reference-admin'] },
    { key: 'hr-admin', label: 'hr-admin - reference-hr-admin', username: 'hr.admin@erp', roles: ['reference-hr-admin'] },
    { key: 'reader', label: 'reader - reference-reader', username: 'reader@erp', roles: ['reference-reader'] },
    { key: 'hr-reader', label: 'hr-reader - reference-hr-reader', username: 'hr.reader@erp', roles: ['reference-hr-reader'] },
    { key: 'none', label: 'учётная запись без ролей', username: 'guest@erp', roles: [] },
    { key: 'anonymous', label: 'без токена', username: null, roles: [], anonymous: true },
  ];

  const EMPLOYEE_REF = { name: 'employee', label: 'Сотрудник', type: 'ref', ref: 'employees', required: true, immutable: true };
  const START_DATE = { name: 'start_date', label: 'Действует с', type: 'date', required: true };
  const END_DATE = { name: 'end_date', label: 'Действует по', type: 'date', hint: 'пусто - действует сейчас' };

  const CATALOGS = {
    employees: {
      title: 'Сотрудники',
      group: 'G-2',
      idParam: 'employee_id',
      idHint: 'табельный номер: от 1 до 10 цифр',
      idRe: /^[0-9]{1,10}$/,
      displayName: true,
      card: true,
      fields: [
        { name: 'family_name', label: 'Фамилия', type: 'text', required: true, maxLen: 100, account: true },
        { name: 'given_name', label: 'Имя', type: 'text', required: true, maxLen: 100, account: true },
        { name: 'middle_name', label: 'Отчество', type: 'text', maxLen: 100, account: true },
        { name: 'email', label: 'Адрес почты', type: 'email', required: true, re: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, err: 'адрес вида user@example.org', unique: true, account: true },
        { name: 'username', label: 'Логин', type: 'text', required: true, re: /^[a-z][a-z0-9._-]{2,63}$/, err: 'строчные латинские буквы, цифры, точка, дефис, от 3 символов', unique: true, immutable: true },
        { name: 'hire_date', label: 'Дата приёма', type: 'date', required: true },
      ],
      readOnly: [
        { name: 'employment_state', label: 'Состояние занятости' },
        { name: 'dismissal_date', label: 'Дата увольнения' },
        { name: 'org_unit', label: 'Подразделение' },
        { name: 'position', label: 'Должность' },
        { name: 'account_state', label: 'Состояние учётной записи' },
        { name: 'account_user_id', label: 'Идентификатор учётной записи' },
      ],
    },
    org_units: {
      title: 'Подразделения',
      group: 'G-2',
      idParam: 'org_unit_id',
      idHint: SLUG_HINT,
      idRe: SLUG_RE,
      displayName: true,
      fields: [
        { name: 'kind', label: 'Вид', type: 'enum', values: ['DEPARTMENT', 'TEAM'], required: true },
        { name: 'parent', label: 'Вышестоящее подразделение', type: 'ref', ref: 'org_units' },
      ],
    },
    positions: {
      title: 'Должности',
      group: 'G-2',
      idParam: 'position_id',
      idHint: SLUG_HINT,
      idRe: SLUG_RE,
      displayName: true,
      fields: [],
    },
    assignments: {
      title: 'Назначения',
      group: 'G-2',
      dated: true,
      displayName: false,
      fields: [
        EMPLOYEE_REF,
        { name: 'org_unit', label: 'Подразделение', type: 'ref', ref: 'org_units', required: true },
        { name: 'position', label: 'Должность', type: 'ref', ref: 'positions', required: true },
        START_DATE,
        END_DATE,
      ],
    },
    salaries: {
      title: 'Оклады',
      group: 'G-3',
      dated: true,
      displayName: false,
      fields: [
        EMPLOYEE_REF,
        { name: 'amount', label: 'Оклад в месяц', type: 'number', required: true, min: 0.01, err: 'положительное число' },
        { name: 'currency', label: 'Валюта', type: 'ref', ref: 'currencies', required: true },
        START_DATE,
        END_DATE,
      ],
    },
    absences: {
      title: 'Отсутствия',
      group: 'G-3',
      dated: true,
      displayName: false,
      fields: [
        EMPLOYEE_REF,
        { name: 'kind', label: 'Вид', type: 'enum', values: ['VACATION', 'SICK_LEAVE', 'OTHER'], required: true },
        { name: 'start_date', label: 'Первый день', type: 'date', required: true },
        { name: 'end_date', label: 'Последний день', type: 'date', required: true },
      ],
    },
    currencies: {
      title: 'Валюты',
      group: 'G-1',
      idParam: 'currency_id',
      idHint: 'три заглавные латинские буквы (ISO 4217)',
      idRe: /^[A-Z]{3}$/,
      displayName: true,
      fields: [
        { name: 'numeric_code', label: 'Числовой код', type: 'text', required: true, re: /^[0-9]{3}$/, err: 'три цифры', unique: true },
        { name: 'minor_units', label: 'Знаков дробной части', type: 'number', required: true, min: 0, max: 6, integer: true, err: 'целое число от 0 до 6' },
        { name: 'symbol', label: 'Символ', type: 'text', maxLen: 8 },
      ],
    },
    countries: {
      title: 'Страны',
      group: 'G-1',
      idParam: 'country_id',
      idHint: 'две заглавные латинские буквы (ISO 3166-1 alpha-2)',
      idRe: /^[A-Z]{2}$/,
      displayName: true,
      fields: [
        { name: 'alpha3', label: 'Код alpha-3', type: 'text', required: true, re: /^[A-Z]{3}$/, err: 'три заглавные латинские буквы', unique: true },
        { name: 'numeric_code', label: 'Числовой код', type: 'text', required: true, re: /^[0-9]{3}$/, err: 'три цифры', unique: true },
        { name: 'currency', label: 'Валюта', type: 'ref', ref: 'currencies' },
      ],
    },
    project_roles: {
      title: 'Проектные роли',
      group: 'G-1',
      idParam: 'project_role_id',
      idHint: SLUG_HINT,
      idRe: SLUG_RE,
      displayName: true,
      fields: [],
    },
    grades: {
      title: 'Грейды',
      group: 'G-1',
      idParam: 'grade_id',
      idHint: SLUG_HINT,
      idRe: SLUG_RE,
      displayName: true,
      fields: [],
    },
  };

  const LABELS = {
    name: 'name',
    display_name: 'Наименование',
    state: 'Состояние',
    etag: 'etag',
    delete_time: 'Время удаления',
  };

  function levels(user, collection) {
    const group = CATALOGS[collection].group;
    let result = '';
    for (const role of user.roles || []) result += (ROLES[role] && ROLES[role][group]) || '';
    return result;
  }

  function can(user, collection, level) {
    return levels(user, collection).includes(level);
  }

  // stored fields of a record, in the order they are shown and exported
  function storedFields(collection) {
    const cat = CATALOGS[collection];
    const names = [];
    if (cat.displayName) names.push('display_name');
    for (const field of cat.fields) names.push(field.name);
    return names;
  }

  // fields a List filter and order_by may name
  function queryFields(collection) {
    const cat = CATALOGS[collection];
    const names = ['name', 'state', 'etag', 'delete_time', ...storedFields(collection)];
    for (const field of cat.readOnly || []) names.push(field.name);
    return names;
  }

  function fieldLabel(collection, name) {
    const cat = CATALOGS[collection];
    const field = cat.fields.find((f) => f.name === name) || (cat.readOnly || []).find((f) => f.name === name);
    return field ? field.label : LABELS[name] || name;
  }

  function refTarget(value) {
    const match = /^([a-z_]+)\/([^/]+)$/.exec(String(value || ''));
    return match ? { collection: match[1], id: match[2] } : null;
  }

  return { DATE_RE, GROUPS, ROLES, USERS, CATALOGS, LABELS, levels, can, storedFields, queryFields, fieldLabel, refTarget };
});
