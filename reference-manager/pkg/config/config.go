package config

import (
	"fmt"
	"io/fs"
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

func ReadFromDir[Config any](dirPath string) (*Config, error) {
	var cfg Config

	err := filepath.WalkDir(dirPath, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}

		if d.IsDir() || strings.HasPrefix(d.Name(), ".") {
			return nil
		}

		return cleanenv.ReadConfig(path, &cfg)
	})

	if err != nil {
		return nil, fmt.Errorf("failed to read configuration files: %w", err)
	}

	return &cfg, nil
}

func ReadFromEnv[Config any]() (*Config, error) {
	var cfg Config
	if err := cleanenv.ReadEnv(cfg); err != nil {
		return nil, fmt.Errorf("failed to read configuration from environment: %w", err)
	}

	return &cfg, nil
}
