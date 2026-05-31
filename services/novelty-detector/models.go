package main

// EnrichedTrack is the incoming message from the tracks.enriched Kafka topic.
type EnrichedTrack struct {
	SignalID          string   `json:"signal_id"`
	Artist            string   `json:"artist"`
	ArtistID          *string  `json:"artist_id"`
	Title             string   `json:"title"`
	Genres            []string `json:"genres"`
	ArtistPopularity  *int     `json:"artist_popularity"`
	TrackPopularity   *int     `json:"track_popularity"`
	PlayedAt          *string  `json:"played_at"`
	PendingEnrichment bool     `json:"pending_enrichment"`
}

// NoveltySignals holds the novelty detection results for a single track.
type NoveltySignals struct {
	TrackIsNew        bool     `json:"track_is_new"`
	ArtistIsNew       bool     `json:"artist_is_new"`
	NewGenres         []string `json:"new_genres"`
	KnownGenres       []string `json:"known_genres"`
	GenreNoveltyRatio float64  `json:"genre_novelty_ratio"`
}

// NoveltyEvent is the outgoing message produced to the tracks.novel Kafka topic.
type NoveltyEvent struct {
	SignalID         string         `json:"signal_id"`
	Artist           string         `json:"artist"`
	ArtistID         *string        `json:"artist_id"`
	Genres           []string       `json:"genres"`
	ArtistPopularity *int           `json:"artist_popularity"`
	TrackPopularity  *int           `json:"track_popularity"`
	PlayedAt         *string        `json:"played_at"`
	NoveltySignals   NoveltySignals `json:"novelty_signals"`
}

// DLQEntry is the error envelope published to novelty-detector.dlq.
type DLQEntry struct {
	ErrorReason     string `json:"error_reason"`
	ErrorDetail     string `json:"error_detail"`
	OriginalPayload any    `json:"original_payload"`
	FailedAt        string `json:"failed_at"`
}

// Artist represents a row from the artists PostgreSQL table.
type Artist struct {
	ID            string
	Status        string
	ScrobbleCount int
}
