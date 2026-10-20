INSERT INTO assignments (employee_id, org_unit_id, position_id, start_date, end_date) VALUES (1, 2, 1, '2024-01-15', NULL);
INSERT INTO assignment_revisions (assignment_id, revision_number, change, changed_by, changed_at)
VALUES (1, 1, '[{"op": "add", "path": "/employee_id", "value": 1}]', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-10-01 10:00:00+00');

INSERT INTO salaries (employee_id, amount, currency_id, start_date, end_date) VALUES (1, 150000.00, 1, '2024-01-15', NULL);
INSERT INTO salary_revisions (salary_id, revision_number, change, changed_by, changed_at)
VALUES (1, 1, '[{"op": "add", "path": "/employee_id", "value": 1}]', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-10-01 10:00:00+00');
