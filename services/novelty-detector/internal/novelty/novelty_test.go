package novelty

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestCompute_AllNew(t *testing.T) {
	genres := []string{"jazz", "soul"}
	s := Compute(genres, true, false, genres)

	assert.True(t, s.ArtistIsNew)
	assert.False(t, s.TrackIsNew)
	assert.Equal(t, genres, s.NewGenres)
	assert.Empty(t, s.KnownGenres)
	assert.InDelta(t, 1.0, s.GenreNoveltyRatio, 0.001)
}

func TestCompute_AllKnown(t *testing.T) {
	genres := []string{"rock", "pop"}
	s := Compute(genres, false, false, []string{})

	assert.False(t, s.ArtistIsNew)
	assert.Empty(t, s.NewGenres)
	assert.Equal(t, genres, s.KnownGenres)
	assert.InDelta(t, 0.0, s.GenreNoveltyRatio, 0.001)
}

func TestCompute_PartiallyNew(t *testing.T) {
	genres := []string{"rock", "jazz", "soul"}
	newGenres := []string{"jazz"}
	s := Compute(genres, false, false, newGenres)

	assert.Equal(t, newGenres, s.NewGenres)
	assert.ElementsMatch(t, []string{"rock", "soul"}, s.KnownGenres)
	assert.InDelta(t, 1.0/3.0, s.GenreNoveltyRatio, 0.001)
}

func TestCompute_EmptyGenres(t *testing.T) {
	s := Compute([]string{}, false, false, []string{})

	assert.Empty(t, s.NewGenres)
	assert.Empty(t, s.KnownGenres)
	assert.InDelta(t, 0.0, s.GenreNoveltyRatio, 0.001)
}

func TestCompute_NilGenres(t *testing.T) {
	s := Compute(nil, true, true, nil)

	assert.True(t, s.ArtistIsNew)
	assert.True(t, s.TrackIsNew)
	assert.InDelta(t, 0.0, s.GenreNoveltyRatio, 0.001)
}

func TestShouldEmit_ArtistNew(t *testing.T) {
	assert.True(t, ShouldEmit(Signals{ArtistIsNew: true}))
}

func TestShouldEmit_NewGenres(t *testing.T) {
	assert.True(t, ShouldEmit(Signals{NewGenres: []string{"jazz"}}))
}

func TestShouldEmit_NothingNew(t *testing.T) {
	assert.False(t, ShouldEmit(Signals{ArtistIsNew: false, NewGenres: []string{}}))
}

func TestShouldEmit_BothNew(t *testing.T) {
	assert.True(t, ShouldEmit(Signals{ArtistIsNew: true, NewGenres: []string{"jazz"}}))
}
