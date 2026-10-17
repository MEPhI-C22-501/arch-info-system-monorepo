package telemetry

import (
	"time"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/telemetry/log"
)

type Config struct {
	Resource ResourceConfig `yaml:"resource"`
	Exporter ExporterConfig `yaml:"exporter"`
	Traces   TracesConfig   `yaml:"traces"`
	Metrics  MetricsConfig  `yaml:"metrics"`
	Log      log.Config     `yaml:"log"`
}

type ResourceConfig struct {
	ServiceName    string `yaml:"service_name"`
	ServiceVersion string `yaml:"service_version" env-default:"0.0.0"`
	Environment    string `yaml:"environment"`
}

// ExporterConfig describes the OTLP gRPC connection to the OpenTelemetry Collector.
// When the exporter is disabled, traces and metrics are not collected and logs are written to stdout only.
type ExporterConfig struct {
	Enabled  bool          `yaml:"enabled" env-default:"false"`
	Endpoint string        `yaml:"endpoint" env-default:"localhost:4317"`
	Insecure bool          `yaml:"insecure" env-default:"false"`
	Timeout  time.Duration `yaml:"timeout" env-default:"10s"`
}

type TracesConfig struct {
	// SamplingRatio is the share of the root traces to sample, from 0 to 1, the parent decision is respected.
	SamplingRatio float64 `yaml:"sampling_ratio" env-default:"1"`
}

type MetricsConfig struct {
	ExportInterval time.Duration `yaml:"export_interval" env-default:"15s"`
}
