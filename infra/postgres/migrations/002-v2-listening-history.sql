-- migrate:up
--
-- Invariant: init.sql represents the v2 final schema for fresh databases.
-- This migration handles in-place upgrades from v1 (audio_features, popularity).
-- All statements are idempotent: DROP IF EXISTS, ADD IF NOT EXISTS, and a DO $$
-- guard on RENAME so fresh installs (where the column is already artist_popularity)
-- apply this migration as a safe no-op.
--
-- DROP and RENAME must be separate ALTER TABLE statements in PostgreSQL.

ALTER TABLE listening_history DROP COLUMN IF EXISTS audio_features;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'listening_history' AND column_name = 'popularity'
    ) THEN
        ALTER TABLE listening_history RENAME COLUMN popularity TO artist_popularity;
    END IF;
END $$;

ALTER TABLE listening_history ADD COLUMN IF NOT EXISTS track_id           TEXT;
ALTER TABLE listening_history ADD COLUMN IF NOT EXISTS track_popularity   INT;
ALTER TABLE listening_history ADD COLUMN IF NOT EXISTS pending_enrichment BOOLEAN DEFAULT false;

-- migrate:down

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'listening_history' AND column_name = 'artist_popularity'
    ) THEN
        ALTER TABLE listening_history RENAME COLUMN artist_popularity TO popularity;
    END IF;
END $$;

ALTER TABLE listening_history ADD COLUMN IF NOT EXISTS audio_features JSONB;
ALTER TABLE listening_history DROP COLUMN IF EXISTS track_id;
ALTER TABLE listening_history DROP COLUMN IF EXISTS track_popularity;
ALTER TABLE listening_history DROP COLUMN IF EXISTS pending_enrichment;
