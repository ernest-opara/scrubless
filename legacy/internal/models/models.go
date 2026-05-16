// Package models holds the shared domain types passed between the API,
// pipeline, and search layers.
package models

import "time"

// ProcessingStatus is the lifecycle state of a video.
type ProcessingStatus string

const (
	StatusDownloading ProcessingStatus = "downloading" // fetching a YouTube source
	StatusProcessing  ProcessingStatus = "processing"  // indexing pipeline running
	StatusIndexed     ProcessingStatus = "indexed"     // searchable
	StatusError       ProcessingStatus = "error"
)

// VideoKind is how a video entered Scrubless.
type VideoKind string

const (
	KindUpload VideoKind = "upload" // a user-uploaded file
	KindImport VideoKind = "import" // downloaded from a video URL
)

// Video is a video and the state of its indexing pipeline.
type Video struct {
	ID              string           `json:"id"`
	Kind            VideoKind        `json:"kind"`
	Title           string           `json:"title"`
	Filename        string           `json:"filename,omitempty"`
	Status          ProcessingStatus `json:"status"`
	ProgressPct     int              `json:"progress_pct"`
	SegmentsIndexed int              `json:"segments_indexed"`
	DurationSec     float64          `json:"duration_sec"`
	ErrorMessage    string           `json:"error_message,omitempty"`
	CreatedAt       time.Time        `json:"created_at"`

	// ThumbnailURL is a poster image, when the source provides one.
	ThumbnailURL string `json:"thumbnail_url,omitempty"`
	// ImportURL is the original video URL, set only when Kind == KindImport.
	// It is exposed so the frontend can play the video from its origin —
	// imported videos are processed then discarded, never stored by us.
	ImportURL string `json:"import_url,omitempty"`
	// SourceKey is the storage key of the source video file. Empty for
	// imports, whose source is discarded after processing.
	SourceKey string `json:"-"`
}

// Segment is one indexed time window of a video: a frame plus the transcript
// that overlaps it. Segments are what search matches against.
type Segment struct {
	VideoID        string  `json:"video_id"`
	Index          int     `json:"index"`
	TimestampStart float64 `json:"timestamp_start"`
	TimestampEnd   float64 `json:"timestamp_end"`
	FrameKey       string  `json:"frame_key"`       // storage key of the frame image
	TranscriptText string  `json:"transcript_text"` // transcript overlapping this window
}

// SearchResult is one ranked match returned from a query, optionally enriched
// with a Claude Vision description.
type SearchResult struct {
	TimestampStart    float64 `json:"timestamp_start"`
	TimestampEnd      float64 `json:"timestamp_end"`
	ThumbnailURL      string  `json:"thumbnail_url"`
	Score             float64 `json:"score"`
	Description       string  `json:"description"`
	TranscriptSnippet string  `json:"transcript_snippet"`
}
