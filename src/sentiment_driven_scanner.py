"""
Sentiment-Driven Stock Scanner
Combines market sentiment analysis with technical breakout detection.
Alerts on stocks running up in bullish markets with AI validation.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import pytz

logger = logging.getLogger(__name__)


class SentimentDrivenScanner:
    """
    Scans for stocks showing technical breakouts aligned with market sentiment.
    - Filters stocks based on market sentiment
    - Identifies stocks with momentum and volume
    - Validates breakouts using AI analysis
    - Generates intelligent alerts
    """
    
    BREAKOUT_MIN_CHANGE = 1.0  # Minimum 1% move
    BREAKOUT_VOLUME_RATIO = 1.5  # 1.5x average volume
    
    # Sentiment-based filtering
    SENTIMENT_THRESHOLDS = {
        'STRONGLY_BULLISH': {
            'min_change': 0.5,
            'min_volume': 1.2,
            'enable_weak_breakouts': True
        },
        'BULLISH': {
            'min_change': 1.0,
            'min_volume': 1.5,
            'enable_weak_breakouts': False
        },
        'NEUTRAL': {
            'min_change': 1.5,
            'min_volume': 2.0,
            'enable_weak_breakouts': False
        },
        'BEARISH': {
            'min_change': 2.0,
            'min_volume': 2.5,
            'enable_weak_breakouts': False
        },
        'STRONGLY_BEARISH': {
            'min_change': 3.0,
            'min_volume': 3.0,
            'enable_weak_breakouts': False
        }
    }
    
    def __init__(self, data_fetcher=None, sentiment_analyzer=None, ai_analyzer=None):
        self.data_fetcher = data_fetcher
        self.sentiment_analyzer = sentiment_analyzer
        self.ai_analyzer = ai_analyzer
        self.ist = pytz.timezone('Asia/Kolkata')
        
        logger.info("SentimentDrivenScanner initialized")
    
    def scan_with_sentiment(self, stocks: List[str], lookback: int = 5) -> List[Dict[str, Any]]:
        """
        Scan stocks for technical breakouts aligned with market sentiment.
        Returns list of stocks with breakout signals.
        """
        if not self.sentiment_analyzer:
            logger.warning("Sentiment analyzer not available")
            return []
        
        alerts = []
        
        try:
            # Get current market sentiment
            sentiment_data = self.sentiment_analyzer.analyze_market_sentiment()
            sentiment = sentiment_data.get('sentiment', 'NEUTRAL')
            
            logger.info(f"Market Sentiment: {sentiment}")
            logger.info(f"Scanning {len(stocks)} stocks...")
            
            # Get sentiment thresholds
            thresholds = self.SENTIMENT_THRESHOLDS.get(sentiment, self.SENTIMENT_THRESHOLDS['NEUTRAL'])
            
            for symbol in stocks:
                try:
                    signal = self._analyze_stock_breakout(symbol, thresholds, sentiment_data, lookback)
                    if signal:
                        alerts.append(signal)
                except Exception as e:
                    logger.debug(f"Error analyzing {symbol}: {e}")
            
            # Sort by confidence/strength
            alerts.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            
            logger.info(f"Found {len(alerts)} breakout signals")
            return alerts
            
        except Exception as e:
            logger.error(f"Error in sentiment-driven scan: {e}")
            return []
    
    def _analyze_stock_breakout(self, symbol: str, thresholds: Dict[str, Any], 
                                sentiment_data: Dict[str, Any], lookback: int) -> Optional[Dict[str, Any]]:
        """Analyze a single stock for breakout signals."""
        try:
            if not self.data_fetcher:
                return None
            
            # Fetch data
            df = self.data_fetcher.fetch_data(symbol, period='3mo', interval='1d')
            
            if df is None or len(df) < max(lookback, 50):
                return None
            
            current_row = df.iloc[-1]
            close = current_row['close']
            volume = current_row['volume']
            
            # Calculate metrics
            prev_close = df['close'].iloc[-lookback]
            price_change = ((close - prev_close) / prev_close) * 100
            
            volume_ma = df['volume'].tail(20).mean()
            volume_ratio = (volume / volume_ma) if volume_ma > 0 else 1.0
            
            # Check breakout thresholds
            min_change = thresholds.get('min_change', 1.0)
            min_volume = thresholds.get('min_volume', 1.5)
            
            if price_change < min_change or volume_ratio < min_volume:
                return None
            
            # Calculate technical indicators
            ema20 = df['close'].ewm(span=20).mean().iloc[-1]
            ema50 = df['close'].ewm(span=50).mean().iloc[-1]
            ema100 = df['close'].ewm(span=100).mean().iloc[-1]
            ema200 = df['close'].ewm(span=200).mean().iloc[-1]
            rsi = self._calculate_rsi(df, 14)
            atr = self._calculate_atr(df, 14)
            
            # Check for 20-day high
            high_20 = df['high'].tail(20).max()
            is_high_breakout = close > high_20 * 0.99  # Allow 1% tolerance
            
            # Detect breakout type
            breakout_type = self._detect_breakout_type(close, ema20, ema50, ema100, ema200, high_20)
            
            # Calculate momentum score
            momentum_score = self._calculate_momentum_score(
                price_change, volume_ratio, rsi, close, ema50
            )
            
            # Technical quality score
            quality_score = self._calculate_quality_score(
                close, ema20, ema50, ema100, ema200, rsi, volume_ratio, high_20
            )
            
            # Determine confidence based on sentiment
            base_confidence = self._calculate_base_confidence(sentiment_data, quality_score)
            
            # AI validation (if available)
            ai_valid = True
            ai_reason = "No AI validation"
            ai_confidence = 0.5
            
            if self.ai_analyzer:
                ai_valid, ai_reason, ai_confidence = self.sentiment_analyzer.validate_breakout_with_ai(
                    symbol,
                    {
                        'price': close,
                        'rsi': rsi,
                        'volume_ratio': volume_ratio,
                        'ema20': ema20,
                        'ema50': ema50,
                        'price_change': price_change,
                        'sentiment': sentiment_data.get('sentiment', 'NEUTRAL')
                    }
                )
            
            # Final confidence
            final_confidence = (base_confidence * 0.7 + ai_confidence * 0.3) if ai_valid else (base_confidence * 0.5)
            
            # Only alert if confidence is reasonable
            if final_confidence < 0.5:
                return None
            
            # Support/Resistance levels
            resistance = close + (atr * 2)
            support = close - (atr * 1.5)
            
            return {
                'symbol': symbol,
                'price': close,
                'price_change': price_change,
                'volume_ratio': volume_ratio,
                'ema20': ema20,
                'ema50': ema50,
                'ema100': ema100,
                'ema200': ema200,
                'rsi': rsi,
                'atr': atr,
                'breakout_type': breakout_type,
                'is_high_breakout': is_high_breakout,
                'momentum_score': momentum_score,
                'quality_score': quality_score,
                'confidence': final_confidence,
                'ai_valid': ai_valid,
                'ai_reason': ai_reason,
                'support': support,
                'resistance': resistance,
                'sentiment': sentiment_data.get('sentiment', 'NEUTRAL'),
                'timestamp': datetime.now(self.ist).isoformat()
            }
        
        except Exception as e:
            logger.debug(f"Error analyzing {symbol}: {e}")
            return None
    
    def _detect_breakout_type(self, close: float, ema20: float, ema50: float, 
                              ema100: float, ema200: float, high_20: float) -> str:
        """Detect type of breakout."""
        if close > ema20 > ema50 > ema100 > ema200:
            return "TREND_ALIGNED"
        elif close > high_20:
            return "LEVEL_BREAKOUT"
        elif close > ema20 and close > ema50:
            return "MA_BREAKOUT"
        else:
            return "MOMENTUM_BREAKOUT"
    
    def _calculate_momentum_score(self, price_change: float, volume_ratio: float, 
                                  rsi: float, close: float, ema50: float) -> float:
        """Calculate momentum score (0-10)."""
        try:
            # Price change contribution
            price_score = min(10, abs(price_change) * 2)
            
            # Volume contribution
            volume_score = min(10, volume_ratio * 3)
            
            # RSI contribution (away from 50)
            rsi_distance = abs(rsi - 50) / 50
            rsi_score = rsi_distance * 10
            
            # Price above EMA50
            ema_position = (close - ema50) / ema50 * 100
            ema_score = min(10, abs(ema_position) * 0.5)
            
            momentum = (price_score * 0.4 + volume_score * 0.3 + rsi_score * 0.2 + ema_score * 0.1)
            
            return float(min(10, max(0, momentum)))
        except:
            return 0.0
    
    def _calculate_quality_score(self, close: float, ema20: float, ema50: float, 
                                 ema100: float, ema200: float, rsi: float, 
                                 volume_ratio: float, high_20: float) -> float:
        """Calculate technical quality score (0-10)."""
        try:
            score = 0.0
            
            # EMA alignment (0-3)
            if close > ema20 > ema50 > ema100 > ema200:
                score += 3
            elif close > ema20 > ema50:
                score += 2
            elif close > ema20:
                score += 1
            
            # RSI position (0-2)
            if 50 < rsi < 75:
                score += 2
            elif 50 < rsi < 80:
                score += 1.5
            elif 40 < rsi < 60:
                score += 1
            
            # Volume (0-2)
            if volume_ratio > 2.5:
                score += 2
            elif volume_ratio > 1.5:
                score += 1.5
            elif volume_ratio > 1.2:
                score += 1
            
            # Distance from 20-day high (0-2)
            distance_from_high = (1 - ((high_20 - close) / high_20)) * 100
            if distance_from_high > 1:  # Close to or above 20-day high
                score += 2
            elif distance_from_high > -1:
                score += 1.5
            
            # Price above key EMAs (0-1)
            if close > ema100:
                score += 1
            
            return float(min(10, max(0, score)))
        except:
            return 0.0
    
    def _calculate_base_confidence(self, sentiment_data: Dict[str, Any], quality_score: float) -> float:
        """Calculate base confidence based on sentiment and quality."""
        sentiment = sentiment_data.get('sentiment', 'NEUTRAL')
        momentum = sentiment_data.get('market_momentum', 0.0)
        
        # Sentiment multiplier
        sentiment_multiplier = {
            'STRONGLY_BULLISH': 1.4,
            'BULLISH': 1.2,
            'NEUTRAL': 1.0,
            'BEARISH': 0.7,
            'STRONGLY_BEARISH': 0.4
        }
        
        multiplier = sentiment_multiplier.get(sentiment, 1.0)
        
        # Base confidence from quality (0-1)
        quality_confidence = quality_score / 10.0
        
        # Apply sentiment multiplier and momentum
        final_confidence = quality_confidence * multiplier
        
        # Add momentum bonus in bullish markets
        if momentum > 0.3 and sentiment in ['STRONGLY_BULLISH', 'BULLISH']:
            final_confidence *= 1.1
        
        return float(min(1.0, max(0.0, final_confidence)))
    
    def _calculate_rsi(self, df, period=14):
        """Calculate RSI."""
        try:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss if loss.iloc[-1] > 0 else 0
            rsi = 100 - (100 / (1 + rs)) if rs > 0 else 50
            return float(rsi.iloc[-1])
        except:
            return 50.0
    
    def _calculate_atr(self, df, period=14):
        """Calculate ATR."""
        try:
            high = df['high']
            low = df['low']
            close = df['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean().iloc[-1]
            return float(atr)
        except:
            return 0.0
    
    def format_breakout_alert(self, signal: Dict[str, Any]) -> str:
        """Format breakout signal as alert message."""
        try:
            confidence_pct = signal.get('confidence', 0) * 100
            symbol = signal.get('symbol', 'N/A')
            price = signal.get('price', 0)
            price_change = signal.get('price_change', 0)
            volume_ratio = signal.get('volume_ratio', 0)
            rsi = signal.get('rsi', 0)
            breakout_type = signal.get('breakout_type', 'UNKNOWN')
            support = signal.get('support', 0)
            resistance = signal.get('resistance', 0)
            sentiment = signal.get('sentiment', 'NEUTRAL')
            quality_score = signal.get('quality_score', 0)
            
            # Determine emoji based on confidence
            if confidence_pct >= 80:
                emoji = "🟢"
            elif confidence_pct >= 60:
                emoji = "🟡"
            else:
                emoji = "🟠"
            
            alert = f"""{emoji} SENTIMENT-DRIVEN BREAKOUT
━━━━━━━━━━━━━━━━━━━━━━━
📊 {symbol} @ ₹{price:.2f}

📈 Price Action:
   • Change: +{price_change:.2f}%
   • Volume: {volume_ratio:.2f}x avg
   • RSI: {rsi:.1f}

🎯 Technical:
   • Type: {breakout_type}
   • Support: ₹{support:.2f}
   • Target: ₹{resistance:.2f}
   • Quality: {quality_score:.1f}/10

📍 Market Context:
   • Sentiment: {sentiment}
   • Confidence: {confidence_pct:.0f}%

⏰ {signal.get('timestamp', 'N/A')}"""
            
            return alert
        
        except Exception as e:
            logger.error(f"Error formatting alert: {e}")
            return f"Breakout Signal: {signal.get('symbol', 'N/A')}"


def create_sentiment_driven_scanner(data_fetcher=None, sentiment_analyzer=None, ai_analyzer=None) -> SentimentDrivenScanner:
    """Factory function to create sentiment-driven scanner."""
    return SentimentDrivenScanner(
        data_fetcher=data_fetcher,
        sentiment_analyzer=sentiment_analyzer,
        ai_analyzer=ai_analyzer
    )
