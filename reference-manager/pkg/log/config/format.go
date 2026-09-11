package config

import (
	"fmt"
	"strings"
)

type Format string

const (
	FormatJSON Format = "json"
	FormatText Format = "text"
)

func (f *Format) UnmarshalText(text []byte) error {
	value := Format(strings.ToLower(string(text)))

	switch value {
	case FormatJSON, FormatText:
		*f = value
		return nil

	default:
		return fmt.Errorf("unsupported log format %q", string(text))
	}
}
