package recordsrv

import (
	"errors"
	"testing"

	"go.einride.tech/aip/filtering"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/access"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
)

type fields struct {
	Code  string
	Name  string
	Owner *int64
}

var desc = &record.Descriptor[fields]{
	Singular: "thing",
	Plural:   "things",
	Group:    access.GroupClassifiers,
	Columns: []record.Column[fields]{
		{Name: "code", Type: filtering.TypeString, Stored: true, Updatable: false,
			Value: func(f *fields) any { return f.Code }, Ptr: func(f *fields) any { return &f.Code }},
		{Name: "name", Type: filtering.TypeString, Stored: true, Updatable: true,
			Value: func(f *fields) any { return f.Name }, Ptr: func(f *fields) any { return &f.Name }},
		{Name: "owner", Type: filtering.TypeInt, Stored: true, Updatable: true,
			Value: func(f *fields) any { return f.Owner }, Ptr: func(f *fields) any { return &f.Owner }},
	},
}

func TestParseUpdateMask(t *testing.T) {
	t.Parallel()

	updatable := desc.UpdatableFields()

	for _, mask := range []string{"", "*", " * "} {
		got, err := parseUpdateMask(mask, updatable)
		if err != nil || len(got) != 2 {
			t.Errorf("mask %q: expected all updatable fields, got %v, %v", mask, got, err)
		}
	}

	got, err := parseUpdateMask(" name , owner", updatable)
	if err != nil || len(got) != 2 || got[0] != "name" || got[1] != "owner" {
		t.Errorf("expected the listed fields, got %v, %v", got, err)
	}

	_, err = parseUpdateMask("code", updatable)
	if !errors.Is(err, domains.ErrInvalidArgument) {
		t.Errorf("an immutable field must be rejected, got %v", err)
	}
}

func TestApplyUpdateMask(t *testing.T) {
	t.Parallel()

	s := NewService[fields](desc, nil, nil, nil, nil)

	owner := int64(3)
	dst := fields{Code: "a", Name: "old"}
	src := fields{Code: "b", Name: "new", Owner: &owner}

	if err := s.applyUpdateMask(&dst, &src, []string{"name", "owner"}); err != nil {
		t.Fatal(err)
	}

	if dst.Code != "a" || dst.Name != "new" || dst.Owner == nil || *dst.Owner != 3 {
		t.Errorf("unexpected result %+v", dst)
	}

	if err := s.applyUpdateMask(&dst, &src, []string{"missing"}); !errors.Is(err, domains.ErrInvalidArgument) {
		t.Errorf("an unknown field must be rejected, got %v", err)
	}
}

func TestListFieldsAndTokens(t *testing.T) {
	t.Parallel()

	s := NewService[fields](desc, nil, nil, nil, nil)

	query, token, err := listQuery(s.fields, &record.ListRequest{Filter: `name : "x" AND owner = 1 AND is_deleted = false`, OrderBy: "created_at desc, code", PageSize: 500})
	if err != nil {
		t.Fatalf("a valid request is rejected: %v", err)
	}
	if query.Limit != maxPageSize || query.Offset != 0 || token.Offset != 0 {
		t.Errorf("unexpected query %+v", query)
	}

	items, next := cutPage([]int{1, 2, 3}, 2, token)
	if len(items) != 2 || next == "" {
		t.Fatalf("expected a next page token, got %v, %q", items, next)
	}

	_, nextToken, err := listQuery(s.fields, &record.ListRequest{Filter: `name : "x" AND owner = 1 AND is_deleted = false`, OrderBy: "created_at desc, code", PageToken: next})
	if err != nil || nextToken.Offset != 2 {
		t.Errorf("the token of the same request must be accepted, got %v, %v", nextToken, err)
	}

	if _, _, err := listQuery(s.fields, &record.ListRequest{PageToken: next}); !errors.Is(err, domains.ErrInvalidArgument) {
		t.Errorf("a token of another request must be rejected, got %v", err)
	}

	for _, bad := range []record.ListRequest{{Filter: "tint = 1"}, {OrderBy: "tint"}, {Filter: "name ="}, {PageSize: -1}} {
		if _, _, err := listQuery(s.fields, &bad); !errors.Is(err, domains.ErrInvalidArgument) {
			t.Errorf("request %+v must be rejected, got %v", bad, err)
		}
	}
}
