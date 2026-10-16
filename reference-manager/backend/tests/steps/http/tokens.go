package http

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

// tokenRefreshMargin is how long before its expiration a cached token is replaced by a new one.
const tokenRefreshMargin = 30 * time.Second

// Tokens gets access tokens of the realm users from Keycloak by the password grant
// and caches them until they are about to expire. The password of a test user is its username.
type Tokens struct {
	tokenURL string
	client   *http.Client

	mu    sync.Mutex
	cache map[tokenKey]cachedToken
}

type tokenKey struct {
	username string
	clientID string
}

type cachedToken struct {
	value     string
	expiresAt time.Time
}

func NewTokens(keycloakURL, realm string, client *http.Client) *Tokens {
	if client == nil {
		client = http.DefaultClient
	}

	return &Tokens{
		tokenURL: strings.TrimSuffix(keycloakURL, "/") + "/realms/" + url.PathEscape(realm) + "/protocol/openid-connect/token",
		client:   client,
		cache:    make(map[tokenKey]cachedToken),
	}
}

// Token returns an access token of the user issued to the client.
func (t *Tokens) Token(ctx context.Context, username, clientID string) (string, error) {
	key := tokenKey{username: username, clientID: clientID}

	t.mu.Lock()
	defer t.mu.Unlock()

	if cached, ok := t.cache[key]; ok && time.Now().Before(cached.expiresAt) {
		return cached.value, nil
	}

	token, err := t.request(ctx, username, clientID)
	if err != nil {
		return "", err
	}

	t.cache[key] = token

	return token.value, nil
}

func (t *Tokens) request(ctx context.Context, username, clientID string) (cachedToken, error) {
	form := url.Values{
		"grant_type": {"password"},
		"client_id":  {clientID},
		"username":   {username},
		"password":   {username},
		"scope":      {"openid"},
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, t.tokenURL, strings.NewReader(form.Encode()))
	if err != nil {
		return cachedToken{}, fmt.Errorf("create token request: %w", err)
	}

	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	requested := time.Now()

	resp, err := t.client.Do(req)
	if err != nil {
		return cachedToken{}, fmt.Errorf("request token of %q: %w", username, err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return cachedToken{}, fmt.Errorf("read token response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return cachedToken{}, fmt.Errorf("request token of %q: status %d: %s", username, resp.StatusCode, body)
	}

	var token struct {
		AccessToken string `json:"access_token"`
		ExpiresIn   int    `json:"expires_in"`
	}
	if err := json.Unmarshal(body, &token); err != nil {
		return cachedToken{}, fmt.Errorf("decode token response: %w", err)
	}

	return cachedToken{
		value:     token.AccessToken,
		expiresAt: requested.Add(time.Duration(token.ExpiresIn)*time.Second - tokenRefreshMargin),
	}, nil
}
