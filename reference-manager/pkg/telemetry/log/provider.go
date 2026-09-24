package log

import (
	"context"
	"fmt"
	"log/slog"

	"go.opentelemetry.io/contrib/bridges/otelslog"
	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc"
	"go.opentelemetry.io/otel/sdk/log"
	"go.opentelemetry.io/otel/sdk/resource"
)

type Provider struct {
	provider *log.LoggerProvider
}

func NewProvider(ctx context.Context, endpoint string, res *resource.Resource) (*Provider, error) {
	exporter, err := otlploggrpc.New(ctx,
		otlploggrpc.WithEndpoint(endpoint),
		otlploggrpc.WithInsecure(),
	)

	if err != nil {
		return nil, fmt.Errorf("failed to initialize exporter: %w", err)
	}

	processor := log.NewBatchProcessor(exporter)

	provider := log.NewLoggerProvider(
		log.WithResource(res),
		log.WithProcessor(processor),
	)

	return &Provider{
		provider: provider,
	}, nil
}

func (p *Provider) Shutdown(ctx context.Context) error {
	return p.provider.Shutdown(ctx)
}

func (p *Provider) Handler(name string) slog.Handler {
	return otelslog.NewHandler(name,
		otelslog.WithLoggerProvider(p.provider),
	)
}
