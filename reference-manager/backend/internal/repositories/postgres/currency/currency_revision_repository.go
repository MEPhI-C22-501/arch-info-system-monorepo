package currencyrepo

import (
	"context"
	_ "embed"
	"fmt"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	postgresrepo "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/repositories/postgres"
)

type CurrencyRevisionRepository struct {
	db postgresrepo.DB
}

func NewCurrencyRevisionRepository(db postgresrepo.DB) *CurrencyRevisionRepository {
	return &CurrencyRevisionRepository{
		db: db,
	}
}

//go:embed sql/create_currency_revision.sql
var createCurrencyRevisionQuery string

func (r *CurrencyRevisionRepository) CreateCurrencyRevision(ctx context.Context, m *currencydmn.CurrencyRevision) error {
	_, err := r.db.Querier(ctx).
		Exec(ctx, createCurrencyRevisionQuery, m.CurrencyID, m.RevisionNumber, string(m.Change), m.ChangedBy)
	if err != nil {
		switch {
		case postgresrepo.HasErrorCode(err, postgresrepo.UniqueViolationCode):
			return domains.ErrAlreadyExists
		case postgresrepo.HasErrorCode(err, postgresrepo.ForeignKeyViolationCode):
			return domains.ErrNotFound
		}

		return fmt.Errorf("insert currency revision: %w", err)
	}

	return nil
}
