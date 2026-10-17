package httptr

import (
	"log/slog"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/render"

	currencyhndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/currency"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/health"
	currencyv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/currency"
	healthv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/health"
	authmw "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/middleware/auth"
	logmw "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/middleware/log"
	ratelimitmw "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/middleware/ratelimit"
	recoverymw "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/middleware/recovery"
	telemetrymw "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/middleware/telemetry"
	timeoutmw "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/middleware/timeout"
)

func NewRouter(
	log *slog.Logger,
	readinessChecker health.ReadinessChecker,
	authenticator authmw.Authenticator,
	currencyService currencyhndl.Service,
) *chi.Mux {
	r := chi.NewRouter()

	r.Use(
		// first, so the logs and the spans of the storage belong to the request trace
		telemetrymw.NewMiddleware("reference-manager", "/v1/health"),
		logmw.NewMiddleware(log),
		recoverymw.NewMiddleware(log),
		ratelimitmw.NewMiddleware(10, 100),     // TODO: implement middleware init via special configuration
		timeoutmw.NewMiddleware(1*time.Second), // TODO: implement middleware init via special configuration
	)

	// health endpoints are called by the infrastructure without a token
	healthv1.HandlerFromMux(health.NewHandler(readinessChecker), r)

	r.Group(func(r chi.Router) {
		r.Use(authmw.NewMiddleware(authenticator, unauthenticated(log)))

		currencyHandler := currencyhndl.NewHandler(currencyService)
		currencyv1.HandlerWithOptions(currencyHandler, currencyv1.ChiServerOptions{
			BaseRouter:       r,
			ErrorHandlerFunc: currencyHandler.HandleParamError,
		})
	})

	return r
}

// unauthenticated responds to requests without a valid access token, the reason is logged and not returned.
func unauthenticated(log *slog.Logger) authmw.ErrorHandler {
	return func(w http.ResponseWriter, r *http.Request, err error) {
		log.DebugContext(r.Context(), "request is not authenticated", slog.String("error", err.Error()))

		w.Header().Set("WWW-Authenticate", `Bearer error="invalid_token"`)
		render.Status(r, http.StatusUnauthorized)
		render.JSON(w, r, currencyv1.Error{Message: "unauthenticated"})
	}
}
