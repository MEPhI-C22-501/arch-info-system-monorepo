package gherkin

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

type Table struct {
	Columns []string
	Rows    [][]string
}

// ParseTable parses a markdown-like table from a doc string:
//
//	| id | name |
//	| 1  | foo  |
//
// Rows with all cells empty are treated as placeholders and skipped.
func ParseTable(content string) (Table, error) {
	var table Table

	for i, line := range strings.Split(content, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		if !strings.HasPrefix(line, "|") || !strings.HasSuffix(line, "|") || len(line) < 2 {
			return Table{}, fmt.Errorf("line %d: table row must start and end with '|': %q", i+1, line)
		}

		cells := strings.Split(line[1:len(line)-1], "|")
		for j := range cells {
			cells[j] = strings.TrimSpace(cells[j])
		}

		if table.Columns == nil {
			table.Columns = cells
			continue
		}

		if len(cells) != len(table.Columns) {
			return Table{}, fmt.Errorf("line %d: expected %d cells, got %d", i+1, len(table.Columns), len(cells))
		}

		if isEmptyRow(cells) {
			continue
		}

		table.Rows = append(table.Rows, cells)
	}

	if table.Columns == nil {
		return Table{}, fmt.Errorf("table has no header")
	}

	return table, nil
}

func isEmptyRow(cells []string) bool {
	for _, cell := range cells {
		if cell != "" {
			return false
		}
	}

	return true
}

// ResolvePath resolves path relative to the directory of the feature file.
// A leading slash is treated as the feature directory root, not the filesystem root.
// If the file does not exist and has no extension, fallback extensions are tried in order.
func ResolvePath(featureURI, path string, fallbackExts ...string) (string, error) {
	resolved := filepath.Join(filepath.Dir(featureURI), strings.TrimPrefix(path, "/"))

	if _, err := os.Stat(resolved); err == nil {
		return resolved, nil
	}

	if filepath.Ext(resolved) == "" {
		for _, ext := range fallbackExts {
			if _, err := os.Stat(resolved + ext); err == nil {
				return resolved + ext, nil
			}
		}
	}

	return "", fmt.Errorf("file %q not found (resolved to %q)", path, resolved)
}

func ReadFile(featureURI, path string, fallbackExts ...string) ([]byte, error) {
	resolved, err := ResolvePath(featureURI, path, fallbackExts...)
	if err != nil {
		return nil, err
	}

	return os.ReadFile(resolved)
}
