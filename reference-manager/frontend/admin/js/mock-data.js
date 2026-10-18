// sample data of the step 1 admin panel: records hold their final state, history lists the changes that led to it
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else (root.RM = root.RM || {}).mockData = factory();
})(globalThis, function () {
  'use strict';

  const SEED_TIME = '2026-01-10T09:00:00Z';
  const SEED_AUTHOR = 'seed@erp';

  const records = {
    currencies: [
      { id: 'RUB', display_name: 'Российский рубль', numeric_code: '643', minor_units: 2, symbol: '₽' },
      { id: 'USD', display_name: 'Доллар США', numeric_code: '840', minor_units: 2, symbol: '$' },
      { id: 'EUR', display_name: 'Евро', numeric_code: '978', minor_units: 2, symbol: '€' },
      { id: 'CNY', display_name: 'Китайский юань', numeric_code: '156', minor_units: 2, symbol: '¥' },
      { id: 'KZT', display_name: 'Казахстанский тенге', numeric_code: '398', minor_units: 2, symbol: '₸' },
      { id: 'GBP', display_name: 'Фунт стерлингов', numeric_code: '826', minor_units: 2, symbol: '£' },
      { id: 'JPY', display_name: 'Японская иена', numeric_code: '392', minor_units: 0, symbol: '¥' },
      { id: 'XTS', display_name: 'Код для тестирования', numeric_code: '963', minor_units: 2, symbol: null, delete_time: '2026-03-02T10:15:00Z' },
    ],
    countries: [
      { id: 'RU', display_name: 'Россия', alpha3: 'RUS', numeric_code: '643', currency: 'currencies/RUB' },
      { id: 'KZ', display_name: 'Казахстан', alpha3: 'KAZ', numeric_code: '398', currency: 'currencies/KZT' },
      { id: 'CN', display_name: 'Китай', alpha3: 'CHN', numeric_code: '156', currency: 'currencies/CNY' },
      { id: 'DE', display_name: 'Германия', alpha3: 'DEU', numeric_code: '276', currency: 'currencies/EUR' },
      { id: 'US', display_name: 'США', alpha3: 'USA', numeric_code: '840', currency: 'currencies/USD' },
      { id: 'GB', display_name: 'Великобритания', alpha3: 'GBR', numeric_code: '826', currency: 'currencies/GBP' },
      { id: 'JP', display_name: 'Япония', alpha3: 'JPN', numeric_code: '392', currency: 'currencies/JPY' },
    ],
    project_roles: [
      { id: 'developer', display_name: 'Разработчик' },
      { id: 'analyst', display_name: 'Аналитик' },
      { id: 'tester', display_name: 'Тестировщик' },
      { id: 'team-lead', display_name: 'Руководитель команды' },
      { id: 'project-manager', display_name: 'Руководитель проекта' },
      { id: 'devops', display_name: 'Инженер эксплуатации' },
    ],
    grades: [
      { id: 'junior', display_name: 'Junior' },
      { id: 'middle', display_name: 'Middle' },
      { id: 'senior', display_name: 'Senior' },
      { id: 'lead', display_name: 'Lead' },
    ],
    org_units: [
      { id: 'dev', display_name: 'Департамент разработки', kind: 'DEPARTMENT', parent: null },
      { id: 'dev-backend', display_name: 'Команда бэкенда', kind: 'TEAM', parent: 'org_units/dev' },
      { id: 'dev-frontend', display_name: 'Команда фронтенда', kind: 'TEAM', parent: 'org_units/dev' },
      { id: 'mobile', display_name: 'Команда мобильной разработки', kind: 'TEAM', parent: 'org_units/dev', delete_time: '2026-06-30T15:00:00Z' },
      { id: 'qa', display_name: 'Отдел качества', kind: 'DEPARTMENT', parent: null },
      { id: 'qa-automation', display_name: 'Команда автоматизации тестирования', kind: 'TEAM', parent: 'org_units/qa' },
      { id: 'hr', display_name: 'Кадровая служба', kind: 'DEPARTMENT', parent: null },
      { id: 'finance', display_name: 'Финансовый отдел', kind: 'DEPARTMENT', parent: null },
    ],
    positions: [
      { id: 'developer', display_name: 'Разработчик' },
      { id: 'senior-developer', display_name: 'Старший разработчик' },
      { id: 'team-lead', display_name: 'Руководитель команды' },
      { id: 'department-head', display_name: 'Руководитель департамента' },
      { id: 'qa-engineer', display_name: 'Инженер по тестированию' },
      { id: 'analyst', display_name: 'Аналитик' },
      { id: 'hr-manager', display_name: 'Менеджер по персоналу' },
      { id: 'accountant', display_name: 'Бухгалтер' },
    ],
    employees: [
      employee('1001', 'Иванов', 'Иван', 'Иванович', 'i.ivanov', '2024-01-15', 'ENABLED'),
      employee('1002', 'Петрова', 'Мария', 'Сергеевна', 'm.petrova', '2023-09-01', 'ENABLED'),
      employee('1003', 'Сидоров', 'Алексей', 'Павлович', 'a.sidorov', '2022-03-14', 'ENABLED', { email: 'alexey.sidorov@example.org' }),
      employee('1004', 'Кузнецова', 'Анна', 'Дмитриевна', 'a.kuznetsova', '2024-06-03', 'ENABLED'),
      employee('1005', 'Смирнов', 'Дмитрий', 'Олегович', 'd.smirnov', '2021-11-22', 'ENABLED'),
      employee('1006', 'Васильева', 'Ольга', 'Николаевна', 'o.vasileva', '2025-02-10', 'ENABLED'),
      employee('1007', 'Попов', 'Николай', 'Андреевич', 'n.popov', '2020-05-18', 'DISABLED', { employment_state: 'DISMISSED', dismissal_date: '2026-08-31' }),
      employee('1008', 'Новикова', 'Екатерина', 'Игоревна', 'e.novikova', '2025-09-01', 'ENABLED'),
      employee('1009', 'Морозов', 'Павел', 'Викторович', 'p.morozov', '2026-10-01', 'PENDING'),
      employee('1010', 'Волкова', 'Светлана', 'Юрьевна', 's.volkova', '2023-04-03', 'ENABLED'),
      employee('1011', 'Лебедев', 'Артём', 'Максимович', 'a.lebedev', '2024-10-07', 'ENABLED'),
      employee('1012', 'Козлова', 'Дарья', 'Романовна', 'd.kozlova', '2022-08-29', 'ENABLED'),
    ],
    assignments: [
      assignment('1', '1001', 'dev-backend', 'developer', '2024-01-15', '2025-06-30'),
      assignment('2', '1001', 'dev-backend', 'senior-developer', '2025-07-01', null),
      assignment('3', '1002', 'dev-frontend', 'developer', '2023-09-01', null),
      assignment('4', '1003', 'dev-backend', 'team-lead', '2022-03-14', null),
      assignment('5', '1004', 'qa', 'qa-engineer', '2024-06-03', null),
      assignment('6', '1005', 'dev', 'department-head', '2021-11-22', null),
      assignment('7', '1006', 'qa-automation', 'qa-engineer', '2025-02-10', null),
      assignment('8', '1007', 'dev-frontend', 'developer', '2020-05-18', '2026-08-31'),
      assignment('9', '1008', 'dev-backend', 'developer', '2025-09-01', null),
      assignment('10', '1010', 'hr', 'hr-manager', '2023-04-03', null),
      assignment('11', '1011', 'dev-frontend', 'developer', '2024-10-07', null),
      assignment('12', '1012', 'finance', 'accountant', '2022-08-29', null),
      Object.assign(assignment('13', '1004', 'dev-frontend', 'developer', '2024-06-03', null), { delete_time: '2024-06-04T08:30:00Z' }),
    ],
    salaries: [
      salary('1', '1001', 150000, '2024-01-15', '2025-06-30'),
      salary('2', '1001', 220000, '2025-07-01', null),
      salary('3', '1002', 160000, '2023-09-01', null),
      salary('4', '1003', 300000, '2022-03-14', null),
      salary('5', '1004', 120000, '2024-06-03', null),
      salary('6', '1005', 400000, '2021-11-22', null),
      salary('7', '1006', 110000, '2025-02-10', null),
      salary('8', '1007', 140000, '2020-05-18', '2026-08-31'),
      salary('9', '1008', 130000, '2025-09-01', null),
      salary('10', '1010', 150000, '2023-04-03', null),
      salary('11', '1011', 125000, '2024-10-07', null),
      salary('12', '1012', 135000, '2022-08-29', null),
    ],
    absences: [
      absence('1', '1001', 'VACATION', '2026-07-06', '2026-07-19'),
      absence('2', '1002', 'SICK_LEAVE', '2026-09-14', '2026-09-18'),
      absence('3', '1004', 'VACATION', '2026-10-20', '2026-11-02'),
      absence('4', '1005', 'OTHER', '2026-03-02', '2026-03-03'),
      absence('5', '1011', 'VACATION', '2026-08-03', '2026-08-16'),
    ],
  };

  // revisions after the seed CREATED one, in chronological order
  const history = [
    { name: 'currencies/RUB', action: 'UPDATED', author: 'admin@erp', create_time: '2025-02-03T11:20:00Z', changes: [{ field: 'symbol', old_value: 'руб.', new_value: '₽' }] },
    { name: 'currencies/XTS', action: 'DELETED', author: 'admin@erp', create_time: '2026-03-02T10:15:00Z', changes: [{ field: 'state', old_value: 'ACTIVE', new_value: 'DELETED' }, { field: 'delete_time', old_value: null, new_value: '2026-03-02T10:15:00Z' }] },
    { name: 'org_units/mobile', action: 'DELETED', author: 'hr.admin@erp', create_time: '2026-06-30T15:00:00Z', changes: [{ field: 'state', old_value: 'ACTIVE', new_value: 'DELETED' }, { field: 'delete_time', old_value: null, new_value: '2026-06-30T15:00:00Z' }] },
    { name: 'assignments/13', action: 'DELETED', author: 'hr.admin@erp', create_time: '2024-06-04T08:30:00Z', changes: [{ field: 'state', old_value: 'ACTIVE', new_value: 'DELETED' }, { field: 'delete_time', old_value: null, new_value: '2024-06-04T08:30:00Z' }] },
    { name: 'employees/1003', action: 'UPDATED', author: 'hr.admin@erp', create_time: '2026-05-12T13:05:00Z', changes: [{ field: 'email', old_value: 'a.sidorov@example.org', new_value: 'alexey.sidorov@example.org' }] },
    { name: 'employees/1007', action: 'UPDATED', author: 'hr.admin@erp', create_time: '2026-08-29T16:40:00Z', changes: [{ field: 'employment_state', old_value: 'EMPLOYED', new_value: 'DISMISSED' }, { field: 'dismissal_date', old_value: null, new_value: '2026-08-31' }, { field: 'account_state', old_value: 'ENABLED', new_value: 'PENDING' }] },
    { name: 'employees/1007', action: 'UPDATED', author: 'hr.admin@erp', create_time: '2026-08-29T16:40:01Z', changes: [{ field: 'account_state', old_value: 'PENDING', new_value: 'DISABLED' }] },
    { name: 'assignments/8', action: 'UPDATED', author: 'hr.admin@erp', create_time: '2026-08-29T16:40:00Z', changes: [{ field: 'end_date', old_value: null, new_value: '2026-08-31' }] },
    { name: 'salaries/8', action: 'UPDATED', author: 'hr.admin@erp', create_time: '2026-08-29T16:40:00Z', changes: [{ field: 'end_date', old_value: null, new_value: '2026-08-31' }] },
    { name: 'assignments/1', action: 'UPDATED', author: 'hr.admin@erp', create_time: '2025-06-25T09:10:00Z', changes: [{ field: 'end_date', old_value: null, new_value: '2025-06-30' }] },
    { name: 'salaries/1', action: 'UPDATED', author: 'hr.admin@erp', create_time: '2025-06-25T09:11:00Z', changes: [{ field: 'end_date', old_value: null, new_value: '2025-06-30' }] },
  ];

  function employee(id, familyName, givenName, middleName, username, hireDate, accountState, extra) {
    const pending = accountState === 'PENDING';
    return Object.assign({
      id,
      display_name: `${familyName} ${givenName} ${middleName}`.trim(),
      family_name: familyName,
      given_name: givenName,
      middle_name: middleName,
      email: `${username}@example.org`,
      username,
      hire_date: hireDate,
      employment_state: 'EMPLOYED',
      dismissal_date: null,
      account_state: accountState,
      account_user_id: pending ? null : `7f0c2b9e-0000-4000-8000-00000000${id}`,
      account_operation: pending ? 'CREATE' : null,
      account_operation_id: pending ? `0b1d2e3f-0000-4000-8000-00000000${id}` : null,
    }, extra || {});
  }

  function assignment(id, employeeId, orgUnit, position, startDate, endDate) {
    return { id, employee: `employees/${employeeId}`, org_unit: `org_units/${orgUnit}`, position: `positions/${position}`, start_date: startDate, end_date: endDate };
  }

  function salary(id, employeeId, amount, startDate, endDate) {
    return { id, employee: `employees/${employeeId}`, amount, currency: 'currencies/RUB', start_date: startDate, end_date: endDate };
  }

  function absence(id, employeeId, kind, startDate, endDate) {
    return { id, employee: `employees/${employeeId}`, kind, start_date: startDate, end_date: endDate };
  }

  return { SEED_TIME, SEED_AUTHOR, records, history };
});
