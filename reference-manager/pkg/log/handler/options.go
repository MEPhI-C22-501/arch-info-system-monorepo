package handler

import (
	"log/slog"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log/config"
)

type Options struct {
	Name   string
	Level  slog.Level
	Format config.Format
}
