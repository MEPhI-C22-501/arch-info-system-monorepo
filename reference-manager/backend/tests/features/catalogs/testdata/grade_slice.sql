-- a grade set on the assignment of employee 1 on 2026-11-10, with full revisions as the service writes them:
-- a slice before that day has the assignment without a grade, a slice after it has the grade (FR-RM-61, FR-RM-69)
INSERT INTO grades (code, name, rank) VALUES ('lead', 'Lead', 4);
INSERT INTO grade_revisions (grade_id, revision_number, change, changed_by, changed_at)
VALUES (1, 1, '[{"op": "add", "path": "/code", "value": "lead"}, {"op": "add", "path": "/name", "value": "Lead"}, {"op": "add", "path": "/rank", "value": 4}, {"op": "add", "path": "/is_deleted", "value": false}]', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-10-01 10:00:00+00');

UPDATE assignment_revisions
SET change = '[{"op": "add", "path": "/employee_id", "value": 1}, {"op": "add", "path": "/org_unit_id", "value": 2}, {"op": "add", "path": "/position_id", "value": 1}, {"op": "add", "path": "/grade_id", "value": null}, {"op": "add", "path": "/start_date", "value": "2024-01-15T00:00:00Z"}, {"op": "add", "path": "/end_date", "value": null}, {"op": "add", "path": "/is_deleted", "value": false}]'
WHERE assignment_id = 1 AND revision_number = 1;

UPDATE assignments SET grade_id = 1 WHERE id = 1;
INSERT INTO assignment_revisions (assignment_id, revision_number, change, changed_by, changed_at)
VALUES (1, 2, '[{"op": "replace", "path": "/grade_id", "value": 1}]', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', '2026-11-10 10:00:00+00');
