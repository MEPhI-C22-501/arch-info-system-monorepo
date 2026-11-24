package record

import (
	"context"
	"testing"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

// deletedRows answers every reference lookup with a deleted record and counts the lookups.
type deletedRows struct{ lookups int }

func (q *deletedRows) Exec(context.Context, string, ...any) (pgconn.CommandTag, error) {
	return pgconn.CommandTag{}, nil
}

func (q *deletedRows) Query(context.Context, string, ...any) (pgx.Rows, error) { return nil, nil }

func (q *deletedRows) QueryRow(context.Context, string, ...any) pgx.Row {
	q.lookups++
	return deletedRow{}
}

type deletedRow struct{}

func (deletedRow) Scan(dest ...any) error {
	*dest[0].(*bool) = true
	return nil
}

func TestCheckReferencesSkipsAnUnchangedReference(t *testing.T) {
	t.Parallel()

	grade, other := int64(4), int64(5)

	q := &deletedRows{}
	err := CheckReferences(context.Background(), q, Reference{Field: "grade_id", Table: "grades", ID: &grade, Before: &grade})
	if err != nil || q.lookups != 0 {
		t.Errorf("a reference that keeps its value is not looked up again, got %v after %d lookups", err, q.lookups)
	}

	q = &deletedRows{}
	err = CheckReferences(context.Background(), q, Reference{Field: "grade_id", Table: "grades", ID: &grade, Before: &other})
	if err == nil || q.lookups != 1 || err.Error() == "" {
		t.Errorf("a changed reference to a deleted record is rejected, got %v after %d lookups", err, q.lookups)
	}

	q = &deletedRows{}
	err = CheckReferences(context.Background(), q, Reference{Field: "grade_id", Table: "grades", ID: &grade})
	if err == nil || q.lookups != 1 {
		t.Errorf("a reference of a new record is always checked, got %v after %d lookups", err, q.lookups)
	}
}
