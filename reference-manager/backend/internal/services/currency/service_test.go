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
	"github.com/stretchr/testify/require"
	"go.einride.tech/aip/ordering"
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
		noExpandedCurrencyRepositoryCalls = func(_ *mocks.MockExpandedCurrencyRepository) {}
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

func TestServiceGetCurrency(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupExpandedCurrencyRepositoryMock func(m *mocks.MockExpandedCurrencyRepository)
		}
		args struct {
			ctx          context.Context
			currencyID   int64
			allowDeleted bool
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
		deletedAt         = time.Date(2026, 10, 6, 7, 54, 0, 0, time.UTC)
		errDatabase       = errors.New("database error")

		authenticatedCtx = actor.WithUserID(context.Background(), changer)

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
		deletedCurrency = &currencydmn.ExpandedCurrency{
			ID:          currencyID,
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
		}

		returnCurrency = func(c *currencydmn.ExpandedCurrency) func(m *mocks.MockExpandedCurrencyRepository) {
			return func(m *mocks.MockExpandedCurrencyRepository) {
				m.EXPECT().
					GetExpandedCurrency(gomock.Any(), currencyID).
					Return(c, nil)
			}
		}
		noExpandedCurrencyRepositoryCalls = func(_ *mocks.MockExpandedCurrencyRepository) {}
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"success": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: returnCurrency(expandedCurrency),
			},
			args: args{
				ctx:        authenticatedCtx,
				currencyID: currencyID,
			},
			want: want{
				result: expandedCurrency,
			},
		},
		"deleted currency is allowed": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: returnCurrency(deletedCurrency),
			},
			args: args{
				ctx:          authenticatedCtx,
				currencyID:   currencyID,
				allowDeleted: true,
			},
			want: want{
				result: deletedCurrency,
			},
		},
		"deleted currency is hidden": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: returnCurrency(deletedCurrency),
			},
			args: args{
				ctx:        authenticatedCtx,
				currencyID: currencyID,
			},
			want: want{
				err: domains.ErrNotFound,
			},
		},
		"unauthenticated": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:        context.Background(),
				currencyID: currencyID,
			},
			want: want{
				err: domains.ErrUnauthenticated,
			},
		},
		"currency not found": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(nil, domains.ErrNotFound)
				},
			},
			args: args{
				ctx:        authenticatedCtx,
				currencyID: currencyID,
			},
			want: want{
				err: domains.ErrNotFound,
			},
		},
		"get expanded currency failed": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(nil, errDatabase)
				},
			},
			args: args{
				ctx:        authenticatedCtx,
				currencyID: currencyID,
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

			mockExpandedCurrencyRepository := mocks.NewMockExpandedCurrencyRepository(ctrl)
			tc.fields.setupExpandedCurrencyRepositoryMock(mockExpandedCurrencyRepository)

			service := currencysrv.NewService(
				mocks.NewMockTxManager(ctrl),
				mocks.NewMockCurrencyRepository(ctrl),
				mocks.NewMockCurrencyVersionRepository(ctrl),
				mockExpandedCurrencyRepository,
			)

			result, err := service.GetCurrency(tc.args.ctx, tc.args.currencyID, tc.args.allowDeleted)

			assert.ErrorIs(t, err, tc.want.err)
			assert.Equal(t, tc.want.result, result)
		})
	}
}

func TestServiceListCurrencies(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupExpandedCurrencyRepositoryMock func(m *mocks.MockExpandedCurrencyRepository)
		}
		args struct {
			ctx     context.Context
			request *currencydmn.ListRequest
		}
		want struct {
			currencies    []*currencydmn.ExpandedCurrency
			nextPageToken bool
			err           error
			errMessage    string
		}
	)

	var (
		changer     = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		errDatabase = errors.New("database error")

		authenticatedCtx = actor.WithUserID(context.Background(), changer)

		usd = &currencydmn.ExpandedCurrency{ID: 1, Code: "USD", Number: "840", Name: "US Dollar", Decimals: 2}
		eur = &currencydmn.ExpandedCurrency{ID: 2, Code: "EUR", Number: "978", Name: "Euro", Decimals: 2}
		jpy = &currencydmn.ExpandedCurrency{ID: 3, Code: "JPY", Number: "392", Name: "Yen"}

		query = func(limit int32, offset int64, allowDeleted, hasFilter bool, orderBy ...ordering.Field) any {
			return gomock.Cond(func(q *currencydmn.ListQuery) bool {
				return q.Limit == limit &&
					q.Offset == offset &&
					q.AllowDeleted == allowDeleted &&
					(q.Filter.CheckedExpr != nil) == hasFilter &&
					reflect.DeepEqual(q.OrderBy.Fields, orderBy)
			})
		}
		noExpandedCurrencyRepositoryCalls = func(_ *mocks.MockExpandedCurrencyRepository) {}
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"page with a next page": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						ListExpandedCurrencies(gomock.Any(), query(3, 0, false, false)).
						Return([]*currencydmn.ExpandedCurrency{usd, eur, jpy}, nil)
				},
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.ListRequest{PageSize: 2},
			},
			want: want{
				currencies:    []*currencydmn.ExpandedCurrency{usd, eur},
				nextPageToken: true,
			},
		},
		"last page": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						ListExpandedCurrencies(gomock.Any(), query(3, 0, false, false)).
						Return([]*currencydmn.ExpandedCurrency{usd, eur}, nil)
				},
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.ListRequest{PageSize: 2},
			},
			want: want{
				currencies: []*currencydmn.ExpandedCurrency{usd, eur},
			},
		},
		"default page size": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						ListExpandedCurrencies(gomock.Any(), query(21, 0, false, false)).
						Return([]*currencydmn.ExpandedCurrency{}, nil)
				},
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.ListRequest{},
			},
			want: want{
				currencies: []*currencydmn.ExpandedCurrency{},
			},
		},
		"page size is capped": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						ListExpandedCurrencies(gomock.Any(), query(101, 0, false, false)).
						Return([]*currencydmn.ExpandedCurrency{}, nil)
				},
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.ListRequest{PageSize: 1000},
			},
			want: want{
				currencies: []*currencydmn.ExpandedCurrency{},
			},
		},
		"filter, ordering and deleted currencies": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						ListExpandedCurrencies(gomock.Any(), query(21, 0, true, true,
							ordering.Field{Path: "decimals", Desc: true},
							ordering.Field{Path: "code"},
						)).
						Return([]*currencydmn.ExpandedCurrency{usd}, nil)
				},
			},
			args: args{
				ctx: authenticatedCtx,
				request: &currencydmn.ListRequest{
					Filter:       `decimals >= 2 AND name:"dollar" AND is_deleted = true AND created_at > "2026-01-01T00:00:00Z"`,
					OrderBy:      "decimals desc, code",
					AllowDeleted: true,
				},
			},
			want: want{
				currencies: []*currencydmn.ExpandedCurrency{usd},
			},
		},
		"unauthenticated": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:     context.Background(),
				request: &currencydmn.ListRequest{},
			},
			want: want{
				err: domains.ErrUnauthenticated,
			},
		},
		"negative page size": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.ListRequest{PageSize: -1},
			},
			want: want{
				err: domains.ErrInvalidArgument,
			},
		},
		"filter with an unknown field": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.ListRequest{Filter: `status = "ACTIVE"`},
			},
			want: want{
				err: domains.ErrInvalidArgument,
			},
		},
		"filter with a type mismatch": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.ListRequest{Filter: `decimals = "two"`},
			},
			want: want{
				err: domains.ErrInvalidArgument,
			},
		},
		"malformed filter": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.ListRequest{Filter: `code = `},
			},
			want: want{
				err:        domains.ErrInvalidArgument,
				errMessage: "invalid filter: syntax error at 1:7: unexpected end of filter",
			},
		},
		"ordering by an unknown field": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.ListRequest{OrderBy: "status"},
			},
			want: want{
				err: domains.ErrInvalidArgument,
			},
		},
		"malformed ordering": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.ListRequest{OrderBy: "code upward"},
			},
			want: want{
				err: domains.ErrInvalidArgument,
			},
		},
		"malformed page token": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.ListRequest{PageToken: "not-a-token"},
			},
			want: want{
				err: domains.ErrInvalidArgument,
			},
		},
		"list expanded currencies failed": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						ListExpandedCurrencies(gomock.Any(), gomock.Any()).
						Return(nil, errDatabase)
				},
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.ListRequest{},
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

			mockExpandedCurrencyRepository := mocks.NewMockExpandedCurrencyRepository(ctrl)
			tc.fields.setupExpandedCurrencyRepositoryMock(mockExpandedCurrencyRepository)

			service := currencysrv.NewService(
				mocks.NewMockTxManager(ctrl),
				mocks.NewMockCurrencyRepository(ctrl),
				mocks.NewMockCurrencyVersionRepository(ctrl),
				mockExpandedCurrencyRepository,
			)

			page, err := service.ListCurrencies(tc.args.ctx, tc.args.request)

			assert.ErrorIs(t, err, tc.want.err)
			if tc.want.errMessage != "" {
				assert.EqualError(t, err, tc.want.errMessage)
			}
			if tc.want.err != nil {
				assert.Nil(t, page)
				return
			}

			assert.Equal(t, tc.want.currencies, page.Currencies)
			assert.Equal(t, tc.want.nextPageToken, page.NextPageToken != "")
		})
	}
}

func TestServiceListCurrenciesPageToken(t *testing.T) {
	t.Parallel()

	var (
		ctx = actor.WithUserID(context.Background(), uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6"))

		usd = &currencydmn.ExpandedCurrency{ID: 1, Code: "USD"}
		eur = &currencydmn.ExpandedCurrency{ID: 2, Code: "EUR"}

		request = currencydmn.ListRequest{PageSize: 1, Filter: `decimals = 2`, OrderBy: "code"}
	)

	ctrl := gomock.NewController(t)
	mockExpandedCurrencyRepository := mocks.NewMockExpandedCurrencyRepository(ctrl)

	service := currencysrv.NewService(
		mocks.NewMockTxManager(ctrl),
		mocks.NewMockCurrencyRepository(ctrl),
		mocks.NewMockCurrencyVersionRepository(ctrl),
		mockExpandedCurrencyRepository,
	)

	mockExpandedCurrencyRepository.EXPECT().
		ListExpandedCurrencies(gomock.Any(), gomock.Cond(func(q *currencydmn.ListQuery) bool { return q.Offset == 0 })).
		Return([]*currencydmn.ExpandedCurrency{usd, eur}, nil)

	first, err := service.ListCurrencies(ctx, &request)
	require.NoError(t, err)
	require.NotEmpty(t, first.NextPageToken)
	assert.Regexp(t, `^[a-zA-Z0-9_-]+$`, first.NextPageToken)

	t.Run("token continues the same request", func(t *testing.T) {
		mockExpandedCurrencyRepository.EXPECT().
			ListExpandedCurrencies(gomock.Any(), gomock.Cond(func(q *currencydmn.ListQuery) bool { return q.Offset == 1 })).
			Return([]*currencydmn.ExpandedCurrency{eur}, nil)

		// Page size may change between pages (AIP-158).
		next := request
		next.PageToken = first.NextPageToken
		next.PageSize = 5

		second, err := service.ListCurrencies(ctx, &next)
		require.NoError(t, err)
		assert.Equal(t, []*currencydmn.ExpandedCurrency{eur}, second.Currencies)
		assert.Empty(t, second.NextPageToken)
	})

	for name, change := range map[string]func(r *currencydmn.ListRequest){
		"filter":        func(r *currencydmn.ListRequest) { r.Filter = `decimals = 0` },
		"order_by":      func(r *currencydmn.ListRequest) { r.OrderBy = "name" },
		"allow deleted": func(r *currencydmn.ListRequest) { r.AllowDeleted = true },
	} {
		t.Run("token is rejected after "+name+" changes", func(t *testing.T) {
			next := request
			next.PageToken = first.NextPageToken
			change(&next)

			_, err := service.ListCurrencies(ctx, &next)
			assert.ErrorIs(t, err, domains.ErrInvalidArgument)
		})
	}
}

func TestServiceExportCurrencies(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupExpandedCurrencyRepositoryMock func(m *mocks.MockExpandedCurrencyRepository)
		}
		args struct {
			ctx context.Context
		}
		want struct {
			currencies []*currencydmn.ExpandedCurrency
			err        error
		}
	)

	var (
		errDatabase = errors.New("database error")

		authenticatedCtx = actor.WithUserID(context.Background(), uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6"))

		usd = &currencydmn.ExpandedCurrency{ID: 1, Code: "USD", Number: "840", Name: "US Dollar", Decimals: 2}
		eur = &currencydmn.ExpandedCurrency{ID: 2, Code: "EUR", Number: "978", Name: "Euro", Decimals: 2}

		// Export takes all active currencies in the default order.
		allActiveCurrencies = gomock.Cond(func(q *currencydmn.ListQuery) bool {
			return q.Limit == 0 &&
				q.Offset == 0 &&
				!q.AllowDeleted &&
				q.Filter.CheckedExpr == nil &&
				len(q.OrderBy.Fields) == 0
		})
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"success": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						ListExpandedCurrencies(gomock.Any(), allActiveCurrencies).
						Return([]*currencydmn.ExpandedCurrency{usd, eur}, nil)
				},
			},
			args: args{
				ctx: authenticatedCtx,
			},
			want: want{
				currencies: []*currencydmn.ExpandedCurrency{usd, eur},
			},
		},
		"unauthenticated": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: func(_ *mocks.MockExpandedCurrencyRepository) {},
			},
			args: args{
				ctx: context.Background(),
			},
			want: want{
				err: domains.ErrUnauthenticated,
			},
		},
		"list expanded currencies failed": {
			fields: fields{
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						ListExpandedCurrencies(gomock.Any(), gomock.Any()).
						Return(nil, errDatabase)
				},
			},
			args: args{
				ctx: authenticatedCtx,
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

			mockExpandedCurrencyRepository := mocks.NewMockExpandedCurrencyRepository(ctrl)
			tc.fields.setupExpandedCurrencyRepositoryMock(mockExpandedCurrencyRepository)

			service := currencysrv.NewService(
				mocks.NewMockTxManager(ctrl),
				mocks.NewMockCurrencyRepository(ctrl),
				mocks.NewMockCurrencyVersionRepository(ctrl),
				mockExpandedCurrencyRepository,
			)

			currencies, err := service.ExportCurrencies(tc.args.ctx)

			assert.ErrorIs(t, err, tc.want.err)
			assert.Equal(t, tc.want.currencies, currencies)
		})
	}
}

func TestServiceUpdateCurrency(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupTxManagerMock                  func(m *mocks.MockTxManager)
			setupCurrencyRepositoryMock         func(m *mocks.MockCurrencyRepository)
			setupCurrencyVersionRepositoryMock  func(m *mocks.MockCurrencyVersionRepository)
			setupExpandedCurrencyRepositoryMock func(m *mocks.MockExpandedCurrencyRepository)
		}
		args struct {
			ctx     context.Context
			request *currencydmn.UpdateRequest
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
		updatedAt         = time.Date(2026, 10, 6, 7, 54, 0, 0, time.UTC)
		errDatabase       = errors.New("database error")

		authenticatedCtx = actor.WithUserID(context.Background(), changer)

		current = &currencydmn.ExpandedCurrency{
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
		deleted = &currencydmn.ExpandedCurrency{
			ID:          currencyID,
			Code:        "USD",
			Number:      "840",
			Name:        "US Dollar",
			Decimals:    2,
			IsDeleted:   true,
			Revision:    2,
			LastChanger: changer,
			CreatedAt:   createdAt,
			UpdatedAt:   updatedAt,
			DeletedAt:   updatedAt,
		}
		updated = &currencydmn.ExpandedCurrency{
			ID:          currencyID,
			Code:        "USD",
			Number:      "840",
			Name:        "United States Dollar",
			Decimals:    2,
			Revision:    2,
			LastChanger: changer,
			CreatedAt:   createdAt,
			UpdatedAt:   updatedAt,
		}
		// requested changes the name and the number, and tries to delete the currency.
		requested = &currencydmn.Currency{
			Code:      "USD",
			Number:    "999",
			Name:      "United States Dollar",
			Decimals:  2,
			IsDeleted: true,
		}
		renamed = &currencydmn.Currency{
			ID:       currencyID,
			Code:     "USD",
			Number:   "840",
			Name:     "United States Dollar",
			Decimals: 2,
		}
		renameRevision = gomock.Cond(func(r *currencydmn.CurrencyRevision) bool {
			return r.CurrencyID == currencyID &&
				r.RevisionNumber == 2 &&
				r.ChangedBy == changer &&
				jsonEqual(r.Change, `[{"op": "replace", "path": "/name", "value": "United States Dollar"}]`)
		})

		runInTx = func(m *mocks.MockTxManager) {
			m.EXPECT().
				Do(gomock.Any(), gomock.Any()).
				DoAndReturn(func(ctx context.Context, fn func(ctx context.Context) error) error {
					return fn(ctx)
				})
		}
		returnCurrent = func(c *currencydmn.ExpandedCurrency) func(m *mocks.MockExpandedCurrencyRepository) {
			return func(m *mocks.MockExpandedCurrencyRepository) {
				m.EXPECT().
					GetExpandedCurrency(gomock.Any(), currencyID).
					Return(c, nil)
			}
		}
		returnCurrentAndUpdated = func(m *mocks.MockExpandedCurrencyRepository) {
			gomock.InOrder(
				m.EXPECT().GetExpandedCurrency(gomock.Any(), currencyID).Return(current, nil),
				m.EXPECT().GetExpandedCurrency(gomock.Any(), currencyID).Return(updated, nil),
			)
		}
		updateCurrency = func(m *mocks.MockCurrencyRepository) {
			m.EXPECT().
				UpdateCurrency(gomock.Any(), renamed).
				Return(nil)
		}
		createRevision = func(m *mocks.MockCurrencyVersionRepository) {
			m.EXPECT().
				CreateCurrencyRevision(gomock.Any(), renameRevision).
				Return(nil)
		}
		noTxManagerCalls                  = func(_ *mocks.MockTxManager) {}
		noCurrencyRepositoryCalls         = func(_ *mocks.MockCurrencyRepository) {}
		noCurrencyVersionRepositoryCalls  = func(_ *mocks.MockCurrencyVersionRepository) {}
		noExpandedCurrencyRepositoryCalls = func(_ *mocks.MockExpandedCurrencyRepository) {}
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"success with mask": {
			fields: fields{
				setupTxManagerMock:                  runInTx,
				setupCurrencyRepositoryMock:         updateCurrency,
				setupCurrencyVersionRepositoryMock:  createRevision,
				setupExpandedCurrencyRepositoryMock: returnCurrentAndUpdated,
			},
			args: args{
				ctx: authenticatedCtx,
				request: &currencydmn.UpdateRequest{
					CurrencyID: currencyID,
					Currency:   requested,
					UpdateMask: " name ",
				},
			},
			want: want{
				result: updated,
			},
		},
		"success without mask": {
			fields: fields{
				setupTxManagerMock: runInTx,
				setupCurrencyRepositoryMock: func(m *mocks.MockCurrencyRepository) {
					m.EXPECT().
						UpdateCurrency(gomock.Any(), &currencydmn.Currency{
							ID:       currencyID,
							Code:     "USD",
							Number:   "999",
							Name:     "United States Dollar",
							Decimals: 2,
						}).
						Return(nil)
				},
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						CreateCurrencyRevision(gomock.Any(), gomock.Cond(func(r *currencydmn.CurrencyRevision) bool {
							return r.RevisionNumber == 2 && jsonEqual(r.Change, `[
								{"op": "replace", "path": "/name", "value": "United States Dollar"},
								{"op": "replace", "path": "/number", "value": "999"}
							]`)
						})).
						Return(nil)
				},
				setupExpandedCurrencyRepositoryMock: returnCurrentAndUpdated,
			},
			args: args{
				ctx: authenticatedCtx,
				request: &currencydmn.UpdateRequest{
					CurrencyID: currencyID,
					Currency:   requested,
				},
			},
			want: want{
				result: updated,
			},
		},
		"nothing changed": {
			fields: fields{
				setupTxManagerMock:                  runInTx,
				setupCurrencyRepositoryMock:         noCurrencyRepositoryCalls,
				setupCurrencyVersionRepositoryMock:  noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: returnCurrent(current),
			},
			args: args{
				ctx: authenticatedCtx,
				request: &currencydmn.UpdateRequest{
					CurrencyID: currencyID,
					Currency:   requested,
					UpdateMask: "code,decimals",
				},
			},
			want: want{
				result: current,
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
				ctx: context.Background(),
				request: &currencydmn.UpdateRequest{
					CurrencyID: currencyID,
					Currency:   requested,
				},
			},
			want: want{
				err: domains.ErrUnauthenticated,
			},
		},
		"read-only field in mask": {
			fields: fields{
				setupTxManagerMock:                  noTxManagerCalls,
				setupCurrencyRepositoryMock:         noCurrencyRepositoryCalls,
				setupCurrencyVersionRepositoryMock:  noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx: authenticatedCtx,
				request: &currencydmn.UpdateRequest{
					CurrencyID: currencyID,
					Currency:   requested,
					UpdateMask: "name,is_deleted",
				},
			},
			want: want{
				err: domains.ErrInvalidArgument,
			},
		},
		"unknown field in mask": {
			fields: fields{
				setupTxManagerMock:                  noTxManagerCalls,
				setupCurrencyRepositoryMock:         noCurrencyRepositoryCalls,
				setupCurrencyVersionRepositoryMock:  noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx: authenticatedCtx,
				request: &currencydmn.UpdateRequest{
					CurrencyID: currencyID,
					Currency:   requested,
					UpdateMask: "symbol",
				},
			},
			want: want{
				err: domains.ErrInvalidArgument,
			},
		},
		"currency not found": {
			fields: fields{
				setupTxManagerMock:                 runInTx,
				setupCurrencyRepositoryMock:        noCurrencyRepositoryCalls,
				setupCurrencyVersionRepositoryMock: noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(nil, domains.ErrNotFound)
				},
			},
			args: args{
				ctx: authenticatedCtx,
				request: &currencydmn.UpdateRequest{
					CurrencyID: currencyID,
					Currency:   requested,
				},
			},
			want: want{
				err: domains.ErrNotFound,
			},
		},
		"currency is deleted": {
			fields: fields{
				setupTxManagerMock:                  runInTx,
				setupCurrencyRepositoryMock:         noCurrencyRepositoryCalls,
				setupCurrencyVersionRepositoryMock:  noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: returnCurrent(deleted),
			},
			args: args{
				ctx: authenticatedCtx,
				request: &currencydmn.UpdateRequest{
					CurrencyID: currencyID,
					Currency:   requested,
				},
			},
			want: want{
				err: domains.ErrNotFound,
			},
		},
		"code or number already taken": {
			fields: fields{
				setupTxManagerMock: runInTx,
				setupCurrencyRepositoryMock: func(m *mocks.MockCurrencyRepository) {
					m.EXPECT().
						UpdateCurrency(gomock.Any(), renamed).
						Return(domains.ErrAlreadyExists)
				},
				setupCurrencyVersionRepositoryMock:  noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: returnCurrent(current),
			},
			args: args{
				ctx: authenticatedCtx,
				request: &currencydmn.UpdateRequest{
					CurrencyID: currencyID,
					Currency:   requested,
					UpdateMask: "name",
				},
			},
			want: want{
				err: domains.ErrAlreadyExists,
			},
		},
		"revision taken concurrently": {
			fields: fields{
				setupTxManagerMock:          runInTx,
				setupCurrencyRepositoryMock: updateCurrency,
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						CreateCurrencyRevision(gomock.Any(), renameRevision).
						Return(domains.ErrAlreadyExists)
				},
				setupExpandedCurrencyRepositoryMock: returnCurrent(current),
			},
			args: args{
				ctx: authenticatedCtx,
				request: &currencydmn.UpdateRequest{
					CurrencyID: currencyID,
					Currency:   requested,
					UpdateMask: "name",
				},
			},
			want: want{
				err: domains.ErrConflict,
			},
		},
		"create currency revision failed": {
			fields: fields{
				setupTxManagerMock:          runInTx,
				setupCurrencyRepositoryMock: updateCurrency,
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						CreateCurrencyRevision(gomock.Any(), renameRevision).
						Return(errDatabase)
				},
				setupExpandedCurrencyRepositoryMock: returnCurrent(current),
			},
			args: args{
				ctx: authenticatedCtx,
				request: &currencydmn.UpdateRequest{
					CurrencyID: currencyID,
					Currency:   requested,
					UpdateMask: "name",
				},
			},
			want: want{
				err: errDatabase,
			},
		},
		"get updated currency failed": {
			fields: fields{
				setupTxManagerMock:                 runInTx,
				setupCurrencyRepositoryMock:        updateCurrency,
				setupCurrencyVersionRepositoryMock: createRevision,
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					gomock.InOrder(
						m.EXPECT().GetExpandedCurrency(gomock.Any(), currencyID).Return(current, nil),
						m.EXPECT().GetExpandedCurrency(gomock.Any(), currencyID).Return(nil, errDatabase),
					)
				},
			},
			args: args{
				ctx: authenticatedCtx,
				request: &currencydmn.UpdateRequest{
					CurrencyID: currencyID,
					Currency:   requested,
					UpdateMask: "name",
				},
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
				ctx: authenticatedCtx,
				request: &currencydmn.UpdateRequest{
					CurrencyID: currencyID,
					Currency:   requested,
				},
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

			result, err := service.UpdateCurrency(tc.args.ctx, tc.args.request)

			assert.ErrorIs(t, err, tc.want.err)
			assert.Equal(t, tc.want.result, result)
		})
	}
}

func TestServiceDeleteCurrency(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupTxManagerMock                  func(m *mocks.MockTxManager)
			setupCurrencyRepositoryMock         func(m *mocks.MockCurrencyRepository)
			setupCurrencyVersionRepositoryMock  func(m *mocks.MockCurrencyVersionRepository)
			setupExpandedCurrencyRepositoryMock func(m *mocks.MockExpandedCurrencyRepository)
		}
		args struct {
			ctx context.Context
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
		deletedAt         = time.Date(2026, 10, 6, 7, 54, 0, 0, time.UTC)
		errDatabase       = errors.New("database error")

		authenticatedCtx = actor.WithUserID(context.Background(), changer)

		current = &currencydmn.ExpandedCurrency{
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
		deleted = &currencydmn.ExpandedCurrency{
			ID:          currencyID,
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
		}
		deletedModel = &currencydmn.Currency{
			ID:        currencyID,
			Code:      "USD",
			Number:    "840",
			Name:      "US Dollar",
			Decimals:  2,
			IsDeleted: true,
		}
		deletionRevision = gomock.Cond(func(r *currencydmn.CurrencyRevision) bool {
			return r.CurrencyID == currencyID &&
				r.RevisionNumber == 2 &&
				r.ChangedBy == changer &&
				jsonEqual(r.Change, `[{"op": "replace", "path": "/is_deleted", "value": true}]`)
		})

		runInTx = func(m *mocks.MockTxManager) {
			m.EXPECT().
				Do(gomock.Any(), gomock.Any()).
				DoAndReturn(func(ctx context.Context, fn func(ctx context.Context) error) error {
					return fn(ctx)
				})
		}
		updateCurrency = func(m *mocks.MockCurrencyRepository) {
			m.EXPECT().
				UpdateCurrency(gomock.Any(), deletedModel).
				Return(nil)
		}
		noTxManagerCalls                  = func(_ *mocks.MockTxManager) {}
		noCurrencyRepositoryCalls         = func(_ *mocks.MockCurrencyRepository) {}
		noCurrencyVersionRepositoryCalls  = func(_ *mocks.MockCurrencyVersionRepository) {}
		noExpandedCurrencyRepositoryCalls = func(_ *mocks.MockExpandedCurrencyRepository) {}
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"success": {
			fields: fields{
				setupTxManagerMock:          runInTx,
				setupCurrencyRepositoryMock: updateCurrency,
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						CreateCurrencyRevision(gomock.Any(), deletionRevision).
						Return(nil)
				},
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					gomock.InOrder(
						m.EXPECT().GetExpandedCurrency(gomock.Any(), currencyID).Return(current, nil),
						m.EXPECT().GetExpandedCurrency(gomock.Any(), currencyID).Return(deleted, nil),
					)
				},
			},
			args: args{
				ctx: authenticatedCtx,
			},
			want: want{
				result: deleted,
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
				ctx: context.Background(),
			},
			want: want{
				err: domains.ErrUnauthenticated,
			},
		},
		"currency not found": {
			fields: fields{
				setupTxManagerMock:                 runInTx,
				setupCurrencyRepositoryMock:        noCurrencyRepositoryCalls,
				setupCurrencyVersionRepositoryMock: noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(nil, domains.ErrNotFound)
				},
			},
			args: args{
				ctx: authenticatedCtx,
			},
			want: want{
				err: domains.ErrNotFound,
			},
		},
		"currency is already deleted": {
			fields: fields{
				setupTxManagerMock:                 runInTx,
				setupCurrencyRepositoryMock:        noCurrencyRepositoryCalls,
				setupCurrencyVersionRepositoryMock: noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(deleted, nil)
				},
			},
			args: args{
				ctx: authenticatedCtx,
			},
			want: want{
				err: domains.ErrNotFound,
			},
		},
		"revision taken concurrently": {
			fields: fields{
				setupTxManagerMock:          runInTx,
				setupCurrencyRepositoryMock: updateCurrency,
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						CreateCurrencyRevision(gomock.Any(), deletionRevision).
						Return(domains.ErrAlreadyExists)
				},
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(current, nil)
				},
			},
			args: args{
				ctx: authenticatedCtx,
			},
			want: want{
				err: domains.ErrConflict,
			},
		},
		"update currency failed": {
			fields: fields{
				setupTxManagerMock: runInTx,
				setupCurrencyRepositoryMock: func(m *mocks.MockCurrencyRepository) {
					m.EXPECT().
						UpdateCurrency(gomock.Any(), deletedModel).
						Return(errDatabase)
				},
				setupCurrencyVersionRepositoryMock: noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(current, nil)
				},
			},
			args: args{
				ctx: authenticatedCtx,
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
				ctx: authenticatedCtx,
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

			result, err := service.DeleteCurrency(tc.args.ctx, currencyID)

			assert.ErrorIs(t, err, tc.want.err)
			assert.Equal(t, tc.want.result, result)
		})
	}
}

func TestServicePurgeCurrency(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupCurrencyRepositoryMock func(m *mocks.MockCurrencyRepository)
		}
		args struct {
			ctx context.Context
		}
		want struct {
			err error
		}
	)

	var (
		currencyID  int64 = 1
		changer           = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		errDatabase       = errors.New("database error")

		authenticatedCtx = actor.WithUserID(context.Background(), changer)

		deleteCurrency = func(err error) func(m *mocks.MockCurrencyRepository) {
			return func(m *mocks.MockCurrencyRepository) {
				m.EXPECT().
					DeleteCurrency(gomock.Any(), currencyID).
					Return(err)
			}
		}
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"success": {
			fields: fields{
				setupCurrencyRepositoryMock: deleteCurrency(nil),
			},
			args: args{
				ctx: authenticatedCtx,
			},
		},
		"unauthenticated": {
			fields: fields{
				setupCurrencyRepositoryMock: func(_ *mocks.MockCurrencyRepository) {},
			},
			args: args{
				ctx: context.Background(),
			},
			want: want{
				err: domains.ErrUnauthenticated,
			},
		},
		"currency not found": {
			fields: fields{
				setupCurrencyRepositoryMock: deleteCurrency(domains.ErrNotFound),
			},
			args: args{
				ctx: authenticatedCtx,
			},
			want: want{
				err: domains.ErrNotFound,
			},
		},
		"delete currency failed": {
			fields: fields{
				setupCurrencyRepositoryMock: deleteCurrency(errDatabase),
			},
			args: args{
				ctx: authenticatedCtx,
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

			mockCurrencyRepository := mocks.NewMockCurrencyRepository(ctrl)
			tc.fields.setupCurrencyRepositoryMock(mockCurrencyRepository)

			service := currencysrv.NewService(
				mocks.NewMockTxManager(ctrl),
				mockCurrencyRepository,
				mocks.NewMockCurrencyVersionRepository(ctrl),
				mocks.NewMockExpandedCurrencyRepository(ctrl),
			)

			err := service.PurgeCurrency(tc.args.ctx, currencyID)

			assert.ErrorIs(t, err, tc.want.err)
		})
	}
}

func TestServiceGetCurrencyRevision(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupCurrencyVersionRepositoryMock  func(m *mocks.MockCurrencyVersionRepository)
			setupExpandedCurrencyRepositoryMock func(m *mocks.MockExpandedCurrencyRepository)
		}
		args struct {
			ctx            context.Context
			currencyID     int64
			revisionNumber int32
			allowDeleted   bool
		}
		want struct {
			result *currencydmn.CurrencyRevision
			err    error
		}
	)

	var (
		currencyID     int64 = 1
		revisionNumber int32 = 2
		changer              = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		errDatabase          = errors.New("database error")

		authenticatedCtx = actor.WithUserID(context.Background(), changer)

		usd        = &currencydmn.ExpandedCurrency{ID: currencyID, Code: "USD", Revision: 2}
		deletedUSD = &currencydmn.ExpandedCurrency{ID: currencyID, Code: "USD", Revision: 2, IsDeleted: true}
		revision   = &currencydmn.CurrencyRevision{
			ID:             10,
			CurrencyID:     currencyID,
			RevisionNumber: revisionNumber,
			Change:         json.RawMessage(`[{"op":"replace","path":"/name","value":"US Dollar"}]`),
			ChangedBy:      changer,
			ChangedAt:      time.Date(2026, 10, 6, 7, 54, 0, 0, time.UTC),
		}

		noCurrencyVersionRepositoryCalls  = func(_ *mocks.MockCurrencyVersionRepository) {}
		noExpandedCurrencyRepositoryCalls = func(_ *mocks.MockExpandedCurrencyRepository) {}
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"success": {
			fields: fields{
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						GetCurrencyRevision(gomock.Any(), currencyID, revisionNumber).
						Return(revision, nil)
				},
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(usd, nil)
				},
			},
			args: args{
				ctx:            authenticatedCtx,
				currencyID:     currencyID,
				revisionNumber: revisionNumber,
			},
			want: want{
				result: revision,
			},
		},
		"revision of a deleted currency is allowed": {
			fields: fields{
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						GetCurrencyRevision(gomock.Any(), currencyID, revisionNumber).
						Return(revision, nil)
				},
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(deletedUSD, nil)
				},
			},
			args: args{
				ctx:            authenticatedCtx,
				currencyID:     currencyID,
				revisionNumber: revisionNumber,
				allowDeleted:   true,
			},
			want: want{
				result: revision,
			},
		},
		"revision of a deleted currency is hidden": {
			fields: fields{
				setupCurrencyVersionRepositoryMock: noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(deletedUSD, nil)
				},
			},
			args: args{
				ctx:            authenticatedCtx,
				currencyID:     currencyID,
				revisionNumber: revisionNumber,
			},
			want: want{
				err: domains.ErrNotFound,
			},
		},
		"unauthenticated": {
			fields: fields{
				setupCurrencyVersionRepositoryMock:  noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:            context.Background(),
				currencyID:     currencyID,
				revisionNumber: revisionNumber,
			},
			want: want{
				err: domains.ErrUnauthenticated,
			},
		},
		"currency not found": {
			fields: fields{
				setupCurrencyVersionRepositoryMock: noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(nil, domains.ErrNotFound)
				},
			},
			args: args{
				ctx:            authenticatedCtx,
				currencyID:     currencyID,
				revisionNumber: revisionNumber,
			},
			want: want{
				err: domains.ErrNotFound,
			},
		},
		"revision not found": {
			fields: fields{
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						GetCurrencyRevision(gomock.Any(), currencyID, revisionNumber).
						Return(nil, domains.ErrNotFound)
				},
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(usd, nil)
				},
			},
			args: args{
				ctx:            authenticatedCtx,
				currencyID:     currencyID,
				revisionNumber: revisionNumber,
			},
			want: want{
				err: domains.ErrRevisionNotFound,
			},
		},
		"get expanded currency failed": {
			fields: fields{
				setupCurrencyVersionRepositoryMock: noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(nil, errDatabase)
				},
			},
			args: args{
				ctx:            authenticatedCtx,
				currencyID:     currencyID,
				revisionNumber: revisionNumber,
			},
			want: want{
				err: errDatabase,
			},
		},
		"get currency revision failed": {
			fields: fields{
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						GetCurrencyRevision(gomock.Any(), currencyID, revisionNumber).
						Return(nil, errDatabase)
				},
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(usd, nil)
				},
			},
			args: args{
				ctx:            authenticatedCtx,
				currencyID:     currencyID,
				revisionNumber: revisionNumber,
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

			mockCurrencyVersionRepository := mocks.NewMockCurrencyVersionRepository(ctrl)
			tc.fields.setupCurrencyVersionRepositoryMock(mockCurrencyVersionRepository)

			mockExpandedCurrencyRepository := mocks.NewMockExpandedCurrencyRepository(ctrl)
			tc.fields.setupExpandedCurrencyRepositoryMock(mockExpandedCurrencyRepository)

			service := currencysrv.NewService(
				mocks.NewMockTxManager(ctrl),
				mocks.NewMockCurrencyRepository(ctrl),
				mockCurrencyVersionRepository,
				mockExpandedCurrencyRepository,
			)

			result, err := service.GetCurrencyRevision(tc.args.ctx, tc.args.currencyID, tc.args.revisionNumber, tc.args.allowDeleted)

			assert.ErrorIs(t, err, tc.want.err)
			assert.Equal(t, tc.want.result, result)
		})
	}
}

func TestServiceListCurrencyRevisions(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupCurrencyVersionRepositoryMock  func(m *mocks.MockCurrencyVersionRepository)
			setupExpandedCurrencyRepositoryMock func(m *mocks.MockExpandedCurrencyRepository)
		}
		args struct {
			ctx     context.Context
			request *currencydmn.RevisionListRequest
		}
		want struct {
			revisions     []*currencydmn.CurrencyRevision
			nextPageToken bool
			err           error
		}
	)

	var (
		currencyID  int64 = 1
		changer           = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		errDatabase       = errors.New("database error")

		authenticatedCtx = actor.WithUserID(context.Background(), changer)

		usd        = &currencydmn.ExpandedCurrency{ID: currencyID, Code: "USD", Revision: 3}
		deletedUSD = &currencydmn.ExpandedCurrency{ID: currencyID, Code: "USD", Revision: 3, IsDeleted: true}

		first  = &currencydmn.CurrencyRevision{ID: 1, CurrencyID: currencyID, RevisionNumber: 1}
		second = &currencydmn.CurrencyRevision{ID: 2, CurrencyID: currencyID, RevisionNumber: 2}
		third  = &currencydmn.CurrencyRevision{ID: 3, CurrencyID: currencyID, RevisionNumber: 3}

		query = func(limit int32, offset int64, hasFilter bool, orderBy ...ordering.Field) any {
			return gomock.Cond(func(q *currencydmn.RevisionListQuery) bool {
				return q.CurrencyID == currencyID &&
					q.Limit == limit &&
					q.Offset == offset &&
					(q.Filter.CheckedExpr != nil) == hasFilter &&
					reflect.DeepEqual(q.OrderBy.Fields, orderBy)
			})
		}
		existingCurrency = func(m *mocks.MockExpandedCurrencyRepository) {
			m.EXPECT().
				GetExpandedCurrency(gomock.Any(), currencyID).
				Return(usd, nil)
		}
		noCurrencyVersionRepositoryCalls  = func(_ *mocks.MockCurrencyVersionRepository) {}
		noExpandedCurrencyRepositoryCalls = func(_ *mocks.MockExpandedCurrencyRepository) {}
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"page with a next page": {
			fields: fields{
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						ListCurrencyRevisions(gomock.Any(), query(3, 0, false)).
						Return([]*currencydmn.CurrencyRevision{first, second, third}, nil)
				},
				setupExpandedCurrencyRepositoryMock: existingCurrency,
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.RevisionListRequest{CurrencyID: currencyID, PageSize: 2},
			},
			want: want{
				revisions:     []*currencydmn.CurrencyRevision{first, second},
				nextPageToken: true,
			},
		},
		"last page": {
			fields: fields{
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						ListCurrencyRevisions(gomock.Any(), query(3, 0, false)).
						Return([]*currencydmn.CurrencyRevision{first, second}, nil)
				},
				setupExpandedCurrencyRepositoryMock: existingCurrency,
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.RevisionListRequest{CurrencyID: currencyID, PageSize: 2},
			},
			want: want{
				revisions: []*currencydmn.CurrencyRevision{first, second},
			},
		},
		"default page size": {
			fields: fields{
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						ListCurrencyRevisions(gomock.Any(), query(21, 0, false)).
						Return([]*currencydmn.CurrencyRevision{}, nil)
				},
				setupExpandedCurrencyRepositoryMock: existingCurrency,
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.RevisionListRequest{CurrencyID: currencyID},
			},
			want: want{
				revisions: []*currencydmn.CurrencyRevision{},
			},
		},
		"page size is capped": {
			fields: fields{
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						ListCurrencyRevisions(gomock.Any(), query(101, 0, false)).
						Return([]*currencydmn.CurrencyRevision{}, nil)
				},
				setupExpandedCurrencyRepositoryMock: existingCurrency,
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.RevisionListRequest{CurrencyID: currencyID, PageSize: 1000},
			},
			want: want{
				revisions: []*currencydmn.CurrencyRevision{},
			},
		},
		"filter, ordering and deleted currency": {
			fields: fields{
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						ListCurrencyRevisions(gomock.Any(), query(21, 0, true,
							ordering.Field{Path: "changed_at", Desc: true},
							ordering.Field{Path: "revision_number"},
						)).
						Return([]*currencydmn.CurrencyRevision{third}, nil)
				},
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(deletedUSD, nil)
				},
			},
			args: args{
				ctx: authenticatedCtx,
				request: &currencydmn.RevisionListRequest{
					CurrencyID:   currencyID,
					Filter:       `revision_number >= 2 AND changed_by = "3fa85f64-5717-4562-b3fc-2c963f66afa6" AND changed_at > "2026-01-01T00:00:00Z"`,
					OrderBy:      "changed_at desc, revision_number",
					AllowDeleted: true,
				},
			},
			want: want{
				revisions: []*currencydmn.CurrencyRevision{third},
			},
		},
		"revisions of a deleted currency are hidden": {
			fields: fields{
				setupCurrencyVersionRepositoryMock: noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(deletedUSD, nil)
				},
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.RevisionListRequest{CurrencyID: currencyID},
			},
			want: want{
				err: domains.ErrNotFound,
			},
		},
		"currency not found": {
			fields: fields{
				setupCurrencyVersionRepositoryMock: noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(nil, domains.ErrNotFound)
				},
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.RevisionListRequest{CurrencyID: currencyID},
			},
			want: want{
				err: domains.ErrNotFound,
			},
		},
		"unauthenticated": {
			fields: fields{
				setupCurrencyVersionRepositoryMock:  noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:     context.Background(),
				request: &currencydmn.RevisionListRequest{CurrencyID: currencyID},
			},
			want: want{
				err: domains.ErrUnauthenticated,
			},
		},
		"negative page size": {
			fields: fields{
				setupCurrencyVersionRepositoryMock:  noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.RevisionListRequest{CurrencyID: currencyID, PageSize: -1},
			},
			want: want{
				err: domains.ErrInvalidArgument,
			},
		},
		"filter with a currency field": {
			fields: fields{
				setupCurrencyVersionRepositoryMock:  noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.RevisionListRequest{CurrencyID: currencyID, Filter: `code = "USD"`},
			},
			want: want{
				err: domains.ErrInvalidArgument,
			},
		},
		"ordering by a field that is not sortable": {
			fields: fields{
				setupCurrencyVersionRepositoryMock:  noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.RevisionListRequest{CurrencyID: currencyID, OrderBy: "changed_by"},
			},
			want: want{
				err: domains.ErrInvalidArgument,
			},
		},
		"malformed page token": {
			fields: fields{
				setupCurrencyVersionRepositoryMock:  noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: noExpandedCurrencyRepositoryCalls,
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.RevisionListRequest{CurrencyID: currencyID, PageToken: "not-a-token"},
			},
			want: want{
				err: domains.ErrInvalidArgument,
			},
		},
		"get expanded currency failed": {
			fields: fields{
				setupCurrencyVersionRepositoryMock: noCurrencyVersionRepositoryCalls,
				setupExpandedCurrencyRepositoryMock: func(m *mocks.MockExpandedCurrencyRepository) {
					m.EXPECT().
						GetExpandedCurrency(gomock.Any(), currencyID).
						Return(nil, errDatabase)
				},
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.RevisionListRequest{CurrencyID: currencyID},
			},
			want: want{
				err: errDatabase,
			},
		},
		"list currency revisions failed": {
			fields: fields{
				setupCurrencyVersionRepositoryMock: func(m *mocks.MockCurrencyVersionRepository) {
					m.EXPECT().
						ListCurrencyRevisions(gomock.Any(), gomock.Any()).
						Return(nil, errDatabase)
				},
				setupExpandedCurrencyRepositoryMock: existingCurrency,
			},
			args: args{
				ctx:     authenticatedCtx,
				request: &currencydmn.RevisionListRequest{CurrencyID: currencyID},
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

			mockCurrencyVersionRepository := mocks.NewMockCurrencyVersionRepository(ctrl)
			tc.fields.setupCurrencyVersionRepositoryMock(mockCurrencyVersionRepository)

			mockExpandedCurrencyRepository := mocks.NewMockExpandedCurrencyRepository(ctrl)
			tc.fields.setupExpandedCurrencyRepositoryMock(mockExpandedCurrencyRepository)

			service := currencysrv.NewService(
				mocks.NewMockTxManager(ctrl),
				mocks.NewMockCurrencyRepository(ctrl),
				mockCurrencyVersionRepository,
				mockExpandedCurrencyRepository,
			)

			page, err := service.ListCurrencyRevisions(tc.args.ctx, tc.args.request)

			assert.ErrorIs(t, err, tc.want.err)
			if tc.want.err != nil {
				assert.Nil(t, page)
				return
			}

			assert.Equal(t, tc.want.revisions, page.Revisions)
			assert.Equal(t, tc.want.nextPageToken, page.NextPageToken != "")
		})
	}
}

func TestServiceListCurrencyRevisionsPageToken(t *testing.T) {
	t.Parallel()

	var (
		ctx = actor.WithUserID(context.Background(), uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6"))

		first  = &currencydmn.CurrencyRevision{ID: 1, CurrencyID: 1, RevisionNumber: 1}
		second = &currencydmn.CurrencyRevision{ID: 2, CurrencyID: 1, RevisionNumber: 2}

		request = currencydmn.RevisionListRequest{CurrencyID: 1, PageSize: 1, Filter: `revision_number > 0`, OrderBy: "changed_at"}
	)

	ctrl := gomock.NewController(t)
	mockCurrencyVersionRepository := mocks.NewMockCurrencyVersionRepository(ctrl)
	mockExpandedCurrencyRepository := mocks.NewMockExpandedCurrencyRepository(ctrl)

	service := currencysrv.NewService(
		mocks.NewMockTxManager(ctrl),
		mocks.NewMockCurrencyRepository(ctrl),
		mockCurrencyVersionRepository,
		mockExpandedCurrencyRepository,
	)

	mockExpandedCurrencyRepository.EXPECT().
		GetExpandedCurrency(gomock.Any(), gomock.Any()).
		Return(&currencydmn.ExpandedCurrency{ID: 1}, nil).
		AnyTimes()
	mockCurrencyVersionRepository.EXPECT().
		ListCurrencyRevisions(gomock.Any(), gomock.Cond(func(q *currencydmn.RevisionListQuery) bool { return q.Offset == 0 })).
		Return([]*currencydmn.CurrencyRevision{first, second}, nil)

	firstPage, err := service.ListCurrencyRevisions(ctx, &request)
	require.NoError(t, err)
	require.NotEmpty(t, firstPage.NextPageToken)
	assert.Regexp(t, `^[a-zA-Z0-9_-]+$`, firstPage.NextPageToken)

	t.Run("token continues the same request", func(t *testing.T) {
		mockCurrencyVersionRepository.EXPECT().
			ListCurrencyRevisions(gomock.Any(), gomock.Cond(func(q *currencydmn.RevisionListQuery) bool { return q.Offset == 1 })).
			Return([]*currencydmn.CurrencyRevision{second}, nil)

		next := request
		next.PageToken = firstPage.NextPageToken
		next.PageSize = 5

		secondPage, err := service.ListCurrencyRevisions(ctx, &next)
		require.NoError(t, err)
		assert.Equal(t, []*currencydmn.CurrencyRevision{second}, secondPage.Revisions)
		assert.Empty(t, secondPage.NextPageToken)
	})

	for name, change := range map[string]func(r *currencydmn.RevisionListRequest){
		"currency":      func(r *currencydmn.RevisionListRequest) { r.CurrencyID = 2 },
		"filter":        func(r *currencydmn.RevisionListRequest) { r.Filter = `revision_number > 1` },
		"order_by":      func(r *currencydmn.RevisionListRequest) { r.OrderBy = "revision_number" },
		"allow deleted": func(r *currencydmn.RevisionListRequest) { r.AllowDeleted = true },
	} {
		t.Run("token is rejected after "+name+" changes", func(t *testing.T) {
			next := request
			next.PageToken = firstPage.NextPageToken
			change(&next)

			_, err := service.ListCurrencyRevisions(ctx, &next)
			assert.ErrorIs(t, err, domains.ErrInvalidArgument)
		})
	}
}
