"""Data models for the NSE Momentum Scanner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class SetupType(Enum):
    """Classification of detected momentum pattern."""

    PULLBACK_CONTINUATION = "PULLBACK_CONTINUATION"
    COMPRESSION_BREAKOUT = "COMPRESSION_BREAKOUT"


@dataclass
class MomentumSignal:
    """Core output of the scanner pipeline."""

    symbol: str
    setup_type: SetupType
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    relative_volume: float  # current_vol / SMA(vol, 30)
    relative_strength: float  # weighted composite RS score
    sector_strength: float  # sector outperformance vs NIFTY
    trend_quality_score: float  # 0-100, from Stage 1
    rank_score: float  # 0-100, final weighted composite
    breakout_strength: float  # 0-100, from Stage 3
    distance_from_breakout: float  # inverse score, closer = higher
    timeframe: str  # "15m"
    timestamp: datetime  # IST
    risk_pct: float  # (entry - stop_loss) / entry * 100
    trailing_stop: float  # EMA(20) on 15m


# --- Sub-config dataclasses for ScannerConfig (ARCH-002) ---


@dataclass
class EMAConfig:
    """EMA-related configuration parameters."""

    fast: int = 20
    medium: int = 50
    slow: int = 200
    slope_lookback: int = 5


@dataclass
class ATRConfig:
    """ATR-related configuration parameters."""

    period: int = 14
    sl_multiplier: float = 1.2


@dataclass
class VolumeConfig:
    """Volume-related configuration parameters."""

    ma_period: int = 30
    expansion_threshold: float = 1.5


@dataclass
class RSWeights:
    """Relative Strength window weights."""

    intraday: float = 0.5
    one_day: float = 0.3
    five_day: float = 0.2


@dataclass
class RankingWeights:
    """Final ranking component weights."""

    relative_volume: float = 0.35
    breakout_strength: float = 0.25
    trend_quality: float = 0.20
    distance: float = 0.10
    sector: float = 0.10


@dataclass
class ScannerConfig:
    """All configurable parameters for the momentum scanner.

    While this dataclass retains flat field access for backward compatibility,
    the fields are logically grouped into sub-configs (EMAConfig, ATRConfig, etc.)
    for clarity. The flat fields are the canonical source used by all pipeline stages.
    """

    # EMA periods
    ema_fast: int = 20
    ema_medium: int = 50
    ema_slow: int = 200
    ema_slope_lookback: int = 5

    # ATR
    atr_period: int = 14
    atr_sl_multiplier: float = 1.2

    # Volume
    volume_ma_period: int = 30
    volume_expansion_threshold: float = 1.5

    # Relative Strength weights
    rs_intraday_weight: float = 0.5
    rs_1day_weight: float = 0.3
    rs_5day_weight: float = 0.2

    # Ranking weights
    rank_relative_volume_weight: float = 0.35
    rank_breakout_strength_weight: float = 0.25
    rank_trend_quality_weight: float = 0.20
    rank_distance_weight: float = 0.10
    rank_sector_weight: float = 0.10

    # Scan timing
    scan_interval_seconds: int = 120
    market_open: str = "09:15"
    market_close: str = "15:30"
    pre_market_time: str = "09:00"

    # Alert throttling
    cooldown_period_seconds: int = 1800  # 30 min default
    max_alerts_per_day: int = 20

    # Filters
    min_liquidity_value: float = 10_000_000  # 1 Cr daily traded value
    min_daily_volume: int = 100_000
    max_gap_pct: float = 5.0
    min_breakout_strength: float = 40.0
    breadth_decline_ratio: float = 1.5

    # Sector boost
    sector_boost_pct: float = 5.0

    # Performance
    max_scan_duration_seconds: int = 60
    warn_scan_duration_seconds: int = 90
    batch_size: int = 50

    # --- Convenience sub-config accessors ---

    @property
    def ema(self) -> EMAConfig:
        """Get EMA configuration as a sub-config object."""
        return EMAConfig(
            fast=self.ema_fast,
            medium=self.ema_medium,
            slow=self.ema_slow,
            slope_lookback=self.ema_slope_lookback,
        )

    @property
    def atr(self) -> ATRConfig:
        """Get ATR configuration as a sub-config object."""
        return ATRConfig(
            period=self.atr_period,
            sl_multiplier=self.atr_sl_multiplier,
        )

    @property
    def volume(self) -> VolumeConfig:
        """Get volume configuration as a sub-config object."""
        return VolumeConfig(
            ma_period=self.volume_ma_period,
            expansion_threshold=self.volume_expansion_threshold,
        )

    @property
    def rs_weights(self) -> RSWeights:
        """Get RS weights as a sub-config object."""
        return RSWeights(
            intraday=self.rs_intraday_weight,
            one_day=self.rs_1day_weight,
            five_day=self.rs_5day_weight,
        )

    @property
    def ranking_weights(self) -> RankingWeights:
        """Get ranking weights as a sub-config object."""
        return RankingWeights(
            relative_volume=self.rank_relative_volume_weight,
            breakout_strength=self.rank_breakout_strength_weight,
            trend_quality=self.rank_trend_quality_weight,
            distance=self.rank_distance_weight,
            sector=self.rank_sector_weight,
        )


@dataclass
class ScanCycleResult:
    """Result of one complete scan cycle."""

    timestamp: datetime
    duration_seconds: float
    stage1_passed: int
    stage2_ranked: int
    stage3_triggered: int
    signals_generated: List[MomentumSignal] = field(default_factory=list)
    signals_suppressed: int = 0  # dedup/cooldown
    market_breadth_healthy: bool = True
    rejected_reasons: Dict[str, int] = field(default_factory=dict)  # reason -> count


@dataclass
class AlertState:
    """Per-stock alert tracking state."""

    symbol: str
    last_alert_time: datetime
    last_setup_type: SetupType
    last_rank_score: float
    alert_count_today: int = 0


@dataclass
class EODReport:
    """End-of-day summary report."""

    date: datetime
    total_scans: int
    total_signals: int
    top_performers: List[MomentumSignal] = field(default_factory=list)
    setup_breakdown: Dict[str, int] = field(default_factory=dict)  # setup_type -> count
    sector_breakdown: Dict[str, int] = field(default_factory=dict)  # sector -> signal count
    avg_rank_score: float = 0.0
    market_breadth_suppressed_count: int = 0
