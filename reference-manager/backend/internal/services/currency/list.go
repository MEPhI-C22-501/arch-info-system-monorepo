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

// sortableFields are the fields accepted in order_by (AIP-132).
var sortableFields = []string{
	"code", "number", "name", "decimals", "is_deleted",
	"revision", "created_at", "updated_at", "deleted_at",
}

// filterDeclarations declare the fields and functions accepted in filter (AIP-160).
var filterDeclarations = mustDeclarations(append(
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
)...)

func mustDeclarations(opts ...filtering.DeclarationOption) *filtering.Declarations {
	declarations, err := filtering.NewDeclarations(opts...)
	if err != nil {
		panic(fmt.Sprintf("declare currency filter: %v", err))
	}

	return declarations
}

// pageToken is an opaque offset token (AIP-158). The checksum binds it to the request it was issued for,
// so that a token cannot be reused with another filter, ordering or visibility of deleted currencies.
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

func requestChecksum(r *currencydmn.ListRequest) uint32 {
	h := crc32.NewIEEE()
	for _, part := range []string{r.Filter, r.OrderBy, strconv.FormatBool(r.AllowDeleted)} {
		_, _ = h.Write([]byte(part))
		_, _ = h.Write([]byte{0})
	}

	return h.Sum32()
}

// listQuery validates the client request and turns it into a query, the returned page token is the current one.
func listQuery(r *currencydmn.ListRequest) (*currencydmn.ListQuery, pageToken, error) {
	pageSize := r.PageSize
	switch {
	case pageSize < 0:
		return nil, pageToken{}, &domains.InvalidArgumentError{Argument: "pageSize", Err: errors.New("must not be negative")}
	case pageSize == 0:
		pageSize = defaultPageSize
	case pageSize > maxPageSize:
		pageSize = maxPageSize
	}

	filter, err := filtering.ParseFilterString(r.Filter, filterDeclarations)
	if err != nil {
		return nil, pageToken{}, &domains.InvalidArgumentError{Argument: "filter", Err: compactFilterError(err)}
	}

	var orderBy ordering.OrderBy
	if err := orderBy.UnmarshalString(r.OrderBy); err != nil {
		return nil, pageToken{}, &domains.InvalidArgumentError{Argument: "order_by", Err: err}
	}
	if err := orderBy.ValidateForPaths(sortableFields...); err != nil {
		return nil, pageToken{}, &domains.InvalidArgumentError{Argument: "order_by", Err: err}
	}

	token, err := parsePageToken(r.PageToken, requestChecksum(r))
	if err != nil {
		return nil, pageToken{}, &domains.InvalidArgumentError{Argument: "pageToken", Err: err}
	}

	return &currencydmn.ListQuery{
		Filter:       filter,
		OrderBy:      orderBy,
		AllowDeleted: r.AllowDeleted,
		Offset:       token.Offset,
		Limit:        pageSize,
	}, token, nil
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
