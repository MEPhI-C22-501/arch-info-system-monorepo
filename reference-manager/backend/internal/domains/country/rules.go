package countrydmn

import (
	"context"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
)

// validate checks that the main currency of the country exists and is not deleted.
func validate(ctx context.Context, q postgres.Querier, next, _ *record.Record[Fields]) error {
	return record.CheckReferences(ctx, q, record.Reference{Field: "currency_id", Table: "currencies", ID: next.Fields.CurrencyID})
}
