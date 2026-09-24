package main

import (
	"context"
	"flag"
	"os/signal"
	"syscall"

	app "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/app/reference-manager"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/config"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/errors"
)

func main() {
	var configs string

	flag.StringVar(&configs, "configs", "", `path to the directory with configuration files. If not provided, configuration will be read from environment variables`)
	flag.Parse()

	cfg := errors.Must(config.Read[app.Config](configs))

	initCtx, initCancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	app, err := app.NewApp(initCtx, cfg)
	if err != nil {
		initCancel()
		panic(err)
	}

	initCancel()

	startupCtx, startupCancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	if err := app.Startup(startupCtx); err != nil {
		startupCancel()
		panic(err)
	}

	startupCancel()

	shutdownCtx, shutdownCancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer shutdownCancel()

	if err := app.Shutdown(shutdownCtx); err != nil {
		panic(err)
	}
}
