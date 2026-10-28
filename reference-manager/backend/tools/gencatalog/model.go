package main

import (
	"fmt"
	"strconv"
	"strings"
)

// fieldView is a field with every string the templates need precomputed.
type fieldView struct {
	Name        string
	GoName      string
	APIName     string
	GoType      string
	Description string
	Example     string

	Input       bool
	RequiredIn  bool
	RequiredOut bool
	Stored      bool
	Updatable   bool
	Computed    string
	IsDate      bool
	IsEnum      bool
	GoDefault   string

	SchemaYAML string
	SQLColumn  string
	FilterType string
	SQLExpr    string
	Rules      string
	FromAPI    string
	ToAPI      string
	ExportName string
}

// catalogView is a catalog with every string the templates need precomputed.
type catalogView struct {
	Catalog

	Package     string
	DomainPkg   string
	HandlerPkg  string
	PathParam   string
	ParamType   string
	PluralTitle string
	GroupIdent  string
	Fields      []fieldView
	Enums       []enumView
	NeedsTime   bool
	NeedsDate   bool
	NeedsRegexp bool
	UniqueNames []string
	RefNames    []string
	Migration   string
	ReadRoles   string
	WriteRoles  string
	// ConstraintsSQL are the extra constraints with the plural name substituted.
	ConstraintsSQL []string
}

type enumView struct {
	Name        string
	Values      []string
	Description string
}

func newCatalogView(c Catalog) catalogView {
	compact := strings.ReplaceAll(c.Singular, "_", "")
	v := catalogView{
		Catalog:     c,
		Package:     compact + "v1",
		DomainPkg:   compact + "dmn",
		HandlerPkg:  compact + "hndl",
		PathParam:   lowerFirst(c.Title) + "ID",
		ParamType:   c.Title + "ID",
		PluralTitle: camel(c.Plural, false),
		GroupIdent:  c.Group,
		Migration:   fmt.Sprintf("%06d", c.Migration),
	}
	v.ReadRoles, v.WriteRoles = roles(c.Group)
	for _, constraint := range c.Constraints {
		if strings.Contains(constraint, "%") {
			constraint = fmt.Sprintf(constraint, c.Plural)
		}
		v.ConstraintsSQL = append(v.ConstraintsSQL, constraint)
	}

	for _, f := range c.Fields {
		fv := newFieldView(f, v.Package)
		v.Fields = append(v.Fields, fv)

		if f.Kind == KindDate {
			v.NeedsTime = true
			v.NeedsDate = true
		}
		if f.Pattern != "" {
			v.NeedsRegexp = true
		}
		if f.Unique {
			v.UniqueNames = append(v.UniqueNames, f.Name)
		}
		if f.Kind == KindRef && f.Computed == "" {
			v.RefNames = append(v.RefNames, f.Name)
		}
		if f.Kind == KindEnum {
			v.Enums = append(v.Enums, enumView{Name: f.EnumName, Values: f.Enum, Description: f.Description})
		}
	}

	return v
}

func newFieldView(f Field, apiPkg string) fieldView {
	optional := !f.Required
	v := fieldView{
		Name:        f.Name,
		GoName:      camel(f.Name, true),
		APIName:     camel(f.Name, false),
		Description: f.Description,
		Example:     f.Example,
		Input:       !f.ServerManaged && f.Computed == "",
		RequiredIn:  f.Required && !f.ServerManaged && f.Computed == "",
		RequiredOut: f.Required,
		Stored:      f.Computed == "",
		Updatable:   !f.Immutable && !f.ServerManaged && f.Computed == "",
		Computed:    f.Computed,
		IsDate:      f.Kind == KindDate,
		IsEnum:      f.Kind == KindEnum,
		ExportName:  humanize(f.Name),
		GoDefault:   f.GoDefault,
	}

	var (
		goType, apiType, filterType string
		schema                      []string
	)

	switch f.Kind {
	case KindString:
		goType, apiType, filterType = "string", "string", "filtering.TypeString"
		schema = append(schema, "type: string")
		if f.MinLen > 0 {
			schema = append(schema, "minLength: "+strconv.Itoa(f.MinLen))
		}
		if f.MaxLen > 0 {
			schema = append(schema, "maxLength: "+strconv.Itoa(f.MaxLen))
		}
		if f.Pattern != "" {
			schema = append(schema, "pattern: '"+f.Pattern+"'")
		}
	case KindEnum:
		goType, apiType, filterType = "string", apiPkg+"."+f.EnumName, "filtering.TypeString"
		schema = append(schema, "$ref: '#/components/schemas/"+f.EnumName+"'")
	case KindInt:
		goType, apiType, filterType = "int32", "int32", "filtering.TypeInt"
		schema = append(schema, "type: integer", "format: int32")
		if f.Min != nil {
			schema = append(schema, "minimum: "+formatFloat(*f.Min))
		}
		if f.Max != nil {
			schema = append(schema, "maximum: "+formatFloat(*f.Max))
		}
	case KindRef:
		goType, apiType, filterType = "int64", "int64", "filtering.TypeInt"
		schema = append(schema, "type: integer", "format: int64", "minimum: 1")
	case KindDate:
		goType, apiType, filterType = "time.Time", "openapi_types.Date", "filtering.TypeString"
		v.SQLExpr = f.Name + "::text"
		schema = append(schema, "type: string", "format: date")
	case KindMoney:
		goType, apiType, filterType = "float64", "float64", "filtering.TypeFloat"
		schema = append(schema, "type: number", "format: double")
		if f.Min != nil {
			schema = append(schema, "minimum: "+formatFloat(*f.Min))
		}
	case KindBool:
		goType, apiType, filterType = "bool", "bool", "filtering.TypeBool"
		schema = append(schema, "type: boolean")
	}

	if optional {
		goType = "*" + goType
		apiType = "*" + apiType
	}

	description := f.Description
	if f.ServerManaged || f.Computed != "" {
		description = strings.TrimSpace(description + " Read-only, set by the service.")
	}
	if description != "" && f.Kind != KindEnum {
		schema = append(schema, "description: "+yamlString(description))
	}
	if f.Example != "" && f.Kind != KindEnum {
		schema = append(schema, "example: "+yamlExample(f))
	}

	v.GoType = goType
	v.FilterType = filterType
	v.SchemaYAML = strings.Join(schema, "\n")
	v.SQLColumn = sqlColumn(f)
	v.Rules = rulesLiteral(f)
	v.FromAPI, v.ToAPI = conversions(f, v, apiType)

	return v
}

func sqlColumn(f Field) string {
	var column string

	switch f.Kind {
	case KindString:
		if f.MaxLen > 0 {
			column = "VARCHAR(" + strconv.Itoa(f.MaxLen) + ")"
		} else {
			column = "TEXT"
		}
	case KindEnum:
		values := make([]string, 0, len(f.Enum))
		for _, e := range f.Enum {
			values = append(values, "'"+e+"'")
		}
		column = "TEXT CHECK (" + f.Name + " IN (" + strings.Join(values, ", ") + "))"
	case KindInt:
		column = "INTEGER"
		if f.Min != nil && f.Max != nil {
			column += " CHECK (" + f.Name + " BETWEEN " + formatFloat(*f.Min) + " AND " + formatFloat(*f.Max) + ")"
		}
	case KindRef:
		column = "BIGINT REFERENCES " + f.Ref + "(id)"
	case KindDate:
		column = "DATE"
	case KindMoney:
		column = "NUMERIC(14,2)"
	case KindBool:
		column = "BOOLEAN"
	}

	if f.Required {
		column += " NOT NULL"
	}
	if f.Default != "" {
		column += " DEFAULT " + f.Default
	}

	return column
}

func rulesLiteral(f Field) string {
	parts := []string{}
	if f.Required {
		parts = append(parts, "Required: true")
	}
	if f.Pattern != "" {
		parts = append(parts, "Pattern: regexp.MustCompile(`"+f.Pattern+"`)", "PatternText: "+strconv.Quote(f.Pattern))
	}
	if f.MinLen > 0 {
		parts = append(parts, "MinLen: "+strconv.Itoa(f.MinLen))
	}
	if f.MaxLen > 0 {
		parts = append(parts, "MaxLen: "+strconv.Itoa(f.MaxLen))
	}
	if f.Min != nil {
		parts = append(parts, "Min: f64("+formatFloat(*f.Min)+")")
	}
	if f.Max != nil {
		parts = append(parts, "Max: f64("+formatFloat(*f.Max)+")")
	}
	if len(f.Enum) > 0 {
		quoted := make([]string, 0, len(f.Enum))
		for _, e := range f.Enum {
			quoted = append(quoted, strconv.Quote(e))
		}
		parts = append(parts, "Enum: []string{"+strings.Join(quoted, ", ")+"}")
	}

	return "record.Rules{" + strings.Join(parts, ", ") + "}"
}

// conversions return the expressions turning the API input field into the domain value and back.
func conversions(f Field, v fieldView, apiType string) (fromAPI, toAPI string) {
	in := "in." + v.APIName
	out := "f." + v.GoName

	switch f.Kind {
	case KindEnum:
		if f.Required {
			return "string(" + in + ")", apiType + "(" + out + ")"
		}

		return "recordhndl.EnumPtr(" + in + ")", "recordhndl.EnumPtrTo[" + strings.TrimPrefix(apiType, "*") + "](" + out + ")"
	case KindDate:
		if f.Required {
			return in + ".Time", "openapi_types.Date{Time: " + out + "}"
		}

		return "recordhndl.DatePtr(" + in + ")", "recordhndl.DatePtrTo(" + out + ")"
	default:
		return in, out
	}
}

// camel turns snake_case into CamelCase, with initialisms when the Go naming convention is wanted.
func camel(s string, goNaming bool) string {
	parts := strings.Split(s, "_")
	for i, p := range parts {
		if p == "" {
			continue
		}
		if goNaming && p == "id" {
			parts[i] = "ID"
			continue
		}
		parts[i] = strings.ToUpper(p[:1]) + p[1:]
	}

	return strings.Join(parts, "")
}

func lowerFirst(s string) string {
	if s == "" {
		return s
	}

	return strings.ToLower(s[:1]) + s[1:]
}

// humanize turns a field name into an export column title: "numeric_code" becomes "Numeric code".
func humanize(s string) string {
	s = strings.ReplaceAll(s, "_", " ")
	if s == "" {
		return s
	}

	return strings.ToUpper(s[:1]) + s[1:]
}

func formatFloat(v float64) string {
	return strconv.FormatFloat(v, 'f', -1, 64)
}

func yamlString(s string) string {
	return strconv.Quote(s)
}

func yamlExample(f Field) string {
	switch f.Kind {
	case KindInt, KindRef, KindMoney, KindBool:
		return f.Example
	default:
		return strconv.Quote(f.Example)
	}
}

// indent prefixes every line with spaces, for YAML blocks rendered inside templates.
func indent(spaces int, s string) string {
	pad := strings.Repeat(" ", spaces)
	lines := strings.Split(strings.TrimRight(s, "\n"), "\n")
	for i, line := range lines {
		if line != "" {
			lines[i] = pad + line
		}
	}

	return strings.Join(lines, "\n")
}

// roles returns the x-required-roles of the read and the write operations of a group (documents/070.role-matrix.md).
func roles(group string) (read, write string) {
	switch group {
	case "GroupClassifiers":
		return "[reference-reader, reference-hr-reader, reference-admin, reference-hr-admin]", "[reference-admin]"
	case "GroupHR":
		return "[reference-reader, reference-hr-reader, reference-admin, reference-hr-admin]", "[reference-hr-admin]"
	default:
		return "[reference-hr-reader, reference-hr-admin]", "[reference-hr-admin]"
	}
}
