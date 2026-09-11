package log

import (
	"errors"
	"fmt"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log/config"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log/handler"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log/handlers/console"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log/handlers/file"
)

var (
	ErrNilFactory      = errors.New("log: nil handler factory")
	ErrFactoryExists   = errors.New("log: handler factory already registered")
	ErrFactoryNotFound = errors.New("log: handler factory not found")
)

type Registry struct {
	factories map[string]handler.Factory
}

func NewRegistry(cfg config.Config) (*Registry, error) {
	registry := &Registry{
		factories: make(map[string]handler.Factory),
	}

	for _, handlerConfig := range cfg.Handlers {
		if err := registry.registerByType(handlerConfig.Type); err != nil {
			return nil, fmt.Errorf(
				"register handler %q: %w",
				handlerConfig.Name,
				err,
			)
		}
	}

	return registry, nil
}

func (r *Registry) registerByType(handlerType string) error {
	if _, exists := r.factories[handlerType]; exists {
		return nil
	}

	switch handlerType {
	case file.Type:
		return r.Register(file.NewFactory())

	case console.Type:
		return r.Register(console.NewFactory())

	default:
		return fmt.Errorf("unsupported handler type %q", handlerType)
	}
}

func (r *Registry) Register(factory handler.Factory) error {
	if factory == nil {
		return ErrNilFactory
	}

	handlerType := factory.Type()
	if handlerType == "" {
		return errors.New("log: handler factory type is empty")
	}

	if _, exists := r.factories[handlerType]; exists {
		return fmt.Errorf("%w: %q", ErrFactoryExists, handlerType)
	}

	r.factories[handlerType] = factory

	return nil
}

func (r *Registry) Get(handlerType string) (handler.Factory, error) {
	factory, exists := r.factories[handlerType]
	if !exists {
		return nil, fmt.Errorf("%w: %q", ErrFactoryNotFound, handlerType)
	}

	return factory, nil
}
