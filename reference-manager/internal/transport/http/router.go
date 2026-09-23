package httptr

import (
	"log/slog"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/health"
	apiv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1"
	logmw "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/middleware/log"
	ratelimitmw "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/middleware/ratelimit"
	recoverymw "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/middleware/recovery"
	timeoutmw "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/middleware/timeout"
)

func NewRouter(
	log *slog.Logger,
	readinessChecker health.ReadinessChecker,
) *chi.Mux {
	r := chi.NewRouter()

	r.Use(
		logmw.NewMiddleware(log),
		recoverymw.NewMiddleware(log),
		ratelimitmw.NewMiddleware(10, 100),
		timeoutmw.NewMiddleware(1*time.Second),
	)

	r.Mount("/v1", apiv1.Handler(
		health.NewHandler(readinessChecker)),
	)

	return r
}
