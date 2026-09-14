package retry

import (
	"errors"
	"log/slog"
	"time"
)

const (
	DefaultAttempts int           = 3
	DefaultDelay    time.Duration = 100 * time.Millisecond
	DefaultMaxDelay time.Duration = 5 * time.Second
	DefaultTimeout  time.Duration = 5 * time.Second
	DefaultScale    float64       = 2.0
)

type options struct {
	attemptsCount int
	initialDelay  time.Duration
	maxDelay      time.Duration
	timeout       time.Duration
	backoffScale  float64
	log           *slog.Logger
}

func defaultOptions() *options {
	return &options{
		attemptsCount: DefaultAttempts,
		initialDelay:  DefaultDelay,
		maxDelay:      DefaultMaxDelay,
		timeout:       DefaultTimeout,
		backoffScale:  DefaultScale,
		log:           slog.New(slog.DiscardHandler),
	}
}

type Option func(*options) error

var (
	ErrInvalidAttempts = errors.New("attempts cannot be negative")
	ErrInvalidDelay    = errors.New("delay must be greater than 0")
	ErrInvalidMaxDelay = errors.New("max delay must be greater than 0")
	ErrInvalidTimeout  = errors.New("timeout must be greater than 0")
	ErrInvalidScale    = errors.New("scale must be greater than 1.0")
	ErrNilLogger       = errors.New("logger cannot be nil")
)

func WithAttemptsCount(attempts int) Option {
	return func(o *options) error {
		if attempts < 0 {
			return ErrInvalidAttempts
		}
		o.attemptsCount = attempts
		return nil
	}
}

func WithInitialDelay(delay time.Duration) Option {
	return func(o *options) error {
		if delay <= 0 {
			return ErrInvalidDelay
		}
		o.initialDelay = delay
		return nil
	}
}

func WithMaxDelay(maxDelay time.Duration) Option {
	return func(o *options) error {
		if maxDelay <= 0 {
			return ErrInvalidMaxDelay
		}
		o.maxDelay = maxDelay
		return nil
	}
}

func WithAttemptTimeout(timeout time.Duration) Option {
	return func(o *options) error {
		if timeout <= 0 {
			return ErrInvalidTimeout
		}
		o.timeout = timeout
		return nil
	}
}

func WithBackoffScale(scale float64) Option {
	return func(o *options) error {
		if scale <= 1.0 {
			return ErrInvalidScale
		}
		o.backoffScale = scale
		return nil
	}
}

func WithLogger(log *slog.Logger) Option {
	return func(o *options) error {
		if log == nil {
			return ErrNilLogger
		}
		o.log = log
		return nil
	}
}
