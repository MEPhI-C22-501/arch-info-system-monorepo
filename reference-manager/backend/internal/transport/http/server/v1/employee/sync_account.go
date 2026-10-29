package employeehndl

import (
	"net/http"

	"github.com/go-chi/render"

	recordhndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/record"
	employeev1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/employee"
)

// SyncEmployeeAccount repeats the pending operation with the Keycloak account of the employee and returns the record.
func (h *Handler) SyncEmployeeAccount(w http.ResponseWriter, r *http.Request, id employeev1.EmployeeID) {
	synced, err := h.service.SyncAccount(r.Context(), id)
	if err != nil {
		recordhndl.RenderError(w, r, err, singular)
		return
	}

	render.Status(r, http.StatusOK)
	render.JSON(w, r, expandedToAPI(synced))
}
