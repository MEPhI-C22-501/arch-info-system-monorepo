package httptr

import (
	"log/slog"
	"time"

	"github.com/go-chi/chi/v5"
	nethttpmiddleware "github.com/oapi-codegen/nethttp-middleware"

	currencyhndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/currency"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/health"
	currencyv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/currency"
	healthv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/health"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/errors"
	logmw "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/middleware/log"
	ratelimitmw "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/middleware/ratelimit"
	recoverymw "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/middleware/recovery"
	timeoutmw "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/middleware/timeout"
)

func NewRouter(
	log *slog.Logger,
	readinessChecker health.ReadinessChecker,
	// currencyService currencyhndl.Service
) *chi.Mux {
	r := chi.NewRouter()

	r.Use(
		logmw.NewMiddleware(log),
		recoverymw.NewMiddleware(log),
		ratelimitmw.NewMiddleware(10, 100),     // TODO: implement middleware init via special configuration
		timeoutmw.NewMiddleware(1*time.Second), // TODO: implement middleware init via special configuration
	)

	healthv1.HandlerFromMux(health.NewHandler(readinessChecker), r)

	r.Group(func(r chi.Router) {
		spec := errors.Must(currencyv1.GetSpec())
		r.Use(nethttpmiddleware.OapiRequestValidator(spec))

		// TODO: change nil on currencyService
		currencyv1.HandlerFromMux(currencyhndl.NewHandler(nil), r)
	})

	return r
}
