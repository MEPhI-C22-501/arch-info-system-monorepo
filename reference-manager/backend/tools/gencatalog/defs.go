package main

// Kind is the type of a catalog field, it defines the OpenAPI schema, the Go type, the SQL column and the filtering type.
type Kind int

const (
	KindString Kind = iota
	KindEnum
	KindInt
	KindRef
	KindDate
	KindMoney
	KindBool
)

// Field is one field of a catalog as the definition sees it.
type Field struct {
	Name        string
	Kind        Kind
	Description string
	Example     string
	// Required fields are NOT NULL in the table and required in the input schema.
	Required bool
	Unique   bool
	// Immutable fields are accepted on creation and rejected in the update mask.
	Immutable bool
	// ServerManaged fields are stored but never accepted from the client, the service sets them.
	ServerManaged bool
	// Default is the SQL default of a server-managed column, GoDefault the Go literal the service starts a new record with.
	Default   string
	GoDefault string
	// Computed fields are expressions of the view, they are read and filtered, never stored.
	Computed string
	Pattern  string
	MinLen   int
	MaxLen   int
	Min      *float64
	Max      *float64
	// Enum lists the values of an enum field, EnumName is the name of its schema component.
	Enum     []string
	EnumName string
	// Ref is the referenced table of a KindRef field.
	Ref string
	// Migration is the number of the hand-written migration that adds the column to an existing table,
	// zero means the column is created with the table. The create migration and its view leave such fields out.
	Migration int
}

// CustomOp is a catalog-specific method the generator declares in the spec and the service interface,
// its handler and service code are written by hand.
type CustomOp struct {
	// Path is the sub-path after the record: "dismiss" gives POST /v1/employees/{employeeID}/dismiss.
	Path        string
	OperationID string
	Summary     string
	Description string
	// BodySchema is the name of the request body schema, BodyYAML its YAML definition indented by four spaces.
	// An operation without a body leaves both empty.
	BodySchema string
	BodyYAML   string
	// ServiceMethod is the Go signature the handler expects from the service.
	ServiceMethod string
}

// Catalog is the definition the generator renders into a spec, a domain package, a handler and a migration.
type Catalog struct {
	Singular    string
	Plural      string
	Title       string
	Description string
	// Group is the access group constant: GroupClassifiers, GroupHR or GroupRestrictedHR.
	Group string
	// Migration is the sequence number of the migration files.
	Migration int
	Fields    []Field
	// Constraints are extra table constraints, Indexes extra statements, Extensions required extensions.
	Constraints []string
	Indexes     []string
	Extensions  []string
	// HasRules is true when the domain package has a hand-written validate function.
	HasRules bool
	Custom   []CustomOp
}

func float(v float64) *float64 { return &v }

const (
	slugPattern = `^[a-z][a-z0-9-]{1,63}$`
	slugHint    = "lowercase latin letters, digits and hyphens, 2 to 64 characters"
)

func codeField(description string) Field {
	return Field{
		Name: "code", Kind: KindString, Required: true, Unique: true, Pattern: slugPattern, MinLen: 2, MaxLen: 64,
		Description: description + " " + slugHint + ".", Example: "developer",
	}
}

func nameField(description, example string) Field {
	return Field{Name: "name", Kind: KindString, Required: true, MaxLen: 128, Description: description, Example: example}
}

var employeeRef = Field{
	Name: "employee_id", Kind: KindRef, Ref: "employees", Required: true, Immutable: true,
	Description: "Identifier of the employee, cannot be changed after creation.", Example: "1",
}

var startDate = Field{Name: "start_date", Kind: KindDate, Required: true, Description: "First day the record is in effect.", Example: "2026-01-01"}

var periodConstraints = []string{
	"CONSTRAINT chk_%[1]s_period CHECK (end_date IS NULL OR end_date >= start_date)",
	"CONSTRAINT excl_%[1]s_employee_period EXCLUDE USING gist (employee_id WITH =, daterange(start_date, end_date, '[]') WITH &&) WHERE (NOT is_deleted)",
}

// Catalogs are the catalogs of the first version besides currencies, in migration order.
var Catalogs = []Catalog{
	{
		Singular: "country", Plural: "countries", Title: "Country", Group: "GroupClassifiers", Migration: 2,
		Description: "Countries according to ISO 3166-1 with a reference to the main currency.",
		Fields: []Field{
			{Name: "alpha2", Kind: KindString, Required: true, Unique: true, Pattern: `^[A-Z]{2}$`, MinLen: 2, MaxLen: 2, Description: "Two-letter ISO 3166-1 alpha-2 code.", Example: "RU"},
			{Name: "alpha3", Kind: KindString, Required: true, Unique: true, Pattern: `^[A-Z]{3}$`, MinLen: 3, MaxLen: 3, Description: "Three-letter ISO 3166-1 alpha-3 code.", Example: "RUS"},
			{Name: "numeric_code", Kind: KindString, Required: true, Unique: true, Pattern: `^\d{3}$`, MinLen: 3, MaxLen: 3, Description: "Three-digit ISO 3166-1 numeric code, a string to keep leading zeros.", Example: "643"},
			nameField("Short name of the country.", "Russia"),
			{Name: "currency_id", Kind: KindRef, Ref: "currencies", Description: "Identifier of the main currency of the country.", Example: "1"},
		},
		HasRules: true,
	},
	{
		Singular: "project_role", Plural: "project_roles", Title: "ProjectRole", Group: "GroupClassifiers", Migration: 3,
		Description: "Project roles used by the planning of work.",
		Fields: []Field{
			codeField("Stable code of the role:"),
			nameField("Name of the role.", "Developer"),
			{Name: "description", Kind: KindString, MaxLen: 512, Description: "What the role does in a project.", Example: "Implements and reviews code."},
		},
	},
	{
		Singular: "grade", Plural: "grades", Title: "Grade", Group: "GroupClassifiers", Migration: 4,
		Description: "Qualification grades of employees used by the planning of work.",
		Fields: []Field{
			codeField("Stable code of the grade:"),
			nameField("Name of the grade.", "Senior"),
			{Name: "rank", Kind: KindInt, Required: true, Min: float(1), Max: float(100), Description: "Order of the grade, higher is more senior.", Example: "3"},
		},
	},
	{
		Singular: "org_unit", Plural: "org_units", Title: "OrgUnit", Group: "GroupHR", Migration: 5,
		Description: "Organizational units: departments and teams with their hierarchy.",
		Fields: []Field{
			codeField("Stable code of the unit:"),
			nameField("Name of the unit.", "Backend team"),
			{Name: "kind", Kind: KindEnum, Required: true, Enum: []string{"DEPARTMENT", "TEAM"}, EnumName: "OrgUnitKind", Description: "Department or team.", Example: "TEAM"},
			{Name: "parent_id", Kind: KindRef, Ref: "org_units", Description: "Identifier of the parent unit, empty for a top-level unit. A reference that forms a cycle is rejected.", Example: "1"},
		},
		Indexes:  []string{"CREATE INDEX idx_org_units_parent ON org_units (parent_id) WHERE is_deleted = FALSE;"},
		HasRules: true,
	},
	{
		Singular: "position", Plural: "positions", Title: "Position", Group: "GroupHR", Migration: 6,
		Description: "Positions employees are assigned to.",
		Fields: []Field{
			codeField("Stable code of the position:"),
			nameField("Name of the position.", "Software developer"),
		},
	},
	{
		Singular: "employee", Plural: "employees", Title: "Employee", Group: "GroupHR", Migration: 7,
		Description: "HR profiles of employees. The unit and the position come from the assignment in effect today.",
		Fields: []Field{
			{Name: "personnel_number", Kind: KindString, Required: true, Unique: true, Pattern: `^[0-9]{1,10}$`, MinLen: 1, MaxLen: 10, Description: "Personnel number, 1 to 10 digits.", Example: "1024"},
			{Name: "family_name", Kind: KindString, Required: true, MaxLen: 100, Description: "Family name.", Example: "Ivanov"},
			{Name: "given_name", Kind: KindString, Required: true, MaxLen: 100, Description: "Given name.", Example: "Ivan"},
			{Name: "middle_name", Kind: KindString, MaxLen: 100, Description: "Middle name, when present.", Example: "Ivanovich"},
			{Name: "email", Kind: KindString, Required: true, Unique: true, Pattern: `^[^@\s]+@[^@\s]+\.[^@\s]+$`, MaxLen: 254, Description: "Work email address.", Example: "i.ivanov@example.org"},
			{Name: "username", Kind: KindString, Required: true, Unique: true, Immutable: true, Pattern: `^[a-z][a-z0-9._-]{2,63}$`, MinLen: 3, MaxLen: 64, Description: "Login in Keycloak, cannot be changed after creation.", Example: "i.ivanov"},
			{Name: "hire_date", Kind: KindDate, Required: true, Description: "Date of hire.", Example: "2026-10-01"},
			{Name: "employment_state", Kind: KindEnum, Required: true, ServerManaged: true, Default: "'EMPLOYED'", GoDefault: `"EMPLOYED"`, Enum: []string{"EMPLOYED", "DISMISSED"}, EnumName: "EmploymentState", Description: "EMPLOYED until the employee is dismissed.", Example: "EMPLOYED"},
			{Name: "dismissal_date", Kind: KindDate, ServerManaged: true, Description: "Date of dismissal, set by the dismissal.", Example: "2026-10-31"},
			{Name: "org_unit_id", Kind: KindRef, Ref: "org_units", Computed: "NULL::bigint", Description: "Identifier of the unit from the assignment in effect today, filled by migration 000011.", Example: "1"},
			{Name: "position_id", Kind: KindRef, Ref: "positions", Computed: "NULL::bigint", Description: "Identifier of the position from the assignment in effect today, filled by migration 000011.", Example: "1"},
			{Name: "account_state", Kind: KindEnum, Required: true, ServerManaged: true, Default: "'PENDING'", GoDefault: `"PENDING"`, Enum: []string{"PENDING", "ENABLED", "DISABLED"}, EnumName: "AccountState", Migration: 12,
				Description: "State of the Keycloak account: PENDING until the last operation with the account is confirmed, ENABLED while the employee works, DISABLED after the dismissal (FR-RM-55).", Example: "ENABLED"},
			{Name: "account_user_id", Kind: KindString, ServerManaged: true, MaxLen: 36, Migration: 12,
				Description: "Identifier of the Keycloak account, the sub claim of its tokens. Empty until the account is created, kept after the dismissal.", Example: "9b2f1c4e-6d3a-4b8e-9f10-2a7c5d8e1b34"},
		},
		Constraints: []string{"CONSTRAINT chk_employees_dismissal CHECK (dismissal_date IS NULL OR dismissal_date >= hire_date)"},
		Indexes:     []string{"CREATE INDEX idx_employees_employment_state ON employees (employment_state) WHERE is_deleted = FALSE;"},
		HasRules:    true,
		Custom: []CustomOp{{
			Path: "dismiss", OperationID: "dismissEmployee", Summary: "Dismiss an employee",
			Description: "Sets the employment state to DISMISSED with the dismissal date and closes the assignment and the salary in effect with that date. A dismissed employee cannot be dismissed again.",
			BodySchema:  "EmployeeDismissal",
			BodyYAML: "      type: object\n      required:\n        - dismissal_date\n      properties:\n        dismissal_date:\n" +
				"          type: string\n          format: date\n          description: Last day of employment, not earlier than the hire date.\n          example: \"2026-10-31\"\n",
			ServiceMethod: "Dismiss(ctx context.Context, id int64, dismissalDate time.Time) (*record.Expanded[employeedmn.Fields], error)",
		}, {
			Path: "syncAccount", OperationID: "syncEmployeeAccount", Summary: "Repeat the pending operation with the Keycloak account",
			Description:   "Brings the Keycloak account in line with the record: creates it when it is missing, enables it while the employee works, disables it after the dismissal and passes the names and the email. Safe to repeat, a second account is never created (FR-RM-56).",
			ServiceMethod: "SyncAccount(ctx context.Context, id int64) (*record.Expanded[employeedmn.Fields], error)",
		}},
	},
	{
		Singular: "assignment", Plural: "assignments", Title: "Assignment", Group: "GroupHR", Migration: 8,
		Description: "Assignments of employees to units and positions with the period they are in effect. Periods of one employee do not overlap.",
		Fields: []Field{
			employeeRef,
			{Name: "org_unit_id", Kind: KindRef, Ref: "org_units", Required: true, Description: "Identifier of the unit.", Example: "1"},
			{Name: "position_id", Kind: KindRef, Ref: "positions", Required: true, Description: "Identifier of the position.", Example: "1"},
			startDate,
			{Name: "end_date", Kind: KindDate, Description: "Last day the record is in effect, empty while it is in effect.", Example: "2026-12-31"},
		},
		Constraints: periodConstraints,
		Extensions:  []string{"btree_gist"},
		HasRules:    true,
	},
	{
		Singular: "salary", Plural: "salaries", Title: "Salary", Group: "GroupRestrictedHR", Migration: 9,
		Description: "Monthly salaries of employees with the period they are in effect. Periods of one employee do not overlap. Readable by the HR roles only.",
		Fields: []Field{
			employeeRef,
			{Name: "amount", Kind: KindMoney, Required: true, Min: float(0.01), Description: "Monthly salary, a positive amount with two decimals.", Example: "150000.00"},
			{Name: "currency_id", Kind: KindRef, Ref: "currencies", Required: true, Description: "Identifier of the currency of the amount.", Example: "1"},
			startDate,
			{Name: "end_date", Kind: KindDate, Description: "Last day the record is in effect, empty while it is in effect.", Example: "2026-12-31"},
		},
		Constraints: append([]string{"CONSTRAINT chk_salaries_amount CHECK (amount > 0)"}, periodConstraints...),
		Extensions:  []string{"btree_gist"},
		HasRules:    true,
	},
	{
		Singular: "absence", Plural: "absences", Title: "Absence", Group: "GroupRestrictedHR", Migration: 10,
		Description: "Absences of employees: vacations, sick leaves and other periods. Readable by the HR roles only.",
		Fields: []Field{
			employeeRef,
			{Name: "kind", Kind: KindEnum, Required: true, Enum: []string{"VACATION", "SICK_LEAVE", "OTHER"}, EnumName: "AbsenceKind", Description: "Kind of the absence.", Example: "VACATION"},
			{Name: "start_date", Kind: KindDate, Required: true, Description: "First day of the absence.", Example: "2026-07-06"},
			{Name: "end_date", Kind: KindDate, Required: true, Description: "Last day of the absence, not earlier than the first day.", Example: "2026-07-19"},
		},
		Constraints: []string{"CONSTRAINT chk_absences_period CHECK (end_date >= start_date)"},
		Indexes:     []string{"CREATE INDEX idx_absences_employee_period ON absences (employee_id, start_date, end_date) WHERE is_deleted = FALSE;"},
		HasRules:    true,
	},
}
