package currencyrepo_test

import (
	"context"
	"encoding/json"
	"errors"
	"testing"
	"uuid"

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

func TestCurrencyRevisionRepositoryCreateCurrencyRevision(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupPgxMock func(m pgxmock.PgxConnIface, query string)
		}
		args struct {
			revision *currencydmn.CurrencyRevision
		}
		want struct {
			err error
		}
	)

	var (
		changer     = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		change      = `[{"op":"add","path":"/code","value":"USD"}]`
		errDatabase = errors.New("database error")

		revision = &currencydmn.CurrencyRevision{
			CurrencyID:     1,
			RevisionNumber: 1,
			Change:         json.RawMessage(change),
			ChangedBy:      changer,
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
						WithArgs(int64(1), int32(1), change, changer).
						WillReturnResult(pgxmock.NewResult("INSERT", 1))
				},
			},
			args: args{
				revision: revision,
			},
		},
		"unique violation": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectExec(query).
						WithArgs(int64(1), int32(1), change, changer).
						WillReturnError(&pgconn.PgError{Code: "23505"})
				},
			},
			args: args{
				revision: revision,
			},
			want: want{
				err: domains.ErrAlreadyExists,
			},
		},
		"foreign key violation": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectExec(query).
						WithArgs(int64(1), int32(1), change, changer).
						WillReturnError(&pgconn.PgError{Code: "23503"})
				},
			},
			args: args{
				revision: revision,
			},
			want: want{
				err: domains.ErrNotFound,
			},
		},
		"unexpected database error": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectExec(query).
						WithArgs(int64(1), int32(1), change, changer).
						WillReturnError(errDatabase)
				},
			},
			args: args{
				revision: revision,
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
			tc.fields.setupPgxMock(pgxMock, readQuery(t, "create_currency_revision.sql"))

			ctrl := gomock.NewController(t)
			mockDB := mocks.NewMockDB(ctrl)
			mockDB.EXPECT().Querier(gomock.Any()).Return(pgxMock)

			repository := currencyrepo.NewCurrencyRevisionRepository(mockDB)

			err = repository.CreateCurrencyRevision(context.Background(), tc.args.revision)

			assert.ErrorIs(t, err, tc.want.err)
			assert.NoError(t, pgxMock.ExpectationsWereMet())
		})
	}
}
