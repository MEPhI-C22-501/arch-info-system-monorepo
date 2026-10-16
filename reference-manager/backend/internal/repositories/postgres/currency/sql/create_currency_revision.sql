-- changed_at is omitted so that the database default (now()) is used.
INSERT INTO currency_revisions (currency_id, revision_number, change, changed_by)
VALUES ($1, $2, $3, $4);
