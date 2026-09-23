package httptr

import (
	"github.com/go-chi/chi/v5"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/health"
	apiv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1"
)

func NewRouter(
	readinessChecker health.ReadinessChecker,
) *chi.Mux {
	r := chi.NewRouter()

	r.Mount("/v1", apiv1.Handler(
		health.NewHandler(readinessChecker)),
	)

	return r
}
