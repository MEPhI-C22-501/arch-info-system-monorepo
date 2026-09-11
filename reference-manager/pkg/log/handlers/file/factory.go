package file

import (
	"fmt"
	"log/slog"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log/config"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log/handler"
)

const Type = "file"

type Factory struct{}

func NewFactory() *Factory {
	return &Factory{}
}

func (f *Factory) Type() string {
	return Type
}

func (f *Factory) Create(rawConfig any, options handler.Options) (slog.Handler, error) {
	cfg, ok := rawConfig.(*config.FileConfig)
	if !ok || cfg == nil {
		return nil, fmt.Errorf("%s handler: invalid config type %T", Type, rawConfig)
	}

	writer, err := newWriter(*cfg, options.Name)
	if err != nil {
		return nil, fmt.Errorf("%s handler: create writer: %w", Type, err)
	}

	return handler.NewWriter(writer, options)
}
