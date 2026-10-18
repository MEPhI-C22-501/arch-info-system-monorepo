package currencydmn

// UpdateRequest is a client request for a partial currency update, its fields keep the raw client input.
type UpdateRequest struct {
	CurrencyID int64
	Currency   *Currency
	// UpdateMask is a comma-separated list of the fields to update, all updatable fields when empty or "*".
	UpdateMask string
}
