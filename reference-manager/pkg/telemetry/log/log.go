package log

import (
	"fmt"
	"log/slog"
	"os"
)

func NewLogger(opts ...Option) (*slog.Logger, error) {
	options := defaultOptions()
	for _, opt := range opts {
		if err := opt(options); err != nil {
			return nil, fmt.Errorf("failed to initialize logger options: %w", err)
		}
	}

	handlerOptions := &slog.HandlerOptions{Level: options.level}
	handler := options.format.Handler(os.Stdout, handlerOptions).WithAttrs(options.attrs)

	return slog.New(handler), nil
}
