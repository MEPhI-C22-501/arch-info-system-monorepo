package currencyrepo_test

import (
	"os"
	"path/filepath"
	"testing"
)

func readQuery(t *testing.T, name string) string {
	t.Helper()

	query, err := os.ReadFile(filepath.Join("sql", name))
	if err != nil {
		t.Fatalf("read query %s: %v", name, err)
	}

	return string(query)
}
