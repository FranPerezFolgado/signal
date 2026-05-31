package main

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestComputeNovelty_AllNew(t *testing.T) {
	genres := []string{"jazz", "soul"}
	signals := ComputeNovelty(genres, true, false, genres)

	assert.True(t, signals.ArtistIsNew)
	assert.False(t, signals.TrackIsNew)
	assert.Equal(t, genres, signals.NewGenres)
	assert.Empty(t, signals.KnownGenres)
	assert.InDelta(t, 1.0, signals.GenreNoveltyRatio, 0.001)
}

func TestComputeNovelty_AllKnown(t *testing.T) {
	genres := []string{"rock", "pop"}
	signals := ComputeNovelty(genres, false, false, []string{})

	assert.False(t, signals.ArtistIsNew)
	assert.Empty(t, signals.NewGenres)
	assert.Equal(t, genres, signals.KnownGenres)
	assert.InDelta(t, 0.0, signals.GenreNoveltyRatio, 0.001)
}

func TestComputeNovelty_PartiallyNew(t *testing.T) {
	genres := []string{"rock", "jazz", "soul"}
	newGenres := []string{"jazz"}
	signals := ComputeNovelty(genres, false, false, newGenres)

	assert.Equal(t, newGenres, signals.NewGenres)
	assert.ElementsMatch(t, []string{"rock", "soul"}, signals.KnownGenres)
	assert.InDelta(t, 1.0/3.0, signals.GenreNoveltyRatio, 0.001)
}

func TestComputeNovelty_EmptyGenres(t *testing.T) {
	signals := ComputeNovelty([]string{}, false, false, []string{})

	assert.Empty(t, signals.NewGenres)
	assert.Empty(t, signals.KnownGenres)
	assert.InDelta(t, 0.0, signals.GenreNoveltyRatio, 0.001)
}

func TestComputeNovelty_NilGenres(t *testing.T) {
	signals := ComputeNovelty(nil, true, true, nil)

	assert.True(t, signals.ArtistIsNew)
	assert.True(t, signals.TrackIsNew)
	assert.InDelta(t, 0.0, signals.GenreNoveltyRatio, 0.001)
}

func TestShouldEmit_ArtistNew(t *testing.T) {
	assert.True(t, ShouldEmit(NoveltySignals{ArtistIsNew: true}))
}

func TestShouldEmit_NewGenres(t *testing.T) {
	assert.True(t, ShouldEmit(NoveltySignals{NewGenres: []string{"jazz"}}))
}

func TestShouldEmit_NothingNew(t *testing.T) {
	assert.False(t, ShouldEmit(NoveltySignals{ArtistIsNew: false, NewGenres: []string{}}))
}

func TestShouldEmit_BothNew(t *testing.T) {
	assert.True(t, ShouldEmit(NoveltySignals{ArtistIsNew: true, NewGenres: []string{"jazz"}}))
}
