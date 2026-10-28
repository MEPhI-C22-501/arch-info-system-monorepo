package postgresrepo

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5/pgconn"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
)

const (
	UniqueViolationCode     = "23505"
	ForeignKeyViolationCode = "23503"
)

//go:generate go tool mockgen -source=db.go -destination=mocks/db.go -package=mocks
type DB interface {
	Querier(ctx context.Context) postgres.Querier
}

func HasErrorCode(err error, code string) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && pgErr.Code == code
}
