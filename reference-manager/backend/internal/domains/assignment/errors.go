package assignmentdmn

import (
	"errors"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
)

func asValidation(err error, target **record.ValidationError) bool {
	return errors.As(err, target)
}
