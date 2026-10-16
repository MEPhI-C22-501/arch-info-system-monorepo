package auth_test

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"uuid"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/actor"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/http/middleware/auth"
)

type authenticatorFunc func(ctx context.Context, token string) (*actor.Actor, error)

func (f authenticatorFunc) Authenticate(ctx context.Context, token string) (*actor.Actor, error) {
	return f(ctx, token)
}

func TestMiddleware(t *testing.T) {
	t.Parallel()

	var (
		user = &actor.Actor{
			UserID: uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6"),
			Roles:  []string{"reference-reader"},
		}
		errInvalid = errors.New("invalid token")

		authenticator = authenticatorFunc(func(_ context.Context, token string) (*actor.Actor, error) {
			if token != "valid" {
				return nil, errInvalid
			}

			return user, nil
		})
	)

	testCases := map[string]struct {
		header string
		actor  *actor.Actor
		err    error
	}{
		"valid token": {
			header: "Bearer valid",
			actor:  user,
		},
		"scheme is case insensitive": {
			header: "bearer valid",
			actor:  user,
		},
		"header is absent": {
			err: auth.ErrMissingToken,
		},
		"basic scheme": {
			header: "Basic dXNlcjpwYXNz",
			err:    auth.ErrMalformedToken,
		},
		"empty token": {
			header: "Bearer ",
			err:    auth.ErrMalformedToken,
		},
		"token without scheme": {
			header: "valid",
			err:    auth.ErrMalformedToken,
		},
		"invalid token": {
			header: "Bearer forged",
			err:    errInvalid,
		},
	}

	for name, tc := range testCases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			var (
				reached  bool
				gotActor *actor.Actor
				gotErr   error
			)

			next := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				reached = true
				gotActor, _ = actor.FromContext(r.Context())
				w.WriteHeader(http.StatusOK)
			})
			onError := func(w http.ResponseWriter, _ *http.Request, err error) {
				gotErr = err
				w.WriteHeader(http.StatusUnauthorized)
			}

			r := httptest.NewRequest(http.MethodGet, "/v1/currencies/", http.NoBody)
			if tc.header != "" {
				r.Header.Set("Authorization", tc.header)
			}

			w := httptest.NewRecorder()
			auth.NewMiddleware(authenticator, onError)(next).ServeHTTP(w, r)

			if tc.err != nil {
				require.ErrorIs(t, gotErr, tc.err)
				assert.False(t, reached)
				assert.Equal(t, http.StatusUnauthorized, w.Code)

				return
			}

			require.NoError(t, gotErr)
			assert.True(t, reached)
			assert.Equal(t, tc.actor, gotActor)
		})
	}
}
