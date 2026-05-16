package api

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/ernest-opara/scrubless/internal/clip"
	"github.com/ernest-opara/scrubless/internal/config"
	"github.com/ernest-opara/scrubless/internal/models"
	"github.com/ernest-opara/scrubless/internal/pipeline"
	"github.com/ernest-opara/scrubless/internal/search"
	"github.com/ernest-opara/scrubless/internal/storage"
	"github.com/ernest-opara/scrubless/internal/store"

	"github.com/go-chi/chi/v5"
)

// maxUploadBytes caps an uploaded video. Generous: a 2-hour video is allowed.
const maxUploadBytes = 10 << 30 // 10 GiB

// acceptedVideoExt is the set of container extensions the API accepts.
var acceptedVideoExt = map[string]bool{
	".mp4": true, ".mov": true, ".mkv": true,
	".webm": true, ".avi": true, ".m4v": true,
}

// Handler holds the dependencies shared by all HTTP handlers.
type Handler struct {
	cfg      config.Config
	storage  storage.Storage
	videos   store.VideoStore
	pipeline *pipeline.Pipeline
	searcher *search.Searcher
}

// NewHandler wires the API handlers to their dependencies.
func NewHandler(cfg config.Config, st storage.Storage, vs store.VideoStore, p *pipeline.Pipeline, s *search.Searcher) *Handler {
	return &Handler{cfg: cfg, storage: st, videos: vs, pipeline: p, searcher: s}
}

// Upload handles POST /api/videos/upload. It stores the uploaded file, creates
// a video record, and kicks off async processing.
func (h *Handler) Upload(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, maxUploadBytes)
	if err := r.ParseMultipartForm(32 << 20); err != nil {
		writeError(w, http.StatusBadRequest, "could not parse upload: "+err.Error())
		return
	}

	file, header, err := r.FormFile("file")
	if err != nil {
		writeError(w, http.StatusBadRequest, `missing "file" form field`)
		return
	}
	defer file.Close()

	ext := strings.ToLower(filepath.Ext(header.Filename))
	if !acceptedVideoExt[ext] {
		writeError(w, http.StatusBadRequest, fmt.Sprintf("unsupported video type %q", ext))
		return
	}

	id := newID()
	sourceKey := fmt.Sprintf("videos/%s/source%s", id, ext)
	if err := h.storage.Save(r.Context(), sourceKey, file); err != nil {
		writeError(w, http.StatusInternalServerError, "failed to store video: "+err.Error())
		return
	}

	video := &models.Video{
		ID:          id,
		Kind:        models.KindUpload,
		Title:       header.Filename,
		Filename:    header.Filename,
		Status:      models.StatusProcessing,
		ProgressPct: 0,
		SourceKey:   sourceKey,
		CreatedAt:   time.Now().UTC(),
	}
	h.videos.Create(video)

	// Process asynchronously; the client polls /status for progress.
	go h.pipeline.Process(id)

	log.Printf("api: accepted upload %s (%s)", id, header.Filename)
	writeJSON(w, http.StatusAccepted, map[string]any{
		"id":     id,
		"status": video.Status,
	})
}

// Import handles POST /api/videos/import. It imports a video from any video
// URL (YouTube, Vimeo, a direct file link, … — anything yt-dlp supports):
// metadata is read inline so the response carries a title, then the download
// and indexing run asynchronously.
func (h *Handler) Import(w http.ResponseWriter, r *http.Request) {
	var req struct {
		URL string `json:"url"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}
	url := strings.TrimSpace(req.URL)
	if url == "" {
		writeError(w, http.StatusBadRequest, `"url" is required`)
		return
	}
	if !strings.HasPrefix(url, "http://") && !strings.HasPrefix(url, "https://") {
		writeError(w, http.StatusBadRequest, "url must start with http:// or https://")
		return
	}

	// Read metadata inline so the response can show the title right away.
	metaCtx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()
	meta, err := pipeline.FetchVideoMetadata(metaCtx, url)
	if err != nil {
		writeError(w, http.StatusBadGateway, "could not read a video at that URL: "+err.Error())
		return
	}

	id := newID()
	video := &models.Video{
		ID:           id,
		Kind:         models.KindImport,
		Title:        meta.Title,
		Status:       models.StatusDownloading,
		DurationSec:  meta.DurationSec,
		ThumbnailURL: meta.ThumbnailURL,
		ImportURL:    url,
		CreatedAt:    time.Now().UTC(),
	}
	h.videos.Create(video)

	// Download + index asynchronously; the client polls /status for progress.
	go h.pipeline.Process(id)

	log.Printf("api: accepted url import %s (%q)", id, meta.Title)
	writeJSON(w, http.StatusAccepted, map[string]any{
		"id":       id,
		"status":   video.Status,
		"title":    meta.Title,
		"duration": meta.DurationSec,
	})
}

// Status handles GET /api/videos/{id}/status.
func (h *Handler) Status(w http.ResponseWriter, r *http.Request) {
	video, ok := h.videos.Get(chi.URLParam(r, "id"))
	if !ok {
		writeError(w, http.StatusNotFound, "video not found")
		return
	}
	// A URL to the source video so the player can load it. YouTube imports
	// keep no stored source — the frontend embeds the YouTube player instead.
	var sourceURL string
	if video.SourceKey != "" {
		u, err := h.storage.URL(r.Context(), video.SourceKey)
		if err != nil {
			log.Printf("api: source url for %s: %v", video.ID, err)
		}
		sourceURL = u
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"status":           video.Status,
		"progress_pct":     video.ProgressPct,
		"segments_indexed": video.SegmentsIndexed,
		"duration_sec":     video.DurationSec,
		"error_message":    video.ErrorMessage,
		"source_url":       sourceURL,
		"import_url":       video.ImportURL,
		"kind":             video.Kind,
		"title":            video.Title,
		"thumbnail_url":    video.ThumbnailURL,
	})
}

// ListVideos handles GET /api/videos.
func (h *Handler) ListVideos(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, h.videos.List())
}

// DeleteVideo handles DELETE /api/videos/{id}. It removes the record and the
// stored source plus frames. Index data is removed once ChromaDB is wired in.
func (h *Handler) DeleteVideo(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	video, ok := h.videos.Get(id)
	if !ok {
		writeError(w, http.StatusNotFound, "video not found")
		return
	}

	ctx := r.Context()
	if video.SourceKey != "" {
		if err := h.storage.Delete(ctx, video.SourceKey); err != nil {
			log.Printf("api: delete %s source: %v", id, err)
		}
	}
	for i := 1; i <= video.SegmentsIndexed; i++ {
		if err := h.storage.Delete(ctx, pipeline.FrameKey(id, i)); err != nil {
			log.Printf("api: delete %s frame %d: %v", id, i, err)
		}
	}
	if err := h.pipeline.DeleteIndex(ctx, id); err != nil {
		log.Printf("api: delete %s from index: %v", id, err)
	}
	h.videos.Delete(id)

	w.WriteHeader(http.StatusNoContent)
}

// Search handles POST /api/videos/{id}/search. It runs a natural-language
// query against the video's indexed segments.
func (h *Handler) Search(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	video, ok := h.videos.Get(id)
	if !ok {
		writeError(w, http.StatusNotFound, "video not found")
		return
	}
	if video.Status != models.StatusIndexed {
		writeError(w, http.StatusConflict,
			fmt.Sprintf("video is not searchable yet (status: %s)", video.Status))
		return
	}

	var req struct {
		Query string `json:"query"`
		Limit int    `json:"limit"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}
	if strings.TrimSpace(req.Query) == "" {
		writeError(w, http.StatusBadRequest, `"query" is required`)
		return
	}

	results, err := h.searcher.Search(r.Context(), id, req.Query, req.Limit)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "search failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, results)
}

// Segments handles GET /api/videos/{id}/segments — a debug/browse listing of
// every indexed segment.
func (h *Handler) Segments(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if _, ok := h.videos.Get(id); !ok {
		writeError(w, http.StatusNotFound, "video not found")
		return
	}
	segments, err := h.pipeline.Index().ListSegments(r.Context(), id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "failed to list segments: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, segments)
}

// Clip handles POST /api/videos/{id}/clip. It trims the requested time span
// out of the source video and returns a URL to the exported clip.
func (h *Handler) Clip(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	video, ok := h.videos.Get(id)
	if !ok {
		writeError(w, http.StatusNotFound, "video not found")
		return
	}
	// Imported videos are processed then discarded — there is no stored
	// source to trim, so clip export is uploads-only.
	if video.Kind == models.KindImport {
		writeError(w, http.StatusConflict,
			"clip export is available for uploaded videos only")
		return
	}

	var req struct {
		Start float64 `json:"start"`
		End   float64 `json:"end"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}
	if req.Start < 0 || req.End <= req.Start {
		writeError(w, http.StatusBadRequest, "require 0 <= start < end")
		return
	}
	end := req.End
	if video.DurationSec > 0 {
		if req.Start >= video.DurationSec {
			writeError(w, http.StatusBadRequest, "start is beyond the end of the video")
			return
		}
		end = min(end, video.DurationSec) // clamp to the video's length
	}

	ctx := r.Context()
	tmpDir, err := os.MkdirTemp("", "scrubless-clip-*")
	if err != nil {
		writeError(w, http.StatusInternalServerError, "clip export failed: "+err.Error())
		return
	}
	defer os.RemoveAll(tmpDir)

	// Pull the source local for ffmpeg (storage may be S3).
	localSource := filepath.Join(tmpDir, "source"+filepath.Ext(video.Filename))
	if err := h.fetchToFile(ctx, video.SourceKey, localSource); err != nil {
		writeError(w, http.StatusInternalServerError, "could not load source video: "+err.Error())
		return
	}

	localClip := filepath.Join(tmpDir, "clip.mp4")
	if err := clip.Extract(ctx, localSource, localClip, req.Start, end); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	clipKey := fmt.Sprintf("videos/%s/clips/%s.mp4", id, newID())
	cf, err := os.Open(localClip)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "clip export failed: "+err.Error())
		return
	}
	err = h.storage.Save(ctx, clipKey, cf)
	cf.Close()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not store clip: "+err.Error())
		return
	}

	clipURL, err := h.storage.URL(ctx, clipKey)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "could not build clip url: "+err.Error())
		return
	}
	log.Printf("api: exported clip %s [%.1f-%.1f]s", id, req.Start, end)
	writeJSON(w, http.StatusOK, map[string]any{
		"clip_url": clipURL,
		"duration": end - req.Start,
	})
}

// fetchToFile copies a stored object to a local file path.
func (h *Handler) fetchToFile(ctx context.Context, key, dst string) error {
	rc, err := h.storage.Open(ctx, key)
	if err != nil {
		return err
	}
	defer rc.Close()

	f, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = io.Copy(f, rc)
	return err
}

// newID returns a random 16-character hex identifier.
func newID() string {
	var b [8]byte
	if _, err := rand.Read(b[:]); err != nil {
		// crypto/rand failing is unrecoverable; fall back to a timestamp.
		return fmt.Sprintf("%016x", time.Now().UnixNano())
	}
	return hex.EncodeToString(b[:])
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(body); err != nil {
		log.Printf("api: encode response: %v", err)
	}
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}
