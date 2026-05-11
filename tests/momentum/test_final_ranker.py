"""Unit tests for FinalRanker class."""

import pytest

from src.momentum.final_ranker import CandidateSignal, FinalRanker, RankedSignal
from src.momentum.models import ScannerConfig


@pytest.fixture
def config():
    """Default scanner config."""
    return ScannerConfig()


@pytest.fixture
def ranker(config):
    """FinalRanker instance with default config."""
    return FinalRanker(config)


def _make_candidate(
    symbol: str = "RELIANCE",
    relative_volume: float = 2.0,
    breakout_strength: float = 70.0,
    trend_quality_score: float = 80.0,
    distance_from_breakout: float = 1.0,
    sector_boost: float = 5.0,
) -> CandidateSignal:
    """Helper to create a CandidateSignal with sensible defaults."""
    return CandidateSignal(
        symbol=symbol,
        relative_volume=relative_volume,
        breakout_strength=breakout_strength,
        trend_quality_score=trend_quality_score,
        distance_from_breakout=distance_from_breakout,
        sector_boost=sector_boost,
        setup_type="PULLBACK_CONTINUATION",
        entry_price=100.0,
        stop_loss=95.0,
        target_1=105.0,
        target_2=110.0,
        relative_strength=5.0,
        timeframe="15m",
    )


class TestNormalizeRelativeVolume:
    """Tests for _normalize_relative_volume()."""

    def test_rv_zero_returns_zero(self, ranker):
        """RV of 0 should normalize to 0."""
        assert ranker._normalize_relative_volume(0.0) == 0.0

    def test_rv_negative_returns_zero(self, ranker):
        """Negative RV should normalize to 0."""
        assert ranker._normalize_relative_volume(-1.0) == 0.0

    def test_rv_3_returns_100(self, ranker):
        """RV of 3.0 should normalize to 100."""
        assert ranker._normalize_relative_volume(3.0) == pytest.approx(100.0)

    def test_rv_1_5_returns_50(self, ranker):
        """RV of 1.5 should normalize to 50."""
        assert ranker._normalize_relative_volume(1.5) == pytest.approx(50.0)

    def test_rv_above_3_capped_at_100(self, ranker):
        """RV above 3.0 should be capped at 100."""
        assert ranker._normalize_relative_volume(5.0) == 100.0

    def test_rv_linear_scaling(self, ranker):
        """RV normalization should be linear."""
        score_1 = ranker._normalize_relative_volume(1.0)
        score_2 = ranker._normalize_relative_volume(2.0)
        assert score_2 == pytest.approx(score_1 * 2.0)


class TestNormalizeBreakoutStrength:
    """Tests for _normalize_breakout_strength()."""

    def test_already_in_range(self, ranker):
        """Values already in [0, 100] should pass through."""
        assert ranker._normalize_breakout_strength(75.0) == 75.0

    def test_clamps_above_100(self, ranker):
        """Values above 100 should be clamped to 100."""
        assert ranker._normalize_breakout_strength(120.0) == 100.0

    def test_clamps_below_0(self, ranker):
        """Values below 0 should be clamped to 0."""
        assert ranker._normalize_breakout_strength(-5.0) == 0.0


class TestNormalizeTrendQuality:
    """Tests for _normalize_trend_quality()."""

    def test_already_in_range(self, ranker):
        """Values already in [0, 100] should pass through."""
        assert ranker._normalize_trend_quality(60.0) == 60.0

    def test_clamps_above_100(self, ranker):
        """Values above 100 should be clamped to 100."""
        assert ranker._normalize_trend_quality(150.0) == 100.0

    def test_clamps_below_0(self, ranker):
        """Values below 0 should be clamped to 0."""
        assert ranker._normalize_trend_quality(-10.0) == 0.0


class TestNormalizeDistance:
    """Tests for _normalize_distance() — inverse scoring."""

    def test_zero_distance_returns_100(self, ranker):
        """Distance of 0 (at breakout) should score 100."""
        assert ranker._normalize_distance(0.0) == 100.0

    def test_max_distance_returns_0(self, ranker):
        """Distance at max (10%) should score 0."""
        assert ranker._normalize_distance(10.0) == 0.0

    def test_beyond_max_distance_returns_0(self, ranker):
        """Distance beyond max should score 0."""
        assert ranker._normalize_distance(15.0) == 0.0

    def test_negative_distance_returns_100(self, ranker):
        """Negative distance (below entry) should score 100."""
        assert ranker._normalize_distance(-2.0) == 100.0

    def test_5_pct_distance_returns_50(self, ranker):
        """5% distance (half of max) should score 50."""
        assert ranker._normalize_distance(5.0) == pytest.approx(50.0)

    def test_inverse_relationship(self, ranker):
        """Closer distance should always score higher."""
        score_close = ranker._normalize_distance(1.0)
        score_far = ranker._normalize_distance(5.0)
        assert score_close > score_far


class TestNormalizeSectorBoost:
    """Tests for _normalize_sector_boost()."""

    def test_zero_boost_returns_0(self, ranker):
        """No sector boost should normalize to 0."""
        assert ranker._normalize_sector_boost(0.0) == 0.0

    def test_full_boost_returns_100(self, ranker):
        """Full sector_boost_pct (5.0) should normalize to 100."""
        assert ranker._normalize_sector_boost(5.0) == pytest.approx(100.0)

    def test_negative_boost_returns_0(self, ranker):
        """Negative boost should normalize to 0."""
        assert ranker._normalize_sector_boost(-1.0) == 0.0

    def test_above_max_capped_at_100(self, ranker):
        """Boost above sector_boost_pct should be capped at 100."""
        assert ranker._normalize_sector_boost(10.0) == 100.0

    def test_zero_sector_boost_pct_config(self):
        """If sector_boost_pct is 0 in config, always return 0."""
        config = ScannerConfig(sector_boost_pct=0.0)
        ranker = FinalRanker(config)
        assert ranker._normalize_sector_boost(5.0) == 0.0


class TestRank:
    """Tests for rank() method."""

    def test_empty_candidates_returns_empty(self, ranker):
        """Empty input should return empty output."""
        assert ranker.rank([]) == []

    def test_single_candidate_returns_one(self, ranker):
        """Single candidate should return one ranked signal."""
        candidates = [_make_candidate("RELIANCE")]
        result = ranker.rank(candidates)
        assert len(result) == 1
        assert result[0].symbol == "RELIANCE"

    def test_returns_max_5(self, ranker):
        """Should return at most 5 signals even with more candidates."""
        candidates = [
            _make_candidate(f"STOCK{i}", relative_volume=float(i))
            for i in range(1, 10)
        ]
        result = ranker.rank(candidates)
        assert len(result) == 5

    def test_returns_fewer_than_5_when_less_candidates(self, ranker):
        """Should return all candidates when fewer than 5."""
        candidates = [_make_candidate(f"STOCK{i}") for i in range(3)]
        result = ranker.rank(candidates)
        assert len(result) == 3

    def test_sorted_by_rank_score_descending(self, ranker):
        """Output should be sorted by rank_score descending."""
        candidates = [
            _make_candidate("LOW", relative_volume=0.5, breakout_strength=20.0),
            _make_candidate("HIGH", relative_volume=3.0, breakout_strength=95.0),
            _make_candidate("MID", relative_volume=1.5, breakout_strength=60.0),
        ]
        result = ranker.rank(candidates)
        assert result[0].symbol == "HIGH"
        assert result[-1].symbol == "LOW"
        # Verify descending order
        for i in range(len(result) - 1):
            assert result[i].rank_score >= result[i + 1].rank_score

    def test_top_5_are_highest_scored(self, ranker):
        """Top 5 should be the 5 highest-scored candidates."""
        candidates = [
            _make_candidate(f"STOCK{i}", relative_volume=float(i) * 0.5)
            for i in range(1, 8)
        ]
        result = ranker.rank(candidates)
        # The top 5 should have the highest RV values (since other params are equal)
        result_symbols = {r.symbol for r in result}
        # Stocks 3-7 have RV 1.5 to 3.5, which are the highest
        for i in range(3, 8):
            assert f"STOCK{i}" in result_symbols

    def test_rank_score_formula(self, ranker):
        """Verify rank score matches the weighted formula."""
        candidate = CandidateSignal(
            symbol="TEST",
            relative_volume=1.5,  # norm: 50
            breakout_strength=80.0,  # norm: 80
            trend_quality_score=60.0,  # norm: 60
            distance_from_breakout=5.0,  # norm: 50
            sector_boost=5.0,  # norm: 100
        )
        result = ranker.rank([candidate])
        expected = 0.35 * 50.0 + 0.25 * 80.0 + 0.20 * 60.0 + 0.10 * 50.0 + 0.10 * 100.0
        assert result[0].rank_score == pytest.approx(expected)

    def test_rank_score_bounded_0_100(self, ranker):
        """Rank score should always be in [0, 100]."""
        # Maximum possible score
        max_candidate = _make_candidate(
            relative_volume=3.0,
            breakout_strength=100.0,
            trend_quality_score=100.0,
            distance_from_breakout=0.0,
            sector_boost=5.0,
        )
        # Minimum possible score
        min_candidate = _make_candidate(
            relative_volume=0.0,
            breakout_strength=0.0,
            trend_quality_score=0.0,
            distance_from_breakout=10.0,
            sector_boost=0.0,
        )
        results = ranker.rank([max_candidate, min_candidate])
        for r in results:
            assert 0.0 <= r.rank_score <= 100.0

    def test_higher_rv_ranks_higher_all_else_equal(self, ranker):
        """Higher relative volume should produce higher rank score."""
        low_rv = _make_candidate("LOW_RV", relative_volume=1.0)
        high_rv = _make_candidate("HIGH_RV", relative_volume=2.5)
        result = ranker.rank([low_rv, high_rv])
        assert result[0].symbol == "HIGH_RV"

    def test_closer_distance_ranks_higher_all_else_equal(self, ranker):
        """Closer to breakout should produce higher rank score."""
        far = _make_candidate("FAR", distance_from_breakout=8.0)
        close = _make_candidate("CLOSE", distance_from_breakout=1.0)
        result = ranker.rank([far, close])
        assert result[0].symbol == "CLOSE"

    def test_sector_boost_increases_score(self, ranker):
        """Stock with sector boost should rank higher than without."""
        no_boost = _make_candidate("NO_BOOST", sector_boost=0.0)
        with_boost = _make_candidate("WITH_BOOST", sector_boost=5.0)
        result = ranker.rank([no_boost, with_boost])
        assert result[0].symbol == "WITH_BOOST"

    def test_pass_through_fields_preserved(self, ranker):
        """Pass-through fields should be preserved in output."""
        candidate = CandidateSignal(
            symbol="INFY",
            relative_volume=2.0,
            breakout_strength=70.0,
            trend_quality_score=80.0,
            distance_from_breakout=1.0,
            sector_boost=5.0,
            setup_type="COMPRESSION_BREAKOUT",
            entry_price=1500.0,
            stop_loss=1450.0,
            target_1=1550.0,
            target_2=1600.0,
            relative_strength=3.5,
            timeframe="15m",
        )
        result = ranker.rank([candidate])
        assert result[0].setup_type == "COMPRESSION_BREAKOUT"
        assert result[0].entry_price == 1500.0
        assert result[0].stop_loss == 1450.0
        assert result[0].target_1 == 1550.0
        assert result[0].target_2 == 1600.0
        assert result[0].relative_strength == 3.5
        assert result[0].timeframe == "15m"

    def test_normalized_scores_stored(self, ranker):
        """Normalized component scores should be stored in output."""
        candidate = _make_candidate(
            relative_volume=1.5,  # norm: 50
            breakout_strength=80.0,  # norm: 80
            trend_quality_score=60.0,  # norm: 60
            distance_from_breakout=5.0,  # norm: 50
            sector_boost=5.0,  # norm: 100
        )
        result = ranker.rank([candidate])
        assert result[0].rv_normalized == pytest.approx(50.0)
        assert result[0].bs_normalized == pytest.approx(80.0)
        assert result[0].tq_normalized == pytest.approx(60.0)
        assert result[0].dist_normalized == pytest.approx(50.0)
        assert result[0].sector_normalized == pytest.approx(100.0)


class TestCustomWeights:
    """Tests with custom weight configurations."""

    def test_custom_weights_applied(self):
        """Custom weights should change ranking behavior."""
        # Config where sector weight dominates
        config = ScannerConfig(
            rank_relative_volume_weight=0.05,
            rank_breakout_strength_weight=0.05,
            rank_trend_quality_weight=0.05,
            rank_distance_weight=0.05,
            rank_sector_weight=0.80,
        )
        ranker = FinalRanker(config)

        # Stock with high sector boost but low everything else
        sector_stock = _make_candidate(
            "SECTOR",
            relative_volume=0.5,
            breakout_strength=20.0,
            trend_quality_score=20.0,
            distance_from_breakout=8.0,
            sector_boost=5.0,
        )
        # Stock with high everything but no sector boost
        other_stock = _make_candidate(
            "OTHER",
            relative_volume=3.0,
            breakout_strength=95.0,
            trend_quality_score=95.0,
            distance_from_breakout=0.0,
            sector_boost=0.0,
        )
        result = ranker.rank([sector_stock, other_stock])
        # With 80% weight on sector, the sector stock should win
        assert result[0].symbol == "SECTOR"
