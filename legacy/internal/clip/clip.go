// Package clip extracts subclips from a video using ffmpeg.
package clip

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
)

// Extract writes the [start, end) span of sourcePath to outPath as an MP4.
//
// It uses stream copy (no re-encode), so the cut is fast but snaps to the
// nearest keyframe at or before start — precise enough for clip export and
// consistent with the project's cost-optimized design.
func Extract(ctx context.Context, sourcePath, outPath string, start, end float64) error {
	if start < 0 {
		return fmt.Errorf("clip: start %.2f is negative", start)
	}
	if end <= start {
		return fmt.Errorf("clip: end %.2f must be after start %.2f", end, start)
	}
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		return fmt.Errorf("clip: mkdir: %w", err)
	}

	duration := end - start
	cmd := exec.CommandContext(ctx, "ffmpeg",
		"-hide_banner", "-loglevel", "error",
		"-y",
		"-ss", secs(start),
		"-i", sourcePath,
		"-t", secs(duration),
		"-c", "copy",
		outPath,
	)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		if msg := strings.TrimSpace(stderr.String()); msg != "" {
			return fmt.Errorf("clip: ffmpeg: %w: %s", err, msg)
		}
		return fmt.Errorf("clip: ffmpeg: %w", err)
	}
	return nil
}

// secs formats a seconds value for an ffmpeg time argument.
func secs(v float64) string {
	return strconv.FormatFloat(v, 'f', 3, 64)
}
