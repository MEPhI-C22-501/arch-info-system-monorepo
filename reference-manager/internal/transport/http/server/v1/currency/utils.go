package currencyhndl

import (
	"errors"
	"net/http"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	currencyv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/currency"
)

func currencyToModel(fromAPI *currencyv1.Currency) *currencydmn.Currency {
	return &currencydmn.Currency{
		Code:     fromAPI.Code,
		Number:   fromAPI.Number,
		Name:     fromAPI.Name,
		Decimals: fromAPI.Decimals,
	}
}

func expandedCurrencyToAPI(fromModel *currencydmn.ExpandedCurrency) *currencyv1.ExpandedCurrency {
	return &currencyv1.ExpandedCurrency{
		Code:        fromModel.Code,
		Number:      fromModel.Number,
		Name:        fromModel.Name,
		Decimals:    fromModel.Decimals,
		Revision:    fromModel.Revision,
		LastChanger: fromModel.LastChanger,
		IsDeleted:   fromModel.IsDeleted,
		CreatedAt:   fromModel.CreatedAt,
		UpdatedAt:   fromModel.UpdatedAt,
		DeletedAt:   fromModel.DeletedAt,
	}
}

func errToAPI(err error) (currencyv1.Error, int) {
	switch {
	case errors.Is(err, domains.ErrAlreadyExists):
		return currencyv1.Error{Message: "currency already exists"}, http.StatusConflict

	default:
		return currencyv1.Error{Message: "internal server error"}, http.StatusInternalServerError
	}
}
