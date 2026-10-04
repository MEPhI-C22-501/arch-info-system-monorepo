package telemetry

import "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/telemetry/log"

type Config struct {
	Resource ResourceConfig `yaml:"resource"`
	Log      log.Config     `yaml:"log"`
}

type ResourceConfig struct {
	ServiceName string `yaml:"service_name"`
	Environment string `yaml:"environment"`
}
