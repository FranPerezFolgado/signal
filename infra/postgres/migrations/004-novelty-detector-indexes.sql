-- Migration 004: indexes required by the novelty-detector service
-- is_artist_new uses LOWER(artist) = LOWER(%s) against listening_history;
-- without a functional index this is a full table scan on every message.

CREATE INDEX IF NOT EXISTS idx_listening_history_artist_lower
    ON listening_history (LOWER(artist));
