INSERT INTO currencies (code, number, name, decimals, is_deleted)
VALUES ($1, $2, $3, $4, $5)
RETURNING id;
