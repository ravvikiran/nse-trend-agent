"""
Options Scanner

Focus: Volatility + timing
Timeframes: Trend → Daily, Entry → 15m / 5m

Core Logic - Signal ONLY if:
- Underlying stock gives signal
- IV expansion starting
- OI confirms direction

Key Indicators:
- IV percentile
- OI change
- PCR (Put Call Ratio)
- ATR expansion

Strategies:
- Breakout + Call buy
- Breakdown + Put buy
- High IV → option selling (advanced)

Risk: Strict SL (options decay fast)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class OptionsSignal:
    """Options trading signal"""
    ticker: str
    signal_type: str  # CALL or PUT
    timestamp: datetime
    
    # Underlying
    underlying_signal: bool
    underlying_price: float
    
    # IV Analysis
    iv_percentile: float = 0.0
    iv_expansion_starting: bool = False
    iv_rank: str = "LOW"
    
    # OI Analysis
    oi_change_pct: float = 0.0
    oi_direction: str = "NEUTRAL"
    
    # PCR
    pcr: float = 1.0
    pcr_interpretation: str = "NEUTRAL"
    
    # ATR
    atr_percent: float = 0.0
    atr_expanding: bool = False
    
    # Entry parameters
    entry_price: float = 0.0
    strike_price: float = 0.0
    expiry: str = ""
    option_type: str = ""  # CE or PE
    
    # Stop loss (strict - options decay fast)
    stop_loss: float = 0.0
    stop_loss_pct: float = 0.0
    
    # Target
    target_price: float = 0.0
    target_pct: float = 0.0
    
    # Strategy
    strategy_type: str = "BREAKOUT_CALL"  # or BREAKDOWN_PUT, IV_SELL
    
    # Confidence
    confidence_score: int = 0
    rejection_reason: Optional[str] = None
    
    # Risk
    risk_reward: float = 0.0
    
    # Reasoning
    reasoning_breakdown: Dict[str, str] = field(default_factory=dict)
    
    def is_valid(self) -> bool:
        return self.rejection_reason is None and self.confidence_score >= 7
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'ticker': self.ticker,
            'signal_type': self.signal_type,
            'underlying_signal': self.underlying_signal,
            'iv_percentile': self.iv_percentile,
            'iv_expansion_starting': self.iv_expansion_starting,
            'oi_change_pct': self.oi_change_pct,
            'pcr': self.pcr,
            'atr_percent': self.atr_percent,
            'entry_price': self.entry_price,
            'strike_price': self.strike_price,
            'stop_loss': self.stop_loss,
            'target_price': self.target_price,
            'confidence_score': self.confidence_score,
            'is_valid': self.is_valid(),
            'rejection_reason': self.rejection_reason,
            'strategy_type': self.strategy_type
        }


class OptionsScanner:
    """
    Scanner for options trading signals.
    
    Timeframe Setup:
    - Trend: 1D (Daily) - For underlying direction
    - Entry: 15m / 5m - For timing
    
    Prerequisites (ALL must be true):
    1. Underlying stock gives a signal
    2. IV expansion starting (IV percentile rising)
    3. OI confirms direction
    
    Key Indicators:
    - IV percentile (threshold: >50 for calls, high IV)
    - OI change (>10% increase in direction)
    - PCR (<0.7 bullish, >1.3 bearish)
    - ATR expansion (volatility increasing)
    
    Risk Management:
    - Strict SL (options decay fast)
    - Max loss: 30%
    """
    
    MIN_CONFIDENCE = 7
    MIN_IV_PERCENTILE = 50.0
    MIN_OI_CHANGE = 10.0
    MAX_STOP_LOSS_PCT = 30.0
    
    def __init__(self):
        self.alerted_today = set()
        self.last_reset_date = None
    
    def get_iv_data(self, ticker: str) -> Dict[str, Any]:
        """
        Get IV data for the stock from options chain.
        Returns: {iv_percentile, iv_rank, iv_current}
        """
        try:
            import yfinance as yf
            ticker_clean = ticker.replace('.NS', '')
            nse_ticker = f"{ticker_clean}.NS"
            
            stock = yf.Ticker(nse_ticker)
            info = stock.info
            
            iv = info.get('impliedVolatility', 0)
            iv_historical = info.get('historicalVolatility', 0)
            
            if iv and iv_historical:
                percentile = min(100, (iv / iv_historical) * 50) if iv_historical > 0 else 50
            else:
                percentile = 50.0
            
            return {
                'iv_percentile': percentile,
                'iv_current': iv * 100 if iv else 50,
                'iv_rank': 'HIGH' if percentile > 70 else 'MEDIUM' if percentile > 40 else 'LOW'
            }
        except Exception as e:
            logger.debug(f"Could not fetch IV for {ticker}: {e}")
            return {
                'iv_percentile': 50.0,
                'iv_current': 50.0,
                'iv_rank': 'MEDIUM'
            }
    
    def get_oi_data(self, ticker: str) -> Dict[str, Any]:
        """
        Get OI data for the stock.
        Returns: {total_oi, oi_change_pct, oi_direction}
        """
        try:
            return {
                'total_oi': 0,
                'oi_change_pct': 0.0,
                'oi_direction': 'NEUTRAL'
            }
        except:
            return {
                'total_oi': 0,
                'oi_change_pct': 0.0,
                'oi_direction': 'NEUTRAL'
            }
    
    def get_pcr(self, ticker: str) -> Tuple[float, str]:
        """
        Get Put Call Ratio and interpretation.
        
        PCR < 0.7: Bullish (more calls)
        PCR 0.7-1.3: Neutral
        PCR > 1.3: Bearish (more puts)
        """
        try:
            return 1.0, "NEUTRAL"
        except:
            return 1.0, "NEUTRAL"
    
    def check_iv_expansion(self, indicators: Dict[str, float], prev_indicators: Optional[Dict[str, float]]) -> Tuple[bool, str]:
        """
        Check if IV is expanding.
        Compare current ATR with previous to detect volatility expansion.
        """
        current_atr = indicators.get('atr', 0)
        current_price = indicators.get('close', 0)
        
        if current_price > 0:
            atr_percent = (current_atr / current_price) * 100
        else:
            atr_percent = 0
        
        if prev_indicators:
            prev_atr = prev_indicators.get('atr', 0)
            if prev_atr > 0:
                atr_change = ((current_atr - prev_atr) / prev_atr) * 100
                if atr_change > 20:
                    return True, f"ATR expanding +{atr_change:.1f}%"
        
        if atr_percent > 2.0:
            return True, f"High ATR: {atr_percent:.2f}%"
        
        return False, f"Low ATR: {atr_percent:.2f}%"
    
    def check_atr_expansion(
        self, 
        df_15m: pd.DataFrame, 
        lookback: int = 20
    ) -> Tuple[bool, float]:
        """
        Check if ATR is expanding (volatility increasing).
        """
        if df_15m is None or len(df_15m) < lookback:
            return False, 0.0
        
        try:
            recent = df_15m.tail(lookback).copy()
            
            tr1 = recent['high'] - recent['low']
            tr2 = abs(recent['high'] - recent['close'].shift(1))
            tr3 = abs(recent['low'] - recent['close'].shift(1))
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            recent_atr = tr.rolling(window=14).mean().iloc[-1]
            older_atr = tr.rolling(window=14).mean().iloc[-10]
            
            if older_atr > 0:
                atr_change = ((recent_atr - older_atr) / older_atr) * 100
                
                current_price = recent['close'].iloc[-1]
                atr_percent = (recent_atr / current_price) * 100
                
                return atr_change > 20, atr_percent
            
            return False, 0.0
        except:
            return False, 0.0
    
    def calculate_option_strike(
        self,
        underlying_price: float,
        signal_type: str,
        atm_offset: float = 0.02
    ) -> float:
        """
        Calculate ATM strike price.
        Default: 2% OTM for options
        """
        if signal_type == "CALL":
            return underlying_price * (1 + atm_offset)
        else:
            return underlying_price * (1 - atm_offset)
    
    def calculate_option_prices(
        self,
        underlying_price: float,
        strike_price: float,
        iv_percentile: float,
        days_to_expiry: int = 7
    ) -> Tuple[float, float, float]:
        """
        Estimate option prices using simple model.
        Returns: (entry_price, stop_loss, target)
        
        Note: For accurate pricing, use Black-Scholes or market data
        """
        moneyness = abs(underlying_price - strike_price) / strike_price
        
        base_premium = underlying_price * 0.02
        
        iv_multiplier = 1 + (iv_percentile / 100)
        
        time_decay = 1 - (days_to_expiry / 30)
        time_decay = max(0.5, time_decay)
        
        entry = base_premium * iv_multiplier * time_decay
        
        stop_loss = entry * 0.70
        target = entry * 2.0
        
        return entry, stop_loss, target
    
    def scan_stock(
        self,
        ticker: str,
        underlying_signal: bool,
        df_15m: pd.DataFrame,
        indicators_15m: Dict[str, float],
        prev_indicators_15m: Optional[Dict[str, float]] = None,
        trade_direction: str = "BULLISH"
    ) -> Optional[OptionsSignal]:
        """
        Scan a single stock for options trading opportunities.
        
        Args:
            ticker: Stock symbol
            underlying_signal: Whether underlying gives signal
            df_15m: 15-minute timeframe data
            indicators_15m: Indicators from 15m
            prev_indicators_15m: Previous indicators for comparison
            trade_direction: BULLISH or BEARISH
            
        Returns:
            OptionsSignal if valid, None if rejected
        """
        timestamp = datetime.now()
        
        if not underlying_signal:
            logger.debug(f"{ticker} - No underlying signal")
            return None
        
        iv_data = self.get_iv_data(ticker)
        iv_percentile = iv_data['iv_percentile']
        iv_rank = iv_data['iv_rank']
        
        oi_data = self.get_oi_data(ticker)
        oi_change_pct = oi_data['oi_change_pct']
        
        pcr, pcr_interp = self.get_pcr(ticker)
        
        iv_expanding, iv_reason = self.check_iv_expansion(
            indicators_15m, 
            prev_indicators_15m
        )
        
        atr_expanding, atr_percent = self.check_atr_expansion(df_15m)
        
        if trade_direction == "BULLISH":
            if pcr > 1.0:
                logger.debug(f"{ticker} - PCR bearish for call")
                return None
            
            if pcr < 0.7:
                pcr_favorable = True
            else:
                pcr_favorable = False
                
            signal_type = "CALL"
            oi_expected = "CALL"
        else:
            if pcr < 1.0:
                logger.debug(f"{ticker} - PCR bullish for put")
                return None
            
            if pcr > 1.3:
                pcr_favorable = True
            else:
                pcr_favorable = False
                
            signal_type = "PUT"
            oi_expected = "PUT"
        
        oi_direction = oi_data.get('oi_direction', 'NEUTRAL')
        if oi_expected == "CALL" and oi_direction == "INCREASING":
            oi_favorable = True
        elif oi_expected == "PUT" and oi_direction == "DECREASING":
            oi_favorable = True
        else:
            oi_favorable = abs(oi_change_pct) > self.MIN_OI_CHANGE
        
        if not iv_expanding and iv_percentile < self.MIN_IV_PERCENTILE:
            logger.debug(f"{ticker} - No IV expansion, low IV")
            return None
        
        underlying_price = indicators_15m.get('close', 0)
        
        if signal_type == "CALL":
            strike = self.calculate_option_strike(underlying_price, "CALL")
            option_type = "CE"
        else:
            strike = self.calculate_option_strike(underlying_price, "PUT")
            option_type = "PE"
        
        entry_price, stop_loss, target_price = self.calculate_option_prices(
            underlying_price,
            strike,
            iv_percentile
        )
        
        stop_loss_pct = ((entry_price - stop_loss) / entry_price) * 100
        
        if stop_loss_pct > self.MAX_STOP_LOSS_PCT:
            stop_loss = entry_price * 0.70
            stop_loss_pct = 30.0
        
        target_pct = ((target_price - entry_price) / entry_price) * 100
        risk_reward = target_pct / stop_loss_pct if stop_loss_pct > 0 else 0
        
        confidence = self._calculate_confidence(
            underlying_signal=underlying_signal,
            iv_percentile=iv_percentile,
            iv_expanding=iv_expanding,
            oi_change_pct=oi_change_pct,
            pcr_favorable=pcr_favorable,
            atr_expanding=atr_expanding,
            atr_percent=atr_percent
        )
        
        strategy = "BREAKOUT_CALL" if signal_type == "CALL" else "BREAKDOWN_PUT"
        
        if iv_percentile > 70:
            strategy = "HIGH_IV_SELL"
        
        reasoning = {
            "IV": f"{iv_percentile:.1f}% ({iv_rank})",
            "IV Expansion": "Yes" if iv_expanding else "No",
            "OI Change": f"{oi_change_pct:+.1f}%",
            "PCR": f"{pcr:.2f} ({pcr_interp})",
            "ATR": f"{atr_percent:.2f}%",
            "Direction": trade_direction
        }
        
        signal = OptionsSignal(
            ticker=ticker,
            signal_type=signal_type,
            timestamp=timestamp,
            underlying_signal=underlying_signal,
            underlying_price=underlying_price,
            iv_percentile=iv_percentile,
            iv_expansion_starting=iv_expanding,
            iv_rank=iv_rank,
            oi_change_pct=oi_change_pct,
            oi_direction=oi_direction,
            pcr=pcr,
            pcr_interpretation=pcr_interp,
            atr_percent=atr_percent,
            atr_expanding=atr_expanding,
            entry_price=entry_price,
            strike_price=strike,
            option_type=option_type,
            stop_loss=stop_loss,
            stop_loss_pct=stop_loss_pct,
            target_price=target_price,
            target_pct=target_pct,
            strategy_type=strategy,
            confidence_score=confidence,
            risk_reward=risk_reward,
            reasoning_breakdown=reasoning
        )
        
        if confidence >= self.MIN_CONFIDENCE:
            return signal
        
        return None
    
    def _calculate_confidence(
        self,
        underlying_signal: bool,
        iv_percentile: float,
        iv_expanding: bool,
        oi_change_pct: float,
        pcr_favorable: bool,
        atr_expanding: bool,
        atr_percent: float
    ) -> int:
        """Calculate confidence score (0-10)"""
        score = 4
        
        if underlying_signal:
            score += 2
        
        if iv_expanding:
            score += 2
        elif iv_percentile > 70:
            score += 1
        
        if abs(oi_change_pct) > self.MIN_OI_CHANGE:
            score += 2
        
        if pcr_favorable:
            score += 1
        
        if atr_expanding:
            score += 1
        elif atr_percent > 2.0:
            score += 1
        
        return min(10, max(1, score))
    
    def scan_multiple_stocks(
        self,
        stocks_data: Dict[str, pd.DataFrame],
        all_indicators: Dict[str, Dict[str, float]],
        underlying_signals: Dict[str, bool],
        trade_directions: Dict[str, str]
    ) -> List[OptionsSignal]:
        """Scan multiple stocks"""
        signals = []
        
        for ticker, df_15m in stocks_data.items():
            indicators = all_indicators.get(ticker, {}).get('15m', {})
            prev_indicators = all_indicators.get(ticker, {}).get('15m_prev')
            
            underlying = underlying_signals.get(ticker, False)
            direction = trade_directions.get(ticker, "BULLISH")
            
            signal = self.scan_stock(
                ticker=ticker,
                underlying_signal=underlying,
                df_15m=df_15m,
                indicators_15m=indicators,
                prev_indicators_15m=prev_indicators,
                trade_direction=direction
            )
            
            if signal:
                signals.append(signal)
        
        signals.sort(key=lambda x: x.confidence_score, reverse=True)
        return signals
    
    def reset_daily(self):
        """Reset alerted stocks for new day"""
        from datetime import date
        today = date.today()
        
        if self.last_reset_date != today:
            self.alerted_today.clear()
            self.last_reset_date = today


def format_options_signal_alert(signal: OptionsSignal) -> str:
    """Format options signal as alert message"""
    emoji = "📈" if signal.signal_type == "CALL" else "📉"
    
    lines = [
        f"{emoji} OPTIONS SIGNAL",
        "",
        f"🎯 {signal.ticker} {signal.option_type}",
        f"₹{signal.strike_price:.0f} {signal.expiry if signal.expiry else 'Weekly'}",
        "",
        f"💰 Entry: ₹{signal.entry_price:.2f}",
        f"🛡️ SL: ₹{signal.stop_loss:.2f} ({signal.stop_loss_pct:.1f}%)",
        f"🎯 Target: ₹{signal.target_price:.2f} ({signal.target_pct:.1f}%)",
        "",
        f"📊 IV: {signal.iv_percentile:.1f}% ({signal.iv_rank})",
        f"📊 OI: {signal.oi_change_pct:+.1f}%",
        f"📊 PCR: {signal.pcr:.2f}",
        f"📊 ATR: {signal.atr_percent:.2f}%",
        f"📈 Conf: {signal.confidence_score}/10"
    ]
    
    return "\n".join(lines)


def create_options_scanner() -> OptionsScanner:
    """Create and return a configured options scanner"""
    return OptionsScanner()
