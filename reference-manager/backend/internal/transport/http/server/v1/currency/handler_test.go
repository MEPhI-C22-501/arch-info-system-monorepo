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
