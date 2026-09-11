package app

import (
	logconfig "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log/config"
)

type Config struct {
	Log logconfig.Config `yaml:"log"`
}
