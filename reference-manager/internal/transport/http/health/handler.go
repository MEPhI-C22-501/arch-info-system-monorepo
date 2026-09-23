package health

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"

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

type DependencyFailure struct {
	Name  string `json:"name"`
	Error string `json:"error"`
}

type ReadinessResponse struct {
	Ready              bool                `json:"ready"`
	FailedDependencies []DependencyFailure `json:"failed_dependencies,omitempty"`
}

func (h *Handler) GetLiveness(w http.ResponseWriter, _ *http.Request) {
	w.WriteHeader(http.StatusOK)
}

func (h *Handler) GetReadiness(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	err := h.readinessChecker.CheckReadiness(r.Context())
	if err == nil {
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(ReadinessResponse{Ready: true})

		return
	}

	errs := []error{err}

	var multiErr interface{ Unwrap() []error }
	if errors.As(err, &multiErr) {
		errs = multiErr.Unwrap()
	}

	dependencies := make([]DependencyFailure, 0, len(errs))

	for _, err := range errs {
		failure := DependencyFailure{Name: "unknown", Error: err.Error()}

		if customErr, ok := errors.AsType[*ready.Error](err); ok {
			failure.Name = customErr.CheckName
		}

		dependencies = append(dependencies, failure)
	}

	w.WriteHeader(http.StatusServiceUnavailable)
	_ = json.NewEncoder(w).Encode(ReadinessResponse{
		Ready:              false,
		FailedDependencies: dependencies,
	})
}
