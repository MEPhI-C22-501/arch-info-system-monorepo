package health

import "net/http"

type Handler struct {
}

func NewHandler() *Handler {
	return &Handler{}
}

func (h *Handler) GetLiveness(w http.ResponseWriter, _ *http.Request) {
	w.WriteHeader(http.StatusOK)
}

func (h *Handler) GetReadiness(w http.ResponseWriter, _ *http.Request) {
	w.WriteHeader(http.StatusOK)
}
