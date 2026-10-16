package config

import (
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"strings"

	"github.com/ilyakaznacheev/cleanenv"
)

func Read[Config any](dirPath string) (*Config, error) {
	if dirPath != "" {
		return ReadFromDir[Config](dirPath)
	}

	return ReadFromEnv[Config]()
}

// ReadFromDir reads every configuration file of the directory into one configuration.
// Environment variables, defaults and required fields are applied once all files are read,
// so a required field may be defined in any file.
func ReadFromDir[Config any](dirPath string) (*Config, error) {
	var cfg Config

	err := filepath.WalkDir(dirPath, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}

		if d.IsDir() || strings.HasPrefix(d.Name(), ".") {
			return nil
		}

		return parseFile(path, &cfg)
	})
	if err != nil {
		return nil, fmt.Errorf("failed to read configuration files: %w", err)
	}

	if err := cleanenv.ReadEnv(&cfg); err != nil {
		return nil, fmt.Errorf("failed to read configuration files: %w", err)
	}

	return &cfg, nil
}

func parseFile(path string, cfg any) error {
	var parse func(r io.Reader, cfg any) error

	switch ext := strings.ToLower(filepath.Ext(path)); ext {
	case ".yaml", ".yml":
		parse = cleanenv.ParseYAML
	case ".json":
		parse = cleanenv.ParseJSON
	default:
		return fmt.Errorf("file %s: unsupported configuration format %q", path, ext)
	}

	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()

	if err := parse(f, cfg); err != nil {
		return fmt.Errorf("file %s: %w", path, err)
	}

	return nil
}

func ReadFromEnv[Config any]() (*Config, error) {
	var cfg Config
	if err := cleanenv.ReadEnv(&cfg); err != nil {
		return nil, fmt.Errorf("failed to read configuration from environment: %w", err)
	}

	return &cfg, nil
}
