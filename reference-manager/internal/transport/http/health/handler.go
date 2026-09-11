package health

import (
	"encoding/json"
	"net/http"
)

func NewHandler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		w.WriteHeader(http.StatusOK)

		response := map[string]string{"status": "READY"}
		_ = json.NewEncoder(w).Encode(response)
	}
}
