package domains

import (
	"errors"
	"fmt"
)

var (
	ErrAlreadyExists   = errors.New("already exists")
	ErrNotFound        = errors.New("error not found")
	ErrUnauthenticated = errors.New("unauthenticated")
	ErrInvalidArgument = errors.New("invalid argument")
	// ErrConflict means the resource was changed concurrently, the client can retry the request.
	ErrConflict = errors.New("conflict")
	// ErrRevisionNotFound means the resource exists, but has no revision with the requested number.
	ErrRevisionNotFound = fmt.Errorf("revision %w", ErrNotFound)
)

// InvalidArgumentError describes a request argument the client has to fix, its message is safe to return to the client.
type InvalidArgumentError struct {
	Argument string
	Err      error
}

func (e *InvalidArgumentError) Error() string {
	return fmt.Sprintf("invalid %s: %v", e.Argument, e.Err)
}

func (e *InvalidArgumentError) Is(target error) bool {
	return target == ErrInvalidArgument
}

func (e *InvalidArgumentError) Unwrap() error {
	return e.Err
}
