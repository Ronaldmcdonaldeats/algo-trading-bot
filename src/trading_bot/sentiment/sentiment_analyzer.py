"""Sentiment Analysis - NLP-based financial news sentiment for trading signals

Analyzes sentiment from financial news articles and generates trading signals:
- TextBlob-based polarity scoring
- Keyword extraction and weighting
- Multi-source sentiment aggregation
- Signal generation (bullish/bearish/neutral)
- Sentiment history tracking
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# Sentiment keywords
BULLISH_KEYWORDS = {
    'bullish': 2.0, 'buy': 1.5, 'surge': 1.8, 'soar': 1.8,
    'strong': 1.5, 'beat': 1.6, 'growth': 1.5, 'profit': 1.4,
    'upside': 1.6, 'momentum': 1.5, 'break_out': 1.7, 'outperform': 1.6,
    'positive': 1.4, 'rise': 1.3, 'improve': 1.3, 'upgrade': 1.6
}

BEARISH_KEYWORDS = {
    'bearish': -2.0, 'sell': -1.5, 'crash': -1.8, 'plunge': -1.8,
    'weak': -1.5, 'miss': -1.6, 'decline': -1.5, 'loss': -1.4,
    'downside': -1.6, 'downtrend': -1.6, 'break_down': -1.7, 'underperform': -1.6,
    'negative': -1.4, 'fall': -1.3, 'worsen': -1.3, 'downgrade': -1.6
}


@dataclass
class SentimentScore:
    """Sentiment score for a symbol"""
    symbol: str
    polarity: float  # -1 to 1
    subjectivity: float  # 0 to 1 (0=objective, 1=subjective)
    keyword_score: float  # From keywords
    sources_count: int
    signal: str  # "STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"
    confidence: float  # 0 to 1
    timestamp: datetime


class SentimentAnalyzer:
    """Analyze market sentiment for trading signals"""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.sentiment_history: Dict[str, List[SentimentScore]] = defaultdict(list)
        
    def analyze_article(self, text: str, symbol: str) -> Tuple[float, float]:
        """Analyze sentiment of article text
        
        Returns:
            (polarity, subjectivity) where polarity is -1 to 1
        """
        
        # Simple sentiment analysis based on keywords
        text_lower = text.lower()
        
        polarity = 0.0
        keyword_matches = 0
        
        # Check bullish keywords
        for keyword, score in BULLISH_KEYWORDS.items():
            if keyword.replace('_', ' ') in text_lower:
                polarity += score
                keyword_matches += 1
        
        # Check bearish keywords
        for keyword, score in BEARISH_KEYWORDS.items():
            if keyword.replace('_', ' ') in text_lower:
                polarity += score
                keyword_matches += 1
        
        # Normalize polarity
        if keyword_matches > 0:
            polarity = polarity / (keyword_matches * 2.0)  # Normalize to -1 to 1
        
        polarity = max(-1.0, min(1.0, polarity))
        
        # Subjectivity based on subjective indicators
        subjective_words = ['think', 'believe', 'opinion', 'feel', 'seems', 'appears']
        subjectivity = sum(1 for word in subjective_words if word in text_lower) / 10.0
        subjectivity = max(0.0, min(1.0, subjectivity))
        
        return polarity, subjectivity
    
    def aggregate_sentiment(self, symbol: str, articles: List[Tuple[str, str]]) -> SentimentScore:
        """Aggregate sentiment from multiple articles
        
        Args:
            symbol: Stock symbol
            articles: List of (title, text) tuples
        """
        
        if not articles:
            return SentimentScore(symbol, 0.0, 0.0, 0.0, 0, "NEUTRAL", 0.0, datetime.now())
        
        polarities = []
        subjectivities = []
        
        for title, text in articles:
            # Combine title and text
            combined = f"{title} {text}"
            polarity, subjectivity = self.analyze_article(combined, symbol)
            polarities.append(polarity)
            subjectivities.append(subjectivity)
        
        avg_polarity = sum(polarities) / len(polarities)
        avg_subjectivity = sum(subjectivities) / len(subjectivities)
        
        # Generate trading signal
        signal, confidence = self._polarity_to_signal(avg_polarity, avg_subjectivity, len(articles))
        
        sentiment = SentimentScore(
            symbol=symbol,
            polarity=avg_polarity,
            subjectivity=avg_subjectivity,
            keyword_score=avg_polarity,
            sources_count=len(articles),
            signal=signal,
            confidence=confidence,
            timestamp=datetime.now()
        )
        
        # Store in history
        self.sentiment_history[symbol].append(sentiment)
        
        return sentiment
    
    def _polarity_to_signal(self, polarity: float, subjectivity: float, 
                           source_count: int) -> Tuple[str, float]:
        """Convert polarity score to trading signal
        
        Returns:
            (signal, confidence)
        """
        
        # Adjust confidence based on subjectivity and source count
        confidence = 0.5 + (0.5 * (1.0 - subjectivity))  # Lower subjectivity = higher confidence
        confidence = confidence * (1.0 + min(source_count - 1, 5) / 10.0)  # More sources = higher confidence
        confidence = min(confidence, 1.0)
        
        if polarity > 0.5:
            return "STRONG_BUY", confidence
        elif polarity > 0.1:
            return "BUY", confidence * 0.8
        elif polarity < -0.5:
            return "STRONG_SELL", confidence
        elif polarity < -0.1:
            return "SELL", confidence * 0.8
        else:
            return "NEUTRAL", 0.0
    
    def get_trending_symbols(self, top_n: int = 10, 
                            min_confidence: float = 0.6) -> List[Tuple[str, str]]:
        """Get most bullish symbols by sentiment
        
        Returns:
            List of (symbol, signal) tuples
        """
        
        symbols_by_sentiment = []
        
        for symbol, scores in self.sentiment_history.items():
            if not scores:
                continue
            
            latest = scores[-1]
            if latest.confidence >= min_confidence:
                symbols_by_sentiment.append((symbol, latest.signal, latest.polarity))
        
        # Sort by polarity
        symbols_by_sentiment.sort(key=lambda x: x[2], reverse=True)
        
        return [(s[0], s[1]) for s in symbols_by_sentiment[:top_n]]
    
    def get_sentiment_for_symbol(self, symbol: str) -> Optional[SentimentScore]:
        """Get latest sentiment for symbol"""
        
        if symbol in self.sentiment_history and self.sentiment_history[symbol]:
            return self.sentiment_history[symbol][-1]
        
        return None
    
    def sentiment_momentum(self, symbol: str, lookback: int = 5) -> float:
        """Get sentiment momentum (is sentiment improving?)
        
        Returns:
            Value from -1 to 1 (negative = worsening, positive = improving)
        """
        
        scores = self.sentiment_history.get(symbol, [])
        
        if len(scores) < 2:
            return 0.0
        
        recent = scores[-lookback:] if len(scores) >= lookback else scores
        
        if len(recent) < 2:
            return 0.0
        
        older_polarity = recent[0].polarity
        newer_polarity = recent[-1].polarity
        
        momentum = newer_polarity - older_polarity
        return max(-1.0, min(1.0, momentum))
    
    def save_sentiment_history(self, filename: str = "sentiment_history.json"):
        """Save sentiment analysis to JSON"""
        
        filepath = self.cache_dir / filename
        
        data = {}
        for symbol, scores in self.sentiment_history.items():
            data[symbol] = [
                {
                    'polarity': s.polarity,
                    'subjectivity': s.subjectivity,
                    'signal': s.signal,
                    'confidence': s.confidence,
                    'sources': s.sources_count,
                    'timestamp': s.timestamp.isoformat()
                }
                for s in scores
            ]
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Sentiment history saved to {filepath}")
        return str(filepath)
