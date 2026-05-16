// Package pipeline orchestrates video indexing: ffmpeg extraction, Whisper
// transcription, CLIP embedding, and ChromaDB storage.
package pipeline

import (
	"context"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/ernest-opara/scrubless/internal/models"
	"github.com/ernest-opara/scrubless/internal/storage"
	"github.com/ernest-opara/scrubless/internal/store"
)

const (
	// processTimeout caps a single video's end-to-end processing.
	processTimeout = 2 * time.Hour
	// audioChunkSec is the length of each transcription audio chunk.
	audioChunkSec = 600
)

// Pipeline runs the indexing stages for an uploaded video.
type Pipeline struct {
	storage     storage.Storage
	videos      store.VideoStore
	ffmpeg      *FFmpeg
	transcriber *Transcriber
	embedder    Embedder
	index       *Index
	workRoot    string // local scratch directory for processing
}

// New constructs a Pipeline. workRoot is created if missing.
func New(st storage.Storage, vs store.VideoStore, ff *FFmpeg, tr *Transcriber, emb Embedder, idx *Index, workRoot string) (*Pipeline, error) {
	if err := os.MkdirAll(workRoot, 0o755); err != nil {
		return nil, fmt.Errorf("pipeline: create work root: %w", err)
	}
	return &Pipeline{
		storage:     st,
		videos:      vs,
		ffmpeg:      ff,
		transcriber: tr,
		embedder:    emb,
		index:       idx,
		workRoot:    workRoot,
	}, nil
}

// Process runs the full indexing pipeline for videoID. It is meant to run in
// its own goroutine: it returns nothing and records any failure on the video
// record as StatusError.
func (p *Pipeline) Process(videoID string) {
	ctx, cancel := context.WithTimeout(context.Background(), processTimeout)
	defer cancel()

	if err := p.process(ctx, videoID); err != nil {
		log.Printf("pipeline: video %s failed: %v", videoID, err)
		p.videos.Update(videoID, func(v *models.Video) {
			v.Status = models.StatusError
			v.ErrorMessage = err.Error()
		})
	}
}

func (p *Pipeline) process(ctx context.Context, videoID string) error {
	video, ok := p.videos.Get(videoID)
	if !ok {
		return fmt.Errorf("unknown video %s", videoID)
	}

	workDir := filepath.Join(p.workRoot, videoID)
	if err := os.MkdirAll(workDir, 0o755); err != nil {
		return fmt.Errorf("create work dir: %w", err)
	}
	defer os.RemoveAll(workDir)

	// Stage 1: get the source onto local disk. Uploads come from storage;
	// YouTube imports are downloaded with yt-dlp and may bring captions.
	localSource, captionsPath, err := p.acquireSource(ctx, video, workDir)
	if err != nil {
		return err
	}

	// Stage 2: probe duration.
	duration, err := p.ffmpeg.Duration(ctx, localSource)
	if err != nil {
		return err
	}
	p.setProgress(videoID, 10, func(v *models.Video) { v.DurationSec = duration })

	// Stage 3: extract frames and store them for thumbnails / enrichment.
	frames, err := p.ffmpeg.ExtractFrames(ctx, localSource, filepath.Join(workDir, "frames"))
	if err != nil {
		return err
	}
	if len(frames) == 0 {
		return fmt.Errorf("no frames extracted")
	}
	p.setProgress(videoID, 25, nil)

	if err := p.storeFrames(ctx, videoID, frames); err != nil {
		return fmt.Errorf("store frames: %w", err)
	}
	p.setProgress(videoID, 40, nil)

	// Stage 4: build the transcript — YouTube captions if present, else Whisper.
	transcript, err := p.buildTranscript(ctx, video, localSource, captionsPath, workDir)
	if err != nil {
		return err
	}
	p.setProgress(videoID, 60, nil)

	// Stage 5: CLIP-embed every frame via the sidecar.
	embeddings, err := p.embedFrames(ctx, frames)
	if err != nil {
		return fmt.Errorf("embed frames: %w", err)
	}
	p.setProgress(videoID, 85, nil)

	// Stage 6: build segments and store them in ChromaDB.
	segments := buildSegments(videoID, frames, duration, transcript)
	if err := p.index.Add(ctx, segments, embeddings); err != nil {
		return err
	}

	p.videos.Update(videoID, func(v *models.Video) {
		v.Status = models.StatusIndexed
		v.ProgressPct = 100
		v.SegmentsIndexed = len(segments)
	})
	log.Printf("pipeline: video %s indexed %d segments (%.0fs, transcript=%t)",
		videoID, len(segments), duration, len(transcript) > 0)
	return nil
}

// acquireSource gets the video's source file onto local disk and returns its
// path plus an optional captions file.
//
// Uploads are pulled from storage. URL imports are downloaded with yt-dlp into
// the work dir and processed from there — the downloaded source is never
// persisted to storage; it is discarded with the work dir once frames and
// embeddings have been extracted. Only frames, embeddings, and metadata are
// kept for an imported video.
func (p *Pipeline) acquireSource(ctx context.Context, video *models.Video, workDir string) (sourcePath, captionsPath string, err error) {
	if video.Kind == models.KindImport {
		p.videos.Update(video.ID, func(v *models.Video) {
			v.Status = models.StatusDownloading
			v.ProgressPct = 4
		})
		res, err := DownloadVideo(ctx, video.ImportURL, workDir)
		if err != nil {
			return "", "", fmt.Errorf("download video: %w", err)
		}
		p.videos.Update(video.ID, func(v *models.Video) {
			v.Status = models.StatusProcessing
			v.ProgressPct = 8
		})
		return res.VideoPath, res.CaptionsPath, nil
	}

	sourcePath = filepath.Join(workDir, "source"+filepath.Ext(video.Filename))
	if err := p.fetchSource(ctx, video.SourceKey, sourcePath); err != nil {
		return "", "", fmt.Errorf("fetch source: %w", err)
	}
	return sourcePath, "", nil
}

// buildTranscript produces transcript segments for a video. Free, instant
// YouTube captions are used when present; otherwise it falls back to the
// Whisper API (itself a no-op without an API key).
func (p *Pipeline) buildTranscript(ctx context.Context, video *models.Video, sourcePath, captionsPath, workDir string) ([]TranscriptSegment, error) {
	if captionsPath != "" {
		segs, err := ParseVTT(captionsPath)
		if err != nil {
			log.Printf("pipeline: video %s: caption parse failed (%v) — falling back to Whisper", video.ID, err)
		} else if len(segs) > 0 {
			log.Printf("pipeline: video %s: using %d YouTube caption segments", video.ID, len(segs))
			return segs, nil
		}
	}
	return p.transcribe(ctx, sourcePath, workDir)
}

// transcribe extracts audio in chunks and transcribes each, returning all
// transcript segments with video-relative timestamps. It returns nil (no
// error) when transcription is disabled.
func (p *Pipeline) transcribe(ctx context.Context, sourcePath, workDir string) ([]TranscriptSegment, error) {
	if !p.transcriber.Enabled() {
		log.Printf("pipeline: no Whisper key — indexing visual-only")
		return nil, nil
	}
	chunks, err := p.ffmpeg.ExtractAudioChunks(ctx, sourcePath, filepath.Join(workDir, "audio"), audioChunkSec)
	if err != nil {
		return nil, err
	}
	var transcript []TranscriptSegment
	for _, ch := range chunks {
		segs, err := p.transcriber.Transcribe(ctx, ch.Path, ch.OffsetSec)
		if err != nil {
			return nil, fmt.Errorf("transcribe chunk at %.0fs: %w", ch.OffsetSec, err)
		}
		transcript = append(transcript, segs...)
	}
	return transcript, nil
}

// embedFrames reads each frame file and CLIP-embeds them as a batch.
func (p *Pipeline) embedFrames(ctx context.Context, frames []Frame) ([][]float32, error) {
	images := make([][]byte, len(frames))
	for i, fr := range frames {
		data, err := os.ReadFile(fr.Path)
		if err != nil {
			return nil, fmt.Errorf("read frame %d: %w", fr.Index, err)
		}
		images[i] = data
	}
	return p.embedder.EmbedImageBatch(ctx, images)
}

// fetchSource copies the stored source object to a local path.
func (p *Pipeline) fetchSource(ctx context.Context, key, dst string) error {
	rc, err := p.storage.Open(ctx, key)
	if err != nil {
		return err
	}
	defer rc.Close()

	f, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer f.Close()
	if _, err := io.Copy(f, rc); err != nil {
		return err
	}
	return nil
}

// storeFrames uploads each extracted frame to storage under the video's
// frame prefix, keyed by extraction index.
func (p *Pipeline) storeFrames(ctx context.Context, videoID string, frames []Frame) error {
	for _, fr := range frames {
		f, err := os.Open(fr.Path)
		if err != nil {
			return err
		}
		key := FrameKey(videoID, fr.Index)
		err = p.storage.Save(ctx, key, f)
		f.Close()
		if err != nil {
			return err
		}
	}
	return nil
}

// setProgress updates a video's progress, optionally applying extra mutations.
func (p *Pipeline) setProgress(videoID string, pct int, extra func(*models.Video)) {
	p.videos.Update(videoID, func(v *models.Video) {
		v.ProgressPct = pct
		if extra != nil {
			extra(v)
		}
	})
}

// buildSegments turns frames into indexable Segments. Each frame defines a
// time window running until the next frame (or the video's end), and carries
// whatever transcript overlaps that window.
func buildSegments(videoID string, frames []Frame, duration float64, transcript []TranscriptSegment) []models.Segment {
	segments := make([]models.Segment, len(frames))
	for i, fr := range frames {
		end := duration
		if i+1 < len(frames) {
			end = frames[i+1].TimestampSec
		}
		segments[i] = models.Segment{
			VideoID:        videoID,
			Index:          fr.Index,
			TimestampStart: fr.TimestampSec,
			TimestampEnd:   end,
			FrameKey:       FrameKey(videoID, fr.Index),
			TranscriptText: transcriptForWindow(transcript, fr.TimestampSec, end),
		}
	}
	return segments
}

// transcriptForWindow joins the text of every transcript segment overlapping
// the half-open window [start, end).
func transcriptForWindow(transcript []TranscriptSegment, start, end float64) string {
	var parts []string
	for _, ts := range transcript {
		if ts.Start < end && ts.End > start {
			if t := strings.TrimSpace(ts.Text); t != "" {
				parts = append(parts, t)
			}
		}
	}
	return strings.Join(parts, " ")
}

// FrameKey is the storage key for a video's nth extracted frame.
func FrameKey(videoID string, index int) string {
	return fmt.Sprintf("videos/%s/frames/frame_%04d.jpg", videoID, index)
}

// Index exposes the segment index so the API layer can search and delete.
func (p *Pipeline) Index() *Index { return p.index }

// DeleteIndex removes a video's segments from the vector index.
func (p *Pipeline) DeleteIndex(ctx context.Context, videoID string) error {
	return p.index.DeleteVideo(ctx, videoID)
}
