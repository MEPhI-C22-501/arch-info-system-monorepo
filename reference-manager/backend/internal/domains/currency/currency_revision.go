package currencydmn

import (
	"encoding/json"
	"time"
	"uuid"
)

type CurrencyRevision struct {
	ID             int64
	CurrencyID     int64
	RevisionNumber int32
	Change         json.RawMessage
	ChangedBy      uuid.UUID
	ChangedAt      time.Time
}
