package app

import (
	httpconfig "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/server"
	logconfig "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log/config"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
)

type Config struct {
	Transport TransportConfig  `yaml:"transport"`
	Databases DatabasesConfig  `yaml:"databases"`
	Log       logconfig.Config `yaml:"log"`
}

type TransportConfig struct {
	HTTP httpconfig.Config `yaml:"http"`
}

type DatabasesConfig struct {
	Postgres postgres.Config `yaml:"postgres"`
}
