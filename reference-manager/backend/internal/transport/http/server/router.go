package httptr

import (
	"log/slog"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/render"
	"golang.org/x/time/rate"

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

// Mount registers the handlers of one catalog on the authenticated router.
type Mount func(r chi.Router)

// Limits are the request limits of the router, they come from the configuration (K-07).
type Limits struct {
	// RequestsPerSecond is the sustained rate of requests the service accepts, Burst the size of the bucket.
	RequestsPerSecond float64 `yaml:"requests_per_second" env-default:"10"`
	Burst             int     `yaml:"burst" env-default:"100"`
	// RequestTimeout cancels the context of a request that runs longer.
	RequestTimeout time.Duration `yaml:"request_timeout" env-default:"1s"`
}

func NewRouter(
	log *slog.Logger,
	readinessChecker health.ReadinessChecker,
	authenticator authmw.Authenticator,
	limits *Limits,
	currencyService currencyhndl.Service,
	mounts ...Mount,
) *chi.Mux {
	r := chi.NewRouter()

	r.Use(
		// first, so the logs and the spans of the storage belong to the request trace
		telemetrymw.NewMiddleware("reference-manager", "/v1/health"),
		logmw.NewMiddleware(log),
		recoverymw.NewMiddleware(log),
		ratelimitmw.NewMiddleware(rate.Limit(limits.RequestsPerSecond), limits.Burst),
		timeoutmw.NewMiddleware(limits.RequestTimeout),
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

		for _, mount := range mounts {
			mount(r)
		}
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
