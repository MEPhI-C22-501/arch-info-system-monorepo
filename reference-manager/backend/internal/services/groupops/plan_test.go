package groupopssrv

import (
	"errors"
	"testing"
	"time"

	assignmentdmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/assignment"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	salarydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/salary"
)

func day(s string) time.Time {
	t, err := time.Parse(dateLayout, s)
	if err != nil {
		panic(err)
	}

	return t
}

func ptr[T any](v T) *T { return &v }

func salary(id, employee int64, amount float64, currency int64, start string, end *time.Time) *record.Expanded[salarydmn.Fields] {
	return &record.Expanded[salarydmn.Fields]{Record: record.Record[salarydmn.Fields]{ID: id, Fields: salarydmn.Fields{
		EmployeeID: employee, Amount: amount, CurrencyID: currency, StartDate: day(start), EndDate: end,
	}}}
}

func assignment(id, employee, unit, position int64, start string, end *time.Time) *record.Expanded[assignmentdmn.Fields] {
	return &record.Expanded[assignmentdmn.Fields]{Record: record.Record[assignmentdmn.Fields]{ID: id, Fields: assignmentdmn.Fields{
		EmployeeID: employee, OrgUnitID: unit, PositionID: position, StartDate: day(start), EndDate: end,
	}}}
}

func fieldsOf(err error) map[string]string {
	var v *record.ValidationError
	if !errors.As(err, &v) {
		return nil
	}

	fields := map[string]string{}
	for _, f := range v.Fields {
		fields[f.Field] = f.Message
	}

	return fields
}

func TestValidateRevision(t *testing.T) {
	t.Parallel()

	start := day("2027-01-01")

	if err := validateRevision(&salarydmn.GroupChangeRequest{OrgUnitID: 2, StartDate: start, Percent: ptr(10.0)}); err != nil {
		t.Errorf("a percent change is valid: %v", err)
	}
	if err := validateRevision(&salarydmn.GroupChangeRequest{OrgUnitID: 2, StartDate: start, Amount: ptr(150000.0), CurrencyID: ptr(int64(1))}); err != nil {
		t.Errorf("an amount with a currency is valid: %v", err)
	}

	cases := map[string]struct {
		request *salarydmn.GroupChangeRequest
		field   string
	}{
		"no unit":               {&salarydmn.GroupChangeRequest{StartDate: start, Percent: ptr(5.0)}, "org_unit_id"},
		"no date":               {&salarydmn.GroupChangeRequest{OrgUnitID: 2, Percent: ptr(5.0)}, "start_date"},
		"neither change":        {&salarydmn.GroupChangeRequest{OrgUnitID: 2, StartDate: start}, "percent"},
		"both changes":          {&salarydmn.GroupChangeRequest{OrgUnitID: 2, StartDate: start, Percent: ptr(5.0), Amount: ptr(1.0)}, "amount"},
		"zero percent":          {&salarydmn.GroupChangeRequest{OrgUnitID: 2, StartDate: start, Percent: ptr(0.0)}, "percent"},
		"minus hundred percent": {&salarydmn.GroupChangeRequest{OrgUnitID: 2, StartDate: start, Percent: ptr(-100.0)}, "percent"},
		"currency with percent": {&salarydmn.GroupChangeRequest{OrgUnitID: 2, StartDate: start, Percent: ptr(5.0), CurrencyID: ptr(int64(1))}, "currency_id"},
		"negative amount":       {&salarydmn.GroupChangeRequest{OrgUnitID: 2, StartDate: start, Amount: ptr(-1.0)}, "amount"},
		"zero currency":         {&salarydmn.GroupChangeRequest{OrgUnitID: 2, StartDate: start, Amount: ptr(1.0), CurrencyID: ptr(int64(0))}, "currency_id"},
	}
	for name, tc := range cases {
		if _, ok := fieldsOf(validateRevision(tc.request))[tc.field]; !ok {
			t.Errorf("%s: want a violation of %s, got %v", name, tc.field, validateRevision(tc.request))
		}
	}
}

func TestPlanRevisionByPercent(t *testing.T) {
	t.Parallel()

	end := day("2027-06-30")
	request := &salarydmn.GroupChangeRequest{OrgUnitID: 2, StartDate: day("2027-01-01"), Percent: ptr(10.0)}
	current := map[int64]*record.Expanded[salarydmn.Fields]{
		1: salary(11, 1, 150000, 1, "2026-01-01", nil),
		2: salary(12, 2, 98765.43, 1, "2026-03-01", &end),
		5: salary(15, 5, 100000, 1, "2026-01-01", nil),
	}
	employed := map[int64]bool{1: true, 2: true, 3: true, 4: false, 5: true}

	plan := planRevision(request, []int64{1, 2, 3, 4, 5}, employed, current)

	if len(plan.blocked) != 0 || len(plan.steps) != 3 {
		t.Fatalf("want three changes and nothing blocked, got %+v", plan)
	}

	first := plan.steps[0]
	if first.close.ID != 11 || first.item.Amount != 165000 || first.item.CurrencyID != 1 || first.item.EndDate != nil || *first.item.ClosedSalaryID != 11 || *first.item.PreviousAmount != 150000 {
		t.Errorf("the open salary of employee 1 ends and a raised one opens: %+v", first.item)
	}

	second := plan.steps[1]
	if second.item.Amount != 108641.97 || second.item.EndDate == nil || !second.item.EndDate.Equal(end) {
		t.Errorf("the raised amount is rounded to two decimals and keeps the end of the closed salary: %+v", second.item)
	}
	if second.item.SalaryID != nil {
		t.Errorf("the plan has no created salary yet: %+v", second.item)
	}

	want := []salarydmn.Skipped{{EmployeeID: 3, Reason: reasonNoSalary}, {EmployeeID: 4, Reason: reasonDismissed}}
	if len(plan.skipped) != 2 || plan.skipped[0] != want[0] || plan.skipped[1] != want[1] {
		t.Errorf("employees without a salary and dismissed ones are skipped with the reason, got %+v", plan.skipped)
	}
}

func TestPlanRevisionByAmount(t *testing.T) {
	t.Parallel()

	request := &salarydmn.GroupChangeRequest{OrgUnitID: 2, StartDate: day("2027-01-01"), Amount: ptr(120000.0), CurrencyID: ptr(int64(2))}
	current := map[int64]*record.Expanded[salarydmn.Fields]{1: salary(11, 1, 150000, 1, "2026-01-01", nil)}

	plan := planRevision(request, []int64{1, 3}, map[int64]bool{1: true, 3: true}, current)
	if len(plan.steps) != 2 {
		t.Fatalf("want two changes, got %+v", plan)
	}
	if plan.steps[0].item.Amount != 120000 || plan.steps[0].item.CurrencyID != 2 {
		t.Errorf("the amount and the currency of the request replace the current ones: %+v", plan.steps[0].item)
	}
	if plan.steps[1].close != nil || plan.steps[1].item.ClosedSalaryID != nil || plan.steps[1].item.CurrencyID != 2 {
		t.Errorf("an employee without a salary gets a first one: %+v", plan.steps[1].item)
	}

	withoutCurrency := planRevision(&salarydmn.GroupChangeRequest{OrgUnitID: 2, StartDate: day("2027-01-01"), Amount: ptr(1.0)}, []int64{3}, map[int64]bool{3: true}, nil)
	if len(withoutCurrency.steps) != 0 || len(withoutCurrency.skipped) != 1 || withoutCurrency.skipped[0].Reason != reasonNoCurrency {
		t.Errorf("without a salary and a currency nothing can be created: %+v", withoutCurrency)
	}
}

func TestPlanRevisionBlocksASalaryStartingOnTheDate(t *testing.T) {
	t.Parallel()

	request := &salarydmn.GroupChangeRequest{OrgUnitID: 2, StartDate: day("2027-01-01"), Percent: ptr(5.0)}
	current := map[int64]*record.Expanded[salarydmn.Fields]{
		1: salary(11, 1, 150000, 1, "2026-01-01", nil),
		2: salary(12, 2, 150000, 1, "2027-01-01", nil),
	}

	plan := planRevision(request, []int64{1, 2}, map[int64]bool{1: true, 2: true}, current)
	if len(plan.blocked) != 1 || plan.blocked[0] != 2 {
		t.Errorf("a salary that starts on the date cannot end the day before, got %+v", plan)
	}
}

func TestValidateTransfer(t *testing.T) {
	t.Parallel()

	start := day("2027-01-01")
	if err := validateTransfer(&assignmentdmn.TransferRequest{OrgUnitID: 3, TargetOrgUnitID: 4, StartDate: start}); err != nil {
		t.Errorf("a transfer is valid: %v", err)
	}

	cases := map[string]struct {
		request *assignmentdmn.TransferRequest
		field   string
	}{
		"no unit":       {&assignmentdmn.TransferRequest{TargetOrgUnitID: 4, StartDate: start}, "org_unit_id"},
		"no target":     {&assignmentdmn.TransferRequest{OrgUnitID: 3, StartDate: start}, "target_org_unit_id"},
		"same unit":     {&assignmentdmn.TransferRequest{OrgUnitID: 3, TargetOrgUnitID: 3, StartDate: start}, "target_org_unit_id"},
		"no date":       {&assignmentdmn.TransferRequest{OrgUnitID: 3, TargetOrgUnitID: 4}, "start_date"},
		"zero position": {&assignmentdmn.TransferRequest{OrgUnitID: 3, TargetOrgUnitID: 4, StartDate: start, PositionID: ptr(int64(0))}, "position_id"},
	}
	for name, tc := range cases {
		if _, ok := fieldsOf(validateTransfer(tc.request))[tc.field]; !ok {
			t.Errorf("%s: want a violation of %s, got %v", name, tc.field, validateTransfer(tc.request))
		}
	}
}

func TestPlanTransfer(t *testing.T) {
	t.Parallel()

	end := day("2027-12-31")
	assignments := []*record.Expanded[assignmentdmn.Fields]{
		assignment(21, 1, 3, 7, "2026-01-01", nil),
		assignment(22, 2, 5, 8, "2026-02-01", &end),
		assignment(23, 3, 4, 7, "2026-01-01", nil),
		assignment(24, 4, 3, 7, "2026-01-01", nil),
		assignment(25, 6, 3, 7, "2027-01-01", nil),
	}
	employed := map[int64]bool{1: true, 2: true, 3: true, 4: false, 6: true}

	plan := planTransfer(&assignmentdmn.TransferRequest{OrgUnitID: 3, TargetOrgUnitID: 4, StartDate: day("2027-01-01"), IncludeSubunits: true}, assignments, employed)

	if len(plan.blocked) != 1 || plan.blocked[0] != 6 {
		t.Errorf("an assignment that starts on the date cannot end the day before, got %+v", plan.blocked)
	}
	if len(plan.steps) != 2 {
		t.Fatalf("want two moves, got %+v", plan.steps)
	}
	if got := plan.steps[0].item; got.ClosedAssignmentID != 21 || got.FromOrgUnitID != 3 || got.TargetOrgUnitID != 4 || got.PositionID != 7 || got.EndDate != nil {
		t.Errorf("employee 1 moves with the position: %+v", got)
	}
	if got := plan.steps[1].item; got.FromOrgUnitID != 5 || got.EndDate == nil || !got.EndDate.Equal(end) {
		t.Errorf("employee 2 of a subunit moves and keeps the end of the closed assignment: %+v", got)
	}
	want := []assignmentdmn.Skipped{{EmployeeID: 3, Reason: reasonInTarget}, {EmployeeID: 4, Reason: reasonDismissed}}
	if len(plan.skipped) != 2 || plan.skipped[0] != want[0] || plan.skipped[1] != want[1] {
		t.Errorf("an employee already in the target and a dismissed one are skipped, got %+v", plan.skipped)
	}

	withPosition := planTransfer(&assignmentdmn.TransferRequest{OrgUnitID: 4, TargetOrgUnitID: 4, StartDate: day("2027-01-01"), PositionID: ptr(int64(9))}, assignments[2:3], employed)
	if len(withPosition.steps) != 1 || withPosition.steps[0].item.PositionID != 9 {
		t.Errorf("a new position makes a move inside the target unit, got %+v", withPosition)
	}
}

func TestRoundMoneyAndFilters(t *testing.T) {
	t.Parallel()

	if roundMoney(165000.004) != 165000 || roundMoney(10.126) != 10.13 {
		t.Errorf("unexpected rounding %v, %v", roundMoney(165000.004), roundMoney(10.126))
	}
	if roundMoney(98765.43*1.1) != 108641.97 {
		t.Errorf("unexpected rounding %v", roundMoney(98765.43*1.1))
	}
	if got := inEffectFilter(day("2027-01-01")); got != `start_date <= "2027-01-01" AND (end_date >= "2027-01-01" OR NOT end_date:*)` {
		t.Errorf("unexpected filter %s", got)
	}
}
