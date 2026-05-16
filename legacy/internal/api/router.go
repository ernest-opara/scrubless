package api

import (
	"net/http"

	"github.com/ernest-opara/scrubless/internal/config"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
)

// NewRouter builds the HTTP router: middleware stack, API routes, and — for
// the local storage backend — a static file server for frames and clips.
func NewRouter(h *Handler, cfg config.Config) http.Handler {
	r := chi.NewRouter()

	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(corsMiddleware)

	r.Get("/health", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})

	r.Route("/api", func(r chi.Router) {
		r.Get("/videos", h.ListVideos)
		r.Post("/videos/upload", h.Upload)
		r.Post("/videos/import", h.Import)
		r.Get("/videos/{id}/status", h.Status)
		r.Delete("/videos/{id}", h.DeleteVideo)
		r.Post("/videos/{id}/search", h.Search)
		r.Get("/videos/{id}/segments", h.Segments)
		r.Post("/videos/{id}/clip", h.Clip)
	})

	// In dev, serve stored frames/clips so the frontend can load thumbnails.
	// In prod (S3) the storage layer hands out presigned URLs instead.
	if cfg.StorageBackend == "local" || cfg.StorageBackend == "" {
		fs := http.FileServer(http.Dir(cfg.StoragePath))
		r.Handle("/storage/*", http.StripPrefix("/storage/", fs))
	}

	return r
}
