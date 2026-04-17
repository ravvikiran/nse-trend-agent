"""
Market Sentiment Analyzer - AI-Driven Market Analysis
Analyzes market sentiment, sector trends, and identifies stocks running up.
Provides AI-validated alerts for technical breakouts in bullish markets.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd
import pytz

logger = logging.getLogger(__name__)

DATA_DIR = 'data'


class MarketSentimentAnalyzer:
    """
    Comprehensive market sentiment analysis for Indian stock market.
    - Analyzes NIFTY trend and momentum
    - Detects sector strength/weakness
    - Identifies stocks running up with volume
    - Provides AI-validated alerts
    """
    
    SENTIMENT_FILE = 'market_sentiment.json'
    SECTOR_PERFORMANCE_FILE = 'sector_performance.json'
    
    NIFTY_SYMBOL = '^NSEI'
    BANK_NIFTY_SYMBOL = '^NSEBANK'
    
    SENTIMENT_TTL_MINUTES = 15
    
    # Sentiment thresholds
    BULLISH_EMA_THRESHOLD = 1.002  # EMA20 > EMA50 * 1.002 (0.2%)
    BEARISH_EMA_THRESHOLD = 0.998  # EMA20 < EMA50 * 0.998 (0.2%)
    STRONG_MOMENTUM_RSI = 65
    WEAK_MOMENTUM_RSI = 35
    
    # Sectors in Indian market
    SECTORS = {
        'IT': ['INFY', 'TCS', 'WIPRO', 'HCLTECH', 'LTTS', 'MPHASIS'],
        'BANKING': ['ICICIBANK', 'HDFC BANK', 'AXISBANK', 'SBIN', 'KOTAK'],
        'AUTO': ['MARUTI', 'HYUNDAI', 'TATA MOTORS', 'BAJAJ AUTO', 'HERO'],
        'PHARMA': ['CIPLA', 'SUNPHARMA', 'DIVI LAB', 'LUPIN', 'GLENMARK'],
        'FMCG': ['NESTLEIND', 'BRITANNIA', 'MARICO', 'ITC', 'GODREJ'],
        'ENERGY': ['RELIANCE', 'NTPC', 'IOC', 'BPCLPSE', 'ADANIGREEN'],
        'METALS': ['TATASTEEL', 'HINDALCO', 'JINDALSTEL', 'VEDL'],
        'REALTY': ['DLF', 'LODHA', 'SUNTECK', 'SHRIRAMCITY'],
    }
    
    def __init__(self, data_fetcher=None, ai_analyzer=None, data_dir: str = DATA_DIR):
        self.data_fetcher = data_fetcher
        self.ai_analyzer = ai_analyzer
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        self.current_sentiment = 'NEUTRAL'
        self.sentiment_strength = 0.0  # -1 to +1
        self.nifty_trend = 'SIDEWAYS'
        self.market_momentum = 0.0
        self.volatility = 0.0
        self.sector_trends = {}
        self.running_stocks = []
        self.last_update = None
        self.ist = pytz.timezone('Asia/Kolkata')
        
        self._load_sentiment()
        logger.info("MarketSentimentAnalyzer initialized")
    
    def _load_sentiment(self) -> None:
        """Load cached sentiment data."""
        filepath = os.path.join(self.data_dir, self.SENTIMENT_FILE)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    self.current_sentiment = data.get('current_sentiment', 'NEUTRAL')
                    self.sentiment_strength = data.get('sentiment_strength', 0.0)
                    self.nifty_trend = data.get('nifty_trend', 'SIDEWAYS')
                    self.market_momentum = data.get('market_momentum', 0.0)
                    self.volatility = data.get('volatility', 0.0)
                    self.sector_trends = data.get('sector_trends', {})
                    self.last_update = data.get('last_updated')
            except Exception as e:
                logger.error(f"Error loading sentiment data: {e}")
    
    def _save_sentiment(self) -> None:
        """Save sentiment data to cache."""
        filepath = os.path.join(self.data_dir, self.SENTIMENT_FILE)
        data = {
            'current_sentiment': self.current_sentiment,
            'sentiment_strength': self.sentiment_strength,
            'nifty_trend': self.nifty_trend,
            'market_momentum': self.market_momentum,
            'volatility': self.volatility,
            'sector_trends': self.sector_trends,
            'last_updated': datetime.now(self.ist).isoformat()
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving sentiment data: {e}")
    
    def analyze_market_sentiment(self) -> Dict[str, Any]:
        """
        Analyze overall market sentiment.
        Returns: {sentiment, strength, nifty_trend, momentum, volatility, sector_trends}
        """
        if not self.data_fetcher:
            logger.warning("No data fetcher available for sentiment analysis")
            return self._get_cached_sentiment()
        
        try:
            # Fetch NIFTY data
            nifty_data = self._fetch_index_data(self.NIFTY_SYMBOL)
            if nifty_data is None:
                return self._get_cached_sentiment()
            
            # Calculate sentiment components
            self.nifty_trend = self._determine_trend(nifty_data)
            self.market_momentum = self._calculate_momentum(nifty_data)
            self.volatility = nifty_data.get('volatility', 0.0)
            self.sentiment_strength = self._calculate_sentiment_strength(nifty_data)
            
            # Determine overall sentiment
            self.current_sentiment = self._determine_sentiment(
                self.nifty_trend,
                self.market_momentum,
                self.sentiment_strength
            )
            
            # Analyze sector trends
            self.sector_trends = self._analyze_sector_trends()
            
            # Save sentiment data
            self._save_sentiment()
            
            return self.get_sentiment_summary()
            
        except Exception as e:
            logger.error(f"Error analyzing market sentiment: {e}")
            return self._get_cached_sentiment()
    
    def _fetch_index_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch and analyze index data."""
        try:
            df = self.data_fetcher.fetch_data(symbol, period='3mo', interval='1d')
            
            if df is None or df.empty or len(df) < 50:
                return None
            
            close = df['close'].iloc[-1]
            volume = df['volume'].iloc[-1]
            
            # Calculate EMAs
            ema20 = df['close'].ewm(span=20).mean().iloc[-1]
            ema50 = df['close'].ewm(span=50).mean().iloc[-1]
            ema100 = df['close'].ewm(span=100).mean().iloc[-1]
            ema200 = df['close'].ewm(span=200).mean().iloc[-1]
            
            # Calculate RSI
            rsi = self._calculate_rsi(df, 14)
            
            # Calculate ATR and volatility
            atr = self._calculate_atr(df, 14)
            volatility = (atr / close * 100) if close > 0 else 0
            
            # Price performance
            price_change_5d = ((close - df['close'].iloc[-5]) / df['close'].iloc[-5] * 100) if len(df) >= 5 else 0
            price_change_20d = ((close - df['close'].iloc[-20]) / df['close'].iloc[-20] * 100) if len(df) >= 20 else 0
            
            # Volume analysis
            volume_ma = df['volume'].tail(20).mean()
            volume_ratio = (volume / volume_ma) if volume_ma > 0 else 1.0
            
            # EMA alignment
            ema_aligned = close > ema20 > ema50 > ema100 > ema200
            
            return {
                'close': close,
                'volume': volume,
                'ema20': ema20,
                'ema50': ema50,
                'ema100': ema100,
                'ema200': ema200,
                'rsi': rsi,
                'atr': atr,
                'volatility': volatility,
                'price_change_5d': price_change_5d,
                'price_change_20d': price_change_20d,
                'volume_ratio': volume_ratio,
                'ema_aligned': ema_aligned,
                'ema_slope': ((ema50 - ema200) / ema200 * 100) if ema200 > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error fetching index data for {symbol}: {e}")
            return None
    
    def _determine_trend(self, index_data: Dict[str, Any]) -> str:
        """Determine trend from EMA alignment."""
        close = index_data['close']
        ema20 = index_data['ema20']
        ema50 = index_data['ema50']
        ema200 = index_data['ema200']
        
        if close > ema20 > ema50 > ema200:
            return 'UPTREND'
        elif close < ema20 < ema50 < ema200:
            return 'DOWNTREND'
        else:
            return 'SIDEWAYS'
    
    def _calculate_momentum(self, index_data: Dict[str, Any]) -> float:
        """Calculate market momentum (-1 to +1)."""
        rsi = index_data['rsi']
        price_change_20d = index_data['price_change_20d']
        volume_ratio = index_data['volume_ratio']
        
        # RSI contribution (-1 to +1)
        rsi_momentum = (rsi - 50) / 50  # -1 at 0, +1 at 100
        
        # Price change contribution (-1 to +1)
        price_momentum = max(-1, min(1, price_change_20d / 20))
        
        # Volume contribution
        volume_momentum = max(-1, min(1, (volume_ratio - 1) / 2))
        
        momentum = (rsi_momentum * 0.5 + price_momentum * 0.35 + volume_momentum * 0.15)
        return float(momentum)
    
    def _calculate_sentiment_strength(self, index_data: Dict[str, Any]) -> float:
        """Calculate sentiment strength (-1 to +1)."""
        close = index_data['close']
        ema50 = index_data['ema50']
        ema200 = index_data['ema200']
        rsi = index_data['rsi']
        
        # Distance from EMA50
        distance_from_ema50 = (close - ema50) / ema50
        
        # EMA slope
        ema_slope = index_data['ema_slope']
        
        # RSI extreme
        rsi_strength = abs(rsi - 50) / 50
        
        strength = (
            distance_from_ema50 * 0.3 +
            (ema_slope / 10) * 0.4 +  # Normalize slope
            (1 if rsi > 65 or rsi < 35 else 0.5) * 0.3
        )
        
        return float(max(-1, min(1, strength)))
    
    def _determine_sentiment(self, trend: str, momentum: float, strength: float) -> str:
        """Determine overall market sentiment."""
        if trend == 'UPTREND' and momentum > 0.2:
            return 'STRONGLY_BULLISH'
        elif trend == 'UPTREND' and momentum > -0.2:
            return 'BULLISH'
        elif trend == 'DOWNTREND' and momentum < -0.2:
            return 'STRONGLY_BEARISH'
        elif trend == 'DOWNTREND' and momentum < 0.2:
            return 'BEARISH'
        else:
            return 'NEUTRAL'
    
    def _analyze_sector_trends(self) -> Dict[str, str]:
        """Analyze trend for major sectors."""
        sector_trends = {}
        
        for sector, stocks in self.SECTORS.items():
            try:
                sector_performances = []
                
                for stock in stocks[:3]:  # Check first 3 stocks per sector
                    try:
                        df = self.data_fetcher.fetch_data(stock, period='1mo', interval='1d')
                        if df is not None and len(df) > 0:
                            change = ((df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100)
                            sector_performances.append(change)
                    except:
                        continue
                
                if sector_performances:
                    avg_change = sum(sector_performances) / len(sector_performances)
                    if avg_change > 2:
                        sector_trends[sector] = 'STRONG'
                    elif avg_change > 0:
                        sector_trends[sector] = 'POSITIVE'
                    elif avg_change > -2:
                        sector_trends[sector] = 'NEGATIVE'
                    else:
                        sector_trends[sector] = 'WEAK'
            except Exception as e:
                logger.debug(f"Error analyzing sector {sector}: {e}")
                sector_trends[sector] = 'UNKNOWN'
        
        return sector_trends
    
    def identify_running_stocks(self, stocks: List[str], lookback: int = 5) -> List[Dict[str, Any]]:
        """
        Identify stocks running up with momentum.
        Lookback: number of days to check
        """
        running_stocks = []
        
        for symbol in stocks:
            try:
                df = self.data_fetcher.fetch_data(symbol, period='1mo', interval='1d')
                
                if df is None or len(df) < lookback:
                    continue
                
                close = df['close'].iloc[-1]
                prev_close = df['close'].iloc[-lookback]
                volume = df['volume'].iloc[-1]
                volume_ma = df['volume'].tail(20).mean()
                
                # Calculate momentum
                price_change = ((close - prev_close) / prev_close) * 100
                volume_ratio = (volume / volume_ma) if volume_ma > 0 else 1.0
                
                # Identify running stocks (up > 1% with volume)
                if price_change > 1.0 and volume_ratio > 1.2:
                    ema20 = df['close'].ewm(span=20).mean().iloc[-1]
                    ema50 = df['close'].ewm(span=50).mean().iloc[-1]
                    rsi = self._calculate_rsi(df, 14)
                    
                    running_stocks.append({
                        'symbol': symbol,
                        'price': close,
                        'change': price_change,
                        'volume_ratio': volume_ratio,
                        'ema20': ema20,
                        'ema50': ema50,
                        'rsi': rsi,
                        'momentum_score': price_change * volume_ratio  # Simple momentum score
                    })
            except Exception as e:
                logger.debug(f"Error analyzing {symbol}: {e}")
        
        # Sort by momentum score
        running_stocks.sort(key=lambda x: x['momentum_score'], reverse=True)
        self.running_stocks = running_stocks
        
        return running_stocks
    
    def validate_breakout_with_ai(self, symbol: str, stock_data: Dict[str, Any]) -> Tuple[bool, str, float]:
        """
        Use AI to validate if a stock breakout is strong and worth alerting.
        Returns: (is_valid, reason, confidence)
        """
        if not self.ai_analyzer:
            logger.warning("No AI analyzer available for breakout validation")
            return False, "No AI analyzer", 0.0
        
        try:
            # Prepare context
            market_context = f"""
Market Sentiment: {self.current_sentiment}
NIFTY Trend: {self.nifty_trend}
Market Momentum: {self.market_momentum:.2f}
Sector Trend: {self.sector_trends.get('IT', 'UNKNOWN')}
"""
            
            # Create analysis prompt
            prompt = f"""
Validate this stock breakout in current market conditions:

Stock: {symbol}
Current Price: ₹{stock_data.get('price', 0)}
RSI: {stock_data.get('rsi', 0):.1f}
Volume Ratio: {stock_data.get('volume_ratio', 0):.2f}x
EMA 20: ₹{stock_data.get('ema20', 0)}
EMA 50: ₹{stock_data.get('ema50', 0)}
Price Change (5d): {stock_data.get('price_change', 0):.2f}%

Market Context:
{market_context}

Is this a valid breakout to alert on? Consider:
1. Market sentiment alignment
2. Volume confirmation
3. Technical structure
4. Risk/reward potential

Respond with: YES/NO | Confidence (1-10) | Reason (one line)
"""
            
            # Get AI analysis
            response = self.ai_analyzer.analyze_generic(symbol, prompt)
            
            if response:
                lines = response.strip().split('\n')
                first_line = lines[0] if lines else ""
                
                if '|' in first_line:
                    parts = first_line.split('|')
                    is_valid = 'YES' in parts[0].upper()
                    
                    confidence = 5.0
                    try:
                        conf_str = parts[1].strip() if len(parts) > 1 else "5"
                        confidence = float(conf_str.split('/')[0].strip())
                    except:
                        pass
                    
                    reason = parts[2].strip() if len(parts) > 2 else "AI validation"
                    
                    return is_valid, reason, confidence / 10.0
            
            return False, "Could not get AI response", 0.0
            
        except Exception as e:
            logger.error(f"Error validating breakout with AI: {e}")
            return False, f"AI validation error: {str(e)}", 0.0
    
    def get_sentiment_summary(self) -> Dict[str, Any]:
        """Get current sentiment summary."""
        return {
            'sentiment': self.current_sentiment,
            'sentiment_strength': self.sentiment_strength,
            'nifty_trend': self.nifty_trend,
            'market_momentum': self.market_momentum,
            'volatility': self.volatility,
            'sector_trends': self.sector_trends,
            'running_stocks_count': len(self.running_stocks),
            'timestamp': datetime.now(self.ist).isoformat()
        }
    
    def _get_cached_sentiment(self) -> Dict[str, Any]:
        """Return cached sentiment data."""
        return {
            'sentiment': self.current_sentiment,
            'sentiment_strength': self.sentiment_strength,
            'nifty_trend': self.nifty_trend,
            'market_momentum': self.market_momentum,
            'volatility': self.volatility,
            'sector_trends': self.sector_trends,
            'running_stocks_count': len(self.running_stocks),
            'timestamp': self.last_update or 'unknown'
        }
    
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
    
    def generate_sentiment_alert(self) -> Optional[str]:
        """Generate market sentiment alert if significant change."""
        try:
            if self.current_sentiment in ['STRONGLY_BULLISH', 'STRONGLY_BEARISH']:
                return f"""
🎯 MARKET SENTIMENT ALERT
━━━━━━━━━━━━━━━━━━━━━
Sentiment: {self.current_sentiment}
NIFTY Trend: {self.nifty_trend}
Momentum: {self.market_momentum:.2f} ({'+Strong' if self.market_momentum > 0.3 else 'Weak' if self.market_momentum < -0.3 else 'Neutral'})
Volatility: {self.volatility:.2f}%

Top Sectors:
{self._format_sector_summary()}

⏰ {datetime.now(self.ist).strftime('%H:%M IST')}
"""
        except Exception as e:
            logger.error(f"Error generating sentiment alert: {e}")
        
        return None
    
    def _format_sector_summary(self) -> str:
        """Format sector summary for alerts."""
        strong_sectors = [s for s, t in self.sector_trends.items() if t in ['STRONG', 'POSITIVE']]
        weak_sectors = [s for s, t in self.sector_trends.items() if t in ['WEAK', 'NEGATIVE']]
        
        summary = ""
        if strong_sectors:
            summary += f"✅ Strong: {', '.join(strong_sectors[:3])}\n"
        if weak_sectors:
            summary += f"❌ Weak: {', '.join(weak_sectors[:3])}"
        
        return summary if summary else "Neutral across sectors"


def create_market_sentiment_analyzer(data_fetcher=None, ai_analyzer=None) -> MarketSentimentAnalyzer:
    """Factory function to create sentiment analyzer."""
    return MarketSentimentAnalyzer(data_fetcher=data_fetcher, ai_analyzer=ai_analyzer)
