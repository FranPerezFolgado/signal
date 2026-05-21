-- Schema inicial del MVP de Signal

CREATE TABLE listening_history (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  signal_id       TEXT NOT NULL UNIQUE,
  artist          TEXT NOT NULL,
  artist_id       TEXT,
  title           TEXT NOT NULL,
  genres          TEXT[],
  played_at       TIMESTAMPTZ,
  sources         TEXT[],
  audio_features  JSONB,
  popularity      INT,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_listening_history_artist ON listening_history(artist);
CREATE INDEX idx_listening_history_genres ON listening_history USING GIN(genres);

CREATE TABLE artists (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name             TEXT NOT NULL,
  external_ids     JSONB,
  status           TEXT NOT NULL DEFAULT 'TRACKED',
  high_priority    BOOLEAN DEFAULT false,
  source           TEXT,
  genres           TEXT[],
  play_count       INT DEFAULT 0,
  added_at         TIMESTAMPTZ DEFAULT now(),
  first_seen_at    TIMESTAMPTZ DEFAULT now(),
  last_explored_at TIMESTAMPTZ
);

-- Unique artist identity: normalised name ensures idempotent upserts from normalizer
CREATE UNIQUE INDEX idx_artists_name_lower ON artists (LOWER(name));

CREATE TABLE artist_recommendations (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  artist_id       UUID REFERENCES artists(id),
  score           FLOAT NOT NULL,
  score_breakdown JSONB,
  evidence_tracks JSONB,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE ingester_checkpoints (
  service        TEXT PRIMARY KEY,
  last_played_at TIMESTAMPTZ NOT NULL,
  updated_at     TIMESTAMPTZ DEFAULT now()
);
