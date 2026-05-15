"""NSE Momentum Scanner - Deterministic rule-based momentum scanning pipeline."""

from src.momentum.alert_service import AlertService
from src.momentum.data_provider import DataProvider
from src.momentum.providers.mock_provider import MockDataProvider
from src.momentum.stage1_trend_filter import Stage1TrendFilter
from src.momentum.stage2_relative_strength import Stage2RelativeStrength
from src.momentum.stage3_entry_trigger import EntryTriggerResult, Stage3EntryTrigger

__all__ = [
    "AlertService",
    "DataProvider",
    "MockDataProvider",
    "Stage1TrendFilter",
    "Stage2RelativeStrength",
    "Stage3EntryTrigger",
    "EntryTriggerResult",
]

from src.momentum.models import (
    SetupType,
    MomentumSignal,
    ScannerConfig,
    ScanCycleResult,
    AlertState,
    EODReport,
    EMAConfig,
    ATRConfig,
    VolumeConfig,
    RSWeights,
    RankingWeights,
)

__all__.extend([
    "SetupType",
    "MomentumSignal",
    "ScannerConfig",
    "ScanCycleResult",
    "AlertState",
    "EODReport",
    "EMAConfig",
    "ATRConfig",
    "VolumeConfig",
    "RSWeights",
    "RankingWeights",
])
