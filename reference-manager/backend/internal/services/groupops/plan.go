package groupopssrv

import (
	"math"

	assignmentdmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/assignment"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	salarydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/salary"
)

const (
	reasonDismissed       = "the employee is dismissed"
	reasonNoSalary        = "the employee has no salary in effect on start_date"
	reasonNoCurrency      = "the employee has no salary in effect on start_date and no currency_id is given"
	reasonInTarget        = "the employee is already in the target unit with the position"
	maxPercent            = 1000
	minPercent            = -99.99
	moneyFractionMultiple = 100
)

// validateRevision checks the request before any record is read.
func validateRevision(r *salarydmn.GroupChangeRequest) error {
	errs := &record.ValidationError{}

	if r.OrgUnitID <= 0 {
		errs.Add("org_unit_id", "must be a positive identifier")
	}
	if r.StartDate.IsZero() {
		errs.Add("start_date", "is required")
	}

	switch {
	case r.Percent == nil && r.Amount == nil:
		errs.Add("percent", "exactly one of percent and amount is required")
	case r.Percent != nil && r.Amount != nil:
		errs.Add("amount", "exactly one of percent and amount is allowed")
	case r.Percent != nil:
		if *r.Percent == 0 || *r.Percent < minPercent || *r.Percent > maxPercent {
			errs.Add("percent", "must be between -99.99 and 1000 and not zero")
		}
		if r.CurrencyID != nil {
			errs.Add("currency_id", "is allowed with amount only, a percent keeps the currency")
		}
	default:
		if *r.Amount <= 0 {
			errs.Add("amount", "must be positive")
		}
	}

	if r.CurrencyID != nil && *r.CurrencyID <= 0 {
		errs.Add("currency_id", "must be a positive identifier")
	}

	return errs.OrNil()
}

// validateTransfer checks the request before any record is read.
func validateTransfer(r *assignmentdmn.TransferRequest) error {
	errs := &record.ValidationError{}

	if r.OrgUnitID <= 0 {
		errs.Add("org_unit_id", "must be a positive identifier")
	}
	if r.TargetOrgUnitID <= 0 {
		errs.Add("target_org_unit_id", "must be a positive identifier")
	}
	if r.OrgUnitID > 0 && r.OrgUnitID == r.TargetOrgUnitID {
		errs.Add("target_org_unit_id", "must differ from org_unit_id")
	}
	if r.StartDate.IsZero() {
		errs.Add("start_date", "is required")
	}
	if r.PositionID != nil && *r.PositionID <= 0 {
		errs.Add("position_id", "must be a positive identifier")
	}

	return errs.OrNil()
}

type revisionStep struct {
	item  salarydmn.GroupChangeItem
	close *record.Expanded[salarydmn.Fields]
}

type revisionPlan struct {
	steps   []revisionStep
	skipped []salarydmn.Skipped
	// blocked are the employees whose salary in effect starts on the date: it cannot end the day before
	blocked []int64
}

// planRevision decides the change of every employee of the unit, employees are in identifier order and current
// holds the salary in effect on the date of those who have one.
func planRevision(r *salarydmn.GroupChangeRequest, employees []int64, employed map[int64]bool, current map[int64]*record.Expanded[salarydmn.Fields]) revisionPlan {
	var plan revisionPlan

	for _, id := range employees {
		if !employed[id] {
			plan.skipped = append(plan.skipped, salarydmn.Skipped{EmployeeID: id, Reason: reasonDismissed})
			continue
		}

		salary := current[id]
		if salary != nil && !salary.Fields.StartDate.Before(r.StartDate) {
			plan.blocked = append(plan.blocked, id)
			continue
		}

		item := salarydmn.GroupChangeItem{EmployeeID: id, StartDate: r.StartDate}

		switch {
		case salary == nil && r.Percent != nil:
			plan.skipped = append(plan.skipped, salarydmn.Skipped{EmployeeID: id, Reason: reasonNoSalary})
			continue
		case salary == nil && r.CurrencyID == nil:
			plan.skipped = append(plan.skipped, salarydmn.Skipped{EmployeeID: id, Reason: reasonNoCurrency})
			continue
		case salary == nil:
			item.Amount = *r.Amount
			item.CurrencyID = *r.CurrencyID
		default:
			closedID, previous := salary.ID, salary.Fields.Amount
			item.ClosedSalaryID = &closedID
			item.PreviousAmount = &previous
			item.EndDate = salary.Fields.EndDate
			item.CurrencyID = salary.Fields.CurrencyID
			if r.CurrencyID != nil {
				item.CurrencyID = *r.CurrencyID
			}

			if r.Percent != nil {
				item.Amount = roundMoney(previous * (1 + *r.Percent/100))
			} else {
				item.Amount = *r.Amount
			}
		}

		plan.steps = append(plan.steps, revisionStep{item: item, close: salary})
	}

	return plan
}

type transferStep struct {
	item assignmentdmn.TransferItem
}

type transferPlan struct {
	steps   []transferStep
	skipped []assignmentdmn.Skipped
	// blocked are the employees whose assignment in effect starts on the date: it cannot end the day before
	blocked []int64
}

// planTransfer decides the move of every employee of the unit from the assignments in effect on the date,
// sorted by employee; an employee has at most one of them, periods of one employee never overlap.
func planTransfer(r *assignmentdmn.TransferRequest, assignments []*record.Expanded[assignmentdmn.Fields], employed map[int64]bool) transferPlan {
	var plan transferPlan

	for _, a := range assignments {
		id := a.Fields.EmployeeID
		if !employed[id] {
			plan.skipped = append(plan.skipped, assignmentdmn.Skipped{EmployeeID: id, Reason: reasonDismissed})
			continue
		}

		position := a.Fields.PositionID
		if r.PositionID != nil {
			position = *r.PositionID
		}

		if a.Fields.OrgUnitID == r.TargetOrgUnitID && a.Fields.PositionID == position {
			plan.skipped = append(plan.skipped, assignmentdmn.Skipped{EmployeeID: id, Reason: reasonInTarget})
			continue
		}

		if !a.Fields.StartDate.Before(r.StartDate) {
			plan.blocked = append(plan.blocked, id)
			continue
		}

		plan.steps = append(plan.steps, transferStep{item: assignmentdmn.TransferItem{
			EmployeeID:         id,
			ClosedAssignmentID: a.ID,
			FromOrgUnitID:      a.Fields.OrgUnitID,
			TargetOrgUnitID:    r.TargetOrgUnitID,
			PositionID:         position,
			StartDate:          r.StartDate,
			EndDate:            a.Fields.EndDate,
		}})
	}

	return plan
}

// roundMoney keeps two decimals, halves away from zero.
func roundMoney(v float64) float64 {
	return math.Round(v*moneyFractionMultiple) / moneyFractionMultiple
}
