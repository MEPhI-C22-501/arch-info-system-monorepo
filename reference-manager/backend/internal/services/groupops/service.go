// Package groupopssrv implements the group operations over the employees of an org unit: a revision of their
// salaries and a transfer to another unit, each from one date and in one transaction (FR-RM-63, FR-RM-64).
// The decision for every employee is a pure plan (plan.go), this file loads its input and applies it.
package groupopssrv

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"
	"uuid"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/access"
	assignmentdmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/assignment"
	employeedmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/employee"
	orgunitdmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/org_unit"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	salarydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/salary"
	recordsrv "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/services/record"
)

const dateLayout = "2006-01-02"

// errValidateOnly rolls back the transaction of a validation after the plan has been applied and checked.
var errValidateOnly = errors.New("validate only")

// subunitsQuery returns the unit and every active unit below it.
const subunitsQuery = `WITH RECURSIVE tree AS (
    SELECT id FROM org_units WHERE id = $1
    UNION
    SELECT o.id FROM org_units o JOIN tree t ON o.parent_id = t.id WHERE o.is_deleted = FALSE
)
SELECT id FROM tree ORDER BY id`

// Service runs the group operations on top of the catalog services, so every change gets its revision and passes
// the rules of its catalog.
type Service struct {
	txManager   recordsrv.TxManager
	db          recordsrv.DB
	orgUnits    *recordsrv.Service[orgunitdmn.Fields]
	employees   *recordsrv.Service[employeedmn.Fields]
	assignments *recordsrv.Service[assignmentdmn.Fields]
	salaries    *recordsrv.Service[salarydmn.Fields]
}

func NewService(
	txManager recordsrv.TxManager,
	db recordsrv.DB,
	orgUnits *recordsrv.Service[orgunitdmn.Fields],
	employees *recordsrv.Service[employeedmn.Fields],
	assignments *recordsrv.Service[assignmentdmn.Fields],
	salaries *recordsrv.Service[salarydmn.Fields],
) *Service {
	return &Service{
		txManager:   txManager,
		db:          db,
		orgUnits:    orgUnits,
		employees:   employees,
		assignments: assignments,
		salaries:    salaries,
	}
}

// ReviseSalaries gives the employees of the unit new salaries from the date: the salary in effect ends the day
// before, the new one keeps its end. The whole operation is applied or rejected (FR-RM-63).
func (s *Service) ReviseSalaries(ctx context.Context, request *salarydmn.GroupChangeRequest) (*salarydmn.GroupChangeResult, error) {
	changer, err := s.authorizeWrite(ctx, s.salaries.Authorize)
	if err != nil {
		return nil, err
	}

	if err := validateRevision(request); err != nil {
		return nil, err
	}

	result := &salarydmn.GroupChangeResult{ValidateOnly: request.ValidateOnly}

	err = s.txManager.Do(ctx, func(ctx context.Context) error {
		members, err := s.members(ctx, request.OrgUnitID, request.IncludeSubunits, request.StartDate)
		if err != nil {
			return err
		}

		current := make(map[int64]*record.Expanded[salarydmn.Fields], len(members.employees))
		for _, id := range members.employees {
			found, err := s.salaries.ListAll(ctx, "employee_id = "+strconv.FormatInt(id, 10)+" AND "+inEffectFilter(request.StartDate), false)
			if err != nil {
				return err
			}
			if len(found) > 0 {
				current[id] = found[0]
			}
		}

		plan := planRevision(request, members.employees, members.employed, current)
		if len(plan.blocked) > 0 {
			return blockedError("the salary in effect starts on start_date, change it directly", plan.blocked)
		}

		for i := range plan.steps {
			step := &plan.steps[i]
			if step.close != nil {
				end := request.StartDate.AddDate(0, 0, -1)
				if _, err := s.salaries.Modify(ctx, step.close.ID, changer, func(m *record.Record[salarydmn.Fields]) error {
					m.Fields.EndDate = &end
					return nil
				}); err != nil {
					return fmt.Errorf("close salary %d of employee %d: %w", step.close.ID, step.item.EmployeeID, err)
				}
			}

			created, err := s.salaries.Create(ctx, &salarydmn.Fields{
				EmployeeID: step.item.EmployeeID,
				Amount:     step.item.Amount,
				CurrencyID: step.item.CurrencyID,
				StartDate:  step.item.StartDate,
				EndDate:    step.item.EndDate,
			})
			if err != nil {
				return fmt.Errorf("create salary of employee %d: %w", step.item.EmployeeID, err)
			}

			if !request.ValidateOnly {
				id := created.ID
				step.item.SalaryID = &id
			}

			result.Items = append(result.Items, step.item)
		}

		result.Skipped = plan.skipped

		if request.ValidateOnly {
			return errValidateOnly
		}

		return nil
	})
	if err != nil && !errors.Is(err, errValidateOnly) {
		return nil, err
	}

	return result, nil
}

// TransferAssignments moves the employees of the unit to the target unit from the date: the assignment in effect
// ends the day before, the new one keeps its end. The whole operation is applied or rejected (FR-RM-64).
func (s *Service) TransferAssignments(ctx context.Context, request *assignmentdmn.TransferRequest) (*assignmentdmn.TransferResult, error) {
	changer, err := s.authorizeWrite(ctx, s.assignments.Authorize)
	if err != nil {
		return nil, err
	}

	if err := validateTransfer(request); err != nil {
		return nil, err
	}

	result := &assignmentdmn.TransferResult{ValidateOnly: request.ValidateOnly}

	err = s.txManager.Do(ctx, func(ctx context.Context) error {
		if _, err := s.orgUnits.Get(ctx, request.TargetOrgUnitID, false); err != nil {
			if errors.Is(err, domains.ErrNotFound) {
				return record.Violation("target_org_unit_id", fmt.Sprintf("org unit %d does not exist or is deleted", request.TargetOrgUnitID))
			}

			return err
		}

		members, err := s.members(ctx, request.OrgUnitID, request.IncludeSubunits, request.StartDate)
		if err != nil {
			return err
		}

		plan := planTransfer(request, members.assignments, members.employed)
		if len(plan.blocked) > 0 {
			return blockedError("the assignment in effect starts on start_date, change it directly", plan.blocked)
		}

		for i := range plan.steps {
			step := &plan.steps[i]
			end := request.StartDate.AddDate(0, 0, -1)
			if _, err := s.assignments.Modify(ctx, step.item.ClosedAssignmentID, changer, func(m *record.Record[assignmentdmn.Fields]) error {
				m.Fields.EndDate = &end
				return nil
			}); err != nil {
				return fmt.Errorf("close assignment %d of employee %d: %w", step.item.ClosedAssignmentID, step.item.EmployeeID, err)
			}

			created, err := s.assignments.Create(ctx, &assignmentdmn.Fields{
				EmployeeID: step.item.EmployeeID,
				OrgUnitID:  step.item.TargetOrgUnitID,
				PositionID: step.item.PositionID,
				StartDate:  step.item.StartDate,
				EndDate:    step.item.EndDate,
			})
			if err != nil {
				return fmt.Errorf("create assignment of employee %d: %w", step.item.EmployeeID, err)
			}

			if !request.ValidateOnly {
				id := created.ID
				step.item.AssignmentID = &id
			}

			result.Items = append(result.Items, step.item)
		}

		result.Skipped = plan.skipped

		if request.ValidateOnly {
			return errValidateOnly
		}

		return nil
	})
	if err != nil && !errors.Is(err, errValidateOnly) {
		return nil, err
	}

	return result, nil
}

// authorizeWrite checks that the caller may create and update records of the catalog the operation writes.
func (s *Service) authorizeWrite(ctx context.Context, authorize func(context.Context, access.Level) (uuid.UUID, error)) (uuid.UUID, error) {
	if _, err := authorize(ctx, access.LevelCreate); err != nil {
		return uuid.UUID{}, err
	}

	return authorize(ctx, access.LevelUpdate)
}

// members are the employees of the unit on the date: the assignments in effect, the employees in identifier order
// and whether each of them works.
type members struct {
	assignments []*record.Expanded[assignmentdmn.Fields]
	employees   []int64
	employed    map[int64]bool
}

func (s *Service) members(ctx context.Context, orgUnitID int64, includeSubunits bool, day time.Time) (*members, error) {
	if _, err := s.orgUnits.Get(ctx, orgUnitID, false); err != nil {
		if errors.Is(err, domains.ErrNotFound) {
			return nil, record.Violation("org_unit_id", fmt.Sprintf("org unit %d does not exist or is deleted", orgUnitID))
		}

		return nil, err
	}

	units := []int64{orgUnitID}
	if includeSubunits {
		var err error
		if units, err = s.subunits(ctx, orgUnitID); err != nil {
			return nil, err
		}
	}

	conditions := make([]string, 0, len(units))
	for _, id := range units {
		conditions = append(conditions, "org_unit_id = "+strconv.FormatInt(id, 10))
	}

	assignments, err := s.assignments.ListAll(ctx, "("+strings.Join(conditions, " OR ")+") AND "+inEffectFilter(day), false)
	if err != nil {
		return nil, err
	}

	sort.Slice(assignments, func(i, j int) bool { return assignments[i].Fields.EmployeeID < assignments[j].Fields.EmployeeID })

	m := &members{assignments: assignments, employed: make(map[int64]bool, len(assignments))}
	for _, a := range assignments {
		id := a.Fields.EmployeeID
		if _, seen := m.employed[id]; seen {
			continue
		}

		employee, err := s.employees.Get(ctx, id, false)
		switch {
		case errors.Is(err, domains.ErrNotFound):
			m.employed[id] = false
		case err != nil:
			return nil, err
		default:
			m.employed[id] = employee.Fields.EmploymentState == employeedmn.StateEmployed
		}

		m.employees = append(m.employees, id)
	}

	return m, nil
}

func (s *Service) subunits(ctx context.Context, orgUnitID int64) ([]int64, error) {
	rows, err := s.db.Querier(ctx).Query(ctx, subunitsQuery, orgUnitID)
	if err != nil {
		return nil, fmt.Errorf("select subunits of org unit %d: %w", orgUnitID, err)
	}
	defer rows.Close()

	var units []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			return nil, fmt.Errorf("scan subunit: %w", err)
		}

		units = append(units, id)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("select subunits of org unit %d: %w", orgUnitID, err)
	}

	return units, nil
}

// inEffectFilter selects the dated records in effect on the day: started by then and not ended before it.
func inEffectFilter(day time.Time) string {
	d := strconv.Quote(day.Format(dateLayout))
	return "start_date <= " + d + " AND (end_date >= " + d + " OR NOT end_date:*)"
}

// blockedError rejects the whole operation for the employees whose record in effect cannot be split on the date.
func blockedError(reason string, employees []int64) error {
	ids := make([]string, 0, len(employees))
	for _, id := range employees {
		ids = append(ids, strconv.FormatInt(id, 10))
	}

	return fmt.Errorf("employees %s: %s: %w", strings.Join(ids, ", "), reason, domains.ErrFailedPrecondition)
}
