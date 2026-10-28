package employeehndl

import (
	"net/http"

	"github.com/go-chi/render"

	recordhndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/record"
	employeev1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/employee"
)

// DismissEmployee dismisses the employee on the date of the request body and returns the updated record.
func (h *Handler) DismissEmployee(w http.ResponseWriter, r *http.Request, id employeev1.EmployeeID) {
	var in employeev1.EmployeeDismissal
	if !recordhndl.DecodeJSON(w, r, &in) {
		return
	}

	dismissed, err := h.service.Dismiss(r.Context(), id, in.DismissalDate.Time)
	if err != nil {
		recordhndl.RenderError(w, r, err, singular)
		return
	}

	render.Status(r, http.StatusOK)
	render.JSON(w, r, expandedToAPI(dismissed))
}
