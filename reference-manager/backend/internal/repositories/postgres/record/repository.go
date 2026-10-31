// Package recordrepo stores the records, the expanded records and the revisions of any catalog described
// by a record.Descriptor. The SQL is built once from the descriptor, so client input never reaches the query text.
package recordrepo

import (
	"context"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"
	"uuid"

	"github.com/jackc/pgx/v5"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	postgresrepo "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/repositories/postgres"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/aipsql"
)

// exclusionViolationCode is the SQLSTATE of a violated EXCLUDE constraint, dated catalogs use it against overlapping periods.
const exclusionViolationCode = "23P01"

// checkViolationCode is the SQLSTATE of a violated CHECK constraint.
const checkViolationCode = "23514"

// lifecycleColumns are the columns every expanded view ends with, in the order they are scanned.
var lifecycleColumns = []string{"is_deleted", "revision", "last_changer", "created_at", "updated_at", "deleted_at"}

// Repository stores the records of one catalog and reads them back expanded with their lifecycle.
type Repository[F any] struct {
	db   postgresrepo.DB
	desc *record.Descriptor[F]

	stored  []record.Column[F]
	columns aipsql.Columns

	insertQuery string
	updateQuery string
	deleteQuery string
	selectQuery string
}

func NewRepository[F any](db postgresrepo.DB, desc *record.Descriptor[F]) *Repository[F] {
	stored := desc.StoredColumns()

	names := make([]string, 0, len(stored))
	placeholders := make([]string, 0, len(stored)+1)
	assignments := make([]string, 0, len(stored)+1)
	for i, c := range stored {
		names = append(names, c.Name)
		placeholders = append(placeholders, "$"+strconv.Itoa(i+1))
		assignments = append(assignments, c.Name+" = $"+strconv.Itoa(i+2))
	}
	placeholders = append(placeholders, "$"+strconv.Itoa(len(stored)+1))
	assignments = append(assignments, "is_deleted = $"+strconv.Itoa(len(stored)+2))

	selected := []string{"id"}
	columns := aipsql.Columns{
		"is_deleted":   "is_deleted",
		"revision":     "revision",
		"last_changer": "last_changer::text",
		"created_at":   "created_at",
		"updated_at":   "updated_at",
		"deleted_at":   "deleted_at",
	}
	for _, c := range desc.Columns {
		selected = append(selected, c.Name)

		sql := c.SQL
		if sql == "" {
			sql = c.Name
		}
		columns[c.Name] = sql
	}
	selected = append(selected, lifecycleColumns...)

	return &Repository[F]{
		db:      db,
		desc:    desc,
		stored:  stored,
		columns: columns,
		insertQuery: "INSERT INTO " + desc.Table + " (" + strings.Join(names, ", ") + ", is_deleted)\n" +
			"VALUES (" + strings.Join(placeholders, ", ") + ")\nRETURNING id",
		updateQuery: "UPDATE " + desc.Table + "\nSET " + strings.Join(assignments, ", ") + "\nWHERE id = $1",
		deleteQuery: "DELETE FROM " + desc.Table + "\nWHERE id = $1",
		selectQuery: "SELECT " + strings.Join(selected, ", ") + "\nFROM " + desc.View,
	}
}

// Columns are the fields of the list that can be filtered and sorted.
func (r *Repository[F]) Columns() aipsql.Columns {
	return r.columns
}

func (r *Repository[F]) Create(ctx context.Context, m *record.Record[F]) (int64, error) {
	var id int64

	err := r.db.Querier(ctx).QueryRow(ctx, r.insertQuery, r.writeArgs(m)...).Scan(&id)
	if err != nil {
		return 0, r.writeError("insert", err)
	}

	return id, nil
}

func (r *Repository[F]) Update(ctx context.Context, m *record.Record[F]) error {
	tag, err := r.db.Querier(ctx).Exec(ctx, r.updateQuery, append([]any{m.ID}, r.writeArgs(m)...)...)
	if err != nil {
		return r.writeError("update", err)
	}

	if tag.RowsAffected() == 0 {
		return domains.ErrNotFound
	}

	return nil
}

// Delete removes a record permanently, its revisions go with it by ON DELETE CASCADE.
func (r *Repository[F]) Delete(ctx context.Context, id int64) error {
	tag, err := r.db.Querier(ctx).Exec(ctx, r.deleteQuery, id)
	if err != nil {
		// records of other catalogs refer to this one, they have to go first (FR-RM-11)
		if postgresrepo.HasErrorCode(err, postgresrepo.ForeignKeyViolationCode) {
			return fmt.Errorf("%s %d is referenced by records of other catalogs: %w", r.desc.Singular, id, domains.ErrFailedPrecondition)
		}

		return fmt.Errorf("delete %s: %w", r.desc.Singular, err)
	}

	if tag.RowsAffected() == 0 {
		return domains.ErrNotFound
	}

	return nil
}

func (r *Repository[F]) GetExpanded(ctx context.Context, id int64) (*record.Expanded[F], error) {
	m, err := r.scan(r.db.Querier(ctx).QueryRow(ctx, r.selectQuery+"\nWHERE id = $1", id))
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, domains.ErrNotFound
		}

		return nil, fmt.Errorf("select expanded %s: %w", r.desc.Singular, err)
	}

	return m, nil
}

func (r *Repository[F]) ListExpanded(ctx context.Context, q *record.ListQuery) ([]*record.Expanded[F], error) {
	query, args, err := r.buildListQuery(q)
	if err != nil {
		return nil, err
	}

	rows, err := r.db.Querier(ctx).Query(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("select expanded %s: %w", r.desc.Plural, err)
	}
	defer rows.Close()

	records := make([]*record.Expanded[F], 0, q.Limit)
	for rows.Next() {
		m, err := r.scan(rows)
		if err != nil {
			return nil, fmt.Errorf("scan expanded %s: %w", r.desc.Singular, err)
		}

		records = append(records, m)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("select expanded %s: %w", r.desc.Plural, err)
	}

	return records, nil
}

func (r *Repository[F]) buildListQuery(q *record.ListQuery) (string, []any, error) {
	var (
		args       aipsql.Args
		conditions []string
	)

	if !q.AllowDeleted {
		conditions = append(conditions, "is_deleted = FALSE")
	}

	filter, err := aipsql.TranspileFilter(q.Filter, r.columns, &args)
	if err != nil {
		return "", nil, &domains.InvalidArgumentError{Argument: "filter", Err: err}
	}
	if filter != "" {
		conditions = append(conditions, filter)
	}

	orderBy, err := aipsql.TranspileOrderBy(q.OrderBy, r.columns, "id")
	if err != nil {
		return "", nil, &domains.InvalidArgumentError{Argument: "order_by", Err: err}
	}

	var b strings.Builder
	b.WriteString(r.selectQuery)
	if len(conditions) > 0 {
		b.WriteString("\nWHERE " + strings.Join(conditions, " AND "))
	}
	b.WriteString("\nORDER BY " + orderBy)
	if q.Limit > 0 {
		b.WriteString("\nLIMIT " + args.Add(q.Limit) + " OFFSET " + args.Add(q.Offset))
	}

	return b.String(), args.Values(), nil
}

func (r *Repository[F]) writeArgs(m *record.Record[F]) []any {
	args := make([]any, 0, len(r.stored)+1)
	for _, c := range r.stored {
		args = append(args, c.Value(&m.Fields))
	}

	return append(args, m.IsDeleted)
}

func (r *Repository[F]) scan(row pgx.Row) (*record.Expanded[F], error) {
	var (
		m = &record.Expanded[F]{}

		// lifecycle columns are derived from revisions and are NULL when a record has none
		revision    *int32
		lastChanger *uuid.UUID
		createdAt   *time.Time
		updatedAt   *time.Time
		deletedAt   *time.Time
	)

	targets := make([]any, 0, len(r.desc.Columns)+7)
	targets = append(targets, &m.ID)
	for _, c := range r.desc.Columns {
		targets = append(targets, c.Ptr(&m.Fields))
	}
	targets = append(targets, &m.IsDeleted, &revision, &lastChanger, &createdAt, &updatedAt, &deletedAt)

	if err := row.Scan(targets...); err != nil {
		return nil, err
	}

	m.Revision = valueOrZero(revision)
	m.LastChanger = valueOrZero(lastChanger)
	m.CreatedAt = valueOrZero(createdAt).UTC()
	m.UpdatedAt = valueOrZero(updatedAt).UTC()
	m.DeletedAt = valueOrZero(deletedAt).UTC()

	return m, nil
}

// writeError maps the constraint violations of the storage to domain errors, the client sees a field-level message
// only for the rules the service has not checked itself.
func (r *Repository[F]) writeError(operation string, err error) error {
	switch {
	case postgresrepo.HasErrorCode(err, postgresrepo.UniqueViolationCode):
		return domains.ErrAlreadyExists
	case postgresrepo.HasErrorCode(err, postgresrepo.ForeignKeyViolationCode):
		return &domains.InvalidArgumentError{Argument: r.desc.Singular, Err: errors.New("referenced record does not exist")}
	case postgresrepo.HasErrorCode(err, exclusionViolationCode):
		return &domains.InvalidArgumentError{Argument: "start_date, end_date", Err: errors.New("period overlaps another record of the employee")}
	case postgresrepo.HasErrorCode(err, checkViolationCode):
		return &domains.InvalidArgumentError{Argument: r.desc.Singular, Err: errors.New("values violate a constraint of the record")}
	}

	return fmt.Errorf("%s %s: %w", operation, r.desc.Singular, err)
}

func valueOrZero[T any](v *T) T {
	if v == nil {
		var zero T
		return zero
	}

	return *v
}
