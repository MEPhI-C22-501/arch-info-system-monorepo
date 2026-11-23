package recordsrv

import (
	"context"
	"errors"
	"testing"
	"uuid"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/access"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/actor"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
)

type inlineTx struct{}

func (inlineTx) Do(ctx context.Context, fn func(ctx context.Context) error) error { return fn(ctx) }

type noDB struct{}

func (noDB) Querier(context.Context) postgres.Querier { return nil }

// storedThing keeps one record at revision 1, as both concurrent requests read it.
type storedThing struct{ updated int }

func (s *storedThing) Create(context.Context, *record.Record[fields]) (int64, error) { return 0, nil }
func (s *storedThing) Update(context.Context, *record.Record[fields]) error {
	s.updated++
	return nil
}
func (s *storedThing) Delete(context.Context, int64) error { return nil }
func (s *storedThing) GetExpanded(context.Context, int64) (*record.Expanded[fields], error) {
	return &record.Expanded[fields]{Record: record.Record[fields]{ID: 7, Fields: fields{Code: "c", Name: "old"}}, Revision: 1}, nil
}
func (s *storedThing) ListExpanded(context.Context, *record.ListQuery) ([]*record.Expanded[fields], error) {
	return nil, nil
}

// takenRevision answers as the database does when the other request has already stored revision 2.
type takenRevision struct{}

func (takenRevision) CreateRevision(context.Context, *record.Revision) error {
	return domains.ErrAlreadyExists
}
func (takenRevision) GetRevision(context.Context, int64, int32) (*record.Revision, error) {
	return nil, nil
}
func (takenRevision) ListRevisions(context.Context, *record.RevisionListQuery) ([]*record.Revision, error) {
	return nil, nil
}

// TestConcurrentUpdateIsAConflict covers the quality scenario "concurrent edit" of 075: the second of two
// updates read at the same revision fails with a conflict, so its transaction rolls back and the client retries.
func TestConcurrentUpdateIsAConflict(t *testing.T) {
	t.Parallel()

	admin := &actor.Actor{UserID: uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6"), Roles: []string{access.RoleAdmin}}
	ctx := actor.WithActor(context.Background(), admin)
	store := &storedThing{}
	things := *desc
	things.Snapshot = func(r *record.Record[fields]) any {
		return map[string]any{"code": r.Fields.Code, "name": r.Fields.Name}
	}
	service := NewService(&things, inlineTx{}, noDB{}, store, takenRevision{})

	_, err := service.Update(ctx, &record.UpdateRequest[fields]{ID: 7, UpdateMask: "name", Fields: fields{Code: "c", Name: "new"}})
	if !errors.Is(err, domains.ErrConflict) {
		t.Fatalf("expected a conflict, got %v", err)
	}

	if err.Error() != "create thing revision 2: conflict" {
		t.Fatalf("unexpected error text %q", err.Error())
	}
}
