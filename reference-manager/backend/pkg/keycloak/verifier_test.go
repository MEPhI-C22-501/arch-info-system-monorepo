package keycloak_test

import (
	"context"
	"crypto/rand"
	"crypto/rsa"
	"encoding/base64"
	"encoding/json"
	"io"
	"log/slog"
	"math/big"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"
	"uuid"

	"github.com/golang-jwt/jwt/v5"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/actor"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/keycloak"
)

const (
	issuer   = "http://keycloak.test/realms/arch-info-system"
	audience = "reference-manager"
	clientID = "reference-manager"
)

var userID = uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6")

type signingKey struct {
	id  string
	key *rsa.PrivateKey
}

func newSigningKey(t *testing.T, id string) signingKey {
	t.Helper()

	key, err := rsa.GenerateKey(rand.Reader, 2048)
	require.NoError(t, err)

	return signingKey{id: id, key: key}
}

func (k signingKey) sign(t *testing.T, claims jwt.MapClaims) string {
	t.Helper()

	token := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	token.Header["kid"] = k.id

	signed, err := token.SignedString(k.key)
	require.NoError(t, err)

	return signed
}

// jwksServer serves the public parts of its keys like the certs endpoint of a Keycloak realm.
type jwksServer struct {
	*httptest.Server

	mu   sync.Mutex
	keys []signingKey
	down bool
}

func newJWKSServer(t *testing.T, keys ...signingKey) *jwksServer {
	t.Helper()

	s := &jwksServer{keys: keys}
	s.Server = httptest.NewServer(http.HandlerFunc(s.serveHTTP))
	t.Cleanup(s.Close)

	return s
}

func (s *jwksServer) setKeys(keys ...signingKey) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.keys = keys
}

func (s *jwksServer) setDown(down bool) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.down = down
}

func (s *jwksServer) serveHTTP(w http.ResponseWriter, _ *http.Request) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.down {
		w.WriteHeader(http.StatusServiceUnavailable)
		return
	}

	keys := make([]map[string]string, 0, len(s.keys))
	for _, k := range s.keys {
		keys = append(keys, map[string]string{
			"kid": k.id,
			"kty": "RSA",
			"alg": "RS256",
			"use": "sig",
			"n":   base64.RawURLEncoding.EncodeToString(k.key.N.Bytes()),
			"e":   base64.RawURLEncoding.EncodeToString(big.NewInt(int64(k.key.E)).Bytes()),
		})
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]any{"keys": keys})
}

func newVerifier(t *testing.T, jwksURL string) *keycloak.Verifier {
	t.Helper()

	v, err := keycloak.NewVerifier(&keycloak.Config{
		IssuerURL:  issuer,
		JWKSURL:    jwksURL,
		Audience:   audience,
		ClientID:   clientID,
		Algorithms: []string{"RS256"},
		Leeway:     time.Second,
		JWKS: keycloak.JWKSConfig{
			RefreshInterval:           time.Hour,
			UnknownKeyRefreshInterval: time.Millisecond,
			RequestTimeout:            time.Second,
		},
	}, slog.New(slog.NewTextHandler(io.Discard, nil)))
	require.NoError(t, err)

	t.Cleanup(func() { _ = v.Shutdown(context.Background()) })

	return v
}

func accessTokenClaims() jwt.MapClaims {
	now := time.Now()

	return jwt.MapClaims{
		"iss": issuer,
		"aud": []string{audience, "account"},
		"sub": userID.String(),
		"typ": "Bearer",
		"iat": now.Unix(),
		"exp": now.Add(5 * time.Minute).Unix(),
		"realm_access": map[string]any{
			"roles": []string{"reference-reader", "default-roles-arch-info-system"},
		},
		"resource_access": map[string]any{
			clientID:  map[string]any{"roles": []string{"reference-admin", "reference-reader"}},
			"account": map[string]any{"roles": []string{"manage-account"}},
		},
	}
}

func TestVerifierAuthenticate(t *testing.T) {
	t.Parallel()

	key := newSigningKey(t, "key-1")
	otherKey := newSigningKey(t, "key-2")
	server := newJWKSServer(t, key)
	verifier := newVerifier(t, server.URL)

	with := func(changes map[string]any) jwt.MapClaims {
		claims := accessTokenClaims()
		for name, value := range changes {
			if value == nil {
				delete(claims, name)
				continue
			}

			claims[name] = value
		}

		return claims
	}

	testCases := map[string]struct {
		token string
		want  *actor.Actor
	}{
		"valid access token": {
			token: key.sign(t, accessTokenClaims()),
			want: &actor.Actor{
				UserID: userID,
				Roles:  []string{"default-roles-arch-info-system", "reference-admin", "reference-reader"},
			},
		},
		"expired": {
			token: key.sign(t, with(map[string]any{"exp": time.Now().Add(-time.Minute).Unix()})),
		},
		"without expiration": {
			token: key.sign(t, with(map[string]any{"exp": nil})),
		},
		"issued in the future": {
			token: key.sign(t, with(map[string]any{"iat": time.Now().Add(time.Hour).Unix()})),
		},
		"not yet valid": {
			token: key.sign(t, with(map[string]any{"nbf": time.Now().Add(time.Hour).Unix()})),
		},
		"another issuer": {
			token: key.sign(t, with(map[string]any{"iss": "http://keycloak.test/realms/master"})),
		},
		"another audience": {
			token: key.sign(t, with(map[string]any{"aud": "account"})),
		},
		"ID token": {
			token: key.sign(t, with(map[string]any{"typ": "ID"})),
		},
		"subject is not a user ID": {
			token: key.sign(t, with(map[string]any{"sub": "service-account"})),
		},
		"signed by an unknown key": {
			token: otherKey.sign(t, accessTokenClaims()),
		},
		"signed by an unknown key with a known key ID": {
			token: signingKey{id: key.id, key: otherKey.key}.sign(t, accessTokenClaims()),
		},
		"symmetric algorithm": {
			token: func() string {
				token := jwt.NewWithClaims(jwt.SigningMethodHS256, accessTokenClaims())
				token.Header["kid"] = key.id

				signed, err := token.SignedString([]byte("secret"))
				require.NoError(t, err)

				return signed
			}(),
		},
		"unsigned": {
			token: func() string {
				signed, err := jwt.NewWithClaims(jwt.SigningMethodNone, accessTokenClaims()).
					SignedString(jwt.UnsafeAllowNoneSignatureType)
				require.NoError(t, err)

				return signed
			}(),
		},
		"garbage": {
			token: "not-a-jwt",
		},
	}

	for name, tc := range testCases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			got, err := verifier.Authenticate(context.Background(), tc.token)
			if tc.want == nil {
				require.ErrorIs(t, err, keycloak.ErrInvalidToken)
				assert.Nil(t, got)

				return
			}

			require.NoError(t, err)
			assert.Equal(t, tc.want, got)
		})
	}
}

func TestVerifierPicksUpRotatedKey(t *testing.T) {
	t.Parallel()

	oldKey := newSigningKey(t, "old")
	newKey := newSigningKey(t, "new")
	server := newJWKSServer(t, oldKey)
	verifier := newVerifier(t, server.URL)

	_, err := verifier.Authenticate(context.Background(), oldKey.sign(t, accessTokenClaims()))
	require.NoError(t, err)

	server.setKeys(newKey)

	_, err = verifier.Authenticate(context.Background(), newKey.sign(t, accessTokenClaims()))
	require.NoError(t, err)
}

func TestVerifierUsesCachedKeysWhileKeycloakIsDown(t *testing.T) {
	t.Parallel()

	key := newSigningKey(t, "key-1")
	server := newJWKSServer(t, key)
	verifier := newVerifier(t, server.URL)

	server.setDown(true)

	_, err := verifier.Authenticate(context.Background(), key.sign(t, accessTokenClaims()))
	require.NoError(t, err)
}

func TestVerifierStartsWhileKeycloakIsDown(t *testing.T) {
	t.Parallel()

	key := newSigningKey(t, "key-1")
	server := newJWKSServer(t, key)
	server.setDown(true)

	verifier := newVerifier(t, server.URL)

	_, err := verifier.Authenticate(context.Background(), key.sign(t, accessTokenClaims()))
	require.ErrorIs(t, err, keycloak.ErrInvalidToken)

	server.setDown(false)

	_, err = verifier.Authenticate(context.Background(), key.sign(t, accessTokenClaims()))
	require.NoError(t, err)
}

func TestVerifierWithoutClientRoles(t *testing.T) {
	t.Parallel()

	key := newSigningKey(t, "key-1")
	server := newJWKSServer(t, key)

	v, err := keycloak.NewVerifier(&keycloak.Config{
		IssuerURL:  issuer,
		JWKSURL:    server.URL,
		Algorithms: []string{"RS256"},
		JWKS:       keycloak.JWKSConfig{RefreshInterval: time.Hour, UnknownKeyRefreshInterval: time.Minute, RequestTimeout: time.Second},
	}, slog.New(slog.NewTextHandler(io.Discard, nil)))
	require.NoError(t, err)
	t.Cleanup(func() { _ = v.Shutdown(context.Background()) })

	got, err := v.Authenticate(context.Background(), key.sign(t, accessTokenClaims()))
	require.NoError(t, err)
	assert.Equal(t, []string{"default-roles-arch-info-system", "reference-reader"}, got.Roles)
}
