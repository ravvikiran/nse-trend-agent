"""Configuration manager for the NSE Momentum Scanner."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from src.momentum.models import ScannerConfig

logger = logging.getLogger(__name__)

# Valid ranges for configuration parameters
_VALID_RANGES: Dict[str, tuple] = {
    "ema_fast": (5, 50),
    "ema_medium": (20, 100),
    "ema_slow": (100, 500),
    "ema_slope_lookback": (2, 20),
    "atr_period": (5, 30),
    "atr_sl_multiplier": (0.5, 3.0),
    "volume_ma_period": (10, 100),
    "volume_expansion_threshold": (1.0, 5.0),
    "rs_intraday_weight": (0.0, 1.0),
    "rs_1day_weight": (0.0, 1.0),
    "rs_5day_weight": (0.0, 1.0),
    "rank_relative_volume_weight": (0.0, 1.0),
    "rank_breakout_strength_weight": (0.0, 1.0),
    "rank_trend_quality_weight": (0.0, 1.0),
    "rank_distance_weight": (0.0, 1.0),
    "rank_sector_weight": (0.0, 1.0),
    "scan_interval_seconds": (30, 600),
    "cooldown_period_seconds": (60, 7200),
    "max_alerts_per_day": (1, 100),
    "min_liquidity_value": (0, 1_000_000_000),
    "min_daily_volume": (0, 10_000_000),
    "max_gap_pct": (1.0, 20.0),
    "min_breakout_strength": (0.0, 100.0),
    "breadth_decline_ratio": (1.0, 5.0),
    "sector_boost_pct": (0.0, 20.0),
    "max_scan_duration_seconds": (10, 300),
    "warn_scan_duration_seconds": (30, 600),
    "batch_size": (10, 200),
}


class ConfigManager:
    """Loads and validates scanner configuration from JSON file."""

    DEFAULT_CONFIG_PATH = "config/momentum_scanner.json"

    def __init__(self, config_path: Optional[str] = None):
        self._config_path = config_path or self.DEFAULT_CONFIG_PATH

    def load(self, path: Optional[str] = None) -> ScannerConfig:
        """Load config from JSON file, validate ranges, apply defaults for missing values.

        Args:
            path: Optional override path to config file. Uses instance path if not provided.

        Returns:
            ScannerConfig with validated values and defaults applied.
        """
        config_path = path or self._config_path
        raw_config = self._read_config_file(config_path)

        if raw_config is None:
            logger.warning(
                "Configuration file '%s' is missing or unreadable. Using defaults.",
                config_path,
            )
            return ScannerConfig()

        return self._build_config(raw_config)

    def _read_config_file(self, path: str) -> Optional[Dict[str, Any]]:
        """Read and parse JSON config file.

        Returns:
            Parsed dict or None if file is missing/unreadable.
        """
        config_file = Path(path)
        if not config_file.exists():
            return None

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read config file '%s': %s", path, e)
            return None

    def _build_config(self, raw: Dict[str, Any]) -> ScannerConfig:
        """Build ScannerConfig from raw dict, validating each field."""
        defaults = ScannerConfig()
        validated: Dict[str, Any] = {}

        for field_name in vars(defaults):
            if field_name in raw:
                value = raw[field_name]
                validated_value = self._validate_field(field_name, value, getattr(defaults, field_name))
                validated[field_name] = validated_value
            # If field not in raw, it will use the dataclass default

        return ScannerConfig(**validated)

    def _validate_field(self, name: str, value: Any, default: Any) -> Any:
        """Validate a single config field against its valid range.

        Returns the value if valid, or the default with a warning if out of range.
        """
        # Type check
        expected_type = type(default)
        if expected_type == int and isinstance(value, float) and value == int(value):
            value = int(value)
        elif expected_type == float and isinstance(value, int):
            value = float(value)

        if not isinstance(value, expected_type):
            logger.warning(
                "Config '%s': expected %s, got %s. Using default: %s",
                name,
                expected_type.__name__,
                type(value).__name__,
                default,
            )
            return default

        # Range check for numeric fields
        if name in _VALID_RANGES:
            min_val, max_val = _VALID_RANGES[name]
            if value < min_val or value > max_val:
                logger.warning(
                    "Config '%s': value %s out of range [%s, %s]. Using default: %s",
                    name,
                    value,
                    min_val,
                    max_val,
                    default,
                )
                return default

        return value
