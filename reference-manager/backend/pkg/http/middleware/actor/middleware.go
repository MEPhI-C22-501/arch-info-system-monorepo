package actor

import (
	"net/http"
	"uuid"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/actor"
)

const UserIDHeader = "X-User-ID"

// NewMiddleware puts the user ID from the X-User-ID header into the request context.
// It is a temporary source of the actor until authentication via Keycloak is implemented.
// Requests without a valid header are passed on without a user, handlers decide how to treat them.
func NewMiddleware() func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			userID, err := uuid.Parse(r.Header.Get(UserIDHeader))
			if err != nil {
				next.ServeHTTP(w, r)
				return
			}

			next.ServeHTTP(w, r.WithContext(actor.WithUserID(r.Context(), userID)))
		})
	}
}
