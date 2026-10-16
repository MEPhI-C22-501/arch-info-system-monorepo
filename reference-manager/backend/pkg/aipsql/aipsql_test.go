package aipsql_test

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.einride.tech/aip/filtering"
	"go.einride.tech/aip/ordering"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/aipsql"
)

var testColumns = aipsql.Columns{
	"code":       "code",
	"name":       "name",
	"decimals":   "decimals",
	"is_deleted": "is_deleted",
	"created_at": "created_at",
	"deleted_at": "deleted_at",
}

func testDeclarations(t *testing.T) *filtering.Declarations {
	t.Helper()

	declarations, err := filtering.NewDeclarations(append(
		aipsql.BoolLiteralDeclarations(),
		filtering.DeclareStandardFunctions(),
		filtering.DeclareIdent("code", filtering.TypeString),
		filtering.DeclareIdent("name", filtering.TypeString),
		filtering.DeclareIdent("decimals", filtering.TypeInt),
		filtering.DeclareIdent("is_deleted", filtering.TypeBool),
		filtering.DeclareIdent("created_at", filtering.TypeTimestamp),
		filtering.DeclareIdent("deleted_at", filtering.TypeTimestamp),
		// Declared but not mapped to a column.
		filtering.DeclareIdent("secret", filtering.TypeString),
	)...)
	require.NoError(t, err)

	return declarations
}

func TestTranspileFilter(t *testing.T) {
	t.Parallel()

	type want struct {
		sql  string
		args []any
		err  bool
	}

	createdAt := time.Date(2026, 10, 5, 7, 54, 0, 0, time.UTC)

	testCases := map[string]struct {
		filter string
		want   want
	}{
		"empty filter": {
			filter: "",
			want:   want{sql: ""},
		},
		"string equality": {
			filter: `code = "USD"`,
			want: want{
				sql:  "(code = $1)",
				args: []any{"USD"},
			},
		},
		"all comparison operators": {
			filter: `decimals != 1 AND decimals < 4 AND decimals <= 3 AND decimals > 0 AND decimals >= 1`,
			want: want{
				sql:  "(((((decimals <> $1) AND (decimals < $2)) AND (decimals <= $3)) AND (decimals > $4)) AND (decimals >= $5))",
				args: []any{int64(1), int64(4), int64(3), int64(0), int64(1)},
			},
		},
		"logical operators": {
			filter: `(code = "USD" OR code = "EUR") AND NOT is_deleted`,
			want: want{
				sql:  "(((code = $1) OR (code = $2)) AND (NOT is_deleted))",
				args: []any{"USD", "EUR"},
			},
		},
		"bool comparison": {
			filter: `is_deleted = true`,
			want: want{
				sql: "(is_deleted = TRUE)",
			},
		},
		"prefix wildcard": {
			filter: `name = "*Dollar"`,
			want: want{
				sql:  "(name LIKE $1)",
				args: []any{"%Dollar"},
			},
		},
		"negated suffix wildcard escapes LIKE characters": {
			filter: `name != "100%_*"`,
			want: want{
				sql:  "(name NOT LIKE $1)",
				args: []any{`100\%\_%`},
			},
		},
		"has on string is a case-insensitive containment": {
			filter: `name:"dollar"`,
			want: want{
				sql:  "(name ILIKE $1)",
				args: []any{"%dollar%"},
			},
		},
		"has with wildcard is a presence check": {
			filter: `deleted_at:*`,
			want: want{
				sql: "(deleted_at IS NOT NULL)",
			},
		},
		"bool literal alone": {
			filter: `false`,
			want: want{
				sql: "FALSE",
			},
		},
		"timestamp as string": {
			filter: `created_at >= "2026-10-05T07:54:00Z"`,
			want: want{
				sql:  "(created_at >= $1)",
				args: []any{createdAt},
			},
		},
		"timestamp function": {
			filter: `created_at < timestamp("2026-10-05T07:54:00Z")`,
			want: want{
				sql:  "(created_at < $1)",
				args: []any{createdAt},
			},
		},
		"field without a column": {
			filter: `secret = "x"`,
			want: want{
				err: true,
			},
		},
	}

	for name, tc := range testCases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			filter, err := filtering.ParseFilterString(tc.filter, testDeclarations(t))
			require.NoError(t, err)

			var args aipsql.Args
			sql, err := aipsql.TranspileFilter(filter, testColumns, &args)

			assert.Equal(t, tc.want.err, err != nil)
			assert.Equal(t, tc.want.sql, sql)
			assert.Equal(t, tc.want.args, args.Values())
		})
	}
}

func TestTranspileOrderBy(t *testing.T) {
	t.Parallel()

	type want struct {
		sql string
		err bool
	}

	testCases := map[string]struct {
		orderBy string
		want    want
	}{
		"no ordering uses the tiebreaker": {
			orderBy: "",
			want:    want{sql: "id"},
		},
		"several fields": {
			orderBy: "decimals desc, code",
			want:    want{sql: "decimals DESC, code, id"},
		},
		"unknown field": {
			orderBy: "secret",
			want:    want{err: true},
		},
	}

	for name, tc := range testCases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			var orderBy ordering.OrderBy
			require.NoError(t, orderBy.UnmarshalString(tc.orderBy))

			sql, err := aipsql.TranspileOrderBy(orderBy, testColumns, "id")

			assert.Equal(t, tc.want.err, err != nil)
			assert.Equal(t, tc.want.sql, sql)
		})
	}
}
