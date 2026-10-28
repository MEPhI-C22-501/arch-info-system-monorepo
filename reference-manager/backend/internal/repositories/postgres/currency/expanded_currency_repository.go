package currencyrepo

import (
	"context"
	_ "embed"
	"errors"
	"fmt"
	"strings"
	"time"
	"uuid"

	"github.com/jackc/pgx/v5"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	postgresrepo "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/repositories/postgres"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/aipsql"
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
	m, err := scanExpandedCurrency(r.db.Querier(ctx).QueryRow(ctx, getExpandedCurrencyQuery, currencyID))
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, domains.ErrNotFound
		}

		return nil, fmt.Errorf("select expanded currency: %w", err)
	}

	return m, nil
}

//go:embed sql/list_expanded_currencies.sql
var listExpandedCurrenciesQuery string

// expandedCurrencyColumns are the fields of the currency list that can be filtered and sorted.
var expandedCurrencyColumns = aipsql.Columns{
	"code":         "code",
	"number":       "number",
	"name":         "name",
	"decimals":     "decimals",
	"is_deleted":   "is_deleted",
	"revision":     "revision",
	"last_changer": "last_changer::text",
	"created_at":   "created_at",
	"updated_at":   "updated_at",
	"deleted_at":   "deleted_at",
}

func (r *ExpandedCurrencyRepository) ListExpandedCurrencies(
	ctx context.Context,
	q *currencydmn.ListQuery,
) ([]*currencydmn.ExpandedCurrency, error) {
	query, args, err := buildListExpandedCurrenciesQuery(q)
	if err != nil {
		return nil, err
	}

	rows, err := r.db.Querier(ctx).Query(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("select expanded currencies: %w", err)
	}
	defer rows.Close()

	currencies := make([]*currencydmn.ExpandedCurrency, 0, q.Limit)
	for rows.Next() {
		m, err := scanExpandedCurrency(rows)
		if err != nil {
			return nil, fmt.Errorf("scan expanded currency: %w", err)
		}

		currencies = append(currencies, m)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("select expanded currencies: %w", err)
	}

	return currencies, nil
}

func buildListExpandedCurrenciesQuery(q *currencydmn.ListQuery) (string, []any, error) {
	var (
		args       aipsql.Args
		conditions []string
	)

	if !q.AllowDeleted {
		conditions = append(conditions, "is_deleted = FALSE")
	}

	filter, err := aipsql.TranspileFilter(q.Filter, expandedCurrencyColumns, &args)
	if err != nil {
		return "", nil, &domains.InvalidArgumentError{Argument: "filter", Err: err}
	}
	if filter != "" {
		conditions = append(conditions, filter)
	}

	orderBy, err := aipsql.TranspileOrderBy(q.OrderBy, expandedCurrencyColumns, "id")
	if err != nil {
		return "", nil, &domains.InvalidArgumentError{Argument: "order_by", Err: err}
	}

	var b strings.Builder
	b.WriteString(strings.TrimSpace(listExpandedCurrenciesQuery))
	if len(conditions) > 0 {
		b.WriteString("\nWHERE " + strings.Join(conditions, " AND "))
	}
	b.WriteString("\nORDER BY " + orderBy)
	if q.Limit > 0 {
		b.WriteString("\nLIMIT " + args.Add(q.Limit) + " OFFSET " + args.Add(q.Offset))
	}

	return b.String(), args.Values(), nil
}

func scanExpandedCurrency(row pgx.Row) (*currencydmn.ExpandedCurrency, error) {
	var (
		m = &currencydmn.ExpandedCurrency{}

		// Lifecycle columns are derived from revisions and are NULL when a currency has none.
		revision    *int32
		lastChanger *uuid.UUID
		createdAt   *time.Time
		updatedAt   *time.Time
		deletedAt   *time.Time
	)

	err := row.Scan(
		&m.ID, &m.Code, &m.Number, &m.Name, &m.Decimals, &m.IsDeleted,
		&revision, &lastChanger, &createdAt, &updatedAt, &deletedAt,
	)
	if err != nil {
		return nil, err
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
