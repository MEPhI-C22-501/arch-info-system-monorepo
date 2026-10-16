-- Revisions of the currency are removed by ON DELETE CASCADE.
DELETE FROM currencies
WHERE id = $1;
