-- migrate:up
ALTER TABLE artist_recommendations
    ADD CONSTRAINT uq_artist_recommendations_artist_id UNIQUE (artist_id);

-- migrate:down
ALTER TABLE artist_recommendations
    DROP CONSTRAINT uq_artist_recommendations_artist_id;
