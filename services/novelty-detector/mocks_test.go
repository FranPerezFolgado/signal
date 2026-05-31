package main

import (
	"context"
	"encoding/json"
	"syscall"
	"time"

	kafka "github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

// mockKafkaConsumer delivers a fixed slice of messages then sends SIGTERM.
type mockKafkaConsumer struct {
	messages  []*kafka.Message
	idx       int
	committed bool
}

func (m *mockKafkaConsumer) Subscribe(_ []string) error { return nil }
func (m *mockKafkaConsumer) Close() error               { return nil }

func (m *mockKafkaConsumer) Poll(_ int) kafka.Event {
	if m.idx >= len(m.messages) {
		_ = syscall.Kill(syscall.Getpid(), syscall.SIGTERM)
		time.Sleep(50 * time.Millisecond)
		return nil
	}
	msg := m.messages[m.idx]
	m.idx++
	return msg
}

func (m *mockKafkaConsumer) Commit() ([]kafka.TopicPartition, error) {
	m.committed = true
	return nil, nil
}

// mockKafkaProducer records produced payloads; unflushed controls Flush return.
type mockKafkaProducer struct {
	produced   [][]byte
	flushCount int
	unflushed  int
	closed     bool
}

func (m *mockKafkaProducer) Produce(_ string, payload any, _ string) error {
	data, _ := json.Marshal(payload)
	m.produced = append(m.produced, data)
	return nil
}

func (m *mockKafkaProducer) Flush(_ int) int {
	m.flushCount++
	return m.unflushed
}

func (m *mockKafkaProducer) Close() { m.closed = true }

// captureDLQProducer captures DLQEntry messages for inspection in tests.
type captureDLQProducer struct {
	entries []DLQEntry
}

func (c *captureDLQProducer) Produce(_ string, payload any, _ string) error {
	data, _ := json.Marshal(payload)
	var entry DLQEntry
	if err := json.Unmarshal(data, &entry); err != nil {
		return err
	}
	c.entries = append(c.entries, entry)
	return nil
}

func (c *captureDLQProducer) Flush(_ int) int { return 0 }
func (c *captureDLQProducer) Close()          {}

// mockArtistRepo is a configurable ArtistRepo for unit tests.
type mockArtistRepo struct {
	artist         *Artist
	getErr         error
	promoted       bool
	promoteErr     error
	promotesCalled int
}

func (m *mockArtistRepo) GetArtist(_ context.Context, _ string) (*Artist, error) {
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
var _ KafkaConsumer = (*mockKafkaConsumer)(nil)
var _ KafkaProducer = (*mockKafkaProducer)(nil)
var _ KafkaProducer = (*captureDLQProducer)(nil)
var _ ArtistRepo = (*mockArtistRepo)(nil)
var _ NoveltyRepo = (*mockNoveltyRepo)(nil)
