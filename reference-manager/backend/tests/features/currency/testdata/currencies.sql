-- Six currencies created one per day, RUR has been soft-deleted by a second revision.
INSERT INTO currencies (code, number, name, decimals, is_deleted) VALUES
    ('USD', '840', 'US Dollar', 2, FALSE),
    ('EUR', '978', 'Euro', 2, FALSE),
    ('JPY', '392', 'Yen', 0, FALSE),
    ('BHD', '048', 'Bahraini Dinar', 3, FALSE),
    ('RUR', '810', 'Russian Ruble', 2, TRUE),
    ('CLF', '990', 'Unidad de Fomento', 4, FALSE);

INSERT INTO currency_revisions (currency_id, revision_number, change, changed_by, changed_at) VALUES
    (1, 1, '[]', '3fa85f64-5717-4562-b3fc-2c963f66afa6', '2026-10-01 10:00:00+00'),
    (2, 1, '[]', '3fa85f64-5717-4562-b3fc-2c963f66afa6', '2026-10-02 10:00:00+00'),
    (3, 1, '[]', '9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c', '2026-10-03 10:00:00+00'),
    (4, 1, '[]', '9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c', '2026-10-04 10:00:00+00'),
    (5, 1, '[]', '3fa85f64-5717-4562-b3fc-2c963f66afa6', '2026-10-05 10:00:00+00'),
    (5, 2, '[{"op": "replace", "path": "/is_deleted", "value": true}]', '3fa85f64-5717-4562-b3fc-2c963f66afa6', '2026-10-06 10:00:00+00'),
    (6, 1, '[]', '3fa85f64-5717-4562-b3fc-2c963f66afa6', '2026-10-07 10:00:00+00');
