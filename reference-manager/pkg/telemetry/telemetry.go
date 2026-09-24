package telemetry

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/telemetry/log"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/sdk/resource"
	"golang.org/x/sync/errgroup"
)

type Telemetry struct {
	service string
	logs    *log.Provider
}

func New(ctx context.Context, cfg *Config) (*Telemetry, error) {
	res, err := resource.New(ctx, resource.WithAttributes(
		attribute.String("service", cfg.ResourceDefinition.Service),
		attribute.String("environment", cfg.ResourceDefinition.Environment),
	))

	if err != nil {
		return nil, fmt.Errorf("failed to initialize resource: %w", err)
	}

	logs, err := log.NewProvider(ctx, cfg.OtelCollectorEndpoint, res)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize logs provider: %w", err)
	}

	return &Telemetry{
		service: cfg.ResourceDefinition.Service,
		logs:    logs,
	}, nil
}

func (t *Telemetry) Shutdown(ctx context.Context) error {
	g, gCtx := errgroup.WithContext(ctx)

	g.Go(func() error {
		return t.logs.Shutdown(gCtx)
	})

	return g.Wait()
}

func (t *Telemetry) LogHandler() slog.Handler {
	return t.logs.Handler(t.service)
}
