package currencyhndl

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"mime"
	"net/http"
	"strconv"

	"github.com/go-chi/render"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	currencyv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/currency"
)

//go:generate go tool mockgen -source=handler.go -destination=mocks/service.go -package=mocks
type Service interface {
	CreateCurrency(ctx context.Context, currency *currencydmn.Currency) (*currencydmn.ExpandedCurrency, error)
	GetCurrency(ctx context.Context, currencyID int64, allowDeleted bool) (*currencydmn.ExpandedCurrency, error)
	ListCurrencies(ctx context.Context, request *currencydmn.ListRequest) (*currencydmn.ListPage, error)
	ExportCurrencies(ctx context.Context) ([]*currencydmn.ExpandedCurrency, error)
	UpdateCurrency(ctx context.Context, request *currencydmn.UpdateRequest) (*currencydmn.ExpandedCurrency, error)
	DeleteCurrency(ctx context.Context, currencyID int64) (*currencydmn.ExpandedCurrency, error)
	PurgeCurrency(ctx context.Context, currencyID int64) error
	GetCurrencyRevision(
		ctx context.Context,
		currencyID int64,
		revisionNumber int32,
		allowDeleted bool,
	) (*currencydmn.CurrencyRevision, error)
	ListCurrencyRevisions(ctx context.Context, request *currencydmn.RevisionListRequest) (*currencydmn.RevisionListPage, error)
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

func (h *Handler) GetCurrency(
	w http.ResponseWriter,
	r *http.Request,
	currencyID currencyv1.CurrencyID,
	params currencyv1.GetCurrencyParams,
) {
	currency, err := h.service.GetCurrency(r.Context(), currencyID, valueOrZero(params.AllowDeleted))
	if err != nil {
		apiErr, status := errorToAPI(err)

		render.Status(r, status)
		render.JSON(w, r, apiErr)

		return
	}

	render.Status(r, http.StatusOK)
	render.JSON(w, r, expandedCurrencyToAPI(currency))
}

func (h *Handler) ListCurrencies(w http.ResponseWriter, r *http.Request, params currencyv1.ListCurrenciesParams) {
	page, err := h.service.ListCurrencies(r.Context(), listParamsToModel(&params))
	if err != nil {
		apiErr, status := errorToAPI(err)

		render.Status(r, status)
		render.JSON(w, r, apiErr)

		return
	}

	render.Status(r, http.StatusOK)
	render.JSON(w, r, listPageToAPI(page))
}

// ExportCurrencies responds with an Excel file of all active currencies.
func (h *Handler) ExportCurrencies(w http.ResponseWriter, r *http.Request) {
	currencies, err := h.service.ExportCurrencies(r.Context())
	if err != nil {
		apiErr, status := errorToAPI(err)

		render.Status(r, status)
		render.JSON(w, r, apiErr)

		return
	}

	// The file is built in memory first, so that a failure still gets a proper error response.
	var file bytes.Buffer
	if err := writeCurrenciesExcel(&file, currencies); err != nil {
		apiErr, status := errorToAPI(err)

		render.Status(r, status)
		render.JSON(w, r, apiErr)

		return
	}

	w.Header().Set("Content-Type", excelContentType)
	w.Header().Set("Content-Disposition", mime.FormatMediaType("attachment", map[string]string{"filename": exportFileName}))
	w.Header().Set("Content-Length", strconv.Itoa(file.Len()))
	w.WriteHeader(http.StatusOK)
	_, _ = file.WriteTo(w)
}

func (h *Handler) UpdateCurrency(
	w http.ResponseWriter,
	r *http.Request,
	currencyID currencyv1.CurrencyID,
	params currencyv1.UpdateCurrencyParams,
) {
	var currency currencyv1.Currency
	if err := render.DecodeJSON(r.Body, &currency); err != nil {
		render.Status(r, http.StatusBadRequest)
		render.JSON(w, r, currencyv1.Error{Message: "failed to decode request"})

		return
	}

	updated, err := h.service.UpdateCurrency(r.Context(), &currencydmn.UpdateRequest{
		CurrencyID: currencyID,
		Currency:   currencyToModel(&currency),
		UpdateMask: valueOrZero(params.UpdateMask),
	})
	if err != nil {
		apiErr, status := errorToAPI(err)

		render.Status(r, status)
		render.JSON(w, r, apiErr)

		return
	}

	render.Status(r, http.StatusOK)
	render.JSON(w, r, expandedCurrencyToAPI(updated))
}

// DeleteCurrency soft-deletes a currency and returns it, with force the currency is removed permanently without content.
func (h *Handler) DeleteCurrency(
	w http.ResponseWriter,
	r *http.Request,
	currencyID currencyv1.CurrencyID,
	params currencyv1.DeleteCurrencyParams,
) {
	if valueOrZero(params.Force) {
		if err := h.service.PurgeCurrency(r.Context(), currencyID); err != nil {
			apiErr, status := errorToAPI(err)

			render.Status(r, status)
			render.JSON(w, r, apiErr)

			return
		}

		render.NoContent(w, r)

		return
	}

	deleted, err := h.service.DeleteCurrency(r.Context(), currencyID)
	if err != nil {
		apiErr, status := errorToAPI(err)

		render.Status(r, status)
		render.JSON(w, r, apiErr)

		return
	}

	render.Status(r, http.StatusOK)
	render.JSON(w, r, expandedCurrencyToAPI(deleted))
}

func (h *Handler) GetCurrencyRevision(
	w http.ResponseWriter,
	r *http.Request,
	currencyID currencyv1.CurrencyID,
	revisionNumber currencyv1.RevisionNumber,
	params currencyv1.GetCurrencyRevisionParams,
) {
	revision, err := h.service.GetCurrencyRevision(r.Context(), currencyID, revisionNumber, valueOrZero(params.AllowDeleted))
	if err != nil {
		apiErr, status := errorToAPI(err)

		render.Status(r, status)
		render.JSON(w, r, apiErr)

		return
	}

	resp, err := currencyRevisionToAPI(revision)
	if err != nil {
		apiErr, status := errorToAPI(err)

		render.Status(r, status)
		render.JSON(w, r, apiErr)

		return
	}

	render.Status(r, http.StatusOK)
	render.JSON(w, r, resp)
}

func (h *Handler) ListCurrencyRevisions(
	w http.ResponseWriter,
	r *http.Request,
	currencyID currencyv1.CurrencyID,
	params currencyv1.ListCurrencyRevisionsParams,
) {
	page, err := h.service.ListCurrencyRevisions(r.Context(), revisionListParamsToModel(currencyID, &params))
	if err != nil {
		apiErr, status := errorToAPI(err)

		render.Status(r, status)
		render.JSON(w, r, apiErr)

		return
	}

	resp, err := revisionListPageToAPI(page)
	if err != nil {
		apiErr, status := errorToAPI(err)

		render.Status(r, status)
		render.JSON(w, r, apiErr)

		return
	}

	render.Status(r, http.StatusOK)
	render.JSON(w, r, resp)
}

// HandleParamError responds to requests whose path or query parameters could not be parsed.
func (h *Handler) HandleParamError(w http.ResponseWriter, r *http.Request, _ error) {
	render.Status(r, http.StatusBadRequest)
	render.JSON(w, r, currencyv1.Error{Message: "invalid request parameters"})
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

func listParamsToModel(p *currencyv1.ListCurrenciesParams) *currencydmn.ListRequest {
	return &currencydmn.ListRequest{
		PageSize:     valueOrZero(p.PageSize),
		PageToken:    valueOrZero(p.PageToken),
		Filter:       valueOrZero(p.Filter),
		OrderBy:      valueOrZero(p.OrderBy),
		AllowDeleted: valueOrZero(p.AllowDeleted),
	}
}

func listPageToAPI(p *currencydmn.ListPage) *currencyv1.SuccessWithExpandedCurrencies {
	currencies := make([]currencyv1.ExpandedCurrency, 0, len(p.Currencies))
	for _, c := range p.Currencies {
		currencies = append(currencies, *expandedCurrencyToAPI(c))
	}

	resp := &currencyv1.SuccessWithExpandedCurrencies{Currencies: &currencies}
	if p.NextPageToken != "" {
		resp.NextPageToken = &p.NextPageToken
	}

	return resp
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

func revisionListParamsToModel(
	currencyID int64,
	p *currencyv1.ListCurrencyRevisionsParams,
) *currencydmn.RevisionListRequest {
	return &currencydmn.RevisionListRequest{
		CurrencyID:   currencyID,
		PageSize:     valueOrZero(p.PageSize),
		PageToken:    valueOrZero(p.PageToken),
		Filter:       valueOrZero(p.Filter),
		OrderBy:      valueOrZero(p.OrderBy),
		AllowDeleted: valueOrZero(p.AllowDeleted),
	}
}

func revisionListPageToAPI(p *currencydmn.RevisionListPage) (*currencyv1.SuccessWithCurrencyRevisionList, error) {
	revisions := make([]currencyv1.CurrencyRevision, 0, len(p.Revisions))
	for _, revision := range p.Revisions {
		apiRevision, err := currencyRevisionToAPI(revision)
		if err != nil {
			return nil, err
		}

		revisions = append(revisions, *apiRevision)
	}

	resp := &currencyv1.SuccessWithCurrencyRevisionList{Revisions: &revisions}
	if p.NextPageToken != "" {
		resp.NextPageToken = &p.NextPageToken
	}

	return resp, nil
}

func currencyRevisionToAPI(r *currencydmn.CurrencyRevision) (*currencyv1.CurrencyRevision, error) {
	var change []map[string]any
	if err := json.Unmarshal(r.Change, &change); err != nil {
		return nil, fmt.Errorf("unmarshal change of currency revision %d: %w", r.ID, err)
	}

	return &currencyv1.CurrencyRevision{
		Id:             &r.ID,
		CurrencyId:     &r.CurrencyID,
		RevisionNumber: &r.RevisionNumber,
		Change:         &change,
		ChangedBy:      &r.ChangedBy,
		ChangedAt:      &r.ChangedAt,
	}, nil
}

func errorToAPI(err error) (currencyv1.Error, int) {
	var invalidArgErr *domains.InvalidArgumentError

	switch {
	case errors.As(err, &invalidArgErr):
		return currencyv1.Error{Message: invalidArgErr.Error()}, http.StatusBadRequest
	case errors.Is(err, domains.ErrAlreadyExists):
		return currencyv1.Error{Message: "currency already exists"}, http.StatusConflict
	case errors.Is(err, domains.ErrConflict):
		return currencyv1.Error{Message: "currency was modified concurrently, retry the request"}, http.StatusConflict
	case errors.Is(err, domains.ErrUnauthenticated):
		return currencyv1.Error{Message: "unauthenticated"}, http.StatusUnauthorized
	case errors.Is(err, domains.ErrPermissionDenied):
		return currencyv1.Error{Message: "permission denied"}, http.StatusForbidden
	case errors.Is(err, domains.ErrRevisionNotFound):
		return currencyv1.Error{Message: "currency revision not found"}, http.StatusNotFound
	case errors.Is(err, domains.ErrNotFound):
		return currencyv1.Error{Message: "currency not found"}, http.StatusNotFound
	default:
		return currencyv1.Error{Message: "internal server error"}, http.StatusInternalServerError
	}
}

func valueOrZero[T any](v *T) T {
	if v == nil {
		var zero T
		return zero
	}

	return *v
}
