package currencysrv

import (
	"fmt"
	"slices"
	"strings"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
)

// allFieldsMask selects all updatable fields (AIP-134).
const allFieldsMask = "*"

// updatableFields are the fields accepted in updateMask, is_deleted is changed only by deletion.
var updatableFields = []string{"code", "number", "name", "decimals"}

// parseUpdateMask returns the fields to update, all updatable fields when the mask is empty or "*".
func parseUpdateMask(mask string) ([]string, error) {
	mask = strings.TrimSpace(mask)
	if mask == "" || mask == allFieldsMask {
		return updatableFields, nil
	}

	paths := strings.Split(mask, ",")
	fields := make([]string, 0, len(paths))
	for _, path := range paths {
		path = strings.TrimSpace(path)
		if !slices.Contains(updatableFields, path) {
			return nil, &domains.InvalidArgumentError{
				Argument: "updateMask",
				Err:      fmt.Errorf("field %q cannot be updated, updatable fields: %s", path, strings.Join(updatableFields, ", ")),
			}
		}

		fields = append(fields, path)
	}

	return fields, nil
}

// applyUpdateMask copies the masked fields from src to dst.
func applyUpdateMask(dst, src *currencydmn.Currency, fields []string) {
	for _, field := range fields {
		switch field {
		case "code":
			dst.Code = src.Code
		case "number":
			dst.Number = src.Number
		case "name":
			dst.Name = src.Name
		case "decimals":
			dst.Decimals = src.Decimals
		}
	}
}
