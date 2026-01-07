"""
ExaSignal - Market Matcher
Encontra mercados Polymarket relevantes baseado em keywords de notícias.

Flow: News headline → Extract keywords → Search markets → Return matches
"""
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.utils.logger import logger


# Common words to ignore when extracting keywords
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "must", "shall", "can", "need", "dare", "ought", "used",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as", "into",
    "through", "during", "before", "after", "above", "below", "between",
    "and", "but", "or", "nor", "so", "yet", "both", "either", "neither",
    "not", "only", "own", "same", "than", "too", "very", "just", "also",
    "now", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "new", "says", "said", "according", "report", "reports", "reuters",
    "bloomberg", "source", "sources", "breaking", "update", "latest",
}

# High-value keywords for prediction markets
PRIORITY_KEYWORDS = {
    # Politics - US
    "trump", "biden", "president", "election", "congress", "senate",
    "republican", "democrat", "vote", "impeach", "resign",
    # Politics - World Leaders
    "maduro", "venezuela", "putin", "russia", "zelensky", "ukraine",
    "netanyahu", "israel", "gaza", "hamas", "china", "xi", "jinping",
    "kim", "korea", "iran", "khamenei", "bolsonaro", "brazil",
    # Crypto
    "bitcoin", "ethereum", "crypto", "btc", "eth", "sec", "etf", "solana",
    # Tech
    "openai", "gpt", "ai", "agi", "tesla", "musk", "spacex", "apple", "google",
    "microsoft", "meta", "amazon", "nvidia", "anthropic", "claude",
    # Finance
    "fed", "interest", "rate", "inflation", "recession", "gdp", "stock",
    # Events
    "war", "peace", "invasion", "sanctions", "earthquake", "hurricane",
}


@dataclass
class MarketMatch:
    """A matched market with relevance score."""
    market_id: str
    market_name: str
    slug: str
    relevance_score: float  # 0-1
    matched_keywords: List[str]
    category: str
    
    def to_dict(self) -> dict:
        return {
            "id": self.market_id,
            "name": self.market_name,
            "slug": self.slug,
            "relevance": round(self.relevance_score, 2),
            "matched_keywords": self.matched_keywords,
            "category": self.category,
        }


class MarketMatcher:
    """
    Matches news to relevant prediction markets.
    
    Uses keyword extraction and fuzzy matching.
    """
    
    def __init__(self, search_func=None):
        """
        Args:
            search_func: Async function to search markets. 
                        Should accept (query: str, limit: int) and return markets list.
        """
        self.search_func = search_func
        self._market_cache: List[Dict] = []
        self._cache_time: Optional[float] = None
    
    def extract_keywords(self, text: str, min_length: int = 3) -> List[str]:
        """
        Extract meaningful keywords from text.
        
        Priority keywords get boosted.
        """
        # Clean and tokenize
        text_lower = text.lower()
        words = re.findall(r'\b[a-zA-Z]+\b', text_lower)
        
        keywords = []
        seen = set()
        
        for word in words:
            if len(word) < min_length:
                continue
            if word in STOP_WORDS:
                continue
            if word in seen:
                continue
            
            seen.add(word)
            
            # Boost priority keywords
            if word in PRIORITY_KEYWORDS:
                keywords.insert(0, word)  # Add to front
            else:
                keywords.append(word)
        
        return keywords[:10]  # Max 10 keywords
    
    def calculate_relevance(
        self, 
        market: Dict[str, Any], 
        keywords: List[str]
    ) -> tuple[float, List[str]]:
        """
        Calculate relevance score between market and keywords.
        
        Returns: (score 0-1, matched_keywords)
        """
        market_text = (
            (market.get("name", "") or market.get("title", "") or market.get("question", "")) + " " +
            (market.get("description", "") or "")
        ).lower()
        
        matched = []
        priority_matches = 0
        
        for kw in keywords:
            if kw in market_text:
                matched.append(kw)
                if kw in PRIORITY_KEYWORDS:
                    priority_matches += 1
        
        if not matched:
            return 0.0, []
        
        # Score: base matches + priority boost
        base_score = len(matched) / len(keywords)
        priority_boost = min(priority_matches * 0.1, 0.3)
        
        score = min(base_score + priority_boost, 1.0)
        
        return score, matched
    
    async def find_markets(
        self,
        news_text: str,
        limit: int = 5,
        min_relevance: float = 0.1  # Lower threshold to catch more matches
    ) -> List[MarketMatch]:
        """
        Find markets relevant to a news headline.
        
        Args:
            news_text: News headline or text
            limit: Max markets to return
            min_relevance: Minimum relevance score (0-1)
        
        Returns:
            List of MarketMatch sorted by relevance
        """
        if not self.search_func:
            logger.warning("market_matcher_no_search", 
                          msg="No search function configured")
            return []
        
        # Extract keywords
        keywords = self.extract_keywords(news_text)
        
        if not keywords:
            logger.debug("no_keywords_extracted", text=news_text[:50])
            return []
        
        logger.info("matching_keywords", keywords=keywords[:5])
        
        # Search markets using top keywords
        search_query = " ".join(keywords[:3])  # Use top 3 keywords
        
        try:
            markets = await self.search_func(search_query, limit=50)
        except Exception as e:
            logger.error("market_search_error", error=str(e))
            return []
        
        # Score and filter markets
        matches = []
        for market in markets:
            score, matched_kw = self.calculate_relevance(market, keywords)
            
            if score >= min_relevance:
                matches.append(MarketMatch(
                    market_id=market.get("id", market.get("slug", "")),
                    market_name=(market.get("name") or market.get("title") or 
                                market.get("question", "Unknown")),
                    slug=market.get("slug", ""),
                    relevance_score=score,
                    matched_keywords=matched_kw,
                    category=market.get("category", "Other")
                ))
        
        # Sort by relevance
        matches.sort(key=lambda m: m.relevance_score, reverse=True)
        
        logger.info("markets_matched", 
                   total=len(matches), 
                   query=search_query)
        
        return matches[:limit]
    
    async def find_best_market(self, news_text: str) -> Optional[MarketMatch]:
        """Find single best matching market for news."""
        matches = await self.find_markets(news_text, limit=1)
        return matches[0] if matches else None
