package currencyrepo_test

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"
	"uuid"

	"github.com/jackc/pgx/v5"
	"github.com/pashagolub/pgxmock/v4"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.einride.tech/aip/filtering"
	"go.einride.tech/aip/ordering"
	"go.uber.org/mock/gomock"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	currencyrepo "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/repositories/postgres/currency"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/repositories/postgres/mocks"
)

func TestExpandedCurrencyRepositoryGetExpandedCurrency(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupPgxMock func(m pgxmock.PgxConnIface, query string)
		}
		args struct {
			currencyID int64
		}
		want struct {
			result *currencydmn.ExpandedCurrency
			err    error
		}
	)

	var (
		revision    int32 = 2
		changer           = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		createdAt         = time.Date(2026, 10, 5, 7, 54, 0, 0, time.UTC)
		updatedAt         = time.Date(2026, 10, 6, 7, 54, 0, 0, time.UTC)
		errDatabase       = errors.New("database error")

		columns = []string{
			"id", "code", "number", "name", "decimals", "is_deleted",
			"revision", "last_changer", "created_at", "updated_at", "deleted_at",
		}
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"success": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectQuery(query).
						WithArgs(int64(1)).
						WillReturnRows(pgxmock.NewRows(columns).AddRow(
							int64(1), "USD", "840", "US Dollar", int8(2), false,
							&revision, &changer, &createdAt, &updatedAt, nil,
						))
				},
			},
			args: args{
				currencyID: 1,
			},
			want: want{
				result: &currencydmn.ExpandedCurrency{
					ID:          1,
					Code:        "USD",
					Number:      "840",
					Name:        "US Dollar",
					Decimals:    2,
					Revision:    2,
					LastChanger: changer,
					CreatedAt:   createdAt,
					UpdatedAt:   updatedAt,
				},
			},
		},
		"currency without revisions": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectQuery(query).
						WithArgs(int64(1)).
						WillReturnRows(pgxmock.NewRows(columns).AddRow(
							int64(1), "USD", "840", "US Dollar", int8(2), false,
							nil, nil, nil, nil, nil,
						))
				},
			},
			args: args{
				currencyID: 1,
			},
			want: want{
				result: &currencydmn.ExpandedCurrency{
					ID:       1,
					Code:     "USD",
					Number:   "840",
					Name:     "US Dollar",
					Decimals: 2,
				},
			},
		},
		"not found": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectQuery(query).
						WithArgs(int64(1)).
						WillReturnError(pgx.ErrNoRows)
				},
			},
			args: args{
				currencyID: 1,
			},
			want: want{
				err: domains.ErrNotFound,
			},
		},
		"unexpected database error": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectQuery(query).
						WithArgs(int64(1)).
						WillReturnError(errDatabase)
				},
			},
			args: args{
				currencyID: 1,
			},
			want: want{
				err: errDatabase,
			},
		},
	}

	for name, tc := range testCases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			pgxMock, err := pgxmock.NewConn(pgxmock.QueryMatcherOption(pgxmock.QueryMatcherEqual))
			require.NoError(t, err)
			tc.fields.setupPgxMock(pgxMock, readQuery(t, "get_expanded_currency.sql"))

			ctrl := gomock.NewController(t)
			mockDB := mocks.NewMockDB(ctrl)
			mockDB.EXPECT().Querier(gomock.Any()).Return(pgxMock)

			repository := currencyrepo.NewExpandedCurrencyRepository(mockDB)

			result, err := repository.GetExpandedCurrency(context.Background(), tc.args.currencyID)

			assert.ErrorIs(t, err, tc.want.err)
			assert.Equal(t, tc.want.result, result)
			assert.NoError(t, pgxMock.ExpectationsWereMet())
		})
	}
}

func TestExpandedCurrencyRepositoryListExpandedCurrencies(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupPgxMock func(m pgxmock.PgxConnIface, query string)
		}
		args struct {
			query *currencydmn.ListQuery
		}
		want struct {
			result []*currencydmn.ExpandedCurrency
			err    error
		}
	)

	var (
		revision    int32 = 1
		changer           = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		createdAt         = time.Date(2026, 10, 5, 7, 54, 0, 0, time.UTC)
		errDatabase       = errors.New("database error")

		columns = []string{
			"id", "code", "number", "name", "decimals", "is_deleted",
			"revision", "last_changer", "created_at", "updated_at", "deleted_at",
		}

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
		eur = &currencydmn.ExpandedCurrency{
			ID:       2,
			Code:     "EUR",
			Number:   "978",
			Name:     "Euro",
			Decimals: 2,
		}

		noPgxCalls = func(_ pgxmock.PgxConnIface, _ string) {}
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"active currencies by default": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectQuery(query+"\nWHERE is_deleted = FALSE\nORDER BY id\nLIMIT $1 OFFSET $2").
						WithArgs(int32(21), int64(0)).
						WillReturnRows(pgxmock.NewRows(columns).
							AddRow(
								int64(1), "USD", "840", "US Dollar", int8(2), false,
								&revision, &changer, &createdAt, &createdAt, nil,
							).
							AddRow(
								int64(2), "EUR", "978", "Euro", int8(2), false,
								nil, nil, nil, nil, nil,
							))
				},
			},
			args: args{
				query: &currencydmn.ListQuery{Limit: 21},
			},
			want: want{
				result: []*currencydmn.ExpandedCurrency{usd, eur},
			},
		},
		"filter, ordering and offset with deleted currencies": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectQuery(query+"\nWHERE (code = $1)\nORDER BY name DESC, id\nLIMIT $2 OFFSET $3").
						WithArgs("USD", int32(11), int64(20)).
						WillReturnRows(pgxmock.NewRows(columns))
				},
			},
			args: args{
				query: &currencydmn.ListQuery{
					Filter:       parseFilter(t, `code = "USD"`),
					OrderBy:      parseOrderBy(t, "name desc"),
					AllowDeleted: true,
					Offset:       20,
					Limit:        11,
				},
			},
			want: want{
				result: []*currencydmn.ExpandedCurrency{},
			},
		},
		"filter field without a column": {
			fields: fields{
				setupPgxMock: noPgxCalls,
			},
			args: args{
				query: &currencydmn.ListQuery{
					Filter: parseFilter(t, `secret = "x"`),
					Limit:  21,
				},
			},
			want: want{
				err: domains.ErrInvalidArgument,
			},
		},
		"order field without a column": {
			fields: fields{
				setupPgxMock: noPgxCalls,
			},
			args: args{
				query: &currencydmn.ListQuery{
					OrderBy: parseOrderBy(t, "secret"),
					Limit:   21,
				},
			},
			want: want{
				err: domains.ErrInvalidArgument,
			},
		},
		"unexpected database error": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectQuery(query+"\nWHERE is_deleted = FALSE\nORDER BY id\nLIMIT $1 OFFSET $2").
						WithArgs(int32(21), int64(0)).
						WillReturnError(errDatabase)
				},
			},
			args: args{
				query: &currencydmn.ListQuery{Limit: 21},
			},
			want: want{
				err: errDatabase,
			},
		},
	}

	for name, tc := range testCases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			pgxMock, err := pgxmock.NewConn(pgxmock.QueryMatcherOption(pgxmock.QueryMatcherEqual))
			require.NoError(t, err)
			tc.fields.setupPgxMock(pgxMock, strings.TrimSpace(readQuery(t, "list_expanded_currencies.sql")))

			ctrl := gomock.NewController(t)
			mockDB := mocks.NewMockDB(ctrl)
			mockDB.EXPECT().Querier(gomock.Any()).Return(pgxMock).AnyTimes()

			repository := currencyrepo.NewExpandedCurrencyRepository(mockDB)

			result, err := repository.ListExpandedCurrencies(context.Background(), tc.args.query)

			assert.ErrorIs(t, err, tc.want.err)
			assert.Equal(t, tc.want.result, result)
			assert.NoError(t, pgxMock.ExpectationsWereMet())
		})
	}
}

func parseFilter(t *testing.T, filter string) filtering.Filter {
	t.Helper()

	declarations, err := filtering.NewDeclarations(
		filtering.DeclareStandardFunctions(),
		filtering.DeclareIdent("code", filtering.TypeString),
		filtering.DeclareIdent("secret", filtering.TypeString),
	)
	require.NoError(t, err)

	parsed, err := filtering.ParseFilterString(filter, declarations)
	require.NoError(t, err)

	return parsed
}

func parseOrderBy(t *testing.T, orderBy string) ordering.OrderBy {
	t.Helper()

	var parsed ordering.OrderBy
	require.NoError(t, parsed.UnmarshalString(orderBy))

	return parsed
}
