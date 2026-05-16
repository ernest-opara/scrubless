// Package store keeps video metadata and processing state. The MVP uses an
// in-memory implementation behind the VideoStore interface; a database-backed
// one can be swapped in later without touching callers.
package store

import (
	"sort"
	"sync"

	"github.com/ernest-opara/scrubless/internal/models"
)

// VideoStore persists video records and their evolving processing state.
type VideoStore interface {
	// Create inserts v. The caller owns v.ID.
	Create(v *models.Video)
	// Get returns the video by id, or false if absent.
	Get(id string) (*models.Video, bool)
	// List returns all videos, newest first.
	List() []*models.Video
	// Update applies fn to the stored video under a lock. It is a no-op if
	// the id is unknown. fn must not retain the pointer.
	Update(id string, fn func(*models.Video))
	// Delete removes the video. Deleting an unknown id is a no-op.
	Delete(id string)
}

// Memory is an in-process, mutex-guarded VideoStore.
type Memory struct {
	mu     sync.RWMutex
	videos map[string]*models.Video
}

// NewMemory returns an empty in-memory store.
func NewMemory() *Memory {
	return &Memory{videos: make(map[string]*models.Video)}
}

func (m *Memory) Create(v *models.Video) {
	m.mu.Lock()
	defer m.mu.Unlock()
	cp := *v
	m.videos[v.ID] = &cp
}

func (m *Memory) Get(id string) (*models.Video, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	v, ok := m.videos[id]
	if !ok {
		return nil, false
	}
	cp := *v // hand out a copy so callers can't mutate stored state
	return &cp, true
}

func (m *Memory) List() []*models.Video {
	m.mu.RLock()
	defer m.mu.RUnlock()
	out := make([]*models.Video, 0, len(m.videos))
	for _, v := range m.videos {
		cp := *v
		out = append(out, &cp)
	}
	sort.Slice(out, func(i, j int) bool {
		return out[i].CreatedAt.After(out[j].CreatedAt)
	})
	return out
}

func (m *Memory) Update(id string, fn func(*models.Video)) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if v, ok := m.videos[id]; ok {
		fn(v)
	}
}

func (m *Memory) Delete(id string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	delete(m.videos, id)
}
