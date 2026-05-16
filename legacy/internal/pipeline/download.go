package pipeline

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// VideoMeta is the metadata yt-dlp reports for a video URL.
type VideoMeta struct {
	ID           string
	Title        string
	DurationSec  float64
	ThumbnailURL string
}

// DownloadResult is what DownloadVideo produced on local disk.
type DownloadResult struct {
	VideoPath    string // local path to the downloaded video
	CaptionsPath string // local path to the .vtt captions, or "" if none
}

// videoExts are the container extensions yt-dlp may produce for the video.
var videoExts = map[string]bool{
	".mp4": true, ".mkv": true, ".webm": true, ".m4v": true, ".mov": true,
}

// FetchVideoMetadata reads a URL's metadata via `yt-dlp --dump-json`, without
// downloading any media. yt-dlp supports ~1800 sites plus direct video files,
// so this works for any public, non-DRM video URL.
func FetchVideoMetadata(ctx context.Context, url string) (VideoMeta, error) {
	cmd := exec.CommandContext(ctx, "yt-dlp",
		"--dump-json", "--no-warnings", "--no-playlist", url)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return VideoMeta{}, fmt.Errorf("yt-dlp metadata: %w: %s", err, strings.TrimSpace(stderr.String()))
	}

	var j struct {
		ID        string  `json:"id"`
		Title     string  `json:"title"`
		Duration  float64 `json:"duration"`
		Thumbnail string  `json:"thumbnail"`
	}
	if err := json.Unmarshal(stdout.Bytes(), &j); err != nil {
		return VideoMeta{}, fmt.Errorf("yt-dlp metadata: decode: %w", err)
	}
	if j.ID == "" {
		return VideoMeta{}, fmt.Errorf("yt-dlp metadata: no video found at %s", url)
	}
	title := j.Title
	if title == "" {
		title = "Untitled video"
	}
	return VideoMeta{
		ID:           j.ID,
		Title:        title,
		DurationSec:  j.Duration,
		ThumbnailURL: j.Thumbnail,
	}, nil
}

// DownloadVideo downloads a video URL (capped at 720p) into destDir, then
// best-effort fetches its English captions. The video download is required;
// caption failure (rate limits, no captions) is logged and non-fatal — the
// pipeline simply falls back to Whisper.
func DownloadVideo(ctx context.Context, url, destDir string) (DownloadResult, error) {
	if err := os.MkdirAll(destDir, 0o755); err != nil {
		return DownloadResult{}, fmt.Errorf("yt-dlp: mkdir: %w", err)
	}

	// 1. Download the video itself (required).
	cmd := exec.CommandContext(ctx, "yt-dlp",
		"-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
		"--merge-output-format", "mp4",
		"--no-playlist", "--no-warnings", "--retries", "3",
		"-o", filepath.Join(destDir, "source.%(ext)s"),
		url,
	)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return DownloadResult{}, fmt.Errorf("yt-dlp download: %w: %s", err, strings.TrimSpace(stderr.String()))
	}

	res := DownloadResult{VideoPath: findVideoFile(destDir)}
	if res.VideoPath == "" {
		return DownloadResult{}, fmt.Errorf("yt-dlp download: no video file produced")
	}

	// 2. Best-effort English captions, in a separate call so a failure here
	// (often a site rate limit) never sinks the whole import.
	res.CaptionsPath = fetchCaptions(ctx, url, destDir)
	return res, nil
}

// findVideoFile returns the downloaded source video in destDir, or "".
func findVideoFile(destDir string) string {
	matches, _ := filepath.Glob(filepath.Join(destDir, "source.*"))
	for _, p := range matches {
		if videoExts[strings.ToLower(filepath.Ext(p))] {
			return p
		}
	}
	return ""
}

// fetchCaptions tries to download English captions as a .vtt, returning its
// path or "" if none could be fetched. Most useful for YouTube; harmless
// elsewhere.
func fetchCaptions(ctx context.Context, url, destDir string) string {
	cmd := exec.CommandContext(ctx, "yt-dlp",
		"--write-auto-subs", "--write-subs",
		"--sub-langs", "en,en-orig", "--sub-format", "vtt",
		"--skip-download", "--no-playlist", "--no-warnings",
		"-o", filepath.Join(destDir, "source.%(ext)s"),
		url,
	)
	if err := cmd.Run(); err != nil {
		log.Printf("yt-dlp captions: %v — continuing without captions", err)
		return ""
	}
	matches, _ := filepath.Glob(filepath.Join(destDir, "source*.vtt"))
	if len(matches) > 0 {
		return matches[0]
	}
	return ""
}
