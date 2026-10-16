package currencyrepo

import (
	"context"
	_ "embed"
	"fmt"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	postgresrepo "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/repositories/postgres"
)

type CurrencyRepository struct {
	db postgresrepo.DB
}

func NewCurrencyRepository(db postgresrepo.DB) *CurrencyRepository {
	return &CurrencyRepository{
		db: db,
	}
}

//go:embed sql/create_currency.sql
var createCurrencyQuery string

func (r *CurrencyRepository) CreateCurrency(ctx context.Context, m *currencydmn.Currency) (int64, error) {
	var id int64

	err := r.db.Querier(ctx).
		QueryRow(ctx, createCurrencyQuery, m.Code, m.Number, m.Name, m.Decimals, m.IsDeleted).
		Scan(&id)
	if err != nil {
		if postgresrepo.HasErrorCode(err, postgresrepo.UniqueViolationCode) {
			return 0, domains.ErrAlreadyExists
		}

		return 0, fmt.Errorf("insert currency: %w", err)
	}

	return id, nil
}
