-- the second unit of hr.sql gets more people: employee 1 of employee_in_effect.sql works in unit 2 with a salary,
-- employee 2 works in unit 1 with a salary that started on 2025-03-01, employee 3 works in unit 2 without a salary,
-- employee 4 was dismissed and has no assignment in effect any more
INSERT INTO employees (personnel_number, family_name, given_name, email, username, hire_date)
VALUES ('1002', 'Petrova', 'Maria', 'm.petrova@example.org', 'm.petrova', '2025-03-01'),
       ('1003', 'Sidorov', 'Alexey', 'a.sidorov@example.org', 'a.sidorov', '2026-02-01');
INSERT INTO employees (personnel_number, family_name, given_name, email, username, hire_date, employment_state, dismissal_date)
VALUES ('1004', 'Kuznetsova', 'Anna', 'a.kuznetsova@example.org', 'a.kuznetsova', '2024-05-01', 'DISMISSED', '2026-06-30');
INSERT INTO employee_revisions (employee_id, revision_number, change, changed_by, changed_at)
VALUES (2, 1, '[{"op": "add", "path": "/personnel_number", "value": "1002"}]', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-10-01 10:00:00+00'),
       (3, 1, '[{"op": "add", "path": "/personnel_number", "value": "1003"}]', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-10-01 10:00:00+00'),
       (4, 1, '[{"op": "add", "path": "/personnel_number", "value": "1004"}]', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-10-01 10:00:00+00');

INSERT INTO assignments (employee_id, org_unit_id, position_id, start_date, end_date)
VALUES (2, 1, 1, '2025-03-01', NULL),
       (3, 2, 1, '2026-02-01', NULL),
       (4, 2, 1, '2024-05-01', '2026-06-30');
INSERT INTO assignment_revisions (assignment_id, revision_number, change, changed_by, changed_at)
VALUES (2, 1, '[{"op": "add", "path": "/employee_id", "value": 2}]', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-10-01 10:00:00+00'),
       (3, 1, '[{"op": "add", "path": "/employee_id", "value": 3}]', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-10-01 10:00:00+00'),
       (4, 1, '[{"op": "add", "path": "/employee_id", "value": 4}]', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-10-01 10:00:00+00');

INSERT INTO salaries (employee_id, amount, currency_id, start_date, end_date) VALUES (2, 98765.43, 1, '2025-03-01', NULL);
INSERT INTO salary_revisions (salary_id, revision_number, change, changed_by, changed_at)
VALUES (2, 1, '[{"op": "add", "path": "/employee_id", "value": 2}]', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-10-01 10:00:00+00');
