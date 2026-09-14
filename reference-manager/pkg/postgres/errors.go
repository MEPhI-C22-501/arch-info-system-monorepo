package postgres

import "errors"

var (
	ErrNotConnected   = errors.New("postgres client is not connected")
	ErrAlreadyStarted = errors.New("postgres client is already started")
)

type errorRow struct {
	err error
}

func (r errorRow) Scan(...any) error {
	return r.err
}
