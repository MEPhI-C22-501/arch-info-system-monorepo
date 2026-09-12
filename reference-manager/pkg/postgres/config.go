package postgres

import (
	"time"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/retry"
)

type Config struct {
	Host         string              `yaml:"host" env-required:"true"`
	Port         string              `yaml:"port" env-required:"true"`
	User         string              `yaml:"user" env-required:"true"`
	Password     string              `yaml:"password" env-required:"true"`
	Database     string              `yaml:"database" env-required:"true"`
	Pool         *PoolConfig         `yaml:"pool"`
	ConnectRetry *ConnectRetryConfig `yaml:"connect_retry"`
}

type PoolConfig struct {
	MaxConns          int32         `yaml:"max_connections" env-default:"10"`
	MinConns          int32         `yaml:"min_connections" env-default:"1"`
	MinIdleConns      int32         `yaml:"min_idle_connections" env-default:"1"`
	MaxConnLifetime   time.Duration `yaml:"max_connection_lifetime" env-default:"1h"`
	MaxConnIdleTime   time.Duration `yaml:"max_connection_idle_time" env-default:"30m"`
	HealthCheckPeriod time.Duration `yaml:"health_check_period" env-default:"1m"`
}

type ConnectRetryConfig struct {
	Enabled      bool `yaml:"enabled" env-default:"false"`
	retry.Config `yaml:",inline"`
}
