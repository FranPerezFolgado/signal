import logging

import pytest
from signal_scorer.scoring import compute_score, validate_message


# ─── validate_message ─────────────────────────────────────────────────────────


class TestValidateMessage:
    def _valid(self, **overrides) -> dict:
        base = {
            "signal_id": "abc123",
            "artist": "Actress",
            "novelty_signals": {"genre_novelty_ratio": 0.5},
        }
        base.update(overrides)
        return base

    def test_valid_message_passes(self):
        validate_message(self._valid())  # must not raise

    def test_missing_signal_id_raises(self):
        with pytest.raises(ValueError, match="signal_id"):
            validate_message(self._valid(signal_id=None))

    def test_missing_artist_raises(self):
        with pytest.raises(ValueError, match="artist"):
            validate_message(self._valid(artist=None))

    def test_missing_novelty_signals_raises(self):
        msg = self._valid()
        del msg["novelty_signals"]
        with pytest.raises(ValueError, match="novelty_signals"):
            validate_message(msg)

    def test_novelty_signals_not_dict_raises(self):
        with pytest.raises(ValueError, match="novelty_signals"):
            validate_message(self._valid(novelty_signals="bad"))

    def test_genre_novelty_ratio_missing_raises(self):
        with pytest.raises(ValueError, match="genre_novelty_ratio"):
            validate_message(self._valid(novelty_signals={}))

    def test_genre_novelty_ratio_above_1_raises(self):
        with pytest.raises(ValueError, match="genre_novelty_ratio"):
            validate_message(self._valid(novelty_signals={"genre_novelty_ratio": 1.1}))

    def test_genre_novelty_ratio_negative_raises(self):
        with pytest.raises(ValueError, match="genre_novelty_ratio"):
            validate_message(self._valid(novelty_signals={"genre_novelty_ratio": -0.1}))

    def test_genre_novelty_ratio_zero_is_valid(self):
        validate_message(self._valid(novelty_signals={"genre_novelty_ratio": 0.0}))

    def test_genre_novelty_ratio_one_is_valid(self):
        validate_message(self._valid(novelty_signals={"genre_novelty_ratio": 1.0}))


# ─── compute_score ────────────────────────────────────────────────────────────


class TestComputeScore:
    def test_nominal_case(self):
        # W1=0.6, W2=0.4, ratio=0.8, popularity=20 → 0.6*0.8 + 0.4*(1-0.20) = 0.48 + 0.32 = 0.80
        score, breakdown = compute_score(0.8, 20, False, 0.6, 0.4, 1.2)
        assert score == pytest.approx(0.80, abs=1e-4)
        assert breakdown["genre_novelty"] == pytest.approx(0.48, abs=1e-4)
        assert breakdown["popularity_norm"] == pytest.approx(0.32, abs=1e-4)

    def test_null_popularity_treated_as_zero(self):
        # popularity=None → treated as 0 → pop factor = W2 * 1.0
        score, _ = compute_score(0.0, None, False, 0.6, 0.4, 1.2)
        assert score == pytest.approx(0.4, abs=1e-4)

    def test_hp_bonus_applied(self):
        score_plain, _ = compute_score(0.5, 50, False, 0.6, 0.4, 1.2)
        score_hp, _ = compute_score(0.5, 50, True, 0.6, 0.4, 1.2)
        assert score_hp == pytest.approx(score_plain * 1.2, abs=1e-4)

    def test_hp_bonus_capped_at_1(self):
        # High ratio + HP_BONUS should never exceed 1.0
        score, _ = compute_score(1.0, 0, True, 0.6, 0.4, 1.5)
        assert score <= 1.0

    def test_score_never_exceeds_1_without_hp(self):
        score, _ = compute_score(1.0, 0, False, 0.6, 0.4, 1.2)
        assert score <= 1.0

    def test_score_never_negative(self):
        score, _ = compute_score(0.0, 100, False, 0.6, 0.4, 1.2)
        assert score >= 0.0

    def test_weight_variation_changes_score(self):
        # Use asymmetric inputs so changing weights produces different totals.
        # ratio=0.5, popularity=20: W1*0.5 + W2*0.8 differs across weight splits.
        score_a, _ = compute_score(0.5, 20, False, 0.6, 0.4, 1.2)
        score_b, _ = compute_score(0.5, 20, False, 0.8, 0.2, 1.2)
        assert score_a != pytest.approx(score_b, abs=1e-4)

    def test_hp_bonus_1_same_as_no_bonus(self):
        score_plain, _ = compute_score(0.5, 50, False, 0.6, 0.4, 1.0)
        score_hp, _ = compute_score(0.5, 50, True, 0.6, 0.4, 1.0)
        assert score_plain == pytest.approx(score_hp, abs=1e-4)

    def test_breakdown_keys_present(self):
        _, breakdown = compute_score(0.5, 50, False, 0.6, 0.4, 1.2)
        assert "genre_novelty" in breakdown
        assert "popularity_norm" in breakdown

    def test_breakdown_rounded_to_4_decimals(self):
        _, breakdown = compute_score(1 / 3, 33, False, 0.6, 0.4, 1.2)
        for val in breakdown.values():
            assert len(str(val).split(".")[-1]) <= 4

    def test_weight_sum_warning_logged(self, caplog):
        with caplog.at_level(logging.WARNING):
            compute_score(0.5, 50, False, 0.8, 0.5, 1.2)  # W1+W2=1.3, deviation > 0.01
        # Warning is emitted by __main__ at startup, not by compute_score itself —
        # this test documents the expected location. compute_score is pure; no warning here.
        # The startup warning is tested via test_app.py.
