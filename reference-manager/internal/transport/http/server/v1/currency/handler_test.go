package currencyhndl_test

import (
	"bytes"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	currencyhndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/currency"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/currency/mocks"
	"github.com/go-openapi/testify/v2/assert"
	"go.uber.org/mock/gomock"
)

func TestCreateCurrency(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			serviceMockSetup func(m *mocks.MockService)
		}
		args struct {
			requestBody string
		}
		want struct {
			statusCode int
			body       string
		}
	)

	tests := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"bad_request": {
			fields: fields{serviceMockSetup: func(m *mocks.MockService) {}},
			args:   args{requestBody: `{invalid}`},
			want:   want{statusCode: http.StatusBadRequest, body: `{"message": "failed to decode http request body"}`},
		},
		"conflict": {
			fields: fields{serviceMockSetup: func(m *mocks.MockService) {
				m.EXPECT().
					CreateCurrency(gomock.Any(), gomock.Any()).
					Return(nil, domains.ErrAlreadyExists)
			}},
			args: args{requestBody: `{
				"code": "USD",
				"number": "840",
				"name": "US Dollar",
				"decimals": 2
			}`},
			want: want{
				statusCode: http.StatusConflict,
				body:       `{"message": "currency already exists"}`,
			},
		},
		"internal_server_error": {
			fields: fields{serviceMockSetup: func(m *mocks.MockService) {
				m.EXPECT().
					CreateCurrency(gomock.Any(), gomock.Any()).
					Return(nil, errors.New("unexpected error"))
			}},
			args: args{requestBody: `{
				"code": "USD",
				"number": "840",
				"name": "US Dollar",
				"decimals": 2
			}`},
			want: want{
				statusCode: http.StatusInternalServerError,
				body:       `{"message": "internal server error"}`,
			},
		},
		"created": {
			fields: fields{serviceMockSetup: func(m *mocks.MockService) {
				m.EXPECT().
					CreateCurrency(gomock.Any(), gomock.Any()).
					Return(&currencydmn.ExpandedCurrency{
						Code:     "USD",
						Number:   "840",
						Name:     "US Dollar",
						Decimals: 2,
					}, nil)
			}},
			args: args{requestBody: `{
				"code": "USD",
				"number": "840",
				"name": "US Dollar",
				"decimals": 2
			}`},
			want: want{
				statusCode: http.StatusCreated,
				body: `{
					"code": "USD",
					"number": "840",
					"name": "US Dollar",
					"decimals": 2,
					"revision": 0,
					"last_changer": "00000000-0000-0000-0000-000000000000",
					"is_deleted": false,
					"created_at": "0001-01-01T00:00:00Z",
					"updated_at": "0001-01-01T00:00:00Z",
					"deleted_at": "0001-01-01T00:00:00Z"
				}`,
			},
		},
	}

	for tn, tc := range tests {
		t.Run(tn, func(t *testing.T) {
			t.Parallel()

			ctrl := gomock.NewController(t)
			defer ctrl.Finish()

			mock := mocks.NewMockService(ctrl)
			tc.fields.serviceMockSetup(mock)

			handler := currencyhndl.NewHandler(mock)

			req := httptest.NewRequest(http.MethodPost, "/v1/currencies", bytes.NewBuffer([]byte(tc.args.requestBody)))
			req.Header.Set("Content-Type", "application/json")

			w := httptest.NewRecorder()

			handler.CreateCurrency(w, req)

			assert.Equal(t, tc.want.statusCode, w.Code)
			if tc.want.body != "" {
				assert.JSONEq(t, tc.want.body, w.Body.String())
			}
		})
	}
}
