// Package employeesrv adds the dismissal to the standard methods of the employees catalog.
package employeesrv

import (
	"context"
	"fmt"
	"time"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/access"
	assignmentdmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/assignment"
	employeedmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/employee"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	salarydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/salary"
	recordsrv "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/services/record"
)

const dateLayout = "2006-01-02"

// Service serves employees: the generic methods plus the dismissal, which also closes the dated records in effect.
type Service struct {
	*recordsrv.Service[employeedmn.Fields]

	txManager   recordsrv.TxManager
	assignments *recordsrv.Service[assignmentdmn.Fields]
	salaries    *recordsrv.Service[salarydmn.Fields]
}

func NewService(
	employees *recordsrv.Service[employeedmn.Fields],
	txManager recordsrv.TxManager,
	assignments *recordsrv.Service[assignmentdmn.Fields],
	salaries *recordsrv.Service[salarydmn.Fields],
) *Service {
	return &Service{
		Service:     employees,
		txManager:   txManager,
		assignments: assignments,
		salaries:    salaries,
	}
}

// Dismiss sets the employee to DISMISSED with the date and closes the assignment and the salary in effect
// with the same date, every change gets its own revision (FR-RM-54).
func (s *Service) Dismiss(ctx context.Context, id int64, dismissalDate time.Time) (*record.Expanded[employeedmn.Fields], error) {
	changer, err := s.Authorize(ctx, access.LevelUpdate)
	if err != nil {
		return nil, err
	}

	var dismissed *record.Expanded[employeedmn.Fields]
	err = s.txManager.Do(ctx, func(ctx context.Context) error {
		current, err := s.Get(ctx, id, false)
		if err != nil {
			return err
		}

		if current.Fields.EmploymentState == employeedmn.StateDismissed {
			return fmt.Errorf("employee %d is already dismissed on %s: %w",
				id, current.Fields.DismissalDate.Format(dateLayout), domains.ErrFailedPrecondition)
		}

		if dismissalDate.Before(current.Fields.HireDate) {
			return record.Violation("dismissal_date", "must not be earlier than hire_date")
		}

		dismissed, err = s.Modify(ctx, id, changer, func(m *record.Record[employeedmn.Fields]) error {
			date := dismissalDate
			m.Fields.EmploymentState = employeedmn.StateDismissed
			m.Fields.DismissalDate = &date

			return nil
		})
		if err != nil {
			return err
		}

		if err := closeAssignments(ctx, s.assignments, id, dismissalDate, changer); err != nil {
			return err
		}

		return closeSalaries(ctx, s.salaries, id, dismissalDate, changer)
	})
	if err != nil {
		return nil, err
	}

	return dismissed, nil
}

// inEffectFilter selects the records of the employee that are in effect on the date or later.
func inEffectFilter(employeeID int64, date time.Time) string {
	day := date.Format(dateLayout)
	return fmt.Sprintf(`employee_id = %d AND start_date <= %q AND (NOT end_date:* OR end_date > %q)`, employeeID, day, day)
}

func closeAssignments(ctx context.Context, assignments *recordsrv.Service[assignmentdmn.Fields], employeeID int64, date time.Time, changer uuidType) error {
	open, err := assignments.ListAll(ctx, inEffectFilter(employeeID, date), false)
	if err != nil {
		return fmt.Errorf("list assignments in effect: %w", err)
	}

	for _, a := range open {
		_, err := assignments.Modify(ctx, a.ID, changer, func(m *record.Record[assignmentdmn.Fields]) error {
			end := date
			m.Fields.EndDate = &end

			return nil
		})
		if err != nil {
			return fmt.Errorf("close assignment %d: %w", a.ID, err)
		}
	}

	return nil
}

func closeSalaries(ctx context.Context, salaries *recordsrv.Service[salarydmn.Fields], employeeID int64, date time.Time, changer uuidType) error {
	open, err := salaries.ListAll(ctx, inEffectFilter(employeeID, date), false)
	if err != nil {
		return fmt.Errorf("list salaries in effect: %w", err)
	}

	for _, s := range open {
		_, err := salaries.Modify(ctx, s.ID, changer, func(m *record.Record[salarydmn.Fields]) error {
			end := date
			m.Fields.EndDate = &end

			return nil
		})
		if err != nil {
			return fmt.Errorf("close salary %d: %w", s.ID, err)
		}
	}

	return nil
}
