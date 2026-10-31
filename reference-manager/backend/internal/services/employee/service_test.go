package employeesrv_test

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"testing"
	"time"
	"uuid"

	"github.com/stretchr/testify/require"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	assignmentdmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/assignment"
	employeedmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/employee"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	salarydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/salary"
	employeesrv "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/services/employee"
	recordsrv "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/services/record"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/actor"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/keycloak"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
)

var hrAdmin = uuid.MustParse("d81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d")

type fakeTx struct{}

func (fakeTx) Do(ctx context.Context, fn func(ctx context.Context) error) error { return fn(ctx) }

type fakeDB struct{}

func (fakeDB) Querier(context.Context) postgres.Querier { return nil }

// fakeRepo keeps the records and the revisions of one catalog in memory.
type fakeRepo[F any] struct {
	records   map[int64]*record.Record[F]
	revisions map[int64][]*record.Revision
	next      int64
}

func newFakeRepo[F any]() *fakeRepo[F] {
	return &fakeRepo[F]{records: map[int64]*record.Record[F]{}, revisions: map[int64][]*record.Revision{}}
}

func (r *fakeRepo[F]) Create(_ context.Context, m *record.Record[F]) (int64, error) {
	r.next++
	stored := *m
	stored.ID = r.next
	r.records[stored.ID] = &stored

	return stored.ID, nil
}

func (r *fakeRepo[F]) Update(_ context.Context, m *record.Record[F]) error {
	stored := *m
	r.records[m.ID] = &stored

	return nil
}

func (r *fakeRepo[F]) Delete(_ context.Context, id int64) error {
	delete(r.records, id)
	return nil
}

func (r *fakeRepo[F]) GetExpanded(_ context.Context, id int64) (*record.Expanded[F], error) {
	m, ok := r.records[id]
	if !ok {
		return nil, domains.ErrNotFound
	}

	revisions := r.revisions[id]
	x := &record.Expanded[F]{Record: *m, Revision: int32(len(revisions))}

	if len(revisions) > 0 {
		x.LastChanger = revisions[len(revisions)-1].ChangedBy
	}

	return x, nil
}

func (r *fakeRepo[F]) ListExpanded(context.Context, *record.ListQuery) ([]*record.Expanded[F], error) {
	return nil, nil
}

func (r *fakeRepo[F]) CreateRevision(_ context.Context, m *record.Revision) error {
	for _, rev := range r.revisions[m.RecordID] {
		if rev.RevisionNumber == m.RevisionNumber {
			return domains.ErrAlreadyExists
		}
	}

	r.revisions[m.RecordID] = append(r.revisions[m.RecordID], m)

	return nil
}

func (r *fakeRepo[F]) GetRevision(context.Context, int64, int32) (*record.Revision, error) {
	return nil, domains.ErrNotFound
}

func (r *fakeRepo[F]) ListRevisions(context.Context, *record.RevisionListQuery) ([]*record.Revision, error) {
	return nil, nil
}

// fakeAccounts is Keycloak in memory, down makes every call fail as an outage.
type fakeAccounts struct {
	down    bool
	byID    map[string]*keycloak.Account
	creates int
	updates int
}

func newFakeAccounts() *fakeAccounts {
	return &fakeAccounts{byID: map[string]*keycloak.Account{}}
}

func (f *fakeAccounts) add(a keycloak.Account) {
	f.byID[a.ID] = &a
}

func (f *fakeAccounts) FindByUsername(_ context.Context, username string) (*keycloak.Account, error) {
	if f.down {
		return nil, keycloak.ErrAccountUnavailable
	}

	for _, a := range f.byID {
		if a.Username == username {
			found := *a
			return &found, nil
		}
	}

	return nil, nil
}

func (f *fakeAccounts) Get(_ context.Context, id string) (*keycloak.Account, error) {
	if f.down {
		return nil, keycloak.ErrAccountUnavailable
	}

	a, ok := f.byID[id]
	if !ok {
		return nil, fmt.Errorf("account %s: %w", id, keycloak.ErrAccountNotFound)
	}

	found := *a

	return &found, nil
}

func (f *fakeAccounts) Create(ctx context.Context, a *keycloak.Account, temporaryPassword string) (string, error) {
	if f.down {
		return "", keycloak.ErrAccountUnavailable
	}

	if temporaryPassword == "" {
		return "", errors.New("temporary password is empty")
	}

	if existing, _ := f.FindByUsername(ctx, a.Username); existing != nil {
		return "", keycloak.ErrAccountConflict
	}

	f.creates++
	created := *a
	created.ID = fmt.Sprintf("acc-%d", len(f.byID)+1)
	created.Enabled = false
	f.byID[created.ID] = &created

	return created.ID, nil
}

func (f *fakeAccounts) Update(_ context.Context, a *keycloak.Account) error {
	if f.down {
		return keycloak.ErrAccountUnavailable
	}

	if _, ok := f.byID[a.ID]; !ok {
		return keycloak.ErrAccountNotFound
	}

	f.updates++
	updated := *a
	f.byID[a.ID] = &updated

	return nil
}

func newService(accounts employeesrv.Accounts) (*employeesrv.Service, *fakeRepo[employeedmn.Fields]) {
	employeesRepo := newFakeRepo[employeedmn.Fields]()
	employees := recordsrv.NewService(employeedmn.Descriptor, fakeTx{}, fakeDB{}, employeesRepo, employeesRepo)

	assignmentsRepo := newFakeRepo[assignmentdmn.Fields]()
	assignments := recordsrv.NewService(assignmentdmn.Descriptor, fakeTx{}, fakeDB{}, assignmentsRepo, assignmentsRepo)

	salariesRepo := newFakeRepo[salarydmn.Fields]()
	salaries := recordsrv.NewService(salarydmn.Descriptor, fakeTx{}, fakeDB{}, salariesRepo, salariesRepo)

	log := slog.New(slog.NewTextHandler(io.Discard, nil))

	return employeesrv.NewService(log, employees, fakeTx{}, assignments, salaries, accounts), employeesRepo
}

func hrAdminContext() context.Context {
	return actor.WithActor(context.Background(), &actor.Actor{UserID: hrAdmin, Roles: []string{"reference-hr-admin"}})
}

func petrova() *employeedmn.Fields {
	return &employeedmn.Fields{
		PersonnelNumber: "1024",
		FamilyName:      "Petrova",
		GivenName:       "Maria",
		Email:           "m.petrova@example.org",
		Username:        "m.petrova",
		HireDate:        time.Date(2026, 11, 2, 0, 0, 0, 0, time.UTC),
		EmploymentState: employeedmn.StateEmployed,
		AccountState:    employeedmn.AccountPending,
	}
}

func TestCreateProvisionsAccount(t *testing.T) {
	t.Parallel()

	accounts := newFakeAccounts()
	service, _ := newService(accounts)

	created, err := service.Create(hrAdminContext(), petrova())
	require.NoError(t, err)

	require.Equal(t, employeedmn.AccountEnabled, created.Fields.AccountState)
	require.NotNil(t, created.Fields.AccountUserID)
	require.Equal(t, int32(2), created.Revision, "the account result is a revision of its own")

	account := accounts.byID[*created.Fields.AccountUserID]
	require.NotNil(t, account)
	require.True(t, account.Enabled)
	require.Equal(t, "m.petrova", account.Username)
	require.Equal(t, "Maria", account.FirstName)
	require.Equal(t, "Petrova", account.LastName)
	require.Equal(t, 1, accounts.creates)
}

func TestCreateWhileKeycloakIsDownStaysPending(t *testing.T) {
	t.Parallel()

	accounts := newFakeAccounts()
	accounts.down = true
	service, repo := newService(accounts)
	ctx := hrAdminContext()

	_, err := service.Create(ctx, petrova())
	require.ErrorIs(t, err, domains.ErrUnavailable)
	require.ErrorContains(t, err, "SyncAccount")

	stored, err := service.Get(ctx, 1, false)
	require.NoError(t, err, "the record is stored before the account is created")
	require.Equal(t, employeedmn.AccountPending, stored.Fields.AccountState)
	require.Nil(t, stored.Fields.AccountUserID)
	require.Len(t, repo.revisions[1], 1)

	accounts.down = false

	synced, err := service.SyncAccount(ctx, 1)
	require.NoError(t, err)
	require.Equal(t, employeedmn.AccountEnabled, synced.Fields.AccountState)
	require.Equal(t, 1, accounts.creates)

	again, err := service.SyncAccount(ctx, 1)
	require.NoError(t, err)
	require.Equal(t, synced.Revision, again.Revision, "a repeated sync changes nothing")
	require.Equal(t, 1, accounts.creates, "a second account is never created")
}

func TestSyncAccountAdoptsInterruptedCreation(t *testing.T) {
	t.Parallel()

	accounts := newFakeAccounts()
	accounts.add(keycloak.Account{ID: "left-over", Username: "m.petrova", Email: "m.petrova@example.org", Enabled: false})
	service, _ := newService(accounts)

	created, err := service.Create(hrAdminContext(), petrova())
	require.NoError(t, err)
	require.Equal(t, 0, accounts.creates, "the account with the username and the email is adopted")
	require.Equal(t, "left-over", *created.Fields.AccountUserID)
	require.True(t, accounts.byID["left-over"].Enabled)
}

func TestForeignAccountWithTheUsernameIsAConflict(t *testing.T) {
	t.Parallel()

	accounts := newFakeAccounts()
	accounts.add(keycloak.Account{ID: "foreign", Username: "m.petrova", Email: "someone.else@example.org", Enabled: true})
	service, _ := newService(accounts)
	ctx := hrAdminContext()

	_, err := service.Create(ctx, petrova())
	require.ErrorIs(t, err, domains.ErrFailedPrecondition)
	require.ErrorContains(t, err, "belongs to another account")

	stored, err := service.Get(ctx, 1, false)
	require.NoError(t, err)
	require.Equal(t, employeedmn.AccountPending, stored.Fields.AccountState)
	require.Equal(t, 0, accounts.creates)
}

func TestDismissDisablesAccount(t *testing.T) {
	t.Parallel()

	accounts := newFakeAccounts()
	service, _ := newService(accounts)
	ctx := hrAdminContext()

	created, err := service.Create(ctx, petrova())
	require.NoError(t, err)

	dismissed, err := service.Dismiss(ctx, created.ID, time.Date(2026, 12, 31, 0, 0, 0, 0, time.UTC))
	require.NoError(t, err)
	require.Equal(t, employeedmn.StateDismissed, dismissed.Fields.EmploymentState)
	require.Equal(t, employeedmn.AccountDisabled, dismissed.Fields.AccountState)
	require.Equal(t, *created.Fields.AccountUserID, *dismissed.Fields.AccountUserID, "the link survives the dismissal")
	require.False(t, accounts.byID[*dismissed.Fields.AccountUserID].Enabled)
}

func TestDismissWhileKeycloakIsDownKeepsTheDismissal(t *testing.T) {
	t.Parallel()

	accounts := newFakeAccounts()
	service, _ := newService(accounts)
	ctx := hrAdminContext()

	created, err := service.Create(ctx, petrova())
	require.NoError(t, err)

	accounts.down = true

	_, err = service.Dismiss(ctx, created.ID, time.Date(2026, 12, 31, 0, 0, 0, 0, time.UTC))
	require.ErrorIs(t, err, domains.ErrUnavailable)

	stored, err := service.Get(ctx, created.ID, false)
	require.NoError(t, err)
	require.Equal(t, employeedmn.StateDismissed, stored.Fields.EmploymentState)
	require.Equal(t, employeedmn.AccountPending, stored.Fields.AccountState)
	require.True(t, accounts.byID[*created.Fields.AccountUserID].Enabled, "the account is still enabled")

	accounts.down = false

	synced, err := service.SyncAccount(ctx, created.ID)
	require.NoError(t, err)
	require.Equal(t, employeedmn.AccountDisabled, synced.Fields.AccountState)
	require.False(t, accounts.byID[*created.Fields.AccountUserID].Enabled)
}

func TestDeleteNeedsTheDismissalFirst(t *testing.T) {
	t.Parallel()

	accounts := newFakeAccounts()
	service, _ := newService(accounts)
	ctx := hrAdminContext()

	created, err := service.Create(ctx, petrova())
	require.NoError(t, err)

	_, err = service.Delete(ctx, created.ID)
	require.ErrorIs(t, err, domains.ErrFailedPrecondition)

	_, err = service.Dismiss(ctx, created.ID, time.Date(2026, 12, 31, 0, 0, 0, 0, time.UTC))
	require.NoError(t, err)

	deleted, err := service.Delete(ctx, created.ID)
	require.NoError(t, err)
	require.True(t, deleted.IsDeleted)
}

func TestUpdatePassesNamesAndEmailToTheAccount(t *testing.T) {
	t.Parallel()

	accounts := newFakeAccounts()
	service, _ := newService(accounts)
	ctx := hrAdminContext()

	created, err := service.Create(ctx, petrova())
	require.NoError(t, err)
	require.Equal(t, 1, accounts.updates)

	fields := petrova()
	fields.Email = "maria.petrova@example.org"

	_, err = service.Update(ctx, &record.UpdateRequest[employeedmn.Fields]{ID: created.ID, Fields: *fields, UpdateMask: "email"})
	require.NoError(t, err)
	require.Equal(t, "maria.petrova@example.org", accounts.byID[*created.Fields.AccountUserID].Email)
	require.Equal(t, 2, accounts.updates)

	fields.HireDate = time.Date(2026, 11, 9, 0, 0, 0, 0, time.UTC)

	_, err = service.Update(ctx, &record.UpdateRequest[employeedmn.Fields]{ID: created.ID, Fields: *fields, UpdateMask: "hire_date"})
	require.NoError(t, err)
	require.Equal(t, 2, accounts.updates, "a change outside the names and the email does not reach Keycloak")
}
