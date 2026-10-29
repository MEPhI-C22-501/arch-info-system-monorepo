package app

import (
	httptr "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server"
	httpconfig "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/server"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/keycloak"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/telemetry"
)

type Config struct {
	Transport TransportConfig  `yaml:"transport"`
	Databases DatabasesConfig  `yaml:"databases"`
	Auth      AuthConfig       `yaml:"auth"`
	Telemetry telemetry.Config `yaml:"telemetry"`
}

type TransportConfig struct {
	HTTP   httpconfig.Config `yaml:"http"`
	Limits httptr.Limits     `yaml:"limits"`
}

type DatabasesConfig struct {
	Postgres postgres.Config `yaml:"postgres"`
}

type AuthConfig struct {
	Keycloak keycloak.Config `yaml:"keycloak"`
}
