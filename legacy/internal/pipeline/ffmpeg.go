package pipeline

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

// Frame is one extracted video frame and the source timestamp it represents.
type Frame struct {
	Index        int     // 1-based extraction order
	TimestampSec float64 // approximate source time of the frame
	Path         string  // local filesystem path to the JPEG
}

// FFmpeg wraps the ffmpeg / ffprobe command-line tools.
type FFmpeg struct {
	frameInterval int // seconds between extracted frames
}

// NewFFmpeg returns an FFmpeg helper extracting one frame every
// frameInterval seconds. A non-positive interval falls back to 5s.
func NewFFmpeg(frameInterval int) *FFmpeg {
	if frameInterval <= 0 {
		frameInterval = 5
	}
	return &FFmpeg{frameInterval: frameInterval}
}

// Duration returns the length of the video at inputPath, in seconds.
func (f *FFmpeg) Duration(ctx context.Context, inputPath string) (float64, error) {
	cmd := exec.CommandContext(ctx, "ffprobe",
		"-v", "error",
		"-show_entries", "format=duration",
		"-of", "default=noprint_wrappers=1:nokey=1",
		inputPath,
	)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	out, err := cmd.Output()
	if err != nil {
		return 0, fmt.Errorf("ffprobe duration: %w", withStderr(err, stderr.String()))
	}
	secs, err := strconv.ParseFloat(strings.TrimSpace(string(out)), 64)
	if err != nil {
		return 0, fmt.Errorf("ffprobe duration: parse %q: %w", out, err)
	}
	return secs, nil
}

// ExtractFrames writes one JPEG every frameInterval seconds into outDir and
// returns them ordered by timestamp. outDir is created if missing.
func (f *FFmpeg) ExtractFrames(ctx context.Context, inputPath, outDir string) ([]Frame, error) {
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return nil, fmt.Errorf("extract frames: mkdir: %w", err)
	}
	pattern := filepath.Join(outDir, "frame_%04d.jpg")
	err := run(exec.CommandContext(ctx, "ffmpeg",
		"-hide_banner", "-loglevel", "error",
		"-i", inputPath,
		"-vf", fmt.Sprintf("fps=1/%d", f.frameInterval),
		"-q:v", "2",
		pattern,
	))
	if err != nil {
		return nil, fmt.Errorf("extract frames: %w", err)
	}

	matches, err := filepath.Glob(filepath.Join(outDir, "frame_*.jpg"))
	if err != nil {
		return nil, fmt.Errorf("extract frames: glob: %w", err)
	}
	sort.Strings(matches)

	frames := make([]Frame, len(matches))
	for i, path := range matches {
		frames[i] = Frame{
			Index:        i + 1,
			TimestampSec: float64(i * f.frameInterval),
			Path:         path,
		}
	}
	return frames, nil
}

// AudioChunk is one segment of extracted audio plus its offset (seconds) from
// the start of the video.
type AudioChunk struct {
	Path      string
	OffsetSec float64
}

// ExtractAudioChunks extracts the audio track as 16kHz mono MP3 split into
// chunkSec-long files. Chunking keeps each file well under the Whisper API's
// 25MB upload limit regardless of video length. Chunks are returned in order.
func (f *FFmpeg) ExtractAudioChunks(ctx context.Context, inputPath, outDir string, chunkSec int) ([]AudioChunk, error) {
	if chunkSec <= 0 {
		chunkSec = 600
	}
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return nil, fmt.Errorf("extract audio: mkdir: %w", err)
	}
	pattern := filepath.Join(outDir, "audio_%03d.mp3")
	err := run(exec.CommandContext(ctx, "ffmpeg",
		"-hide_banner", "-loglevel", "error",
		"-y",
		"-i", inputPath,
		"-vn",
		"-acodec", "libmp3lame",
		"-ar", "16000",
		"-ac", "1",
		"-b:a", "64k",
		"-f", "segment",
		"-segment_time", strconv.Itoa(chunkSec),
		pattern,
	))
	if err != nil {
		return nil, fmt.Errorf("extract audio: %w", err)
	}

	matches, err := filepath.Glob(filepath.Join(outDir, "audio_*.mp3"))
	if err != nil {
		return nil, fmt.Errorf("extract audio: glob: %w", err)
	}
	sort.Strings(matches)

	chunks := make([]AudioChunk, len(matches))
	for i, path := range matches {
		chunks[i] = AudioChunk{Path: path, OffsetSec: float64(i * chunkSec)}
	}
	return chunks, nil
}

// run executes cmd, folding any stderr output into the returned error.
func run(cmd *exec.Cmd) error {
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return withStderr(err, stderr.String())
	}
	return nil
}

// withStderr appends trimmed stderr text to err when present.
func withStderr(err error, stderr string) error {
	if s := strings.TrimSpace(stderr); s != "" {
		return fmt.Errorf("%w: %s", err, s)
	}
	return err
}
