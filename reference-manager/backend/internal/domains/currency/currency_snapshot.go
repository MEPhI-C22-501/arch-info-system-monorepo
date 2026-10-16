package currencydmn

// CurrencySnapshot is the JSON representation of a currency that revision patches are computed against.
// Its JSON field names are stored in currency revisions, so renaming them breaks existing history.
type CurrencySnapshot struct {
	Code      string `json:"code"`
	Number    string `json:"number"`
	Name      string `json:"name"`
	Decimals  int8   `json:"decimals"`
	IsDeleted bool   `json:"is_deleted"`
}

func (c *Currency) Snapshot() *CurrencySnapshot {
	return &CurrencySnapshot{
		Code:      c.Code,
		Number:    c.Number,
		Name:      c.Name,
		Decimals:  c.Decimals,
		IsDeleted: c.IsDeleted,
	}
}
