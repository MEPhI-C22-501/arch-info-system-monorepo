package salaryhndl

import (
	"net/http"

	"github.com/go-chi/render"
	openapi_types "github.com/oapi-codegen/runtime/types"

	salarydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/salary"
	recordhndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/record"
	salaryv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/salary"
)

// ReviseSalaries applies or, with validate_only, plans a group change of the salaries of the employees of an org
// unit from one date (FR-RM-63).
func (h *Handler) ReviseSalaries(w http.ResponseWriter, r *http.Request) {
	var in salaryv1.GroupSalaryChange
	if !recordhndl.DecodeJSON(w, r, &in) {
		return
	}

	result, err := h.service.Revise(r.Context(), &salarydmn.GroupChangeRequest{
		OrgUnitID:       in.OrgUnitId,
		IncludeSubunits: recordhndl.ValueOrZero(in.IncludeSubunits),
		StartDate:       in.StartDate.Time,
		Percent:         in.Percent,
		Amount:          in.Amount,
		CurrencyID:      in.CurrencyId,
		ValidateOnly:    recordhndl.ValueOrZero(in.ValidateOnly),
	})
	if err != nil {
		recordhndl.RenderError(w, r, err, singular)
		return
	}

	render.Status(r, http.StatusOK)
	render.JSON(w, r, groupChangeToAPI(result))
}

func groupChangeToAPI(m *salarydmn.GroupChangeResult) salaryv1.GroupSalaryChangeResult {
	resp := salaryv1.GroupSalaryChangeResult{
		ValidateOnly: m.ValidateOnly,
		Items:        make([]salaryv1.GroupSalaryChangeItem, 0, len(m.Items)),
		Skipped:      make([]salaryv1.SkippedEmployee, 0, len(m.Skipped)),
	}

	for _, item := range m.Items {
		apiItem := salaryv1.GroupSalaryChangeItem{
			EmployeeId:     item.EmployeeID,
			ClosedSalaryId: item.ClosedSalaryID,
			PreviousAmount: item.PreviousAmount,
			SalaryId:       item.SalaryID,
			Amount:         item.Amount,
			CurrencyId:     item.CurrencyID,
			StartDate:      openapi_types.Date{Time: item.StartDate},
		}
		if item.EndDate != nil {
			apiItem.EndDate = &openapi_types.Date{Time: *item.EndDate}
		}

		resp.Items = append(resp.Items, apiItem)
	}

	for _, s := range m.Skipped {
		resp.Skipped = append(resp.Skipped, salaryv1.SkippedEmployee{EmployeeId: s.EmployeeID, Reason: s.Reason})
	}

	return resp
}
