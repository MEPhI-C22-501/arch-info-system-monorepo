package assignmentdmn

import (
	"context"

	employeedmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/employee"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
)

// validate checks the references and the period of an assignment, the overlap with other assignments
// of the employee is rejected by the exclusion constraint of the table (FR-RM-52).
func validate(ctx context.Context, q postgres.Querier, next, prev *record.Record[Fields]) error {
	f := &next.Fields
	errs := &record.ValidationError{}

	if f.EndDate != nil && f.EndDate.Before(f.StartDate) {
		errs.Add("end_date", "must not be earlier than start_date")
	}

	// a new assignment needs a working employee, closing an existing one does not
	if prev == nil {
		message, err := employeedmn.CheckEmployed(ctx, q, f.EmployeeID)
		if err != nil {
			return err
		}
		if message != "" {
			errs.Add("employee_id", message)
		}
	}

	// an unchanged reference is not checked again, so an assignment that points at a since deleted unit, position
	// or grade can still be closed, for example by a dismissal
	var orgUnitBefore, positionBefore, gradeBefore *int64
	if prev != nil {
		orgUnitBefore, positionBefore, gradeBefore = &prev.Fields.OrgUnitID, &prev.Fields.PositionID, prev.Fields.GradeID
	}

	if err := record.CheckReferences(ctx, q,
		record.Reference{Field: "org_unit_id", Table: "org_units", ID: &f.OrgUnitID, Before: orgUnitBefore},
		record.Reference{Field: "position_id", Table: "positions", ID: &f.PositionID, Before: positionBefore},
		// the grade is optional (FR-RM-69): an empty one is not checked
		record.Reference{Field: "grade_id", Table: "grades", ID: f.GradeID, Before: gradeBefore},
	); err != nil {
		var refErrs *record.ValidationError
		if !asValidation(err, &refErrs) {
			return err
		}

		errs.Fields = append(errs.Fields, refErrs.Fields...)
	}

	return errs.OrNil()
}
