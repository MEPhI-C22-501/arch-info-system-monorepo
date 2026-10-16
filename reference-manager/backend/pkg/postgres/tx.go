package postgres

import (
	"context"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

type Querier interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

type txKey struct{}

type TxManager struct {
	client *Client
}

func NewTxManager(client *Client) *TxManager {
	return &TxManager{
		client: client,
	}
}

// Do runs fn in a transaction that is committed if fn returns nil and rolled back otherwise.
// If ctx already carries a transaction, fn joins it instead of starting a new one.
func (m *TxManager) Do(ctx context.Context, fn func(ctx context.Context) error) error {
	if _, ok := ctx.Value(txKey{}).(pgx.Tx); ok {
		return fn(ctx)
	}

	return pgx.BeginFunc(ctx, m.client, func(tx pgx.Tx) error {
		return fn(context.WithValue(ctx, txKey{}, tx))
	})
}

// Querier returns the transaction carried by ctx, or the client itself when there is none.
func (c *Client) Querier(ctx context.Context) Querier {
	if tx, ok := ctx.Value(txKey{}).(pgx.Tx); ok {
		return tx
	}

	return c
}
