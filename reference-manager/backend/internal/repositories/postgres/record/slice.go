package recordrepo

import (
	"strings"

	"go.einride.tech/aip/filtering"
	expr "google.golang.org/genproto/googleapis/api/expr/v1alpha1"
)

// SliceColumn is a column of an expanded view as the slice of the records at a moment rebuilds it.
type SliceColumn struct {
	Name string
	// Stored columns are rebuilt from the revisions, the computed ones of the view are NULL of Type in a slice.
	Stored bool
	Type   *expr.Type
}

// SliceSource returns a select of the records of a catalog as they were at the moment given by the placeholder,
// with the columns of its expanded view: id, the columns in their order, then the lifecycle (FR-RM-61).
//
// A revision holds a flat JSON Patch against the previous snapshot of the record, one "add" or "replace" per field,
// so the value of a field at the moment is the value of its last operation before the moment; the typed columns are
// read from that document by jsonb_populate_record on the row type of the table. The lifecycle is computed from the
// same revisions the way the view computes it. A record created after the moment has no revisions before it and is
// absent, a purged record has lost its revisions and is absent as well.
func SliceSource(table, revisionTable, revisionColumn string, columns []SliceColumn, moment string) string {
	selected := make([]string, 0, len(columns)+7)
	selected = append(selected, "s.record_id AS id")
	for _, c := range columns {
		if c.Stored {
			selected = append(selected, "p."+c.Name)
			continue
		}
		selected = append(selected, "NULL::"+sqlType(c.Type)+" AS "+c.Name)
	}
	selected = append(selected,
		"COALESCE((s.state ->> 'is_deleted')::boolean, FALSE) AS is_deleted",
		"l.revision", "l.last_changer", "l.created_at", "l.updated_at", "l.deleted_at")

	return "WITH revs AS (\n" +
		"    SELECT r." + revisionColumn + " AS record_id, r.revision_number, r.change, r.changed_by, r.changed_at\n" +
		"    FROM " + revisionTable + " r\n" +
		"    WHERE r.changed_at <= " + moment + "\n" +
		"), fields AS (\n" +
		"    SELECT DISTINCT ON (revs.record_id, op.value ->> 'path')\n" +
		"        revs.record_id, substr(op.value ->> 'path', 2) AS name, op.value ->> 'op' AS kind, op.value -> 'value' AS value\n" +
		"    FROM revs CROSS JOIN LATERAL jsonb_array_elements(revs.change) AS op(value)\n" +
		"    ORDER BY revs.record_id, op.value ->> 'path', revs.revision_number DESC\n" +
		"), states AS (\n" +
		"    SELECT record_id, jsonb_object_agg(name, CASE WHEN kind = 'remove' THEN 'null'::jsonb ELSE value END) AS state\n" +
		"    FROM fields\n" +
		"    GROUP BY record_id\n" +
		"), lifecycle AS (\n" +
		"    SELECT record_id,\n" +
		"        MAX(revision_number) AS revision,\n" +
		"        MAX(changed_at) AS updated_at,\n" +
		"        (ARRAY_AGG(changed_by ORDER BY revision_number DESC))[1] AS last_changer,\n" +
		"        MIN(changed_at) FILTER (WHERE revision_number = 1) AS created_at,\n" +
		"        MAX(changed_at) FILTER (WHERE change @> '[{\"path\": \"/is_deleted\", \"value\": true}]'::jsonb) AS deleted_at\n" +
		"    FROM revs\n" +
		"    GROUP BY record_id\n" +
		")\n" +
		"SELECT " + strings.Join(selected, ", ") + "\n" +
		"FROM states s\n" +
		"JOIN lifecycle l ON l.record_id = s.record_id\n" +
		"CROSS JOIN LATERAL jsonb_populate_record(NULL::" + table + ", s.state) AS p"
}

// sqlType is the column type of a computed column by its filtering type.
func sqlType(t *expr.Type) string {
	switch t {
	case filtering.TypeInt:
		return "bigint"
	case filtering.TypeFloat:
		return "numeric"
	case filtering.TypeBool:
		return "boolean"
	case filtering.TypeTimestamp:
		return "timestamptz"
	default:
		return "text"
	}
}
