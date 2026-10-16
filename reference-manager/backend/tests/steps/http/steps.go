package http

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"slices"
	"strconv"
	"strings"
	"time"

	"github.com/cucumber/godog"
	"github.com/wI2L/jsondiff"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/tests/steps/internal/gherkin"
)

var fileBodyExts = []string{".json"}

type Steps struct {
	baseURL string
	client  *http.Client

	featureURI string

	method  string
	query   url.Values
	headers http.Header
	body    []byte

	response     *http.Response
	responseBody []byte
}

func New(baseURL string, client *http.Client) *Steps {
	if client == nil {
		client = http.DefaultClient
	}

	return &Steps{
		baseURL: strings.TrimSuffix(baseURL, "/"),
		client:  client,
	}
}

func (s *Steps) Register(sc *godog.ScenarioContext) {
	sc.Before(func(ctx context.Context, scenario *godog.Scenario) (context.Context, error) {
		s.reset(scenario.Uri)
		return ctx, nil
	})

	sc.Step(`^a (GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) HTTP request$`, s.aRequest)
	sc.Step(`^the HTTP request contains URL parameters$`, s.requestContainsURLParameters)
	sc.Step(`^the HTTP request contains URL parameter "([^"]*)" from the HTTP response value at "([^"]*)"$`,
		s.requestContainsURLParameterFromResponse)
	sc.Step(`^the HTTP request contains headers$`, s.requestContainsHeaders)
	sc.Step(`^the HTTP request contains a body$`, s.requestContainsBody)
	sc.Step(`^the HTTP request contains a body from file "([^"]*)"$`, s.requestContainsBodyFromFile)
	sc.Step(`^the HTTP request is sent to "([^"]*)"$`, s.requestIsSentTo)
	sc.Step(`^an HTTP response is received with status (\d+)$`, s.responseIsReceivedWithStatus)
	sc.Step(`^the HTTP response contains headers$`, s.responseContainsHeaders)
	sc.Step(`^the HTTP response contains a body$`, s.responseContainsBody)
	sc.Step(`^the HTTP response contains a body from file "([^"]*)"$`, s.responseContainsBodyFromFile)
	sc.Step(`^the HTTP response contains a value at "([^"]*)"$`, s.responseContainsValueAt)
}

func (s *Steps) reset(featureURI string) {
	s.featureURI = featureURI
	s.method = ""
	s.query = url.Values{}
	s.headers = http.Header{}
	s.body = nil
	s.response = nil
	s.responseBody = nil
}

// aRequest starts a new request, the previous response stays available until the new request is sent,
// so that the new request can use values from it.
func (s *Steps) aRequest(method string) error {
	s.method = method
	s.query = url.Values{}
	s.headers = http.Header{}
	s.body = nil

	return nil
}

func (s *Steps) requestContainsURLParameters(params *godog.DocString) error {
	for i, line := range strings.Split(params.Content, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		key, value, ok := strings.Cut(line, "=")
		if !ok {
			return fmt.Errorf("line %d: URL parameter must be in form key=value: %q", i+1, line)
		}

		s.query.Add(strings.TrimSpace(key), strings.TrimSpace(value))
	}

	return nil
}

func (s *Steps) requestContainsURLParameterFromResponse(key, pointer string) error {
	value, err := s.responseValueAt(pointer)
	if err != nil {
		return err
	}

	str, ok := value.(string)
	if !ok {
		return fmt.Errorf("response value at %q is not a string: %v", pointer, value)
	}

	s.query.Add(key, str)

	return nil
}

func (s *Steps) requestContainsHeaders(headers *godog.DocString) error {
	table, err := parseHeaderTable(headers.Content)
	if err != nil {
		return err
	}

	for _, row := range table.Rows {
		s.headers.Add(row[0], row[1])
	}

	return nil
}

func (s *Steps) requestContainsBody(body *godog.DocString) error {
	s.body = []byte(body.Content)
	return nil
}

func (s *Steps) requestContainsBodyFromFile(path string) error {
	body, err := gherkin.ReadFile(s.featureURI, path, fileBodyExts...)
	if err != nil {
		return fmt.Errorf("read request body: %w", err)
	}

	s.body = body

	return nil
}

func (s *Steps) requestIsSentTo(ctx context.Context, path string) error {
	if s.method == "" {
		return fmt.Errorf("HTTP method is not set")
	}

	target, err := url.Parse(s.baseURL + path)
	if err != nil {
		return fmt.Errorf("parse request URL: %w", err)
	}

	query := target.Query()
	for key, values := range s.query {
		for _, value := range values {
			query.Add(key, value)
		}
	}
	target.RawQuery = query.Encode()

	// The service limits the request rate, so a rejected request is sent again after the time it asks to wait.
	for attempt := 1; ; attempt++ {
		resp, respBody, err := s.send(ctx, target.String())
		if err != nil {
			return err
		}

		s.response = resp
		s.responseBody = respBody

		if resp.StatusCode != http.StatusTooManyRequests || attempt == maxRateLimitedAttempts {
			return nil
		}

		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(retryAfter(resp)):
		}
	}
}

// maxRateLimitedAttempts is how many times a request is sent while the service rejects it with 429 Too Many Requests.
const maxRateLimitedAttempts = 5

func (s *Steps) send(ctx context.Context, target string) (*http.Response, []byte, error) {
	var body io.Reader
	if s.body != nil {
		body = bytes.NewReader(s.body)
	}

	req, err := http.NewRequestWithContext(ctx, s.method, target, body)
	if err != nil {
		return nil, nil, fmt.Errorf("create request: %w", err)
	}

	req.Header = s.headers.Clone()
	if s.body != nil && req.Header.Get("Content-Type") == "" && json.Valid(s.body) {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, nil, fmt.Errorf("send request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, nil, fmt.Errorf("read response body: %w", err)
	}

	return resp, respBody, nil
}

// retryAfter returns the delay from the Retry-After header in seconds, one second when it is absent or malformed.
func retryAfter(resp *http.Response) time.Duration {
	seconds, err := strconv.Atoi(resp.Header.Get("Retry-After"))
	if err != nil || seconds <= 0 {
		return time.Second
	}

	return time.Duration(seconds) * time.Second
}

func (s *Steps) responseIsReceivedWithStatus(status int) error {
	if s.response == nil {
		return fmt.Errorf("HTTP request was not sent")
	}

	if s.response.StatusCode != status {
		return fmt.Errorf("expected status %d, got %d, body: %s", status, s.response.StatusCode, s.responseBody)
	}

	return nil
}

func (s *Steps) responseContainsHeaders(headers *godog.DocString) error {
	if s.response == nil {
		return fmt.Errorf("HTTP request was not sent")
	}

	table, err := parseHeaderTable(headers.Content)
	if err != nil {
		return err
	}

	for _, row := range table.Rows {
		name, expected := row[0], row[1]

		actual, ok := s.response.Header[http.CanonicalHeaderKey(name)]
		if !ok {
			return fmt.Errorf("response header %q is missing", name)
		}

		if !slices.Contains(actual, expected) {
			return fmt.Errorf("response header %q: expected %q, got %q", name, expected, actual)
		}
	}

	return nil
}

func (s *Steps) responseContainsBody(body *godog.DocString) error {
	return s.compareResponseBody([]byte(body.Content))
}

func (s *Steps) responseContainsBodyFromFile(path string) error {
	expected, err := gherkin.ReadFile(s.featureURI, path, fileBodyExts...)
	if err != nil {
		return fmt.Errorf("read expected response body: %w", err)
	}

	return s.compareResponseBody(expected)
}

func (s *Steps) compareResponseBody(expected []byte) error {
	if s.response == nil {
		return fmt.Errorf("HTTP request was not sent")
	}

	if !json.Valid(expected) {
		if !bytes.Equal(bytes.TrimSpace(expected), bytes.TrimSpace(s.responseBody)) {
			return fmt.Errorf("response body mismatch:\nexpected: %s\nactual:   %s", expected, s.responseBody)
		}

		return nil
	}

	if !json.Valid(s.responseBody) {
		return fmt.Errorf("response body is not valid JSON: %s", s.responseBody)
	}

	if err := compareJSON(expected, s.responseBody); err != nil {
		return fmt.Errorf("response body mismatch: %w\nactual: %s", err, s.responseBody)
	}

	return nil
}

func (s *Steps) responseContainsValueAt(pointer string, expected *godog.DocString) error {
	value, err := s.responseValueAt(pointer)
	if err != nil {
		return err
	}

	actual, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("encode response value at %q: %w", pointer, err)
	}

	if err := compareJSON([]byte(expected.Content), actual); err != nil {
		return fmt.Errorf("response value at %q mismatch: %w\nactual: %s", pointer, err, actual)
	}

	return nil
}

func (s *Steps) responseValueAt(pointer string) (any, error) {
	if s.response == nil {
		return nil, fmt.Errorf("HTTP request was not sent")
	}

	var doc any
	if err := json.Unmarshal(s.responseBody, &doc); err != nil {
		return nil, fmt.Errorf("response body is not valid JSON: %s", s.responseBody)
	}

	value, err := resolvePointer(doc, pointer)
	if err != nil {
		return nil, fmt.Errorf("response value at %q: %w, body: %s", pointer, err, s.responseBody)
	}

	return value, nil
}

// compareJSON compares JSON documents semantically, AnyValue placeholders in expected match any value.
func compareJSON(expected, actual []byte) error {
	if !json.Valid(expected) {
		return fmt.Errorf("expected value is not valid JSON: %s", expected)
	}

	ignored, err := anyValuePointers(expected, actual)
	if err != nil {
		return err
	}

	patch, err := jsondiff.CompareJSON(expected, actual, jsondiff.Ignores(ignored...))
	if err != nil {
		return fmt.Errorf("compare JSON: %w", err)
	}

	if len(patch) > 0 {
		return fmt.Errorf("diff: %s", patch)
	}

	return nil
}

func parseHeaderTable(content string) (gherkin.Table, error) {
	table, err := gherkin.ParseTable(content)
	if err != nil {
		return gherkin.Table{}, fmt.Errorf("parse headers table: %w", err)
	}

	if len(table.Columns) != 2 {
		return gherkin.Table{}, fmt.Errorf("headers table must have 2 columns (Header, Value), got %d", len(table.Columns))
	}

	return table, nil
}
