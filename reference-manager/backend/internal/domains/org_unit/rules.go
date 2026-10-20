package orgunitdmn

import (
	"context"
	"fmt"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
)

// ancestorsQuery walks up from a unit to the top of the hierarchy and reports whether a unit is on the way.
const ancestorsQuery = `
WITH RECURSIVE ancestors AS (
    SELECT id, parent_id FROM org_units WHERE id = $1
    UNION ALL
    SELECT u.id, u.parent_id FROM org_units u JOIN ancestors a ON u.id = a.parent_id
)
SELECT EXISTS (SELECT 1 FROM ancestors WHERE id = $2)`

// validate checks the parent of the unit: it exists, is not deleted and does not make the hierarchy a cycle (FR-RM-50).
func validate(ctx context.Context, q postgres.Querier, next, _ *record.Record[Fields]) error {
	parent := next.Fields.ParentID
	if parent == nil {
		return nil
	}

	if next.ID != 0 && *parent == next.ID {
		return record.Violation("parent_id", "a unit cannot be its own parent")
	}

	if err := record.CheckReferences(ctx, q, record.Reference{Field: "parent_id", Table: "org_units", ID: parent}); err != nil {
		return err
	}

	// a new unit has no descendants yet, an existing one must not move under one of them
	if next.ID == 0 {
		return nil
	}

	var cycle bool
	if err := q.QueryRow(ctx, ancestorsQuery, *parent, next.ID).Scan(&cycle); err != nil {
		return fmt.Errorf("check org unit hierarchy: %w", err)
	}

	if cycle {
		return record.Violation("parent_id", "reference forms a cycle in the hierarchy")
	}

	return nil
}
