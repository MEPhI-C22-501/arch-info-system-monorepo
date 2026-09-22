package retry

import "time"

type Config struct {
	AttemptsCount  int           `yaml:"attempts_count" env-default:"0"`
	AttemptTimeout time.Duration `yaml:"attempt_timeout" env-default:"5s"`
	InitialDelay   time.Duration `yaml:"initial_delay" env-default:"1s"`
	MaxDelay       time.Duration `yaml:"max_delay" env-default:"5s"`
	BackoffScale   float64       `yaml:"backoff_scale" env-default:"1.1"`
}

func (c *Config) Options() []Option {
	return []Option{
		WithAttemptsCount(c.AttemptsCount),
		WithAttemptTimeout(c.AttemptTimeout),
		WithInitialDelay(c.InitialDelay),
		WithMaxDelay(c.MaxDelay),
		WithBackoffScale(c.BackoffScale),
	}
}
