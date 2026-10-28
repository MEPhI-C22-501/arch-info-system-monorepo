package record

import (
	"errors"
	"regexp"
	"testing"
	"time"

	"go.einride.tech/aip/filtering"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/access"
)

type sample struct {
	Code   string
	Note   *string
	Rank   int32
	Amount *float64
	Since  time.Time
	Until  *time.Time
	Kind   string
	Parent *int64
}

func f64(v float64) *float64 { return &v }

var sampleDescriptor = &Descriptor[sample]{
	Singular: "sample",
	Plural:   "samples",
	Group:    access.GroupClassifiers,
	Columns: []Column[sample]{
		{Name: "code", Type: filtering.TypeString, Stored: true, Updatable: true,
			Value: func(f *sample) any { return f.Code }, Ptr: func(f *sample) any { return &f.Code },
			Rules: Rules{Required: true, Pattern: regexp.MustCompile(`^[a-z]+$`), PatternText: "^[a-z]+$", MinLen: 2, MaxLen: 4}},
		{Name: "note", Type: filtering.TypeString, Stored: true, Updatable: true,
			Value: func(f *sample) any { return f.Note }, Ptr: func(f *sample) any { return &f.Note },
			Rules: Rules{MaxLen: 5}},
		{Name: "rank", Type: filtering.TypeInt, Stored: true, Updatable: true,
			Value: func(f *sample) any { return f.Rank }, Ptr: func(f *sample) any { return &f.Rank },
			Rules: Rules{Min: f64(1), Max: f64(10)}},
		{Name: "amount", Type: filtering.TypeFloat, Stored: true, Updatable: true,
			Value: func(f *sample) any { return f.Amount }, Ptr: func(f *sample) any { return &f.Amount },
			Rules: Rules{Required: true, Min: f64(0.01)}},
		{Name: "since", Type: filtering.TypeString, SQL: "since::text", Stored: true, Updatable: true,
			Value: func(f *sample) any { return f.Since }, Ptr: func(f *sample) any { return &f.Since },
			Rules: Rules{Required: true}},
		{Name: "until", Type: filtering.TypeString, SQL: "until::text", Stored: true, Updatable: true,
			Value: func(f *sample) any { return f.Until }, Ptr: func(f *sample) any { return &f.Until }},
		{Name: "kind", Type: filtering.TypeString, Stored: true, Updatable: false,
			Value: func(f *sample) any { return f.Kind }, Ptr: func(f *sample) any { return &f.Kind },
			Rules: Rules{Required: true, Enum: []string{"A", "B"}}},
		{Name: "parent", Type: filtering.TypeInt, Stored: false,
			Value: func(f *sample) any { return f.Parent }, Ptr: func(f *sample) any { return &f.Parent }},
	},
}

func TestValidateFields(t *testing.T) {
	t.Parallel()

	valid := sample{Code: "ab", Rank: 5, Amount: f64(10), Since: time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC), Kind: "A"}
	if err := ValidateFields(sampleDescriptor, &valid); err != nil {
		t.Fatalf("valid sample rejected: %v", err)
	}

	long := "toolong"
	invalid := sample{Code: "AB1", Note: &long, Rank: 11, Amount: f64(0), Kind: "C"}

	err := ValidateFields(sampleDescriptor, &invalid)
	if !errors.Is(err, domains.ErrInvalidArgument) {
		t.Fatalf("expected an invalid argument error, got %v", err)
	}

	var validationErr *ValidationError
	if !errors.As(err, &validationErr) {
		t.Fatalf("expected a ValidationError, got %T", err)
	}

	want := map[string]string{
		"code":   "must match ^[a-z]+$",
		"note":   "must be at most 5 characters long",
		"rank":   "must be at most 10",
		"amount": "must be at least 0.01",
		"since":  "required",
		"kind":   "must be one of A, B",
	}
	if len(validationErr.Fields) != len(want) {
		t.Fatalf("expected %d violations, got %d: %v", len(want), len(validationErr.Fields), validationErr.Fields)
	}
	for _, f := range validationErr.Fields {
		if want[f.Field] != f.Message {
			t.Errorf("field %s: expected %q, got %q", f.Field, want[f.Field], f.Message)
		}
	}
}

func TestValidateFieldsReportsMissingRequiredPointers(t *testing.T) {
	t.Parallel()

	missing := sample{Code: "ab", Rank: 5, Since: time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC), Kind: "A"}

	var validationErr *ValidationError
	if err := ValidateFields(sampleDescriptor, &missing); !errors.As(err, &validationErr) {
		t.Fatalf("expected a ValidationError, got %v", err)
	}

	if len(validationErr.Fields) != 1 || validationErr.Fields[0].Field != "amount" || validationErr.Fields[0].Message != "required" {
		t.Fatalf("expected the amount to be required, got %v", validationErr.Fields)
	}
}

func TestDescriptorColumns(t *testing.T) {
	t.Parallel()

	if got := len(sampleDescriptor.StoredColumns()); got != 7 {
		t.Errorf("expected 7 stored columns, got %d", got)
	}

	updatable := sampleDescriptor.UpdatableFields()
	if len(updatable) != 6 || updatable[0] != "code" || updatable[5] != "until" {
		t.Errorf("unexpected updatable fields %v", updatable)
	}

	if _, ok := sampleDescriptor.Column("parent"); !ok {
		t.Error("computed column is missing")
	}
	if _, ok := sampleDescriptor.Column("missing"); ok {
		t.Error("unknown column found")
	}
}

func TestCell(t *testing.T) {
	t.Parallel()

	note := "x"
	when := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)

	cases := map[string]struct {
		in   any
		want any
	}{
		"string":       {in: "a", want: "a"},
		"nil string":   {in: (*string)(nil), want: ""},
		"string ptr":   {in: &note, want: "x"},
		"nil int":      {in: (*int64)(nil), want: ""},
		"nil time":     {in: (*time.Time)(nil), want: ""},
		"time ptr":     {in: &when, want: when},
		"float":        {in: 1.5, want: 1.5},
		"nil float":    {in: (*float64)(nil), want: ""},
		"bool":         {in: true, want: true},
		"int32 ptr":    {in: func() *int32 { v := int32(3); return &v }(), want: int32(3)},
		"untyped keep": {in: int64(7), want: int64(7)},
	}

	for name, tc := range cases {
		if got := Cell(tc.in); got != tc.want {
			t.Errorf("%s: expected %v, got %v", name, tc.want, got)
		}
	}
}
