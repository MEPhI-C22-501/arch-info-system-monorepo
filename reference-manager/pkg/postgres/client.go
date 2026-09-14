package postgres

import (
	"context"
	"fmt"
	"log/slog"
	"net"
	"net/url"
	"sync"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/retry"
)

type Client struct {
	mu           sync.RWMutex
	config       *pgxpool.Config
	pool         *pgxpool.Pool
	connectRetry *ConnectRetryConfig
	log          *slog.Logger
}

func NewClient(cfg *Config, log *slog.Logger) (*Client, error) {
	switch {
	case cfg == nil:
		return nil, fmt.Errorf("configuration is required")
	case log == nil:
		return nil, fmt.Errorf("logger is required")
	}

	dsn := (&url.URL{
		Scheme: "postgres",
		User:   url.UserPassword(cfg.User, cfg.Password),
		Host:   net.JoinHostPort(cfg.Host, cfg.Port),
		Path:   cfg.Database,
	}).String()

	poolConfig, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, fmt.Errorf("parse postgres config: %w", err)
	}

	poolConfig.MaxConns = cfg.Pool.MaxConns
	poolConfig.MinConns = cfg.Pool.MinConns
	poolConfig.MinIdleConns = cfg.Pool.MinIdleConns
	poolConfig.MaxConnLifetime = cfg.Pool.MaxConnLifetime
	poolConfig.MaxConnIdleTime = cfg.Pool.MaxConnIdleTime
	poolConfig.HealthCheckPeriod = cfg.Pool.HealthCheckPeriod

	return &Client{
		config:       poolConfig,
		connectRetry: cfg.ConnectRetry,
		log:          log,
	}, nil
}

func (c *Client) Startup(ctx context.Context) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.pool != nil {
		return ErrAlreadyStarted
	}

	pool, err := pgxpool.NewWithConfig(ctx, c.config.Copy())
	if err != nil {
		return fmt.Errorf("create postgres pool: %w", err)
	}

	if err := c.ping(ctx, pool); err != nil {
		pool.Close()

		return err
	}

	c.pool = pool

	return nil
}

func (c *Client) ping(ctx context.Context, pool *pgxpool.Pool) error {
	fn := func(ctx context.Context) error {
		return pool.Ping(ctx)
	}

	if c.connectRetry == nil || !c.connectRetry.Enabled {
		return fn(ctx)
	}

	retryOptions := append(c.connectRetry.Options(), retry.WithLogger(c.log))
	return retry.Retry(ctx, fn, retryOptions...)
}

func (c *Client) Shutdown(ctx context.Context) error {
	done := make(chan struct{})
	go func() {
		c.mu.Lock()
		defer c.mu.Unlock()

		if c.pool != nil {
			c.pool.Close()
		}

		close(done)
	}()

	select {
	case <-done:
		return nil

	case <-ctx.Done():
		return ctx.Err()
	}
}

func (c *Client) Ping(ctx context.Context) error {
	pool, err := c.getPool()
	if err != nil {
		return err
	}

	return pool.Ping(ctx)
}

func (c *Client) IsReady(ctx context.Context) bool {
	pool, err := c.getPool()
	if err != nil {
		return false
	}

	return pool.Ping(ctx) == nil
}

func (c *Client) Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error) {
	pool, err := c.getPool()
	if err != nil {
		return pgconn.CommandTag{}, err
	}

	return pool.Exec(ctx, sql, args...)
}

func (c *Client) Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error) {
	pool, err := c.getPool()
	if err != nil {
		return nil, err
	}

	return pool.Query(ctx, sql, args...)
}

func (c *Client) QueryRow(ctx context.Context, sql string, args ...any) pgx.Row {
	pool, err := c.getPool()
	if err != nil {
		return errorRow{
			err: err,
		}
	}

	return pool.QueryRow(ctx, sql, args...)
}

func (c *Client) Begin(ctx context.Context) (pgx.Tx, error) {
	pool, err := c.getPool()
	if err != nil {
		return nil, err
	}

	return pool.Begin(ctx)
}

func (c *Client) BeginTx(ctx context.Context, opts pgx.TxOptions) (pgx.Tx, error) {
	pool, err := c.getPool()
	if err != nil {
		return nil, err
	}

	return pool.BeginTx(ctx, opts)
}

func (c *Client) getPool() (*pgxpool.Pool, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	if c.pool == nil {
		return nil, ErrNotConnected
	}

	return c.pool, nil
}
