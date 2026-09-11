package config

import (
	"fmt"
	"log/slog"
	"strings"
)

type Level string

const (
	LevelDebug Level = "debug"
	LevelInfo  Level = "info"
	LevelWarn  Level = "warn"
	LevelError Level = "error"
)

func (l *Level) UnmarshalText(text []byte) error {
	value := Level(strings.ToLower(string(text)))

	switch value {
	case LevelDebug, LevelInfo, LevelWarn, LevelError:
		*l = value
		return nil

	default:
		return fmt.Errorf("unsupported log level %q", string(text))
	}
}

func (l Level) Slog() slog.Level {
	switch l {
	case LevelDebug:
		return slog.LevelDebug

	case LevelWarn:
		return slog.LevelWarn

	case LevelError:
		return slog.LevelError

	case LevelInfo:
		fallthrough

	default:
		return slog.LevelInfo
	}
}
