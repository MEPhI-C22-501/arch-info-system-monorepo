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

//go:embed sql/update_currency.sql
var updateCurrencyQuery string

func (r *CurrencyRepository) UpdateCurrency(ctx context.Context, m *currencydmn.Currency) error {
	tag, err := r.db.Querier(ctx).
		Exec(ctx, updateCurrencyQuery, m.ID, m.Code, m.Number, m.Name, m.Decimals, m.IsDeleted)
	if err != nil {
		if postgresrepo.HasErrorCode(err, postgresrepo.UniqueViolationCode) {
			return domains.ErrAlreadyExists
		}

		return fmt.Errorf("update currency: %w", err)
	}

	if tag.RowsAffected() == 0 {
		return domains.ErrNotFound
	}

	return nil
}

//go:embed sql/delete_currency.sql
var deleteCurrencyQuery string

func (r *CurrencyRepository) DeleteCurrency(ctx context.Context, currencyID int64) error {
	tag, err := r.db.Querier(ctx).Exec(ctx, deleteCurrencyQuery, currencyID)
	if err != nil {
		return fmt.Errorf("delete currency: %w", err)
	}

	if tag.RowsAffected() == 0 {
		return domains.ErrNotFound
	}

	return nil
}
