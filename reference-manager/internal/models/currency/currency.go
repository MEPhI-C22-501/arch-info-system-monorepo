package currency

type Currency struct {
	ID         int64  `json:"id"`
	CodeAlpha  string `json:"code_alpha"`
	CodeNum    string `json:"code_num"`
	Name       string `json:"name"`
	MinorUnits int16  `json:"minor_units"`
	Symbol     string `json:"symbol"`
}
