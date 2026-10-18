package config_test

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/config"
)

type testConfig struct {
	Auth struct {
		Issuer string        `yaml:"issuer" env-required:"true"`
		Leeway time.Duration `yaml:"leeway" env-default:"30s"`
	} `yaml:"auth"`
	Database struct {
		Host string `yaml:"host" env-required:"true"`
	} `yaml:"database"`
}

func writeFile(t *testing.T, dir, name, content string) {
	t.Helper()

	require.NoError(t, os.WriteFile(filepath.Join(dir, name), []byte(content), 0o600))
}

func TestReadFromDirChecksRequiredFieldsAfterAllFiles(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	// the files are read in lexical order, the first one lacks the required field of the second one
	writeFile(t, dir, "auth.yaml", "auth:\n  issuer: http://keycloak/realms/test\n")
	writeFile(t, dir, "databases.yaml", "database:\n  host: postgres\n")
	writeFile(t, dir, ".hidden.yaml", "not: [valid")

	cfg, err := config.ReadFromDir[testConfig](dir)
	require.NoError(t, err)

	assert.Equal(t, "http://keycloak/realms/test", cfg.Auth.Issuer)
	assert.Equal(t, 30*time.Second, cfg.Auth.Leeway)
	assert.Equal(t, "postgres", cfg.Database.Host)
}

func TestReadFromDirFailsWithoutRequiredField(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	writeFile(t, dir, "databases.yaml", "database:\n  host: postgres\n")

	_, err := config.ReadFromDir[testConfig](dir)
	require.Error(t, err)
}
