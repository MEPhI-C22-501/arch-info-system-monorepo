package sql

import (
	"context"
	"encoding/csv"
	"fmt"
	"slices"
	"strings"

	"github.com/cucumber/godog"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/tests/steps/internal/gherkin"
)

// migrationsTable is kept on truncation, it holds the schema version applied by migrate.
const migrationsTable = "schema_migrations"

// NullValue is how SQL NULL is represented in expected tables and CSV files.
const NullValue = "NULL"

type Steps struct {
	pool *pgxpool.Pool

	featureURI string

	executed bool
	result   gherkin.Table
}

func New(pool *pgxpool.Pool) *Steps {
	return &Steps{pool: pool}
}

func (s *Steps) Register(sc *godog.ScenarioContext) {
	sc.Before(func(ctx context.Context, scenario *godog.Scenario) (context.Context, error) {
		s.featureURI = scenario.Uri
		s.executed = false
		s.result = gherkin.Table{}

		if err := s.truncateTables(ctx); err != nil {
			return ctx, fmt.Errorf("isolate scenario: %w", err)
		}

		return ctx, nil
	})

	sc.Step(`^the SQL query is executed$`, s.queryIsExecuted)
	sc.Step(`^the SQL query from file "([^"]*)" is executed$`, s.queryFromFileIsExecuted)
	sc.Step(`^the query result is received$`, s.queryResultIsReceived)
	sc.Step(`^the query result matches file "([^"]*)"$`, s.queryResultMatchesFile)
}

func (s *Steps) queryIsExecuted(ctx context.Context, query *godog.DocString) error {
	return s.execute(ctx, query.Content)
}

func (s *Steps) queryFromFileIsExecuted(ctx context.Context, path string) error {
	query, err := gherkin.ReadFile(s.featureURI, path, ".sql")
	if err != nil {
		return fmt.Errorf("read SQL query: %w", err)
	}

	return s.execute(ctx, string(query))
}

func (s *Steps) queryResultIsReceived(expected *godog.DocString) error {
	table, err := gherkin.ParseTable(expected.Content)
	if err != nil {
		return fmt.Errorf("parse expected result: %w", err)
	}

	return s.compareResult(table)
}

func (s *Steps) queryResultMatchesFile(path string) error {
	content, err := gherkin.ReadFile(s.featureURI, path, ".csv")
	if err != nil {
		return fmt.Errorf("read expected result: %w", err)
	}

	records, err := csv.NewReader(strings.NewReader(string(content))).ReadAll()
	if err != nil {
		return fmt.Errorf("parse CSV %q: %w", path, err)
	}

	if len(records) == 0 {
		return fmt.Errorf("CSV %q has no header", path)
	}

	return s.compareResult(gherkin.Table{Columns: records[0], Rows: records[1:]})
}

// truncateTables isolates scenarios from each other: every scenario starts with
// empty tables and identity sequences restarted, so generated IDs are predictable.
func (s *Steps) truncateTables(ctx context.Context) error {
	rows, err := s.pool.Query(ctx, `
		SELECT format('%I.%I', schemaname, tablename)
		FROM pg_tables
		WHERE schemaname = current_schema() AND tablename <> $1`,
		migrationsTable,
	)
	if err != nil {
		return fmt.Errorf("list tables: %w", err)
	}

	tables, err := pgx.CollectRows(rows, pgx.RowTo[string])
	if err != nil {
		return fmt.Errorf("list tables: %w", err)
	}

	if len(tables) == 0 {
		return nil
	}

	if _, err := s.pool.Exec(ctx, "TRUNCATE "+strings.Join(tables, ", ")+" RESTART IDENTITY CASCADE"); err != nil {
		return fmt.Errorf("truncate tables: %w", err)
	}

	return nil
}

// execute runs the query using the simple protocol so that values are returned
// in PostgreSQL text format and can be compared as strings.
func (s *Steps) execute(ctx context.Context, query string) error {
	rows, err := s.pool.Query(ctx, query, pgx.QueryExecModeSimpleProtocol)
	if err != nil {
		return fmt.Errorf("execute query: %w", err)
	}
	defer rows.Close()

	var result gherkin.Table
	for _, field := range rows.FieldDescriptions() {
		result.Columns = append(result.Columns, field.Name)
	}

	for rows.Next() {
		raw := rows.RawValues()

		row := make([]string, len(raw))
		for i, value := range raw {
			if value == nil {
				row[i] = NullValue
				continue
			}
			row[i] = string(value)
		}

		result.Rows = append(result.Rows, row)
	}

	if err := rows.Err(); err != nil {
		return fmt.Errorf("execute query: %w", err)
	}

	s.executed = true
	s.result = result

	return nil
}

// compareResult checks that the result has the expected rows in the same order.
// Only columns listed in expected are compared.
func (s *Steps) compareResult(expected gherkin.Table) error {
	if !s.executed {
		return fmt.Errorf("SQL query was not executed")
	}

	indexes := make([]int, len(expected.Columns))
	for i, column := range expected.Columns {
		indexes[i] = slices.Index(s.result.Columns, column)
		if indexes[i] < 0 {
			return fmt.Errorf("column %q is missing in query result, got columns %v", column, s.result.Columns)
		}
	}

	if len(expected.Rows) != len(s.result.Rows) {
		return fmt.Errorf("expected %d rows, got %d:\n%s", len(expected.Rows), len(s.result.Rows), formatTable(s.result))
	}

	for i, expectedRow := range expected.Rows {
		if len(expectedRow) != len(expected.Columns) {
			return fmt.Errorf("expected row %d: expected %d cells, got %d", i+1, len(expected.Columns), len(expectedRow))
		}

		for j, expectedValue := range expectedRow {
			actual := s.result.Rows[i][indexes[j]]
			if actual != expectedValue {
				return fmt.Errorf("row %d, column %q: expected %q, got %q:\n%s",
					i+1, expected.Columns[j], expectedValue, actual, formatTable(s.result))
			}
		}
	}

	return nil
}

func formatTable(table gherkin.Table) string {
	var b strings.Builder

	writeRow := func(cells []string) {
		b.WriteString("| " + strings.Join(cells, " | ") + " |\n")
	}

	writeRow(table.Columns)
	for _, row := range table.Rows {
		writeRow(row)
	}

	return b.String()
}
