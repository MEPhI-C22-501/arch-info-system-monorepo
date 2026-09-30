package currency

import (
	"time"
	"uuid"
)

type Currency struct {
	Name        string
	UID         uuid.UUID
	Code        string
	NumericCode string
	DisplayName string
	MinorUnits  int32
	CreateTime  time.Time
	UpdateTime  time.Time
}
