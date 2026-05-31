package main

// ComputeNovelty builds the NoveltySignals for a track given the results of the
// three database novelty queries. It is a pure function with no side effects.
func ComputeNovelty(genres []string, artistIsNew, trackIsNew bool, newGenres []string) NoveltySignals {
	knownGenres := make([]string, 0, len(genres))
	newGenreSet := make(map[string]struct{}, len(newGenres))
	for _, g := range newGenres {
		newGenreSet[g] = struct{}{}
	}
	for _, g := range genres {
		if _, isNew := newGenreSet[g]; !isNew {
			knownGenres = append(knownGenres, g)
		}
	}

	var ratio float64
	if len(genres) > 0 {
		ratio = float64(len(newGenres)) / float64(len(genres))
	}

	return NoveltySignals{
		TrackIsNew:        trackIsNew,
		ArtistIsNew:       artistIsNew,
		NewGenres:         newGenres,
		KnownGenres:       knownGenres,
		GenreNoveltyRatio: ratio,
	}
}

// ShouldEmit returns true if the novelty signals warrant emitting a tracks.novel event.
// An event is emitted if the artist is new OR at least one genre is new.
func ShouldEmit(signals NoveltySignals) bool {
	return signals.ArtistIsNew || len(signals.NewGenres) > 0
}
