package currencydmn

import (
	"time"

	"go.einride.tech/aip/filtering"
	"go.einride.tech/aip/ordering"
)

// ListRequest is a client request for a page of currencies, its fields keep the raw client input.
type ListRequest struct {
	PageSize     int32
	PageToken    string
	Filter       string
	OrderBy      string
	AllowDeleted bool
	// ReadTime asks for the currencies as they were at the moment, rebuilt from the revisions; zero means now.
	ReadTime time.Time
}

// ExportRequest narrows the export of the active currencies, every field is optional (FR-RM-62).
type ExportRequest struct {
	Filter   string
	OrderBy  string
	ReadTime time.Time
}

// ListQuery is a validated request for currencies that repositories can execute.
type ListQuery struct {
	// Filter is an AIP-160 filter expression checked against the filterable fields, empty when absent.
	Filter filtering.Filter
	// OrderBy is an AIP-132 ordering validated against the sortable fields, empty when absent.
	OrderBy      ordering.OrderBy
	AllowDeleted bool
	// ReadTime selects the slice of the currencies at the moment instead of their current state, zero means now.
	ReadTime time.Time
	Offset   int64
	// Limit is the maximum number of currencies, zero means no limit, the offset is ignored then.
	Limit int32
}

type ListPage struct {
	Currencies []*ExpandedCurrency
	// NextPageToken is empty on the last page.
	NextPageToken string
}
