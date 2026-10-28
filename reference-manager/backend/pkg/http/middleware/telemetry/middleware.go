package telemetry

import (
	"net/http"
	"strings"

	"github.com/go-chi/chi/v5"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	semconv "go.opentelemetry.io/otel/semconv/v1.43.0"
	"go.opentelemetry.io/otel/trace"
)

const TraceIDHeader = "X-Trace-Id"

// NewMiddleware traces the request, continues the incoming traceparent and records the HTTP server metrics.
// The trace id is returned in the X-Trace-Id header, the span is named after the chi route once it is matched.
// Requests with a path under one of the skipped prefixes, such as the health probes, are not traced.
func NewMiddleware(service string, skippedPrefixes ...string) func(next http.Handler) http.Handler {
	filter := func(r *http.Request) bool {
		for _, prefix := range skippedPrefixes {
			if strings.HasPrefix(r.URL.Path, prefix) {
				return false
			}
		}

		return true
	}

	return func(next http.Handler) http.Handler {
		fn := func(w http.ResponseWriter, r *http.Request) {
			span := trace.SpanFromContext(r.Context())
			if sc := span.SpanContext(); sc.HasTraceID() {
				w.Header().Set(TraceIDHeader, sc.TraceID().String())
			}

			next.ServeHTTP(w, r)

			rctx := chi.RouteContext(r.Context())
			if rctx == nil || rctx.RoutePattern() == "" {
				return
			}

			route := rctx.RoutePattern()

			span.SetName(r.Method + " " + route)
			span.SetAttributes(semconv.HTTPRoute(route))

			if labeler, ok := otelhttp.LabelerFromContext(r.Context()); ok {
				labeler.Add(semconv.HTTPRoute(route))
			}
		}

		return otelhttp.NewMiddleware(service, otelhttp.WithFilter(filter))(http.HandlerFunc(fn))
	}
}
