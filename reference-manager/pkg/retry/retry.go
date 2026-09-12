package retry

import (
	"context"
	"fmt"
	"log/slog"
	"time"
)

type RetryableFunc func(ctx context.Context) error

func Retry(ctx context.Context, fn RetryableFunc, opts ...Option) error {
	options := defaultOptions()
	for _, opt := range opts {
		if err := opt(options); err != nil {
			return fmt.Errorf("retry: invalid option: %w", err)
		}
	}

	var lastErr error

	attempt, currentDelay := 1, options.initialDelay
	for attempt <= options.attemptsCount {
		errCh := make(chan error)
		go func() {
			fnCtx, cancel := context.WithTimeout(ctx, options.timeout)
			defer cancel()

			select {
			case errCh <- fn(fnCtx):
			case <-ctx.Done():
			}
			close(errCh)
		}()

		select {
		case err := <-errCh:
			if err == nil {
				return nil
			}

			options.log.WithGroup("attempt_error").Error("attempt failed",
				slog.String("reason", err.Error()),
				slog.Int("attempt", attempt),
			)

			lastErr = err
			currentDelay = time.Duration(float64(currentDelay) * options.backoffScale)
			if currentDelay > options.maxDelay {
				currentDelay = options.maxDelay
			}

			attempt++

		case <-ctx.Done():
			return ctx.Err()
		}

		select {
		case <-time.After(currentDelay):
		case <-ctx.Done():
			return ctx.Err()
		}
	}

	return fmt.Errorf("retry: all %d attempts failed. last known error: %w", attempt, lastErr)
}
