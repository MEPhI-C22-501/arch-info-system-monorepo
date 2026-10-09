package currencyhndl

import (
	"context"
	"net/http"

	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	currencyv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/currency"
	"github.com/go-chi/render"
)

//go:generate go run go.uber.org/mock/mockgen -source=handler.go -destination=mocks/service.go -package=mocks
type Service interface {
	CreateCurrency(ctx context.Context, currency *currencydmn.Currency) (*currencydmn.ExpandedCurrency, error)
}

type Handler struct {
	service Service
}

func NewHandler(service Service) *Handler {
	return &Handler{
		service: service,
	}
}

// CreateCurrency implements [currencyv1.ServerInterface].
func (h *Handler) CreateCurrency(w http.ResponseWriter, r *http.Request) {
	var currency currencyv1.Currency
	if err := render.DecodeJSON(r.Body, &currency); err != nil {
		render.Status(r, http.StatusBadRequest)
		render.JSON(w, r, currencyv1.Error{Message: "failed to decode http request body"})

		return
	}

	created, err := h.service.CreateCurrency(r.Context(), currencyToModel(&currency))
	if err != nil {
		apiErr, status := errToAPI(err)

		render.Status(r, status)
		render.JSON(w, r, apiErr)

		return
	}

	render.Status(r, http.StatusCreated)
	render.JSON(w, r, expandedCurrencyToAPI(created))
}

// DeleteCurrency implements [currencyv1.ServerInterface].
func (h *Handler) DeleteCurrency(w http.ResponseWriter, r *http.Request, currencyID currencyv1.CurrencyID, params currencyv1.DeleteCurrencyParams) {
	panic("unimplemented")
}

// ExportCurrencies implements [currencyv1.ServerInterface].
func (h *Handler) ExportCurrencies(w http.ResponseWriter, r *http.Request) {
	panic("unimplemented")
}

// GetCurrency implements [currencyv1.ServerInterface].
func (h *Handler) GetCurrency(w http.ResponseWriter, r *http.Request, currencyID currencyv1.CurrencyID, params currencyv1.GetCurrencyParams) {
	panic("unimplemented")
}

// GetCurrencyRevision implements [currencyv1.ServerInterface].
func (h *Handler) GetCurrencyRevision(w http.ResponseWriter, r *http.Request, currencyID currencyv1.CurrencyID, revisionNumber currencyv1.RevisionNumber) {
	panic("unimplemented")
}

// ListCurrencies implements [currencyv1.ServerInterface].
func (h *Handler) ListCurrencies(w http.ResponseWriter, r *http.Request, params currencyv1.ListCurrenciesParams) {
	panic("unimplemented")
}

// ListCurrencyRevisions implements [currencyv1.ServerInterface].
func (h *Handler) ListCurrencyRevisions(w http.ResponseWriter, r *http.Request, currencyID currencyv1.CurrencyID, params currencyv1.ListCurrencyRevisionsParams) {
	panic("unimplemented")
}

// UpdateCurrency implements [currencyv1.ServerInterface].
func (h *Handler) UpdateCurrency(w http.ResponseWriter, r *http.Request, currencyID currencyv1.CurrencyID, params currencyv1.UpdateCurrencyParams) {
	panic("unimplemented")
}
