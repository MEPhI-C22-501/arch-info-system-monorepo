package server

import "time"

type Config struct {
	ListenHost        string        `yaml:"listen_host" env-default:"0.0.0.0"`
	ListenPort        string        `yaml:"listen_port" env-default:"8080"`
	ReadHeaderTimeout time.Duration `yaml:"read_header_timeout" env-default:"5s"`
	ReadTimeout       time.Duration `yaml:"read_timeout" env-default:"5s"`
	WriteTimeout      time.Duration `yaml:"write_timeout" env-default:"5s"`
	IdleTimeout       time.Duration `yaml:"idle_timeout" env-default:"10s"`
}
