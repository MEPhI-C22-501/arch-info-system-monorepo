package currencyhndl_test

import (
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
	"uuid"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	currencyhndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/currency"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/currency/mocks"
	currencyv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/currency"
	"github.com/stretchr/testify/assert"
	"go.uber.org/mock/gomock"
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
				setupServiceMock: func(m *mocks.MockService) {},
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
