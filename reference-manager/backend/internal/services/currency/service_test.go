package currencysrv_test

import (
	"context"
	"encoding/json"
	"errors"
	"reflect"
	"testing"
	"time"
	"uuid"

	"github.com/stretchr/testify/assert"
	"go.uber.org/mock/gomock"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	currencysrv "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/services/currency"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/services/currency/mocks"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/actor"
)

func TestServiceCreateCurrency(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupTxManagerMock                  func(m *mocks.MockTxManager)
			setupCurrencyRepositoryMock         func(m *mocks.MockCurrencyRepository)
			setupCurrencyVersionRepositoryMock  func(m *mocks.MockCurrencyVersionRepository)
			setupExpandedCurrencyRepositoryMock func(m *mocks.MockExpandedCurrencyRepository)
		}
		args struct {
			ctx      context.Context
			currency *currencydmn.Currency
		}
		want struct {
			result *currencydmn.ExpandedCurrency
			err    error
		}
	)

	var (
		currencyID  int64 = 1
		changer           = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		createdAt         = time.Date(2026, 10, 5, 7, 54, 0, 0, time.UTC)
		errDatabase       = errors.New("database error")

		authenticatedCtx = actor.WithUserID(context.Background(), changer)

		currency = &currencydmn.Currency{
			Code:     "USD",
			Number:   "840",
			Name:     "US Dollar",
			Decimals: 2,
		}
		expandedCurrency = &currencydmn.ExpandedCurrency{
			ID:          currencyID,
			Code:        "USD",
			Number:      "840",
			Name:        "US Dollar",
			Decimals:    2,
			Revision:    1,
			LastChanger: changer,
			CreatedAt:   createdAt,
			UpdatedAt:   createdAt,
		}
		revision = gomock.Cond(func(r *currencydmn.CurrencyRevision) bool {
			return r.CurrencyID == currencyID &&
				r.RevisionNumber == 1 &&
				r.ChangedBy == changer &&
				jsonEqual(r.Change, `[
					{"op": "add", "path": "/code", "value": "USD"},
					{"op": "add", "path": "/decimals", "value": 2},
					{"op": "add", "path": "/is_deleted", "value": false},
					{"op": "add", "path": "/name", "value": "US Dollar"},
					{"op": "add", "path": "/number", "value": "840"}
				]`)
		})

		runInTx = func(m *mocks.MockTxManager) {
			m.EXPECT().
				Do(gomock.Any(), gomock.Any()).
				DoAndReturn(func(ctx context.Context, fn func(ctx context.Context) error) error {
					return fn(ctx)
				})
		}
		noTxManagerCalls                  = func(m *mocks.MockTxManager) {}
		noCurrencyRepositoryCalls         = func(m *mocks.MockCurrencyRepository) {}
		noCurrencyVersionRepositoryCalls  = func(m *mocks.MockCurrencyVersionRepository) {}
		noExpandedCurrencyRepositoryCalls = func(m *mocks.MockExpandedCurrencyRepository) {}
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"success": {
			fields: fields{
				setupTxManagerMock: runInTx,
				setupCurrencyRepositoryMock: func(m *mocks.MockCurrencyRepository) {
					m.EXPECT().
						CreateCurrency(gomock.Any(), currency).
						Return(currencyID, nil)
				},
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						CreateCurrencyRevision(gomock.Any(), revision).
						Return(nil)
				},
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(expandedCurrency, nil)
				},
			},
			args: args{
				ctx:      authenticatedCtx,
				currency: currency,
			},
			want: want{
				result: expandedCurrency,
			},
		},
		"unauthenticated": {
			fields: fields{
				setupTxManagerMock:                  noTxManagerCalls,
				setupCurrencyRepositoryMock:         noCurrencyRepositoryCalls,
				setupCurrencyVersionRepositoryMock:  noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:      context.Background(),
				currency: currency,
			},
			want: want{
				err: domains.ErrUnauthenticated,
			},
		},
		"currency already exists": {
			fields: fields{
				setupTxManagerMock: runInTx,
				setupCurrencyRepositoryMock: func(m *mocks.MockCurrencyRepository) {
					m.EXPECT().
						CreateCurrency(gomock.Any(), currency).
						Return(int64(0), domains.ErrAlreadyExists)
				},
				setupCurrencyVersionRepositoryMock:  noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:      authenticatedCtx,
				currency: currency,
			},
			want: want{
				err: domains.ErrAlreadyExists,
			},
		},
		"create currency revision failed": {
			fields: fields{
				setupTxManagerMock: runInTx,
				setupCurrencyRepositoryMock: func(m *mocks.MockCurrencyRepository) {
					m.EXPECT().
						CreateCurrency(gomock.Any(), currency).
						Return(currencyID, nil)
				},
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						CreateCurrencyRevision(gomock.Any(), revision).
						Return(errDatabase)
				},
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:      authenticatedCtx,
				currency: currency,
			},
			want: want{
				err: errDatabase,
			},
		},
		"get expanded currency failed": {
			fields: fields{
				setupTxManagerMock: runInTx,
				setupCurrencyRepositoryMock: func(m *mocks.MockCurrencyRepository) {
					m.EXPECT().
						CreateCurrency(gomock.Any(), currency).
						Return(currencyID, nil)
				},
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						CreateCurrencyRevision(gomock.Any(), revision).
						Return(nil)
				},
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(nil, errDatabase)
				},
			},
			args: args{
				ctx:      authenticatedCtx,
				currency: currency,
			},
			want: want{
				err: errDatabase,
			},
		},
		"transaction failed": {
			fields: fields{
				setupTxManagerMock: func(m *mocks.MockTxManager) {
					m.EXPECT().
						Do(gomock.Any(), gomock.Any()).
						Return(errDatabase)
				},
				setupCurrencyRepositoryMock:         noCurrencyRepositoryCalls,
				setupCurrencyVersionRepositoryMock:  noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:      authenticatedCtx,
				currency: currency,
			},
			want: want{
				err: errDatabase,
			},
		},
	}

	for name, tc := range testCases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			ctrl := gomock.NewController(t)

			mockTxManager := mocks.NewMockTxManager(ctrl)
			tc.fields.setupTxManagerMock(mockTxManager)

			mockCurrencyRepository := mocks.NewMockCurrencyRepository(ctrl)
			tc.fields.setupCurrencyRepositoryMock(mockCurrencyRepository)

			mockCurrencyVersionRepository := mocks.NewMockCurrencyVersionRepository(ctrl)
			tc.fields.setupCurrencyVersionRepositoryMock(mockCurrencyVersionRepository)

			mockExpandedCurrencyRepository := mocks.NewMockExpandedCurrencyRepository(ctrl)
			tc.fields.setupExpandedCurrencyRepositoryMock(mockExpandedCurrencyRepository)

			service := currencysrv.NewService(
				mockTxManager,
				mockCurrencyRepository,
				mockCurrencyVersionRepository,
				mockExpandedCurrencyRepository,
			)

			result, err := service.CreateCurrency(tc.args.ctx, tc.args.currency)

			assert.ErrorIs(t, err, tc.want.err)
			assert.Equal(t, tc.want.result, result)
		})
	}
}

func jsonEqual(actual json.RawMessage, expected string) bool {
	var a, e any
	if err := json.Unmarshal(actual, &a); err != nil {
		return false
	}
	if err := json.Unmarshal([]byte(expected), &e); err != nil {
		return false
	}

	return reflect.DeepEqual(a, e)
}
