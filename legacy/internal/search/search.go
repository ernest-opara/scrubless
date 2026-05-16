package search

import (
	"context"
	"fmt"
	"io"
	"log"
	"sync"

	"github.com/ernest-opara/scrubless/internal/models"
	"github.com/ernest-opara/scrubless/internal/pipeline"
	"github.com/ernest-opara/scrubless/internal/storage"
)

const (
	defaultLimit = 10
	maxLimit     = 50
)

// Searcher answers natural-language queries over an indexed video: it embeds
// the query with CLIP, retrieves the nearest segments from ChromaDB, and
// enriches the top results with Claude Vision descriptions.
type Searcher struct {
	embedder   pipeline.Embedder
	index      *pipeline.Index
	enricher   *Enricher
	storage    storage.Storage
	enrichTopN int
}

// New constructs a Searcher. enrichTopN bounds how many top results receive a
// Claude Vision description.
func New(emb pipeline.Embedder, idx *pipeline.Index, enr *Enricher, st storage.Storage, enrichTopN int) *Searcher {
	return &Searcher{
		embedder:   emb,
		index:      idx,
		enricher:   enr,
		storage:    st,
		enrichTopN: enrichTopN,
	}
}

// Search returns the moments of videoID best matching query, ranked by
// similarity. The top results carry a Claude Vision description.
func (s *Searcher) Search(ctx context.Context, videoID, query string, limit int) ([]models.SearchResult, error) {
	if limit <= 0 {
		limit = defaultLimit
	}
	if limit > maxLimit {
		limit = maxLimit
	}

	// Tier 1: embed the query and retrieve nearest segments from ChromaDB.
	queryVec, err := s.embedder.EmbedText(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("search: embed query: %w", err)
	}
	hits, err := s.index.Query(ctx, videoID, queryVec, limit)
	if err != nil {
		return nil, fmt.Errorf("search: %w", err)
	}

	results := make([]models.SearchResult, len(hits))
	for i, h := range hits {
		thumbURL, err := s.storage.URL(ctx, h.Segment.FrameKey)
		if err != nil {
			log.Printf("search: thumbnail url for %s: %v", h.Segment.FrameKey, err)
		}
		results[i] = models.SearchResult{
			TimestampStart:    h.Segment.TimestampStart,
			TimestampEnd:      h.Segment.TimestampEnd,
			ThumbnailURL:      thumbURL,
			Score:             h.Score,
			TranscriptSnippet: h.Segment.TranscriptText,
		}
	}

	// Tier 2: enrich the top-N frames with Claude Vision descriptions.
	s.enrichTop(ctx, hits, results)
	return results, nil
}

// enrichTop fills in the Description of the first enrichTopN results, fetching
// each frame and describing it via Claude Vision concurrently. A failed
// enrichment is logged and leaves that result's Description empty.
func (s *Searcher) enrichTop(ctx context.Context, hits []pipeline.Hit, results []models.SearchResult) {
	if !s.enricher.Enabled() {
		return
	}
	n := min(s.enrichTopN, len(results))

	var wg sync.WaitGroup
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			desc, err := s.describeFrame(ctx, hits[i].Segment.FrameKey)
			if err != nil {
				log.Printf("search: enrich %s: %v", hits[i].Segment.FrameKey, err)
				return
			}
			results[i].Description = desc
		}(i)
	}
	wg.Wait()
}

// describeFrame fetches a stored frame and returns a Claude Vision description.
func (s *Searcher) describeFrame(ctx context.Context, frameKey string) (string, error) {
	rc, err := s.storage.Open(ctx, frameKey)
	if err != nil {
		return "", fmt.Errorf("open frame: %w", err)
	}
	defer rc.Close()

	data, err := io.ReadAll(rc)
	if err != nil {
		return "", fmt.Errorf("read frame: %w", err)
	}
	return s.enricher.Describe(ctx, data, "image/jpeg")
}
