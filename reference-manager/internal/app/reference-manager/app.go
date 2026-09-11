package app

import (
	"context"
	"fmt"

	"golang.org/x/sync/errgroup"
)

type App struct {
}

func NewApp(_ *Config) (*App, error) {
	return &App{}, nil
}

func (a *App) Startup(ctx context.Context) error {
	g, _ := errgroup.WithContext(ctx)

	if err := g.Wait(); err != nil {
		return fmt.Errorf("failed to startup application: %w", err)
	}

	return nil
}

func (a *App) Shutdown(ctx context.Context) error {
	g, _ := errgroup.WithContext(ctx)

	if err := g.Wait(); err != nil {
		return fmt.Errorf("failed to shutdown application: %w", err)
	}

	return nil
}
