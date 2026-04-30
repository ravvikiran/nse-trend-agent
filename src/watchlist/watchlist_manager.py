"""
Watchlist Manager Module

Manages user watchlist with technical analysis suggestions.
Stores watchlist items in JSON file and provides BUY/SELL/HOLD recommendations
based on technical indicators and market conditions.
"""

import os
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

DATA_DIR = 'data'
WATCHLIST_FILE = 'watchlist.json'


@dataclass
class WatchlistItem:
    """Watchlist item data structure."""
    symbol: str
    added_at: str
    notes: str = ""
    id: str = None

    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())[:8]


@dataclass
class AnalysisResult:
    """Technical analysis result for a stock."""
    symbol: str
    recommendation: str  # BUY, SELL, HOLD
    confidence: int  # 1-10
    current_price: float
    entry_zone: str
    stop_loss: float
    stop_loss_pct: float
    target1: float
    target1_pct: float
    target2: float
    target2_pct: float
    reasoning: str
    risk_assessment: str
    technical_signals: List[str]
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WatchlistManager:
    """
    Manages watchlist data and generates technical analysis suggestions.
    """

    def __init__(self, data_dir: str = DATA_DIR, data_fetcher=None, indicator_engine=None):
        """
        Initialize WatchlistManager.

        Args:
            data_dir: Directory to store watchlist data
            data_fetcher: DataFetcher instance for fetching stock data
            indicator_engine: IndicatorEngine instance for calculating indicators
        """
        self.data_dir = data_dir
        self.data_fetcher = data_fetcher
        self.indicator_engine = indicator_engine
        os.makedirs(data_dir, exist_ok=True)
        self.watchlist = self._load_watchlist()
        logger.info(f"WatchlistManager initialized. Items: {len(self.watchlist)}")

    def _load_watchlist(self) -> List[Dict[str, Any]]:
        """Load watchlist from JSON file."""
        filepath = os.path.join(self.data_dir, WATCHLIST_FILE)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    logger.info(f"Loaded {len(data)} items from watchlist")
                    return data
                else:
                    logger.warning("Invalid watchlist format, starting fresh")
                    return []
            except Exception as e:
                logger.error(f"Error loading watchlist: {e}")
                return []
        return []

    def _save_watchlist(self) -> None:
        """Save watchlist to JSON file."""
        filepath = os.path.join(self.data_dir, WATCHLIST_FILE)
        try:
            with open(filepath, 'w') as f:
                json.dump(self.watchlist, f, indent=2)
            logger.debug(f"Saved watchlist with {len(self.watchlist)} items")
        except Exception as e:
            logger.error(f"Error saving watchlist: {e}")

    def add_stock(self, symbol: str, notes: str = "") -> bool:
        """
        Add a stock to the watchlist.

        Args:
            symbol: Stock symbol (e.g., 'RELIANCE')
            notes: Optional notes about the stock

        Returns:
            True if added, False if already exists
        """
        symbol_clean = symbol.strip().upper()

        # Check if already exists
        for item in self.watchlist:
            if item['symbol'] == symbol_clean:
                logger.info(f"Stock {symbol_clean} already in watchlist")
                return False

        new_item = {
            'id': str(uuid.uuid4())[:8],
            'symbol': symbol_clean,
            'added_at': datetime.now().isoformat(),
            'notes': notes
        }

        self.watchlist.append(new_item)
        self._save_watchlist()
        logger.info(f"Added {symbol_clean} to watchlist")
        return True

    def add_multiple_stocks(self, symbols: List[str]) -> Dict[str, bool]:
        """
        Add multiple stocks to the watchlist.

        Returns:
            Dict mapping symbol to success status
        """
        results = {}
        for symbol in symbols:
            results[symbol] = self.add_stock(symbol)
        return results

    def remove_stock(self, symbol: str) -> bool:
        """
        Remove a stock from the watchlist.

        Args:
            symbol: Stock symbol to remove

        Returns:
            True if removed, False if not found
        """
        symbol_clean = symbol.strip().upper()
        initial_count = len(self.watchlist)
        self.watchlist = [item for item in self.watchlist if item['symbol'] != symbol_clean]

        if len(self.watchlist) < initial_count:
            self._save_watchlist()
            logger.info(f"Removed {symbol_clean} from watchlist")
            return True
        else:
            logger.info(f"Stock {symbol_clean} not found in watchlist")
            return False

    def get_watchlist(self) -> List[Dict[str, Any]]:
        """Get all watchlist items."""
        return self.watchlist.copy()

    def clear_watchlist(self) -> None:
        """Clear all items from watchlist."""
        self.watchlist = []
        self._save_watchlist()
        logger.info("Cleared watchlist")

    def analyze_stock(self, symbol: str) -> Optional[AnalysisResult]:
        """
        Analyze a single stock and generate recommendation.

        Uses technical indicators and rule-based scoring to provide
        BUY/SELL/HOLD suggestions with entry/exit levels.

        Args:
            symbol: Stock symbol to analyze

        Returns:
            AnalysisResult with recommendation and levels, or None on failure
        """
        if not self.data_fetcher or not self.indicator_engine:
            logger.error("DataFetcher or IndicatorEngine not provided")
            return None

        try:
            # Fetch stock data (200 days for EMA200)
            df = self.data_fetcher.fetch_stock_data(symbol, interval='1D', days=200)
            if df is None or df.empty:
                logger.warning(f"No data fetched for {symbol}")
                return None

            # Calculate indicators
            df_with_ind = self.indicator_engine.calculate_indicators(df)
            if df_with_ind.empty:
                logger.warning(f"Failed to calculate indicators for {symbol}")
                return None

            latest = self.indicator_engine.get_latest_indicators(df_with_ind)
            if not latest:
                logger.warning(f"No latest indicators for {symbol}")
                return None

            return self._generate_analysis(symbol, df_with_ind, latest)

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}", exc_info=True)
            return None

    def _generate_analysis(self, symbol: str, df: Any, indicators: Dict[str, Any]) -> AnalysisResult:
        """
        Generate analysis result from indicators using rule-based scoring.

        Args:
            symbol: Stock symbol
            df: DataFrame with OHLCV and indicators
            indicators: Dictionary of latest indicator values

        Returns:
            AnalysisResult with recommendation
        """
        close = indicators.get('close', 0)
        ema_20 = indicators.get('ema_20', 0)
        ema_50 = indicators.get('ema_50', 0)
        ema_100 = indicators.get('ema_100', 0)
        ema_200 = indicators.get('ema_200', 0)
        rsi = indicators.get('rsi', 50)
        volume = indicators.get('volume', 0)
        volume_ma = indicators.get('volume_ma', 0)
        atr = indicators.get('atr', 0)
        high_20 = indicators.get('high_20', 0)
        low_20 = indicators.get('low_20', 0)

        # Calculate volume ratio
        volume_ratio = volume / volume_ma if volume_ma and volume_ma > 0 else 1.0

        # Previous values for crossover detection
        prev_ema_20 = indicators.get('prev_ema_20', 0)
        prev_ema_50 = indicators.get('prev_ema_50', 0)

        # ============ SCORING SYSTEM (similar to TrendDetector) ============
        score = 0
        signals = []

        # 1. EMA Alignment (EMA20 > EMA50 > EMA100 > EMA200) - Strong uptrend
        if ema_20 > ema_50 > ema_100 > ema_200:
            score += 3
            signals.append("✅ Strong EMA alignment (20>50>100>200)")
        elif ema_20 > ema_50 > ema_100:
            score += 2
            signals.append("✅ Good EMA alignment (20>50>100)")
        elif ema_20 > ema_50:
            score += 1
            signals.append("✅ EMA20 above EMA50")

        # 2. Fresh Crossover (EMA20 just crossed above EMA50)
        if prev_ema_20 and prev_ema_50:
            if prev_ema_20 <= prev_ema_50 and ema_20 > ema_50:
                score += 2
                signals.append("🔄 Fresh bullish EMA crossover")

        # 3. Price Breakout (above 20-day high)
        if close >= high_20 * 0.99:  # Within 1% of high
            score += 2
            signals.append("📈 Near 20-day high (breakout)")

        # 4. Volume Spike (>= 1.5x average)
        if volume_ratio >= 1.5:
            score += 2
            signals.append(f"📊 Volume spike ({volume_ratio:.1f}x avg)")
        elif volume_ratio >= 1.2:
            score += 1
            signals.append(f"📊 Elevated volume ({volume_ratio:.1f}x avg)")

        # 5. RSI Analysis
        if 40 <= rsi <= 65:
            score += 1
            signals.append(f"🔄 RSI in optimal zone ({rsi:.1f})")
        elif rsi >= 70:
            score -= 2
            signals.append(f"⚠️ RSI overbought ({rsi:.1f})")
        elif rsi <= 30:
            score += 2
            signals.append(f"✅ RSI oversold ({rsi:.1f})")

        # 6. Price relative to EMAs
        if close > ema_20:
            score += 1
            signals.append("✅ Price above EMA20")
        if close > ema_50:
            score += 1
            signals.append("✅ Price above EMA50")
        if close < ema_20:
            score -= 1
            signals.append("❌ Price below EMA20")
        if close < ema_50:
            score -= 1
            signals.append("❌ Price below EMA50")

        # ============ DETERMINE RECOMMENDATION ============
        recommendation = "HOLD"
        confidence = 5
        reasoning = ""
        risk = "MEDIUM"

        # Strong buy signal
        if score >= 7:
            recommendation = "STRONG BUY"
            confidence = min(10, 7 + (score - 7))
            reasoning = "Multiple bullish factors aligned"
            risk = "LOW" if atr / close < 0.02 else "MEDIUM"
        elif score >= 5:
            recommendation = "BUY"
            confidence = min(9, 5 + (score - 5))
            reasoning = "Bullish technical setup"
            risk = "MEDIUM"
        elif score <= -2:
            recommendation = "STRONG SELL"
            confidence = min(10, abs(score))
            reasoning = "Multiple bearish factors"
            risk = "HIGH"
        elif score <= 0:
            recommendation = "SELL"
            confidence = min(8, abs(score))
            reasoning = "Bearish technical indicators"
            risk = "MEDIUM"
        else:
            recommendation = "HOLD"
            confidence = 5 + score if score > 0 else 5
            reasoning = "Mixed signals, wait for clearer trend"

        # Adjust confidence based on volume confirmation
        if volume_ratio < 0.8 and recommendation != "SELL":
            confidence = max(3, confidence - 2)
            reasoning += " (low volume confirmation)"

        # ============ CALCULATE ENTRY / SL / TARGETS ============
        # Use ATR for stop loss and targets
        risk_amount = atr * 2 if atr > 0 else close * 0.02

        if recommendation in ["BUY", "STRONG BUY"]:
            entry_min = max(close * 0.98, close - atr * 0.5)
            entry_max = min(close * 1.02, close + atr * 0.5)
            entry_zone = f"₹{entry_min:.2f} - ₹{entry_max:.2f}"
            stop_loss = max(entry_min - risk_amount, low_20 * 0.99)
            if stop_loss >= entry_min:
                stop_loss = entry_min - risk_amount

            target1 = close + risk_amount * 2
            target2 = close + risk_amount * 3

            sl_pct = ((close - stop_loss) / close) * 100
            t1_pct = ((target1 - close) / close) * 100
            t2_pct = ((target2 - close) / close) * 100
        else:
            # For SELL/HOLD, show current levels
            entry_zone = f"₹{close:.2f}"
            stop_loss = ema_50 if ema_50 > 0 else close * 1.05
            target1 = close * 0.95
            target2 = close * 0.90
            sl_pct = ((stop_loss - close) / close) * 100
            t1_pct = ((close - target1) / close) * 100
            t2_pct = ((close - target2) / close) * 100

        return AnalysisResult(
            symbol=symbol,
            recommendation=recommendation,
            confidence=confidence,
            current_price=close,
            entry_zone=entry_zone,
            stop_loss=stop_loss,
            stop_loss_pct=sl_pct,
            target1=target1,
            target1_pct=t1_pct,
            target2=target2,
            target2_pct=t2_pct,
            reasoning=reasoning,
            risk_assessment=risk,
            technical_signals=signals,
            timestamp=datetime.now().isoformat()
        )

    def get_watchlist_with_analysis(self) -> List[Dict[str, Any]]:
        """
        Get all watchlist items with their technical analysis.

        Returns:
            List of watchlist items with analysis results
        """
        results = []
        for item in self.watchlist:
            symbol = item['symbol']
            analysis = self.analyze_stock(symbol)

            if analysis:
                results.append({
                    'id': item['id'],
                    'symbol': symbol,
                    'added_at': item['added_at'],
                    'notes': item.get('notes', ''),
                    'analysis': analysis.to_dict()
                })
            else:
                # Include item but with error marker
                results.append({
                    'id': item['id'],
                    'symbol': symbol,
                    'added_at': item['added_at'],
                    'notes': item.get('notes', ''),
                    'analysis': None,
                    'error': 'Failed to fetch data'
                })

        return results
