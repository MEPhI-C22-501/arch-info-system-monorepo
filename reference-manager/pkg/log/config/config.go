package config

import (
	"fmt"
	"time"
)

type Config struct {
	Meta     map[string]string `yaml:"meta"`
	Handlers []Handler         `yaml:"handlers"`
}

type Handler struct {
	Name   string `yaml:"name"`
	Type   string `yaml:"type"`
	Level  Level  `yaml:"level"`
	Format Format `yaml:"format"`

	File *FileConfig `yaml:"file,omitempty"`
}

func (h Handler) Config() (any, error) {
	switch h.Type {
	case "file":
		if h.File == nil {
			return nil, fmt.Errorf("file handler configuration is missing")
		}

		return h.File, nil

	case "console":
		return nil, nil

	default:
		return nil, fmt.Errorf("unknown handler type %q", h.Type)
	}
}

type FileConfig struct {
	Location string         `yaml:"location"`
	Rotation RotationConfig `yaml:"rotation"`
}

type RotationConfig struct {
	Enabled         bool          `yaml:"enabled"`
	FilenamePattern string        `yaml:"filename_pattern"`
	MaxSize         int64         `yaml:"max_size"`
	MaxAge          time.Duration `yaml:"max_age"`
	MaxBackups      int           `yaml:"max_backups"`
	Compress        bool          `yaml:"compress"`
}
