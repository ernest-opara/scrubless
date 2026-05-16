package pipeline

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// Embedder turns frames and query text into vectors in a shared embedding
// space. Code depends on this interface, not the CLIP implementation, so the
// model can be swapped (SigLIP, Marengo, ...) without touching the pipeline.
type Embedder interface {
	EmbedImage(ctx context.Context, imageData []byte) ([]float32, error)
	EmbedText(ctx context.Context, text string) ([]float32, error)
	EmbedImageBatch(ctx context.Context, images [][]byte) ([][]float32, error)
}

// clipBatchSize bounds how many images go to the sidecar per request, keeping
// request size and sidecar memory in check.
const clipBatchSize = 16

// CLIPEmbedder is an Embedder backed by the Python CLIP sidecar over HTTP.
type CLIPEmbedder struct {
	baseURL    string
	httpClient *http.Client
}

// NewCLIPEmbedder returns a CLIPEmbedder calling the sidecar at baseURL.
func NewCLIPEmbedder(baseURL string) *CLIPEmbedder {
	return &CLIPEmbedder{
		baseURL:    baseURL,
		httpClient: &http.Client{Timeout: 2 * time.Minute},
	}
}

// EmbedImage embeds a single image.
func (c *CLIPEmbedder) EmbedImage(ctx context.Context, imageData []byte) ([]float32, error) {
	var out struct {
		Embedding []float32 `json:"embedding"`
	}
	body := map[string]string{"image_base64": base64.StdEncoding.EncodeToString(imageData)}
	if err := c.post(ctx, "/embed/image", body, &out); err != nil {
		return nil, err
	}
	return out.Embedding, nil
}

// EmbedText embeds a query string.
func (c *CLIPEmbedder) EmbedText(ctx context.Context, text string) ([]float32, error) {
	var out struct {
		Embedding []float32 `json:"embedding"`
	}
	if err := c.post(ctx, "/embed/text", map[string]string{"text": text}, &out); err != nil {
		return nil, err
	}
	return out.Embedding, nil
}

// EmbedImageBatch embeds many images, internally chunking into sidecar-sized
// requests. The result is aligned 1:1 with the input order.
func (c *CLIPEmbedder) EmbedImageBatch(ctx context.Context, images [][]byte) ([][]float32, error) {
	embeddings := make([][]float32, 0, len(images))
	for start := 0; start < len(images); start += clipBatchSize {
		end := min(start+clipBatchSize, len(images))

		encoded := make([]string, end-start)
		for i, img := range images[start:end] {
			encoded[i] = base64.StdEncoding.EncodeToString(img)
		}

		var out struct {
			Embeddings [][]float32 `json:"embeddings"`
		}
		if err := c.post(ctx, "/embed/batch", map[string][]string{"images": encoded}, &out); err != nil {
			return nil, err
		}
		if len(out.Embeddings) != end-start {
			return nil, fmt.Errorf("clip: batch returned %d embeddings, want %d", len(out.Embeddings), end-start)
		}
		embeddings = append(embeddings, out.Embeddings...)
	}
	return embeddings, nil
}

// post sends body as JSON to path and decodes the JSON response into out.
func (c *CLIPEmbedder) post(ctx context.Context, path string, body, out any) error {
	payload, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("clip: marshal request: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+path, bytes.NewReader(payload))
	if err != nil {
		return fmt.Errorf("clip: build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("clip: call %s: %w", path, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		msg, _ := io.ReadAll(io.LimitReader(resp.Body, 2<<10))
		return fmt.Errorf("clip: %s status %d: %s", path, resp.StatusCode, msg)
	}
	if err := json.NewDecoder(resp.Body).Decode(out); err != nil {
		return fmt.Errorf("clip: decode %s response: %w", path, err)
	}
	return nil
}
