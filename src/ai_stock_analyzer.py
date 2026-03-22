"""
AI Stock Analyzer - Uses LLM to analyze stock trends and generate recommendations.
"""

import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


# System prompt for stock analysis
SYSTEM_PROMPT = """You are an expert Indian stock market analyst with deep knowledge of:
- Technical analysis (EMA, RSI, MACD, Volume, Support/Resistance)
- Price action trading
- Market sentiment analysis
- Risk management and position sizing

You analyze NSE (National Stock Exchange of India) stocks and provide:
1. A clear BUY/SELL/HOLD recommendation
2. Entry price zone
3. Stop loss level
4. Target prices
5. A detailed reasoning for your recommendation
6. Risk assessment

Always consider:
- Current market trend (bullish/bearish/sideways)
- Key support and resistance levels
- Volume patterns
- Technical indicator signals
- Risk-reward ratio (minimum 1:2 for buy recommendations)

Respond in a structured format that can be easily parsed."""


# User prompt template for stock analysis
STOCK_ANALYSIS_PROMPT = """Analyze the following NSE stock:

**Stock Symbol:** {symbol}

**Current Price Data:**
- Current Price: ₹{current_price}
- Open: ₹{open_price}
- High: ₹{high_price}
- Low: ₹{low_price}
- Volume: {volume:,}

**Technical Indicators:**
- EMA 20: ₹{ema20}
- EMA 50: ₹{ema50}
- EMA 100: ₹{ema100}
- EMA 200: ₹{ema200}
- RSI (14): {rsi}
- ATR (14): ₹{atr}

**Volume Analysis:**
- Current Volume: {volume:,}
- Volume MA 30: {volume_ma30}
- Volume Ratio: {volume_ratio}x

**Moving Averages Alignment:**
- EMA Alignment Score: {ema_alignment_score}/4
- Trend: {trend_direction}

**Recent Price Action (Last 5 days):**
{recent_candles}

**Market Context:**
- Nifty 50 Trend: {nifty_trend}
- Sector Performance: {sector_performance}

Based on the above data, provide your analysis in the following format:

```
RECOMMENDATION: [BUY/SELL/HOLD]
CONFIDENCE: [1-10]

ENTRY ZONE: ₹{entry_min:.2f} - ₹{entry_max:.2f}
STOP LOSS: ₹{stop_loss:.2f} ({stop_loss_pct:.1f}%)
TARGET 1: ₹{target1:.2f} ({target1_pct:.1f}%)
TARGET 2: ₹{target2:.2f} ({target2_pct:.1f}%)

REASONING:
[Detailed reasoning for the recommendation]

RISK ASSESSMENT:
[Low/Medium/High - based on volatility, position size recommendation]
```

Be concise but thorough in your reasoning. Consider the risk-reward ratio before making any BUY recommendation."""


# Quick analysis prompt for simple queries
QUICK_ANALYSIS_PROMPT = """You are a stock market analyst. Based on the following brief technical data for NSE stock {symbol}:

- Price: ₹{price}
- EMA 20: ₹{ema20}, EMA 50: ₹{ema50}, EMA 100: ₹{ema100}, EMA 200: ₹{ema200}
- Volume Ratio: {vol_ratio}x
- RSI: {rsi}

Provide a brief BUY/SELL/HOLD recommendation with 1-line reasoning. Format:
```
RECOMMENDATION: [BUY/SELL/HOLD]
REASON: [One line reasoning]
```"""


class AIStockAnalyzer:
    """AI-powered stock analyzer using LLM."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize the AI stock analyzer.
        
        Args:
            api_key: OpenAI API key (defaults to env var)
            model: Model to use for analysis
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.client = None
        
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                logger.info(f"AI Analyzer initialized with model: {model}")
            except ImportError:
                logger.warning("OpenAI package not installed")
        else:
            logger.warning("No OpenAI API key provided")
    
    def is_available(self) -> bool:
        """Check if AI analyzer is available."""
        return self.client is not None
    
    def analyze_stock(self, symbol: str, market_data: Dict[str, Any]) -> str:
        """
        Analyze a stock and return recommendation.
        
        Args:
            symbol: Stock symbol (e.g., "RELIANCE")
            market_data: Dictionary containing all market data
            
        Returns:
            Formatted analysis string
        """
        if not self.is_available():
            return "❌ AI Analysis unavailable. Please configure OPENAI_API_KEY."
        
        try:
            # Prepare the prompt with market data
            prompt = self._prepare_analysis_prompt(symbol, market_data)
            
            # Call the LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error analyzing stock {symbol}: {e}")
            return f"❌ Error analyzing stock: {str(e)}"
    
    def quick_analyze(self, symbol: str, price: float, ema20: float, ema50: float, 
                      ema100: float, ema200: float, vol_ratio: float, rsi: float) -> str:
        """
        Quick analysis with minimal data.
        
        Args:
            symbol: Stock symbol
            price: Current price
            ema20-ema200: EMA values
            vol_ratio: Volume ratio
            rsi: RSI value
            
        Returns:
            Quick recommendation
        """
        if not self.is_available():
            return "❌ AI Analysis unavailable. Please configure OPENAI_API_KEY."
        
        try:
            prompt = QUICK_ANALYSIS_PROMPT.format(
                symbol=symbol,
                price=price,
                ema20=ema20,
                ema50=ema50,
                ema100=ema100,
                ema200=ema200,
                vol_ratio=vol_ratio,
                rsi=rsi
            )
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a concise stock market analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error in quick analysis for {symbol}: {e}")
            return f"❌ Error: {str(e)}"
    
    def _prepare_analysis_prompt(self, symbol: str, data: Dict[str, Any]) -> str:
        """Prepare the full analysis prompt with market data."""
        
        # Format recent candles
        recent_candles = ""
        if 'recent_candles' in data:
            for i, candle in enumerate(data['recent_candles'][-5:]):
                recent_candles += f"- Day {i+1}: O:{candle.get('open', 'N/A')} H:{candle.get('high', 'N/A')} L:{candle.get('low', 'N/A')} C:{candle.get('close', 'N/A')} V:{candle.get('volume', 0):,}\n"
        
        # Calculate entry/stop/target defaults
        current_price = data.get('current_price', 0)
        ema50 = data.get('ema50', current_price)
        
        entry_min = current_price
        entry_max = current_price * 1.005
        stop_loss = min(ema50, current_price * 0.98)
        
        risk = entry_min - stop_loss
        target1 = entry_min + (risk * 2)
        target2 = entry_min + (risk * 3)
        
        stop_loss_pct = ((stop_loss / current_price) - 1) * 100 if current_price > 0 else 0
        target1_pct = ((target1 / current_price) - 1) * 100 if current_price > 0 else 0
        target2_pct = ((target2 / current_price) - 1) * 100 if current_price > 0 else 0
        
        return STOCK_ANALYSIS_PROMPT.format(
            symbol=symbol,
            current_price=current_price,
            open_price=data.get('open', 'N/A'),
            high_price=data.get('high', 'N/A'),
            low_price=data.get('low', 'N/A'),
            volume=data.get('volume', 0),
            ema20=data.get('ema20', 'N/A'),
            ema50=data.get('ema50', 'N/A'),
            ema100=data.get('ema100', 'N/A'),
            ema200=data.get('ema200', 'N/A'),
            rsi=data.get('rsi', 'N/A'),
            atr=data.get('atr', 'N/A'),
            volume_ma30=data.get('volume_ma30', 'N/A'),
            volume_ratio=data.get('volume_ratio', 'N/A'),
            ema_alignment_score=data.get('ema_alignment_score', 0),
            trend_direction=data.get('trend_direction', 'Unknown'),
            recent_candles=recent_candles or "No recent data available",
            nifty_trend=data.get('nifty_trend', 'Unknown'),
            sector_performance=data.get('sector_performance', 'Unknown'),
            entry_min=entry_min,
            entry_max=entry_max,
            stop_loss=stop_loss,
            stop_loss_pct=stop_loss_pct,
            target1=target1,
            target1_pct=target1_pct,
            target2=target2,
            target2_pct=target2_pct
        )


def create_analyzer() -> AIStockAnalyzer:
    """Factory function to create AI analyzer."""
    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    return AIStockAnalyzer(api_key=api_key, model=model)
