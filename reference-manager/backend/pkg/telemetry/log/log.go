package log

import (
	"context"
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

	if len(options.handlers) == 0 {
		return slog.New(handler), nil
	}

	handlers := []slog.Handler{handler}
	for _, h := range options.handlers {
		handlers = append(handlers, &levelHandler{Handler: h, level: options.level})
	}

	return slog.New(slog.NewMultiHandler(handlers...)), nil
}

// levelHandler applies the configured level to the additional handlers, which do not filter records themselves.
type levelHandler struct {
	slog.Handler
	level slog.Leveler
}

func (h *levelHandler) Enabled(ctx context.Context, level slog.Level) bool {
	return level >= h.level.Level() && h.Handler.Enabled(ctx, level)
}

func (h *levelHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	return &levelHandler{Handler: h.Handler.WithAttrs(attrs), level: h.level}
}

func (h *levelHandler) WithGroup(name string) slog.Handler {
	return &levelHandler{Handler: h.Handler.WithGroup(name), level: h.level}
}
