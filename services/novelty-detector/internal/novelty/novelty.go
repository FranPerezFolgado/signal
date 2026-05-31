package novelty

// Signals holds the detection results for a single track.
type Signals struct {
	TrackIsNew        bool     `json:"track_is_new"`
	ArtistIsNew       bool     `json:"artist_is_new"`
	NewGenres         []string `json:"new_genres"`
	KnownGenres       []string `json:"known_genres"`
	GenreNoveltyRatio float64  `json:"genre_novelty_ratio"`
}

// Compute builds Signals from DB query results.
// Precondition: newGenres is a subset of genres (guaranteed by the DB query).
func Compute(genres []string, artistIsNew, trackIsNew bool, newGenres []string) Signals {
	newGenreSet := make(map[string]struct{}, len(newGenres))
	for _, g := range newGenres {
		newGenreSet[g] = struct{}{}
	}

	knownGenres := make([]string, 0, len(genres))
	for _, g := range genres {
		if _, isNew := newGenreSet[g]; !isNew {
			knownGenres = append(knownGenres, g)
		}
	}

	var ratio float64
	if len(genres) > 0 {
		ratio = float64(len(newGenres)) / float64(len(genres))
	}

	return Signals{
		TrackIsNew:        trackIsNew,
		ArtistIsNew:       artistIsNew,
		NewGenres:         newGenres,
		KnownGenres:       knownGenres,
		GenreNoveltyRatio: ratio,
	}
}

// ShouldEmit returns true if the signals warrant emitting a tracks.novel event.
func ShouldEmit(s Signals) bool {
	return s.ArtistIsNew || len(s.NewGenres) > 0
}
