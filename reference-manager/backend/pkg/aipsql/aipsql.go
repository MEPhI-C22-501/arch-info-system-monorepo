// Package aipsql translates AIP-160 filters and AIP-132 orderings parsed by go.einride.tech/aip into PostgreSQL.
package aipsql

import (
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"go.einride.tech/aip/filtering"
	"go.einride.tech/aip/ordering"
	expr "google.golang.org/genproto/googleapis/api/expr/v1alpha1"
	"google.golang.org/protobuf/proto"
)

// Columns maps the fields of AIP-160 filters and AIP-132 orderings to SQL column names.
// Only the mapped fields can be used, so client input never reaches the query text.
type Columns map[string]string

// Args collects the query arguments and returns PostgreSQL placeholders for them.
type Args struct {
	values []any
}

func (a *Args) Add(value any) string {
	a.values = append(a.values, value)
	return "$" + strconv.Itoa(len(a.values))
}

func (a *Args) Values() []any {
	return a.values
}

var errUnsupportedFilter = errors.New("unsupported filter expression")

// TranspileFilter turns a checked AIP-160 filter into an SQL condition, it returns an empty string for an empty filter.
// An error means that the filter uses an expression or a field that cannot be translated.
func TranspileFilter(filter filtering.Filter, columns Columns, args *Args) (string, error) {
	if filter.CheckedExpr == nil {
		return "", nil
	}

	t := filterTranspiler{
		typeMap: filter.CheckedExpr.GetTypeMap(),
		columns: columns,
		args:    args,
	}

	return t.transpile(filter.CheckedExpr.GetExpr())
}

// TranspileOrderBy turns an AIP-132 ordering into an ORDER BY list, the tiebreaker keeps pagination stable.
func TranspileOrderBy(orderBy ordering.OrderBy, columns Columns, tiebreaker string) (string, error) {
	fields := make([]string, 0, len(orderBy.Fields)+1)
	for _, field := range orderBy.Fields {
		column, ok := columns[field.Path]
		if !ok {
			return "", fmt.Errorf("unknown field %q", field.Path)
		}

		if field.Desc {
			column += " DESC"
		}

		fields = append(fields, column)
	}

	return strings.Join(append(fields, tiebreaker), ", "), nil
}

type filterTranspiler struct {
	typeMap map[int64]*expr.Type
	columns Columns
	args    *Args
}

var comparisonOperators = map[string]string{
	filtering.FunctionEquals:        "=",
	filtering.FunctionNotEquals:     "<>",
	filtering.FunctionLessThan:      "<",
	filtering.FunctionLessEquals:    "<=",
	filtering.FunctionGreaterThan:   ">",
	filtering.FunctionGreaterEquals: ">=",
}

func (t *filterTranspiler) transpile(e *expr.Expr) (string, error) {
	switch {
	case e.GetIdentExpr() != nil:
		return t.ident(e)
	case e.GetCallExpr() != nil:
		return t.transpileCall(e)
	default:
		return "", errUnsupportedFilter
	}
}

func (t *filterTranspiler) transpileCall(e *expr.Expr) (string, error) {
	call := e.GetCallExpr()
	args := call.GetArgs()

	switch call.GetFunction() {
	case filtering.FunctionAnd, filtering.FunctionOr:
		return t.transpileLogical(call.GetFunction(), args)
	case filtering.FunctionNot:
		operand, err := t.transpile(args[0])
		if err != nil {
			return "", err
		}

		return "(NOT " + operand + ")", nil
	case filtering.FunctionHas:
		return t.transpileHas(args[0], args[1])
	}

	operator, ok := comparisonOperators[call.GetFunction()]
	if !ok {
		return "", fmt.Errorf("unsupported function %q", call.GetFunction())
	}

	return t.transpileComparison(operator, args[0], args[1])
}

func (t *filterTranspiler) transpileLogical(function string, args []*expr.Expr) (string, error) {
	operands := make([]string, 0, len(args))
	for _, arg := range args {
		operand, err := t.transpile(arg)
		if err != nil {
			return "", err
		}

		operands = append(operands, operand)
	}

	return "(" + strings.Join(operands, " "+function+" ") + ")", nil
}

func (t *filterTranspiler) transpileComparison(operator string, lhs, rhs *expr.Expr) (string, error) {
	// A string with a leading or trailing * is a wildcard match (AIP-160).
	if pattern, ok := wildcardPattern(rhs); ok && (operator == "=" || operator == "<>") && t.isString(lhs) {
		column, err := t.column(lhs)
		if err != nil {
			return "", err
		}

		like := "LIKE"
		if operator == "<>" {
			like = "NOT LIKE"
		}

		return "(" + column + " " + like + " " + t.args.Add(pattern) + ")", nil
	}

	left, err := t.operand(lhs, rhs)
	if err != nil {
		return "", err
	}

	right, err := t.operand(rhs, lhs)
	if err != nil {
		return "", err
	}

	return "(" + left + " " + operator + " " + right + ")", nil
}

// transpileHas treats `field:*` as a presence check and `field:"text"` as a case-insensitive containment check.
func (t *filterTranspiler) transpileHas(lhs, rhs *expr.Expr) (string, error) {
	column, err := t.column(lhs)
	if err != nil {
		return "", err
	}

	value := rhs.GetConstExpr().GetStringValue()
	if value == "*" {
		return "(" + column + " IS NOT NULL)", nil
	}

	if !t.isString(lhs) {
		return "", errors.New("the has operator only supports string fields and presence checks")
	}

	return "(" + column + " ILIKE " + t.args.Add("%"+escapeLike(value)+"%") + ")", nil
}

// operand transpiles a comparison operand, peer is the other operand that defines how a string literal is read.
func (t *filterTranspiler) operand(e, peer *expr.Expr) (string, error) {
	switch {
	case e.GetIdentExpr() != nil:
		return t.ident(e)
	case e.GetConstExpr() != nil:
		value, err := t.constant(e.GetConstExpr(), peer)
		if err != nil {
			return "", err
		}

		return t.args.Add(value), nil
	case e.GetCallExpr().GetFunction() == filtering.FunctionTimestamp:
		value, err := parseTimestamp(e.GetCallExpr().GetArgs()[0].GetConstExpr().GetStringValue())
		if err != nil {
			return "", err
		}

		return t.args.Add(value), nil
	default:
		return "", errUnsupportedFilter
	}
}

func (t *filterTranspiler) constant(c *expr.Constant, peer *expr.Expr) (any, error) {
	switch v := c.GetConstantKind().(type) {
	case *expr.Constant_BoolValue:
		return v.BoolValue, nil
	case *expr.Constant_Int64Value:
		return v.Int64Value, nil
	case *expr.Constant_DoubleValue:
		return v.DoubleValue, nil
	case *expr.Constant_StringValue:
		if proto.Equal(t.typeMap[peer.GetId()], filtering.TypeTimestamp) {
			return parseTimestamp(v.StringValue)
		}

		return v.StringValue, nil
	default:
		return nil, errUnsupportedFilter
	}
}

// boolLiterals are the idents true and false, the filtering library has no bool literals,
// so filters declare them as bool idents (see BoolLiteralDeclarations).
var boolLiterals = map[string]string{
	"true":  "TRUE",
	"false": "FALSE",
}

// BoolLiteralDeclarations declare the idents true and false, which TranspileFilter turns into bool literals.
func BoolLiteralDeclarations() []filtering.DeclarationOption {
	options := make([]filtering.DeclarationOption, 0, len(boolLiterals))
	for name := range boolLiterals {
		options = append(options, filtering.DeclareIdent(name, filtering.TypeBool))
	}

	return options
}

func (t *filterTranspiler) ident(e *expr.Expr) (string, error) {
	if literal, ok := boolLiterals[e.GetIdentExpr().GetName()]; ok {
		return literal, nil
	}

	return t.column(e)
}

func (t *filterTranspiler) column(e *expr.Expr) (string, error) {
	name := e.GetIdentExpr().GetName()

	column, ok := t.columns[name]
	if !ok {
		return "", fmt.Errorf("unknown field %q", name)
	}

	return column, nil
}

func (t *filterTranspiler) isString(e *expr.Expr) bool {
	return proto.Equal(t.typeMap[e.GetId()], filtering.TypeString)
}

func wildcardPattern(e *expr.Expr) (string, bool) {
	value, ok := e.GetConstExpr().GetConstantKind().(*expr.Constant_StringValue)
	if !ok {
		return "", false
	}

	s := value.StringValue
	prefix, suffix := strings.HasPrefix(s, "*"), strings.HasSuffix(s, "*")
	if !prefix && !suffix {
		return "", false
	}

	s = strings.TrimSuffix(strings.TrimPrefix(s, "*"), "*")

	pattern := escapeLike(s)
	if prefix {
		pattern = "%" + pattern
	}
	if suffix {
		pattern += "%"
	}

	return pattern, true
}

var likeEscaper = strings.NewReplacer(`\`, `\\`, `%`, `\%`, `_`, `\_`)

func escapeLike(s string) string {
	return likeEscaper.Replace(s)
}

func parseTimestamp(s string) (time.Time, error) {
	value, err := time.Parse(time.RFC3339, s)
	if err != nil {
		return time.Time{}, fmt.Errorf("invalid timestamp %q, should be in RFC3339 format", s)
	}

	return value, nil
}
