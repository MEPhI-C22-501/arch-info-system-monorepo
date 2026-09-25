package log

import (
	"fmt"
	"io"
	"log/slog"
	"strings"
)

type Format string

const (
	TextFormat Format = "text"
	JsonFormat Format = "json"
)

func NewFormat(v string) (Format, error) {
	switch casted := Format(strings.ToLower(v)); casted {
	case TextFormat, JsonFormat:
		return casted, nil
	default:
		return "", fmt.Errorf("unsupported log format: %s", v)
	}
}

func (f Format) Handler(w io.Writer, opts *slog.HandlerOptions) slog.Handler {
	switch f {
	case TextFormat:
		return slog.NewTextHandler(w, opts)
	case JsonFormat:
		return slog.NewJSONHandler(w, opts)
	default:
		return nil
	}
}
