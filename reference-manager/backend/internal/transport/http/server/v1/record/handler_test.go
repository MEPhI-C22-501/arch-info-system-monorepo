package recordhndl

import (
	"errors"
	"fmt"
	"net/http"
	"testing"
	"time"

	openapi_types "github.com/oapi-codegen/runtime/types"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
)

func TestErrorToAPI(t *testing.T) {
	t.Parallel()

	cases := []struct {
		err     error
		status  int
		message string
		details int
	}{
		{&record.ValidationError{Fields: []record.FieldError{{Field: "code", Message: "required"}, {Field: "name", Message: "too long"}}}, http.StatusBadRequest, "validation failed", 2},
		{&domains.InvalidArgumentError{Argument: "filter", Err: errors.New("bad")}, http.StatusBadRequest, "invalid filter: bad", 0},
		{domains.ErrAlreadyExists, http.StatusConflict, "country already exists", 0},
		{domains.ErrConflict, http.StatusConflict, "country was modified concurrently, retry the request", 0},
		{fmt.Errorf("already dismissed: %w", domains.ErrFailedPrecondition), http.StatusBadRequest, "already dismissed: failed precondition", 0},
		{domains.ErrUnauthenticated, http.StatusUnauthorized, "unauthenticated", 0},
		{domains.ErrPermissionDenied, http.StatusForbidden, "permission denied", 0},
		{domains.ErrRevisionNotFound, http.StatusNotFound, "country revision not found", 0},
		{domains.ErrNotFound, http.StatusNotFound, "country not found", 0},
		{errors.New("boom"), http.StatusInternalServerError, "internal server error", 0},
	}

	for _, tc := range cases {
		apiErr, status := ErrorToAPI(tc.err, "country")
		if status != tc.status || apiErr.Message != tc.message || len(apiErr.Details) != tc.details {
			t.Errorf("%v: expected %d %q with %d details, got %d %q with %d", tc.err, tc.status, tc.message, tc.details, status, apiErr.Message, len(apiErr.Details))
		}
	}
}

func TestConversions(t *testing.T) {
	t.Parallel()

	type kind string

	if EnumPtr[kind](nil) != nil || EnumPtrTo[kind](nil) != nil || DatePtr(nil) != nil || DatePtrTo(nil) != nil {
		t.Fatal("nil must stay nil")
	}

	k := kind("TEAM")
	if s := EnumPtr(&k); s == nil || *s != "TEAM" {
		t.Errorf("unexpected enum conversion %v", s)
	}

	s := "DEPARTMENT"
	if e := EnumPtrTo[kind](&s); e == nil || *e != "DEPARTMENT" {
		t.Errorf("unexpected enum conversion %v", e)
	}

	day := time.Date(2026, 10, 31, 0, 0, 0, 0, time.UTC)
	if d := DatePtrTo(&day); d == nil || !d.Equal(day) {
		t.Errorf("unexpected date conversion %v", d)
	}
	if back := DatePtr(&openapi_types.Date{Time: day}); back == nil || !back.Equal(day) {
		t.Errorf("unexpected date conversion %v", back)
	}
}

func TestRevisionToAPI(t *testing.T) {
	t.Parallel()

	resp, err := RevisionToAPI("country_id", &record.Revision{ID: 9, RecordID: 2, RevisionNumber: 3, Change: []byte(`[{"op":"add","path":"/code","value":"RU"}]`)})
	if err != nil {
		t.Fatal(err)
	}
	if resp["country_id"] != int64(2) || resp["revision_number"] != int32(3) || resp["id"] != int64(9) {
		t.Errorf("unexpected revision %v", resp)
	}

	if _, err := RevisionToAPI("country_id", &record.Revision{Change: []byte("not json")}); err == nil {
		t.Error("a malformed change must be reported")
	}
}

func TestSheetName(t *testing.T) {
	t.Parallel()

	if got := sheetName("org_units"); got != "Org units" {
		t.Errorf("unexpected sheet name %q", got)
	}
	if got := sheetName(""); got != "Sheet1" {
		t.Errorf("unexpected sheet name %q", got)
	}
}
