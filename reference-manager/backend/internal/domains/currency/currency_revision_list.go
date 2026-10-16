package currencydmn

import (
	"go.einride.tech/aip/filtering"
	"go.einride.tech/aip/ordering"
)

// RevisionListRequest is a client request for a page of currency revisions, its fields keep the raw client input.
type RevisionListRequest struct {
	CurrencyID   int64
	PageSize     int32
	PageToken    string
	Filter       string
	OrderBy      string
	AllowDeleted bool
}

// RevisionListQuery is a validated request for revisions of a currency that repositories can execute.
type RevisionListQuery struct {
	CurrencyID int64
	// Filter is an AIP-160 filter expression checked against the filterable fields, empty when absent.
	Filter filtering.Filter
	// OrderBy is an AIP-132 ordering validated against the sortable fields, empty when absent.
	OrderBy ordering.OrderBy
	Offset  int64
	Limit   int32
}

type RevisionListPage struct {
	Revisions []*CurrencyRevision
	// NextPageToken is empty on the last page.
	NextPageToken string
}
