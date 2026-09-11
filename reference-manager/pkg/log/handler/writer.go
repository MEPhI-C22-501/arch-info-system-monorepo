package handler

import (
	"fmt"
	"io"
	"log/slog"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log/config"
)

func NewWriter(writer io.Writer, options Options) (slog.Handler, error) {
	if writer == nil {
		return nil, fmt.Errorf("handler: writer is nil")
	}

	slogOptions := &slog.HandlerOptions{
		Level: options.Level,
	}

	switch options.Format {
	case config.FormatJSON:
		return slog.NewJSONHandler(writer, slogOptions), nil

	case config.FormatText:
		return slog.NewTextHandler(writer, slogOptions), nil

	default:
		return nil, fmt.Errorf("handler: unsupported format %q", options.Format)
	}
}
