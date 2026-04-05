"""
AI Stock Analyzer - Multi-Provider LLM Support
Automatically falls back to alternate providers if one is unavailable or quota-exhausted.
"""

import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod

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


class BaseLLMProvider(ABC):
    """Base class for LLM providers."""
    
    def __init__(self, name: str):
        self.name = name
        self.client = None
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available."""
        pass
    
    @abstractmethod
    def generate(self, messages: List[Dict], **kwargs) -> str:
        """Generate a response."""
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider."""
    
    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini"):
        super().__init__("OpenAI")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.client = None
        self._init_client()
    
    def _init_client(self):
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("OpenAI package not installed")
    
    def is_available(self) -> bool:
        return self.client is not None and bool(self.api_key)
    
    def generate(self, messages: List[Dict], **kwargs) -> str:
        if not self.is_available():
            raise Exception("OpenAI not available")
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 1000)
        )
        return response.choices[0].message.content


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider."""
    
    def __init__(self, api_key: str = None, model: str = "claude-3-haiku-20240307"):
        super().__init__("Anthropic")
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self.client = None
        self._init_client()
    
    def _init_client(self):
        if self.api_key:
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=self.api_key)
            except ImportError:
                logger.warning("Anthropic package not installed")
    
    def is_available(self) -> bool:
        return self.client is not None and bool(self.api_key)
    
    def generate(self, messages: List[Dict], **kwargs) -> str:
        if not self.is_available():
            raise Exception("Anthropic not available")
        
        # Convert messages format
        system = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=kwargs.get("max_tokens", 1000),
            system=system,
            messages=user_messages
        )
        return response.content[0].text


class GoogleGeminiProvider(BaseLLMProvider):
    """Google Gemini provider."""
    
    def __init__(self, api_key: str = None, model: str = "gemini-1.5-flash"):
        super().__init__("Google Gemini")
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self.model = model
        self.client = None
        self._init_client()
    
    def _init_client(self):
        if self.api_key:
            try:
                from google.genai import Client
                self.client = Client(api_key=self.api_key)
            except ImportError:
                logger.warning("Google GenAI package not installed")
    
    def is_available(self) -> bool:
        return self.client is not None and bool(self.api_key)
    
    def generate(self, messages: List[Dict], **kwargs) -> str:
        if not self.is_available():
            raise Exception("Google Gemini not available")
        
        # Convert messages format
        prompt = ""
        for msg in messages:
            if msg["role"] == "system":
                prompt = msg["content"] + "\n\n"
            else:
                prompt += msg["content"]
        
        response = self.client.models.generate(
            model=self.model,
            contents=prompt,
            config={
                'temperature': kwargs.get("temperature", 0.7),
                'max_output_tokens': kwargs.get("max_tokens", 1000)
            }
        )
        return response.text


class GroqProvider(BaseLLMProvider):
    """Groq provider (fast inference, free tier available)."""
    
    def __init__(self, api_key: str = None, model: str = "llama-3.1-70b-versatile"):
        super().__init__("Groq")
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model
        self.client = None
        self._init_client()
    
    def _init_client(self):
        if self.api_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
            except ImportError:
                logger.warning("Groq package not installed")
    
    def is_available(self) -> bool:
        return self.client is not None and bool(self.api_key)
    
    def generate(self, messages: List[Dict], **kwargs) -> str:
        if not self.is_available():
            raise Exception("Groq not available")
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 1000)
        )
        return response.choices[0].message.content


class MultiProviderAIAnalyzer:
    """
    Multi-provider AI analyzer with automatic fallback.
    Tries providers in order until one succeeds.
    """
    
    def __init__(self):
        self.providers: List[BaseLLMProvider] = []
        self._init_providers()
    
    def _init_providers(self):
        """Initialize all available providers."""
        # Initialize providers based on available API keys
        
        # OpenAI (default)
        openai_key = os.environ.get("OPENAI_API_KEY")
        openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        if openai_key:
            self.providers.append(OpenAIProvider(openai_key, openai_model))
            logger.info("OpenAI provider initialized")
        
        # Groq (free tier available)
        groq_key = os.environ.get("GROQ_API_KEY")
        groq_model = os.environ.get("GROQ_MODEL", "llama-3.1-70b-versatile")
        if groq_key:
            self.providers.append(GroqProvider(groq_key, groq_model))
            logger.info("Groq provider initialized")
        
        # Anthropic
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        anthropic_model = os.environ.get("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
        if anthropic_key:
            self.providers.append(AnthropicProvider(anthropic_key, anthropic_model))
            logger.info("Anthropic provider initialized")
        
        # Google Gemini
        google_key = os.environ.get("GOOGLE_API_KEY")
        google_model = os.environ.get("GOOGLE_MODEL", "gemini-1.5-flash")
        if google_key:
            self.providers.append(GoogleGeminiProvider(google_key, google_model))
            logger.info("Google Gemini provider initialized")
        
        logger.info(f"Initialized {len(self.providers)} AI providers")
    
    def is_available(self) -> bool:
        """Check if any provider is available."""
        return len(self.providers) > 0
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider names."""
        return [p.name for p in self.providers if p.is_available()]
    
    def analyze_stock(self, symbol: str, market_data: Dict[str, Any]) -> str:
        """
        Analyze a stock using available providers.
        Automatically falls back if one provider fails.
        """
        if not self.is_available():
            return "❌ No AI providers available. Please configure at least one API key."
        
        # Prepare the prompt
        prompt = self._prepare_analysis_prompt(symbol, market_data)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        # Try each provider in order
        errors = []
        for provider in self.providers:
            try:
                if provider.is_available():
                    logger.info(f"Trying {provider.name} for analysis...")
                    result = provider.generate(messages)
                    logger.info(f"Successfully used {provider.name}")
                    return result
            except Exception as e:
                error_msg = f"{provider.name}: {str(e)}"
                errors.append(error_msg)
                logger.warning(f"{provider.name} failed: {e}")
                continue
        
        # All providers failed - sanitize error message for user safety
        return "❌ All AI providers failed. Please check your API keys and quotas."
    
    def quick_analyze(self, symbol: str, price: float, ema20: float, ema50: float,
                      ema100: float, ema200: float, vol_ratio: float, rsi: float) -> str:
        """Quick analysis with minimal data."""
        if not self.is_available():
            return "❌ No AI providers available. Please configure at least one API key."
        
        prompt = QUICK_ANALYSIS_PROMPT.format(
            symbol=symbol, price=price, ema20=ema20, ema50=ema50,
            ema100=ema100, ema200=ema200, vol_ratio=vol_ratio, rsi=rsi
        )
        
        messages = [
            {"role": "system", "content": "You are a concise stock market analyst."},
            {"role": "user", "content": prompt}
        ]
        
        # Try each provider
        for provider in self.providers:
            try:
                if provider.is_available():
                    return provider.generate(messages, max_tokens=200)
            except Exception as e:
                logger.warning(f"{provider.name} failed: {e}")
                continue
        
        return "❌ All AI providers failed"
    
    def _prepare_analysis_prompt(self, symbol: str, data: Dict[str, Any]) -> str:
        """Prepare the full analysis prompt with market data."""
        
        recent_candles = ""
        if 'recent_candles' in data:
            for i, candle in enumerate(data['recent_candles'][-5:]):
                recent_candles += f"- Day {i+1}: O:{candle.get('open', 'N/A')} H:{candle.get('high', 'N/A')} L:{candle.get('low', 'N/A')} C:{candle.get('close', 'N/A')} V:{candle.get('volume', 0):,}\n"
        
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


# Backward compatibility - keep the old class name
AIStockAnalyzer = MultiProviderAIAnalyzer


def create_analyzer() -> MultiProviderAIAnalyzer:
    """Factory function to create the multi-provider AI analyzer."""
    return MultiProviderAIAnalyzer()
