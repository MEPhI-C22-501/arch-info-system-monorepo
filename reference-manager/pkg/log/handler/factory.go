package handler

import "log/slog"

type Factory interface {
	Type() string

	Create(cfg any, options Options) (slog.Handler, error)
}
