"""
ExaSignal - Finnhub Client
Real-time news + Twitter sentiment for trading signals.

Finnhub API: https://finnhub.io/docs/api
- News feed em tempo real
- Twitter sentiment
- Company news por símbolo
"""
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import httpx
from dotenv import load_dotenv

load_dotenv()

from src.utils.logger import logger

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
FINNHUB_AVAILABLE = bool(FINNHUB_API_KEY)


class FinnhubClient:
    """
    Cliente para Finnhub API.
    
    Features:
    - General news (real-time)
    - Company news
    - Market news by category
    - Twitter sentiment (social)
    """
    
    BASE_URL = "https://finnhub.io/api/v1"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or FINNHUB_API_KEY
        self.is_available = bool(self.api_key)
        
        if not self.is_available:
            logger.warning("finnhub_no_key", 
                          hint="Add FINNHUB_API_KEY to .env for real-time news")
    
    async def _request(self, endpoint: str, params: dict = None) -> Any:
        """Make authenticated request to Finnhub."""
        if not self.is_available:
            return None
        
        params = params or {}
        params["token"] = self.api_key
        
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                r = await client.get(f"{self.BASE_URL}/{endpoint}", params=params)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPError as e:
                logger.error("finnhub_error", endpoint=endpoint, error=str(e))
                return None
    
    async def get_general_news(self, category: str = "general") -> List[Dict[str, Any]]:
        """
        Get general market news.
        
        Categories: general, forex, crypto, merger
        """
        data = await self._request("news", {"category": category})
        
        if not data:
            return []
        
        # Transform to standard format
        news = []
        for item in data:
            news.append({
                "title": item.get("headline", ""),
                "source": item.get("source", "Finnhub"),
                "publishedAt": datetime.fromtimestamp(
                    item.get("datetime", 0)
                ).isoformat() if item.get("datetime") else None,
                "url": item.get("url", ""),
                "summary": item.get("summary", ""),
                "category": item.get("category", category),
                "related": item.get("related", ""),  # Related symbols
            })
        
        logger.info("finnhub_news", category=category, count=len(news))
        return news
    
    async def get_crypto_news(self) -> List[Dict[str, Any]]:
        """Get crypto-specific news."""
        return await self.get_general_news("crypto")
    
    async def get_company_news(
        self, 
        symbol: str, 
        from_date: str = None,
        to_date: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get news for specific company/symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'TSLA')
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
        """
        if not from_date:
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")
        
        data = await self._request("company-news", {
            "symbol": symbol,
            "from": from_date,
            "to": to_date
        })
        
        if not data:
            return []
        
        news = []
        for item in data:
            news.append({
                "title": item.get("headline", ""),
                "source": item.get("source", ""),
                "publishedAt": datetime.fromtimestamp(
                    item.get("datetime", 0)
                ).isoformat() if item.get("datetime") else None,
                "url": item.get("url", ""),
                "summary": item.get("summary", ""),
                "symbol": symbol,
            })
        
        return news
    
    async def get_social_sentiment(self, symbol: str) -> Dict[str, Any]:
        """
        Get Twitter/social sentiment for a symbol.
        
        Returns sentiment score and mention volume.
        """
        data = await self._request("stock/social-sentiment", {"symbol": symbol})
        
        if not data:
            return {"available": False}
        
        # Aggregate Twitter data
        twitter = data.get("twitter", [])
        
        if not twitter:
            return {"available": False, "symbol": symbol}
        
        # Get latest sentiment
        latest = twitter[-1] if twitter else {}
        
        return {
            "available": True,
            "symbol": symbol,
            "score": latest.get("score", 0),
            "positive": latest.get("positiveMention", 0),
            "negative": latest.get("negativeMention", 0),
            "total_mentions": latest.get("mention", 0),
            "date": latest.get("atTime", ""),
        }
    
    async def get_breaking_news(self, max_age_minutes: int = 30) -> List[Dict[str, Any]]:
        """
        Get only breaking/recent news (within last N minutes).
        
        This is ideal for trading signals - only fresh news.
        """
        all_news = []
        
        # Fetch from multiple categories
        for category in ["general", "crypto"]:
            news = await self.get_general_news(category)
            all_news.extend(news)
        
        # Filter by time
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        
        breaking = []
        for item in all_news:
            pub_time = item.get("publishedAt")
            if pub_time:
                try:
                    dt = datetime.fromisoformat(pub_time.replace("Z", ""))
                    if dt > cutoff:
                        breaking.append(item)
                except:
                    pass
        
        logger.info("finnhub_breaking", 
                   total=len(all_news), 
                   breaking=len(breaking),
                   max_age_min=max_age_minutes)
        
        return breaking
    
    async def get_all_fresh_news(self) -> List[Dict[str, Any]]:
        """
        Get all fresh news from Finnhub - multiple categories.
        
        Returns deduplicated, sorted by time.
        """
        categories = ["general", "forex", "crypto", "merger"]
        
        all_news = []
        seen_titles = set()
        
        for cat in categories:
            news = await self.get_general_news(cat)
            for item in news:
                title = item.get("title", "")
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    all_news.append(item)
        
        # Sort by publish time (newest first)
        all_news.sort(
            key=lambda x: x.get("publishedAt", "") or "",
            reverse=True
        )
        
        return all_news


# Singleton
finnhub = FinnhubClient()
