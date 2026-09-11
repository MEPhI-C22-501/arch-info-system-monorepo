package app

import (
	httpconfig "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/server"
	logconfig "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log/config"
)

type Config struct {
	Transport TransportConfig  `yaml:"transport"`
	Log       logconfig.Config `yaml:"log"`
}

type TransportConfig struct {
	HTTP httpconfig.Config `yaml:"http"`
}
