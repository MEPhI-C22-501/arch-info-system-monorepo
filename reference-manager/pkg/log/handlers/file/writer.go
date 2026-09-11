package file

import (
	"fmt"
	"io"
	"os"
	"path/filepath"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log/config"
)

const (
	defaultDirMode  os.FileMode = 0o755
	defaultFileMode os.FileMode = 0o644
)

func newWriter(cfg config.FileConfig, handlerName string) (io.Writer, error) {
	if cfg.Location == "" {
		return nil, fmt.Errorf("location is empty")
	}

	if handlerName == "" {
		return nil, fmt.Errorf("handler name is empty")
	}

	if err := os.MkdirAll(cfg.Location, defaultDirMode); err != nil {
		return nil, fmt.Errorf("create log directory %q: %w", cfg.Location, err)
	}

	if cfg.Rotation.Enabled {
		return newRotatingWriter(cfg)
	}

	return newFileWriter(cfg.Location, handlerName)
}

func newFileWriter(location string, handlerName string) (io.Writer, error) {
	if filepath.Base(handlerName) != handlerName {
		return nil, fmt.Errorf("invalid handler name %q", handlerName)
	}

	path := filepath.Join(location, handlerName)

	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, defaultFileMode)
	if err != nil {
		return nil, fmt.Errorf("open log file %q: %w", path, err)
	}

	return f, nil
}
