UPDATE currencies
SET code = $2, number = $3, name = $4, decimals = $5, is_deleted = $6
WHERE id = $1;
