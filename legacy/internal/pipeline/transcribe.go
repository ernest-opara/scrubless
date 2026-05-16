package pipeline

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

const whisperEndpoint = "https://api.openai.com/v1/audio/transcriptions"

// TranscriptSegment is one timestamped chunk of transcribed speech.
type TranscriptSegment struct {
	Start float64 // seconds from the start of the video
	End   float64
	Text  string
}

// Transcriber turns audio into timestamped text via the OpenAI Whisper API.
// When constructed without an API key it is disabled and yields no transcript,
// letting indexing proceed as visual-only.
type Transcriber struct {
	apiKey     string
	httpClient *http.Client
}

// NewTranscriber returns a Transcriber. An empty apiKey leaves it disabled.
func NewTranscriber(apiKey string) *Transcriber {
	return &Transcriber{
		apiKey:     apiKey,
		httpClient: &http.Client{Timeout: 10 * time.Minute},
	}
}

// Enabled reports whether a Whisper API key is configured.
func (t *Transcriber) Enabled() bool { return t.apiKey != "" }

// Transcribe transcribes a single audio file. timeOffset is added to every
// returned timestamp, so callers can transcribe chunks of a longer recording
// and get timestamps relative to the whole video.
func (t *Transcriber) Transcribe(ctx context.Context, audioPath string, timeOffset float64) ([]TranscriptSegment, error) {
	if !t.Enabled() {
		return nil, nil
	}

	body, contentType, err := t.buildRequest(audioPath)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, whisperEndpoint, body)
	if err != nil {
		return nil, fmt.Errorf("transcribe: build request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+t.apiKey)
	req.Header.Set("Content-Type", contentType)

	resp, err := t.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("transcribe: call whisper: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		msg, _ := io.ReadAll(io.LimitReader(resp.Body, 2<<10))
		return nil, fmt.Errorf("transcribe: whisper status %d: %s", resp.StatusCode, msg)
	}

	var parsed struct {
		Segments []struct {
			Start float64 `json:"start"`
			End   float64 `json:"end"`
			Text  string  `json:"text"`
		} `json:"segments"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&parsed); err != nil {
		return nil, fmt.Errorf("transcribe: decode response: %w", err)
	}

	segments := make([]TranscriptSegment, len(parsed.Segments))
	for i, s := range parsed.Segments {
		segments[i] = TranscriptSegment{
			Start: s.Start + timeOffset,
			End:   s.End + timeOffset,
			Text:  s.Text,
		}
	}
	return segments, nil
}

// buildRequest assembles the multipart body Whisper expects.
func (t *Transcriber) buildRequest(audioPath string) (*bytes.Buffer, string, error) {
	f, err := os.Open(audioPath)
	if err != nil {
		return nil, "", fmt.Errorf("transcribe: open audio: %w", err)
	}
	defer f.Close()

	var buf bytes.Buffer
	mw := multipart.NewWriter(&buf)

	part, err := mw.CreateFormFile("file", filepath.Base(audioPath))
	if err != nil {
		return nil, "", fmt.Errorf("transcribe: form file: %w", err)
	}
	if _, err := io.Copy(part, f); err != nil {
		return nil, "", fmt.Errorf("transcribe: copy audio: %w", err)
	}
	for field, value := range map[string]string{
		"model":           "whisper-1",
		"response_format": "verbose_json",
	} {
		if err := mw.WriteField(field, value); err != nil {
			return nil, "", fmt.Errorf("transcribe: write field %s: %w", field, err)
		}
	}
	if err := mw.Close(); err != nil {
		return nil, "", fmt.Errorf("transcribe: close multipart: %w", err)
	}
	return &buf, mw.FormDataContentType(), nil
}
