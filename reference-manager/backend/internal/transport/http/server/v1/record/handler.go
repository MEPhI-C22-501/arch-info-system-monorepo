// Package recordhndl holds the HTTP behavior shared by the generated catalog handlers: decoding, the error
// contract, the common list and revision responses and the .xlsx export.
package recordhndl

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"mime"
	"net/http"
	"strconv"

	"github.com/go-chi/render"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
)

// Error is the error response of every catalog, the same shape the currency API uses.
type Error struct {
	Message string        `json:"message"`
	Details []ErrorDetail `json:"details,omitempty"`
}

type ErrorDetail struct {
	Field   string `json:"field,omitempty"`
	Message string `json:"message"`
}

// ErrorToAPI maps a service error to the response and its status, singular names the catalog in messages.
func ErrorToAPI(err error, singular string) (Error, int) {
	var (
		validationErr *record.ValidationError
		invalidArgErr *domains.InvalidArgumentError
	)

	switch {
	case errors.As(err, &validationErr):
		details := make([]ErrorDetail, 0, len(validationErr.Fields))
		for _, f := range validationErr.Fields {
			details = append(details, ErrorDetail{Field: f.Field, Message: f.Message})
		}

		return Error{Message: "validation failed", Details: details}, http.StatusBadRequest
	case errors.As(err, &invalidArgErr):
		return Error{Message: invalidArgErr.Error()}, http.StatusBadRequest
	case errors.Is(err, domains.ErrAlreadyExists):
		return Error{Message: singular + " already exists"}, http.StatusConflict
	case errors.Is(err, domains.ErrConflict):
		return Error{Message: singular + " was modified concurrently, retry the request"}, http.StatusConflict
	case errors.Is(err, domains.ErrFailedPrecondition):
		return Error{Message: err.Error()}, http.StatusBadRequest
	case errors.Is(err, domains.ErrUnauthenticated):
		return Error{Message: "unauthenticated"}, http.StatusUnauthorized
	case errors.Is(err, domains.ErrPermissionDenied):
		return Error{Message: "permission denied"}, http.StatusForbidden
	case errors.Is(err, domains.ErrRevisionNotFound):
		return Error{Message: singular + " revision not found"}, http.StatusNotFound
	case errors.Is(err, domains.ErrNotFound):
		return Error{Message: singular + " not found"}, http.StatusNotFound
	default:
		return Error{Message: "internal server error"}, http.StatusInternalServerError
	}
}

// RenderError writes the error response of a failed service call.
func RenderError(w http.ResponseWriter, r *http.Request, err error, singular string) {
	apiErr, status := ErrorToAPI(err, singular)

	render.Status(r, status)
	render.JSON(w, r, apiErr)
}

// RenderParamError responds to requests whose path or query parameters could not be parsed.
func RenderParamError(w http.ResponseWriter, r *http.Request, _ error) {
	render.Status(r, http.StatusBadRequest)
	render.JSON(w, r, Error{Message: "invalid request parameters"})
}

// DecodeJSON reads the request body into v, it responds with 400 and returns false on a malformed body.
func DecodeJSON(w http.ResponseWriter, r *http.Request, v any) bool {
	if err := render.DecodeJSON(r.Body, v); err != nil {
		render.Status(r, http.StatusBadRequest)
		render.JSON(w, r, Error{Message: "failed to decode request"})

		return false
	}

	return true
}

// ListRequest builds the service request from the optional list parameters of a generated handler.
func ListRequest(pageSize *int32, pageToken, filter, orderBy *string, allowDeleted *bool) *record.ListRequest {
	return &record.ListRequest{
		PageSize:     ValueOrZero(pageSize),
		PageToken:    ValueOrZero(pageToken),
		Filter:       ValueOrZero(filter),
		OrderBy:      ValueOrZero(orderBy),
		AllowDeleted: ValueOrZero(allowDeleted),
	}
}

// RevisionListRequest builds the service request from the optional revision list parameters of a generated handler.
func RevisionListRequest(recordID int64, pageSize *int32, pageToken, filter, orderBy *string, allowDeleted *bool) *record.RevisionListRequest {
	return &record.RevisionListRequest{
		RecordID:     recordID,
		PageSize:     ValueOrZero(pageSize),
		PageToken:    ValueOrZero(pageToken),
		Filter:       ValueOrZero(filter),
		OrderBy:      ValueOrZero(orderBy),
		AllowDeleted: ValueOrZero(allowDeleted),
	}
}

// ListPageToAPI builds the list response: the records under the collection key and the next page token.
func ListPageToAPI[F, T any](collection string, page *record.ListPage[F], toAPI func(*record.Expanded[F]) T) map[string]any {
	items := make([]T, 0, len(page.Records))
	for _, m := range page.Records {
		items = append(items, toAPI(m))
	}

	resp := map[string]any{collection: items}
	if page.NextPageToken != "" {
		resp["nextPageToken"] = page.NextPageToken
	}

	return resp
}

// RevisionToAPI builds the revision response, column names the record reference field, for example "country_id".
func RevisionToAPI(column string, m *record.Revision) (map[string]any, error) {
	var change []map[string]any
	if err := json.Unmarshal(m.Change, &change); err != nil {
		return nil, fmt.Errorf("unmarshal change of revision %d: %w", m.ID, err)
	}

	return map[string]any{
		"id":              m.ID,
		column:            m.RecordID,
		"revision_number": m.RevisionNumber,
		"change":          change,
		"changed_by":      m.ChangedBy,
		"changed_at":      m.ChangedAt,
	}, nil
}

// RevisionPageToAPI builds the revision list response.
func RevisionPageToAPI(column string, page *record.RevisionListPage) (map[string]any, error) {
	revisions := make([]map[string]any, 0, len(page.Revisions))
	for _, m := range page.Revisions {
		apiRevision, err := RevisionToAPI(column, m)
		if err != nil {
			return nil, err
		}

		revisions = append(revisions, apiRevision)
	}

	resp := map[string]any{"revisions": revisions}
	if page.NextPageToken != "" {
		resp["nextPageToken"] = page.NextPageToken
	}

	return resp, nil
}

// RenderExcel responds with the records as an .xlsx file built from the export columns of the descriptor.
func RenderExcel[F any](w http.ResponseWriter, r *http.Request, desc *record.Descriptor[F], records []*record.Expanded[F]) {
	// the file is built in memory first, so that a failure still gets a proper error response
	var file bytes.Buffer
	if err := writeExcel(&file, desc, records); err != nil {
		RenderError(w, r, err, desc.Singular)
		return
	}

	w.Header().Set("Content-Type", excelContentType)
	w.Header().Set("Content-Disposition", mime.FormatMediaType("attachment", map[string]string{"filename": desc.Plural + ".xlsx"}))
	w.Header().Set("Content-Length", strconv.Itoa(file.Len()))
	w.WriteHeader(http.StatusOK)
	_, _ = file.WriteTo(w)
}

func ValueOrZero[T any](v *T) T {
	if v == nil {
		var zero T
		return zero
	}

	return *v
}
