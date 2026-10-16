package currencyrepo

import (
	"context"
	_ "embed"
	"errors"
	"fmt"
	"time"
	"uuid"

	"github.com/jackc/pgx/v5"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	postgresrepo "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/repositories/postgres"
)

type ExpandedCurrencyRepository struct {
	db postgresrepo.DB
}

func NewExpandedCurrencyRepository(db postgresrepo.DB) *ExpandedCurrencyRepository {
	return &ExpandedCurrencyRepository{
		db: db,
	}
}

//go:embed sql/get_expanded_currency.sql
var getExpandedCurrencyQuery string

func (r *ExpandedCurrencyRepository) GetExpandedCurrency(ctx context.Context, currencyID int64) (*currencydmn.ExpandedCurrency, error) {
	var (
		m = &currencydmn.ExpandedCurrency{}

		// Lifecycle columns are derived from revisions and are NULL when a currency has none.
		revision    *int32
		lastChanger *uuid.UUID
		createdAt   *time.Time
		updatedAt   *time.Time
		deletedAt   *time.Time
	)

	err := r.db.Querier(ctx).
		QueryRow(ctx, getExpandedCurrencyQuery, currencyID).
		Scan(
			&m.ID, &m.Code, &m.Number, &m.Name, &m.Decimals, &m.IsDeleted,
			&revision, &lastChanger, &createdAt, &updatedAt, &deletedAt,
		)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, domains.ErrNotFound
		}

		return nil, fmt.Errorf("select expanded currency: %w", err)
	}

	m.Revision = valueOrZero(revision)
	m.LastChanger = valueOrZero(lastChanger)
	m.CreatedAt = valueOrZero(createdAt).UTC()
	m.UpdatedAt = valueOrZero(updatedAt).UTC()
	m.DeletedAt = valueOrZero(deletedAt).UTC()

	return m, nil
}

func valueOrZero[T any](v *T) T {
	if v == nil {
		var zero T
		return zero
	}

	return *v
}
