-- migrate:up
--
-- Replace the signal_id-only unique constraint with (signal_id, played_at) so
-- that each play event is a distinct row. signal_id continues to identify the
-- canonical track; the combination with played_at identifies a unique play event.
--

ALTER TABLE listening_history
    DROP CONSTRAINT IF EXISTS listening_history_signal_id_key;

DO $$
BEGIN
    BEGIN
        ALTER TABLE listening_history ALTER COLUMN played_at SET NOT NULL;
    EXCEPTION WHEN others THEN
        NULL; -- already NOT NULL
    END;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'listening_history_signal_id_played_at_key'
    ) THEN
        ALTER TABLE listening_history
            ADD CONSTRAINT listening_history_signal_id_played_at_key UNIQUE (signal_id, played_at);
    END IF;
END $$;

-- migrate:down

ALTER TABLE listening_history
    DROP CONSTRAINT IF EXISTS listening_history_signal_id_played_at_key;

ALTER TABLE listening_history
    ALTER COLUMN played_at DROP NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'listening_history_signal_id_key'
    ) THEN
        ALTER TABLE listening_history
            ADD CONSTRAINT listening_history_signal_id_key UNIQUE (signal_id);
    END IF;
END $$;
