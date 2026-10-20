// Package recordsrv implements the standard methods of a catalog (List, Get, Create, Update, Delete, revisions,
// export) once for every catalog described by a record.Descriptor. Catalog-specific rules come from the descriptor,
// catalog-specific methods wrap the service (see the employee service).
package recordsrv

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"reflect"
	"uuid"

	"github.com/wI2L/jsondiff"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/access"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
)

type TxManager interface {
	Do(ctx context.Context, fn func(ctx context.Context) error) error
}

// DB gives the validators of a catalog access to the storage inside the write transaction.
type DB interface {
	Querier(ctx context.Context) postgres.Querier
}

type Repository[F any] interface {
	Create(ctx context.Context, m *record.Record[F]) (int64, error)
	Update(ctx context.Context, m *record.Record[F]) error
	Delete(ctx context.Context, id int64) error
	GetExpanded(ctx context.Context, id int64) (*record.Expanded[F], error)
	ListExpanded(ctx context.Context, query *record.ListQuery) ([]*record.Expanded[F], error)
}

type RevisionRepository interface {
	CreateRevision(ctx context.Context, m *record.Revision) error
	GetRevision(ctx context.Context, recordID int64, revisionNumber int32) (*record.Revision, error)
	ListRevisions(ctx context.Context, query *record.RevisionListQuery) ([]*record.Revision, error)
}

// Service serves one catalog, F is the fields struct of the catalog.
type Service[F any] struct {
	desc      *record.Descriptor[F]
	txManager TxManager
	db        DB
	records   Repository[F]
	revisions RevisionRepository

	fields    listFields
	updatable []string
}

func NewService[F any](
	desc *record.Descriptor[F],
	txManager TxManager,
	db DB,
	records Repository[F],
	revisions RevisionRepository,
) *Service[F] {
	return &Service[F]{
		desc:      desc,
		txManager: txManager,
		db:        db,
		records:   records,
		revisions: revisions,
		fields:    recordListFields(desc),
		updatable: desc.UpdatableFields(),
	}
}

// Descriptor returns the descriptor of the catalog the service serves.
func (s *Service[F]) Descriptor() *record.Descriptor[F] {
	return s.desc
}

// Create validates the fields, stores the record with its first revision and returns it expanded.
func (s *Service[F]) Create(ctx context.Context, fields *F) (*record.Expanded[F], error) {
	changer, err := s.authorize(ctx, access.LevelCreate)
	if err != nil {
		return nil, err
	}

	m := &record.Record[F]{Fields: *fields}
	if err := record.ValidateFields(s.desc, &m.Fields); err != nil {
		return nil, err
	}

	change, err := s.creationPatch(m)
	if err != nil {
		return nil, fmt.Errorf("build creation patch: %w", err)
	}

	var created *record.Expanded[F]
	err = s.txManager.Do(ctx, func(ctx context.Context) error {
		if err := s.validate(ctx, m, nil); err != nil {
			return err
		}

		id, err := s.records.Create(ctx, m)
		if err != nil {
			return fmt.Errorf("create %s: %w", s.desc.Singular, err)
		}

		err = s.revisions.CreateRevision(ctx, &record.Revision{
			RecordID:       id,
			RevisionNumber: 1,
			Change:         change,
			ChangedBy:      changer,
		})
		if err != nil {
			return fmt.Errorf("create %s revision: %w", s.desc.Singular, err)
		}

		created, err = s.records.GetExpanded(ctx, id)
		if err != nil {
			return fmt.Errorf("get expanded %s: %w", s.desc.Singular, err)
		}

		return nil
	})
	if err != nil {
		return nil, err
	}

	return created, nil
}

func (s *Service[F]) Get(ctx context.Context, id int64, allowDeleted bool) (*record.Expanded[F], error) {
	if _, err := s.authorize(ctx, access.LevelRead); err != nil {
		return nil, err
	}

	return s.get(ctx, id, allowDeleted)
}

func (s *Service[F]) List(ctx context.Context, request *record.ListRequest) (*record.ListPage[F], error) {
	if _, err := s.authorize(ctx, access.LevelRead); err != nil {
		return nil, err
	}

	query, token, err := listQuery(s.fields, request)
	if err != nil {
		return nil, err
	}

	pageSize := query.Limit

	// one extra record is requested to find out whether there is a next page
	query.Limit++

	records, err := s.records.ListExpanded(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("list expanded %s: %w", s.desc.Plural, err)
	}

	page := &record.ListPage[F]{}
	page.Records, page.NextPageToken = cutPage(records, pageSize, token)

	return page, nil
}

// Export returns all active records in creation order, the catalogs are small enough to be exported at once.
func (s *Service[F]) Export(ctx context.Context) ([]*record.Expanded[F], error) {
	if _, err := s.authorize(ctx, access.LevelExecute); err != nil {
		return nil, err
	}

	records, err := s.records.ListExpanded(ctx, &record.ListQuery{})
	if err != nil {
		return nil, fmt.Errorf("list expanded %s: %w", s.desc.Plural, err)
	}

	return records, nil
}

// GetRevision returns a revision of a record, revisions of deleted records are hidden unless allowed.
func (s *Service[F]) GetRevision(ctx context.Context, id int64, revisionNumber int32, allowDeleted bool) (*record.Revision, error) {
	if _, err := s.authorize(ctx, access.LevelRead); err != nil {
		return nil, err
	}

	if _, err := s.get(ctx, id, allowDeleted); err != nil {
		return nil, err
	}

	revision, err := s.revisions.GetRevision(ctx, id, revisionNumber)
	if err != nil {
		if errors.Is(err, domains.ErrNotFound) {
			return nil, fmt.Errorf("get %s revision %d: %w", s.desc.Singular, revisionNumber, domains.ErrRevisionNotFound)
		}

		return nil, fmt.Errorf("get %s revision: %w", s.desc.Singular, err)
	}

	return revision, nil
}

// ListRevisions returns a page of revisions of a record, revisions of deleted records are hidden unless allowed.
func (s *Service[F]) ListRevisions(ctx context.Context, request *record.RevisionListRequest) (*record.RevisionListPage, error) {
	if _, err := s.authorize(ctx, access.LevelRead); err != nil {
		return nil, err
	}

	query, token, err := revisionListQuery(request)
	if err != nil {
		return nil, err
	}

	if _, err := s.get(ctx, request.RecordID, request.AllowDeleted); err != nil {
		return nil, err
	}

	pageSize := query.Limit

	// one extra revision is requested to find out whether there is a next page
	query.Limit++

	revisions, err := s.revisions.ListRevisions(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("list %s revisions: %w", s.desc.Singular, err)
	}

	page := &record.RevisionListPage{}
	page.Revisions, page.NextPageToken = cutPage(revisions, pageSize, token)

	return page, nil
}

// Update changes the masked fields of a record and records the difference as a revision.
func (s *Service[F]) Update(ctx context.Context, request *record.UpdateRequest[F]) (*record.Expanded[F], error) {
	changer, err := s.authorize(ctx, access.LevelUpdate)
	if err != nil {
		return nil, err
	}

	fields, err := parseUpdateMask(request.UpdateMask, s.updatable)
	if err != nil {
		return nil, err
	}

	return s.modify(ctx, request.ID, changer, func(m *record.Record[F]) error {
		return s.applyUpdateMask(&m.Fields, &request.Fields, fields)
	})
}

// Delete soft-deletes a record, the deletion is recorded as a revision.
func (s *Service[F]) Delete(ctx context.Context, id int64) (*record.Expanded[F], error) {
	changer, err := s.authorize(ctx, access.LevelDelete)
	if err != nil {
		return nil, err
	}

	return s.modify(ctx, id, changer, func(m *record.Record[F]) error {
		m.IsDeleted = true
		return nil
	})
}

// Purge permanently removes a record together with its revisions, deleted records included.
func (s *Service[F]) Purge(ctx context.Context, id int64) error {
	if _, err := s.authorize(ctx, access.LevelDelete); err != nil {
		return err
	}

	if err := s.records.Delete(ctx, id); err != nil {
		return fmt.Errorf("delete %s: %w", s.desc.Singular, err)
	}

	return nil
}

// Modify changes an active record on behalf of the changer without an access check, so that a catalog-specific
// method that has authorized its own operation can change records of this catalog in the same transaction.
func (s *Service[F]) Modify(ctx context.Context, id int64, changer uuid.UUID, mutate func(m *record.Record[F]) error) (*record.Expanded[F], error) {
	return s.modify(ctx, id, changer, mutate)
}

// ListAll returns every record matching the query without paging, for catalog-specific methods.
func (s *Service[F]) ListAll(ctx context.Context, filter string, allowDeleted bool) ([]*record.Expanded[F], error) {
	query, _, err := listQuery(s.fields, &record.ListRequest{Filter: filter, AllowDeleted: allowDeleted})
	if err != nil {
		return nil, err
	}

	query.Limit = 0

	records, err := s.records.ListExpanded(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("list expanded %s: %w", s.desc.Plural, err)
	}

	return records, nil
}

// Authorize checks that the caller may perform an operation of the level on the catalog and returns its user ID.
func (s *Service[F]) Authorize(ctx context.Context, level access.Level) (uuid.UUID, error) {
	return s.authorize(ctx, level)
}

func (s *Service[F]) authorize(ctx context.Context, level access.Level) (uuid.UUID, error) {
	a, err := access.Authorize(ctx, s.desc.Group, level)
	if err != nil {
		return uuid.UUID{}, err
	}

	return a.UserID, nil
}

func (s *Service[F]) get(ctx context.Context, id int64, allowDeleted bool) (*record.Expanded[F], error) {
	m, err := s.records.GetExpanded(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("get expanded %s: %w", s.desc.Singular, err)
	}

	// soft-deleted records are hidden unless the caller explicitly asks for them
	if m.IsDeleted && !allowDeleted {
		return nil, fmt.Errorf("%s %d is deleted: %w", s.desc.Singular, id, domains.ErrNotFound)
	}

	return m, nil
}

func (s *Service[F]) validate(ctx context.Context, next, prev *record.Record[F]) error {
	if s.desc.Validate == nil {
		return nil
	}

	return s.desc.Validate(ctx, s.db.Querier(ctx), next, prev)
}

// modify loads the active record, lets mutate change it and stores the result with the next revision.
func (s *Service[F]) modify(ctx context.Context, id int64, changer uuid.UUID, mutate func(m *record.Record[F]) error) (*record.Expanded[F], error) {
	var changed *record.Expanded[F]

	err := s.txManager.Do(ctx, func(ctx context.Context) error {
		current, err := s.get(ctx, id, false)
		if err != nil {
			return err
		}

		next := current.Record
		if err := mutate(&next); err != nil {
			return err
		}

		if err := record.ValidateFields(s.desc, &next.Fields); err != nil {
			return err
		}

		if err := s.validate(ctx, &next, &current.Record); err != nil {
			return err
		}

		changed, err = s.change(ctx, current, &next, changer)

		return err
	})
	if err != nil {
		return nil, err
	}

	return changed, nil
}

// change stores the new state of the current record with the next revision, it has to run in a transaction.
// The current record is returned as is when nothing has changed.
func (s *Service[F]) change(ctx context.Context, current *record.Expanded[F], next *record.Record[F], changer uuid.UUID) (*record.Expanded[F], error) {
	patch, err := jsondiff.Compare(s.desc.Snapshot(&current.Record), s.desc.Snapshot(next))
	if err != nil {
		return nil, fmt.Errorf("build change patch: %w", err)
	}

	if len(patch) == 0 {
		return current, nil
	}

	change, err := json.Marshal(patch)
	if err != nil {
		return nil, fmt.Errorf("marshal change patch: %w", err)
	}

	if err := s.records.Update(ctx, next); err != nil {
		return nil, fmt.Errorf("update %s: %w", s.desc.Singular, err)
	}

	err = s.revisions.CreateRevision(ctx, &record.Revision{
		RecordID:       current.ID,
		RevisionNumber: current.Revision + 1,
		Change:         change,
		ChangedBy:      changer,
	})
	if err != nil {
		// the revision number is taken when another request has changed the record since it was read
		if errors.Is(err, domains.ErrAlreadyExists) {
			return nil, fmt.Errorf("create %s revision %d: %w", s.desc.Singular, current.Revision+1, domains.ErrConflict)
		}

		return nil, fmt.Errorf("create %s revision: %w", s.desc.Singular, err)
	}

	changed, err := s.records.GetExpanded(ctx, current.ID)
	if err != nil {
		return nil, fmt.Errorf("get expanded %s: %w", s.desc.Singular, err)
	}

	return changed, nil
}

// creationPatch describes a new record as a JSON Patch (RFC 6902) against an empty document.
func (s *Service[F]) creationPatch(m *record.Record[F]) (json.RawMessage, error) {
	patch, err := jsondiff.Compare(map[string]any{}, s.desc.Snapshot(m))
	if err != nil {
		return nil, err
	}

	return json.Marshal(patch)
}

// applyUpdateMask copies the masked fields from src to dst through the column accessors of the descriptor.
func (s *Service[F]) applyUpdateMask(dst, src *F, fields []string) error {
	for _, name := range fields {
		column, ok := s.desc.Column(name)
		if !ok {
			return &domains.InvalidArgumentError{Argument: "updateMask", Err: fmt.Errorf("unknown field %q", name)}
		}

		target := reflect.ValueOf(column.Ptr(dst)).Elem()
		target.Set(reflect.ValueOf(column.Value(src)))
	}

	return nil
}
