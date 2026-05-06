"""
Trade Setup Generator Module
Generates actionable trade setups with entry, stop loss, targets, and risk management.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TradeSetup:
    """Complete trade setup with entry, risk management, and targets."""
    stock_symbol: str
    signal_type: str
    timestamp: datetime
    
    direction: str
    
    current_price: float
    
    entry_min: float
    entry_max: float
    entry_strategy: str
    
    stop_loss: float
    stop_loss_pct: float
    risk_level: str
    
    target_1: float
    target_1_pct: float
    target_1_rr: float
    target_1_distance: float
    
    target_2: float
    target_2_pct: float
    target_2_rr: float
    target_2_distance: float
    
    target_3: Optional[float] = None
    target_3_pct: Optional[float] = None
    target_3_rr: Optional[float] = None
    target_3_distance: Optional[float] = None
    
    range_low: float = 0.0
    range_high: float = 0.0
    range_height: float = 0.0
    
    support_level: float = 0.0
    resistance_level: float = 0.0
    
    near_breakout: bool = False
    breakout_distance_pct: float = 0.0
    
    expected_duration: str = ""
    
    confidence: int = 0
    
    positive_factors: List[str] = field(default_factory=list)
    negative_factors: List[str] = field(default_factory=list)
    
    ai_reasoning: str = ""
    sector: str = "Unknown"
    
    position_size: int = 0
    capital_required: float = 0.0
    
    partial_exit_done: bool = False
    trail_sl_active: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'stock_symbol': self.stock_symbol,
            'signal_type': self.signal_type,
            'direction': self.direction,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            'current_price': self.current_price,
            'entry': {
                'min': self.entry_min,
                'max': self.entry_max,
                'strategy': self.entry_strategy
            },
            'stop_loss': {
                'price': self.stop_loss,
                'percentage': self.stop_loss_pct,
                'risk_level': self.risk_level
            },
            'targets': {
                'target_1': {
                    'price': self.target_1,
                    'percentage': self.target_1_pct,
                    'rr_ratio': self.target_1_rr,
                    'distance': self.target_1_distance
                },
                'target_2': {
                    'price': self.target_2,
                    'percentage': self.target_2_pct,
                    'rr_ratio': self.target_2_rr,
                    'distance': self.target_2_distance
                },
                'target_3': {
                    'price': self.target_3,
                    'percentage': self.target_3_pct,
                    'rr_ratio': self.target_3_rr,
                    'distance': self.target_3_distance
                } if self.target_3 else None
            },
            'range': {
                'low': self.range_low,
                'high': self.range_high,
                'height': self.range_height
            },
            'levels': {
                'support': self.support_level,
                'resistance': self.resistance_level
            },
            'breakout': {
                'near_breakout': self.near_breakout,
                'distance_pct': self.breakout_distance_pct
            },
            'expected_duration': self.expected_duration,
            'confidence': self.confidence,
            'positive_factors': self.positive_factors,
            'negative_factors': self.negative_factors,
            'ai_reasoning': self.ai_reasoning,
            'sector': self.sector,
            'position_size': self.position_size,
            'capital_required': self.capital_required,
            'partial_exit_done': self.partial_exit_done,
            'trail_sl_active': self.trail_sl_active
        }


class TradeSetupGenerator:
    """
    Generates actionable trade setups from signals.
    
    Features:
    - Single source of truth for RR / % calc
    - Enforced SL range (2–3%) → no junk trades
    - Targets aligned with validator (5–10%)
    - Better breakout logic (no blind entries)
    - Cleaner confidence scoring
    - Direction-aware logic (BUY/SELL ready)
    - Integrated tracker for adaptive learning
    - Position sizing calculation
    """
    
    MIN_SL = 2.0
    MAX_SL = 3.0
    MIN_TARGET = 5.0
    MAX_TARGET = 10.0
    MIN_RR = 2.0
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        tracker: Optional[Any] = None
    ):
        self.config = config or {}
        self.tracker = tracker
    
    def generate(self, signal: Any, data: Dict[str, Any]) -> Optional[TradeSetup]:
        """
        Generate a trade setup from a signal with strict validation.
        
        Args:
            signal: Signal object with ticker, signal_type, trend_score
            data: Dictionary with price and indicator data
            
        Returns:
            TradeSetup object or None if validation fails
        """
        try:
            price = data.get("close", data.get("current_price", 0))
            if price <= 0:
                return None

            symbol = getattr(signal, "ticker", getattr(signal, "stock_symbol", "UNKNOWN"))
            signal_type = getattr(signal, "signal_type", getattr(signal, "type", "TREND"))
            direction = getattr(signal, "direction", "BUY")
            
            range_low = data.get("range_low", price * 0.98)
            range_high = data.get("range_high", price * 1.02)
            ema_50 = data.get("ema_50", data.get("ema50", price))
            ema_20 = data.get("ema_20", ema_50)
            atr = data.get("atr", 0)
            
            support = min(range_low, ema_50 * 0.98)
            resistance = range_high

            entry_strategy, entry_min, entry_max = self._entry(price, resistance)

            sl = support * 0.98
            sl_pct = self._pct(price, sl)

            if not (self.MIN_SL <= sl_pct <= self.MAX_SL):
                return None
            
            if self.tracker:
                filters = self.tracker.adaptive_filters
                vol_min = filters.get('volume_ratio_min', 1.5)
                rsi_max = filters.get('rsi_max', 70)
                
                vol_ratio = data.get("volume_ratio", 0)
                rsi = data.get("rsi", 50)
                
                if vol_ratio < vol_min:
                    return None
                if rsi > rsi_max:
                    return None
            
            target_1 = price * 1.05
            target_2 = price * 1.08

            t1_pct = self._pct(target_1, price)
            t2_pct = self._pct(target_2, price)

            rr1 = self._rr(price, sl, target_1)
            rr2 = self._rr(price, sl, target_2)

            if rr1 < self.MIN_RR:
                return None

            confidence = self._confidence(signal, data)
            
            if self.tracker:
                weight = self.tracker.get_context_weight(signal_type)
                ai_weight = self.tracker.get_ai_weight(1.0)
                confidence = int(min(10, confidence * weight * ai_weight))

            positives, negatives = self._factors(data, price, resistance)

            range_height = range_high - range_low
            
            target_3 = price * 1.10 if direction == "BUY" else price * 0.90
            t3_pct = self._pct(target_3, price) if direction == "BUY" else self._pct(price, target_3)
            rr3 = self._rr(price, sl, target_3)
            
            expected_duration = self._estimate_duration(atr, price)
            
            position_size, capital_required = self._calculate_position_size(
                price=price,
                stop_loss=sl,
                capital=self.config.get('capital', 100000),
                risk_per_trade=self.config.get('risk_per_trade', 1)
            )

            return TradeSetup(
                stock_symbol=symbol,
                signal_type=signal_type,
                timestamp=datetime.now(),
                direction=direction,
                current_price=price,
                entry_min=round(entry_min, 2),
                entry_max=round(entry_max, 2),
                entry_strategy=entry_strategy,
                stop_loss=round(sl, 2),
                stop_loss_pct=round(sl_pct, 2),
                risk_level=self._risk(sl_pct),
                target_1=round(target_1, 2),
                target_1_pct=round(t1_pct, 2),
                target_1_rr=round(rr1, 2),
                target_1_distance=round(abs(target_1 - price), 2),
                target_2=round(target_2, 2),
                target_2_pct=round(t2_pct, 2),
                target_2_rr=round(rr2, 2),
                target_2_distance=round(abs(target_2 - price), 2),
                target_3=round(target_3, 2),
                target_3_pct=round(t3_pct, 2),
                target_3_rr=round(rr3, 2),
                target_3_distance=round(abs(target_3 - price), 2),
                range_low=round(range_low, 2),
                range_high=round(range_high, 2),
                range_height=round(range_height, 2),
                support_level=round(support, 2),
                resistance_level=round(resistance, 2),
                near_breakout=((resistance - price) / price) * 100 < 1,
                breakout_distance_pct=round(((resistance - price) / price) * 100, 2),
                expected_duration=expected_duration,
                confidence=confidence,
                positive_factors=positives,
                negative_factors=negatives,
                position_size=position_size,
                capital_required=round(capital_required, 2)
            )
        except Exception as e:
            logger.error(f"Error generating trade setup: {e}")
            return None
    
    def _entry(self, price, resistance):
        dist_pct = ((resistance - price) / price) * 100

        if dist_pct <= 0.5:
            return "BREAKOUT", resistance, resistance * 1.005
        return "PULLBACK", price, price * 1.01

    def _pct(self, a, b):
        return abs((a - b) / b) * 100

    def _rr(self, entry, sl, target):
        risk = abs(entry - sl)
        reward = abs(target - entry)
        return reward / risk if risk > 0 else 0

    def _risk(self, sl_pct):
        if sl_pct <= 2:
            return "LOW"
        if sl_pct <= 3:
            return "MEDIUM"
        return "HIGH"

    def _confidence(self, signal, data):
        score = getattr(signal, "trend_score", getattr(signal, "confidence", 5))

        if data.get("volume_ratio", 1) > 1.5:
            score += 1
        if 50 <= data.get("rsi", 50) <= 65:
            score += 1

        return min(10, int(score))

    def _factors(self, data, price, resistance):
        pos, neg = [], []

        if data.get("volume_ratio", 1) > 1.3:
            pos.append("Volume expansion")

        if 50 <= data.get("rsi", 50) <= 65:
            pos.append("RSI ideal zone")

        dist = ((resistance - price) / price) * 100
        if dist < 1:
            pos.append("Near breakout")

        if data.get("rsi", 50) > 70:
            neg.append("Overbought")

        if data.get("volume_ratio", 1) < 1:
            neg.append("Low volume")

        return pos, neg
    
    def _estimate_duration(self, atr: float, current_price: float) -> str:
        """Estimate expected duration based on ATR."""
        if atr <= 0:
            return "Unknown"
        
        atr_pct = (atr / current_price) * 100
        
        if atr_pct < 1.0:
            return "short_term"
        elif atr_pct < 2.0:
            return "medium_term"
        else:
            return "long_term"
    
    def _calculate_position_size(
        self,
        price: float,
        stop_loss: float,
        capital: float = 100000,
        risk_per_trade: float = 1.0
    ) -> Tuple[int, float]:
        """
        Calculate position size based on risk per trade.
        
        Args:
            price: Current price
            stop_loss: Stop loss price
            capital: Total capital
            risk_per_trade: Risk percentage per trade
            
        Returns:
            Tuple of (position_size, capital_required)
        """
        risk_amount = capital * (risk_per_trade / 100)
        risk_per_share = abs(price - stop_loss)
        
        if risk_per_share <= 0:
            return 0, 0.0
        
        qty = int(risk_amount / risk_per_share)
        capital_required = qty * price
        
        return qty, capital_required

    def format_alert_message(self, trade_setup: TradeSetup) -> str:
        """Format trade setup as Telegram alert message."""
        direction_emoji = "🟢" if trade_setup.direction == "BUY" else "🔴"
        
        msg = f"📊 *{trade_setup.signal_type} SIGNAL* {direction_emoji}\n\n"
        msg += f"Stock: *{trade_setup.stock_symbol}*\n"
        msg += f"Direction: *{trade_setup.direction}*\n"
        msg += f"Price: ₹{trade_setup.current_price:.2f}\n\n"
        
        msg += f"🎯 *Entry:*\n"
        msg += f"  Strategy: {trade_setup.entry_strategy}\n"
        msg += f"  Zone: ₹{trade_setup.entry_min:.2f} - ₹{trade_setup.entry_max:.2f}\n\n"
        
        msg += f"🛡️ *Stop Loss:*\n"
        msg += f"  SL: ₹{trade_setup.stop_loss:.2f} ({trade_setup.stop_loss_pct:.1f}%)\n"
        msg += f"  Risk Level: {trade_setup.risk_level}\n\n"
        
        msg += f"🎯 *Targets:*\n"
        msg += f"  T1: ₹{trade_setup.target_1:.2f} (+{trade_setup.target_1_pct:.1f}%) R:R {trade_setup.target_1_rr}\n"
        msg += f"  T2: ₹{trade_setup.target_2:.2f} (+{trade_setup.target_2_pct:.1f}%) R:R {trade_setup.target_2_rr}\n"
        if trade_setup.target_3:
            msg += f"  T3: ₹{trade_setup.target_3:.2f} (+{trade_setup.target_3_pct:.1f}%) R:R {trade_setup.target_3_rr}\n"
        msg += "\n"
        
        msg += f"📈 *Technical Levels:*\n"
        msg += f"  Support: ₹{trade_setup.support_level:.2f}\n"
        msg += f"  Resistance: ₹{trade_setup.resistance_level:.2f}\n"
        msg += f"  Range: ₹{trade_setup.range_low:.2f} - ₹{trade_setup.range_high:.2f}\n"
        
        if trade_setup.near_breakout:
            msg += f"\n⚡ Near Breakout: {trade_setup.breakout_distance_pct:.1f}% away\n"
        
        msg += f"\n⏱️ Expected: {trade_setup.expected_duration}\n"
        msg += f"Confidence: {trade_setup.confidence}/10\n"
        
        if trade_setup.positive_factors:
            msg += f"\n✅ *Positives:*\n"
            for factor in trade_setup.positive_factors[:3]:
                msg += f"  • {factor}\n"
        
        if trade_setup.negative_factors:
            msg += f"\n⚠️ *Negatives:*\n"
            for factor in trade_setup.negative_factors[:3]:
                msg += f"  • {factor}\n"
        
        if trade_setup.ai_reasoning:
            msg += f"\n💡 *AI Insight:*\n{trade_setup.ai_reasoning[:200]}..."
        
        return msg


def create_trade_generator(
    config: Optional[Dict[str, Any]] = None,
    tracker: Optional[Any] = None
) -> TradeSetupGenerator:
    """Factory function to create TradeSetupGenerator."""
    return TradeSetupGenerator(config, tracker)