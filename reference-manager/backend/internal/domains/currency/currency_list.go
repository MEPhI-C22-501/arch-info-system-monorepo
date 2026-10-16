package currencydmn

import (
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
}

// ListQuery is a validated request for currencies that repositories can execute.
type ListQuery struct {
	// Filter is an AIP-160 filter expression checked against the filterable fields, empty when absent.
	Filter filtering.Filter
	// OrderBy is an AIP-132 ordering validated against the sortable fields, empty when absent.
	OrderBy      ordering.OrderBy
	AllowDeleted bool
	Offset       int64
	Limit        int32
}

type ListPage struct {
	Currencies []*ExpandedCurrency
	// NextPageToken is empty on the last page.
	NextPageToken string
}
