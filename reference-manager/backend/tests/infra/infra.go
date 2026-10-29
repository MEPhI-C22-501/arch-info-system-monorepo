package infra

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/url"
	"strings"
	"time"

	"github.com/testcontainers/testcontainers-go/modules/compose"
	"github.com/testcontainers/testcontainers-go/wait"
)

// Service names and container ports as declared in docker-compose.test.yaml.
const (
	serviceName  = "reference-manager"
	servicePort  = "8080/tcp"
	databaseName = "reference-manager-database"
	databasePort = "5432/tcp"
	keycloakName = "reference-manager-keycloak"
	keycloakPort = "8080/tcp"

	startupTimeout = 5 * time.Minute
)

// Infra is the test environment started from a Docker Compose file.
// Its structure (services, images, configs, migrations) is defined by the compose file only,
// endpoints and credentials are read from the started containers.
type Infra struct {
	stack *compose.DockerCompose

	BaseURL     string
	PostgresDSN string
	KeycloakURL string
	// KeycloakAdmin and KeycloakAdminPassword are the bootstrap administrator of the test Keycloak,
	// the steps check the accounts of employees through the Admin REST API with them.
	KeycloakAdmin         string
	KeycloakAdminPassword string
}

func Up(ctx context.Context, composeFile string) (*Infra, error) {
	stack, err := compose.NewDockerCompose(composeFile)
	if err != nil {
		return nil, fmt.Errorf("create compose stack: %w", err)
	}

	infra := &Infra{stack: stack}

	stack.WaitForService(serviceName, wait.ForHealthCheck().WithStartupTimeout(startupTimeout))

	// compose does not report its progress through testcontainers, so the stages are logged here
	log.Printf("starting %s: building images, starting services, waiting for %s to be healthy", composeFile, serviceName)
	started := time.Now()

	if err := stack.Up(ctx); err != nil {
		return nil, errors.Join(fmt.Errorf("start compose stack: %w", err), infra.Down(ctx))
	}

	if err := infra.resolveEndpoints(ctx); err != nil {
		return nil, errors.Join(err, infra.Down(ctx))
	}

	log.Printf("environment is ready in %s: services %v, %s at %s",
		time.Since(started).Round(time.Millisecond), stack.Services(), serviceName, infra.BaseURL)

	return infra, nil
}

func (i *Infra) Down(ctx context.Context) error {
	log.Printf("stopping environment")

	var errs []error

	if err := i.stack.Down(ctx, compose.RemoveOrphans(true), compose.RemoveVolumes(true)); err != nil {
		errs = append(errs, fmt.Errorf("stop compose stack: %w", err))
	}

	if err := i.stack.Close(); err != nil {
		errs = append(errs, fmt.Errorf("close compose stack: %w", err))
	}

	return errors.Join(errs...)
}

func (i *Infra) resolveEndpoints(ctx context.Context) error {
	service, err := i.stack.ServiceContainer(ctx, serviceName)
	if err != nil {
		return fmt.Errorf("get %s container: %w", serviceName, err)
	}

	i.BaseURL, err = service.PortEndpoint(ctx, servicePort, "http")
	if err != nil {
		return fmt.Errorf("get %s endpoint: %w", serviceName, err)
	}

	database, err := i.stack.ServiceContainer(ctx, databaseName)
	if err != nil {
		return fmt.Errorf("get %s container: %w", databaseName, err)
	}

	address, err := database.PortEndpoint(ctx, databasePort, "")
	if err != nil {
		return fmt.Errorf("get %s endpoint: %w", databaseName, err)
	}

	inspect, err := database.Inspect(ctx)
	if err != nil {
		return fmt.Errorf("inspect %s container: %w", databaseName, err)
	}

	env := parseEnv(inspect.Config.Env)

	i.PostgresDSN = (&url.URL{
		Scheme:   "postgres",
		User:     url.UserPassword(env["POSTGRES_USER"], env["POSTGRES_PASSWORD"]),
		Host:     address,
		Path:     env["POSTGRES_DB"],
		RawQuery: "sslmode=disable",
	}).String()

	keycloak, err := i.stack.ServiceContainer(ctx, keycloakName)
	if err != nil {
		return fmt.Errorf("get %s container: %w", keycloakName, err)
	}

	i.KeycloakURL, err = keycloak.PortEndpoint(ctx, keycloakPort, "http")
	if err != nil {
		return fmt.Errorf("get %s endpoint: %w", keycloakName, err)
	}

	keycloakInspect, err := keycloak.Inspect(ctx)
	if err != nil {
		return fmt.Errorf("inspect %s container: %w", keycloakName, err)
	}

	keycloakEnv := parseEnv(keycloakInspect.Config.Env)
	i.KeycloakAdmin = keycloakEnv["KC_BOOTSTRAP_ADMIN_USERNAME"]
	i.KeycloakAdminPassword = keycloakEnv["KC_BOOTSTRAP_ADMIN_PASSWORD"]

	return nil
}

func parseEnv(env []string) map[string]string {
	vars := make(map[string]string, len(env))
	for _, v := range env {
		key, value, _ := strings.Cut(v, "=")
		vars[key] = value
	}

	return vars
}
