package app

import (
	httpconfig "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/server"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/telemetry"
)

type Config struct {
	Transport TransportConfig  `yaml:"transport"`
	Databases DatabasesConfig  `yaml:"databases"`
	Telemetry telemetry.Config `yaml:"telemetry"`
}

type TransportConfig struct {
	HTTP httpconfig.Config `yaml:"http"`
}

type DatabasesConfig struct {
	Postgres postgres.Config `yaml:"postgres"`
}
