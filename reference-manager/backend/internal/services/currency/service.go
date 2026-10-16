package currencysrv

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"uuid"

	"github.com/wI2L/jsondiff"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/actor"
)

//go:generate go tool mockgen -source=service.go -destination=mocks/service.go -package=mocks
type TxManager interface {
	Do(ctx context.Context, fn func(ctx context.Context) error) error
}

type CurrencyRepository interface {
	CreateCurrency(ctx context.Context, m *currencydmn.Currency) (int64, error)
	UpdateCurrency(ctx context.Context, m *currencydmn.Currency) error
	DeleteCurrency(ctx context.Context, currencyID int64) error
}

type CurrencyVersionRepository interface {
	CreateCurrencyRevision(ctx context.Context, m *currencydmn.CurrencyRevision) error
	GetCurrencyRevision(ctx context.Context, currencyID int64, revisionNumber int32) (*currencydmn.CurrencyRevision, error)
	ListCurrencyRevisions(ctx context.Context, query *currencydmn.RevisionListQuery) ([]*currencydmn.CurrencyRevision, error)
}

type ExpandedCurrencyRepository interface {
	GetExpandedCurrency(ctx context.Context, currencyID int64) (*currencydmn.ExpandedCurrency, error)
	ListExpandedCurrencies(ctx context.Context, query *currencydmn.ListQuery) ([]*currencydmn.ExpandedCurrency, error)
}

type Service struct {
	txManager                  TxManager
	currencyRepository         CurrencyRepository
	currencyVersionRepository  CurrencyVersionRepository
	expandedCurrencyRepository ExpandedCurrencyRepository
}

func NewService(
	txManager TxManager,
	currencyRepository CurrencyRepository,
	currencyVersionRepository CurrencyVersionRepository,
	expandedCurrencyRepository ExpandedCurrencyRepository,
) *Service {
	return &Service{
		txManager:                  txManager,
		currencyRepository:         currencyRepository,
		currencyVersionRepository:  currencyVersionRepository,
		expandedCurrencyRepository: expandedCurrencyRepository,
	}
}

func (s *Service) CreateCurrency(ctx context.Context, currency *currencydmn.Currency) (*currencydmn.ExpandedCurrency, error) {
	changer, ok := actor.UserIDFromContext(ctx)
	if !ok {
		return nil, domains.ErrUnauthenticated
	}

	change, err := creationPatch(currency)
	if err != nil {
		return nil, fmt.Errorf("build creation patch: %w", err)
	}

	var created *currencydmn.ExpandedCurrency
	err = s.txManager.Do(ctx, func(ctx context.Context) error {
		currencyID, err := s.currencyRepository.CreateCurrency(ctx, currency)
		if err != nil {
			return fmt.Errorf("create currency: %w", err)
		}

		err = s.currencyVersionRepository.CreateCurrencyRevision(ctx, &currencydmn.CurrencyRevision{
			CurrencyID:     currencyID,
			RevisionNumber: 1,
			Change:         change,
			ChangedBy:      changer,
		})
		if err != nil {
			return fmt.Errorf("create currency revision: %w", err)
		}

		created, err = s.expandedCurrencyRepository.GetExpandedCurrency(ctx, currencyID)
		if err != nil {
			return fmt.Errorf("get expanded currency: %w", err)
		}

		return nil
	})
	if err != nil {
		return nil, err
	}

	return created, nil
}

func (s *Service) GetCurrency(ctx context.Context, currencyID int64, allowDeleted bool) (*currencydmn.ExpandedCurrency, error) {
	if _, ok := actor.UserIDFromContext(ctx); !ok {
		return nil, domains.ErrUnauthenticated
	}

	return s.getCurrency(ctx, currencyID, allowDeleted)
}

func (s *Service) ListCurrencies(ctx context.Context, request *currencydmn.ListRequest) (*currencydmn.ListPage, error) {
	if _, ok := actor.UserIDFromContext(ctx); !ok {
		return nil, domains.ErrUnauthenticated
	}

	query, token, err := listQuery(request)
	if err != nil {
		return nil, err
	}

	pageSize := query.Limit

	// One extra currency is requested to find out whether there is a next page.
	query.Limit++

	currencies, err := s.expandedCurrencyRepository.ListExpandedCurrencies(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("list expanded currencies: %w", err)
	}

	page := &currencydmn.ListPage{}
	page.Currencies, page.NextPageToken = cutPage(currencies, pageSize, token)

	return page, nil
}

// ExportCurrencies returns all active currencies in creation order.
func (s *Service) ExportCurrencies(ctx context.Context) ([]*currencydmn.ExpandedCurrency, error) {
	if _, ok := actor.UserIDFromContext(ctx); !ok {
		return nil, domains.ErrUnauthenticated
	}

	// The query has no limit: the currency reference is small enough to be exported at once.
	currencies, err := s.expandedCurrencyRepository.ListExpandedCurrencies(ctx, &currencydmn.ListQuery{})
	if err != nil {
		return nil, fmt.Errorf("list expanded currencies: %w", err)
	}

	return currencies, nil
}

// GetCurrencyRevision returns a revision of a currency, revisions of deleted currencies are hidden unless allowed.
func (s *Service) GetCurrencyRevision(
	ctx context.Context,
	currencyID int64,
	revisionNumber int32,
	allowDeleted bool,
) (*currencydmn.CurrencyRevision, error) {
	if _, ok := actor.UserIDFromContext(ctx); !ok {
		return nil, domains.ErrUnauthenticated
	}

	if _, err := s.getCurrency(ctx, currencyID, allowDeleted); err != nil {
		return nil, err
	}

	revision, err := s.currencyVersionRepository.GetCurrencyRevision(ctx, currencyID, revisionNumber)
	if err != nil {
		if errors.Is(err, domains.ErrNotFound) {
			return nil, fmt.Errorf("get currency revision %d: %w", revisionNumber, domains.ErrRevisionNotFound)
		}

		return nil, fmt.Errorf("get currency revision: %w", err)
	}

	return revision, nil
}

// ListCurrencyRevisions returns a page of revisions of a currency, revisions of deleted currencies are hidden unless allowed.
func (s *Service) ListCurrencyRevisions(
	ctx context.Context,
	request *currencydmn.RevisionListRequest,
) (*currencydmn.RevisionListPage, error) {
	if _, ok := actor.UserIDFromContext(ctx); !ok {
		return nil, domains.ErrUnauthenticated
	}

	query, token, err := revisionListQuery(request)
	if err != nil {
		return nil, err
	}

	if _, err := s.getCurrency(ctx, request.CurrencyID, request.AllowDeleted); err != nil {
		return nil, err
	}

	pageSize := query.Limit

	// One extra revision is requested to find out whether there is a next page.
	query.Limit++

	revisions, err := s.currencyVersionRepository.ListCurrencyRevisions(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("list currency revisions: %w", err)
	}

	page := &currencydmn.RevisionListPage{}
	page.Revisions, page.NextPageToken = cutPage(revisions, pageSize, token)

	return page, nil
}

func (s *Service) UpdateCurrency(ctx context.Context, request *currencydmn.UpdateRequest) (*currencydmn.ExpandedCurrency, error) {
	changer, ok := actor.UserIDFromContext(ctx)
	if !ok {
		return nil, domains.ErrUnauthenticated
	}

	fields, err := parseUpdateMask(request.UpdateMask)
	if err != nil {
		return nil, err
	}

	var updated *currencydmn.ExpandedCurrency
	err = s.txManager.Do(ctx, func(ctx context.Context) error {
		current, err := s.getCurrency(ctx, request.CurrencyID, false)
		if err != nil {
			return err
		}

		currency := current.Currency()
		applyUpdateMask(currency, request.Currency, fields)

		updated, err = s.changeCurrency(ctx, current, currency, changer)

		return err
	})
	if err != nil {
		return nil, err
	}

	return updated, nil
}

// DeleteCurrency soft-deletes a currency, the deletion is recorded as a revision.
func (s *Service) DeleteCurrency(ctx context.Context, currencyID int64) (*currencydmn.ExpandedCurrency, error) {
	changer, ok := actor.UserIDFromContext(ctx)
	if !ok {
		return nil, domains.ErrUnauthenticated
	}

	var deleted *currencydmn.ExpandedCurrency
	err := s.txManager.Do(ctx, func(ctx context.Context) error {
		current, err := s.getCurrency(ctx, currencyID, false)
		if err != nil {
			return err
		}

		currency := current.Currency()
		currency.IsDeleted = true

		deleted, err = s.changeCurrency(ctx, current, currency, changer)

		return err
	})
	if err != nil {
		return nil, err
	}

	return deleted, nil
}

// PurgeCurrency permanently removes a currency together with its revisions, deleted currencies included.
func (s *Service) PurgeCurrency(ctx context.Context, currencyID int64) error {
	if _, ok := actor.UserIDFromContext(ctx); !ok {
		return domains.ErrUnauthenticated
	}

	if err := s.currencyRepository.DeleteCurrency(ctx, currencyID); err != nil {
		return fmt.Errorf("delete currency: %w", err)
	}

	return nil
}

func (s *Service) getCurrency(ctx context.Context, currencyID int64, allowDeleted bool) (*currencydmn.ExpandedCurrency, error) {
	currency, err := s.expandedCurrencyRepository.GetExpandedCurrency(ctx, currencyID)
	if err != nil {
		return nil, fmt.Errorf("get expanded currency: %w", err)
	}

	// Soft-deleted currencies are hidden unless the caller explicitly asks for them.
	if currency.IsDeleted && !allowDeleted {
		return nil, fmt.Errorf("currency %d is deleted: %w", currencyID, domains.ErrNotFound)
	}

	return currency, nil
}

// changeCurrency stores the new state of the current currency with the next revision, it has to run in a transaction.
// The current currency is returned as is when nothing has changed.
func (s *Service) changeCurrency(
	ctx context.Context,
	current *currencydmn.ExpandedCurrency,
	currency *currencydmn.Currency,
	changer uuid.UUID,
) (*currencydmn.ExpandedCurrency, error) {
	patch, err := jsondiff.Compare(current.Currency().Snapshot(), currency.Snapshot())
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

	if err := s.currencyRepository.UpdateCurrency(ctx, currency); err != nil {
		return nil, fmt.Errorf("update currency: %w", err)
	}

	err = s.currencyVersionRepository.CreateCurrencyRevision(ctx, &currencydmn.CurrencyRevision{
		CurrencyID:     current.ID,
		RevisionNumber: current.Revision + 1,
		Change:         change,
		ChangedBy:      changer,
	})
	if err != nil {
		// The revision number is taken when another request has changed the currency since it was read.
		if errors.Is(err, domains.ErrAlreadyExists) {
			return nil, fmt.Errorf("create currency revision %d: %w", current.Revision+1, domains.ErrConflict)
		}

		return nil, fmt.Errorf("create currency revision: %w", err)
	}

	changed, err := s.expandedCurrencyRepository.GetExpandedCurrency(ctx, current.ID)
	if err != nil {
		return nil, fmt.Errorf("get expanded currency: %w", err)
	}

	return changed, nil
}

// creationPatch describes a newly created currency as a JSON Patch (RFC 6902) against an empty document.
func creationPatch(c *currencydmn.Currency) (json.RawMessage, error) {
	patch, err := jsondiff.Compare(map[string]any{}, c.Snapshot())
	if err != nil {
		return nil, err
	}

	return json.Marshal(patch)
}
