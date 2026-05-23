-- migrate:up
ALTER TABLE artists ADD COLUMN IF NOT EXISTS scrobble_count INT DEFAULT 0;

-- migrate:down
ALTER TABLE artists DROP COLUMN IF EXISTS scrobble_count;
