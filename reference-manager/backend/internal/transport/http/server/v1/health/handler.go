package health

import (
	"context"
	"errors"
	"net/http"

	"github.com/go-chi/render"
	"github.com/hashicorp/go-multierror"

	healthv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/health"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/ready"
)

type ReadinessChecker interface {
	CheckReadiness(ctx context.Context) error
}

type Handler struct {
	readinessChecker ReadinessChecker
}

func NewHandler(readinessChecker ReadinessChecker) *Handler {
	return &Handler{
		readinessChecker: readinessChecker,
	}
}

func (h *Handler) GetLiveness(w http.ResponseWriter, _ *http.Request) {
	w.WriteHeader(http.StatusOK)
}

func (h *Handler) GetReadiness(w http.ResponseWriter, r *http.Request) {
	var err error
	if err = h.readinessChecker.CheckReadiness(r.Context()); err == nil {
		render.Status(r, http.StatusOK)
		render.JSON(w, r, healthv1.Readiness{Ready: true})
		return
	}

	failedDependencies := make([]healthv1.FailedDependency, 0)
	for _, err := range multierror.Append(nil, err).Errors {
		failure := healthv1.FailedDependency{Name: "unknown", Error: err.Error()}

		if customErr, ok := errors.AsType[*ready.Error](err); ok {
			failure.Name = customErr.CheckName
		}

		failedDependencies = append(failedDependencies, failure)
	}

	render.Status(r, http.StatusServiceUnavailable)
	render.JSON(w, r, healthv1.Readiness{
		Ready:              false,
		FailedDependencies: failedDependencies,
	})
}
