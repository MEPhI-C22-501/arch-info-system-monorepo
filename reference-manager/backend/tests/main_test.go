//go:build integration

package tests

import (
	"context"
	"net/http"
	"testing"

	"github.com/cucumber/godog"
	"github.com/jackc/pgx/v5/pgxpool"
	"go.uber.org/goleak"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/tests/infra"
	httpsteps "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/tests/steps/http"
	sqlsteps "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/tests/steps/sql"
)

const (
	composeFile = "docker-compose.test.yaml"
	realm       = "arch-info-system"
)

func TestMain(m *testing.M) {
	goleak.VerifyTestMain(m,
		// connections to Ryuk live until the process exits, so it removes the containers if the tests crash
		goleak.IgnoreTopFunction("github.com/testcontainers/testcontainers-go.(*Reaper).connect.func1"),
	)
}

func TestFeatures(t *testing.T) {
	ctx := context.Background()

	env, err := infra.Up(ctx, composeFile)
	if err != nil {
		t.Fatalf("start test environment: %v", err)
	}
	t.Cleanup(func() {
		if err := env.Down(context.Background()); err != nil {
			t.Errorf("stop test environment: %v", err)
		}
	})

	pool, err := pgxpool.New(ctx, env.PostgresDSN)
	if err != nil {
		t.Fatalf("create postgres pool: %v", err)
	}
	defer pool.Close()

	if err := pool.Ping(ctx); err != nil {
		t.Fatalf("ping postgres: %v", err)
	}

	transport := http.DefaultTransport.(*http.Transport).Clone()
	defer transport.CloseIdleConnections()

	client := &http.Client{Transport: transport}
	tokens := httpsteps.NewTokens(env.KeycloakURL, realm, client)

	suite := godog.TestSuite{
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			httpsteps.New(env.BaseURL, client, tokens).Register(sc)
			sqlsteps.New(pool).Register(sc)
		},
		Options: &godog.Options{
			Format:   "pretty",
			Paths:    []string{"features"},
			Tags:     "~@skip",
			Strict:   true,
			TestingT: t,
		},
	}

	if suite.Run() != 0 {
		t.Fatal("integration tests failed")
	}
}
