package currency

import (
	"time"
	"uuid"
)

type ExpandedCurrency struct {
	ID          int64     `json:"id"`
	CodeAlpha   string    `json:"code_alpha"`
	CodeNum     string    `json:"code_num"`
	Name        string    `json:"name"`
	MinorUnits  int16     `json:"minor_units"`
	Symbol      string    `json:"symbol"`
	Revision    int32     `json:"revision"`
	LastChanger uuid.UUID `json:"last_changer"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}
