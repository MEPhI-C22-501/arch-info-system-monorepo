package currencyrepo_test

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"testing"
	"time"
	"uuid"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/pashagolub/pgxmock/v4"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.einride.tech/aip/filtering"
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

func TestCurrencyRevisionRepositoryGetCurrencyRevision(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupPgxMock func(m pgxmock.PgxConnIface, query string)
		}
		args struct {
			currencyID     int64
			revisionNumber int32
		}
		want struct {
			result *currencydmn.CurrencyRevision
			err    error
		}
	)

	var (
		changer     = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		change      = `[{"op":"replace","path":"/name","value":"US Dollar"}]`
		changedAt   = time.Date(2026, 10, 5, 7, 54, 0, 0, time.UTC)
		errDatabase = errors.New("database error")

		columns = []string{"id", "currency_id", "revision_number", "change", "changed_by", "changed_at"}
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
						WithArgs(int64(1), int32(2)).
						WillReturnRows(pgxmock.NewRows(columns).AddRow(
							int64(10), int64(1), int32(2), json.RawMessage(change), changer, changedAt,
						))
				},
			},
			args: args{
				currencyID:     1,
				revisionNumber: 2,
			},
			want: want{
				result: &currencydmn.CurrencyRevision{
					ID:             10,
					CurrencyID:     1,
					RevisionNumber: 2,
					Change:         json.RawMessage(change),
					ChangedBy:      changer,
					ChangedAt:      changedAt,
				},
			},
		},
		"not found": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectQuery(query).
						WithArgs(int64(1), int32(2)).
						WillReturnError(pgx.ErrNoRows)
				},
			},
			args: args{
				currencyID:     1,
				revisionNumber: 2,
			},
			want: want{
				err: domains.ErrNotFound,
			},
		},
		"unexpected database error": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectQuery(query).
						WithArgs(int64(1), int32(2)).
						WillReturnError(errDatabase)
				},
			},
			args: args{
				currencyID:     1,
				revisionNumber: 2,
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
			tc.fields.setupPgxMock(pgxMock, readQuery(t, "get_currency_revision.sql"))

			ctrl := gomock.NewController(t)
			mockDB := mocks.NewMockDB(ctrl)
			mockDB.EXPECT().Querier(gomock.Any()).Return(pgxMock)

			repository := currencyrepo.NewCurrencyRevisionRepository(mockDB)

			result, err := repository.GetCurrencyRevision(context.Background(), tc.args.currencyID, tc.args.revisionNumber)

			assert.ErrorIs(t, err, tc.want.err)
			assert.Equal(t, tc.want.result, result)
			assert.NoError(t, pgxMock.ExpectationsWereMet())
		})
	}
}

func TestCurrencyRevisionRepositoryListCurrencyRevisions(t *testing.T) {
	t.Parallel()

	type (
		fields struct {
			setupPgxMock func(m pgxmock.PgxConnIface, query string)
		}
		args struct {
			query *currencydmn.RevisionListQuery
		}
		want struct {
			result []*currencydmn.CurrencyRevision
			err    error
		}
	)

	var (
		changer     = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")
		created     = `[{"op":"add","path":"/code","value":"USD"}]`
		deleted     = `[{"op":"replace","path":"/is_deleted","value":true}]`
		createdAt   = time.Date(2026, 10, 5, 7, 54, 0, 0, time.UTC)
		deletedAt   = time.Date(2026, 10, 6, 7, 54, 0, 0, time.UTC)
		errDatabase = errors.New("database error")

		columns = []string{"id", "currency_id", "revision_number", "change", "changed_by", "changed_at"}

		first = &currencydmn.CurrencyRevision{
			ID:             1,
			CurrencyID:     1,
			RevisionNumber: 1,
			Change:         json.RawMessage(created),
			ChangedBy:      changer,
			ChangedAt:      createdAt,
		}
		second = &currencydmn.CurrencyRevision{
			ID:             2,
			CurrencyID:     1,
			RevisionNumber: 2,
			Change:         json.RawMessage(deleted),
			ChangedBy:      changer,
			ChangedAt:      deletedAt,
		}

		noPgxCalls = func(_ pgxmock.PgxConnIface, _ string) {}
	)

	testCases := map[string]struct {
		fields fields
		args   args
		want   want
	}{
		"revisions of a currency by default": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectQuery(query+"\nWHERE currency_id = $1\nORDER BY revision_number\nLIMIT $2 OFFSET $3").
						WithArgs(int64(1), int32(21), int64(0)).
						WillReturnRows(pgxmock.NewRows(columns).
							AddRow(int64(1), int64(1), int32(1), json.RawMessage(created), changer, createdAt).
							AddRow(int64(2), int64(1), int32(2), json.RawMessage(deleted), changer, deletedAt))
				},
			},
			args: args{
				query: &currencydmn.RevisionListQuery{CurrencyID: 1, Limit: 21},
			},
			want: want{
				result: []*currencydmn.CurrencyRevision{first, second},
			},
		},
		"filter, ordering and offset": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectQuery(query+"\nWHERE currency_id = $1 AND (revision_number = $2)\n"+
						"ORDER BY changed_at DESC, revision_number\nLIMIT $3 OFFSET $4").
						WithArgs(int64(1), int64(2), int32(11), int64(20)).
						WillReturnRows(pgxmock.NewRows(columns))
				},
			},
			args: args{
				query: &currencydmn.RevisionListQuery{
					CurrencyID: 1,
					Filter:     parseRevisionFilter(t, "revision_number = 2"),
					OrderBy:    parseOrderBy(t, "changed_at desc"),
					Offset:     20,
					Limit:      11,
				},
			},
			want: want{
				result: []*currencydmn.CurrencyRevision{},
			},
		},
		"filter field without a column": {
			fields: fields{
				setupPgxMock: noPgxCalls,
			},
			args: args{
				query: &currencydmn.RevisionListQuery{
					CurrencyID: 1,
					Filter:     parseRevisionFilter(t, `secret = "x"`),
					Limit:      21,
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
				query: &currencydmn.RevisionListQuery{
					CurrencyID: 1,
					OrderBy:    parseOrderBy(t, "secret"),
					Limit:      21,
				},
			},
			want: want{
				err: domains.ErrInvalidArgument,
			},
		},
		"unexpected database error": {
			fields: fields{
				setupPgxMock: func(m pgxmock.PgxConnIface, query string) {
					m.ExpectQuery(query+"\nWHERE currency_id = $1\nORDER BY revision_number\nLIMIT $2 OFFSET $3").
						WithArgs(int64(1), int32(21), int64(0)).
						WillReturnError(errDatabase)
				},
			},
			args: args{
				query: &currencydmn.RevisionListQuery{CurrencyID: 1, Limit: 21},
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
			tc.fields.setupPgxMock(pgxMock, strings.TrimSpace(readQuery(t, "list_currency_revisions.sql")))

			ctrl := gomock.NewController(t)
			mockDB := mocks.NewMockDB(ctrl)
			mockDB.EXPECT().Querier(gomock.Any()).Return(pgxMock).AnyTimes()

			repository := currencyrepo.NewCurrencyRevisionRepository(mockDB)

			result, err := repository.ListCurrencyRevisions(context.Background(), tc.args.query)

			assert.ErrorIs(t, err, tc.want.err)
			assert.Equal(t, tc.want.result, result)
			assert.NoError(t, pgxMock.ExpectationsWereMet())
		})
	}
}

func parseRevisionFilter(t *testing.T, filter string) filtering.Filter {
	t.Helper()

	declarations, err := filtering.NewDeclarations(
		filtering.DeclareStandardFunctions(),
		filtering.DeclareIdent("revision_number", filtering.TypeInt),
		filtering.DeclareIdent("secret", filtering.TypeString),
	)
	require.NoError(t, err)

	parsed, err := filtering.ParseFilterString(filter, declarations)
	require.NoError(t, err)

	return parsed
}
