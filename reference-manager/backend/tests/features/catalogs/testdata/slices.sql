-- records with their whole history at fixed moments, the revisions hold the same flat JSON Patch the service writes:
-- one "add" per field on creation, one "replace" per changed field later, dates as RFC 3339 timestamps

-- a position created, renamed and deleted, and one created between the rename and the deletion
INSERT INTO positions (code, name, is_deleted) VALUES ('qa', 'QA engineer', TRUE);
INSERT INTO positions (code, name) VALUES ('analyst', 'Analyst');
INSERT INTO position_revisions (position_id, revision_number, change, changed_by, changed_at)
VALUES (1, 1, '[{"op": "add", "path": "/code", "value": "qa"}, {"op": "add", "path": "/name", "value": "Tester"}, {"op": "add", "path": "/is_deleted", "value": false}]',
        '3fa85f64-5717-4562-b3fc-2c963f66afa6', '2026-09-01 09:00:00+00'),
       (1, 2, '[{"op": "replace", "path": "/name", "value": "QA engineer"}]',
        'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-09-15 09:00:00+00'),
       (1, 3, '[{"op": "replace", "path": "/is_deleted", "value": true}]',
        'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-10-01 09:00:00+00'),
       (2, 1, '[{"op": "add", "path": "/code", "value": "analyst"}, {"op": "add", "path": "/name", "value": "Analyst"}, {"op": "add", "path": "/is_deleted", "value": false}]',
        '3fa85f64-5717-4562-b3fc-2c963f66afa6', '2026-09-20 09:00:00+00');

-- a currency renamed after its creation
INSERT INTO currencies (code, number, name, decimals) VALUES ('RUB', '643', 'Russian ruble', 2);
INSERT INTO currency_revisions (currency_id, revision_number, change, changed_by, changed_at)
VALUES (1, 1, '[{"op": "add", "path": "/code", "value": "RUB"}, {"op": "add", "path": "/number", "value": "643"}, {"op": "add", "path": "/name", "value": "Rouble"}, {"op": "add", "path": "/decimals", "value": 2}, {"op": "add", "path": "/is_deleted", "value": false}]',
        '3fa85f64-5717-4562-b3fc-2c963f66afa6', '2026-09-01 09:00:00+00'),
       (1, 2, '[{"op": "replace", "path": "/name", "value": "Russian ruble"}]',
        '3fa85f64-5717-4562-b3fc-2c963f66afa6', '2026-09-15 09:00:00+00');

-- a salary of an employee closed after a month, its dates are stored in the revisions as the service writes them
INSERT INTO employees (personnel_number, family_name, given_name, email, username, hire_date)
VALUES ('1001', 'Ivanov', 'Ivan', 'i.ivanov@example.org', 'i.ivanov', '2026-01-12');
INSERT INTO employee_revisions (employee_id, revision_number, change, changed_by, changed_at)
VALUES (1, 1, '[{"op": "add", "path": "/personnel_number", "value": "1001"}]', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-09-01 09:00:00+00');
INSERT INTO salaries (employee_id, amount, currency_id, start_date, end_date) VALUES (1, 150000.00, 1, '2026-01-12', '2026-06-30');
INSERT INTO salary_revisions (salary_id, revision_number, change, changed_by, changed_at)
VALUES (1, 1, '[{"op": "add", "path": "/employee_id", "value": 1}, {"op": "add", "path": "/amount", "value": 150000}, {"op": "add", "path": "/currency_id", "value": 1}, {"op": "add", "path": "/start_date", "value": "2026-01-12T00:00:00Z"}, {"op": "add", "path": "/end_date", "value": null}, {"op": "add", "path": "/is_deleted", "value": false}]',
        'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-09-01 09:00:00+00'),
       (1, 2, '[{"op": "replace", "path": "/end_date", "value": "2026-06-30T00:00:00Z"}]',
        'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-10-01 09:00:00+00');
