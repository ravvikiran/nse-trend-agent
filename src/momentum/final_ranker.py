"""Final Ranker: Applies weighted scoring formula and selects top 5 stocks.

Normalizes each ranking component to 0-100, applies configurable weights,
and returns the top min(N, 5) stocks sorted by final score descending.

Ranking formula:
    rank_score = 0.35 × RV_norm + 0.25 × BS_norm + 0.20 × TQ_norm
                 + 0.10 × Dist_norm + 0.10 × Sector_norm

Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
"""

import logging
from dataclasses import dataclass
from typing import List

from src.momentum.models import ScannerConfig

logger = logging.getLogger(__name__)

# Maximum relative volume used for normalization (RV of 3.0 maps to score 100)
_RV_NORMALIZATION_CAP = 3.0

# Maximum distance percentage used for inverse scoring normalization.
# Distances beyond this are scored as 0.
_DISTANCE_MAX_PCT = 10.0


@dataclass
class CandidateSignal:
    """Input signal for the FinalRanker.

    Each candidate comes from Stage 3 with associated scores from earlier stages.
    """

    symbol: str
    relative_volume: float  # current_vol / SMA(vol, 30)
    breakout_strength: float  # 0-100 from Stage 3
    trend_quality_score: float  # 0-100 from Stage 1
    distance_from_breakout: float  # percentage distance from entry price (0 = at breakout)
    sector_boost: float  # 0 or sector_boost_pct (e.g., 5.0)
    # Pass-through fields for the final output
    setup_type: str = ""
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target_1: float = 0.0
    target_2: float = 0.0
    relative_strength: float = 0.0
    timeframe: str = "15m"


@dataclass
class RankedSignal:
    """Output of the FinalRanker — a candidate signal with its computed rank score."""

    symbol: str
    rank_score: float  # 0-100 final weighted composite
    relative_volume: float
    breakout_strength: float
    trend_quality_score: float
    distance_from_breakout: float
    sector_boost: float
    # Normalized component scores (for transparency/debugging)
    rv_normalized: float
    bs_normalized: float
    tq_normalized: float
    dist_normalized: float
    sector_normalized: float
    # Pass-through fields
    setup_type: str = ""
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target_1: float = 0.0
    target_2: float = 0.0
    relative_strength: float = 0.0
    timeframe: str = "15m"


class FinalRanker:
    """Applies weighted scoring formula and selects top 5 stocks.

    Each component is normalized to 0-100 before applying weights:
      - relative_volume: linear scale where RV=3.0 maps to 100, capped at 100
      - breakout_strength: already 0-100, used as-is
      - trend_quality_score: already 0-100, used as-is
      - distance_from_breakout: inverse scoring — closer to breakout = higher score
      - sector_boost: 0 maps to 0, sector_boost_pct (5.0) maps to 100

    Final score = weighted sum of all normalized components.
    Output is the top min(N, 5) signals sorted by final score descending.
    """

    # Maximum number of stocks to return
    MAX_OUTPUT_SIZE = 5

    def __init__(self, config: ScannerConfig | None = None):
        """Initialize FinalRanker with scanner configuration.

        Args:
            config: Scanner configuration containing ranking weights and
                    sector_boost_pct. Uses defaults if None.
        """
        self.config = config or ScannerConfig()
        self.weight_rv = self.config.rank_relative_volume_weight
        self.weight_bs = self.config.rank_breakout_strength_weight
        self.weight_tq = self.config.rank_trend_quality_weight
        self.weight_dist = self.config.rank_distance_weight
        self.weight_sector = self.config.rank_sector_weight
        self.sector_boost_pct = self.config.sector_boost_pct

    def rank(self, candidates: List[CandidateSignal]) -> List[RankedSignal]:
        """Normalize components, apply weights, and return top min(N, 5) stocks.

        Args:
            candidates: List of candidate signals from Stage 3 with associated
                        scores from earlier pipeline stages.

        Returns:
            List of RankedSignal sorted by rank_score descending,
            containing at most min(len(candidates), 5) items.
        """
        if not candidates:
            return []

        ranked: List[RankedSignal] = []

        for candidate in candidates:
            # Normalize each component to 0-100
            rv_norm = self._normalize_relative_volume(candidate.relative_volume)
            bs_norm = self._normalize_breakout_strength(candidate.breakout_strength)
            tq_norm = self._normalize_trend_quality(candidate.trend_quality_score)
            dist_norm = self._normalize_distance(candidate.distance_from_breakout)
            sector_norm = self._normalize_sector_boost(candidate.sector_boost)

            # Calculate weighted composite score
            rank_score = (
                self.weight_rv * rv_norm
                + self.weight_bs * bs_norm
                + self.weight_tq * tq_norm
                + self.weight_dist * dist_norm
                + self.weight_sector * sector_norm
            )

            ranked.append(
                RankedSignal(
                    symbol=candidate.symbol,
                    rank_score=rank_score,
                    relative_volume=candidate.relative_volume,
                    breakout_strength=candidate.breakout_strength,
                    trend_quality_score=candidate.trend_quality_score,
                    distance_from_breakout=candidate.distance_from_breakout,
                    sector_boost=candidate.sector_boost,
                    rv_normalized=rv_norm,
                    bs_normalized=bs_norm,
                    tq_normalized=tq_norm,
                    dist_normalized=dist_norm,
                    sector_normalized=sector_norm,
                    setup_type=candidate.setup_type,
                    entry_price=candidate.entry_price,
                    stop_loss=candidate.stop_loss,
                    target_1=candidate.target_1,
                    target_2=candidate.target_2,
                    relative_strength=candidate.relative_strength,
                    timeframe=candidate.timeframe,
                )
            )

        # Sort by rank_score descending
        ranked.sort(key=lambda s: s.rank_score, reverse=True)

        # Select top min(N, 5)
        top_n = min(len(ranked), self.MAX_OUTPUT_SIZE)
        result = ranked[:top_n]

        logger.info(
            "FinalRanker: %d candidates → top %d selected (scores: %.1f to %.1f)",
            len(candidates),
            top_n,
            result[0].rank_score if result else 0.0,
            result[-1].rank_score if result else 0.0,
        )

        return result

    def _normalize_relative_volume(self, rv: float) -> float:
        """Normalize relative volume to 0-100 scale.

        Linear scale where RV of 3.0 maps to 100. Values above 3.0 are capped at 100.
        Values below 0 are floored at 0.

        Args:
            rv: Raw relative volume (current_vol / SMA(vol, 30)).

        Returns:
            Normalized score in [0, 100].
        """
        if rv <= 0:
            return 0.0
        score = (rv / _RV_NORMALIZATION_CAP) * 100.0
        return min(100.0, score)

    def _normalize_breakout_strength(self, bs: float) -> float:
        """Normalize breakout strength to 0-100 scale.

        Breakout strength is already computed as 0-100 by Stage 3.
        Clamp to ensure bounds are respected.

        Args:
            bs: Breakout strength score from Stage 3.

        Returns:
            Clamped score in [0, 100].
        """
        return max(0.0, min(100.0, bs))

    def _normalize_trend_quality(self, tq: float) -> float:
        """Normalize trend quality score to 0-100 scale.

        Trend quality is already computed as 0-100 by Stage 1.
        Clamp to ensure bounds are respected.

        Args:
            tq: Trend quality score from Stage 1.

        Returns:
            Clamped score in [0, 100].
        """
        return max(0.0, min(100.0, tq))

    def _normalize_distance(self, distance_pct: float) -> float:
        """Normalize distance-from-breakout using inverse scoring.

        Closer to breakout = higher score:
          - distance_pct = 0 → score = 100 (at breakout level)
          - distance_pct = _DISTANCE_MAX_PCT (10%) → score = 0 (far extended)
          - Linear interpolation between these bounds

        Negative distances (price below entry) are treated as 0 distance
        (at breakout level) since the signal was just triggered.

        Args:
            distance_pct: Percentage distance from breakout/entry price.
                          0 means price is at entry, positive means extended above.

        Returns:
            Inverse score in [0, 100]. Closer = higher.
        """
        if distance_pct <= 0:
            return 100.0
        if distance_pct >= _DISTANCE_MAX_PCT:
            return 0.0
        # Linear inverse: score decreases as distance increases
        return (1.0 - distance_pct / _DISTANCE_MAX_PCT) * 100.0

    def _normalize_sector_boost(self, sector_boost: float) -> float:
        """Normalize sector boost to 0-100 scale.

        Maps the sector_boost value to 0-100 using sector_boost_pct as the
        maximum (100). If sector_boost_pct is 5.0, then:
          - sector_boost = 0 → score = 0
          - sector_boost = 5.0 → score = 100

        Args:
            sector_boost: Raw sector boost value (0 or sector_boost_pct).

        Returns:
            Normalized score in [0, 100].
        """
        if self.sector_boost_pct <= 0:
            return 0.0
        if sector_boost <= 0:
            return 0.0
        score = (sector_boost / self.sector_boost_pct) * 100.0
        return min(100.0, score)
