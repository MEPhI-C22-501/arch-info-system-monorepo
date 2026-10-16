package currencyrepo_test

import (
	"context"
	"errors"
	"testing"

	"github.com/jackc/pgx/v5/pgconn"
	"github.com/pashagolub/pgxmock/v4"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/mock/gomock"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	currencyrepo "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/repositories/postgres/currency"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/repositories/postgres/mocks"
)

func TestCurrencyRepositoryCreateCurrency(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupPgxMock func(m pgxmock.PgxConnIface, query string)
		}
		args struct {
			currency *currencydmn.Currency
		}
		want struct {
			id  int64
			err error
		}
	)

	var (
		errDatabase = errors.New("database error")

		currency = &currencydmn.Currency{
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
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectQuery(query).
						WithArgs("USD", "840", "US Dollar", int8(2), false).
						WillReturnRows(pgxmock.NewRows([]string{"id"}).AddRow(int64(1)))
				},
			},
			args: args{
				currency: currency,
			},
			want: want{
				id: 1,
			},
		},
		"unique violation": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectQuery(query).
						WithArgs("USD", "840", "US Dollar", int8(2), false).
						WillReturnError(&pgconn.PgError{Code: "23505"})
				},
			},
			args: args{
				currency: currency,
			},
			want: want{
				err: domains.ErrAlreadyExists,
			},
		},
		"unexpected database error": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectQuery(query).
						WithArgs("USD", "840", "US Dollar", int8(2), false).
						WillReturnError(errDatabase)
				},
			},
			args: args{
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

			pgxMock, err := pgxmock.NewConn(pgxmock.QueryMatcherOption(pgxmock.QueryMatcherEqual))
			require.NoError(t, err)
			tc.fields.setupPgxMock(pgxMock, readQuery(t, "create_currency.sql"))

			ctrl := gomock.NewController(t)
			mockDB := mocks.NewMockDB(ctrl)
			mockDB.EXPECT().Querier(gomock.Any()).Return(pgxMock)

			repository := currencyrepo.NewCurrencyRepository(mockDB)

			id, err := repository.CreateCurrency(context.Background(), tc.args.currency)

			assert.ErrorIs(t, err, tc.want.err)
			assert.Equal(t, tc.want.id, id)
			assert.NoError(t, pgxMock.ExpectationsWereMet())
		})
	}
}

func TestCurrencyRepositoryUpdateCurrency(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupPgxMock func(m pgxmock.PgxConnIface, query string)
		}
		args struct {
			currency *currencydmn.Currency
		}
		want struct {
			err error
		}
	)

	var (
		errDatabase = errors.New("database error")

		currency = &currencydmn.Currency{
			ID:       1,
			Code:     "USD",
			Number:   "840",
			Name:     "United States Dollar",
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
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectExec(query).
						WithArgs(int64(1), "USD", "840", "United States Dollar", int8(2), false).
						WillReturnResult(pgxmock.NewResult("UPDATE", 1))
				},
			},
			args: args{
				currency: currency,
			},
		},
		"currency not found": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectExec(query).
						WithArgs(int64(1), "USD", "840", "United States Dollar", int8(2), false).
						WillReturnResult(pgxmock.NewResult("UPDATE", 0))
				},
			},
			args: args{
				currency: currency,
			},
			want: want{
				err: domains.ErrNotFound,
			},
		},
		"unique violation": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectExec(query).
						WithArgs(int64(1), "USD", "840", "United States Dollar", int8(2), false).
						WillReturnError(&pgconn.PgError{Code: "23505"})
				},
			},
			args: args{
				currency: currency,
			},
			want: want{
				err: domains.ErrAlreadyExists,
			},
		},
		"unexpected database error": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectExec(query).
						WithArgs(int64(1), "USD", "840", "United States Dollar", int8(2), false).
						WillReturnError(errDatabase)
				},
			},
			args: args{
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

			pgxMock, err := pgxmock.NewConn(pgxmock.QueryMatcherOption(pgxmock.QueryMatcherEqual))
			require.NoError(t, err)
			tc.fields.setupPgxMock(pgxMock, readQuery(t, "update_currency.sql"))

			ctrl := gomock.NewController(t)
			mockDB := mocks.NewMockDB(ctrl)
			mockDB.EXPECT().Querier(gomock.Any()).Return(pgxMock)

			repository := currencyrepo.NewCurrencyRepository(mockDB)

			err = repository.UpdateCurrency(context.Background(), tc.args.currency)

			assert.ErrorIs(t, err, tc.want.err)
			assert.NoError(t, pgxMock.ExpectationsWereMet())
		})
	}
}

func TestCurrencyRepositoryDeleteCurrency(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupPgxMock func(m pgxmock.PgxConnIface, query string)
		}
		args struct {
			currencyID int64
		}
		want struct {
			err error
		}
	)

	errDatabase := errors.New("database error")

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"success": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectExec(query).
						WithArgs(int64(1)).
						WillReturnResult(pgxmock.NewResult("DELETE", 1))
				},
			},
			args: args{
				currencyID: 1,
			},
		},
		"currency not found": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectExec(query).
						WithArgs(int64(1)).
						WillReturnResult(pgxmock.NewResult("DELETE", 0))
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
					m.ExpectExec(query).
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
			tc.fields.setupPgxMock(pgxMock, readQuery(t, "delete_currency.sql"))

			ctrl := gomock.NewController(t)
			mockDB := mocks.NewMockDB(ctrl)
			mockDB.EXPECT().Querier(gomock.Any()).Return(pgxMock)

			repository := currencyrepo.NewCurrencyRepository(mockDB)

			err = repository.DeleteCurrency(context.Background(), tc.args.currencyID)

			assert.ErrorIs(t, err, tc.want.err)
			assert.NoError(t, pgxMock.ExpectationsWereMet())
		})
	}
}
