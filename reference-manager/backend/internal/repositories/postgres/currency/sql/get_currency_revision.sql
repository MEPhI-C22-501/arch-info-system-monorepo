SELECT id, currency_id, revision_number, change, changed_by, changed_at
FROM currency_revisions
WHERE currency_id = $1 AND revision_number = $2;
