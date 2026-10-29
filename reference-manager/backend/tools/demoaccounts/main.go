// Command demoaccounts creates or repeats the Keycloak accounts of every employee through the API of the service.
// It logs in to Keycloak as an HR administrator by the password grant of the local realm and calls SyncAccount
// for every employee, so the employees of the demonstration data set get their accounts (FR-RM-56).
// Run it from backend/ with `go run ./tools/demoaccounts` after `task up` and `task demo:data`.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

type employee struct {
	ID            int64   `json:"id"`
	Username      string  `json:"username"`
	AccountState  string  `json:"account_state"`
	AccountUserID *string `json:"account_user_id"`
}

type page struct {
	Employees     []employee `json:"employees"`
	NextPageToken string     `json:"nextPageToken"`
}

type apiError struct {
	Message string `json:"message"`
}

func main() {
	api := flag.String("api", "http://localhost:8080", "address of the service")
	keycloakURL := flag.String("keycloak", "http://localhost:8180", "address of Keycloak")
	realm := flag.String("realm", "arch-info-system", "realm of the users")
	clientID := flag.String("client", "reference-manager-ui", "public client with the password grant enabled")
	user := flag.String("user", "hr-admin", "HR administrator, the password is read from DEMO_PASSWORD, by default it equals the user")
	flag.Parse()

	password := os.Getenv("DEMO_PASSWORD")
	if password == "" {
		password = *user
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	client := &http.Client{Timeout: 30 * time.Second}

	token, err := login(ctx, client, *keycloakURL, *realm, *clientID, *user, password)
	if err != nil {
		fail("login as %s: %v", *user, err)
	}

	employees, err := listEmployees(ctx, client, *api, token)
	if err != nil {
		fail("list employees: %v", err)
	}

	fmt.Printf("%-4s %-16s %-9s %s\n", "id", "username", "account", "account_user_id")

	failed := 0

	for _, e := range employees {
		synced, err := syncAccount(ctx, client, *api, token, e.ID)
		if err != nil {
			failed++
			fmt.Printf("%-4d %-16s %-9s %v\n", e.ID, e.Username, "ERROR", err)

			continue
		}

		id := ""
		if synced.AccountUserID != nil {
			id = *synced.AccountUserID
		}

		fmt.Printf("%-4d %-16s %-9s %s\n", synced.ID, synced.Username, synced.AccountState, id)
	}

	if failed > 0 {
		fail("%d of %d accounts are pending, repeat the command once Keycloak is reachable", failed, len(employees))
	}
}

func fail(format string, args ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
	os.Exit(1)
}

// login gets an access token by the password grant, the token stays in memory.
func login(ctx context.Context, client *http.Client, keycloakURL, realm, clientID, user, password string) (string, error) {
	form := url.Values{
		"grant_type": {"password"},
		"client_id":  {clientID},
		"username":   {user},
		"password":   {password},
		"scope":      {"openid"},
	}

	target := strings.TrimSuffix(keycloakURL, "/") + "/realms/" + url.PathEscape(realm) + "/protocol/openid-connect/token"

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, target, strings.NewReader(form.Encode()))
	if err != nil {
		return "", err
	}

	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return "", err
	}

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("token endpoint answered %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}

	var token struct {
		AccessToken string `json:"access_token"`
	}

	if err := json.Unmarshal(body, &token); err != nil || token.AccessToken == "" {
		return "", errors.New("token response is malformed")
	}

	return token.AccessToken, nil
}

func listEmployees(ctx context.Context, client *http.Client, api, token string) ([]employee, error) {
	var all []employee

	pageToken := ""

	for {
		query := url.Values{"pageSize": {"100"}, "allowDeleted": {"false"}}
		if pageToken != "" {
			query.Set("pageToken", pageToken)
		}

		var p page
		if err := call(ctx, client, http.MethodGet, api+"/v1/employees/?"+query.Encode(), token, &p); err != nil {
			return nil, err
		}

		all = append(all, p.Employees...)

		if p.NextPageToken == "" {
			return all, nil
		}

		pageToken = p.NextPageToken
	}
}

func syncAccount(ctx context.Context, client *http.Client, api, token string, id int64) (*employee, error) {
	var synced employee
	if err := call(ctx, client, http.MethodPost, fmt.Sprintf("%s/v1/employees/%d/syncAccount", api, id), token, &synced); err != nil {
		return nil, err
	}

	return &synced, nil
}

func call(ctx context.Context, client *http.Client, method, target, token string, out any) error {
	req, err := http.NewRequestWithContext(ctx, method, target, nil)
	if err != nil {
		return err
	}

	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Accept", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(io.LimitReader(resp.Body, 8<<20))
	if err != nil {
		return err
	}

	if resp.StatusCode/100 != 2 {
		var apiErr apiError
		if json.Unmarshal(body, &apiErr) == nil && apiErr.Message != "" {
			return fmt.Errorf("%d: %s", resp.StatusCode, apiErr.Message)
		}

		return fmt.Errorf("%d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}

	return json.Unmarshal(body, out)
}
