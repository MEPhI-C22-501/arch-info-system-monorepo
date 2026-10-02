package currency

import (
	"encoding/json"
	"time"
	"uuid"
)

type CurrencyRevision struct {
	ID         int64           `json:"id"`
	CurrencyID int64           `json:"currency_id"`
	Revision   int32           `json:"revision"`
	Change     json.RawMessage `json:"change"`
	ChangedBy  uuid.UUID       `json:"changed_by"`
	ChangedAt  time.Time       `json:"changed_at"`
}
