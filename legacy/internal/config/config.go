// Package config loads Scrubless's runtime configuration from environment
// variables, applying the defaults documented in CLAUDE.md.
package config

import (
	"os"
	"strconv"
)

// Config holds all runtime settings for the server.
type Config struct {
	Port string

	// Storage selects where videos, frames, and clips live.
	StorageBackend string // "local" or "s3"
	StoragePath    string // filesystem root for the local backend
	S3Bucket       string
	AWSRegion      string

	// Service dependencies.
	ChromaURL      string
	ClipSidecarURL string

	// API keys.
	AnthropicAPIKey string
	OpenAIAPIKey    string

	// Pipeline tuning.
	FrameInterval    int // seconds between extracted frames
	MaxVideoDuration int // max accepted video length, seconds
	EnrichTopN       int // search results enriched with Claude Vision
}

// Load reads configuration from the environment, falling back to defaults.
func Load() Config {
	return Config{
		Port:             env("PORT", "8080"),
		StorageBackend:   env("STORAGE_BACKEND", "local"),
		StoragePath:      env("STORAGE_PATH", "./storage"),
		S3Bucket:         env("AWS_S3_BUCKET", ""),
		AWSRegion:        env("AWS_REGION", "us-east-1"),
		ChromaURL:        env("CHROMA_URL", "http://localhost:8000"),
		ClipSidecarURL:   env("CLIP_SIDECAR_URL", "http://localhost:8100"),
		AnthropicAPIKey:  env("ANTHROPIC_API_KEY", ""),
		OpenAIAPIKey:     env("OPENAI_API_KEY", ""),
		FrameInterval:    envInt("FRAME_INTERVAL", 5),
		MaxVideoDuration: envInt("MAX_VIDEO_DURATION", 7200),
		EnrichTopN:       envInt("ENRICH_TOP_N", 5),
	}
}

func env(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func envInt(key string, def int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}
