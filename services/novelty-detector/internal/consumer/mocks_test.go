package consumer

import (
	"context"
	"encoding/json"
	"sync"
	"time"

	confluent "github.com/confluentinc/confluent-kafka-go/v2/kafka"

	"signal/novelty-detector/internal/dlq"
	"signal/novelty-detector/internal/kafka"
	"signal/novelty-detector/internal/repository"
)

// mockConsumer delivers a fixed slice of messages then cancels ctx to trigger shutdown.
type mockConsumer struct {
	messages  []*confluent.Message
	idx       int
	committed bool
	cancel    context.CancelFunc
}

func (m *mockConsumer) Subscribe(_ []string) error { return nil }
func (m *mockConsumer) Close() error               { return nil }

func (m *mockConsumer) Poll(_ int) confluent.Event {
	if m.idx >= len(m.messages) {
		if m.cancel != nil {
			m.cancel()
		}
		time.Sleep(10 * time.Millisecond)
		return nil
	}
	msg := m.messages[m.idx]
	m.idx++
	return msg
}

func (m *mockConsumer) Commit() ([]confluent.TopicPartition, error) {
	m.committed = true
	return nil, nil
}

// mockProducer records produced payloads. closed is mutex-protected to be race-safe.
type mockProducer struct {
	produced   [][]byte
	produceErr error
	mu         sync.Mutex
	closed     bool
}

func (m *mockProducer) Produce(_ string, payload any, _ string) error {
	if m.produceErr != nil {
		return m.produceErr
	}
	data, _ := json.Marshal(payload)
	m.produced = append(m.produced, data)
	return nil
}

func (m *mockProducer) Flush(_ int) int { return 0 }

func (m *mockProducer) Close() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.closed = true
}

func (m *mockProducer) isClosed() bool {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.closed
}

// mockDLQWriter captures DLQ entries for assertion.
type mockDLQWriter struct {
	mu      sync.Mutex
	entries []capturedEntry
}

type capturedEntry struct {
	reason string
	detail string
}

func (m *mockDLQWriter) Publish(reason, detail string, _ any) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.entries = append(m.entries, capturedEntry{reason: reason, detail: detail})
}

func (m *mockDLQWriter) len() int {
	m.mu.Lock()
	defer m.mu.Unlock()
	return len(m.entries)
}

func (m *mockDLQWriter) get(i int) capturedEntry {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.entries[i]
}

// mockArtistRepo is a configurable ArtistRepo for unit tests.
type mockArtistRepo struct {
	artist         *repository.Artist
	getErr         error
	promoted       bool
	promoteErr     error
	promotesCalled int
}

func (m *mockArtistRepo) GetArtist(_ context.Context, _ string) (*repository.Artist, error) {
	return m.artist, m.getErr
}

func (m *mockArtistRepo) PromoteToFollowing(_ context.Context, _ string, _ int) (bool, error) {
	m.promotesCalled++
	return m.promoted, m.promoteErr
}

// mockNoveltyRepo is a configurable NoveltyRepo for unit tests.
type mockNoveltyRepo struct {
	artistIsNew bool
	artistErr   error
	newGenres   []string
	genresErr   error
	trackIsNew  bool
	trackErr    error
}

func (m *mockNoveltyRepo) IsArtistNew(_ context.Context, _, _ string) (bool, error) {
	return m.artistIsNew, m.artistErr
}

func (m *mockNoveltyRepo) GetNewGenres(_ context.Context, _ []string, _ string) ([]string, error) {
	return m.newGenres, m.genresErr
}

func (m *mockNoveltyRepo) IsTrackNew(_ context.Context, _ string) (bool, error) {
	return m.trackIsNew, m.trackErr
}

// Interface compliance checks.
var _ kafka.Consumer = (*mockConsumer)(nil)
var _ kafka.Producer = (*mockProducer)(nil)
var _ dlq.Writer = (*mockDLQWriter)(nil)
var _ repository.ArtistRepo = (*mockArtistRepo)(nil)
var _ repository.NoveltyRepo = (*mockNoveltyRepo)(nil)
