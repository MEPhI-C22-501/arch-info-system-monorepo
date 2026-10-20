package salarydmn

import (
	"context"
	"errors"

	employeedmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/employee"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
)

// validate checks the references and the period of a salary, the overlap with other salaries
// of the employee is rejected by the exclusion constraint of the table (FR-RM-52).
func validate(ctx context.Context, q postgres.Querier, next, prev *record.Record[Fields]) error {
	f := &next.Fields
	errs := &record.ValidationError{}

	if f.EndDate != nil && f.EndDate.Before(f.StartDate) {
		errs.Add("end_date", "must not be earlier than start_date")
	}

	// a new salary needs a working employee, closing an existing one does not
	if prev == nil {
		message, err := employeedmn.CheckEmployed(ctx, q, f.EmployeeID)
		if err != nil {
			return err
		}
		if message != "" {
			errs.Add("employee_id", message)
		}
	}

	err := record.CheckReferences(ctx, q, record.Reference{Field: "currency_id", Table: "currencies", ID: &f.CurrencyID})
	if err != nil {
		var refErrs *record.ValidationError
		if !errors.As(err, &refErrs) {
			return err
		}

		errs.Fields = append(errs.Fields, refErrs.Fields...)
	}

	return errs.OrNil()
}
