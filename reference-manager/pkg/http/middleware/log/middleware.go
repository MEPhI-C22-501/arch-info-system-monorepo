package log

import (
	"log/slog"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5/middleware"
)

func NewMiddleware(log *slog.Logger) func(next http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		fn := func(w http.ResponseWriter, r *http.Request) {
			ww := middleware.NewWrapResponseWriter(w, r.ProtoMajor)

			t1 := time.Now()

			defer func() {
				log.InfoContext(r.Context(), "request completed",
					slog.Group("request_metadata",
						slog.String("method", r.Method),
						slog.String("path", r.URL.Path),
						slog.String("remote_addr", r.RemoteAddr),
						slog.String("user_agent", r.UserAgent()),
						slog.String("request_id", middleware.GetReqID(r.Context())),
					),
					slog.Group("response_metadata",
						slog.Int("status", ww.Status()),
						slog.Int("bytes", ww.BytesWritten()),
						slog.Duration("duration", time.Since(t1)),
					),
				)
			}()

			next.ServeHTTP(ww, r)
		}

		return http.HandlerFunc(fn)
	}
}
