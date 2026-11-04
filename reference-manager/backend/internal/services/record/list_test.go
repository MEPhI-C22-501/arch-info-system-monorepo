package recordsrv

import (
	"errors"
	"testing"
	"time"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
)

func TestListQueryCarriesTheMoment(t *testing.T) {
	t.Parallel()

	fields := recordListFields(desc)
	moment := time.Date(2026, 10, 1, 12, 0, 0, 0, time.FixedZone("MSK", 3*60*60))

	query, _, err := listQuery(fields, &record.ListRequest{Filter: `name = "x"`, ReadTime: moment, PageSize: 5})
	if err != nil {
		t.Fatal(err)
	}
	if !query.ReadTime.Equal(moment) || query.ReadTime.Location() != time.UTC {
		t.Errorf("the moment must reach the query in UTC, got %v", query.ReadTime)
	}

	current, _, err := listQuery(fields, &record.ListRequest{})
	if err != nil {
		t.Fatal(err)
	}
	if !current.ReadTime.IsZero() {
		t.Errorf("a list without a moment reads the current state, got %v", current.ReadTime)
	}
}

func TestPageTokenIsBoundToTheMoment(t *testing.T) {
	t.Parallel()

	fields := recordListFields(desc)
	moment := time.Date(2026, 10, 1, 9, 0, 0, 0, time.UTC)

	// a token of the second page of a slice
	_, first, err := listQuery(fields, &record.ListRequest{ReadTime: moment, PageSize: 1})
	if err != nil {
		t.Fatal(err)
	}
	_, token := cutPage([]int{1, 2}, 1, first)

	if _, _, err := listQuery(fields, &record.ListRequest{ReadTime: moment, PageSize: 1, PageToken: token}); err != nil {
		t.Errorf("the token of a slice must be accepted for the same moment: %v", err)
	}

	for name, other := range map[string]*record.ListRequest{
		"another moment": {ReadTime: moment.Add(time.Hour), PageSize: 1, PageToken: token},
		"current state":  {PageSize: 1, PageToken: token},
	} {
		_, _, err := listQuery(fields, other)

		var invalid *domains.InvalidArgumentError
		if !errors.As(err, &invalid) || invalid.Argument != "pageToken" {
			t.Errorf("%s: the token of a slice must be rejected, got %v", name, err)
		}
	}
}

func TestExportQueryKeepsTheSelectionWithoutPaging(t *testing.T) {
	t.Parallel()

	fields := recordListFields(desc)
	moment := time.Date(2026, 10, 1, 9, 0, 0, 0, time.UTC)

	query, err := exportQuery(fields, &record.ExportRequest{Filter: `name = "x"`, OrderBy: "code desc", ReadTime: moment})
	if err != nil {
		t.Fatal(err)
	}
	if query.Limit != 0 || query.Offset != 0 || query.AllowDeleted {
		t.Errorf("an export takes every active record of the selection, got limit %d offset %d deleted %v", query.Limit, query.Offset, query.AllowDeleted)
	}
	if query.Filter.CheckedExpr == nil || len(query.OrderBy.Fields) != 1 || !query.ReadTime.Equal(moment) {
		t.Errorf("the selection is lost: %+v", query)
	}

	_, err = exportQuery(fields, &record.ExportRequest{Filter: "name = "})

	var invalid *domains.InvalidArgumentError
	if !errors.As(err, &invalid) || invalid.Argument != "filter" {
		t.Errorf("a broken filter of an export must be a 400, got %v", err)
	}

	_, err = exportQuery(fields, &record.ExportRequest{OrderBy: "id"})
	if !errors.As(err, &invalid) || invalid.Argument != "order_by" {
		t.Errorf("an export cannot be sorted by the identifier, got %v", err)
	}
}
