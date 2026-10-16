package domains

import "errors"

var (
	ErrAlreadyExists   = errors.New("already exists")
	ErrNotFound        = errors.New("error not found")
	ErrUnauthenticated = errors.New("unauthenticated")
)
