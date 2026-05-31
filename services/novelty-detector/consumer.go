package main

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"os"
	"os/signal"
	"syscall"
	"time"

	kafka "github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/jackc/pgx/v5/pgconn"
)

const (
	inputTopic  = "tracks.enriched"
	outputTopic = "tracks.novel"
	clientID    = "novelty-detector"
)

// RunConsumer is the main consumer loop. It subscribes to tracks.enriched, processes
// each message, and emits to tracks.novel. All dependencies are injected for testability.
func RunConsumer(
	cfg Config,
	consumer KafkaConsumer,
	outputProducer KafkaProducer,
	artistRepo ArtistRepo,
	noveltyRepo NoveltyRepo,
	dlq *DLQPublisher,
	logger *slog.Logger,
) error {
	ctx := context.Background()

	if err := consumer.Subscribe([]string{inputTopic}); err != nil {
		return err
	}

	// Graceful shutdown: set stop=true on SIGTERM or SIGINT.
	stopCh := make(chan os.Signal, 1)
	signal.Notify(stopCh, syscall.SIGTERM, syscall.SIGINT)

	var (
		processed       int
		skippedPending  int
		skippedNoNovel  int
		failedDLQ       int
		stop            bool
	)

	logger.Info("novelty_detector_started", "input_topic", inputTopic, "output_topic", outputTopic)

	defer func() {
		logger.Info("novelty_detector_stopped",
			"processed", processed,
			"skipped_pending", skippedPending,
			"skipped_no_novelty", skippedNoNovel,
			"failed_dlq", failedDLQ,
		)
		outputProducer.Flush(cfg.KafkaFlushTimeoutMs)
		outputProducer.Close()
		consumer.Close()
	}()

	for !stop {
		select {
		case <-stopCh:
			logger.Info("shutdown_requested")
			stop = true
			continue
		default:
		}

		ev := consumer.Poll(1000)
		if ev == nil {
			continue
		}

		msg, ok := ev.(*kafka.Message)
		if !ok {
			// Kafka error event (e.g. rebalance, partition EOF) — not a message.
			if kErr, isErr := ev.(kafka.Error); isErr {
				logger.Warn("kafka_event", "error", kErr)
			}
			continue
		}

		// Parse raw JSON payload.
		var raw map[string]any
		if err := json.Unmarshal(msg.Value, &raw); err != nil {
			dlq.Publish("malformed_message", "failed to parse JSON: "+err.Error(), string(msg.Value))
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}

		// Validate required fields.
		if !isValidMessage(raw) {
			dlq.Publish("malformed_message", "invalid or missing required fields", raw)
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}

		// Decode into EnrichedTrack.
		var track EnrichedTrack
		data, _ := json.Marshal(raw)
		if err := json.Unmarshal(data, &track); err != nil {
			dlq.Publish("malformed_message", "failed to decode track: "+err.Error(), raw)
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}

		// Skip tracks awaiting enrichment — not an error.
		if track.PendingEnrichment {
			logger.Debug("skipping_pending_enrichment", "signal_id", truncate(track.SignalID, 8))
			skippedPending++
			consumer.Commit() //nolint:errcheck
			continue
		}

		genres := filterStrings(track.Genres)

		// Fetch artist from DB.
		artist, err := artistRepo.GetArtist(ctx, track.Artist)
		if err != nil {
			if isOperationalError(err) {
				// Crash — Docker will restart and reconnect.
				return err
			}
			dlq.Publish("processing_error", "failed to fetch artist: "+err.Error(), raw)
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}
		if artist == nil {
			dlq.Publish("artist_record_missing", "artist not found in artists table", raw)
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}

		// Query novelty.
		artistIsNew, err := noveltyRepo.IsArtistNew(ctx, track.Artist, track.SignalID)
		if err != nil {
			if isOperationalError(err) {
				return err
			}
			dlq.Publish("processing_error", "novelty query failed: "+err.Error(), raw)
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}

		newGenres, err := noveltyRepo.GetNewGenres(ctx, genres, track.SignalID)
		if err != nil {
			if isOperationalError(err) {
				return err
			}
			dlq.Publish("processing_error", "genre query failed: "+err.Error(), raw)
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}

		trackIsNew, err := noveltyRepo.IsTrackNew(ctx, track.SignalID)
		if err != nil {
			if isOperationalError(err) {
				return err
			}
			dlq.Publish("processing_error", "track-new query failed: "+err.Error(), raw)
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}

		// Best-effort auto-promotion: TRACKED → FOLLOWING when threshold met.
		if artist.Status == "TRACKED" && artist.ScrobbleCount >= cfg.AutoFollowPlays {
			promoted, promErr := artistRepo.PromoteToFollowing(ctx, track.Artist, cfg.AutoFollowPlays)
			if promErr != nil {
				logger.Warn("auto_promotion_failed", "artist", track.Artist, "error", promErr)
				// Do NOT return or DLQ — promotion failure is best-effort.
			} else if promoted {
				logger.Info("artist_promoted", "artist", track.Artist, "scrobble_count", artist.ScrobbleCount)
			}
		}

		signals := ComputeNovelty(genres, artistIsNew, trackIsNew, newGenres)

		if !ShouldEmit(signals) {
			skippedNoNovel++
			consumer.Commit() //nolint:errcheck
			continue
		}

		event := NoveltyEvent{
			SignalID:         track.SignalID,
			Artist:           track.Artist,
			ArtistID:         track.ArtistID,
			Genres:           genres,
			ArtistPopularity: track.ArtistPopularity,
			TrackPopularity:  track.TrackPopularity,
			PlayedAt:         track.PlayedAt,
			NoveltySignals:   signals,
		}

		if err := outputProducer.Produce(outputTopic, event, track.SignalID); err != nil {
			if isOperationalError(err) {
				return err
			}
			dlq.Publish("processing_error", "failed to produce event: "+err.Error(), raw)
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}

		// Flush-then-commit: only commit offset after durable delivery confirmation.
		unflushed := outputProducer.Flush(cfg.KafkaFlushTimeoutMs)
		if unflushed > 0 {
			logger.Error("kafka_flush_timeout",
				"signal_id", truncate(track.SignalID, 8),
				"unflushed", unflushed,
			)
			// Do NOT commit — message will be redelivered on restart.
			continue
		}

		processed++
		logger.Info("novelty_detected",
			"signal_id", truncate(track.SignalID, 8),
			"artist", track.Artist,
			"artist_is_new", signals.ArtistIsNew,
			"new_genres", signals.NewGenres,
			"genre_novelty_ratio", signals.GenreNoveltyRatio,
		)
		consumer.Commit() //nolint:errcheck
	}

	return nil
}

// isValidMessage checks that a raw parsed message contains all required fields.
func isValidMessage(raw map[string]any) bool {
	signalID, ok := raw["signal_id"].(string)
	if !ok || signalID == "" {
		return false
	}
	artist, ok := raw["artist"].(string)
	if !ok || artist == "" {
		return false
	}
	title, ok := raw["title"].(string)
	if !ok || title == "" {
		return false
	}
	if _, hasPending := raw["pending_enrichment"]; !hasPending {
		return false
	}
	return true
}

// isOperationalError returns true for transient infrastructure failures that
// should crash the service (rather than DLQ the message).
func isOperationalError(err error) bool {
	var pgErr *pgconn.ConnectError
	return errors.As(err, &pgErr)
}

// filterStrings returns a non-nil slice of non-empty strings from src.
func filterStrings(src []string) []string {
	out := make([]string, 0, len(src))
	for _, s := range src {
		if s != "" {
			out = append(out, s)
		}
	}
	return out
}

// truncate returns the first n bytes of s (or s itself if shorter).
func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}

// shutdownTimeout is the maximum time to wait for graceful shutdown (SC-003).
const shutdownTimeout = 5 * time.Second
