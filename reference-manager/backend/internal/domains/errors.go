package domains

import (
	"errors"
	"fmt"
)

var (
	ErrAlreadyExists   = errors.New("already exists")
	ErrNotFound        = errors.New("error not found")
	ErrUnauthenticated = errors.New("unauthenticated")
	// ErrPermissionDenied means the caller is authenticated, but none of its roles grants the operation.
	ErrPermissionDenied = errors.New("permission denied")
	ErrInvalidArgument  = errors.New("invalid argument")
	// ErrConflict means the resource was changed concurrently, the client can retry the request.
	ErrConflict = errors.New("conflict")
	// ErrFailedPrecondition means the operation is not allowed in the current state of the resource.
	ErrFailedPrecondition = errors.New("failed precondition")
	// ErrRevisionNotFound means the resource exists, but has no revision with the requested number.
	ErrRevisionNotFound = fmt.Errorf("revision %w", ErrNotFound)
	// ErrUnavailable means a dependency of the operation (Keycloak) could not be reached, the operation stays
	// pending and the client repeats it later (FR-RM-55).
	ErrUnavailable = errors.New("dependency is unavailable")
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
