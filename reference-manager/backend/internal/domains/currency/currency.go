package currencydmn

type Currency struct {
	ID        int64
	Code      string
	Number    string
	Name      string
	Decimals  int8
	IsDeleted bool
}
