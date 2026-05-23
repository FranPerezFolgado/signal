-- migrate:up

-- DROP and RENAME must be separate ALTER TABLE statements in PostgreSQL.
-- The RENAME is guarded with a DO block so it's a no-op on fresh databases
-- where init.sql already created the column as artist_popularity.

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
