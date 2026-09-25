package telemetry

import (
	"fmt"
	"log/slog"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/telemetry/log"
	"go.opentelemetry.io/otel/sdk/resource"
	semconv "go.opentelemetry.io/otel/semconv/v1.43.0"
)

type Telemetry struct {
	log *slog.Logger
}

func NewTelemetry(cfg *Config) (*Telemetry, error) {
	res := resource.NewWithAttributes(semconv.SchemaURL,
		semconv.DeploymentEnvironmentNameKey.String(cfg.Resource.Environment),
		semconv.ServiceNameKey.String(cfg.Resource.ServiceName),
	)

	log, err := log.NewLogger(cfg.Log.Options(log.WithResource(res))...)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize logger: %w", err)
	}

	return &Telemetry{
		log: log,
	}, nil
}

func (t *Telemetry) Logger() *slog.Logger {
	return t.log
}
