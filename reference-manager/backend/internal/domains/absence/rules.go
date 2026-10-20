package absencedmn

import (
	"context"
	"errors"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
)

// validate checks that the employee exists and the period is ordered, absences of dismissed employees
// stay editable because they describe the past.
func validate(ctx context.Context, q postgres.Querier, next, _ *record.Record[Fields]) error {
	f := &next.Fields
	errs := &record.ValidationError{}

	if f.EndDate.Before(f.StartDate) {
		errs.Add("end_date", "must not be earlier than start_date")
	}

	err := record.CheckReferences(ctx, q, record.Reference{Field: "employee_id", Table: "employees", ID: &f.EmployeeID})
	if err != nil {
		var refErrs *record.ValidationError
		if !errors.As(err, &refErrs) {
			return err
		}

		errs.Fields = append(errs.Fields, refErrs.Fields...)
	}

	return errs.OrNil()
}
