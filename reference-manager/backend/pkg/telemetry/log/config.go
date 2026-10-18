package log

type Config struct {
	Level  string `yaml:"level"`
	Format string `yaml:"format"`
}

func (c Config) Options(external ...Option) []Option {
	return append(external, WithFormat(c.Format), WithLevel(c.Level))
}
