package keycloak

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"path"
	"strings"
	"sync"
	"time"
)

var (
	// ErrAccountUnavailable is returned when Keycloak cannot be reached, times out or answers with an unexpected
	// status. The caller keeps its operation pending and repeats it later (FR-RM-55).
	ErrAccountUnavailable = errors.New("keycloak is unavailable")
	// ErrAccountConflict is returned when Keycloak refuses the account because its username or email is taken.
	ErrAccountConflict = errors.New("account conflict")
	// ErrAccountNotFound is returned when the account with the identifier does not exist.
	ErrAccountNotFound = errors.New("account not found")
)

// maxResponseSize limits what is read from a Keycloak response.
const maxResponseSize = 1 << 20

// tokenRefreshMargin is how long before its expiration the cached service token is renewed.
const tokenRefreshMargin = 10 * time.Second

// Account is the part of a Keycloak user the service manages. Passwords are never read back (FR-RM-58).
type Account struct {
	// ID is the identifier of the user in Keycloak, the "sub" claim of its tokens.
	ID        string
	Username  string
	Email     string
	FirstName string
	LastName  string
	Enabled   bool
}

// AdminConfig configures the calls to the Keycloak Admin REST API under the provisioner client (ADR-019).
type AdminConfig struct {
	// BaseURL is the address the service reaches Keycloak at, by default the address of the JWKS without the realm path.
	BaseURL string `yaml:"base_url"`
	// Realm is the realm the accounts are created in, by default the realm of the JWKS.
	Realm string `yaml:"realm"`
	// ClientID is the service client with the realm-management roles manage-users, view-users, query-users and view-realm.
	ClientID string `yaml:"client_id" env-default:"reference-manager-provisioner"`
	// ClientSecret comes from the environment only, it is never read from a configuration file (NFR-RM-22).
	ClientSecret string `yaml:"-" env:"KEYCLOAK_PROVISIONER_SECRET" env-required:"true"`
	// RequestTimeout limits every call to Keycloak (NFR-RM-47).
	RequestTimeout time.Duration `yaml:"request_timeout" env-default:"5s"`
	// DefaultRealmRoles are given to every created account (FR-RM-53), the roles have to exist in the realm.
	DefaultRealmRoles []string `yaml:"default_realm_roles"`
}

// Admin manages the accounts of employees through the Keycloak Admin REST API (FR-RM-53..58).
// The service token of the provisioner client is cached until it is about to expire.
type Admin struct {
	log      *slog.Logger
	client   *http.Client
	baseURL  string
	realm    string
	clientID string
	secret   string
	roles    []string

	mu        sync.Mutex
	token     string
	expiresAt time.Time
}

func NewAdmin(cfg *Config, log *slog.Logger) (*Admin, error) {
	base, realm, err := cfg.adminTarget()
	if err != nil {
		return nil, err
	}

	if cfg.Provisioner.ClientID == "" {
		return nil, errors.New("provisioner client ID is required")
	}

	if cfg.Provisioner.ClientSecret == "" {
		return nil, errors.New("provisioner client secret is required, set KEYCLOAK_PROVISIONER_SECRET")
	}

	return &Admin{
		log:      log.With(slog.String("keycloak_url", base), slog.String("realm", realm)),
		client:   &http.Client{Timeout: cfg.Provisioner.RequestTimeout},
		baseURL:  base,
		realm:    realm,
		clientID: cfg.Provisioner.ClientID,
		secret:   cfg.Provisioner.ClientSecret,
		roles:    cfg.Provisioner.DefaultRealmRoles,
	}, nil
}

// adminTarget returns the base URL and the realm of the Admin REST API, derived from the JWKS URL unless configured.
func (c *Config) adminTarget() (string, string, error) {
	base, realm := c.Provisioner.BaseURL, c.Provisioner.Realm
	if base != "" && realm != "" {
		return strings.TrimSuffix(base, "/"), realm, nil
	}

	u, err := url.Parse(c.jwksURL())
	if err != nil {
		return "", "", fmt.Errorf("parse JWKS URL: %w", err)
	}

	prefix, rest, ok := strings.Cut(u.Path, "/realms/")
	if !ok {
		return "", "", fmt.Errorf("JWKS URL %q has no realm path, set provisioner base_url and realm", c.jwksURL())
	}

	if base == "" {
		base = u.Scheme + "://" + u.Host + prefix
	}

	if realm == "" {
		realm, _, _ = strings.Cut(rest, "/")
	}

	if realm == "" {
		return "", "", errors.New("provisioner realm is required")
	}

	return strings.TrimSuffix(base, "/"), realm, nil
}

// TemporaryPassword returns a random password for a new account, it is set as temporary,
// so Keycloak asks for a new one at the first login. The service does not keep it (FR-RM-58).
func TemporaryPassword() (string, error) {
	raw := make([]byte, 24)
	if _, err := rand.Read(raw); err != nil {
		return "", fmt.Errorf("generate temporary password: %w", err)
	}

	return base64.RawURLEncoding.EncodeToString(raw), nil
}

// FindByUsername returns the account with the username, or nil when there is none.
func (a *Admin) FindByUsername(ctx context.Context, username string) (*Account, error) {
	status, _, body, err := a.call(ctx, http.MethodGet, "/users", url.Values{"username": {username}, "exact": {"true"}}, nil)
	if err != nil {
		return nil, err
	}

	if status != http.StatusOK {
		return nil, unexpected(http.MethodGet, "/users", status)
	}

	var users []userRepresentation
	if err := json.Unmarshal(body, &users); err != nil {
		return nil, fmt.Errorf("%w: decode users: %w", ErrAccountUnavailable, err)
	}

	for i := range users {
		if strings.EqualFold(users[i].Username, username) {
			return users[i].account(), nil
		}
	}

	return nil, nil
}

// Get returns the account with the identifier.
func (a *Admin) Get(ctx context.Context, id string) (*Account, error) {
	apiPath := "/users/" + url.PathEscape(id)

	status, _, body, err := a.call(ctx, http.MethodGet, apiPath, nil, nil)
	if err != nil {
		return nil, err
	}

	switch status {
	case http.StatusOK:
		var user userRepresentation
		if err := json.Unmarshal(body, &user); err != nil {
			return nil, fmt.Errorf("%w: decode user: %w", ErrAccountUnavailable, err)
		}

		return user.account(), nil
	case http.StatusNotFound:
		return nil, fmt.Errorf("account %s: %w", id, ErrAccountNotFound)
	default:
		return nil, unexpected(http.MethodGet, apiPath, status)
	}
}

// Create creates a disabled account with a temporary password and the default realm roles and returns its identifier.
// The account is enabled by Update once the caller has stored the identifier (FR-RM-53).
func (a *Admin) Create(ctx context.Context, account *Account, temporaryPassword string) (string, error) {
	user := userRepresentation{
		Username:      account.Username,
		Email:         account.Email,
		EmailVerified: true,
		FirstName:     account.FirstName,
		LastName:      account.LastName,
		Enabled:       false,
		Credentials: []credentialRepresentation{
			{Type: "password", Value: temporaryPassword, Temporary: true},
		},
		RequiredActions: []string{"UPDATE_PASSWORD"},
	}

	status, headers, body, err := a.call(ctx, http.MethodPost, "/users", nil, user)
	if err != nil {
		return "", err
	}

	switch status {
	case http.StatusCreated:
	case http.StatusConflict:
		return "", fmt.Errorf("%w: %s", ErrAccountConflict, errorMessage(body, "username or email is taken"))
	default:
		return "", unexpected(http.MethodPost, "/users", status)
	}

	id := path.Base(headers.Get("Location"))
	if id == "" || id == "." || id == "/" {
		return "", fmt.Errorf("%w: created account has no location", ErrAccountUnavailable)
	}

	if err := a.addRealmRoles(ctx, id, a.roles); err != nil {
		return "", err
	}

	a.log.InfoContext(ctx, "keycloak account created", slog.String("account_id", id), slog.String("username", account.Username))

	return id, nil
}

// Update sets the names, the email and the enabled flag of the account (FR-RM-54, FR-RM-57).
func (a *Admin) Update(ctx context.Context, account *Account) error {
	apiPath := "/users/" + url.PathEscape(account.ID)
	user := userRepresentation{
		Username:      account.Username,
		Email:         account.Email,
		EmailVerified: true,
		FirstName:     account.FirstName,
		LastName:      account.LastName,
		Enabled:       account.Enabled,
	}

	status, _, body, err := a.call(ctx, http.MethodPut, apiPath, nil, user)
	if err != nil {
		return err
	}

	switch status {
	case http.StatusNoContent, http.StatusOK:
		a.log.InfoContext(ctx, "keycloak account updated",
			slog.String("account_id", account.ID), slog.String("username", account.Username), slog.Bool("enabled", account.Enabled))

		return nil
	case http.StatusNotFound:
		return fmt.Errorf("account %s: %w", account.ID, ErrAccountNotFound)
	case http.StatusConflict:
		return fmt.Errorf("%w: %s", ErrAccountConflict, errorMessage(body, "username or email is taken"))
	default:
		return unexpected(http.MethodPut, apiPath, status)
	}
}

// addRealmRoles maps the realm roles to the account, a missing role is a configuration error.
func (a *Admin) addRealmRoles(ctx context.Context, id string, roles []string) error {
	if len(roles) == 0 {
		return nil
	}

	representations := make([]roleRepresentation, 0, len(roles))

	for _, name := range roles {
		apiPath := "/roles/" + url.PathEscape(name)

		status, _, body, err := a.call(ctx, http.MethodGet, apiPath, nil, nil)
		if err != nil {
			return err
		}

		if status != http.StatusOK {
			return fmt.Errorf("%w: realm role %q: %s %s answered %d", ErrAccountUnavailable, name, http.MethodGet, apiPath, status)
		}

		var role roleRepresentation
		if err := json.Unmarshal(body, &role); err != nil {
			return fmt.Errorf("%w: decode role: %w", ErrAccountUnavailable, err)
		}

		representations = append(representations, role)
	}

	apiPath := "/users/" + url.PathEscape(id) + "/role-mappings/realm"

	status, _, _, err := a.call(ctx, http.MethodPost, apiPath, nil, representations)
	if err != nil {
		return err
	}

	if status != http.StatusNoContent && status != http.StatusOK {
		return unexpected(http.MethodPost, apiPath, status)
	}

	return nil
}

// call sends one request to the Admin REST API with the service token. A rejected token is renewed once.
// Network errors, timeouts and server errors are reported as ErrAccountUnavailable, the caller handles the other statuses.
func (a *Admin) call(ctx context.Context, method, apiPath string, query url.Values, body any) (int, http.Header, []byte, error) {
	var payload []byte
	if body != nil {
		var err error
		if payload, err = json.Marshal(body); err != nil {
			return 0, nil, nil, fmt.Errorf("encode %s %s: %w", method, apiPath, err)
		}
	}

	target := a.baseURL + "/admin/realms/" + url.PathEscape(a.realm) + apiPath
	if len(query) > 0 {
		target += "?" + query.Encode()
	}

	for attempt := range 2 {
		token, err := a.serviceToken(ctx, attempt > 0)
		if err != nil {
			return 0, nil, nil, err
		}

		req, err := http.NewRequestWithContext(ctx, method, target, bytes.NewReader(payload))
		if err != nil {
			return 0, nil, nil, fmt.Errorf("build %s %s: %w", method, apiPath, err)
		}

		req.Header.Set("Authorization", "Bearer "+token)
		req.Header.Set("Accept", "application/json")
		if body != nil {
			req.Header.Set("Content-Type", "application/json")
		}

		resp, err := a.client.Do(req)
		if err != nil {
			return 0, nil, nil, fmt.Errorf("%w: %s %s: %w", ErrAccountUnavailable, method, apiPath, err)
		}

		data, err := io.ReadAll(io.LimitReader(resp.Body, maxResponseSize))
		_ = resp.Body.Close()
		if err != nil {
			return 0, nil, nil, fmt.Errorf("%w: read %s %s: %w", ErrAccountUnavailable, method, apiPath, err)
		}

		if resp.StatusCode == http.StatusUnauthorized && attempt == 0 {
			continue
		}

		if resp.StatusCode >= http.StatusInternalServerError {
			return 0, nil, nil, unexpected(method, apiPath, resp.StatusCode)
		}

		return resp.StatusCode, resp.Header, data, nil
	}

	return 0, nil, nil, fmt.Errorf("%w: %s %s: service token is rejected", ErrAccountUnavailable, method, apiPath)
}

// serviceToken returns the cached token of the provisioner client, or requests a new one by client credentials.
func (a *Admin) serviceToken(ctx context.Context, renew bool) (string, error) {
	a.mu.Lock()
	defer a.mu.Unlock()

	if !renew && a.token != "" && time.Now().Before(a.expiresAt) {
		return a.token, nil
	}

	form := url.Values{
		"grant_type":    {"client_credentials"},
		"client_id":     {a.clientID},
		"client_secret": {a.secret},
	}

	target := a.baseURL + "/realms/" + url.PathEscape(a.realm) + "/protocol/openid-connect/token"

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, target, strings.NewReader(form.Encode()))
	if err != nil {
		return "", fmt.Errorf("build service token request: %w", err)
	}

	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Accept", "application/json")

	resp, err := a.client.Do(req)
	if err != nil {
		return "", fmt.Errorf("%w: request service token: %w", ErrAccountUnavailable, err)
	}

	data, err := io.ReadAll(io.LimitReader(resp.Body, maxResponseSize))
	_ = resp.Body.Close()
	if err != nil {
		return "", fmt.Errorf("%w: read service token: %w", ErrAccountUnavailable, err)
	}

	if resp.StatusCode != http.StatusOK {
		// the body names the reason (for example a wrong secret) and carries no token, so it is safe to log
		a.log.ErrorContext(ctx, "service token request rejected",
			slog.Int("status", resp.StatusCode), slog.String("response", errorMessage(data, "")))

		return "", fmt.Errorf("%w: service token request answered %d", ErrAccountUnavailable, resp.StatusCode)
	}

	var token struct {
		AccessToken string `json:"access_token"`
		ExpiresIn   int64  `json:"expires_in"`
	}

	if err := json.Unmarshal(data, &token); err != nil || token.AccessToken == "" {
		return "", fmt.Errorf("%w: service token response is malformed", ErrAccountUnavailable)
	}

	a.token = token.AccessToken
	a.expiresAt = time.Now().Add(time.Duration(token.ExpiresIn)*time.Second - tokenRefreshMargin)

	return a.token, nil
}

type userRepresentation struct {
	ID              string                     `json:"id,omitempty"`
	Username        string                     `json:"username"`
	Email           string                     `json:"email"`
	EmailVerified   bool                       `json:"emailVerified"`
	FirstName       string                     `json:"firstName"`
	LastName        string                     `json:"lastName"`
	Enabled         bool                       `json:"enabled"`
	Credentials     []credentialRepresentation `json:"credentials,omitempty"`
	RequiredActions []string                   `json:"requiredActions,omitempty"`
}

func (u *userRepresentation) account() *Account {
	return &Account{
		ID:        u.ID,
		Username:  u.Username,
		Email:     u.Email,
		FirstName: u.FirstName,
		LastName:  u.LastName,
		Enabled:   u.Enabled,
	}
}

type credentialRepresentation struct {
	Type      string `json:"type"`
	Value     string `json:"value"`
	Temporary bool   `json:"temporary"`
}

type roleRepresentation struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

func unexpected(method, apiPath string, status int) error {
	return fmt.Errorf("%w: %s %s answered %d", ErrAccountUnavailable, method, apiPath, status)
}

// errorMessage extracts the message of a Keycloak error response, or returns the fallback.
func errorMessage(body []byte, fallback string) string {
	var e struct {
		ErrorMessage string `json:"errorMessage"`
		Error        string `json:"error"`
		Description  string `json:"error_description"`
	}

	if err := json.Unmarshal(body, &e); err == nil {
		switch {
		case e.ErrorMessage != "":
			return e.ErrorMessage
		case e.Description != "":
			return e.Description
		case e.Error != "":
			return e.Error
		}
	}

	return fallback
}
