package employeedmn

import (
	"context"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
)

// Employment states of an employee, the state changes only by the dismissal.
const (
	StateEmployed  = "EMPLOYED"
	StateDismissed = "DISMISSED"
)

// validate keeps the employment state and the dismissal date consistent.
func validate(_ context.Context, _ postgres.Querier, next, _ *record.Record[Fields]) error {
	errs := &record.ValidationError{}
	f := &next.Fields

	if f.DismissalDate != nil && f.DismissalDate.Before(f.HireDate) {
		errs.Add("dismissal_date", "must not be earlier than hire_date")
	}

	if (f.EmploymentState == StateDismissed) != (f.DismissalDate != nil) {
		errs.Add("employment_state", "DISMISSED requires a dismissal date and EMPLOYED excludes it")
	}

	return errs.OrNil()
}

// CheckEmployed reports a violation message when the employee is missing, deleted or dismissed.
// It is used by the dated catalogs, which accept new records only for working employees.
func CheckEmployed(ctx context.Context, q postgres.Querier, id int64) (string, error) {
	var (
		deleted bool
		state   string
	)

	err := q.QueryRow(ctx, "SELECT is_deleted, employment_state FROM employees WHERE id = $1", id).Scan(&deleted, &state)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return fmt.Sprintf("employees %d does not exist", id), nil
		}

		return "", fmt.Errorf("check employee: %w", err)
	}

	switch {
	case deleted:
		return fmt.Sprintf("employees %d is deleted", id), nil
	case state != StateEmployed:
		return fmt.Sprintf("employees %d is dismissed", id), nil
	}

	return "", nil
}
