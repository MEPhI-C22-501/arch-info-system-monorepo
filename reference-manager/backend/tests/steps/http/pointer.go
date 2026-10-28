package http

import (
	"fmt"
	"strconv"
	"strings"
)

// PointerWildcard is a JSON pointer token that selects every element of an array,
// e.g. "/currencies/*/code" selects the codes of all currencies as an array.
const PointerWildcard = "*"

// resolvePointer returns the value at a JSON pointer (RFC 6901) that may contain PointerWildcard tokens.
func resolvePointer(doc any, pointer string) (any, error) {
	if pointer == "" {
		return doc, nil
	}

	if !strings.HasPrefix(pointer, "/") {
		return nil, fmt.Errorf("JSON pointer %q must start with /", pointer)
	}

	return resolveTokens(doc, strings.Split(pointer[1:], "/"))
}

func resolveTokens(doc any, tokens []string) (any, error) {
	if len(tokens) == 0 {
		return doc, nil
	}

	token, rest := unescapePointerToken(tokens[0]), tokens[1:]

	switch v := doc.(type) {
	case map[string]any:
		value, ok := v[token]
		if !ok {
			return nil, fmt.Errorf("no field %q", token)
		}

		return resolveTokens(value, rest)
	case []any:
		if tokens[0] == PointerWildcard {
			values := make([]any, 0, len(v))
			for i, element := range v {
				value, err := resolveTokens(element, rest)
				if err != nil {
					return nil, fmt.Errorf("element %d: %w", i, err)
				}

				values = append(values, value)
			}

			return values, nil
		}

		i, err := strconv.Atoi(token)
		if err != nil || i < 0 || i >= len(v) {
			return nil, fmt.Errorf("no array element %q", token)
		}

		return resolveTokens(v[i], rest)
	default:
		return nil, fmt.Errorf("cannot select %q from a scalar value", token)
	}
}
