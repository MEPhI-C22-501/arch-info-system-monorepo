package app

import (
	"context"
	"fmt"
	"log/slog"

	"golang.org/x/sync/errgroup"

	httptr "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http"
	httpserver "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/server"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/ready"
)

type App struct {
	log *slog.Logger

	httpServer     *httpserver.Server
	postgresClient *postgres.Client
}

func NewApp(cfg *Config) (*App, error) {
	log, err := log.New(cfg.Log)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize logger: %w", err)
	}

	postgresClient, err := postgres.NewClient(&cfg.Databases.Postgres, log)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize postgres client: %w", err)
	}

	readinessManager := ready.NewManager(log, postgresClient.ReadinessCheck())

	httpServer := httpserver.NewServer(&cfg.Transport.HTTP)
	httpServer.RegisterRouter(httptr.NewRouter(readinessManager))

	log.Info("application initialized successfully")
	return &App{
		log:            log,
		httpServer:     httpServer,
		postgresClient: postgresClient,
	}, nil
}

func (a *App) Startup(ctx context.Context) error {
	a.log.Info("application startup")

	g, gCtx := errgroup.WithContext(ctx)

	g.Go(func() error {
		a.log.Info("postgres client startup")
		return a.postgresClient.Startup(gCtx)
	})

	g.Go(func() error {
		a.log.Info("http server startup")
		return a.httpServer.Startup(gCtx)
	})

	if err := g.Wait(); err != nil {
		a.log.Error("failed to startup application", slog.String("error", err.Error()))
		return fmt.Errorf("failed to startup application: %w", err)
	}

	return nil
}

func (a *App) Shutdown(ctx context.Context) error {
	a.log.Info("application shutdown")

	g, gCtx := errgroup.WithContext(ctx)

	g.Go(func() error {
		a.log.Info("postgres client shutdown")
		return a.postgresClient.Shutdown(gCtx)
	})

	g.Go(func() error {
		a.log.Info("http server shutdown")
		return a.httpServer.Shutdown(gCtx)
	})

	if err := g.Wait(); err != nil {
		a.log.Error("failed to shutdown application", slog.String("error", err.Error()))
		return fmt.Errorf("failed to shutdown application: %w", err)
	}

	return nil
}
