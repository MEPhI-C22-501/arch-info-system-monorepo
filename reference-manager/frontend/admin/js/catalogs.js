// catalog schemas of the first version by documents 130 and 120 (contract of ADR-022), groups and roles of document 070
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else (root.RM = root.RM || {}).catalogs = factory();
})(globalThis, function () {
  'use strict';

  const SLUG = { pattern: /^[a-z][a-z0-9-]{1,63}$/, hint: 'строчные латинские буквы, цифры и дефис, от 2 до 64 символов' };

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

  // read-only fields of every record, set by the service
  const COMMON = [
    { name: 'id', label: 'Идентификатор' },
    { name: 'is_deleted', label: 'Удалена' },
    { name: 'revision', label: 'Ревизия' },
    { name: 'last_changer', label: 'Кто изменил' },
    { name: 'created_at', label: 'Создана' },
    { name: 'updated_at', label: 'Изменена' },
    { name: 'deleted_at', label: 'Удалена в' },
  ];

  const code = (hint) => ({ name: 'code', label: 'Код', type: 'text', required: true, pattern: SLUG.pattern, hint: hint || SLUG.hint, maxLen: 64 });
  const name = (label) => ({ name: 'name', label: label || 'Наименование', type: 'text', required: true, maxLen: 128 });
  const employeeRef = { name: 'employee_id', label: 'Сотрудник', type: 'ref', ref: 'employees', required: true, immutable: true };
  const startDate = { name: 'start_date', label: 'Действует с', type: 'date', required: true };
  const endDate = { name: 'end_date', label: 'Действует по', type: 'date', hint: 'пусто, пока действует' };

  const CATALOGS = {
    currencies: {
      title: 'Валюты',
      group: 'G-1',
      labelFields: ['code', 'name'],
      fields: [
        { name: 'code', label: 'Код', type: 'text', required: true, pattern: /^[A-Z]{3}$/, hint: 'три заглавные латинские буквы (ISO 4217)' },
        { name: 'number', label: 'Числовой код', type: 'text', required: true, pattern: /^\d{3}$/, hint: 'три цифры' },
        name(),
        { name: 'decimals', label: 'Знаков дробной части', type: 'integer', required: true, min: 0, max: 4 },
      ],
    },
    countries: {
      title: 'Страны',
      group: 'G-1',
      labelFields: ['alpha2', 'name'],
      fields: [
        { name: 'alpha2', label: 'Код alpha-2', type: 'text', required: true, pattern: /^[A-Z]{2}$/, hint: 'две заглавные латинские буквы (ISO 3166-1)' },
        { name: 'alpha3', label: 'Код alpha-3', type: 'text', required: true, pattern: /^[A-Z]{3}$/, hint: 'три заглавные латинские буквы' },
        { name: 'numeric_code', label: 'Числовой код', type: 'text', required: true, pattern: /^\d{3}$/, hint: 'три цифры' },
        name(),
        { name: 'currency_id', label: 'Основная валюта', type: 'ref', ref: 'currencies' },
      ],
    },
    project_roles: {
      title: 'Проектные роли',
      group: 'G-1',
      labelFields: ['code', 'name'],
      fields: [code(), name(), { name: 'description', label: 'Описание', type: 'text', maxLen: 512 }],
    },
    grades: {
      title: 'Грейды',
      group: 'G-1',
      labelFields: ['code', 'name'],
      fields: [code(), name(), { name: 'rank', label: 'Порядок', type: 'integer', required: true, min: 1, max: 100, hint: 'выше - старше' }],
    },
    org_units: {
      title: 'Подразделения',
      group: 'G-2',
      labelFields: ['code', 'name'],
      fields: [
        code(),
        name(),
        { name: 'kind', label: 'Вид', type: 'enum', values: ['DEPARTMENT', 'TEAM'], required: true },
        { name: 'parent_id', label: 'Вышестоящее подразделение', type: 'ref', ref: 'org_units', hint: 'пусто для подразделения верхнего уровня' },
      ],
    },
    positions: {
      title: 'Должности',
      group: 'G-2',
      labelFields: ['code', 'name'],
      fields: [code(), name()],
    },
    employees: {
      title: 'Сотрудники',
      group: 'G-2',
      card: true,
      labelFields: ['family_name', 'given_name', 'middle_name'],
      fields: [
        { name: 'personnel_number', label: 'Табельный номер', type: 'text', required: true, pattern: /^[0-9]{1,10}$/, hint: 'от 1 до 10 цифр' },
        { name: 'family_name', label: 'Фамилия', type: 'text', required: true, maxLen: 100, account: true },
        { name: 'given_name', label: 'Имя', type: 'text', required: true, maxLen: 100, account: true },
        { name: 'middle_name', label: 'Отчество', type: 'text', maxLen: 100 },
        { name: 'email', label: 'Адрес почты', type: 'email', required: true, account: true },
        { name: 'username', label: 'Логин', type: 'text', required: true, immutable: true, pattern: /^[a-z][a-z0-9._-]{2,63}$/, hint: 'логин в Keycloak: строчные латинские буквы, цифры, точка, дефис, от 3 символов, после создания не меняется' },
        { name: 'hire_date', label: 'Дата приёма', type: 'date', required: true },
      ],
      readOnly: [
        { name: 'employment_state', label: 'Состояние занятости', type: 'enum' },
        { name: 'dismissal_date', label: 'Дата увольнения', type: 'date' },
        { name: 'org_unit_id', label: 'Подразделение', type: 'ref', ref: 'org_units' },
        { name: 'position_id', label: 'Должность', type: 'ref', ref: 'positions' },
        { name: 'account_state', label: 'Учётная запись', type: 'enum' },
        { name: 'account_user_id', label: 'Идентификатор учётной записи', type: 'text' },
      ],
      columns: ['id', 'personnel_number', 'family_name', 'given_name', 'username', 'hire_date', 'org_unit_id', 'position_id', 'employment_state', 'account_state', 'is_deleted'],
    },
    assignments: {
      title: 'Назначения',
      group: 'G-2',
      dated: true,
      fields: [
        employeeRef,
        { name: 'org_unit_id', label: 'Подразделение', type: 'ref', ref: 'org_units', required: true },
        { name: 'position_id', label: 'Должность', type: 'ref', ref: 'positions', required: true },
        startDate,
        endDate,
      ],
    },
    salaries: {
      title: 'Оклады',
      group: 'G-3',
      dated: true,
      fields: [
        employeeRef,
        { name: 'amount', label: 'Оклад в месяц', type: 'money', required: true, min: 0.01, hint: 'положительное число, два знака' },
        { name: 'currency_id', label: 'Валюта', type: 'ref', ref: 'currencies', required: true },
        startDate,
        endDate,
      ],
    },
    absences: {
      title: 'Отсутствия',
      group: 'G-3',
      dated: true,
      fields: [
        employeeRef,
        { name: 'kind', label: 'Вид', type: 'enum', values: ['VACATION', 'SICK_LEAVE', 'OTHER'], required: true },
        { name: 'start_date', label: 'Первый день', type: 'date', required: true },
        { name: 'end_date', label: 'Последний день', type: 'date', required: true },
      ],
    },
  };

  function levels(user, collection) {
    const group = CATALOGS[collection].group;
    let result = '';
    for (const role of (user && user.roles) || []) result += (ROLES[role] && ROLES[role][group]) || '';
    return result;
  }

  function can(user, collection, level) {
    return levels(user, collection).includes(level);
  }

  function hasAnyRole(user) {
    return ((user && user.roles) || []).some((role) => ROLES[role]);
  }

  // fields a client sends on create and update
  function inputFields(collection) {
    return CATALOGS[collection].fields;
  }

  function readOnlyFields(collection) {
    return CATALOGS[collection].readOnly || [];
  }

  function fieldByName(collection, fieldName) {
    return inputFields(collection).find((f) => f.name === fieldName) || readOnlyFields(collection).find((f) => f.name === fieldName) || null;
  }

  // fields a List filter and order_by may name: the fields of the catalog and the lifecycle fields, never the id
  function queryFields(collection) {
    return [...inputFields(collection).map((f) => f.name), ...readOnlyFields(collection).map((f) => f.name), ...COMMON.map((f) => f.name).filter((n) => n !== 'id')];
  }

  function fieldLabel(collection, fieldName) {
    const field = fieldByName(collection, fieldName) || COMMON.find((f) => f.name === fieldName);
    return field ? field.label : fieldName;
  }

  // columns of the table screen in their order
  function listColumns(collection) {
    const cat = CATALOGS[collection];
    if (cat.columns) return cat.columns;
    return ['id', ...cat.fields.map((f) => f.name), 'is_deleted'];
  }

  // a short human name of a record: the code and the name, the full name of an employee, the id of a dated record
  function recordLabel(collection, rec) {
    const cat = CATALOGS[collection];
    if (!rec) return '';
    if (cat.labelFields) {
      const parts = cat.labelFields.map((f) => rec[f]).filter((v) => v !== null && v !== undefined && v !== '');
      if (parts.length) return parts.join(' ');
    }
    return `#${rec.id}`;
  }

  function normalize(value) {
    return value === null || value === undefined ? '' : String(value).trim();
  }

  // converts the text of the inputs into the JSON body of a request
  function toBody(collection, values) {
    const body = {};
    for (const field of inputFields(collection)) {
      const text = normalize(values[field.name]);
      switch (field.type) {
        case 'integer':
        case 'money':
        case 'ref':
          body[field.name] = text === '' ? null : Number(text);
          break;
        default:
          body[field.name] = text === '' && !field.required ? null : text;
      }
    }
    return body;
  }

  // the names of the updatable fields whose text differs from the stored record
  function updateMask(collection, rec, values) {
    const mask = [];
    for (const field of inputFields(collection)) {
      if (field.immutable) continue;
      if (!(field.name in values)) continue;
      if (normalize(values[field.name]) !== normalize(rec[field.name])) mask.push(field.name);
    }
    return mask;
  }

  return { GROUPS, ROLES, COMMON, CATALOGS, levels, can, hasAnyRole, inputFields, readOnlyFields, fieldByName, queryFields, fieldLabel, listColumns, recordLabel, toBody, updateMask, normalize };
});
