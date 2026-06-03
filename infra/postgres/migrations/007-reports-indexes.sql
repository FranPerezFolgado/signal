-- migrate:up

-- Performance index for period-filtered reports queries
CREATE INDEX IF NOT EXISTS idx_listening_history_played_at
  ON listening_history(played_at);

-- Enables period-aware curation funnel
ALTER TABLE artists ADD COLUMN IF NOT EXISTS status_changed_at TIMESTAMPTZ;

-- migrate:down
DROP INDEX IF EXISTS idx_listening_history_played_at;
ALTER TABLE artists DROP COLUMN IF EXISTS status_changed_at;
