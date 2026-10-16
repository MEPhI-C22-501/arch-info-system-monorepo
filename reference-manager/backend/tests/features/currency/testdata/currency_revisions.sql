-- USD has been created, renamed and its precision changed by two users, RUR has been created and soft-deleted.
INSERT INTO currencies (code, number, name, decimals, is_deleted) VALUES
    ('USD', '840', 'United States Dollar', 3, FALSE),
    ('RUR', '810', 'Russian Ruble', 2, TRUE);

INSERT INTO currency_revisions (currency_id, revision_number, change, changed_by, changed_at) VALUES
    (1, 1, '[{"op": "add", "path": "/code", "value": "USD"}, {"op": "add", "path": "/name", "value": "US Dollar"}]', '3fa85f64-5717-4562-b3fc-2c963f66afa6', '2026-10-01 10:00:00+00'),
    (1, 2, '[{"op": "replace", "path": "/name", "value": "United States Dollar"}]', '9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c', '2026-10-02 10:00:00+00'),
    (1, 3, '[{"op": "replace", "path": "/decimals", "value": 3}]', '3fa85f64-5717-4562-b3fc-2c963f66afa6', '2026-10-03 10:00:00+00'),
    (2, 1, '[{"op": "add", "path": "/code", "value": "RUR"}]', '3fa85f64-5717-4562-b3fc-2c963f66afa6', '2026-10-04 10:00:00+00'),
    (2, 2, '[{"op": "replace", "path": "/is_deleted", "value": true}]', '3fa85f64-5717-4562-b3fc-2c963f66afa6', '2026-10-05 10:00:00+00');
