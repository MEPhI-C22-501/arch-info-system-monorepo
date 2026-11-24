package telemetry_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/config"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/telemetry"
)

// a stand that mounts the local telemetry.yaml points the service at its own collector through the environment
func TestExporterEndpointIsOverriddenByTheEnvironment(t *testing.T) {
	type appConfig struct {
		Telemetry telemetry.Config `yaml:"telemetry"`
	}

	dir := t.TempDir()
	file := "telemetry:\n  exporter:\n    enabled: true\n    endpoint: reference-manager-otel-collector:4317\n"
	require.NoError(t, os.WriteFile(filepath.Join(dir, "telemetry.yaml"), []byte(file), 0o600))

	cfg, err := config.ReadFromDir[appConfig](dir)
	require.NoError(t, err)
	assert.Equal(t, "reference-manager-otel-collector:4317", cfg.Telemetry.Exporter.Endpoint, "the file wins over the default")

	t.Setenv("TELEMETRY_EXPORTER_ENDPOINT", "otel-collector:4317")
	cfg, err = config.ReadFromDir[appConfig](dir)
	require.NoError(t, err)
	assert.Equal(t, "otel-collector:4317", cfg.Telemetry.Exporter.Endpoint, "the environment wins over the file")
}
