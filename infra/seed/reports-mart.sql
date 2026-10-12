-- Идентификаторы демонстрационной витрины Reports. Это не база справочников
-- и не обход provisioning: строки помечают ожидаемые связи до поставки HR API.
CREATE TABLE IF NOT EXISTS demo_link (
    stable_id uuid PRIMARY KEY,
    entity_kind text NOT NULL,
    label text NOT NULL,
    source_note text NOT NULL
);

INSERT INTO demo_link (stable_id, entity_kind, label, source_note) VALUES
    ('10000000-0000-4000-8000-000000000001', 'employee', 'demo-employee', 'fixture; HR API Reference Manager не поставлен'),
    ('10000000-0000-4000-8000-000000000002', 'org-unit', 'demo-org', 'fixture; оргструктура не загружается в чужую БД'),
    ('10000000-0000-4000-8000-000000000003', 'project', 'demo-project', 'fixture витрины Reports'),
    ('10000000-0000-4000-8000-000000000004', 'work-item', 'demo-task', 'fixture; Task Tracker владеет задачей')
ON CONFLICT (stable_id) DO NOTHING;
