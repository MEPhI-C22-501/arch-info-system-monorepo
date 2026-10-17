package telemetry

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"slices"

	"github.com/google/uuid"
	"go.opentelemetry.io/contrib/bridges/otelslog"
	"go.opentelemetry.io/contrib/instrumentation/runtime"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	sdklog "go.opentelemetry.io/otel/sdk/log"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.43.0"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/telemetry/log"
)

type Telemetry struct {
	log       *slog.Logger
	shutdowns []func(context.Context) error
}

// NewTelemetry configures the global OpenTelemetry providers and the logger of the application.
// Exporters connect lazily, so an unavailable collector neither blocks the startup nor fails requests:
// export errors are written to stdout and the data is dropped.
func NewTelemetry(cfg *Config) (*Telemetry, error) {
	service := newServiceResource(&cfg.Resource)

	res, err := resource.Merge(resource.Default(), service)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize telemetry resource: %w", err)
	}

	// export errors are logged to stdout only, otherwise a failing log export would feed itself
	stdoutLog, err := log.NewLogger(cfg.Log.Options(log.WithResource(service))...)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize logger: %w", err)
	}

	otel.SetErrorHandler(otel.ErrorHandlerFunc(func(err error) {
		stdoutLog.Warn("telemetry export failed", slog.String("error", err.Error()))
	}))
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	if !cfg.Exporter.Enabled {
		return &Telemetry{log: stdoutLog}, nil
	}

	t := &Telemetry{}
	if err := t.setupProviders(cfg, res); err != nil {
		return nil, errors.Join(err, t.Shutdown(context.Background()))
	}

	logger, err := log.NewLogger(cfg.Log.Options(
		log.WithResource(service),
		log.WithHandlers(otelslog.NewHandler(cfg.Resource.ServiceName)),
	)...)
	if err != nil {
		return nil, errors.Join(fmt.Errorf("failed to initialize logger: %w", err), t.Shutdown(context.Background()))
	}

	t.log = logger
	return t, nil
}

func (t *Telemetry) setupProviders(cfg *Config, res *resource.Resource) error {
	ctx := context.Background()

	traceExporter, err := otlptracegrpc.New(ctx, traceExporterOptions(&cfg.Exporter)...)
	if err != nil {
		return fmt.Errorf("failed to initialize trace exporter: %w", err)
	}

	tracerProvider := sdktrace.NewTracerProvider(
		sdktrace.WithResource(res),
		sdktrace.WithBatcher(traceExporter),
		sdktrace.WithSampler(sdktrace.ParentBased(sdktrace.TraceIDRatioBased(cfg.Traces.SamplingRatio))),
	)
	t.shutdowns = append(t.shutdowns, tracerProvider.Shutdown)
	otel.SetTracerProvider(tracerProvider)

	metricExporter, err := otlpmetricgrpc.New(ctx, metricExporterOptions(&cfg.Exporter)...)
	if err != nil {
		return fmt.Errorf("failed to initialize metric exporter: %w", err)
	}

	meterProvider := sdkmetric.NewMeterProvider(
		sdkmetric.WithResource(res),
		sdkmetric.WithReader(sdkmetric.NewPeriodicReader(metricExporter,
			sdkmetric.WithInterval(cfg.Metrics.ExportInterval),
		)),
	)
	t.shutdowns = append(t.shutdowns, meterProvider.Shutdown)
	otel.SetMeterProvider(meterProvider)

	if err := runtime.Start(runtime.WithMeterProvider(meterProvider)); err != nil {
		return fmt.Errorf("failed to start runtime metrics: %w", err)
	}

	logExporter, err := otlploggrpc.New(ctx, logExporterOptions(&cfg.Exporter)...)
	if err != nil {
		return fmt.Errorf("failed to initialize log exporter: %w", err)
	}

	loggerProvider := sdklog.NewLoggerProvider(
		sdklog.WithResource(res),
		sdklog.WithProcessor(sdklog.NewBatchProcessor(logExporter)),
	)
	t.shutdowns = append(t.shutdowns, loggerProvider.Shutdown)
	otel.SetLoggerProvider(loggerProvider)

	return nil
}

// newServiceResource describes the service instance, the stdout logs carry the same attributes as the exported telemetry.
func newServiceResource(cfg *ResourceConfig) *resource.Resource {
	return resource.NewWithAttributes(semconv.SchemaURL,
		semconv.ServiceNameKey.String(cfg.ServiceName),
		semconv.ServiceVersionKey.String(cfg.ServiceVersion),
		semconv.ServiceInstanceIDKey.String(uuid.NewString()),
		semconv.DeploymentEnvironmentNameKey.String(cfg.Environment),
	)
}

func traceExporterOptions(cfg *ExporterConfig) []otlptracegrpc.Option {
	opts := []otlptracegrpc.Option{
		otlptracegrpc.WithEndpoint(cfg.Endpoint),
		otlptracegrpc.WithTimeout(cfg.Timeout),
	}
	if cfg.Insecure {
		opts = append(opts, otlptracegrpc.WithInsecure())
	}

	return opts
}

func metricExporterOptions(cfg *ExporterConfig) []otlpmetricgrpc.Option {
	opts := []otlpmetricgrpc.Option{
		otlpmetricgrpc.WithEndpoint(cfg.Endpoint),
		otlpmetricgrpc.WithTimeout(cfg.Timeout),
	}
	if cfg.Insecure {
		opts = append(opts, otlpmetricgrpc.WithInsecure())
	}

	return opts
}

func logExporterOptions(cfg *ExporterConfig) []otlploggrpc.Option {
	opts := []otlploggrpc.Option{
		otlploggrpc.WithEndpoint(cfg.Endpoint),
		otlploggrpc.WithTimeout(cfg.Timeout),
	}
	if cfg.Insecure {
		opts = append(opts, otlploggrpc.WithInsecure())
	}

	return opts
}

func (t *Telemetry) Logger() *slog.Logger {
	return t.log
}

// Shutdown flushes the buffered telemetry and stops the providers, it is called after the rest of the application stopped.
func (t *Telemetry) Shutdown(ctx context.Context) error {
	var errs []error
	for _, shutdown := range slices.Backward(t.shutdowns) {
		if err := shutdown(ctx); err != nil {
			errs = append(errs, err)
		}
	}

	t.shutdowns = nil
	return errors.Join(errs...)
}
