import hashlib

import pytest
from signal_normalizer.signal_id import compute_signal_id, normalize_text


class TestNormalizeText:
    def test_lowercase(self) -> None:
        assert normalize_text("ACTRESS") == "actress"

    def test_punctuation_stripped(self) -> None:
        assert normalize_text("Ascending!") == "ascending"

    def test_whitespace_collapsed(self) -> None:
        assert normalize_text("  The  XX  ") == "the xx"

    def test_unicode_preserved(self) -> None:
        assert normalize_text("Sigur Rós") == "sigur rós"

    def test_unicode_lowercase(self) -> None:
        assert normalize_text("SIGUR RÓS") == "sigur rós"

    def test_empty_string(self) -> None:
        assert normalize_text("") == ""

    def test_only_punctuation(self) -> None:
        assert normalize_text("!!!") == ""

    def test_only_whitespace(self) -> None:
        assert normalize_text("   ") == ""

    def test_numeric(self) -> None:
        assert normalize_text("808") == "808"

    def test_very_long_string(self) -> None:
        long = "a" * 10_000
        result = normalize_text(long)
        assert result == long


class TestComputeSignalId:
    def test_returns_64_char_hex(self) -> None:
        result = compute_signal_id("Actress", "Ascending")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_spec_scenario_1(self) -> None:
        expected = hashlib.sha256(b"actress ascending").hexdigest()
        assert compute_signal_id("Actress", "Ascending") == expected

    def test_spec_scenario_2_case_insensitive(self) -> None:
        assert compute_signal_id("ACTRESS", "Ascending!") == compute_signal_id("Actress", "Ascending")  # noqa: E501

    def test_unicode_preserved(self) -> None:
        expected = hashlib.sha256("sigur rós ára bátur".encode()).hexdigest()
        assert compute_signal_id("Sigur Rós", "Ára bátur") == expected

    def test_unicode_uppercase_same_as_lower(self) -> None:
        assert compute_signal_id("SIGUR RÓS", "ÁRA BÁTUR") == compute_signal_id(
            "Sigur Rós", "Ára bátur"
        )

    def test_extra_whitespace_collapsed(self) -> None:
        assert compute_signal_id("  Actress  ", "  Ascending  ") == compute_signal_id(
            "Actress", "Ascending"
        )

    def test_internal_whitespace_collapsed(self) -> None:
        assert compute_signal_id("The  XX", "Intro") == compute_signal_id("The XX", "Intro")

    def test_deterministic(self) -> None:
        assert compute_signal_id("Burial", "Archangel") == compute_signal_id("Burial", "Archangel")

    def test_separator_is_space(self) -> None:
        # artist="a" title="b" → sha256("a b"), not sha256("ab")
        assert compute_signal_id("a", "b") != compute_signal_id("a b", "")

    @pytest.mark.parametrize(
        "artist,title",
        [
            ("Actress", "ascending"),
            ("actress", "Ascending"),
            ("ACTRESS", "ascending"),
            ("actress", "ascending"),
        ],
    )
    def test_all_case_variants_same(self, artist: str, title: str) -> None:
        assert compute_signal_id(artist, title) == compute_signal_id("Actress", "Ascending")
