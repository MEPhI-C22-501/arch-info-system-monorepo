package log

import (
	"errors"
	"fmt"
	"log/slog"
	"sort"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log/config"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log/handler"
)

var ErrNoHandlers = errors.New("log: no handlers configured")

type Builder struct {
	registry *Registry
}

func NewBuilder(registry *Registry) *Builder {
	return &Builder{
		registry: registry,
	}
}

func (b *Builder) Build(cfg config.Config) (*slog.Logger, error) {
	if len(cfg.Handlers) == 0 {
		return nil, ErrNoHandlers
	}

	handlers := make([]slog.Handler, 0, len(cfg.Handlers))
	for _, cfg := range cfg.Handlers {
		h, err := b.buildHandler(cfg)
		if err != nil {
			return nil, fmt.Errorf("log: build handler %q: %w", cfg.Name, err)
		}
		handlers = append(handlers, h)
	}

	logger := slog.New(slog.NewMultiHandler(handlers...))
	logger = withMeta(logger, cfg.Meta)

	return logger, nil
}

func (b *Builder) buildHandler(cfg config.Handler) (slog.Handler, error) {
	if cfg.Name == "" {
		return nil, errors.New("log: handler name is empty")
	}

	if cfg.Type == "" {
		return nil, errors.New("log: handler type is empty")
	}

	factory, err := b.registry.Get(cfg.Type)
	if err != nil {
		return nil, err
	}

	specificConfig, err := cfg.Config()
	if err != nil {
		return nil, fmt.Errorf("resolve handler config: %w", err)
	}

	handlerOptions := handler.Options{
		Name:   cfg.Name,
		Level:  cfg.Level.Slog(),
		Format: cfg.Format,
	}

	h, err := factory.Create(specificConfig, handlerOptions)
	if err != nil {
		return nil, fmt.Errorf("create %q handler: %w", cfg.Type, err)
	}

	return h, nil
}

func withMeta(logger *slog.Logger, meta map[string]string) *slog.Logger {
	if len(meta) == 0 {
		return logger
	}

	keys := make([]string, 0, len(meta))
	for key := range meta {
		keys = append(keys, key)
	}

	sort.Strings(keys)

	attrs := make([]any, 0, len(keys)*2)
	for _, key := range keys {
		attrs = append(attrs, key, meta[key])
	}

	return logger.With(attrs...)
}
