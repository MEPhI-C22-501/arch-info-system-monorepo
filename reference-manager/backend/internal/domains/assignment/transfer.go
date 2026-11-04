package assignmentdmn

import (
	"time"
)

// TransferRequest moves the employees of an org unit to another unit from one date (FR-RM-64): the assignment in
// effect on the date ends the day before, the new one starts on the date in the target unit and keeps the end of
// the old one.
type TransferRequest struct {
	OrgUnitID       int64
	TargetOrgUnitID int64
	// IncludeSubunits also takes the employees of the units below the unit.
	IncludeSubunits bool
	StartDate       time.Time
	// PositionID is the position in the target unit, the current position of each employee when nil.
	PositionID *int64
	// ValidateOnly returns the plan and changes nothing (AIP-163).
	ValidateOnly bool
}

// TransferItem is the move of one employee.
type TransferItem struct {
	EmployeeID         int64
	ClosedAssignmentID int64
	FromOrgUnitID      int64
	// AssignmentID is the created assignment, nil in a validation.
	AssignmentID    *int64
	TargetOrgUnitID int64
	PositionID      int64
	StartDate       time.Time
	EndDate         *time.Time
}

// Skipped is an employee of the unit the operation leaves as is, with the reason.
type Skipped struct {
	EmployeeID int64
	Reason     string
}

// TransferResult lists the moves in the order of the employee identifiers.
type TransferResult struct {
	ValidateOnly bool
	Items        []TransferItem
	Skipped      []Skipped
}
