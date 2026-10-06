package currencydmn

import (
	"time"
	"uuid"
)

type ExpandedCurrency struct {
	ID          int64
	Code        string
	Number      string
	Name        string
	Decimals    int8
	IsDeleted   bool
	Revision    int32
	LastChanger uuid.UUID
	CreatedAt   time.Time
	UpdatedAt   time.Time
	DeletedAt   time.Time
}
