package telemetry

type Config struct {
	OtelCollectorEndpoint string             `yaml:"otel_collector_endpoint"`
	ResourceDefinition    ResourceDefinition `yaml:"resource_definition"`
}

type ResourceDefinition struct {
	Service     string `yaml:"service_name"`
	Environment string `yaml:"environment"`
}
