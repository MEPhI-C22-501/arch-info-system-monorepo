package server

import (
	"context"
	"errors"
	"fmt"
	"net"
	"net/http"
)

type Server struct {
	address string
	server  *http.Server
}

func NewServer(cfg *Config) *Server {
	return &Server{
		address: net.JoinHostPort(cfg.ListenHost, cfg.ListenPort),
		server: &http.Server{
			Handler:           http.DefaultServeMux,
			ReadHeaderTimeout: cfg.ReadHeaderTimeout,
			ReadTimeout:       cfg.ReadTimeout,
			WriteTimeout:      cfg.WriteTimeout,
			IdleTimeout:       cfg.IdleTimeout,
		},
	}
}

func (s *Server) RegisterRouter(h http.Handler) {
	if h != nil {
		s.server.Handler = h
	}
}

func (s *Server) Startup(ctx context.Context) error {
	listener, err := net.Listen("tcp", s.address)
	if err != nil {
		return fmt.Errorf("failed to listen expected address: %w", err)
	}

	errCh := make(chan error)
	go func() {
		select {
		case errCh <- s.server.Serve(listener):
		case <-ctx.Done():
		}
		close(errCh)
	}()

	select {
	case err := <-errCh:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}

		return fmt.Errorf("failed to serve expected address: %w", err)
	case <-ctx.Done():
		return nil
	}
}

func (s *Server) Shutdown(ctx context.Context) error {
	return s.server.Shutdown(ctx)
}
