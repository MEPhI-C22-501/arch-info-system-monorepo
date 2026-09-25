package log

import (
	"log/slog"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log/config"
)

func New(cfg config.Config) (*slog.Logger, error) {
	registry, err := NewRegistry(cfg)
	if err != nil {
		return nil, err
	}

	return NewBuilder(registry).Build(cfg)
}
