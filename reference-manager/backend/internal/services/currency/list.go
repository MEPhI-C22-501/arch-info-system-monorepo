package currencysrv

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"hash/crc32"
	"io"
	"strconv"

	"go.einride.tech/aip/filtering"
	"go.einride.tech/aip/ordering"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/aipsql"
)

const (
	defaultPageSize int32 = 20
	maxPageSize     int32 = 100
)

// currencyFields are the currency fields accepted in filter (AIP-160) and order_by (AIP-132).
var currencyFields = listFields{
	sortable: []string{
		"code", "number", "name", "decimals", "is_deleted",
		"revision", "created_at", "updated_at", "deleted_at",
	},
	declarations: mustDeclarations(append(
		aipsql.BoolLiteralDeclarations(),
		filtering.DeclareStandardFunctions(),
		filtering.DeclareIdent("code", filtering.TypeString),
		filtering.DeclareIdent("number", filtering.TypeString),
		filtering.DeclareIdent("name", filtering.TypeString),
		filtering.DeclareIdent("decimals", filtering.TypeInt),
		filtering.DeclareIdent("is_deleted", filtering.TypeBool),
		filtering.DeclareIdent("revision", filtering.TypeInt),
		filtering.DeclareIdent("last_changer", filtering.TypeString),
		filtering.DeclareIdent("created_at", filtering.TypeTimestamp),
		filtering.DeclareIdent("updated_at", filtering.TypeTimestamp),
		filtering.DeclareIdent("deleted_at", filtering.TypeTimestamp),
	)...),
}

// revisionFields are the currency revision fields accepted in filter (AIP-160) and order_by (AIP-132).
var revisionFields = listFields{
	sortable: []string{"revision_number", "changed_at"},
	declarations: mustDeclarations(
		filtering.DeclareStandardFunctions(),
		filtering.DeclareIdent("revision_number", filtering.TypeInt),
		filtering.DeclareIdent("changed_by", filtering.TypeString),
		filtering.DeclareIdent("changed_at", filtering.TypeTimestamp),
	),
}

func mustDeclarations(opts ...filtering.DeclarationOption) *filtering.Declarations {
	declarations, err := filtering.NewDeclarations(opts...)
	if err != nil {
		panic(fmt.Sprintf("declare list filter: %v", err))
	}

	return declarations
}

// pageToken is an opaque offset token (AIP-158). The checksum binds it to the request it was issued for,
// so that a token cannot be reused with another filter, ordering or visibility of deleted resources.
type pageToken struct {
	Offset   int64  `json:"o"`
	Checksum uint32 `json:"c"`
}

func (t pageToken) String() string {
	data, _ := json.Marshal(t) //nolint:errchkjson // the struct always marshals
	return base64.RawURLEncoding.EncodeToString(data)
}

func parsePageToken(s string, checksum uint32) (pageToken, error) {
	if s == "" {
		return pageToken{Checksum: checksum}, nil
	}

	data, err := base64.RawURLEncoding.DecodeString(s)
	if err != nil {
		return pageToken{}, errors.New("malformed token")
	}

	var token pageToken
	if err := json.Unmarshal(data, &token); err != nil || token.Offset < 0 {
		return pageToken{}, errors.New("malformed token")
	}

	if token.Checksum != checksum {
		return pageToken{}, errors.New("token does not match the request parameters")
	}

	return token, nil
}

// requestChecksum binds a page token to the request parameters other than the page size and token.
func requestChecksum(parts ...string) uint32 {
	h := crc32.NewIEEE()
	for _, part := range parts {
		_, _ = h.Write([]byte(part))
		_, _ = h.Write([]byte{0})
	}

	return h.Sum32()
}

// listFields declare the fields a list can be filtered and sorted by.
type listFields struct {
	declarations *filtering.Declarations
	sortable     []string
}

// listParams are the validated parameters common to all lists, token is the current page token.
type listParams struct {
	filter  filtering.Filter
	orderBy ordering.OrderBy
	limit   int32
	token   pageToken
}

// parseListParams validates the common parameters of a list request against the fields of the list.
func parseListParams(fields listFields, pageSize int32, filter, orderBy, token string, checksum uint32) (*listParams, error) {
	switch {
	case pageSize < 0:
		return nil, &domains.InvalidArgumentError{Argument: "pageSize", Err: errors.New("must not be negative")}
	case pageSize == 0:
		pageSize = defaultPageSize
	case pageSize > maxPageSize:
		pageSize = maxPageSize
	}

	parsedFilter, err := filtering.ParseFilterString(filter, fields.declarations)
	if err != nil {
		return nil, &domains.InvalidArgumentError{Argument: "filter", Err: compactFilterError(err)}
	}

	var parsedOrderBy ordering.OrderBy
	if err := parsedOrderBy.UnmarshalString(orderBy); err != nil {
		return nil, &domains.InvalidArgumentError{Argument: "order_by", Err: err}
	}
	if err := parsedOrderBy.ValidateForPaths(fields.sortable...); err != nil {
		return nil, &domains.InvalidArgumentError{Argument: "order_by", Err: err}
	}

	parsedToken, err := parsePageToken(token, checksum)
	if err != nil {
		return nil, &domains.InvalidArgumentError{Argument: "pageToken", Err: err}
	}

	return &listParams{
		filter:  parsedFilter,
		orderBy: parsedOrderBy,
		limit:   pageSize,
		token:   parsedToken,
	}, nil
}

// listQuery validates the client request and turns it into a query, the returned page token is the current one.
func listQuery(r *currencydmn.ListRequest) (*currencydmn.ListQuery, pageToken, error) {
	checksum := requestChecksum(r.Filter, r.OrderBy, strconv.FormatBool(r.AllowDeleted))

	params, err := parseListParams(currencyFields, r.PageSize, r.Filter, r.OrderBy, r.PageToken, checksum)
	if err != nil {
		return nil, pageToken{}, err
	}

	return &currencydmn.ListQuery{
		Filter:       params.filter,
		OrderBy:      params.orderBy,
		AllowDeleted: r.AllowDeleted,
		Offset:       params.token.Offset,
		Limit:        params.limit,
	}, params.token, nil
}

// revisionListQuery validates the client request and turns it into a query, the returned page token is the current one.
func revisionListQuery(r *currencydmn.RevisionListRequest) (*currencydmn.RevisionListQuery, pageToken, error) {
	checksum := requestChecksum(
		strconv.FormatInt(r.CurrencyID, 10), r.Filter, r.OrderBy, strconv.FormatBool(r.AllowDeleted),
	)

	params, err := parseListParams(revisionFields, r.PageSize, r.Filter, r.OrderBy, r.PageToken, checksum)
	if err != nil {
		return nil, pageToken{}, err
	}

	return &currencydmn.RevisionListQuery{
		CurrencyID: r.CurrencyID,
		Filter:     params.filter,
		OrderBy:    params.orderBy,
		Offset:     params.token.Offset,
		Limit:      params.limit,
	}, params.token, nil
}

// cutPage drops the extra item that is requested beyond the page size to find out whether there is a next page.
// The returned next page token is empty on the last page.
func cutPage[T any](items []T, pageSize int32, token pageToken) ([]T, string) {
	if len(items) <= int(pageSize) {
		return items, ""
	}

	return items[:pageSize], pageToken{Offset: token.Offset + int64(pageSize), Checksum: token.Checksum}.String()
}

// positionedError is implemented by the syntax errors of the filtering library.
type positionedError interface {
	Position() filtering.Position
	Message() string
}

// compactFilterError keeps only the innermost syntax error, the library reports the whole chain of
// grammar rules being parsed, which makes a multiline message that is useless for a client.
func compactFilterError(err error) error {
	var (
		innermost positionedError
		cause     error
	)

	for e := err; e != nil; e = errors.Unwrap(e) {
		if p, ok := e.(positionedError); ok {
			innermost = p
			continue
		}

		if innermost != nil {
			cause = e
			break
		}
	}

	if innermost == nil {
		return err
	}

	message := innermost.Message()
	if errors.Is(cause, io.EOF) {
		message = "unexpected end of filter"
	}

	return fmt.Errorf("syntax error at %s: %s", innermost.Position(), message)
}
