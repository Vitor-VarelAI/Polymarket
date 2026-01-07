"""
ExaSignal - News Monitor
Monitoriza fontes de notícias e gera sinais de trading.

Flow: Poll news → Match to markets → Generate signals → Alert

Sources:
1. Finnhub (Primary) - Real-time, Twitter sentiment
2. NewsAPI (Fallback) - Broad coverage
"""
import asyncio
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta

from src.api.newsapi_client import NewsAPIClient
from src.api.finnhub_client import FinnhubClient, finnhub
from src.api.groq_client import GroqClient
from src.core.signal_generator import SignalGenerator, Signal
from src.core.market_matcher import MarketMatcher
from src.models.enriched_signal import EnrichedSignal
from src.api.gamma_client import GammaClient
from src.utils.logger import logger


@dataclass
class NewsItem:
    """Standardized news item."""
    title: str
    source: str
    published_at: str
    url: str
    description: Optional[str] = None
    category: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "source": self.source,
            "publishedAt": self.published_at,
            "url": self.url,
            "description": self.description,
        }


class NewsMonitor:
    """
    Monitors news sources and generates trading signals.
    
    Priority Sources:
    1. Finnhub - Real-time news (faster!)
    2. NewsAPI - Fallback
    
    Workflow:
    1. Fetch latest news from APIs
    2. Match news to prediction markets
    3. Generate AI-powered signals
    4. Emit signals via callback
    """
    
    def __init__(
        self,
        newsapi: Optional[NewsAPIClient] = None,
        finnhub_client: Optional[FinnhubClient] = None,
        groq: Optional[GroqClient] = None,
        gamma: Optional[GammaClient] = None,
        search_func: Optional[Callable] = None,
        signal_callback: Optional[Callable[[EnrichedSignal], Any]] = None,
        poll_interval_seconds: int = 60,  # 1 minute for speed
        min_score: int = 70,  # Minimum composite score for alerts
        min_confidence: int = 60,  # Minimum LLM confidence
        max_news_age_minutes: int = 30,  # Only process recent news
        use_enriched: bool = True,  # Use full enriched pipeline
    ):
        self.newsapi = newsapi or NewsAPIClient()
        self.finnhub = finnhub_client or finnhub
        self.groq = groq or GroqClient()
        self.gamma = gamma  # For fetching current odds
        self.signal_generator = SignalGenerator(self.groq)
        self.market_matcher = MarketMatcher(search_func)
        
        self.signal_callback = signal_callback
        self.poll_interval = poll_interval_seconds
        self.min_score = min_score
        self.min_confidence = min_confidence
        self.max_news_age = max_news_age_minutes
        self.use_enriched = use_enriched
        
        self._running = False
        self._seen_news: set = set()  # Track processed news
        self._last_poll: Optional[datetime] = None
        
        # Stats
        self.stats = {
            "finnhub_fetched": 0,
            "newsapi_fetched": 0,
            "signals_generated": 0,
            "enriched_signals": 0,
        }
    
    async def fetch_from_finnhub(self) -> List[NewsItem]:
        """Fetch breaking news from Finnhub (PRIMARY - faster)."""
        if not self.finnhub.is_available:
            return []
        
        news_items = []
        
        try:
            # Get breaking news (last 30 min)
            articles = await self.finnhub.get_breaking_news(
                max_age_minutes=self.max_news_age
            )
            
            for article in articles:
                title = article.get("title", "")
                news_id = f"finnhub:{title[:50]}"
                
                if news_id in self._seen_news:
                    continue
                
                news_items.append(NewsItem(
                    title=title,
                    source=article.get("source", "Finnhub"),
                    published_at=article.get("publishedAt", ""),
                    url=article.get("url", ""),
                    description=article.get("summary", ""),
                    category=article.get("category", ""),
                ))
                
                self._seen_news.add(news_id)
            
            self.stats["finnhub_fetched"] += len(news_items)
            logger.info("finnhub_fetch_complete", count=len(news_items))
            
        except Exception as e:
            logger.error("finnhub_fetch_error", error=str(e))
        
        return news_items
    
    async def fetch_from_newsapi(self, categories: List[str] = None) -> List[NewsItem]:
        """Fetch news from NewsAPI (FALLBACK)."""
        categories = categories or ["crypto", "politics", "technology"]
        
        news_items = []
        
        for category in categories:
            try:
                query = self._category_to_query(category)
                articles = await self.newsapi.search_articles(query, max_results=5)
                
                for article in articles:
                    title = article.get("title", "")
                    news_id = f"newsapi:{title[:50]}"
                    
                    if news_id in self._seen_news:
                        continue
                    
                    news_items.append(NewsItem(
                        title=title,
                        source=article.get("source", {}).get("name", "NewsAPI"),
                        published_at=article.get("publishedAt", ""),
                        url=article.get("url", ""),
                        description=article.get("description"),
                        category=category,
                    ))
                    
                    self._seen_news.add(news_id)
                    
            except Exception as e:
                logger.error("newsapi_fetch_error", category=category, error=str(e))
        
        self.stats["newsapi_fetched"] += len(news_items)
        return news_items
    
    def _category_to_query(self, category: str) -> str:
        """Convert category to search query."""
        queries = {
            "politics": "politics election president",
            "crypto": "bitcoin ethereum crypto",
            "technology": "AI OpenAI tech startup",
            "business": "stock market economy",
        }
        return queries.get(category, category)
    
    async def fetch_latest_news(self) -> List[NewsItem]:
        """
        Fetch from ALL sources, prioritizing Finnhub.
        
        Returns deduplicated, sorted by time.
        """
        all_news = []
        
        # 1. Finnhub (primary - faster)
        finnhub_news = await self.fetch_from_finnhub()
        all_news.extend(finnhub_news)
        
        # 2. NewsAPI (fallback - if Finnhub returned few results)
        if len(finnhub_news) < 5:
            newsapi_news = await self.fetch_from_newsapi()
            all_news.extend(newsapi_news)
        
        # Keep seen set manageable
        if len(self._seen_news) > 500:
            self._seen_news = set(list(self._seen_news)[-250:])
        
        logger.info("news_fetched_total", count=len(all_news))
        return all_news
    
    async def process_news(self, news: NewsItem) -> List[EnrichedSignal]:
        """
        Process single news item through FULL ENRICHED PIPELINE:
        1. Match to markets
        2. Run ResearchLoop (multi-source)
        3. Run AlignmentScorer (5 dimensions)
        4. Run LLM with research context
        5. Return EnrichedSignal
        """
        signals = []
        
        # Find matching markets
        matches = await self.market_matcher.find_markets(
            news.title,
            limit=3,
            min_relevance=0.1  # Lower threshold for more matches
        )
        
        if not matches:
            logger.debug("no_market_match", news=news.title[:50])
            return signals
        
        # Generate ENRICHED signal for each match
        for match in matches:
            try:
                # Get current odds if gamma is available
                current_odds = None
                if self.gamma:
                    try:
                        current_odds = await self.gamma.get_market_odds(match.market_id)
                    except:
                        pass
                
                if self.use_enriched:
                    # === FULL ENRICHED PIPELINE ===
                    signal = await self.signal_generator.analyze_enriched(
                        trigger_type="news",
                        trigger_data=news.to_dict(),
                        market={
                            "id": match.market_id,
                            "name": match.market_name,
                            "slug": match.slug,
                            "category": match.category,
                        },
                        current_odds=current_odds
                    )
                    
                    # Check if actionable based on composite score
                    if signal.is_actionable(self.min_score, self.min_confidence):
                        signals.append(signal)
                        self.stats["enriched_signals"] += 1
                        self.stats["signals_generated"] += 1
                        
                        # Log enriched signal details
                        logger.info(
                            "enriched_signal_actionable",
                            market=match.market_id,
                            direction=signal.direction,
                            score=signal.score_total,
                            confidence=signal.confidence,
                            sources=signal.source_breakdown
                        )
                        
                        # Call callback if set
                        if self.signal_callback:
                            try:
                                await self.signal_callback(signal)
                            except Exception as e:
                                logger.error("signal_callback_error", error=str(e))
                else:
                    # === SIMPLE PIPELINE (backward compatible) ===
                    simple_signal = await self.signal_generator.analyze(
                        news=news.to_dict(),
                        market={
                            "id": match.market_id,
                            "name": match.market_name,
                            "slug": match.slug,
                        },
                        current_odds=current_odds
                    )
                    
                    if simple_signal.is_actionable(self.min_confidence):
                        # Convert to minimal EnrichedSignal for compatibility
                        enriched = self._simple_to_enriched(simple_signal, news, match)
                        signals.append(enriched)
                        self.stats["signals_generated"] += 1
                        
                        if self.signal_callback:
                            try:
                                await self.signal_callback(enriched)
                            except Exception as e:
                                logger.error("signal_callback_error", error=str(e))
                
            except Exception as e:
                logger.error("signal_gen_error", 
                           news=news.title[:30],
                           error=str(e))
        
        return signals
    
    def _simple_to_enriched(self, signal: Signal, news: NewsItem, match) -> EnrichedSignal:
        """Convert simple Signal to minimal EnrichedSignal for backward compatibility."""
        return EnrichedSignal(
            market_id=signal.market_id,
            market_name=signal.market_name,
            market_slug=match.slug,
            direction=signal.direction,
            should_alert=signal.is_actionable(),
            trigger_type="news",
            trigger_data=news.to_dict(),
            confidence=signal.confidence,
            reasoning=signal.reasoning,
            key_points=signal.key_points,
            score_total=signal.confidence,  # Use confidence as score fallback
            score_credibility=0,
            score_recency=0,
            score_consensus=0,
            score_specificity=0,
            score_divergence=0,
            sources=[],
            source_breakdown={},
            current_odds=signal.current_odds,
        )
    
    async def scan_once(self) -> List[Signal]:
        """
        Run single scan: fetch news, process, generate signals.
        
        Returns list of actionable signals.
        """
        logger.info("news_scan_starting")
        
        # Fetch news
        news_items = await self.fetch_latest_news()
        
        if not news_items:
            logger.info("no_new_news")
            return []
        
        # Process each news item
        all_signals = []
        for news in news_items[:20]:  # Limit to 20 per scan
            signals = await self.process_news(news)
            all_signals.extend(signals)
            
            # Small delay between items
            await asyncio.sleep(0.3)
        
        self._last_poll = datetime.now()
        
        logger.info("news_scan_complete",
                   news_count=len(news_items),
                   signals_count=len(all_signals))
        
        return all_signals
    
    async def start_monitoring(self):
        """Start continuous monitoring loop."""
        self._running = True
        logger.info("news_monitor_started", 
                   interval=self.poll_interval,
                   min_confidence=self.min_confidence,
                   finnhub_available=self.finnhub.is_available)
        
        while self._running:
            try:
                await self.scan_once()
            except Exception as e:
                logger.error("monitor_loop_error", error=str(e))
            
            await asyncio.sleep(self.poll_interval)
    
    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self._running = False
        logger.info("news_monitor_stopped")
    
    def get_recent_signals(self, limit: int = 10) -> List[Signal]:
        """Get recent signals from generator."""
        return self.signal_generator.get_recent_signals(limit)
    
    def get_status(self) -> dict:
        """Get monitor status."""
        return {
            "running": self._running,
            "last_poll": self._last_poll.isoformat() if self._last_poll else None,
            "poll_interval_seconds": self.poll_interval,
            "min_confidence": self.min_confidence,
            "max_news_age_minutes": self.max_news_age,
            "seen_news_count": len(self._seen_news),
            "recent_signals": len(self.signal_generator.recent_signals),
            "finnhub_available": self.finnhub.is_available,
            "stats": self.stats,
        }
