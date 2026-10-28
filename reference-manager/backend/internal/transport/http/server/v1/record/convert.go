package recordhndl

import (
	"time"

	openapi_types "github.com/oapi-codegen/runtime/types"
)

// EnumPtr turns an optional enum value of the generated API into the string the domain stores.
func EnumPtr[E ~string](p *E) *string {
	if p == nil {
		return nil
	}

	s := string(*p)

	return &s
}

// EnumPtrTo turns an optional stored string into the enum type of the generated API.
func EnumPtrTo[E ~string](p *string) *E {
	if p == nil {
		return nil
	}

	e := E(*p)

	return &e
}

// DatePtr turns an optional date of the generated API into the time the domain stores.
func DatePtr(d *openapi_types.Date) *time.Time {
	if d == nil {
		return nil
	}

	t := d.Time

	return &t
}

// DatePtrTo turns an optional stored date into the date type of the generated API.
func DatePtrTo(t *time.Time) *openapi_types.Date {
	if t == nil {
		return nil
	}

	return &openapi_types.Date{Time: *t}
}
