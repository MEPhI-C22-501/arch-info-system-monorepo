package recordrepo

import (
	"strings"
	"testing"
	"time"

	"go.einride.tech/aip/filtering"
	"go.einride.tech/aip/ordering"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/access"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
)

type fields struct {
	Code   string
	Parent *int64
	Since  string
}

var desc = &record.Descriptor[fields]{
	Singular:       "unit",
	Plural:         "units",
	Table:          "units",
	View:           "v_expanded_unit",
	RevisionTable:  "unit_revisions",
	RevisionColumn: "unit_id",
	Group:          access.GroupHR,
	Columns: []record.Column[fields]{
		{Name: "code", Type: filtering.TypeString, Stored: true, Updatable: true,
			Value: func(f *fields) any { return f.Code }, Ptr: func(f *fields) any { return &f.Code }},
		{Name: "since", Type: filtering.TypeString, SQL: "since::text", Stored: true, Updatable: true,
			Value: func(f *fields) any { return f.Since }, Ptr: func(f *fields) any { return &f.Since }},
		{Name: "parent", Type: filtering.TypeInt, Stored: false,
			Value: func(f *fields) any { return f.Parent }, Ptr: func(f *fields) any { return &f.Parent }},
	},
}

func TestRepositoryQueries(t *testing.T) {
	t.Parallel()

	r := NewRepository(nil, desc)

	want := map[string]string{
		"insert": "INSERT INTO units (code, since, is_deleted)\nVALUES ($1, $2, $3)\nRETURNING id",
		"update": "UPDATE units\nSET code = $2, since = $3, is_deleted = $4\nWHERE id = $1",
		"delete": "DELETE FROM units\nWHERE id = $1",
		"select": "SELECT id, code, since, parent, is_deleted, revision, last_changer, created_at, updated_at, deleted_at\nFROM v_expanded_unit",
	}
	got := map[string]string{"insert": r.insertQuery, "update": r.updateQuery, "delete": r.deleteQuery, "select": r.selectQuery}
	for name, query := range want {
		if got[name] != query {
			t.Errorf("%s query:\nwant %q\ngot  %q", name, query, got[name])
		}
	}

	columns := r.Columns()
	if columns["since"] != "since::text" || columns["parent"] != "parent" || columns["last_changer"] != "last_changer::text" {
		t.Errorf("unexpected filter columns %v", columns)
	}

	id := int64(5)
	args := r.writeArgs(&record.Record[fields]{ID: 1, Fields: fields{Code: "dev", Since: "2026-01-01", Parent: &id}})
	if len(args) != 3 || args[0] != "dev" || args[1] != "2026-01-01" || args[2] != false {
		t.Errorf("unexpected write arguments %v", args)
	}
}

func TestRepositoryListQuery(t *testing.T) {
	t.Parallel()

	r := NewRepository(nil, desc)

	declarations, err := filtering.NewDeclarations(
		filtering.DeclareStandardFunctions(),
		filtering.DeclareIdent("code", filtering.TypeString),
		filtering.DeclareIdent("parent", filtering.TypeInt),
	)
	if err != nil {
		t.Fatal(err)
	}

	filter, err := filtering.ParseFilterString(`code = "dev" AND parent = 1`, declarations)
	if err != nil {
		t.Fatal(err)
	}

	var orderBy ordering.OrderBy
	if err := orderBy.UnmarshalString("since desc"); err != nil {
		t.Fatal(err)
	}

	query, args, err := r.buildListQuery(&record.ListQuery{Filter: filter, OrderBy: orderBy, Offset: 20, Limit: 10})
	if err != nil {
		t.Fatal(err)
	}

	for _, part := range []string{"WHERE is_deleted = FALSE AND ((code = $1) AND (parent = $2))", "ORDER BY since::text DESC, id", "LIMIT $3 OFFSET $4"} {
		if !strings.Contains(query, part) {
			t.Errorf("query lacks %q:\n%s", part, query)
		}
	}
	if len(args) != 4 || args[0] != "dev" || args[1] != int64(1) || args[2] != int32(10) || args[3] != int64(20) {
		t.Errorf("unexpected arguments %v", args)
	}

	all, args, err := r.buildListQuery(&record.ListQuery{AllowDeleted: true})
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(all, "WHERE") || strings.Contains(all, "LIMIT") || len(args) != 0 {
		t.Errorf("an unlimited query of all records must have no conditions:\n%s", all)
	}
}

func TestRepositorySliceQuery(t *testing.T) {
	t.Parallel()

	r := NewRepository(nil, desc)

	declarations, err := filtering.NewDeclarations(filtering.DeclareStandardFunctions(), filtering.DeclareIdent("code", filtering.TypeString))
	if err != nil {
		t.Fatal(err)
	}

	filter, err := filtering.ParseFilterString(`code = "dev"`, declarations)
	if err != nil {
		t.Fatal(err)
	}

	moment := time.Date(2026, 10, 1, 9, 0, 0, 0, time.UTC)

	query, args, err := r.buildListQuery(&record.ListQuery{Filter: filter, ReadTime: moment, Limit: 10})
	if err != nil {
		t.Fatal(err)
	}

	for _, part := range []string{
		"SELECT id, code, since, parent, is_deleted, revision, last_changer, created_at, updated_at, deleted_at\nFROM (\nWITH revs AS (",
		"FROM unit_revisions r\n    WHERE r.changed_at <= $1\n",
		"SELECT s.record_id AS id, p.code, p.since, NULL::bigint AS parent, COALESCE((s.state ->> 'is_deleted')::boolean, FALSE) AS is_deleted,",
		"CROSS JOIN LATERAL jsonb_populate_record(NULL::units, s.state) AS p\n) AS slice",
		"WHERE is_deleted = FALSE AND (code = $2)",
		"LIMIT $3 OFFSET $4",
	} {
		if !strings.Contains(query, part) {
			t.Errorf("slice query lacks %q:\n%s", part, query)
		}
	}
	if strings.Contains(query, "v_expanded_unit") {
		t.Errorf("a slice must not read the view of the current state:\n%s", query)
	}
	if len(args) != 4 || args[0] != moment || args[1] != "dev" {
		t.Errorf("the moment must be the first argument, got %v", args)
	}

	current, _, err := r.buildListQuery(&record.ListQuery{})
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(current, r.selectQuery) || strings.Contains(current, "unit_revisions") {
		t.Errorf("without a moment the list reads the view:\n%s", current)
	}
}

func TestRevisionRepositoryQueries(t *testing.T) {
	t.Parallel()

	r := NewRevisionRepository(nil, "unit", "unit_revisions", "unit_id")

	if r.insertQuery != "INSERT INTO unit_revisions (unit_id, revision_number, change, changed_by)\nVALUES ($1, $2, $3, $4)" {
		t.Errorf("unexpected insert query %q", r.insertQuery)
	}

	query, args, err := r.buildListQuery(&record.RevisionListQuery{RecordID: 7, Limit: 5, Offset: 0})
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(query, "WHERE unit_id = $1") || !strings.Contains(query, "ORDER BY revision_number") || len(args) != 3 {
		t.Errorf("unexpected revision list query %q with %v", query, args)
	}
}
