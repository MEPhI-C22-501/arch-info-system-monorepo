package record

import "github.com/jackc/pgx/v5"

// pgxNoRows is the error of a row scan without rows, aliased so the validation code does not import pgx twice.
var pgxNoRows = pgx.ErrNoRows
