-- migrate:up
ALTER TABLE artists
  ADD COLUMN IF NOT EXISTS last_similar_explored_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS origin_artist_id UUID REFERENCES artists(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_artists_lastfm_mbid
  ON artists ((external_ids->>'lastfm_mbid'))
  WHERE external_ids->>'lastfm_mbid' IS NOT NULL;

-- migrate:down
DROP INDEX IF EXISTS idx_artists_lastfm_mbid;

ALTER TABLE artists
  DROP COLUMN IF EXISTS last_similar_explored_at,
  DROP COLUMN IF EXISTS origin_artist_id;
