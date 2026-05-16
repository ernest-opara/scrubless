package pipeline

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sort"
	"time"

	"github.com/ernest-opara/scrubless/internal/models"
)

// Chroma's single-node deployment uses these fixed defaults.
const (
	chromaTenant   = "default_tenant"
	chromaDatabase = "default_database"
	collectionName = "scrubless_segments"
)

// Index stores and searches segment embeddings in ChromaDB. All videos share
// one collection; queries are scoped by a video_id metadata filter.
type Index struct {
	collectionsURL string // .../collections
	collectionID   string
	httpClient     *http.Client
}

// Hit is one ranked search result from the index.
type Hit struct {
	Segment  models.Segment
	Distance float64 // cosine distance, 0 = identical
	Score    float64 // cosine similarity, 1 - Distance
}

// NewIndex connects to ChromaDB at chromaURL and ensures the segment
// collection exists, returning a ready Index.
func NewIndex(ctx context.Context, chromaURL string) (*Index, error) {
	idx := &Index{
		collectionsURL: fmt.Sprintf("%s/api/v2/tenants/%s/databases/%s/collections",
			chromaURL, chromaTenant, chromaDatabase),
		httpClient: &http.Client{Timeout: 60 * time.Second},
	}
	if err := idx.ensureCollection(ctx); err != nil {
		return nil, err
	}
	return idx, nil
}

// ensureCollection creates (or fetches) the shared collection and caches its id.
func (idx *Index) ensureCollection(ctx context.Context) error {
	body := map[string]any{
		"name":          collectionName,
		"metadata":      map[string]any{"hnsw:space": "cosine"},
		"get_or_create": true,
	}
	var out struct {
		ID string `json:"id"`
	}
	if err := idx.do(ctx, http.MethodPost, idx.collectionsURL, body, &out); err != nil {
		return fmt.Errorf("index: ensure collection: %w", err)
	}
	if out.ID == "" {
		return fmt.Errorf("index: ensure collection: empty collection id")
	}
	idx.collectionID = out.ID
	return nil
}

// Add stores segments and their embeddings. embeddings must align 1:1 with segs.
func (idx *Index) Add(ctx context.Context, segs []models.Segment, embeddings [][]float32) error {
	if len(segs) != len(embeddings) {
		return fmt.Errorf("index: %d segments but %d embeddings", len(segs), len(embeddings))
	}
	if len(segs) == 0 {
		return nil
	}

	ids := make([]string, len(segs))
	metadatas := make([]map[string]any, len(segs))
	documents := make([]string, len(segs))
	for i, s := range segs {
		ids[i] = segmentID(s.VideoID, s.Index)
		metadatas[i] = map[string]any{
			"video_id":        s.VideoID,
			"segment_index":   s.Index,
			"timestamp_start": s.TimestampStart,
			"timestamp_end":   s.TimestampEnd,
			"frame_key":       s.FrameKey,
			"transcript_text": s.TranscriptText,
		}
		documents[i] = s.TranscriptText
	}

	body := map[string]any{
		"ids":        ids,
		"embeddings": embeddings,
		"metadatas":  metadatas,
		"documents":  documents,
	}
	url := fmt.Sprintf("%s/%s/add", idx.collectionsURL, idx.collectionID)
	if err := idx.do(ctx, http.MethodPost, url, body, nil); err != nil {
		return fmt.Errorf("index: add segments: %w", err)
	}
	return nil
}

// Query returns the topK segments of videoID nearest to embedding.
func (idx *Index) Query(ctx context.Context, videoID string, embedding []float32, topK int) ([]Hit, error) {
	body := map[string]any{
		"query_embeddings": [][]float32{embedding},
		"n_results":        topK,
		"where":            map[string]any{"video_id": videoID},
		"include":          []string{"metadatas", "distances"},
	}
	var out struct {
		Metadatas [][]map[string]any `json:"metadatas"`
		Distances [][]float64        `json:"distances"`
	}
	url := fmt.Sprintf("%s/%s/query", idx.collectionsURL, idx.collectionID)
	if err := idx.do(ctx, http.MethodPost, url, body, &out); err != nil {
		return nil, fmt.Errorf("index: query: %w", err)
	}
	if len(out.Metadatas) == 0 {
		return nil, nil
	}

	metas, dists := out.Metadatas[0], out.Distances[0]
	hits := make([]Hit, len(metas))
	for i, m := range metas {
		hits[i] = Hit{
			Segment:  segmentFromMetadata(m),
			Distance: dists[i],
			Score:    1 - dists[i],
		}
	}
	return hits, nil
}

// ListSegments returns every indexed segment of videoID, ordered by index.
func (idx *Index) ListSegments(ctx context.Context, videoID string) ([]models.Segment, error) {
	body := map[string]any{
		"where":   map[string]any{"video_id": videoID},
		"include": []string{"metadatas"},
	}
	var out struct {
		Metadatas []map[string]any `json:"metadatas"`
	}
	url := fmt.Sprintf("%s/%s/get", idx.collectionsURL, idx.collectionID)
	if err := idx.do(ctx, http.MethodPost, url, body, &out); err != nil {
		return nil, fmt.Errorf("index: list segments: %w", err)
	}

	segs := make([]models.Segment, len(out.Metadatas))
	for i, m := range out.Metadatas {
		segs[i] = segmentFromMetadata(m)
	}
	sort.Slice(segs, func(i, j int) bool { return segs[i].Index < segs[j].Index })
	return segs, nil
}

// DeleteVideo removes every segment belonging to videoID.
func (idx *Index) DeleteVideo(ctx context.Context, videoID string) error {
	body := map[string]any{"where": map[string]any{"video_id": videoID}}
	url := fmt.Sprintf("%s/%s/delete", idx.collectionsURL, idx.collectionID)
	if err := idx.do(ctx, http.MethodPost, url, body, nil); err != nil {
		return fmt.Errorf("index: delete video: %w", err)
	}
	return nil
}

// do issues a JSON request and, when out is non-nil, decodes the JSON response.
func (idx *Index) do(ctx context.Context, method, url string, body, out any) error {
	payload, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("marshal request: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, method, url, bytes.NewReader(payload))
	if err != nil {
		return fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := idx.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("call chromadb: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		msg, _ := io.ReadAll(io.LimitReader(resp.Body, 2<<10))
		return fmt.Errorf("chromadb status %d: %s", resp.StatusCode, msg)
	}
	if out != nil {
		if err := json.NewDecoder(resp.Body).Decode(out); err != nil {
			return fmt.Errorf("decode response: %w", err)
		}
	}
	return nil
}

// segmentID is the ChromaDB record id for a video's nth segment.
func segmentID(videoID string, index int) string {
	return fmt.Sprintf("%s:%d", videoID, index)
}

// segmentFromMetadata rebuilds a Segment from a ChromaDB metadata map, where
// every JSON number arrives as a float64.
func segmentFromMetadata(m map[string]any) models.Segment {
	return models.Segment{
		VideoID:        asString(m["video_id"]),
		Index:          int(asFloat(m["segment_index"])),
		TimestampStart: asFloat(m["timestamp_start"]),
		TimestampEnd:   asFloat(m["timestamp_end"]),
		FrameKey:       asString(m["frame_key"]),
		TranscriptText: asString(m["transcript_text"]),
	}
}

func asString(v any) string {
	s, _ := v.(string)
	return s
}

func asFloat(v any) float64 {
	f, _ := v.(float64)
	return f
}
