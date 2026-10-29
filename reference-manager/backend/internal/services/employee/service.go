// Package employeesrv adds the dismissal and the Keycloak account to the standard methods of the employees catalog.
package employeesrv

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"strings"
	"time"
	"uuid"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/access"
	assignmentdmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/assignment"
	employeedmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/employee"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	salarydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/salary"
	recordsrv "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/services/record"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/keycloak"
)

const dateLayout = "2006-01-02"

// accountFields are the fields of the record the account follows (FR-RM-57).
var accountFields = map[string]bool{"family_name": true, "given_name": true, "email": true}

// Accounts is the part of Keycloak the service uses, implemented by keycloak.Admin.
type Accounts interface {
	// FindByUsername returns nil when there is no account with the username.
	FindByUsername(ctx context.Context, username string) (*keycloak.Account, error)
	Get(ctx context.Context, id string) (*keycloak.Account, error)
	// Create creates a disabled account with the temporary password and returns its identifier.
	Create(ctx context.Context, account *keycloak.Account, temporaryPassword string) (string, error)
	// Update sets the names, the email and the enabled flag of the account.
	Update(ctx context.Context, account *keycloak.Account) error
}

// Service serves employees: the generic methods plus the dismissal, which also closes the dated records in effect,
// and the Keycloak account that follows the record (FR-RM-53..58).
type Service struct {
	*recordsrv.Service[employeedmn.Fields]

	log         *slog.Logger
	txManager   recordsrv.TxManager
	assignments *recordsrv.Service[assignmentdmn.Fields]
	salaries    *recordsrv.Service[salarydmn.Fields]
	accounts    Accounts
}

func NewService(
	log *slog.Logger,
	employees *recordsrv.Service[employeedmn.Fields],
	txManager recordsrv.TxManager,
	assignments *recordsrv.Service[assignmentdmn.Fields],
	salaries *recordsrv.Service[salarydmn.Fields],
	accounts Accounts,
) *Service {
	return &Service{
		Service:     employees,
		log:         log,
		txManager:   txManager,
		assignments: assignments,
		salaries:    salaries,
		accounts:    accounts,
	}
}

// Create stores the employee with the account PENDING, then creates the account in Keycloak and enables it (FR-RM-53).
// When Keycloak is unavailable the record stays PENDING and the client repeats the operation with SyncAccount (FR-RM-55).
func (s *Service) Create(ctx context.Context, fields *employeedmn.Fields) (*record.Expanded[employeedmn.Fields], error) {
	changer, err := s.Authorize(ctx, access.LevelCreate)
	if err != nil {
		return nil, err
	}

	created, err := s.Service.Create(ctx, fields)
	if err != nil {
		return nil, err
	}

	return s.provision(ctx, created, changer)
}

// Update changes the fields of the mask. New names or a new email are passed to the account (FR-RM-57),
// a pending operation with the account is repeated as well.
func (s *Service) Update(ctx context.Context, request *record.UpdateRequest[employeedmn.Fields]) (*record.Expanded[employeedmn.Fields], error) {
	changer, err := s.Authorize(ctx, access.LevelUpdate)
	if err != nil {
		return nil, err
	}

	updated, err := s.Service.Update(ctx, request)
	if err != nil {
		return nil, err
	}

	if updated.Fields.AccountState != employeedmn.AccountPending && !touchesAccount(request.UpdateMask) {
		return updated, nil
	}

	return s.provision(ctx, updated, changer)
}

// Delete rejects a working employee with an account: the dismissal blocks the account first (FR-RM-58).
func (s *Service) Delete(ctx context.Context, id int64) (*record.Expanded[employeedmn.Fields], error) {
	current, err := s.Get(ctx, id, false)
	if err != nil {
		return nil, err
	}

	if current.Fields.EmploymentState == employeedmn.StateEmployed && current.Fields.AccountUserID != nil {
		return nil, fmt.Errorf("employee %d has an account, dismiss the employee before the deletion: %w", id, domains.ErrFailedPrecondition)
	}

	return s.Service.Delete(ctx, id)
}

// Dismiss sets the employee to DISMISSED with the date and closes the assignment and the salary in effect
// with the same date, every change gets its own revision (FR-RM-54). The account is blocked after the transaction,
// until then the operation is PENDING (FR-RM-55).
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
			m.Fields.AccountState = employeedmn.AccountPending

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

	return s.provision(ctx, dismissed, changer)
}

// SyncAccount repeats the pending operation with the account (FR-RM-56). It is safe for any employee:
// the account is found by its identifier or username, a second account is never created.
func (s *Service) SyncAccount(ctx context.Context, id int64) (*record.Expanded[employeedmn.Fields], error) {
	changer, err := s.Authorize(ctx, access.LevelUpdate)
	if err != nil {
		return nil, err
	}

	current, err := s.Get(ctx, id, false)
	if err != nil {
		return nil, err
	}

	return s.provision(ctx, current, changer)
}

// provision brings the account in line with the record and stores the result with a revision: the account exists
// for every working employee, it is enabled while the employee works and disabled after the dismissal, its names
// and email follow the record. Any failure of Keycloak leaves the record PENDING and is reported as ErrUnavailable,
// a username taken by a foreign account as ErrFailedPrecondition (FR-RM-55).
func (s *Service) provision(ctx context.Context, current *record.Expanded[employeedmn.Fields], changer uuid.UUID) (*record.Expanded[employeedmn.Fields], error) {
	account, err := s.syncAccount(ctx, &current.Fields)
	if err != nil {
		s.log.WarnContext(ctx, "account operation is pending",
			slog.Int64("employee_id", current.ID), slog.String("username", current.Fields.Username), slog.String("error", err.Error()))

		if current.Fields.AccountState != employeedmn.AccountPending {
			_, markErr := s.Modify(ctx, current.ID, changer, func(m *record.Record[employeedmn.Fields]) error {
				m.Fields.AccountState = employeedmn.AccountPending
				return nil
			})
			if markErr != nil {
				return nil, fmt.Errorf("mark employee %d account pending: %w", current.ID, markErr)
			}
		}

		if errors.Is(err, keycloak.ErrAccountConflict) {
			return nil, fmt.Errorf("employee %d: %w: %w", current.ID, err, domains.ErrFailedPrecondition)
		}

		return nil, fmt.Errorf("employee %d (%s) is stored, the operation with its account is pending, repeat it with SyncAccount: %w",
			current.ID, current.Fields.Username, domains.ErrUnavailable)
	}

	state := employeedmn.AccountDisabled
	accountID := current.Fields.AccountUserID

	if account != nil {
		id := account.ID
		accountID = &id

		if account.Enabled {
			state = employeedmn.AccountEnabled
		}
	}

	if current.Fields.AccountState == state && equalPtr(current.Fields.AccountUserID, accountID) {
		return current, nil
	}

	return s.Modify(ctx, current.ID, changer, func(m *record.Record[employeedmn.Fields]) error {
		m.Fields.AccountState = state
		m.Fields.AccountUserID = accountID

		return nil
	})
}

// syncAccount finds or creates the account and pushes the record to it. A dismissed employee without an account
// gets none, there is nothing to block.
func (s *Service) syncAccount(ctx context.Context, f *employeedmn.Fields) (*keycloak.Account, error) {
	wantEnabled := f.EmploymentState == employeedmn.StateEmployed

	account, err := s.findAccount(ctx, f)
	if err != nil {
		return nil, err
	}

	if account == nil {
		if !wantEnabled {
			return nil, nil
		}

		password, err := keycloak.TemporaryPassword()
		if err != nil {
			return nil, err
		}

		// created disabled, enabled by the update below once it exists (FR-RM-53)
		account = &keycloak.Account{
			Username:  f.Username,
			Email:     f.Email,
			FirstName: f.GivenName,
			LastName:  f.FamilyName,
		}

		account.ID, err = s.accounts.Create(ctx, account, password)
		if err != nil {
			return nil, err
		}
	}

	account.Email = f.Email
	account.FirstName = f.GivenName
	account.LastName = f.FamilyName
	account.Enabled = wantEnabled

	if err := s.accounts.Update(ctx, account); err != nil {
		return nil, err
	}

	return account, nil
}

// findAccount returns the account linked to the record. Without a link (the creation was interrupted before
// the identifier was stored) the account with the username is adopted when its email matches the record,
// otherwise the username belongs to a foreign account and that is a conflict.
func (s *Service) findAccount(ctx context.Context, f *employeedmn.Fields) (*keycloak.Account, error) {
	if f.AccountUserID != nil {
		account, err := s.accounts.Get(ctx, *f.AccountUserID)
		if err == nil {
			return account, nil
		}

		if !errors.Is(err, keycloak.ErrAccountNotFound) {
			return nil, err
		}

		// the account was removed in Keycloak: it is looked up by username and created again when missing
	}

	account, err := s.accounts.FindByUsername(ctx, f.Username)
	if err != nil || account == nil {
		return nil, err
	}

	if !strings.EqualFold(account.Email, f.Email) {
		return nil, fmt.Errorf("%w: username %q belongs to another account", keycloak.ErrAccountConflict, f.Username)
	}

	return account, nil
}

// touchesAccount reports whether the update mask includes a field the account follows.
func touchesAccount(mask string) bool {
	mask = strings.TrimSpace(mask)
	if mask == "" || mask == "*" {
		return true
	}

	for field := range strings.SplitSeq(mask, ",") {
		if accountFields[strings.TrimSpace(field)] {
			return true
		}
	}

	return false
}

func equalPtr(a, b *string) bool {
	if a == nil || b == nil {
		return a == b
	}

	return *a == *b
}

// inEffectFilter selects the records of the employee that are in effect on the date or later.
func inEffectFilter(employeeID int64, date time.Time) string {
	day := date.Format(dateLayout)

	return fmt.Sprintf(`employee_id = %d AND start_date <= %q AND (NOT end_date:* OR end_date > %q)`, employeeID, day, day)
}

func closeAssignments(ctx context.Context, assignments *recordsrv.Service[assignmentdmn.Fields], employeeID int64, date time.Time, changer uuid.UUID) error {
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

func closeSalaries(ctx context.Context, salaries *recordsrv.Service[salarydmn.Fields], employeeID int64, date time.Time, changer uuid.UUID) error {
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
