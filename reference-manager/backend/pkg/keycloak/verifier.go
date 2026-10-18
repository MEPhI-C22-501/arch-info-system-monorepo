// Package keycloak verifies access tokens issued by Keycloak.
package keycloak

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"slices"
	"strings"
	"time"
	"uuid"

	"github.com/MicahParks/keyfunc/v3"
	"github.com/golang-jwt/jwt/v5"
	"golang.org/x/time/rate"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/actor"
)

// accessTokenType is the "typ" claim of Keycloak access tokens, ID and refresh tokens have other types.
const accessTokenType = "Bearer"

// unknownKeyWait is how long a request may wait for the refresh caused by an unknown key.
// It is short on purpose: a request is rejected rather than held while the refreshes are rate limited.
const unknownKeyWait = time.Millisecond

// ErrInvalidToken is returned for any token that can not be trusted, the wrapped error tells the reason.
var ErrInvalidToken = errors.New("invalid token")

// Verifier checks the signature and the claims of access tokens. The signing keys are taken from the realm JWKS
// and cached, they are refreshed periodically and when a token is signed by an unknown key,
// so key rotation in Keycloak needs no restart and a short Keycloak outage does not affect requests.
type Verifier struct {
	log      *slog.Logger
	clientID string
	keyfunc  keyfunc.Keyfunc
	parser   *jwt.Parser
	cancel   context.CancelFunc
}

func NewVerifier(cfg *Config, log *slog.Logger) (*Verifier, error) {
	if cfg.IssuerURL == "" {
		return nil, errors.New("issuer URL is required")
	}

	if len(cfg.Algorithms) == 0 {
		return nil, errors.New("at least one signing algorithm is required")
	}

	ctx, cancel := context.WithCancel(context.Background())

	jwksURL := cfg.jwksURL()
	log = log.With(slog.String("jwks_url", jwksURL))

	// keys are not required at startup, so that the service starts while Keycloak is unavailable,
	// they are fetched again by the first token with an unknown key
	kf, err := keyfunc.NewDefaultOverrideCtx(ctx, []string{jwksURL}, keyfunc.Override{
		Client:            &http.Client{Timeout: cfg.JWKS.RequestTimeout},
		HTTPTimeout:       cfg.JWKS.RequestTimeout,
		RateLimitWaitMax:  unknownKeyWait,
		RefreshInterval:   cfg.JWKS.RefreshInterval,
		RefreshUnknownKID: rate.NewLimiter(rate.Every(cfg.JWKS.UnknownKeyRefreshInterval), 1),
		RefreshErrorHandlerFunc: func(string) func(ctx context.Context, err error) {
			return func(ctx context.Context, err error) {
				log.WarnContext(ctx, "failed to refresh keycloak signing keys", slog.String("error", err.Error()))
			}
		},
	})
	if err != nil {
		cancel()
		return nil, fmt.Errorf("create keycloak signing keys storage: %w", err)
	}

	options := []jwt.ParserOption{
		jwt.WithValidMethods(cfg.Algorithms),
		jwt.WithIssuer(cfg.IssuerURL),
		jwt.WithLeeway(cfg.Leeway),
		jwt.WithExpirationRequired(),
		jwt.WithIssuedAt(),
	}
	if cfg.Audience != "" {
		options = append(options, jwt.WithAudience(cfg.Audience))
	}

	return &Verifier{
		log:      log,
		clientID: cfg.ClientID,
		keyfunc:  kf,
		parser:   jwt.NewParser(options...),
		cancel:   cancel,
	}, nil
}

type roles struct {
	Roles []string `json:"roles"`
}

type claims struct {
	jwt.RegisteredClaims

	Type           string           `json:"typ"`
	RealmAccess    roles            `json:"realm_access"`
	ResourceAccess map[string]roles `json:"resource_access"`
}

// Authenticate verifies the access token and returns its actor: the user ID from the "sub" claim
// and the realm roles together with the roles of the configured client.
func (v *Verifier) Authenticate(ctx context.Context, token string) (*actor.Actor, error) {
	var c claims
	if _, err := v.parser.ParseWithClaims(token, &c, v.keyfunc.KeyfuncCtx(ctx)); err != nil {
		return nil, fmt.Errorf("%w: %w", ErrInvalidToken, err)
	}

	if !strings.EqualFold(c.Type, accessTokenType) {
		return nil, fmt.Errorf("%w: token type %q is not an access token", ErrInvalidToken, c.Type)
	}

	userID, err := uuid.Parse(c.Subject)
	if err != nil {
		return nil, fmt.Errorf("%w: subject is not a user ID: %w", ErrInvalidToken, err)
	}

	tokenRoles := slices.Clone(c.RealmAccess.Roles)
	if v.clientID != "" {
		tokenRoles = append(tokenRoles, c.ResourceAccess[v.clientID].Roles...)
	}

	slices.Sort(tokenRoles)

	return &actor.Actor{
		UserID: userID,
		Roles:  slices.Compact(tokenRoles),
	}, nil
}

// Shutdown stops the background refresh of the signing keys.
func (v *Verifier) Shutdown(_ context.Context) error {
	v.cancel()
	return nil
}
