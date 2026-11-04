package assignmenthndl

import (
	"net/http"

	"github.com/go-chi/render"
	openapi_types "github.com/oapi-codegen/runtime/types"

	assignmentdmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/assignment"
	recordhndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/record"
	assignmentv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/assignment"
)

// TransferAssignments applies or, with validate_only, plans the transfer of the employees of an org unit to another
// unit from one date (FR-RM-64).
func (h *Handler) TransferAssignments(w http.ResponseWriter, r *http.Request) {
	var in assignmentv1.AssignmentTransfer
	if !recordhndl.DecodeJSON(w, r, &in) {
		return
	}

	result, err := h.service.Transfer(r.Context(), &assignmentdmn.TransferRequest{
		OrgUnitID:       in.OrgUnitId,
		TargetOrgUnitID: in.TargetOrgUnitId,
		IncludeSubunits: recordhndl.ValueOrZero(in.IncludeSubunits),
		StartDate:       in.StartDate.Time,
		PositionID:      in.PositionId,
		ValidateOnly:    recordhndl.ValueOrZero(in.ValidateOnly),
	})
	if err != nil {
		recordhndl.RenderError(w, r, err, singular)
		return
	}

	render.Status(r, http.StatusOK)
	render.JSON(w, r, transferToAPI(result))
}

func transferToAPI(m *assignmentdmn.TransferResult) assignmentv1.AssignmentTransferResult {
	resp := assignmentv1.AssignmentTransferResult{
		ValidateOnly: m.ValidateOnly,
		Items:        make([]assignmentv1.AssignmentTransferItem, 0, len(m.Items)),
		Skipped:      make([]assignmentv1.SkippedEmployee, 0, len(m.Skipped)),
	}

	for _, item := range m.Items {
		apiItem := assignmentv1.AssignmentTransferItem{
			EmployeeId:         item.EmployeeID,
			ClosedAssignmentId: item.ClosedAssignmentID,
			OrgUnitId:          item.FromOrgUnitID,
			AssignmentId:       item.AssignmentID,
			TargetOrgUnitId:    item.TargetOrgUnitID,
			PositionId:         item.PositionID,
			StartDate:          openapi_types.Date{Time: item.StartDate},
		}
		if item.EndDate != nil {
			apiItem.EndDate = &openapi_types.Date{Time: *item.EndDate}
		}

		resp.Items = append(resp.Items, apiItem)
	}

	for _, s := range m.Skipped {
		resp.Skipped = append(resp.Skipped, assignmentv1.SkippedEmployee{EmployeeId: s.EmployeeID, Reason: s.Reason})
	}

	return resp
}
