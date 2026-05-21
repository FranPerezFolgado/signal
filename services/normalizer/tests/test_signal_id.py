import pytest

from signal_normalizer.signal_id import compute_signal_id


class TestComputeSignalId:
    def test_basic(self) -> None:
        result = compute_signal_id("Actress", "Ascending")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_case_insensitive(self) -> None:
        assert compute_signal_id("Actress", "Ascending") == compute_signal_id("ACTRESS", "ASCENDING")

    def test_punctuation_stripped(self) -> None:
        assert compute_signal_id("Actress", "Ascending") == compute_signal_id("ACTRESS", "Ascending!")

    def test_mixed_case_and_punctuation(self) -> None:
        assert compute_signal_id("Actress", "Ascending") == compute_signal_id("actress", "ascending")

    def test_spec_scenario_1(self) -> None:
        import hashlib
        expected = hashlib.sha256(b"actress ascending").hexdigest()
        assert compute_signal_id("Actress", "Ascending") == expected

    def test_spec_scenario_2(self) -> None:
        assert compute_signal_id("ACTRESS", "Ascending!") == compute_signal_id("Actress", "Ascending")

    def test_unicode_preserved(self) -> None:
        import hashlib
        expected = hashlib.sha256("sigur rós ára bátur".encode()).hexdigest()
        assert compute_signal_id("Sigur Rós", "Ára bátur") == expected

    def test_unicode_case(self) -> None:
        assert compute_signal_id("Sigur Rós", "Ára bátur") == compute_signal_id(
            "SIGUR RÓS", "ÁRA BÁTUR"
        )

    def test_extra_whitespace_collapsed(self) -> None:
        assert compute_signal_id("  Actress  ", "  Ascending  ") == compute_signal_id(
            "Actress", "Ascending"
        )

    def test_internal_whitespace_collapsed(self) -> None:
        assert compute_signal_id("The  XX", "Intro") == compute_signal_id("The XX", "Intro")

    def test_deterministic(self) -> None:
        assert compute_signal_id("Burial", "Archangel") == compute_signal_id("Burial", "Archangel")

    @pytest.mark.parametrize(
        "artist,title",
        [
            ("Actress", "ascending"),
            ("actress", "Ascending"),
            ("ACTRESS", "ascending"),
            ("actress", "ascending"),
        ],
    )
    def test_all_variants_same(self, artist: str, title: str) -> None:
        assert compute_signal_id(artist, title) == compute_signal_id("Actress", "Ascending")
