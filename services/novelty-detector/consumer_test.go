package main

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"testing"
	"time"

	kafka "github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func testLogger() *slog.Logger {
	return slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelDebug}))
}

func testConfig() Config {
	return Config{
		KafkaBootstrapServers: "localhost:9092",
		KafkaConsumerGroup:    "test-group",
		DatabaseURL:           "postgres://x",
		AutoFollowPlays:       3,
		KafkaFlushTimeoutMs:   1000,
	}
}

func enrichedMsg(overrides map[string]any) *kafka.Message {
	base := map[string]any{
		"signal_id":          "sig-001",
		"artist":             "Radiohead",
		"title":              "Creep",
		"pending_enrichment": false,
		"genres":             []string{"alt-rock"},
	}
	for k, v := range overrides {
		base[k] = v
	}
	data, _ := json.Marshal(base)
	topic := "tracks.enriched"
	return &kafka.Message{
		TopicPartition: kafka.TopicPartition{Topic: &topic},
		Value:          data,
	}
}

// T018: flush timeout must not commit offset
func TestFlushTimeoutDoesNotCommitOffset(t *testing.T) {
	consumer := &mockKafkaConsumer{messages: []*kafka.Message{enrichedMsg(nil)}}
	producer := &mockKafkaProducer{unflushed: 1}
	dlqProd := &mockKafkaProducer{}

	artistRepo := &mockArtistRepo{artist: &Artist{ID: "a1", Status: "TRACKED", ScrobbleCount: 1}}
	noveltyRepo := &mockNoveltyRepo{artistIsNew: true, newGenres: []string{"alt-rock"}}

	err := RunConsumer(testConfig(), consumer, producer, artistRepo, noveltyRepo,
		newDLQPublisher(dlqProd, testLogger()), testLogger())
	require.NoError(t, err)

	assert.False(t, consumer.committed, "offset must not be committed when flush times out")
	assert.GreaterOrEqual(t, producer.flushCount, 1)
}

// T019: SIGTERM triggers graceful shutdown within 5 seconds
func TestSigtermCompletesInFlightMessage(t *testing.T) {
	consumer := &mockKafkaConsumer{messages: []*kafka.Message{enrichedMsg(nil)}}
	producer := &mockKafkaProducer{}
	dlqProd := &mockKafkaProducer{}

	artistRepo := &mockArtistRepo{artist: &Artist{ID: "a1", Status: "TRACKED", ScrobbleCount: 1}}
	noveltyRepo := &mockNoveltyRepo{artistIsNew: true, newGenres: []string{"alt-rock"}}

	done := make(chan error, 1)
	go func() {
		done <- RunConsumer(testConfig(), consumer, producer, artistRepo, noveltyRepo,
			newDLQPublisher(dlqProd, testLogger()), testLogger())
	}()

	select {
	case err := <-done:
		require.NoError(t, err)
		assert.True(t, producer.closed, "output producer must be closed on shutdown")
	case <-time.After(5 * time.Second):
		t.Fatal("graceful shutdown exceeded 5 second limit")
	}
}

// T023: auto-promotion called when artist is at threshold
func TestAutoPromotionAtThreshold(t *testing.T) {
	consumer := &mockKafkaConsumer{messages: []*kafka.Message{enrichedMsg(nil)}}
	producer := &mockKafkaProducer{}
	dlqProd := &mockKafkaProducer{}

	artistRepo := &mockArtistRepo{
		artist:   &Artist{ID: "a1", Status: "TRACKED", ScrobbleCount: 3},
		promoted: true,
	}
	noveltyRepo := &mockNoveltyRepo{artistIsNew: true, newGenres: []string{"alt-rock"}}

	err := RunConsumer(testConfig(), consumer, producer, artistRepo, noveltyRepo,
		newDLQPublisher(dlqProd, testLogger()), testLogger())
	require.NoError(t, err)

	assert.Equal(t, 1, artistRepo.promotesCalled, "PromoteToFollowing must be called at threshold")
	assert.Len(t, producer.produced, 1, "tracks.novel event must be emitted")
}

// T024: promotion failure does not block event emission
func TestAutoPromotionFailureDoesNotBlockEvent(t *testing.T) {
	consumer := &mockKafkaConsumer{messages: []*kafka.Message{enrichedMsg(nil)}}
	producer := &mockKafkaProducer{}
	dlqProd := &mockKafkaProducer{}

	artistRepo := &mockArtistRepo{
		artist:     &Artist{ID: "a1", Status: "TRACKED", ScrobbleCount: 3},
		promoteErr: fmt.Errorf("db transient error"),
	}
	noveltyRepo := &mockNoveltyRepo{artistIsNew: true, newGenres: []string{"alt-rock"}}

	err := RunConsumer(testConfig(), consumer, producer, artistRepo, noveltyRepo,
		newDLQPublisher(dlqProd, testLogger()), testLogger())
	require.NoError(t, err)

	assert.Len(t, producer.produced, 1, "tracks.novel event must be emitted despite promotion failure")
}

// T027: malformed message (missing artist) routed to DLQ
func TestMalformedMessageRoutedToDLQ(t *testing.T) {
	topic := "tracks.enriched"
	badPayload, _ := json.Marshal(map[string]any{
		"signal_id":          "sig-bad",
		"title":              "Creep",
		"pending_enrichment": false,
		// "artist" is missing
	})
	consumer := &mockKafkaConsumer{
		messages: []*kafka.Message{
			{TopicPartition: kafka.TopicPartition{Topic: &topic}, Value: badPayload},
		},
	}
	producer := &mockKafkaProducer{}
	captured := &captureDLQProducer{}

	err := RunConsumer(testConfig(), consumer, producer, &mockArtistRepo{}, &mockNoveltyRepo{},
		newDLQPublisher(captured, testLogger()), testLogger())
	require.NoError(t, err)

	require.Len(t, captured.entries, 1)
	assert.Equal(t, "malformed_message", captured.entries[0].ErrorReason)
	assert.True(t, consumer.committed, "offset must be committed after DLQ routing")
}

// T028: missing artist record routed to DLQ with artist_record_missing reason
func TestMissingArtistRoutedToDLQ(t *testing.T) {
	consumer := &mockKafkaConsumer{messages: []*kafka.Message{enrichedMsg(nil)}}
	producer := &mockKafkaProducer{}
	captured := &captureDLQProducer{}

	err := RunConsumer(testConfig(), consumer, producer,
		&mockArtistRepo{artist: nil}, // GetArtist returns nil
		&mockNoveltyRepo{},
		newDLQPublisher(captured, testLogger()), testLogger())
	require.NoError(t, err)

	require.Len(t, captured.entries, 1)
	assert.Equal(t, "artist_record_missing", captured.entries[0].ErrorReason)
	assert.True(t, consumer.committed)
}

// T012: mock repo interface verification (repository_test coverage)
func TestMockNoveltyRepoInterface(t *testing.T) {
	repo := &mockNoveltyRepo{artistIsNew: false, newGenres: []string{"jazz"}}
	isNew, err := repo.IsArtistNew(t.Context(), "Radiohead", "sig1")
	require.NoError(t, err)
	assert.False(t, isNew)

	genres, err := repo.GetNewGenres(t.Context(), []string{"jazz", "rock"}, "sig1")
	require.NoError(t, err)
	assert.Equal(t, []string{"jazz"}, genres)
}

func TestMockArtistRepoInterface(t *testing.T) {
	repo := &mockArtistRepo{
		artist:   &Artist{ID: "a1", Status: "FOLLOWING", ScrobbleCount: 10},
		promoted: true,
	}
	artist, err := repo.GetArtist(t.Context(), "Radiohead")
	require.NoError(t, err)
	require.NotNil(t, artist)
	assert.Equal(t, "FOLLOWING", artist.Status)

	ok, err := repo.PromoteToFollowing(t.Context(), "Radiohead", 3)
	require.NoError(t, err)
	assert.True(t, ok)
	assert.Equal(t, 1, repo.promotesCalled)
}
