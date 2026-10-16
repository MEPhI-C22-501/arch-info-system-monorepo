package currencyhndl

import (
	"context"
	"errors"
	"net/http"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	currencyv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/currency"
	"github.com/go-chi/render"
)

//go:generate go tool mockgen -source=handler.go -destination=mocks/service.go -package=mocks
type Service interface {
	CreateCurrency(ctx context.Context, currency *currencydmn.Currency) (*currencydmn.ExpandedCurrency, error)
}

type Handler struct {
	currencyv1.Unimplemented

	service Service
}

func NewHandler(service Service) *Handler {
	return &Handler{
		service: service,
	}
}

func (h *Handler) CreateCurrency(w http.ResponseWriter, r *http.Request) {
	var currency currencyv1.Currency
	if err := render.DecodeJSON(r.Body, &currency); err != nil {
		render.Status(r, http.StatusBadRequest)
		render.JSON(w, r, currencyv1.Error{Message: "failed to decode request"})

		return
	}

	created, err := h.service.CreateCurrency(r.Context(), currencyToModel(&currency))
	if err != nil {
		apiErr, status := errorToAPI(err)

		render.Status(r, status)
		render.JSON(w, r, apiErr)

		return
	}

	render.Status(r, http.StatusCreated)
	render.JSON(w, r, expandedCurrencyToAPI(created))
}

func currencyToModel(c *currencyv1.Currency) *currencydmn.Currency {
	return &currencydmn.Currency{
		Code:      c.Code,
		Number:    c.Number,
		Name:      c.Name,
		Decimals:  c.Decimals,
		IsDeleted: c.IsDeleted,
	}
}

func expandedCurrencyToAPI(c *currencydmn.ExpandedCurrency) *currencyv1.ExpandedCurrency {
	return &currencyv1.ExpandedCurrency{
		Code:        c.Code,
		Number:      c.Number,
		Name:        c.Name,
		Decimals:    c.Decimals,
		IsDeleted:   c.IsDeleted,
		Revision:    c.Revision,
		LastChanger: c.LastChanger,
		CreatedAt:   c.CreatedAt,
		UpdatedAt:   c.UpdatedAt,
		DeletedAt:   c.DeletedAt,
	}
}

func errorToAPI(err error) (currencyv1.Error, int) {
	switch {
	case errors.Is(err, domains.ErrAlreadyExists):
		return currencyv1.Error{Message: "currency already exists"}, http.StatusConflict
	case errors.Is(err, domains.ErrNotFound):
		return currencyv1.Error{Message: "currency not found"}, http.StatusNotFound
	default:
		return currencyv1.Error{Message: "internal server error"}, http.StatusInternalServerError
	}
}
