// Package keycloaksteps checks and prepares the accounts of the realm through the Keycloak Admin REST API
// under the bootstrap administrator of the test environment.
package keycloaksteps

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	"github.com/cucumber/godog"
)

const tokenRefreshMargin = 30 * time.Second

type Steps struct {
	baseURL  string
	realm    string
	admin    string
	password string
	client   *http.Client

	mu        sync.Mutex
	token     string
	expiresAt time.Time
}

func New(keycloakURL, realm, admin, password string, client *http.Client) *Steps {
	if client == nil {
		client = http.DefaultClient
	}

	return &Steps{
		baseURL:  strings.TrimSuffix(keycloakURL, "/"),
		realm:    realm,
		admin:    admin,
		password: password,
		client:   client,
	}
}

func (s *Steps) Register(sc *godog.ScenarioContext) {
	sc.Step(`^the Keycloak account "([^"]*)" is (enabled|disabled|missing)$`, s.accountIs)
	sc.Step(`^the Keycloak account "([^"]*)" has email "([^"]*)"$`, s.accountHasEmail)
	sc.Step(`^the Keycloak account "([^"]*)" has the realm role "([^"]*)"$`, s.accountHasRealmRole)
	sc.Step(`^the Keycloak account "([^"]*)" is removed$`, s.accountIsRemoved)
	sc.Step(`^a Keycloak account "([^"]*)" exists with email "([^"]*)"$`, s.accountExistsWithEmail)
}

type user struct {
	ID       string `json:"id"`
	Username string `json:"username"`
	Email    string `json:"email"`
	Enabled  bool   `json:"enabled"`
}

func (s *Steps) accountIs(ctx context.Context, username, state string) error {
	u, err := s.find(ctx, username)
	if err != nil {
		return err
	}

	switch state {
	case "missing":
		if u != nil {
			return fmt.Errorf("account %q exists", username)
		}
	case "enabled", "disabled":
		if u == nil {
			return fmt.Errorf("account %q does not exist", username)
		}

		if u.Enabled != (state == "enabled") {
			return fmt.Errorf("account %q is not %s", username, state)
		}
	}

	return nil
}

func (s *Steps) accountHasEmail(ctx context.Context, username, email string) error {
	u, err := s.find(ctx, username)
	if err != nil {
		return err
	}

	if u == nil {
		return fmt.Errorf("account %q does not exist", username)
	}

	if !strings.EqualFold(u.Email, email) {
		return fmt.Errorf("account %q has email %q, expected %q", username, u.Email, email)
	}

	return nil
}

func (s *Steps) accountHasRealmRole(ctx context.Context, username, role string) error {
	u, err := s.find(ctx, username)
	if err != nil {
		return err
	}

	if u == nil {
		return fmt.Errorf("account %q does not exist", username)
	}

	var roles []struct {
		Name string `json:"name"`
	}

	status, body, err := s.call(ctx, http.MethodGet, "/users/"+url.PathEscape(u.ID)+"/role-mappings/realm", nil)
	if err != nil {
		return err
	}

	if status != http.StatusOK {
		return fmt.Errorf("role mappings of %q answered %d", username, status)
	}

	if err := json.Unmarshal(body, &roles); err != nil {
		return fmt.Errorf("decode role mappings: %w", err)
	}

	for _, r := range roles {
		if r.Name == role {
			return nil
		}
	}

	return fmt.Errorf("account %q has no realm role %q", username, role)
}

func (s *Steps) accountIsRemoved(ctx context.Context, username string) error {
	u, err := s.find(ctx, username)
	if err != nil || u == nil {
		return err
	}

	status, _, err := s.call(ctx, http.MethodDelete, "/users/"+url.PathEscape(u.ID), nil)
	if err != nil {
		return err
	}

	if status != http.StatusNoContent {
		return fmt.Errorf("delete account %q answered %d", username, status)
	}

	return nil
}

func (s *Steps) accountExistsWithEmail(ctx context.Context, username, email string) error {
	if err := s.accountIsRemoved(ctx, username); err != nil {
		return err
	}

	status, body, err := s.call(ctx, http.MethodPost, "/users", map[string]any{
		"username": username, "email": email, "emailVerified": true, "enabled": false,
		"firstName": "Test", "lastName": "Account",
	})
	if err != nil {
		return err
	}

	if status != http.StatusCreated {
		return fmt.Errorf("create account %q answered %d: %s", username, status, body)
	}

	return nil
}

func (s *Steps) find(ctx context.Context, username string) (*user, error) {
	query := url.Values{"username": {username}, "exact": {"true"}}

	status, body, err := s.call(ctx, http.MethodGet, "/users?"+query.Encode(), nil)
	if err != nil {
		return nil, err
	}

	if status != http.StatusOK {
		return nil, fmt.Errorf("search account %q answered %d", username, status)
	}

	var users []user
	if err := json.Unmarshal(body, &users); err != nil {
		return nil, fmt.Errorf("decode accounts: %w", err)
	}

	for i := range users {
		if strings.EqualFold(users[i].Username, username) {
			return &users[i], nil
		}
	}

	return nil, nil
}

func (s *Steps) call(ctx context.Context, method, path string, body any) (int, []byte, error) {
	token, err := s.adminToken(ctx)
	if err != nil {
		return 0, nil, err
	}

	var payload []byte
	if body != nil {
		if payload, err = json.Marshal(body); err != nil {
			return 0, nil, err
		}
	}

	req, err := http.NewRequestWithContext(ctx, method, s.baseURL+"/admin/realms/"+url.PathEscape(s.realm)+path, bytes.NewReader(payload))
	if err != nil {
		return 0, nil, err
	}

	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := s.client.Do(req)
	if err != nil {
		return 0, nil, fmt.Errorf("%s %s: %w", method, path, err)
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return 0, nil, err
	}

	return resp.StatusCode, data, nil
}

// adminToken logs the bootstrap administrator in to the master realm by the password grant of admin-cli.
func (s *Steps) adminToken(ctx context.Context) (string, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.token != "" && time.Now().Before(s.expiresAt) {
		return s.token, nil
	}

	form := url.Values{
		"grant_type": {"password"},
		"client_id":  {"admin-cli"},
		"username":   {s.admin},
		"password":   {s.password},
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.baseURL+"/realms/master/protocol/openid-connect/token", strings.NewReader(form.Encode()))
	if err != nil {
		return "", err
	}

	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := s.client.Do(req)
	if err != nil {
		return "", fmt.Errorf("admin token: %w", err)
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return "", err
	}

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("admin token answered %d", resp.StatusCode)
	}

	var token struct {
		AccessToken string `json:"access_token"`
		ExpiresIn   int64  `json:"expires_in"`
	}

	if err := json.Unmarshal(data, &token); err != nil || token.AccessToken == "" {
		return "", fmt.Errorf("admin token response is malformed")
	}

	s.token = token.AccessToken
	s.expiresAt = time.Now().Add(time.Duration(token.ExpiresIn)*time.Second - tokenRefreshMargin)

	return s.token, nil
}
