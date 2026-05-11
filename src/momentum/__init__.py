"""NSE Momentum Scanner - Deterministic rule-based momentum scanning pipeline."""

from src.momentum.data_provider import DataProvider
from src.momentum.providers.mock_provider import MockDataProvider
from src.momentum.stage1_trend_filter import Stage1TrendFilter
from src.momentum.stage2_relative_strength import Stage2RelativeStrength
from src.momentum.stage3_entry_trigger import EntryTriggerResult, Stage3EntryTrigger

__all__ = [
    "DataProvider",
    "MockDataProvider",
    "Stage1TrendFilter",
    "Stage2RelativeStrength",
    "Stage3EntryTrigger",
    "EntryTriggerResult",
]

# Models will be exported once models.py is created (task 1.1)
try:
    from src.momentum.models import (
        SetupType,
        MomentumSignal,
        ScannerConfig,
        ScanCycleResult,
        AlertState,
        EODReport,
    )
    __all__.extend([
        "SetupType",
        "MomentumSignal",
        "ScannerConfig",
        "ScanCycleResult",
        "AlertState",
        "EODReport",
    ])
except ImportError:
    pass
