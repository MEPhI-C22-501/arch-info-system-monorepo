package salarydmn

import (
	"time"
)

// GroupChangeRequest asks for new salaries of the employees of an org unit from one date (FR-RM-63): the salary in
// effect on the date ends the day before, the new one starts on the date and keeps the end of the old one.
type GroupChangeRequest struct {
	OrgUnitID int64
	// IncludeSubunits also takes the employees of the units below the unit.
	IncludeSubunits bool
	StartDate       time.Time
	// Percent changes the current amount, Amount sets the same amount for everybody, exactly one of them is set.
	Percent *float64
	Amount  *float64
	// CurrencyID is the currency of a new amount, the currency of the current salary when nil; only with Amount.
	CurrencyID *int64
	// ValidateOnly returns the plan and changes nothing (AIP-163).
	ValidateOnly bool
}

// GroupChangeItem is the change of the salary of one employee.
type GroupChangeItem struct {
	EmployeeID int64
	// ClosedSalaryID and PreviousAmount describe the salary that ends the day before StartDate, nil when the
	// employee had none and gets a first salary.
	ClosedSalaryID *int64
	PreviousAmount *float64
	// SalaryID is the created salary, nil in a validation.
	SalaryID   *int64
	Amount     float64
	CurrencyID int64
	StartDate  time.Time
	EndDate    *time.Time
}

// Skipped is an employee of the unit the operation leaves as is, with the reason.
type Skipped struct {
	EmployeeID int64
	Reason     string
}

// GroupChangeResult lists the changes in the order of the employee identifiers.
type GroupChangeResult struct {
	ValidateOnly bool
	Items        []GroupChangeItem
	Skipped      []Skipped
}
