// Command gencatalog renders the OpenAPI specification, the domain package, the HTTP handler and the migration
// of every catalog defined in defs.go. Run it from backend/ with `go run ./tools/gencatalog`, then `task generate`
// for the API code. Generated files carry a "DO NOT EDIT" header, catalog rules and custom methods are written by hand
// next to them.
package main

import (
	"bytes"
	"embed"
	"flag"
	"fmt"
	"go/format"
	"log"
	"os"
	"path/filepath"
	"strings"
	"text/template"
)

//go:embed templates/*.tmpl
var templateFS embed.FS

type output struct {
	path     string
	template string
	goSource bool
	data     any
}

func main() {
	backend := flag.String("backend", ".", "path to the backend directory")
	migrations := flag.String("migrations", "../deployments/migrations", "path to the migrations directory")
	flag.Parse()

	templates, err := template.New("").Funcs(template.FuncMap{
		"indent": indent,
		"join":   strings.Join,
		"lower":  strings.ToLower,
	}).ParseFS(templateFS, "templates/*.tmpl")
	if err != nil {
		log.Fatalf("parse templates: %v", err)
	}

	for _, c := range Catalogs {
		v := newCatalogView(c)

		outputs := []output{
			{path: filepath.Join(*backend, "api/openapi/v1", c.Singular, "openapi.yaml"), template: "openapi.yaml.tmpl", data: v},
			{path: filepath.Join(*backend, "api/openapi/v1", c.Singular, "codegen.server.yaml"), template: "codegen.yaml.tmpl", data: codegen{v, "server"}},
			{path: filepath.Join(*backend, "api/openapi/v1", c.Singular, "codegen.models.yaml"), template: "codegen.yaml.tmpl", data: codegen{v, "models"}},
			{path: filepath.Join(*backend, "api/openapi/v1", c.Singular, "codegen.client.yaml"), template: "codegen.yaml.tmpl", data: codegen{v, "client"}},
			{path: filepath.Join(*backend, "internal/domains", c.Singular, c.Singular+".gen.go"), template: "domain.go.tmpl", goSource: true, data: v},
			{path: filepath.Join(*backend, "internal/transport/http/server/v1", c.Singular, "handler.gen.go"), template: "handler.go.tmpl", goSource: true, data: v},
			{path: filepath.Join(*migrations, v.Migration+"_create_"+c.Singular+"_database_objects.up.sql"), template: "migration_up.sql.tmpl", data: v},
			{path: filepath.Join(*migrations, v.Migration+"_create_"+c.Singular+"_database_objects.down.sql"), template: "migration_down.sql.tmpl", data: v},
		}

		for _, o := range outputs {
			if err := render(templates, o); err != nil {
				log.Fatalf("%s: %v", o.path, err)
			}
		}

		fmt.Printf("generated %s\n", c.Plural)
	}
}

type codegen struct {
	catalogView
	Target string
}

func render(templates *template.Template, o output) error {
	var buf bytes.Buffer
	if err := templates.ExecuteTemplate(&buf, o.template, o.data); err != nil {
		return fmt.Errorf("execute template: %w", err)
	}

	content := buf.Bytes()
	if o.goSource {
		formatted, err := format.Source(content)
		if err != nil {
			return fmt.Errorf("format source: %w\n%s", err, content)
		}
		content = formatted
	}

	if err := os.MkdirAll(filepath.Dir(o.path), 0o755); err != nil {
		return fmt.Errorf("create directory: %w", err)
	}

	return os.WriteFile(o.path, content, 0o644)
}
