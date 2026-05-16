// Command server is the Scrubless HTTP API entry point.
package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/ernest-opara/scrubless/internal/api"
	"github.com/ernest-opara/scrubless/internal/config"
	"github.com/ernest-opara/scrubless/internal/pipeline"
	"github.com/ernest-opara/scrubless/internal/search"
	"github.com/ernest-opara/scrubless/internal/storage"
	"github.com/ernest-opara/scrubless/internal/store"
)

func main() {
	cfg := config.Load()
	ctx := context.Background()

	st, err := storage.New(ctx, storage.Config{
		Backend:      cfg.StorageBackend,
		LocalPath:    cfg.StoragePath,
		LocalBaseURL: "/storage",
		S3Bucket:     cfg.S3Bucket,
		S3Region:     cfg.AWSRegion,
	})
	if err != nil {
		log.Fatalf("storage init: %v", err)
	}

	videos := store.NewMemory()
	ff := pipeline.NewFFmpeg(cfg.FrameInterval)
	transcriber := pipeline.NewTranscriber(cfg.OpenAIAPIKey)
	embedder := pipeline.NewCLIPEmbedder(cfg.ClipSidecarURL)

	index, err := pipeline.NewIndex(ctx, cfg.ChromaURL)
	if err != nil {
		log.Fatalf("chromadb index init: %v", err)
	}

	workRoot := filepath.Join(os.TempDir(), "scrubless-work")
	pipe, err := pipeline.New(st, videos, ff, transcriber, embedder, index, workRoot)
	if err != nil {
		log.Fatalf("pipeline init: %v", err)
	}

	enricher := search.NewEnricher(cfg.AnthropicAPIKey)
	searcher := search.New(embedder, index, enricher, st, cfg.EnrichTopN)

	handler := api.NewHandler(cfg, st, videos, pipe, searcher)
	router := api.NewRouter(handler, cfg)

	srv := &http.Server{
		Addr:    ":" + cfg.Port,
		Handler: router,
		// Uploads can be large and slow, so no overall Read/Write timeout;
		// ReadHeaderTimeout still guards against slow-header attacks.
		ReadHeaderTimeout: 10 * time.Second,
		IdleTimeout:       120 * time.Second,
	}

	// Run the server until an interrupt signal arrives.
	errCh := make(chan error, 1)
	go func() {
		log.Printf("scrubless server listening on :%s (storage=%s)", cfg.Port, cfg.StorageBackend)
		errCh <- srv.ListenAndServe()
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)

	select {
	case err := <-errCh:
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("server error: %v", err)
		}
	case sig := <-stop:
		log.Printf("received %s, shutting down", sig)
		shutdownCtx, cancel := context.WithTimeout(ctx, 15*time.Second)
		defer cancel()
		if err := srv.Shutdown(shutdownCtx); err != nil {
			log.Fatalf("graceful shutdown failed: %v", err)
		}
		log.Println("server stopped")
	}
}
