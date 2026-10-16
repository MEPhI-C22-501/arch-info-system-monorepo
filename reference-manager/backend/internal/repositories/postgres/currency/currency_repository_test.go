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
