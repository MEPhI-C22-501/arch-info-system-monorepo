package httptr

import (
	"github.com/go-chi/chi/v5"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/health"
)

func NewRouter() *chi.Mux {
	r := chi.NewRouter()

	r.Get("/health", health.NewHandler())

	return r
}
