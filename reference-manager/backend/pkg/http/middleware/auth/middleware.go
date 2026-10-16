package auth

import (
	"context"
	"errors"
	"net/http"
	"strings"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/actor"
)

const bearerScheme = "Bearer"

var (
	ErrMissingToken   = errors.New("bearer token is missing")
	ErrMalformedToken = errors.New("authorization header is not a bearer token")
)

// Authenticator verifies an access token and returns its actor.
type Authenticator interface {
	Authenticate(ctx context.Context, token string) (*actor.Actor, error)
}

// ErrorHandler responds to a request that failed authentication.
type ErrorHandler func(w http.ResponseWriter, r *http.Request, err error)

// NewMiddleware requires a valid bearer token in the Authorization header and puts its actor into the request context.
// Requests without a valid token are passed to the error handler and do not reach the next handler.
func NewMiddleware(authenticator Authenticator, onError ErrorHandler) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			token, err := bearerToken(r)
			if err != nil {
				onError(w, r, err)
				return
			}

			a, err := authenticator.Authenticate(r.Context(), token)
			if err != nil {
				onError(w, r, err)
				return
			}

			next.ServeHTTP(w, r.WithContext(actor.WithActor(r.Context(), a)))
		})
	}
}

func bearerToken(r *http.Request) (string, error) {
	header := r.Header.Get("Authorization")
	if header == "" {
		return "", ErrMissingToken
	}

	scheme, token, ok := strings.Cut(header, " ")
	if !ok || !strings.EqualFold(scheme, bearerScheme) {
		return "", ErrMalformedToken
	}

	token = strings.TrimSpace(token)
	if token == "" {
		return "", ErrMalformedToken
	}

	return token, nil
}
