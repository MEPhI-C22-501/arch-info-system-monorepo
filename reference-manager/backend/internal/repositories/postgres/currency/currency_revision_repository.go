package currencyrepo

import (
	"context"
	_ "embed"
	"errors"
	"fmt"
	"strings"

	"github.com/jackc/pgx/v5"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	postgresrepo "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/repositories/postgres"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/aipsql"
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

//go:embed sql/get_currency_revision.sql
var getCurrencyRevisionQuery string

func (r *CurrencyRevisionRepository) GetCurrencyRevision(
	ctx context.Context,
	currencyID int64,
	revisionNumber int32,
) (*currencydmn.CurrencyRevision, error) {
	m, err := scanCurrencyRevision(r.db.Querier(ctx).QueryRow(ctx, getCurrencyRevisionQuery, currencyID, revisionNumber))
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, domains.ErrNotFound
		}

		return nil, fmt.Errorf("select currency revision: %w", err)
	}

	return m, nil
}

//go:embed sql/list_currency_revisions.sql
var listCurrencyRevisionsQuery string

// currencyRevisionColumns are the fields of the revision list that can be filtered and sorted.
var currencyRevisionColumns = aipsql.Columns{
	"revision_number": "revision_number",
	"changed_by":      "changed_by::text",
	"changed_at":      "changed_at",
}

func (r *CurrencyRevisionRepository) ListCurrencyRevisions(
	ctx context.Context,
	q *currencydmn.RevisionListQuery,
) ([]*currencydmn.CurrencyRevision, error) {
	query, args, err := buildListCurrencyRevisionsQuery(q)
	if err != nil {
		return nil, err
	}

	rows, err := r.db.Querier(ctx).Query(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("select currency revisions: %w", err)
	}
	defer rows.Close()

	revisions := make([]*currencydmn.CurrencyRevision, 0, q.Limit)
	for rows.Next() {
		m, err := scanCurrencyRevision(rows)
		if err != nil {
			return nil, fmt.Errorf("scan currency revision: %w", err)
		}

		revisions = append(revisions, m)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("select currency revisions: %w", err)
	}

	return revisions, nil
}

func buildListCurrencyRevisionsQuery(q *currencydmn.RevisionListQuery) (string, []any, error) {
	var args aipsql.Args

	conditions := []string{"currency_id = " + args.Add(q.CurrencyID)}

	filter, err := aipsql.TranspileFilter(q.Filter, currencyRevisionColumns, &args)
	if err != nil {
		return "", nil, &domains.InvalidArgumentError{Argument: "filter", Err: err}
	}
	if filter != "" {
		conditions = append(conditions, filter)
	}

	orderBy, err := aipsql.TranspileOrderBy(q.OrderBy, currencyRevisionColumns, "revision_number")
	if err != nil {
		return "", nil, &domains.InvalidArgumentError{Argument: "order_by", Err: err}
	}

	var b strings.Builder
	b.WriteString(strings.TrimSpace(listCurrencyRevisionsQuery))
	b.WriteString("\nWHERE " + strings.Join(conditions, " AND "))
	b.WriteString("\nORDER BY " + orderBy)
	b.WriteString("\nLIMIT " + args.Add(q.Limit) + " OFFSET " + args.Add(q.Offset))

	return b.String(), args.Values(), nil
}

func scanCurrencyRevision(row pgx.Row) (*currencydmn.CurrencyRevision, error) {
	m := &currencydmn.CurrencyRevision{}

	err := row.Scan(&m.ID, &m.CurrencyID, &m.RevisionNumber, &m.Change, &m.ChangedBy, &m.ChangedAt)
	if err != nil {
		return nil, err
	}

	m.ChangedAt = m.ChangedAt.UTC()

	return m, nil
}
