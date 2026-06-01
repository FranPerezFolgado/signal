package consumer

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net"
	"time"

	confluent "github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/jackc/pgx/v5/pgconn"

	"signal/novelty-detector/internal/config"
	"signal/novelty-detector/internal/dlq"
	"signal/novelty-detector/internal/kafka"
	"signal/novelty-detector/internal/novelty"
	"signal/novelty-detector/internal/repository"
)

const (
	inputTopic  = "tracks.enriched"
	outputTopic = "tracks.novel"
	ClientID    = "novelty-detector"

	// shutdownTimeout bounds the deferred flush+close sequence after the loop exits.
	shutdownTimeout = 5 * time.Second
)

// EnrichedTrack is the incoming message schema for tracks.enriched.
// PendingEnrichment is a pointer so its absence is distinguishable from false.
type EnrichedTrack struct {
	SignalID          string   `json:"signal_id"`
	Artist            string   `json:"artist"`
	ArtistID          *string  `json:"artist_id"`
	Title             string   `json:"title"`
	Genres            []string `json:"genres"`
	ArtistPopularity  *int     `json:"artist_popularity"`
	TrackPopularity   *int     `json:"track_popularity"`
	PlayedAt          *string  `json:"played_at"`
	PendingEnrichment *bool    `json:"pending_enrichment"`
}

// NoveltyEvent is the outgoing message schema for tracks.novel.
type NoveltyEvent struct {
	SignalID         string          `json:"signal_id"`
	Artist           string          `json:"artist"`
	ArtistID         *string         `json:"artist_id"`
	Genres           []string        `json:"genres"`
	ArtistPopularity *int            `json:"artist_popularity"`
	TrackPopularity  *int            `json:"track_popularity"`
	PlayedAt         *string         `json:"played_at"`
	NoveltySignals   novelty.Signals `json:"novelty_signals"`
}

// Run is the main consumer loop. It subscribes to tracks.enriched, processes each
// message, and emits to tracks.novel. ctx cancellation triggers graceful shutdown.
// Signal handling (signal.Notify / signal.Stop) belongs in main; pass the resulting
// context here so tests can control shutdown without registering OS signal handlers.
func Run(
	ctx context.Context,
	cfg config.Config,
	consumer kafka.Consumer,
	outputProducer kafka.Producer,
	artistRepo repository.ArtistRepo,
	noveltyRepo repository.NoveltyRepo,
	dlqWriter dlq.Writer,
	logger *slog.Logger,
) error {
	if err := consumer.Subscribe([]string{inputTopic}); err != nil {
		return err
	}

	var (
		processed      int
		skippedPending int
		skippedNoNovel int
		failedDLQ      int
	)

	logger.Info("novelty_detector_started", "input_topic", inputTopic, "output_topic", outputTopic)

	// Enforce a hard deadline on the shutdown sequence so close/flush never hang forever.
	defer func() {
		done := make(chan struct{})
		go func() {
			defer close(done)
			outputProducer.Flush(int(shutdownTimeout.Milliseconds()))
			outputProducer.Close()
			consumer.Close() //nolint:errcheck
		}()
		timer := time.NewTimer(shutdownTimeout)
		defer timer.Stop()
		select {
		case <-done:
		case <-timer.C:
			logger.Warn("shutdown_deadline_exceeded", "timeout", shutdownTimeout)
		}
		logger.Info("novelty_detector_stopped",
			"processed", processed,
			"skipped_pending", skippedPending,
			"skipped_no_novelty", skippedNoNovel,
			"failed_dlq", failedDLQ,
		)
	}()

	for {
		select {
		case <-ctx.Done():
			logger.Info("shutdown_requested")
			return nil
		default:
		}

		ev := consumer.Poll(1000)
		if ev == nil {
			continue
		}

		msg, ok := ev.(*confluent.Message)
		if !ok {
			if kErr, isErr := ev.(confluent.Error); isErr {
				logger.Warn("kafka_event", "error", kErr)
			}
			continue
		}

		// Decode directly into typed struct — no intermediate map round-trip.
		var track EnrichedTrack
		if err := json.Unmarshal(msg.Value, &track); err != nil {
			dlqWriter.Publish("malformed_message", "failed to parse JSON: "+err.Error(),
				truncate(string(msg.Value), 4096))
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}

		if !isValidTrack(&track) {
			dlqWriter.Publish("malformed_message", "invalid or missing required fields", track)
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}

		if track.PendingEnrichment != nil && *track.PendingEnrichment {
			logger.Debug("skipping_pending_enrichment", "signal_id", truncate(track.SignalID, 8))
			skippedPending++
			consumer.Commit() //nolint:errcheck
			continue
		}

		genres := filterStrings(track.Genres)

		artist, err := artistRepo.GetArtist(ctx, track.Artist)
		if err != nil {
			if isOperationalError(err) {
				return err
			}
			dlqWriter.Publish("processing_error", "failed to fetch artist: "+err.Error(), track)
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}
		if artist == nil {
			dlqWriter.Publish("artist_record_missing", "artist not found in artists table", track)
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}

		artistIsNew, err := noveltyRepo.IsArtistNew(ctx, track.Artist, track.SignalID)
		if err != nil {
			if isOperationalError(err) {
				return err
			}
			dlqWriter.Publish("processing_error", "novelty query failed: "+err.Error(), track)
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}

		newGenres, err := noveltyRepo.GetNewGenres(ctx, genres, track.SignalID)
		if err != nil {
			if isOperationalError(err) {
				return err
			}
			dlqWriter.Publish("processing_error", "genre query failed: "+err.Error(), track)
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}

		trackIsNew, err := noveltyRepo.IsTrackNew(ctx, track.SignalID)
		if err != nil {
			if isOperationalError(err) {
				return err
			}
			dlqWriter.Publish("processing_error", "track-new query failed: "+err.Error(), track)
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}

		// Best-effort auto-promotion: TRACKED → FOLLOWING when threshold met.
		if artist.Status == "TRACKED" && artist.ScrobbleCount >= cfg.AutoFollowPlays {
			promoted, promErr := artistRepo.PromoteToFollowing(ctx, track.Artist, cfg.AutoFollowPlays)
			if promErr != nil {
				logger.Warn("auto_promotion_failed", "artist", track.Artist, "error", promErr)
			} else if promoted {
				logger.Info("artist_promoted", "artist", track.Artist, "scrobble_count", artist.ScrobbleCount)
			}
		}

		signals := novelty.Compute(genres, artistIsNew, trackIsNew, newGenres)

		if !novelty.ShouldEmit(signals) {
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
			dlqWriter.Publish("processing_error", "failed to produce event: "+err.Error(), track)
			failedDLQ++
			consumer.Commit() //nolint:errcheck
			continue
		}

		// Produce() already confirmed delivery via its internal delivery channel.
		// Commit only after that confirmation — the deferred Flush handles any
		// remaining buffered messages on shutdown.
		processed++
		logger.Info("novelty_detected",
			"signal_id", truncate(track.SignalID, 8),
			"artist", truncate(track.Artist, 64),
			"artist_is_new", signals.ArtistIsNew,
			"new_genres", signals.NewGenres,
			"genre_novelty_ratio", signals.GenreNoveltyRatio,
		)
		consumer.Commit() //nolint:errcheck
	}
}

// isValidTrack returns true if all fields required for processing are present.
func isValidTrack(t *EnrichedTrack) bool {
	return t.SignalID != "" && t.Artist != "" && t.Title != "" && t.PendingEnrichment != nil
}

// isOperationalError returns true for infrastructure failures that should crash
// the service (triggering a Docker restart) rather than routing to the DLQ.
func isOperationalError(err error) bool {
	// Connection establishment failure.
	var connectErr *pgconn.ConnectError
	if errors.As(err, &connectErr) {
		return true
	}
	// SQLSTATE class 08: connection exception (dropped during a running query).
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) {
		return len(pgErr.Code) >= 2 && pgErr.Code[:2] == "08"
	}
	// Network-level errors from the transport layer.
	var netErr net.Error
	if errors.As(err, &netErr) {
		return true
	}
	return errors.Is(err, io.ErrUnexpectedEOF) || errors.Is(err, io.EOF)
}

func filterStrings(src []string) []string {
	out := make([]string, 0, len(src))
	for _, s := range src {
		if s != "" {
			out = append(out, s)
		}
	}
	return out
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}
