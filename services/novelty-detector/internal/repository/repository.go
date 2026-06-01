package repository

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Artist represents a row from the artists table.
type Artist struct {
	ID            string
	Status        string
	ScrobbleCount int
}

// ArtistRepo is the interface for artist database operations.
type ArtistRepo interface {
	GetArtist(ctx context.Context, artist string) (*Artist, error)
	PromoteToFollowing(ctx context.Context, artist string, minScrobbles int) (bool, error)
}

// NoveltyRepo is the interface for novelty detection queries.
type NoveltyRepo interface {
	IsArtistNew(ctx context.Context, artist, signalID string) (bool, error)
	GetNewGenres(ctx context.Context, genres []string, signalID string) ([]string, error)
	IsTrackNew(ctx context.Context, signalID string) (bool, error)
}

// PgxArtistRepo implements ArtistRepo using pgx.
type PgxArtistRepo struct {
	Pool *pgxpool.Pool
}

const getArtistSQL = `
SELECT id, status, scrobble_count
FROM artists
WHERE LOWER(name) = LOWER($1)
`

const promoteSQL = `
UPDATE artists
SET    status = 'FOLLOWING'
WHERE  LOWER(name) = LOWER($1)
  AND  status = 'TRACKED'
  AND  scrobble_count >= $2
RETURNING id
`

func (r *PgxArtistRepo) GetArtist(ctx context.Context, artist string) (*Artist, error) {
	var a Artist
	err := r.Pool.QueryRow(ctx, getArtistSQL, artist).Scan(&a.ID, &a.Status, &a.ScrobbleCount)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, nil
		}
		return nil, fmt.Errorf("get artist %q: %w", artist, err)
	}
	return &a, nil
}

func (r *PgxArtistRepo) PromoteToFollowing(ctx context.Context, artist string, minScrobbles int) (bool, error) {
	var id string
	err := r.Pool.QueryRow(ctx, promoteSQL, artist, minScrobbles).Scan(&id)
	if err != nil {
		if err == pgx.ErrNoRows {
			return false, nil
		}
		return false, fmt.Errorf("promote artist %q: %w", artist, err)
	}
	return true, nil
}

// PgxNoveltyRepo implements NoveltyRepo using pgx.
type PgxNoveltyRepo struct {
	Pool *pgxpool.Pool
}

const isArtistNewSQL = `
SELECT NOT EXISTS (
    SELECT 1 FROM listening_history
    WHERE LOWER(artist) = LOWER($1)
      AND signal_id != $2
) AS artist_is_new
`

const getNewGenresSQL = `
SELECT ARRAY(
    SELECT g
    FROM unnest($1::text[]) AS g
    WHERE NOT EXISTS (
        SELECT 1 FROM listening_history
        WHERE genres @> ARRAY[g]
          AND signal_id != $2
    )
) AS new_genres
`

const isTrackNewSQL = `
SELECT NOT EXISTS (
    SELECT 1 FROM listening_history WHERE signal_id = $1
) AS track_is_new
`

func (r *PgxNoveltyRepo) IsArtistNew(ctx context.Context, artist, signalID string) (bool, error) {
	var isNew bool
	err := r.Pool.QueryRow(ctx, isArtistNewSQL, artist, signalID).Scan(&isNew)
	if err != nil {
		return false, fmt.Errorf("is artist new %q: %w", artist, err)
	}
	return isNew, nil
}

func (r *PgxNoveltyRepo) GetNewGenres(ctx context.Context, genres []string, signalID string) ([]string, error) {
	if len(genres) == 0 {
		return []string{}, nil
	}
	var newGenres []string
	err := r.Pool.QueryRow(ctx, getNewGenresSQL, genres, signalID).Scan(&newGenres)
	if err != nil {
		return nil, fmt.Errorf("get new genres: %w", err)
	}
	if newGenres == nil {
		newGenres = []string{}
	}
	return newGenres, nil
}

func (r *PgxNoveltyRepo) IsTrackNew(ctx context.Context, signalID string) (bool, error) {
	var isNew bool
	err := r.Pool.QueryRow(ctx, isTrackNewSQL, signalID).Scan(&isNew)
	if err != nil {
		return false, fmt.Errorf("is track new %q: %w", signalID, err)
	}
	return isNew, nil
}
