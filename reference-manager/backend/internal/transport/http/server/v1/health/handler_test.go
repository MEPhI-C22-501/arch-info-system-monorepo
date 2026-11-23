package health

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"

	healthv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/health"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/ready"
)

func readiness(t *testing.T, check func(ctx context.Context) error) (int, healthv1.Readiness) {
	t.Helper()

	manager := ready.NewManager(slog.New(slog.DiscardHandler), ready.NewCheck("postgres", check))
	recorder := httptest.NewRecorder()
	NewHandler(manager).GetReadiness(recorder, httptest.NewRequest(http.MethodGet, "/v1/health/readyz", nil))

	var body healthv1.Readiness
	if err := json.Unmarshal(recorder.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode readiness %q: %v", recorder.Body.String(), err)
	}

	return recorder.Code, body
}

// TestReadinessReportsTheDatabaseDown covers the quality scenario "database unavailable" of 075:
// readyz answers 503 and names the failed dependency, so the orchestrator takes the instance out of traffic.
func TestReadinessReportsTheDatabaseDown(t *testing.T) {
	t.Parallel()

	status, body := readiness(t, func(context.Context) error { return errors.New("dial tcp: connection refused") })

	if status != http.StatusServiceUnavailable || body.Ready {
		t.Fatalf("expected 503 and not ready, got %d ready=%v", status, body.Ready)
	}

	if len(body.FailedDependencies) != 1 || body.FailedDependencies[0].Name != "postgres" {
		t.Fatalf("expected the failed dependency postgres, got %+v", body.FailedDependencies)
	}
}

func TestReadinessWhenTheDatabaseAnswers(t *testing.T) {
	t.Parallel()

	status, body := readiness(t, func(context.Context) error { return nil })

	if status != http.StatusOK || !body.Ready || len(body.FailedDependencies) != 0 {
		t.Fatalf("expected 200 and ready, got %d %+v", status, body)
	}
}
