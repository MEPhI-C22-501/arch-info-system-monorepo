package ratelimit

import (
	"net/http"

	"golang.org/x/time/rate"
)

func NewMiddleware(
	requestPerSecond rate.Limit,
	burst int,
) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		limiter := rate.NewLimiter(requestPerSecond, burst)

		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if !limiter.Allow() {
				w.Header().Set("Retry-After", "1")

				http.Error(w, http.StatusText(http.StatusTooManyRequests), http.StatusTooManyRequests)

				return
			}

			next.ServeHTTP(w, r)
		})
	}
}
