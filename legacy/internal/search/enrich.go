// Package search turns a natural-language query into ranked, enriched video
// moments: CLIP retrieval over ChromaDB plus Claude Vision descriptions.
package search

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

const (
	anthropicEndpoint = "https://api.anthropic.com/v1/messages"
	anthropicVersion  = "2023-06-01"
	// enrichModel is the Claude model used for search-time frame description.
	enrichModel = "claude-sonnet-4-6"
)

// enrichPrompt instructs Claude how to describe a matched frame.
const enrichPrompt = `Describe what's happening in this video frame in 1-2 sentences.
Focus on: who's visible and what they're doing, the setting/location,
the emotional mood or energy of the moment, and any notable objects or actions.
Be specific — this description will help a creator find this exact moment.`

// Enricher generates rich frame descriptions via the Claude Vision API.
// Constructed without an API key it is disabled and yields empty descriptions.
type Enricher struct {
	apiKey     string
	httpClient *http.Client
}

// NewEnricher returns an Enricher. An empty apiKey leaves it disabled.
func NewEnricher(apiKey string) *Enricher {
	return &Enricher{
		apiKey:     apiKey,
		httpClient: &http.Client{Timeout: 30 * time.Second},
	}
}

// Enabled reports whether a Claude API key is configured.
func (e *Enricher) Enabled() bool { return e.apiKey != "" }

// Describe asks Claude Vision for a short description of a single frame.
// mediaType is the image MIME type, e.g. "image/jpeg".
func (e *Enricher) Describe(ctx context.Context, imageData []byte, mediaType string) (string, error) {
	if !e.Enabled() {
		return "", nil
	}

	reqBody := map[string]any{
		"model":      enrichModel,
		"max_tokens": 200,
		"messages": []map[string]any{{
			"role": "user",
			"content": []map[string]any{
				{
					"type": "image",
					"source": map[string]any{
						"type":       "base64",
						"media_type": mediaType,
						"data":       base64.StdEncoding.EncodeToString(imageData),
					},
				},
				{"type": "text", "text": enrichPrompt},
			},
		}},
	}
	payload, err := json.Marshal(reqBody)
	if err != nil {
		return "", fmt.Errorf("enrich: marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, anthropicEndpoint, bytes.NewReader(payload))
	if err != nil {
		return "", fmt.Errorf("enrich: build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("x-api-key", e.apiKey)
	req.Header.Set("anthropic-version", anthropicVersion)

	resp, err := e.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("enrich: call claude: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		msg, _ := io.ReadAll(io.LimitReader(resp.Body, 2<<10))
		return "", fmt.Errorf("enrich: claude status %d: %s", resp.StatusCode, msg)
	}

	var parsed struct {
		Content []struct {
			Type string `json:"type"`
			Text string `json:"text"`
		} `json:"content"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&parsed); err != nil {
		return "", fmt.Errorf("enrich: decode response: %w", err)
	}

	var sb strings.Builder
	for _, block := range parsed.Content {
		if block.Type == "text" {
			sb.WriteString(block.Text)
		}
	}
	return strings.TrimSpace(sb.String()), nil
}
