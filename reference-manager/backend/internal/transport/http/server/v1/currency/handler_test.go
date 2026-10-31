package currencyhndl_test

import (
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"
	"uuid"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/xuri/excelize/v2"
	"go.uber.org/mock/gomock"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	currencyhndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/currency"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/currency/mocks"
	currencyv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/currency"
)

func TestHandlerCreateCurrency(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupServiceMock func(m *mocks.MockService)
		}
		args struct {
			requestBody string
		}
		want struct {
			responseStatus int
			responseBody   string
		}
	)

	var (
		changer   = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		createdAt = time.Date(2026, 10, 5, 7, 54, 0, 0, time.UTC)

		validRequestBody = `{
			"code": "USD",
			"number": "840",
			"name": "US Dollar",
			"decimals": 2,
			"is_deleted": false
		}`
		currencyModel = &currencydmn.Currency{
			Code:     "USD",
			Number:   "840",
			Name:     "US Dollar",
			Decimals: 2,
		}
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"success": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						CreateCurrency(gomock.Any(), currencyModel).
						Return(&currencydmn.ExpandedCurrency{
							ID:          1,
							Code:        "USD",
							Number:      "840",
							Name:        "US Dollar",
							Decimals:    2,
							Revision:    1,
							LastChanger: changer,
							CreatedAt:   createdAt,
							UpdatedAt:   createdAt,
						}, nil)
				},
			},
			args: args{
				requestBody: validRequestBody,
			},
			want: want{
				responseStatus: http.StatusCreated,
				responseBody: `{
					"id": 1,
					"code": "USD",
					"number": "840",
					"name": "US Dollar",
					"decimals": 2,
					"is_deleted": false,
					"revision": 1,
					"last_changer": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
					"created_at": "2026-10-05T07:54:00Z",
					"updated_at": "2026-10-05T07:54:00Z",
					"deleted_at": "0001-01-01T00:00:00Z"
				}`,
			},
		},
		"malformed request body": {
			fields: fields{
				setupServiceMock: func(_ *mocks.MockService) {},
			},
			args: args{
				requestBody: `{"code": `,
			},
			want: want{
				responseStatus: http.StatusBadRequest,
				responseBody:   `{"message": "failed to decode request"}`,
			},
		},
		"currency already exists": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						CreateCurrency(gomock.Any(), currencyModel).
						Return(nil, fmt.Errorf("create currency: %w", domains.ErrAlreadyExists))
				},
			},
			args: args{
				requestBody: validRequestBody,
			},
			want: want{
				responseStatus: http.StatusConflict,
				responseBody:   `{"message": "currency already exists"}`,
			},
		},
		"unauthenticated": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						CreateCurrency(gomock.Any(), currencyModel).
						Return(nil, domains.ErrUnauthenticated)
				},
			},
			args: args{
				requestBody: validRequestBody,
			},
			want: want{
				responseStatus: http.StatusUnauthorized,
				responseBody:   `{"message": "unauthenticated"}`,
			},
		},
		"permission denied": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						CreateCurrency(gomock.Any(), currencyModel).
						Return(nil, fmt.Errorf("authorize: %w", domains.ErrPermissionDenied))
				},
			},
			args: args{
				requestBody: validRequestBody,
			},
			want: want{
				responseStatus: http.StatusForbidden,
				responseBody:   `{"message": "permission denied"}`,
			},
		},
		"unexpected service error": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						CreateCurrency(gomock.Any(), currencyModel).
						Return(nil, errors.New("connection refused"))
				},
			},
			args: args{
				requestBody: validRequestBody,
			},
			want: want{
				responseStatus: http.StatusInternalServerError,
				responseBody:   `{"message": "internal server error"}`,
			},
		},
	}

	for name, tc := range testCases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctrl := gomock.NewController(t)
			mockService := mocks.NewMockService(ctrl)
			tc.fields.setupServiceMock(mockService)

			handler := currencyhndl.NewHandler(mockService)

			r := httptest.NewRequest(http.MethodPost, "/v1/currencies", strings.NewReader(tc.args.requestBody))
			rec := httptest.NewRecorder()

			handler.CreateCurrency(rec, r)

			assert.Equal(t, tc.want.responseStatus, rec.Code)
			assert.JSONEq(t, tc.want.responseBody, rec.Body.String())
		})
	}
}

func TestHandlerGetCurrency(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupServiceMock func(m *mocks.MockService)
		}
		args struct {
			currencyID currencyv1.CurrencyID
			params     currencyv1.GetCurrencyParams
		}
		want struct {
			responseStatus int
			responseBody   string
		}
	)

	var (
		changer      = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		createdAt    = time.Date(2026, 10, 5, 7, 54, 0, 0, time.UTC)
		deletedAt    = time.Date(2026, 10, 6, 7, 54, 0, 0, time.UTC)
		allowDeleted = true

		currencyModel = &currencydmn.ExpandedCurrency{
			ID:          1,
			Code:        "USD",
			Number:      "840",
			Name:        "US Dollar",
			Decimals:    2,
			Revision:    1,
			LastChanger: changer,
			CreatedAt:   createdAt,
			UpdatedAt:   createdAt,
		}
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"success": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						GetCurrency(gomock.Any(), int64(1), false).
						Return(currencyModel, nil)
				},
			},
			args: args{
				currencyID: 1,
			},
			want: want{
				responseStatus: http.StatusOK,
				responseBody: `{
					"id": 1,
					"code": "USD",
					"number": "840",
					"name": "US Dollar",
					"decimals": 2,
					"is_deleted": false,
					"revision": 1,
					"last_changer": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
					"created_at": "2026-10-05T07:54:00Z",
					"updated_at": "2026-10-05T07:54:00Z",
					"deleted_at": "0001-01-01T00:00:00Z"
				}`,
			},
		},
		"deleted currency is allowed": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						GetCurrency(gomock.Any(), int64(1), true).
						Return(&currencydmn.ExpandedCurrency{
							ID:          1,
							Code:        "USD",
							Number:      "840",
							Name:        "US Dollar",
							Decimals:    2,
							IsDeleted:   true,
							Revision:    2,
							LastChanger: changer,
							CreatedAt:   createdAt,
							UpdatedAt:   deletedAt,
							DeletedAt:   deletedAt,
						}, nil)
				},
			},
			args: args{
				currencyID: 1,
				params: currencyv1.GetCurrencyParams{
					AllowDeleted: &allowDeleted,
				},
			},
			want: want{
				responseStatus: http.StatusOK,
				responseBody: `{
					"id": 1,
					"code": "USD",
					"number": "840",
					"name": "US Dollar",
					"decimals": 2,
					"is_deleted": true,
					"revision": 2,
					"last_changer": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
					"created_at": "2026-10-05T07:54:00Z",
					"updated_at": "2026-10-06T07:54:00Z",
					"deleted_at": "2026-10-06T07:54:00Z"
				}`,
			},
		},
		"currency not found": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						GetCurrency(gomock.Any(), int64(1), false).
						Return(nil, fmt.Errorf("get expanded currency: %w", domains.ErrNotFound))
				},
			},
			args: args{
				currencyID: 1,
			},
			want: want{
				responseStatus: http.StatusNotFound,
				responseBody:   `{"message": "currency not found"}`,
			},
		},
		"unauthenticated": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						GetCurrency(gomock.Any(), int64(1), false).
						Return(nil, domains.ErrUnauthenticated)
				},
			},
			args: args{
				currencyID: 1,
			},
			want: want{
				responseStatus: http.StatusUnauthorized,
				responseBody:   `{"message": "unauthenticated"}`,
			},
		},
		"permission denied": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						GetCurrency(gomock.Any(), int64(1), false).
						Return(nil, fmt.Errorf("authorize: %w", domains.ErrPermissionDenied))
				},
			},
			args: args{
				currencyID: 1,
			},
			want: want{
				responseStatus: http.StatusForbidden,
				responseBody:   `{"message": "permission denied"}`,
			},
		},
		"unexpected service error": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						GetCurrency(gomock.Any(), int64(1), false).
						Return(nil, errors.New("connection refused"))
				},
			},
			args: args{
				currencyID: 1,
			},
			want: want{
				responseStatus: http.StatusInternalServerError,
				responseBody:   `{"message": "internal server error"}`,
			},
		},
	}

	for name, tc := range testCases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctrl := gomock.NewController(t)
			mockService := mocks.NewMockService(ctrl)
			tc.fields.setupServiceMock(mockService)

			handler := currencyhndl.NewHandler(mockService)

			r := httptest.NewRequest(http.MethodGet, "/v1/currencies/1", nil)
			rec := httptest.NewRecorder()

			handler.GetCurrency(rec, r, tc.args.currencyID, tc.args.params)

			assert.Equal(t, tc.want.responseStatus, rec.Code)
			assert.JSONEq(t, tc.want.responseBody, rec.Body.String())
		})
	}
}

func TestHandlerHandleParamError(t *testing.T) {
	t.Parallel()

	handler := currencyhndl.NewHandler(mocks.NewMockService(gomock.NewController(t)))

	r := httptest.NewRequest(http.MethodGet, "/v1/currencies/abc", nil)
	rec := httptest.NewRecorder()

	handler.HandleParamError(rec, r, errors.New("invalid currencyID"))

	assert.Equal(t, http.StatusBadRequest, rec.Code)
	assert.JSONEq(t, `{"message": "invalid request parameters"}`, rec.Body.String())
}

func TestHandlerListCurrencies(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupServiceMock func(m *mocks.MockService)
		}
		args struct {
			params currencyv1.ListCurrenciesParams
		}
		want struct {
			responseStatus int
			responseBody   string
		}
	)

	var (
		changer   = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		createdAt = time.Date(2026, 10, 5, 7, 54, 0, 0, time.UTC)

		pageSize     int32 = 1
		pageToken          = "token"
		filter             = `code = "USD"`
		orderBy            = "code desc"
		allowDeleted       = true

		usd = &currencydmn.ExpandedCurrency{
			ID:          1,
			Code:        "USD",
			Number:      "840",
			Name:        "US Dollar",
			Decimals:    2,
			Revision:    1,
			LastChanger: changer,
			CreatedAt:   createdAt,
			UpdatedAt:   createdAt,
		}
		usdBody = `{
			"id": 1,
			"code": "USD",
			"number": "840",
			"name": "US Dollar",
			"decimals": 2,
			"is_deleted": false,
			"revision": 1,
			"last_changer": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
			"created_at": "2026-10-05T07:54:00Z",
			"updated_at": "2026-10-05T07:54:00Z",
			"deleted_at": "0001-01-01T00:00:00Z"
		}`
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"page with a next page token": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ListCurrencies(gomock.Any(), &currencydmn.ListRequest{
							PageSize:     1,
							PageToken:    "token",
							Filter:       `code = "USD"`,
							OrderBy:      "code desc",
							AllowDeleted: true,
						}).
						Return(&currencydmn.ListPage{
							Currencies:    []*currencydmn.ExpandedCurrency{usd},
							NextPageToken: "next",
						}, nil)
				},
			},
			args: args{
				params: currencyv1.ListCurrenciesParams{
					PageSize:     &pageSize,
					PageToken:    &pageToken,
					Filter:       &filter,
					OrderBy:      &orderBy,
					AllowDeleted: &allowDeleted,
				},
			},
			want: want{
				responseStatus: http.StatusOK,
				responseBody:   `{"currencies": [` + usdBody + `], "nextPageToken": "next"}`,
			},
		},
		"empty last page": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ListCurrencies(gomock.Any(), &currencydmn.ListRequest{}).
						Return(&currencydmn.ListPage{}, nil)
				},
			},
			want: want{
				responseStatus: http.StatusOK,
				responseBody:   `{"currencies": []}`,
			},
		},
		"invalid argument": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ListCurrencies(gomock.Any(), gomock.Any()).
						Return(nil, &domains.InvalidArgumentError{
							Argument: "filter",
							Err:      errors.New("undeclared identifier 'status'"),
						})
				},
			},
			want: want{
				responseStatus: http.StatusBadRequest,
				responseBody:   `{"message": "invalid filter: undeclared identifier 'status'"}`,
			},
		},
		"unauthenticated": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ListCurrencies(gomock.Any(), gomock.Any()).
						Return(nil, domains.ErrUnauthenticated)
				},
			},
			want: want{
				responseStatus: http.StatusUnauthorized,
				responseBody:   `{"message": "unauthenticated"}`,
			},
		},
		"permission denied": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ListCurrencies(gomock.Any(), gomock.Any()).
						Return(nil, fmt.Errorf("authorize: %w", domains.ErrPermissionDenied))
				},
			},
			want: want{
				responseStatus: http.StatusForbidden,
				responseBody:   `{"message": "permission denied"}`,
			},
		},
		"unexpected service error": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ListCurrencies(gomock.Any(), gomock.Any()).
						Return(nil, errors.New("connection refused"))
				},
			},
			want: want{
				responseStatus: http.StatusInternalServerError,
				responseBody:   `{"message": "internal server error"}`,
			},
		},
	}

	for name, tc := range testCases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctrl := gomock.NewController(t)
			mockService := mocks.NewMockService(ctrl)
			tc.fields.setupServiceMock(mockService)

			handler := currencyhndl.NewHandler(mockService)

			r := httptest.NewRequest(http.MethodGet, "/v1/currencies/", nil)
			rec := httptest.NewRecorder()

			handler.ListCurrencies(rec, r, tc.args.params)

			assert.Equal(t, tc.want.responseStatus, rec.Code)
			assert.JSONEq(t, tc.want.responseBody, rec.Body.String())
		})
	}
}

func TestHandlerUpdateCurrency(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupServiceMock func(m *mocks.MockService)
		}
		args struct {
			params      currencyv1.UpdateCurrencyParams
			requestBody string
		}
		want struct {
			responseStatus int
			responseBody   string
		}
	)

	var (
		changer    = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		createdAt  = time.Date(2026, 10, 5, 7, 54, 0, 0, time.UTC)
		updatedAt  = time.Date(2026, 10, 6, 7, 54, 0, 0, time.UTC)
		updateMask = "name"

		validRequestBody = `{
			"code": "USD",
			"number": "840",
			"name": "United States Dollar",
			"decimals": 2,
			"is_deleted": false
		}`
		updateRequest = &currencydmn.UpdateRequest{
			CurrencyID: 1,
			Currency: &currencydmn.Currency{
				Code:     "USD",
				Number:   "840",
				Name:     "United States Dollar",
				Decimals: 2,
			},
		}
		maskedUpdateRequest = &currencydmn.UpdateRequest{
			CurrencyID: 1,
			Currency:   updateRequest.Currency,
			UpdateMask: updateMask,
		}
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"success": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						UpdateCurrency(gomock.Any(), maskedUpdateRequest).
						Return(&currencydmn.ExpandedCurrency{
							ID:          1,
							Code:        "USD",
							Number:      "840",
							Name:        "United States Dollar",
							Decimals:    2,
							Revision:    2,
							LastChanger: changer,
							CreatedAt:   createdAt,
							UpdatedAt:   updatedAt,
						}, nil)
				},
			},
			args: args{
				params:      currencyv1.UpdateCurrencyParams{UpdateMask: &updateMask},
				requestBody: validRequestBody,
			},
			want: want{
				responseStatus: http.StatusOK,
				responseBody: `{
					"id": 1,
					"code": "USD",
					"number": "840",
					"name": "United States Dollar",
					"decimals": 2,
					"is_deleted": false,
					"revision": 2,
					"last_changer": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
					"created_at": "2026-10-05T07:54:00Z",
					"updated_at": "2026-10-06T07:54:00Z",
					"deleted_at": "0001-01-01T00:00:00Z"
				}`,
			},
		},
		"malformed request body": {
			fields: fields{
				setupServiceMock: func(_ *mocks.MockService) {},
			},
			args: args{
				requestBody: `{"name": `,
			},
			want: want{
				responseStatus: http.StatusBadRequest,
				responseBody:   `{"message": "failed to decode request"}`,
			},
		},
		"invalid update mask": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						UpdateCurrency(gomock.Any(), updateRequest).
						Return(nil, &domains.InvalidArgumentError{Argument: "updateMask", Err: errors.New(`field "is_deleted" cannot be updated`)})
				},
			},
			args: args{
				requestBody: validRequestBody,
			},
			want: want{
				responseStatus: http.StatusBadRequest,
				responseBody:   `{"message": "invalid updateMask: field \"is_deleted\" cannot be updated"}`,
			},
		},
		"currency not found": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						UpdateCurrency(gomock.Any(), updateRequest).
						Return(nil, fmt.Errorf("get expanded currency: %w", domains.ErrNotFound))
				},
			},
			args: args{
				requestBody: validRequestBody,
			},
			want: want{
				responseStatus: http.StatusNotFound,
				responseBody:   `{"message": "currency not found"}`,
			},
		},
		"code or number already taken": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						UpdateCurrency(gomock.Any(), updateRequest).
						Return(nil, fmt.Errorf("update currency: %w", domains.ErrAlreadyExists))
				},
			},
			args: args{
				requestBody: validRequestBody,
			},
			want: want{
				responseStatus: http.StatusConflict,
				responseBody:   `{"message": "currency already exists"}`,
			},
		},
		"concurrent modification": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						UpdateCurrency(gomock.Any(), updateRequest).
						Return(nil, fmt.Errorf("create currency revision 2: %w", domains.ErrConflict))
				},
			},
			args: args{
				requestBody: validRequestBody,
			},
			want: want{
				responseStatus: http.StatusConflict,
				responseBody:   `{"message": "currency was modified concurrently, retry the request"}`,
			},
		},
		"unauthenticated": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						UpdateCurrency(gomock.Any(), updateRequest).
						Return(nil, domains.ErrUnauthenticated)
				},
			},
			args: args{
				requestBody: validRequestBody,
			},
			want: want{
				responseStatus: http.StatusUnauthorized,
				responseBody:   `{"message": "unauthenticated"}`,
			},
		},
		"permission denied": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						UpdateCurrency(gomock.Any(), updateRequest).
						Return(nil, fmt.Errorf("authorize: %w", domains.ErrPermissionDenied))
				},
			},
			args: args{
				requestBody: validRequestBody,
			},
			want: want{
				responseStatus: http.StatusForbidden,
				responseBody:   `{"message": "permission denied"}`,
			},
		},
		"unexpected service error": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						UpdateCurrency(gomock.Any(), updateRequest).
						Return(nil, errors.New("connection refused"))
				},
			},
			args: args{
				requestBody: validRequestBody,
			},
			want: want{
				responseStatus: http.StatusInternalServerError,
				responseBody:   `{"message": "internal server error"}`,
			},
		},
	}

	for name, tc := range testCases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctrl := gomock.NewController(t)
			mockService := mocks.NewMockService(ctrl)
			tc.fields.setupServiceMock(mockService)

			handler := currencyhndl.NewHandler(mockService)

			r := httptest.NewRequest(http.MethodPatch, "/v1/currencies/1", strings.NewReader(tc.args.requestBody))
			rec := httptest.NewRecorder()

			handler.UpdateCurrency(rec, r, 1, tc.args.params)

			assert.Equal(t, tc.want.responseStatus, rec.Code)
			assert.JSONEq(t, tc.want.responseBody, rec.Body.String())
		})
	}
}

func TestHandlerDeleteCurrency(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupServiceMock func(m *mocks.MockService)
		}
		args struct {
			params currencyv1.DeleteCurrencyParams
		}
		want struct {
			responseStatus int
			responseBody   string
		}
	)

	var (
		changer   = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		createdAt = time.Date(2026, 10, 5, 7, 54, 0, 0, time.UTC)
		deletedAt = time.Date(2026, 10, 6, 7, 54, 0, 0, time.UTC)
		force     = true
		noForce   = false
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"soft deletion": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						DeleteCurrency(gomock.Any(), int64(1)).
						Return(&currencydmn.ExpandedCurrency{
							ID:          1,
							Code:        "USD",
							Number:      "840",
							Name:        "US Dollar",
							Decimals:    2,
							IsDeleted:   true,
							Revision:    2,
							LastChanger: changer,
							CreatedAt:   createdAt,
							UpdatedAt:   deletedAt,
							DeletedAt:   deletedAt,
						}, nil)
				},
			},
			args: args{
				params: currencyv1.DeleteCurrencyParams{Force: &noForce},
			},
			want: want{
				responseStatus: http.StatusOK,
				responseBody: `{
					"id": 1,
					"code": "USD",
					"number": "840",
					"name": "US Dollar",
					"decimals": 2,
					"is_deleted": true,
					"revision": 2,
					"last_changer": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
					"created_at": "2026-10-05T07:54:00Z",
					"updated_at": "2026-10-06T07:54:00Z",
					"deleted_at": "2026-10-06T07:54:00Z"
				}`,
			},
		},
		"forced deletion": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						PurgeCurrency(gomock.Any(), int64(1)).
						Return(nil)
				},
			},
			args: args{
				params: currencyv1.DeleteCurrencyParams{Force: &force},
			},
			want: want{
				responseStatus: http.StatusNoContent,
			},
		},
		"currency not found": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						DeleteCurrency(gomock.Any(), int64(1)).
						Return(nil, fmt.Errorf("get expanded currency: %w", domains.ErrNotFound))
				},
			},
			want: want{
				responseStatus: http.StatusNotFound,
				responseBody:   `{"message": "currency not found"}`,
			},
		},
		"forced deletion of missing currency": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						PurgeCurrency(gomock.Any(), int64(1)).
						Return(fmt.Errorf("delete currency: %w", domains.ErrNotFound))
				},
			},
			args: args{
				params: currencyv1.DeleteCurrencyParams{Force: &force},
			},
			want: want{
				responseStatus: http.StatusNotFound,
				responseBody:   `{"message": "currency not found"}`,
			},
		},
		"concurrent modification": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						DeleteCurrency(gomock.Any(), int64(1)).
						Return(nil, fmt.Errorf("create currency revision 2: %w", domains.ErrConflict))
				},
			},
			want: want{
				responseStatus: http.StatusConflict,
				responseBody:   `{"message": "currency was modified concurrently, retry the request"}`,
			},
		},
		"unauthenticated": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						DeleteCurrency(gomock.Any(), int64(1)).
						Return(nil, domains.ErrUnauthenticated)
				},
			},
			want: want{
				responseStatus: http.StatusUnauthorized,
				responseBody:   `{"message": "unauthenticated"}`,
			},
		},
		"permission denied": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						DeleteCurrency(gomock.Any(), int64(1)).
						Return(nil, fmt.Errorf("authorize: %w", domains.ErrPermissionDenied))
				},
			},
			want: want{
				responseStatus: http.StatusForbidden,
				responseBody:   `{"message": "permission denied"}`,
			},
		},
		"unexpected service error": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						PurgeCurrency(gomock.Any(), int64(1)).
						Return(errors.New("connection refused"))
				},
			},
			args: args{
				params: currencyv1.DeleteCurrencyParams{Force: &force},
			},
			want: want{
				responseStatus: http.StatusInternalServerError,
				responseBody:   `{"message": "internal server error"}`,
			},
		},
	}

	for name, tc := range testCases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctrl := gomock.NewController(t)
			mockService := mocks.NewMockService(ctrl)
			tc.fields.setupServiceMock(mockService)

			handler := currencyhndl.NewHandler(mockService)

			r := httptest.NewRequest(http.MethodDelete, "/v1/currencies/1", nil)
			rec := httptest.NewRecorder()

			handler.DeleteCurrency(rec, r, 1, tc.args.params)

			assert.Equal(t, tc.want.responseStatus, rec.Code)
			if tc.want.responseBody == "" {
				assert.Empty(t, rec.Body.String())
			} else {
				assert.JSONEq(t, tc.want.responseBody, rec.Body.String())
			}
		})
	}
}

func TestHandlerGetCurrencyRevision(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupServiceMock func(m *mocks.MockService)
		}
		args struct {
			currencyID     currencyv1.CurrencyID
			revisionNumber currencyv1.RevisionNumber
			params         currencyv1.GetCurrencyRevisionParams
		}
		want struct {
			responseStatus int
			responseBody   string
		}
	)

	var (
		changer      = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		changedAt    = time.Date(2026, 10, 6, 7, 54, 0, 0, time.UTC)
		allowDeleted = true

		revisionModel = &currencydmn.CurrencyRevision{
			ID:             10,
			CurrencyID:     1,
			RevisionNumber: 2,
			Change:         []byte(`[{"op":"replace","path":"/name","value":"US Dollar"}]`),
			ChangedBy:      changer,
			ChangedAt:      changedAt,
		}
		revisionBody = `{
			"id": 10,
			"currency_id": 1,
			"revision_number": 2,
			"change": [{"op": "replace", "path": "/name", "value": "US Dollar"}],
			"changed_by": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
			"changed_at": "2026-10-06T07:54:00Z"
		}`
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"success": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						GetCurrencyRevision(gomock.Any(), int64(1), int32(2), false).
						Return(revisionModel, nil)
				},
			},
			args: args{
				currencyID:     1,
				revisionNumber: 2,
			},
			want: want{
				responseStatus: http.StatusOK,
				responseBody:   revisionBody,
			},
		},
		"revision of a deleted currency is allowed": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						GetCurrencyRevision(gomock.Any(), int64(1), int32(2), true).
						Return(revisionModel, nil)
				},
			},
			args: args{
				currencyID:     1,
				revisionNumber: 2,
				params: currencyv1.GetCurrencyRevisionParams{
					AllowDeleted: &allowDeleted,
				},
			},
			want: want{
				responseStatus: http.StatusOK,
				responseBody:   revisionBody,
			},
		},
		"currency not found": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						GetCurrencyRevision(gomock.Any(), int64(1), int32(2), false).
						Return(nil, fmt.Errorf("get expanded currency: %w", domains.ErrNotFound))
				},
			},
			args: args{
				currencyID:     1,
				revisionNumber: 2,
			},
			want: want{
				responseStatus: http.StatusNotFound,
				responseBody:   `{"message": "currency not found"}`,
			},
		},
		"revision not found": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						GetCurrencyRevision(gomock.Any(), int64(1), int32(2), false).
						Return(nil, fmt.Errorf("get currency revision 2: %w", domains.ErrRevisionNotFound))
				},
			},
			args: args{
				currencyID:     1,
				revisionNumber: 2,
			},
			want: want{
				responseStatus: http.StatusNotFound,
				responseBody:   `{"message": "currency revision not found"}`,
			},
		},
		"unauthenticated": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						GetCurrencyRevision(gomock.Any(), int64(1), int32(2), false).
						Return(nil, domains.ErrUnauthenticated)
				},
			},
			args: args{
				currencyID:     1,
				revisionNumber: 2,
			},
			want: want{
				responseStatus: http.StatusUnauthorized,
				responseBody:   `{"message": "unauthenticated"}`,
			},
		},
		"permission denied": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						GetCurrencyRevision(gomock.Any(), int64(1), int32(2), false).
						Return(nil, fmt.Errorf("authorize: %w", domains.ErrPermissionDenied))
				},
			},
			args: args{
				currencyID:     1,
				revisionNumber: 2,
			},
			want: want{
				responseStatus: http.StatusForbidden,
				responseBody:   `{"message": "permission denied"}`,
			},
		},
		"malformed stored change": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						GetCurrencyRevision(gomock.Any(), int64(1), int32(2), false).
						Return(&currencydmn.CurrencyRevision{ID: 10, Change: []byte(`{`)}, nil)
				},
			},
			args: args{
				currencyID:     1,
				revisionNumber: 2,
			},
			want: want{
				responseStatus: http.StatusInternalServerError,
				responseBody:   `{"message": "internal server error"}`,
			},
		},
		"unexpected service error": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						GetCurrencyRevision(gomock.Any(), int64(1), int32(2), false).
						Return(nil, errors.New("connection refused"))
				},
			},
			args: args{
				currencyID:     1,
				revisionNumber: 2,
			},
			want: want{
				responseStatus: http.StatusInternalServerError,
				responseBody:   `{"message": "internal server error"}`,
			},
		},
	}

	for name, tc := range testCases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctrl := gomock.NewController(t)
			mockService := mocks.NewMockService(ctrl)
			tc.fields.setupServiceMock(mockService)

			handler := currencyhndl.NewHandler(mockService)

			r := httptest.NewRequest(http.MethodGet, "/v1/currencies/1/revisions/2", nil)
			rec := httptest.NewRecorder()

			handler.GetCurrencyRevision(rec, r, tc.args.currencyID, tc.args.revisionNumber, tc.args.params)

			assert.Equal(t, tc.want.responseStatus, rec.Code)
			assert.JSONEq(t, tc.want.responseBody, rec.Body.String())
		})
	}
}

func TestHandlerListCurrencyRevisions(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupServiceMock func(m *mocks.MockService)
		}
		args struct {
			params currencyv1.ListCurrencyRevisionsParams
		}
		want struct {
			responseStatus int
			responseBody   string
		}
	)

	var (
		changer   = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		changedAt = time.Date(2026, 10, 5, 7, 54, 0, 0, time.UTC)

		pageSize     int32 = 1
		pageToken          = "token"
		filter             = "revision_number = 1"
		orderBy            = "changed_at desc"
		allowDeleted       = true

		revision = &currencydmn.CurrencyRevision{
			ID:             1,
			CurrencyID:     1,
			RevisionNumber: 1,
			Change:         []byte(`[{"op":"add","path":"/code","value":"USD"}]`),
			ChangedBy:      changer,
			ChangedAt:      changedAt,
		}
		revisionBody = `{
			"id": 1,
			"currency_id": 1,
			"revision_number": 1,
			"change": [{"op": "add", "path": "/code", "value": "USD"}],
			"changed_by": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
			"changed_at": "2026-10-05T07:54:00Z"
		}`
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"page with a next page token": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ListCurrencyRevisions(gomock.Any(), &currencydmn.RevisionListRequest{
							CurrencyID:   1,
							PageSize:     1,
							PageToken:    "token",
							Filter:       "revision_number = 1",
							OrderBy:      "changed_at desc",
							AllowDeleted: true,
						}).
						Return(&currencydmn.RevisionListPage{
							Revisions:     []*currencydmn.CurrencyRevision{revision},
							NextPageToken: "next",
						}, nil)
				},
			},
			args: args{
				params: currencyv1.ListCurrencyRevisionsParams{
					PageSize:     &pageSize,
					PageToken:    &pageToken,
					Filter:       &filter,
					OrderBy:      &orderBy,
					AllowDeleted: &allowDeleted,
				},
			},
			want: want{
				responseStatus: http.StatusOK,
				responseBody:   `{"revisions": [` + revisionBody + `], "nextPageToken": "next"}`,
			},
		},
		"empty last page": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ListCurrencyRevisions(gomock.Any(), &currencydmn.RevisionListRequest{CurrencyID: 1}).
						Return(&currencydmn.RevisionListPage{}, nil)
				},
			},
			want: want{
				responseStatus: http.StatusOK,
				responseBody:   `{"revisions": []}`,
			},
		},
		"invalid argument": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ListCurrencyRevisions(gomock.Any(), gomock.Any()).
						Return(nil, &domains.InvalidArgumentError{
							Argument: "filter",
							Err:      errors.New("undeclared identifier 'code'"),
						})
				},
			},
			want: want{
				responseStatus: http.StatusBadRequest,
				responseBody:   `{"message": "invalid filter: undeclared identifier 'code'"}`,
			},
		},
		"currency not found": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ListCurrencyRevisions(gomock.Any(), gomock.Any()).
						Return(nil, fmt.Errorf("get expanded currency: %w", domains.ErrNotFound))
				},
			},
			want: want{
				responseStatus: http.StatusNotFound,
				responseBody:   `{"message": "currency not found"}`,
			},
		},
		"unauthenticated": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ListCurrencyRevisions(gomock.Any(), gomock.Any()).
						Return(nil, domains.ErrUnauthenticated)
				},
			},
			want: want{
				responseStatus: http.StatusUnauthorized,
				responseBody:   `{"message": "unauthenticated"}`,
			},
		},
		"permission denied": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ListCurrencyRevisions(gomock.Any(), gomock.Any()).
						Return(nil, fmt.Errorf("authorize: %w", domains.ErrPermissionDenied))
				},
			},
			want: want{
				responseStatus: http.StatusForbidden,
				responseBody:   `{"message": "permission denied"}`,
			},
		},
		"malformed stored change": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ListCurrencyRevisions(gomock.Any(), gomock.Any()).
						Return(&currencydmn.RevisionListPage{
							Revisions: []*currencydmn.CurrencyRevision{{ID: 1, Change: []byte(`{`)}},
						}, nil)
				},
			},
			want: want{
				responseStatus: http.StatusInternalServerError,
				responseBody:   `{"message": "internal server error"}`,
			},
		},
		"unexpected service error": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ListCurrencyRevisions(gomock.Any(), gomock.Any()).
						Return(nil, errors.New("connection refused"))
				},
			},
			want: want{
				responseStatus: http.StatusInternalServerError,
				responseBody:   `{"message": "internal server error"}`,
			},
		},
	}

	for name, tc := range testCases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctrl := gomock.NewController(t)
			mockService := mocks.NewMockService(ctrl)
			tc.fields.setupServiceMock(mockService)

			handler := currencyhndl.NewHandler(mockService)

			r := httptest.NewRequest(http.MethodGet, "/v1/currencies/1/revisions", nil)
			rec := httptest.NewRecorder()

			handler.ListCurrencyRevisions(rec, r, 1, tc.args.params)

			assert.Equal(t, tc.want.responseStatus, rec.Code)
			assert.JSONEq(t, tc.want.responseBody, rec.Body.String())
		})
	}
}

func TestHandlerExportCurrencies(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupServiceMock func(m *mocks.MockService)
		}
		want struct {
			responseStatus int
			// rows are the expected rows of the exported sheet, header included, when the export succeeds.
			rows [][]string
			// responseBody is the expected JSON error when the export fails.
			responseBody string
		}
	)

	var (
		changer   = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		createdAt = time.Date(2026, 10, 5, 7, 54, 0, 0, time.UTC)
		updatedAt = time.Date(2026, 10, 6, 8, 30, 15, 0, time.UTC)

		header = []string{"Code", "Number", "Name", "Decimals", "Revision", "Last changer", "Created at", "Updated at"}
	)

	testCases := map[string]struct {
		fields fields
		want   want
	}{
		"currencies": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ExportCurrencies(gomock.Any()).
						Return([]*currencydmn.ExpandedCurrency{
							{
								ID: 1, Code: "USD", Number: "840", Name: "US Dollar", Decimals: 2,
								Revision: 1, LastChanger: changer, CreatedAt: createdAt, UpdatedAt: createdAt,
							},
							{
								ID: 2, Code: "BHD", Number: "048", Name: "Bahraini Dinar", Decimals: 3,
								Revision: 2, LastChanger: changer, CreatedAt: createdAt, UpdatedAt: updatedAt,
							},
						}, nil)
				},
			},
			want: want{
				responseStatus: http.StatusOK,
				rows: [][]string{
					header,
					{
						"USD", "840", "US Dollar", "2", "1", "3fa85f64-5717-4562-b3fc-2c963f66afa6",
						"2026-10-05 07:54:00", "2026-10-05 07:54:00",
					},
					{
						"BHD", "048", "Bahraini Dinar", "3", "2", "3fa85f64-5717-4562-b3fc-2c963f66afa6",
						"2026-10-05 07:54:00", "2026-10-06 08:30:15",
					},
				},
			},
		},
		"no currencies": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ExportCurrencies(gomock.Any()).
						Return([]*currencydmn.ExpandedCurrency{}, nil)
				},
			},
			want: want{
				responseStatus: http.StatusOK,
				rows:           [][]string{header},
			},
		},
		"unauthenticated": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ExportCurrencies(gomock.Any()).
						Return(nil, domains.ErrUnauthenticated)
				},
			},
			want: want{
				responseStatus: http.StatusUnauthorized,
				responseBody:   `{"message": "unauthenticated"}`,
			},
		},
		"permission denied": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ExportCurrencies(gomock.Any()).
						Return(nil, fmt.Errorf("authorize: %w", domains.ErrPermissionDenied))
				},
			},
			want: want{
				responseStatus: http.StatusForbidden,
				responseBody:   `{"message": "permission denied"}`,
			},
		},
		"unexpected service error": {
			fields: fields{
				setupServiceMock: func(m *mocks.MockService) {
					m.EXPECT().
						ExportCurrencies(gomock.Any()).
						Return(nil, errors.New("connection refused"))
				},
			},
			want: want{
				responseStatus: http.StatusInternalServerError,
				responseBody:   `{"message": "internal server error"}`,
			},
		},
	}

	for name, tc := range testCases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctrl := gomock.NewController(t)
			mockService := mocks.NewMockService(ctrl)
			tc.fields.setupServiceMock(mockService)

			handler := currencyhndl.NewHandler(mockService)

			r := httptest.NewRequest(http.MethodPost, "/v1/currencies/export", nil)
			rec := httptest.NewRecorder()

			handler.ExportCurrencies(rec, r)

			assert.Equal(t, tc.want.responseStatus, rec.Code)

			if tc.want.rows == nil {
				assert.JSONEq(t, tc.want.responseBody, rec.Body.String())
				return
			}

			assert.Equal(t, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", rec.Header().Get("Content-Type"))
			assert.Equal(t, `attachment; filename=currencies.xlsx`, rec.Header().Get("Content-Disposition"))
			assert.Equal(t, strconv.Itoa(rec.Body.Len()), rec.Header().Get("Content-Length"))

			f, err := excelize.OpenReader(rec.Body)
			require.NoError(t, err)
			t.Cleanup(func() { _ = f.Close() })

			assert.Equal(t, []string{"Currencies"}, f.GetSheetList())

			rows, err := f.GetRows("Currencies")
			require.NoError(t, err)
			assert.Equal(t, tc.want.rows, rows)
		})
	}
}
