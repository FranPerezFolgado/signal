package consumer

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"testing"

	confluent "github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"signal/novelty-detector/internal/config"
	"signal/novelty-detector/internal/repository"
)

func testLogger() *slog.Logger {
	return slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelDebug}))
}

func testConfig() config.Config {
	return config.Config{
		KafkaBootstrapServers: "localhost:9092",
		KafkaConsumerGroup:    "test-group",
		DatabaseURL:           "postgres://x",
		AutoFollowPlays:       3,
		KafkaFlushTimeoutMs:   1000,
	}
}

func enrichedMsg(overrides map[string]any) *confluent.Message {
	pending := false
	base := map[string]any{
		"signal_id":          "sig-001",
		"artist":             "Radiohead",
		"title":              "Creep",
		"pending_enrichment": pending,
		"genres":             []string{"alt-rock"},
	}
	for k, v := range overrides {
		base[k] = v
	}
	data, _ := json.Marshal(base)
	topic := inputTopic
	return &confluent.Message{
		TopicPartition: confluent.TopicPartition{Topic: &topic},
		Value:          data,
	}
}

func runWith(t *testing.T, c *mockConsumer, prod *mockProducer, dlqW *mockDLQWriter,
	artistRepo *mockArtistRepo, noveltyRepo *mockNoveltyRepo) error {
	t.Helper()
	ctx, cancel := context.WithCancel(context.Background())
	c.cancel = cancel
	return Run(ctx, testConfig(), c, prod, artistRepo, noveltyRepo, dlqW, testLogger())
}

// TestProduceErrorRoutesToDLQ: Produce failure (non-operational) → DLQ entry, offset committed.
func TestProduceErrorRoutesToDLQ(t *testing.T) {
	c := &mockConsumer{messages: []*confluent.Message{enrichedMsg(nil)}}
	prod := &mockProducer{produceErr: errors.New("broker unavailable")}
	dlqW := &mockDLQWriter{}
	artistRepo := &mockArtistRepo{artist: &repository.Artist{ID: "a1", Status: "TRACKED", ScrobbleCount: 1}}
	noveltyRepo := &mockNoveltyRepo{artistIsNew: true, newGenres: []string{"alt-rock"}}

	err := runWith(t, c, prod, dlqW, artistRepo, noveltyRepo)
	require.NoError(t, err)

	require.Equal(t, 1, dlqW.len())
	assert.Equal(t, "processing_error", dlqW.get(0).reason)
	assert.True(t, c.committed, "offset must be committed after DLQ routing")
}

// TestContextCancelShutdown: cancelling context triggers graceful shutdown and closes producer.
func TestContextCancelShutdown(t *testing.T) {
	c := &mockConsumer{messages: []*confluent.Message{enrichedMsg(nil)}}
	prod := &mockProducer{}
	dlqW := &mockDLQWriter{}
	artistRepo := &mockArtistRepo{artist: &repository.Artist{ID: "a1", Status: "TRACKED", ScrobbleCount: 1}}
	noveltyRepo := &mockNoveltyRepo{artistIsNew: true, newGenres: []string{"alt-rock"}}

	err := runWith(t, c, prod, dlqW, artistRepo, noveltyRepo)
	require.NoError(t, err)
	assert.True(t, prod.isClosed(), "output producer must be closed on shutdown")
}

// TestAutoPromotionAtThreshold: TRACKED artist at threshold → PromoteToFollowing called,
// and the emitted event carries correct novelty signals.
func TestAutoPromotionAtThreshold(t *testing.T) {
	c := &mockConsumer{messages: []*confluent.Message{enrichedMsg(nil)}}
	prod := &mockProducer{}
	dlqW := &mockDLQWriter{}
	artistRepo := &mockArtistRepo{
		artist:   &repository.Artist{ID: "a1", Status: "TRACKED", ScrobbleCount: 3},
		promoted: true,
	}
	noveltyRepo := &mockNoveltyRepo{artistIsNew: true, newGenres: []string{"alt-rock"}}

	err := runWith(t, c, prod, dlqW, artistRepo, noveltyRepo)
	require.NoError(t, err)

	assert.Equal(t, 1, artistRepo.promotesCalled, "PromoteToFollowing must be called at threshold")
	require.Len(t, prod.produced, 1, "tracks.novel event must be emitted")

	var event NoveltyEvent
	require.NoError(t, json.Unmarshal(prod.produced[0], &event))
	assert.Equal(t, "Radiohead", event.Artist)
	assert.True(t, event.NoveltySignals.ArtistIsNew)
	assert.Equal(t, []string{"alt-rock"}, event.NoveltySignals.NewGenres)
}

// TestAutoPromotionFailureDoesNotBlockEvent: DB error during promotion must not prevent emission.
func TestAutoPromotionFailureDoesNotBlockEvent(t *testing.T) {
	c := &mockConsumer{messages: []*confluent.Message{enrichedMsg(nil)}}
	prod := &mockProducer{}
	dlqW := &mockDLQWriter{}
	artistRepo := &mockArtistRepo{
		artist:     &repository.Artist{ID: "a1", Status: "TRACKED", ScrobbleCount: 3},
		promoteErr: fmt.Errorf("db transient error"),
	}
	noveltyRepo := &mockNoveltyRepo{artistIsNew: true, newGenres: []string{"alt-rock"}}

	err := runWith(t, c, prod, dlqW, artistRepo, noveltyRepo)
	require.NoError(t, err)

	assert.Len(t, prod.produced, 1, "event must be emitted despite promotion failure")
}

// TestMalformedMessageRoutedToDLQ: invalid JSON → malformed_message DLQ, offset committed.
func TestMalformedMessageRoutedToDLQ(t *testing.T) {
	topic := inputTopic
	c := &mockConsumer{messages: []*confluent.Message{
		{TopicPartition: confluent.TopicPartition{Topic: &topic}, Value: []byte("not-json")},
	}}
	prod := &mockProducer{}
	dlqW := &mockDLQWriter{}

	err := runWith(t, c, prod, dlqW, &mockArtistRepo{}, &mockNoveltyRepo{})
	require.NoError(t, err)

	require.Equal(t, 1, dlqW.len())
	assert.Equal(t, "malformed_message", dlqW.get(0).reason)
	assert.True(t, c.committed, "offset must be committed after DLQ routing")
}

// TestInvalidTrackMissingArtistRoutedToDLQ: valid JSON but missing artist → malformed_message DLQ.
func TestInvalidTrackMissingArtistRoutedToDLQ(t *testing.T) {
	c := &mockConsumer{messages: []*confluent.Message{
		enrichedMsg(map[string]any{"artist": ""}),
	}}
	prod := &mockProducer{}
	dlqW := &mockDLQWriter{}

	err := runWith(t, c, prod, dlqW, &mockArtistRepo{}, &mockNoveltyRepo{})
	require.NoError(t, err)

	require.Equal(t, 1, dlqW.len())
	assert.Equal(t, "malformed_message", dlqW.get(0).reason)
}

// TestMissingArtistRecordRoutedToDLQ: GetArtist returns nil → artist_record_missing DLQ.
func TestMissingArtistRecordRoutedToDLQ(t *testing.T) {
	c := &mockConsumer{messages: []*confluent.Message{enrichedMsg(nil)}}
	prod := &mockProducer{}
	dlqW := &mockDLQWriter{}

	err := runWith(t, c, prod, dlqW, &mockArtistRepo{artist: nil}, &mockNoveltyRepo{})
	require.NoError(t, err)

	require.Equal(t, 1, dlqW.len())
	assert.Equal(t, "artist_record_missing", dlqW.get(0).reason)
	assert.True(t, c.committed)
}

// TestPendingEnrichmentIsSkipped: pending_enrichment=true → silently skipped, no DLQ, no emit.
func TestPendingEnrichmentIsSkipped(t *testing.T) {
	pending := true
	c := &mockConsumer{messages: []*confluent.Message{
		enrichedMsg(map[string]any{"pending_enrichment": pending}),
	}}
	prod := &mockProducer{}
	dlqW := &mockDLQWriter{}

	err := runWith(t, c, prod, dlqW, &mockArtistRepo{}, &mockNoveltyRepo{})
	require.NoError(t, err)

	assert.Empty(t, prod.produced, "no event must be emitted for pending tracks")
	assert.Equal(t, 0, dlqW.len(), "pending tracks must not go to DLQ")
	assert.True(t, c.committed)
}

// TestKnownArtistNoEmit: artist known + no new genres → ShouldEmit false → no output.
func TestKnownArtistNoEmit(t *testing.T) {
	c := &mockConsumer{messages: []*confluent.Message{enrichedMsg(nil)}}
	prod := &mockProducer{}
	dlqW := &mockDLQWriter{}
	artistRepo := &mockArtistRepo{artist: &repository.Artist{ID: "a1", Status: "FOLLOWING", ScrobbleCount: 10}}
	noveltyRepo := &mockNoveltyRepo{artistIsNew: false, newGenres: []string{}}

	err := runWith(t, c, prod, dlqW, artistRepo, noveltyRepo)
	require.NoError(t, err)

	assert.Empty(t, prod.produced, "no event must be emitted for a fully-known artist")
	assert.Equal(t, 0, dlqW.len())
}

// TestIsValidTrack: unit tests for the validation helper.
func TestIsValidTrack(t *testing.T) {
	pendingFalse := false
	pendingTrue := true

	valid := &EnrichedTrack{SignalID: "s", Artist: "a", Title: "t", PendingEnrichment: &pendingFalse}
	assert.True(t, isValidTrack(valid))

	assert.False(t, isValidTrack(&EnrichedTrack{Artist: "a", Title: "t", PendingEnrichment: &pendingFalse}))
	assert.False(t, isValidTrack(&EnrichedTrack{SignalID: "s", Title: "t", PendingEnrichment: &pendingFalse}))
	assert.False(t, isValidTrack(&EnrichedTrack{SignalID: "s", Artist: "a", PendingEnrichment: &pendingFalse}))
	assert.False(t, isValidTrack(&EnrichedTrack{SignalID: "s", Artist: "a", Title: "t"})) // nil PendingEnrichment

	// pending=true is still valid (field is present); skipping is handled by the consumer loop
	assert.True(t, isValidTrack(&EnrichedTrack{SignalID: "s", Artist: "a", Title: "t", PendingEnrichment: &pendingTrue}))
}
