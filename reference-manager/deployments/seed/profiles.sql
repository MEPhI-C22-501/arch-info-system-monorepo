-- Local realm subjects are pinned in its checked-in import. No name or email matching.
INSERT INTO user_profiles (issuer, subject, display_name, work_email)
VALUES
    ('http://localhost:8183/realms/arch-info-system', '3fa85f64-5717-4562-b3fc-2c963f66afa6', 'Reference Admin', 'admin@reference-manager.local'),
    ('http://localhost:8183/realms/arch-info-system', '9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c', 'Second Admin', 'second-admin@reference-manager.local'),
    ('http://localhost:8183/realms/arch-info-system', 'c5a7e2d0-3b4f-4a19-8e6d-2f1b0c9d8e7a', 'Reference Reader', 'reader@reference-manager.local'),
    ('http://localhost:8183/realms/arch-info-system', 'd81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d', 'HR Admin', 'hr-admin@reference-manager.local'),
    ('http://localhost:8183/realms/arch-info-system', 'e2b9c8a7-6d5f-4e3a-9b1c-0f8e7d6c5b4a', 'HR Reader', 'hr-reader@reference-manager.local'),
    -- an account without roles of the service still reads its own profile (ADR-024)
    ('http://localhost:8183/realms/arch-info-system', 'f7a6b5c4-d3e2-4f1a-8b9c-1d2e3f4a5b6c', 'No Roles User', 'outsider@reference-manager.local')
ON CONFLICT DO NOTHING;
