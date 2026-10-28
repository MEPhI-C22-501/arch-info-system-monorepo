// Package record holds the catalog-independent model of a reference record: the lifecycle shared by every catalog,
// revisions, list queries and the descriptor that tells the generic layers how a catalog is stored and validated.
// A catalog contributes only its fields struct and a descriptor, the generated adapters wire them to the API.
package record

import (
	"context"
	"encoding/json"
	"regexp"
	"time"
	"uuid"

	"go.einride.tech/aip/filtering"
	"go.einride.tech/aip/ordering"
	expr "google.golang.org/genproto/googleapis/api/expr/v1alpha1"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/access"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
)

// Record is the state of a catalog record a client can set: the catalog fields and the soft-delete flag.
type Record[F any] struct {
	ID        int64
	IsDeleted bool
	Fields    F
}

// Expanded is a record together with the lifecycle derived from its revisions.
type Expanded[F any] struct {
	Record[F]
	Revision    int32
	LastChanger uuid.UUID
	CreatedAt   time.Time
	UpdatedAt   time.Time
	DeletedAt   time.Time
}

// Revision is one change of a record, the change is a JSON Patch (RFC 6902) against the previous snapshot.
type Revision struct {
	ID             int64
	RecordID       int64
	RevisionNumber int32
	Change         json.RawMessage
	ChangedBy      uuid.UUID
	ChangedAt      time.Time
}

// ListRequest is a client request for a page of records, its fields keep the raw client input.
type ListRequest struct {
	PageSize     int32
	PageToken    string
	Filter       string
	OrderBy      string
	AllowDeleted bool
}

// ListQuery is a validated request for records that repositories can execute.
type ListQuery struct {
	// Filter is an AIP-160 filter expression checked against the filterable fields, empty when absent.
	Filter filtering.Filter
	// OrderBy is an AIP-132 ordering validated against the sortable fields, empty when absent.
	OrderBy      ordering.OrderBy
	AllowDeleted bool
	Offset       int64
	// Limit is the maximum number of records, zero means no limit, the offset is ignored then.
	Limit int32
}

type ListPage[F any] struct {
	Records []*Expanded[F]
	// NextPageToken is empty on the last page.
	NextPageToken string
}

// RevisionListRequest is a client request for a page of revisions of a record, its fields keep the raw client input.
type RevisionListRequest struct {
	RecordID     int64
	PageSize     int32
	PageToken    string
	Filter       string
	OrderBy      string
	AllowDeleted bool
}

// RevisionListQuery is a validated request for revisions of a record that repositories can execute.
type RevisionListQuery struct {
	RecordID int64
	Filter   filtering.Filter
	OrderBy  ordering.OrderBy
	Offset   int64
	Limit    int32
}

type RevisionListPage struct {
	Revisions []*Revision
	// NextPageToken is empty on the last page.
	NextPageToken string
}

// UpdateRequest is a client request for a partial update, its fields keep the raw client input.
type UpdateRequest[F any] struct {
	ID     int64
	Fields F
	// UpdateMask is a comma-separated list of the fields to update, all updatable fields when empty or "*".
	UpdateMask string
}

// Rules are the checks of a client-provided value, they mirror the constraints of the OpenAPI schema.
type Rules struct {
	Required bool
	// Pattern is checked on strings, PatternText is the source shown to the client.
	Pattern     *regexp.Regexp
	PatternText string
	MinLen      int
	MaxLen      int
	Min         *float64
	Max         *float64
	Enum        []string
}

// Column describes one field of a catalog record as the storage, the filters and the API see it.
type Column[F any] struct {
	// Name is the field name in the API and the column name in the table and the view.
	Name string
	// Type is the filtering type of the field: filtering.TypeString, TypeInt, TypeFloat, TypeBool or TypeTimestamp.
	Type *expr.Type
	// SQL is the expression used in filters and orderings, the column name when empty.
	SQL string
	// Stored is false for values the view computes, they are read and filtered, never written.
	Stored bool
	// Updatable columns are accepted in the update mask.
	Updatable bool
	// Value returns the field value for insert and update arguments.
	Value func(f *F) any
	// Ptr returns the destination the column is scanned into.
	Ptr func(f *F) any
	// Rules validate the client input of stored columns.
	Rules Rules
}

// ExportColumn is one column of the .xlsx export of a catalog.
type ExportColumn[F any] struct {
	Title string
	Value func(x *Expanded[F]) any
}

// Validator checks the cross-field and reference rules of a record before it is written, prev is nil on creation.
// It runs inside the write transaction and may query the storage through q.
type Validator[F any] func(ctx context.Context, q postgres.Querier, next *Record[F], prev *Record[F]) error

// Descriptor tells the generic repositories, services and handlers how a catalog is stored, validated and exported.
type Descriptor[F any] struct {
	// Singular and Plural are the resource names used in messages, file names and revision fields: "country", "countries".
	Singular string
	Plural   string
	// Table, View and RevisionTable are the storage objects of the catalog, RevisionColumn is the record reference
	// in the revision table ("country_id").
	Table          string
	View           string
	RevisionTable  string
	RevisionColumn string
	// Group selects the access rules of the catalog (documents/070.role-matrix.md).
	Group   access.Group
	Columns []Column[F]
	Export  []ExportColumn[F]
	// Snapshot returns the JSON document the revision patches are computed against, its field names are stored
	// in revisions, so renaming them breaks existing history.
	Snapshot func(r *Record[F]) any
	// Validate is optional.
	Validate Validator[F]
}

// StoredColumns are the columns of the table in the order they are written.
func (d *Descriptor[F]) StoredColumns() []Column[F] {
	columns := make([]Column[F], 0, len(d.Columns))
	for _, c := range d.Columns {
		if c.Stored {
			columns = append(columns, c)
		}
	}

	return columns
}

// UpdatableFields are the field names accepted in the update mask.
func (d *Descriptor[F]) UpdatableFields() []string {
	fields := make([]string, 0, len(d.Columns))
	for _, c := range d.Columns {
		if c.Stored && c.Updatable {
			fields = append(fields, c.Name)
		}
	}

	return fields
}

// Column returns the column with the name.
func (d *Descriptor[F]) Column(name string) (Column[F], bool) {
	for _, c := range d.Columns {
		if c.Name == name {
			return c, true
		}
	}

	return Column[F]{}, false
}
