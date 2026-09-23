package ready

import (
	"context"
	"errors"
	"log/slog"
)

type Manager struct {
	log    *slog.Logger
	checks []*Check
}

func NewManager(log *slog.Logger, checks ...*Check) *Manager {
	return &Manager{
		log:    log,
		checks: checks,
	}
}

func (m *Manager) CheckReadiness(ctx context.Context) error {
	errs := make([]error, 0)
	for _, check := range m.checks {
		m.log.Info("running check", slog.String("name", check.name))

		if err := check.Run(ctx); err != nil {
			m.log.Error("readiness check failed", slog.String("reason", err.Error()))
			errs = append(errs, err)
		}
	}

	if len(errs) != 0 {
		return errors.Join(errs...)
	}

	m.log.Info("all readiness checks passed")
	return nil
}
