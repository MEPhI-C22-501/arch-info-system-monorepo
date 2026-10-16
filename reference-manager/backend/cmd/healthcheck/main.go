// Command healthcheck probes an HTTP endpoint of the service and exits with a non-zero code if it is not healthy.
// The runtime image has no shell or curl, so it is used as the Docker healthcheck of the service.
package main

import (
	"context"
	"flag"
	"fmt"
	"net/http"
	"os"
	"time"
)

func main() {
	var (
		url     string
		timeout time.Duration
	)

	flag.StringVar(&url, "url", "http://127.0.0.1:8080/v1/health/readyz", "endpoint to probe, any 2xx response is considered healthy")
	flag.DurationVar(&timeout, "timeout", 3*time.Second, "timeout of the probe request")
	flag.Parse()

	if err := probe(url, timeout); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func probe(url string, timeout time.Duration) error {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, http.NoBody)
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fmt.Errorf("probe %s: %w", url, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		return fmt.Errorf("probe %s: unexpected status %s", url, resp.Status)
	}

	return nil
}
