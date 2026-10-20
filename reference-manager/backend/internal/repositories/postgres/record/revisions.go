package recordrepo

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/jackc/pgx/v5"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	postgresrepo "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/repositories/postgres"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/aipsql"
)

// revisionColumns are the fields of a revision list that can be filtered and sorted.
var revisionColumns = aipsql.Columns{
	"revision_number": "revision_number",
	"changed_by":      "changed_by::text",
	"changed_at":      "changed_at",
}

// RevisionRepository stores the revisions of one catalog.
type RevisionRepository struct {
	db postgresrepo.DB

	singular    string
	insertQuery string
	selectQuery string
	column      string
}

// NewRevisionRepository builds the repository for the revision table of a catalog, column is the record reference.
func NewRevisionRepository(db postgresrepo.DB, singular, table, column string) *RevisionRepository {
	return &RevisionRepository{
		db:       db,
		singular: singular,
		column:   column,
		// changed_at is omitted so that the database default (now()) is used
		insertQuery: "INSERT INTO " + table + " (" + column + ", revision_number, change, changed_by)\nVALUES ($1, $2, $3, $4)",
		selectQuery: "SELECT id, " + column + ", revision_number, change, changed_by, changed_at\nFROM " + table,
	}
}

func (r *RevisionRepository) CreateRevision(ctx context.Context, m *record.Revision) error {
	_, err := r.db.Querier(ctx).Exec(ctx, r.insertQuery, m.RecordID, m.RevisionNumber, string(m.Change), m.ChangedBy)
	if err != nil {
		switch {
		case postgresrepo.HasErrorCode(err, postgresrepo.UniqueViolationCode):
			return domains.ErrAlreadyExists
		case postgresrepo.HasErrorCode(err, postgresrepo.ForeignKeyViolationCode):
			return domains.ErrNotFound
		}

		return fmt.Errorf("insert %s revision: %w", r.singular, err)
	}

	return nil
}

func (r *RevisionRepository) GetRevision(ctx context.Context, recordID int64, revisionNumber int32) (*record.Revision, error) {
	row := r.db.Querier(ctx).QueryRow(ctx, r.selectQuery+"\nWHERE "+r.column+" = $1 AND revision_number = $2", recordID, revisionNumber)

	m, err := scanRevision(row)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, domains.ErrNotFound
		}

		return nil, fmt.Errorf("select %s revision: %w", r.singular, err)
	}

	return m, nil
}

func (r *RevisionRepository) ListRevisions(ctx context.Context, q *record.RevisionListQuery) ([]*record.Revision, error) {
	query, args, err := r.buildListQuery(q)
	if err != nil {
		return nil, err
	}

	rows, err := r.db.Querier(ctx).Query(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("select %s revisions: %w", r.singular, err)
	}
	defer rows.Close()

	revisions := make([]*record.Revision, 0, q.Limit)
	for rows.Next() {
		m, err := scanRevision(rows)
		if err != nil {
			return nil, fmt.Errorf("scan %s revision: %w", r.singular, err)
		}

		revisions = append(revisions, m)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("select %s revisions: %w", r.singular, err)
	}

	return revisions, nil
}

func (r *RevisionRepository) buildListQuery(q *record.RevisionListQuery) (string, []any, error) {
	var args aipsql.Args

	conditions := []string{r.column + " = " + args.Add(q.RecordID)}

	filter, err := aipsql.TranspileFilter(q.Filter, revisionColumns, &args)
	if err != nil {
		return "", nil, &domains.InvalidArgumentError{Argument: "filter", Err: err}
	}
	if filter != "" {
		conditions = append(conditions, filter)
	}

	orderBy, err := aipsql.TranspileOrderBy(q.OrderBy, revisionColumns, "revision_number")
	if err != nil {
		return "", nil, &domains.InvalidArgumentError{Argument: "order_by", Err: err}
	}

	var b strings.Builder
	b.WriteString(r.selectQuery)
	b.WriteString("\nWHERE " + strings.Join(conditions, " AND "))
	b.WriteString("\nORDER BY " + orderBy)
	b.WriteString("\nLIMIT " + args.Add(q.Limit) + " OFFSET " + args.Add(q.Offset))

	return b.String(), args.Values(), nil
}

func scanRevision(row pgx.Row) (*record.Revision, error) {
	m := &record.Revision{}

	if err := row.Scan(&m.ID, &m.RecordID, &m.RevisionNumber, &m.Change, &m.ChangedBy, &m.ChangedAt); err != nil {
		return nil, err
	}

	m.ChangedAt = m.ChangedAt.UTC()

	return m, nil
}
