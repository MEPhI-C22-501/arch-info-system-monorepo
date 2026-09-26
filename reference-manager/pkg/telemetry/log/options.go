package log

import (
	"fmt"
	"log/slog"

	"go.opentelemetry.io/otel/sdk/resource"
)

var (
	DefaultFormat = TextFormat
	DefaultLevel  = slog.LevelDebug
)

type options struct {
	format Format
	level  slog.Level
	attrs  []slog.Attr
}

func defaultOptions() *options {
	return &options{
		format: DefaultFormat,
		level:  DefaultLevel,
		attrs:  make([]slog.Attr, 0),
	}
}

type Option func(*options) error

func WithFormat(v string) Option {
	return func(o *options) error {
		parsed, err := NewFormat(v)
		if err != nil {
			return fmt.Errorf("failed to cast %s to any known log format: %w", v, err)
		}

		o.format = parsed
		return nil
	}
}

func WithLevel(v string) Option {
	return func(o *options) error {
		var level slog.Level
		if err := level.UnmarshalText([]byte(v)); err != nil {
			return fmt.Errorf("failed to unmarshal log level: %w", err)
		}

		o.level = level
		return nil
	}
}

func WithResource(res *resource.Resource) Option {
	return func(o *options) error {
		var attrs []slog.Attr
		for _, kv := range res.Attributes() {
			attrs = append(attrs, slog.Any(string(kv.Key), kv.Value))
		}

		o.attrs = attrs
		return nil
	}
}
