//go:build integration

package consumer

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"strings"
	"testing"
	"time"

	confluent "github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/testcontainers/testcontainers-go"
	kafkacontainer "github.com/testcontainers/testcontainers-go/modules/kafka"
	postgrescontainer "github.com/testcontainers/testcontainers-go/modules/postgres"
	"github.com/testcontainers/testcontainers-go/wait"

	"signal/novelty-detector/internal/config"
	"signal/novelty-detector/internal/dlq"
	"signal/novelty-detector/internal/kafka"
	"signal/novelty-detector/internal/repository"
)

var (
	testBroker string
	testDSN    string
	testPool   *pgxpool.Pool
)

func TestMain(m *testing.M) {
	ctx := context.Background()

	kc, err := kafkacontainer.Run(ctx, "confluentinc/cp-kafka:7.6.0",
		kafkacontainer.WithClusterID("test-cluster"),
	)
	if err != nil {
		fmt.Fprintf(os.Stderr, "kafka container start failed: %v\n", err)
		os.Exit(1)
	}

	brokers, err := kc.Brokers(ctx)
	if err != nil {
		fmt.Fprintf(os.Stderr, "kafka brokers: %v\n", err)
		_ = kc.Terminate(ctx)
		os.Exit(1)
	}
	testBroker = strings.Join(brokers, ",")

	pc, err := postgrescontainer.Run(ctx, "postgres:16-alpine",
		postgrescontainer.WithDatabase("signal_test"),
		postgrescontainer.WithUsername("signal"),
		postgrescontainer.WithPassword("signal"),
		testcontainers.WithWaitStrategy(
			wait.ForLog("database system is ready to accept connections").
				WithOccurrence(2).
				WithStartupTimeout(30*time.Second),
		),
	)
	if err != nil {
		fmt.Fprintf(os.Stderr, "postgres container start failed: %v\n", err)
		_ = kc.Terminate(ctx)
		os.Exit(1)
	}

	testDSN, err = pc.ConnectionString(ctx, "sslmode=disable")
	if err != nil {
		fmt.Fprintf(os.Stderr, "postgres dsn: %v\n", err)
		_ = kc.Terminate(ctx)
		_ = pc.Terminate(ctx)
		os.Exit(1)
	}

	testPool, err = pgxpool.New(ctx, testDSN)
	if err != nil {
		fmt.Fprintf(os.Stderr, "pgxpool: %v\n", err)
		_ = kc.Terminate(ctx)
		_ = pc.Terminate(ctx)
		os.Exit(1)
	}

	if err := applySchema(ctx, testPool); err != nil {
		fmt.Fprintf(os.Stderr, "schema: %v\n", err)
		testPool.Close()
		_ = kc.Terminate(ctx)
		_ = pc.Terminate(ctx)
		os.Exit(1)
	}

	// Capture exit code so cleanup runs before os.Exit (deferred Close skipped by os.Exit).
	code := m.Run()

	testPool.Close()
	_ = kc.Terminate(ctx)
	_ = pc.Terminate(ctx)

	os.Exit(code)
}

func applySchema(ctx context.Context, pool *pgxpool.Pool) error {
	_, err := pool.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS artists (
			id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
			name          TEXT NOT NULL,
			status        TEXT NOT NULL DEFAULT 'TRACKED',
			scrobble_count INT NOT NULL DEFAULT 0
		);
		CREATE TABLE IF NOT EXISTS listening_history (
			signal_id TEXT PRIMARY KEY,
			artist    TEXT NOT NULL,
			title     TEXT NOT NULL,
			genres    TEXT[] NOT NULL DEFAULT '{}',
			played_at TIMESTAMPTZ
		);
	`)
	return err
}

func intCfg(group string) config.Config {
	return config.Config{
		KafkaBootstrapServers: testBroker,
		KafkaConsumerGroup:    group,
		DatabaseURL:           testDSN,
		AutoFollowPlays:       3,
		KafkaFlushTimeoutMs:   10000,
		LogLevel:              "DEBUG",
	}
}

func seedArtist(t *testing.T, name, status string, scrobbles int) {
	t.Helper()
	_, err := testPool.Exec(context.Background(),
		`INSERT INTO artists (name, status, scrobble_count) VALUES ($1, $2, $3)
		 ON CONFLICT DO NOTHING`, name, status, scrobbles)
	require.NoError(t, err)
}

func produceEnriched(t *testing.T, payload map[string]any, key string) {
	t.Helper()
	p, err := kafka.NewProducer(testBroker, "test-producer", 5000)
	require.NoError(t, err)
	defer p.Close()
	require.NoError(t, p.Produce(inputTopic, payload, key))
	p.Flush(5000)
}

func consumeFirstFrom(t *testing.T, topic, group string, timeout time.Duration) *confluent.Message {
	t.Helper()
	c, err := confluent.NewConsumer(&confluent.ConfigMap{
		"bootstrap.servers":  testBroker,
		"group.id":           group,
		"auto.offset.reset":  "earliest",
		"enable.auto.commit": false,
	})
	require.NoError(t, err)
	defer c.Close()
	require.NoError(t, c.Subscribe(topic, nil))

	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		ev := c.Poll(500)
		if msg, ok := ev.(*confluent.Message); ok {
			return msg
		}
	}
	return nil
}

func runConsumerAsync(t *testing.T, cfg config.Config) {
	t.Helper()
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)

	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelDebug}))
	c, err := kafka.NewConsumer(cfg.KafkaBootstrapServers, cfg.KafkaConsumerGroup, ClientID)
	require.NoError(t, err)
	outputProducer, err := kafka.NewProducer(cfg.KafkaBootstrapServers, ClientID+"-output", cfg.KafkaFlushTimeoutMs)
	require.NoError(t, err)
	dlqProducer, err := kafka.NewProducer(cfg.KafkaBootstrapServers, ClientID+"-dlq", cfg.KafkaFlushTimeoutMs)
	require.NoError(t, err)

	go func() {
		_ = Run(ctx, cfg,
			c, outputProducer,
			&repository.PgxArtistRepo{Pool: testPool},
			&repository.PgxNoveltyRepo{Pool: testPool},
			dlq.NewPublisher(dlqProducer, logger),
			logger)
	}()
}

// T015: new artist emits tracks.novel event
func TestNewArtistEmitsNovelEvent(t *testing.T) {
	ctx := context.Background()
	_, _ = testPool.Exec(ctx, "DELETE FROM listening_history WHERE signal_id = 'new-sig-001'")
	_, _ = testPool.Exec(ctx, "DELETE FROM artists WHERE LOWER(name) = LOWER('NewBandIT001')")

	seedArtist(t, "NewBandIT001", "TRACKED", 1)
	runConsumerAsync(t, intCfg("group-t015-new"))

	produceEnriched(t, map[string]any{
		"signal_id": "new-sig-001", "artist": "NewBandIT001", "title": "Song",
		"pending_enrichment": false, "genres": []string{"indie"},
	}, "new-sig-001")

	msg := consumeFirstFrom(t, outputTopic, "reader-t015-new", 15*time.Second)
	require.NotNil(t, msg, "expected a tracks.novel event but none arrived")

	var event NoveltyEvent
	require.NoError(t, json.Unmarshal(msg.Value, &event))
	assert.Equal(t, "NewBandIT001", event.Artist)
	assert.True(t, event.NoveltySignals.ArtistIsNew)
}

// T015b: known artist with all known genres produces no output
func TestKnownArtistAllKnownGenresSilentSkip(t *testing.T) {
	ctx := context.Background()
	_, _ = testPool.Exec(ctx, "DELETE FROM listening_history WHERE signal_id IN ('old-known', 'known-sig-001')")
	_, _ = testPool.Exec(ctx, "DELETE FROM artists WHERE LOWER(name) = LOWER('KnownBandIT001')")

	seedArtist(t, "KnownBandIT001", "FOLLOWING", 10)
	_, err := testPool.Exec(ctx,
		`INSERT INTO listening_history (signal_id, artist, title, genres)
		 VALUES ('old-known', 'KnownBandIT001', 'OldSong', '{"rock"}')`)
	require.NoError(t, err)

	runConsumerAsync(t, intCfg("group-t015-known"))

	produceEnriched(t, map[string]any{
		"signal_id": "known-sig-001", "artist": "KnownBandIT001", "title": "NewSong",
		"pending_enrichment": false, "genres": []string{"rock"},
	}, "known-sig-001")

	msg := consumeFirstFrom(t, outputTopic, "reader-t015-known", 8*time.Second)
	assert.Nil(t, msg, "expected no tracks.novel event for fully-known artist")
}

// T026: auto-promotion moves TRACKED artist to FOLLOWING at threshold
func TestAutoPromotionPromotesTrackedArtist(t *testing.T) {
	ctx := context.Background()
	_, _ = testPool.Exec(ctx, "DELETE FROM listening_history WHERE signal_id = 'promo-sig-001'")
	_, _ = testPool.Exec(ctx, "DELETE FROM artists WHERE LOWER(name) = LOWER('PromotedArtistIT')")

	seedArtist(t, "PromotedArtistIT", "TRACKED", 3)

	runConsumerAsync(t, intCfg("group-t026-promo"))

	produceEnriched(t, map[string]any{
		"signal_id": "promo-sig-001", "artist": "PromotedArtistIT", "title": "Hit",
		"pending_enrichment": false, "genres": []string{"pop"},
	}, "promo-sig-001")

	msg := consumeFirstFrom(t, outputTopic, "reader-t026", 15*time.Second)
	require.NotNil(t, msg, "expected tracks.novel event for new-genre detection")

	var status string
	err := testPool.QueryRow(ctx,
		"SELECT status FROM artists WHERE LOWER(name) = LOWER('PromotedArtistIT')").Scan(&status)
	require.NoError(t, err)
	assert.Equal(t, "FOLLOWING", status)
}

// T030: malformed message routed to DLQ, consumer continues for next valid message
func TestDLQOnMalformedMessage(t *testing.T) {
	ctx := context.Background()
	_, _ = testPool.Exec(ctx, "DELETE FROM listening_history WHERE signal_id = 'dlq-valid-001'")
	_, _ = testPool.Exec(ctx, "DELETE FROM artists WHERE LOWER(name) = LOWER('DLQArtistIT')")

	seedArtist(t, "DLQArtistIT", "TRACKED", 1)

	rawProd, err := confluent.NewProducer(&confluent.ConfigMap{
		"bootstrap.servers": testBroker,
		"client.id":         "raw-producer",
	})
	require.NoError(t, err)
	defer rawProd.Close()

	// Produce malformed message (missing signal_id).
	badData, _ := json.Marshal(map[string]any{
		"artist": "DLQArtistIT", "title": "Song", "pending_enrichment": false,
	})
	topic := inputTopic
	deliveryCh := make(chan confluent.Event, 1)
	require.NoError(t, rawProd.Produce(&confluent.Message{
		TopicPartition: confluent.TopicPartition{Topic: &topic, Partition: confluent.PartitionAny},
		Value:          badData,
	}, deliveryCh))
	<-deliveryCh

	produceEnriched(t, map[string]any{
		"signal_id": "dlq-valid-001", "artist": "DLQArtistIT", "title": "ValidSong",
		"pending_enrichment": false, "genres": []string{"indie"},
	}, "dlq-valid-001")

	runConsumerAsync(t, intCfg("group-t030-dlq"))

	dlqMsg := consumeFirstFrom(t, dlq.Topic, "reader-t030-dlq", 15*time.Second)
	require.NotNil(t, dlqMsg, "expected DLQ entry for malformed message")
	var entry dlq.Entry
	require.NoError(t, json.Unmarshal(dlqMsg.Value, &entry))
	assert.Equal(t, "malformed_message", entry.ErrorReason)

	novelMsg := consumeFirstFrom(t, outputTopic, "reader-t030-novel", 15*time.Second)
	require.NotNil(t, novelMsg, "consumer stalled after DLQ — valid message never reached tracks.novel")
}
