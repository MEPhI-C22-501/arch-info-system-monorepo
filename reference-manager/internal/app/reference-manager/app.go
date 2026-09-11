package app

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log"
	"golang.org/x/sync/errgroup"
)

type App struct {
	log *slog.Logger
}

func NewApp(cfg *Config) (*App, error) {
	log, err := log.New(cfg.Log)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize logger: %w", err)
	}

	log.Info("application initialized successfully")
	return &App{
		log: log,
	}, nil
}

func (a *App) Startup(ctx context.Context) error {
	a.log.Info("application startup")

	g, _ := errgroup.WithContext(ctx)

	if err := g.Wait(); err != nil {
		a.log.Error("failed to startup application", slog.String("error", err.Error()))
		return fmt.Errorf("failed to startup application: %w", err)
	}

	return nil
}

func (a *App) Shutdown(ctx context.Context) error {
	a.log.Info("application shutdown")

	g, _ := errgroup.WithContext(ctx)

	if err := g.Wait(); err != nil {
		a.log.Error("failed to shutdown application", slog.String("error", err.Error()))
		return fmt.Errorf("failed to shutdown application: %w", err)
	}

	return nil
}
