package recordsrv

import (
	"fmt"
	"slices"
	"strings"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
)

// allFieldsMask selects all updatable fields (AIP-134).
const allFieldsMask = "*"

// parseUpdateMask returns the fields to update, all updatable fields when the mask is empty or "*".
func parseUpdateMask(mask string, updatable []string) ([]string, error) {
	mask = strings.TrimSpace(mask)
	if mask == "" || mask == allFieldsMask {
		return updatable, nil
	}

	paths := strings.Split(mask, ",")
	fields := make([]string, 0, len(paths))
	for _, path := range paths {
		path = strings.TrimSpace(path)
		if !slices.Contains(updatable, path) {
			return nil, &domains.InvalidArgumentError{
				Argument: "updateMask",
				Err:      fmt.Errorf("field %q cannot be updated, updatable fields: %s", path, strings.Join(updatable, ", ")),
			}
		}

		fields = append(fields, path)
	}

	return fields, nil
}
