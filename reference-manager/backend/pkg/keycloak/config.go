package keycloak

import (
	"strings"
	"time"
)

type Config struct {
	// IssuerURL is the URL of the realm, the "iss" claim of the tokens has to match it exactly,
	// e.g. https://keycloak.example.com/realms/arch-info-system.
	IssuerURL string `yaml:"issuer_url" env-required:"true"`
	// JWKSURL is the URL of the realm keys. It is set when the service reaches Keycloak by another address
	// than the one in the issuer, by default it is derived from the issuer.
	JWKSURL string `yaml:"jwks_url"`
	// Audience is required in the "aud" claim of the tokens when set.
	Audience string `yaml:"audience"`
	// ClientID is the client whose roles from the "resource_access" claim are taken in addition to the realm roles.
	ClientID string `yaml:"client_id"`
	// Algorithms are the accepted signing algorithms.
	Algorithms []string `yaml:"algorithms" env-default:"RS256"`
	// Leeway is the allowed clock skew when checking the token lifetime.
	Leeway time.Duration `yaml:"leeway" env-default:"30s"`

	JWKS JWKSConfig `yaml:"jwks"`

	// Provisioner is the service client the accounts of employees are managed with (FR-RM-53..58).
	Provisioner AdminConfig `yaml:"provisioner"`
}

type JWKSConfig struct {
	// RefreshInterval is the period of the background refresh of the cached keys.
	RefreshInterval time.Duration `yaml:"refresh_interval" env-default:"1h"`
	// UnknownKeyRefreshInterval is the minimal period between refreshes caused by tokens signed by an unknown key,
	// it keeps tokens with made up key IDs from flooding Keycloak.
	UnknownKeyRefreshInterval time.Duration `yaml:"unknown_key_refresh_interval" env-default:"1m"`
	// RequestTimeout limits a single request for the keys.
	RequestTimeout time.Duration `yaml:"request_timeout" env-default:"5s"`
}

func (c *Config) jwksURL() string {
	if c.JWKSURL != "" {
		return c.JWKSURL
	}

	return strings.TrimSuffix(c.IssuerURL, "/") + "/protocol/openid-connect/certs"
}
