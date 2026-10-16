package currencysrv

import (
	"context"
	"encoding/json"
	"fmt"

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
}

type CurrencyVersionRepository interface {
	CreateCurrencyRevision(ctx context.Context, m *currencydmn.CurrencyRevision) error
}

type ExpandedCurrencyRepository interface {
	GetExpandedCurrency(ctx context.Context, currencyID int64) (*currencydmn.ExpandedCurrency, error)
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

// creationPatch describes a newly created currency as a JSON Patch (RFC 6902) against an empty document.
func creationPatch(c *currencydmn.Currency) (json.RawMessage, error) {
	patch, err := jsondiff.Compare(map[string]any{}, c.Snapshot())
	if err != nil {
		return nil, err
	}

	return json.Marshal(patch)
}
