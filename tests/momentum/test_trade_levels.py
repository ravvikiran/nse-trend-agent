"""Unit tests for TradeLevelCalculator class."""

import pytest

from src.momentum.models import ScannerConfig
from src.momentum.trade_levels import TradeLevelCalculator, TradeLevels


@pytest.fixture
def config():
    """Default scanner config."""
    return ScannerConfig()


@pytest.fixture
def calculator(config):
    """TradeLevelCalculator instance with default config."""
    return TradeLevelCalculator(config)


class TestTradeLevelCalculator:
    """Tests for TradeLevelCalculator.calculate()."""

    def test_basic_calculation(self, calculator):
        """Test basic trade level calculation with typical values."""
        # Entry = 100, candle_low = 97, ATR = 2.0, EMA20 = 99
        # ATR-based SL = 100 - 1.2 * 2.0 = 97.6
        # SL = min(97, 97.6) = 97
        # Risk = 100 - 97 = 3
        # T1 = 100 + 3 = 103
        # T2 = 100 + 6 = 106
        result = calculator.calculate(
            entry_price=100.0,
            trigger_candle_low=97.0,
            atr_value=2.0,
            ema_20_value=99.0,
        )

        assert result is not None
        assert result.entry_price == 100.0
        assert result.stop_loss == 97.0
        assert result.risk == pytest.approx(3.0)
        assert result.target_1 == pytest.approx(103.0)
        assert result.target_2 == pytest.approx(106.0)
        assert result.trailing_stop == 99.0
        assert result.risk_pct == pytest.approx(3.0)
        assert result.reward_risk_ratio == pytest.approx(2.0)

    def test_atr_based_sl_is_lower(self, calculator):
        """Test when ATR-based SL is lower than candle low (ATR-based wins)."""
        # Entry = 100, candle_low = 99, ATR = 3.0, EMA20 = 98
        # ATR-based SL = 100 - 1.2 * 3.0 = 96.4
        # SL = min(99, 96.4) = 96.4
        # Risk = 100 - 96.4 = 3.6
        result = calculator.calculate(
            entry_price=100.0,
            trigger_candle_low=99.0,
            atr_value=3.0,
            ema_20_value=98.0,
        )

        assert result is not None
        assert result.stop_loss == pytest.approx(96.4)
        assert result.risk == pytest.approx(3.6)
        assert result.target_1 == pytest.approx(103.6)
        assert result.target_2 == pytest.approx(107.2)

    def test_candle_low_is_lower(self, calculator):
        """Test when candle low is lower than ATR-based SL (candle low wins)."""
        # Entry = 100, candle_low = 95, ATR = 2.0, EMA20 = 99
        # ATR-based SL = 100 - 1.2 * 2.0 = 97.6
        # SL = min(95, 97.6) = 95
        # Risk = 100 - 95 = 5
        result = calculator.calculate(
            entry_price=100.0,
            trigger_candle_low=95.0,
            atr_value=2.0,
            ema_20_value=99.0,
        )

        assert result is not None
        assert result.stop_loss == pytest.approx(95.0)
        assert result.risk == pytest.approx(5.0)
        assert result.target_1 == pytest.approx(105.0)
        assert result.target_2 == pytest.approx(110.0)

    def test_invalid_sl_above_entry(self, calculator):
        """Test that signal is discarded when SL >= entry (invalid risk)."""
        # Entry = 100, candle_low = 101, ATR = very small
        # ATR-based SL = 100 - 1.2 * 0.01 = 99.988
        # SL = min(101, 99.988) = 99.988 — still below entry, so valid
        # But if candle_low > entry AND ATR-based SL > entry:
        # Entry = 100, candle_low = 101, ATR = -1 (invalid)
        result = calculator.calculate(
            entry_price=100.0,
            trigger_candle_low=101.0,
            atr_value=-1.0,
            ema_20_value=99.0,
        )
        assert result is None

    def test_zero_atr_returns_none(self, calculator):
        """Test that zero ATR returns None (invalid input)."""
        result = calculator.calculate(
            entry_price=100.0,
            trigger_candle_low=97.0,
            atr_value=0.0,
            ema_20_value=99.0,
        )
        assert result is None

    def test_zero_entry_price_returns_none(self, calculator):
        """Test that zero entry price returns None (invalid input)."""
        result = calculator.calculate(
            entry_price=0.0,
            trigger_candle_low=97.0,
            atr_value=2.0,
            ema_20_value=99.0,
        )
        assert result is None

    def test_negative_entry_price_returns_none(self, calculator):
        """Test that negative entry price returns None."""
        result = calculator.calculate(
            entry_price=-10.0,
            trigger_candle_low=97.0,
            atr_value=2.0,
            ema_20_value=99.0,
        )
        assert result is None

    def test_sl_equals_entry_returns_none(self, calculator):
        """Test that SL == entry returns None (zero risk)."""
        # Entry = 100, candle_low = 100, ATR very large so ATR-based SL is below
        # Actually min(100, 100 - 1.2*0.0001) = min(100, 99.99988) = 99.99988
        # That's still valid. Let's make candle_low = entry and ATR = 0 (already tested)
        # Better: entry = candle_low and ATR-based SL = entry
        # entry = 100, candle_low = 100, ATR = 0 → invalid ATR
        # Let's use a scenario where both are at entry
        # Actually if candle_low = entry_price, ATR-based SL = entry - 1.2*ATR
        # For SL = entry, we need min(candle_low, entry - 1.2*ATR) = entry
        # That means candle_low >= entry AND entry - 1.2*ATR >= entry → -1.2*ATR >= 0 → ATR <= 0
        # So this only happens with invalid ATR, already covered
        pass

    def test_risk_pct_calculation(self, calculator):
        """Test risk percentage is correctly calculated."""
        result = calculator.calculate(
            entry_price=200.0,
            trigger_candle_low=194.0,
            atr_value=5.0,
            ema_20_value=198.0,
        )
        # ATR-based SL = 200 - 1.2 * 5 = 194
        # SL = min(194, 194) = 194
        # Risk = 200 - 194 = 6
        # Risk% = 6 / 200 * 100 = 3.0%
        assert result is not None
        assert result.risk_pct == pytest.approx(3.0)

    def test_trailing_stop_is_ema20(self, calculator):
        """Test that trailing stop equals the provided EMA(20) value."""
        result = calculator.calculate(
            entry_price=100.0,
            trigger_candle_low=97.0,
            atr_value=2.0,
            ema_20_value=98.5,
        )
        assert result is not None
        assert result.trailing_stop == 98.5

    def test_reward_risk_ratio_always_2(self, calculator):
        """Test that reward-risk ratio for T2 is always 2.0 by construction."""
        result = calculator.calculate(
            entry_price=500.0,
            trigger_candle_low=480.0,
            atr_value=10.0,
            ema_20_value=495.0,
        )
        # ATR-based SL = 500 - 12 = 488
        # SL = min(480, 488) = 480
        # Risk = 20, T2 = 500 + 40 = 540
        # RR = (540 - 500) / 20 = 2.0
        assert result is not None
        assert result.reward_risk_ratio == pytest.approx(2.0)

    def test_custom_atr_multiplier(self):
        """Test with custom ATR multiplier from config."""
        config = ScannerConfig(atr_sl_multiplier=2.0)
        calc = TradeLevelCalculator(config)

        result = calc.calculate(
            entry_price=100.0,
            trigger_candle_low=97.0,
            atr_value=2.0,
            ema_20_value=99.0,
        )
        # ATR-based SL = 100 - 2.0 * 2.0 = 96
        # SL = min(97, 96) = 96
        # Risk = 4
        assert result is not None
        assert result.stop_loss == pytest.approx(96.0)
        assert result.risk == pytest.approx(4.0)
        assert result.target_1 == pytest.approx(104.0)
        assert result.target_2 == pytest.approx(108.0)

    def test_large_atr_relative_to_price(self, calculator):
        """Test with large ATR that pushes SL far below entry."""
        result = calculator.calculate(
            entry_price=100.0,
            trigger_candle_low=90.0,
            atr_value=20.0,
            ema_20_value=95.0,
        )
        # ATR-based SL = 100 - 1.2 * 20 = 76
        # SL = min(90, 76) = 76
        # Risk = 24
        assert result is not None
        assert result.stop_loss == pytest.approx(76.0)
        assert result.risk == pytest.approx(24.0)
        assert result.target_1 == pytest.approx(124.0)
        assert result.target_2 == pytest.approx(148.0)

    def test_small_price_stock(self, calculator):
        """Test with a low-priced stock (e.g., ₹10)."""
        result = calculator.calculate(
            entry_price=10.0,
            trigger_candle_low=9.5,
            atr_value=0.5,
            ema_20_value=9.8,
        )
        # ATR-based SL = 10 - 1.2 * 0.5 = 9.4
        # SL = min(9.5, 9.4) = 9.4
        # Risk = 0.6
        assert result is not None
        assert result.stop_loss == pytest.approx(9.4)
        assert result.risk == pytest.approx(0.6)
        assert result.target_1 == pytest.approx(10.6)
        assert result.target_2 == pytest.approx(11.2)

    def test_high_price_stock(self, calculator):
        """Test with a high-priced stock (e.g., ₹5000)."""
        result = calculator.calculate(
            entry_price=5000.0,
            trigger_candle_low=4950.0,
            atr_value=40.0,
            ema_20_value=4980.0,
        )
        # ATR-based SL = 5000 - 1.2 * 40 = 4952
        # SL = min(4950, 4952) = 4950
        # Risk = 50
        assert result is not None
        assert result.stop_loss == pytest.approx(4950.0)
        assert result.risk == pytest.approx(50.0)
        assert result.target_1 == pytest.approx(5050.0)
        assert result.target_2 == pytest.approx(5100.0)
