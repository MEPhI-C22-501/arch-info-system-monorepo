package record

import (
	"context"
	"errors"
	"fmt"
	"slices"
	"strconv"
	"strings"
	"time"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
)

// FieldError is a violation of one field, its message is safe to return to the client.
type FieldError struct {
	Field   string
	Message string
}

// ValidationError lists every field a client has to fix, it is reported as a whole (FR-RM-35).
type ValidationError struct {
	Fields []FieldError
}

func (e *ValidationError) Error() string {
	parts := make([]string, 0, len(e.Fields))
	for _, f := range e.Fields {
		parts = append(parts, f.Field+": "+f.Message)
	}

	return "invalid fields: " + strings.Join(parts, "; ")
}

func (e *ValidationError) Is(target error) bool {
	return target == domains.ErrInvalidArgument
}

// Add appends a violation.
func (e *ValidationError) Add(field, message string) {
	e.Fields = append(e.Fields, FieldError{Field: field, Message: message})
}

// Violation builds an error with a single violation.
func Violation(field, message string) *ValidationError {
	e := &ValidationError{}
	e.Add(field, message)

	return e
}

// OrNil returns the error only when it holds violations.
func (e *ValidationError) OrNil() error {
	if len(e.Fields) == 0 {
		return nil
	}

	return e
}

// ValidateFields checks the client input of every stored column against its rules.
func ValidateFields[F any](d *Descriptor[F], f *F) error {
	errs := &ValidationError{}
	for _, c := range d.StoredColumns() {
		if message := checkValue(c.Value(f), c.Rules); message != "" {
			errs.Add(c.Name, message)
		}
	}

	return errs.OrNil()
}

// checkValue returns the violation message of a value, empty when the value satisfies the rules.
func checkValue(value any, rules Rules) string {
	switch v := value.(type) {
	case string:
		return checkString(v, rules)
	case *string:
		if v == nil {
			return requiredMessage(rules)
		}

		return checkString(*v, rules)
	case time.Time:
		if v.IsZero() {
			return requiredMessage(rules)
		}
	case *time.Time:
		if v == nil {
			return requiredMessage(rules)
		}
	case int64:
		return checkNumber(float64(v), rules)
	case *int64:
		if v == nil {
			return requiredMessage(rules)
		}

		return checkNumber(float64(*v), rules)
	case int32:
		return checkNumber(float64(v), rules)
	case int16:
		return checkNumber(float64(v), rules)
	case float64:
		return checkNumber(v, rules)
	case *float64:
		if v == nil {
			return requiredMessage(rules)
		}

		return checkNumber(*v, rules)
	}

	return ""
}

func requiredMessage(rules Rules) string {
	if rules.Required {
		return "required"
	}

	return ""
}

func checkString(s string, rules Rules) string {
	if s == "" {
		return requiredMessage(rules)
	}

	length := len([]rune(s))
	switch {
	case rules.MinLen > 0 && length < rules.MinLen:
		return fmt.Sprintf("must be at least %d characters long", rules.MinLen)
	case rules.MaxLen > 0 && length > rules.MaxLen:
		return fmt.Sprintf("must be at most %d characters long", rules.MaxLen)
	case rules.Pattern != nil && !rules.Pattern.MatchString(s):
		return "must match " + rules.PatternText
	case len(rules.Enum) > 0 && !slices.Contains(rules.Enum, s):
		return "must be one of " + strings.Join(rules.Enum, ", ")
	}

	return ""
}

func checkNumber(v float64, rules Rules) string {
	switch {
	case rules.Min != nil && v < *rules.Min:
		return "must be at least " + strconv.FormatFloat(*rules.Min, 'f', -1, 64)
	case rules.Max != nil && v > *rules.Max:
		return "must be at most " + strconv.FormatFloat(*rules.Max, 'f', -1, 64)
	}

	return ""
}

// Reference is a reference from a record to a record of another catalog.
type Reference struct {
	// Field is the referencing field reported in violations.
	Field string
	// Table is the referenced table.
	Table string
	// ID is the referenced record, nil when the field is empty.
	ID *int64
}

// CheckReferences verifies that every referenced record exists and is not deleted, the violations are collected
// into one ValidationError.
func CheckReferences(ctx context.Context, q postgres.Querier, refs ...Reference) error {
	errs := &ValidationError{}
	for _, ref := range refs {
		if ref.ID == nil {
			continue
		}

		message, err := checkReference(ctx, q, ref)
		if err != nil {
			return err
		}

		if message != "" {
			errs.Add(ref.Field, message)
		}
	}

	return errs.OrNil()
}

func checkReference(ctx context.Context, q postgres.Querier, ref Reference) (string, error) {
	var deleted bool

	// the table name comes from the descriptor, never from the client
	err := q.QueryRow(ctx, "SELECT is_deleted FROM "+ref.Table+" WHERE id = $1", *ref.ID).Scan(&deleted)
	if err != nil {
		if errors.Is(err, pgxNoRows) {
			return fmt.Sprintf("%s %d does not exist", ref.Table, *ref.ID), nil
		}

		return "", fmt.Errorf("check reference to %s: %w", ref.Table, err)
	}

	if deleted {
		return fmt.Sprintf("%s %d is deleted", ref.Table, *ref.ID), nil
	}

	return "", nil
}
