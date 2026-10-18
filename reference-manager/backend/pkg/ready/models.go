package ready

import (
	"context"
	"fmt"
)

type Check struct {
	name  string
	check func(ctx context.Context) error
}

func NewCheck(name string, fn func(ctx context.Context) error) *Check {
	return &Check{
		name:  name,
		check: fn,
	}
}

func (c *Check) Run(ctx context.Context) *Error {
	if err := c.check(ctx); err != nil {
		return &Error{CheckName: c.name, Reason: err}
	}

	return nil
}

type Error struct {
	CheckName string
	Reason    error
}

func (e *Error) Error() string {
	return fmt.Sprintf("readiness check attempt for %s failed: %v", e.CheckName, e.Reason)
}

func (e *Error) Unwrap() error {
	return e.Reason
}
