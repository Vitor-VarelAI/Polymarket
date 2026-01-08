"""
ExaSignal - Event Scheduler
Schedules pre-event analysis for all markets based on category and end date.

Features:
- Fetches market end dates from Polymarket API
- Calculates analysis windows by category
- Triggers analysis at optimal time before event
- Includes position sizing recommendations
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from src.api.gamma_client import GammaClient
from src.core.market_manager import MarketManager
from src.utils.logger import logger


class MarketCategory(Enum):
    """Market categories with different analysis timing."""
    SPORTS = "sports"
    CRYPTO = "crypto"
    POLITICS = "politics"
    TECH = "tech"
    GEOPOLITICS = "geopolitics"
    OTHER = "other"


@dataclass
class CategoryConfig:
    """Configuration for each market category."""
    threshold: int  # Score threshold for alerts
    analysis_hours_before: int  # Hours before event to analyze
    min_odds: float = 0.20  # Minimum odds to consider (20%)
    max_odds: float = 0.80  # Maximum odds to consider (80%)


# Global category configurations
CATEGORY_CONFIGS: Dict[MarketCategory, CategoryConfig] = {
    MarketCategory.SPORTS: CategoryConfig(threshold=55, analysis_hours_before=3),
    MarketCategory.CRYPTO: CategoryConfig(threshold=50, analysis_hours_before=1),
    MarketCategory.POLITICS: CategoryConfig(threshold=65, analysis_hours_before=72),  # 3 days
    MarketCategory.TECH: CategoryConfig(threshold=60, analysis_hours_before=24),
    MarketCategory.GEOPOLITICS: CategoryConfig(threshold=60, analysis_hours_before=6),
    MarketCategory.OTHER: CategoryConfig(threshold=60, analysis_hours_before=24),
}


@dataclass
class ScheduledEvent:
    """An event scheduled for analysis."""
    market_id: str
    market_name: str
    category: MarketCategory
    end_date: datetime
    analysis_time: datetime  # When to trigger analysis
    current_odds: Optional[float] = None
    
    @property
    def time_until_analysis(self) -> timedelta:
        """Time until analysis should be triggered."""
        return self.analysis_time - datetime.now()
    
    @property
    def time_until_event(self) -> timedelta:
        """Time until event ends."""
        return self.end_date - datetime.now()
    
    @property
    def is_due(self) -> bool:
        """Check if analysis is due."""
        return datetime.now() >= self.analysis_time
    
    @property
    def is_expired(self) -> bool:
        """Check if event has already ended."""
        return datetime.now() >= self.end_date


@dataclass
class PositionSizing:
    """Position sizing rules for budget management."""
    total_budget: float = 20.0  # Total budget
    per_trade: float = 1.50  # Per trade amount
    max_exposure: float = 6.0  # Max total exposure
    max_positions: int = 4  # Max simultaneous positions
    current_exposure: float = 0.0  # Current exposure
    
    @property
    def can_trade(self) -> bool:
        """Check if can open new position."""
        return self.current_exposure + self.per_trade <= self.max_exposure
    
    @property
    def remaining_budget(self) -> float:
        """Remaining available budget."""
        return self.max_exposure - self.current_exposure
    
    def to_dict(self) -> Dict:
        """Convert to dict for display."""
        return {
            "per_trade": f"${self.per_trade:.2f}",
            "max_exposure": f"${self.max_exposure:.2f}",
            "current_exposure": f"${self.current_exposure:.2f}",
            "remaining": f"${self.remaining_budget:.2f}",
            "can_trade": self.can_trade
        }


class EventScheduler:
    """
    Schedules and manages pre-event analysis for all markets.
    
    Usage:
        scheduler = EventScheduler(market_manager, gamma_client)
        await scheduler.refresh_schedule()
        upcoming = scheduler.get_upcoming_events(limit=5)
        due = scheduler.get_due_events()
    """
    
    def __init__(
        self,
        market_manager: MarketManager,
        gamma_client: GammaClient,
        position_sizing: PositionSizing = None
    ):
        """Initialize scheduler."""
        self.market_manager = market_manager
        self.gamma = gamma_client
        self.position_sizing = position_sizing or PositionSizing()
        
        self._scheduled_events: Dict[str, ScheduledEvent] = {}
        self._last_refresh: Optional[datetime] = None
    
    def detect_category(self, market_name: str, tags: List[str] = None) -> MarketCategory:
        """
        Detect market category from name and tags.
        """
        name_lower = market_name.lower()
        tags_lower = [t.lower() for t in (tags or [])]
        all_text = name_lower + " ".join(tags_lower)
        
        # Sports
        sports_keywords = ["premier league", "epl", "nfl", "nba", "ufc", "champions league",
                         "football", "soccer", "match", "game", "win", "liverpool", 
                         "manchester", "arsenal", "chelsea"]
        if any(kw in all_text for kw in sports_keywords):
            return MarketCategory.SPORTS
        
        # Crypto
        crypto_keywords = ["bitcoin", "btc", "ethereum", "eth", "solana", "sol", 
                          "crypto", "price", "$"]
        if any(kw in all_text for kw in crypto_keywords):
            return MarketCategory.CRYPTO
        
        # Politics
        politics_keywords = ["trump", "biden", "election", "president", "senate",
                            "congress", "vote", "poll", "approval"]
        if any(kw in all_text for kw in politics_keywords):
            return MarketCategory.POLITICS
        
        # Tech
        tech_keywords = ["openai", "google", "ai", "gpt", "gemini", "anthropic",
                        "ipo", "launch", "release", "model"]
        if any(kw in all_text for kw in tech_keywords):
            return MarketCategory.TECH
        
        # Geopolitics
        geo_keywords = ["war", "invasion", "military", "strike", "iran", "russia",
                       "china", "venezuela", "israel"]
        if any(kw in all_text for kw in geo_keywords):
            return MarketCategory.GEOPOLITICS
        
        return MarketCategory.OTHER
    
    def get_config(self, category: MarketCategory) -> CategoryConfig:
        """Get configuration for category."""
        return CATEGORY_CONFIGS.get(category, CATEGORY_CONFIGS[MarketCategory.OTHER])
    
    async def refresh_schedule(self) -> int:
        """
        Refresh scheduled events from all markets.
        
        Returns:
            Number of events scheduled
        """
        self._scheduled_events.clear()
        
        markets = self.market_manager.get_all_markets()
        
        for market in markets:
            try:
                # Get market details from API
                details = await self.gamma.get_market_details(market.market_id)
                if not details:
                    continue
                
                # Parse end date
                end_date_str = details.get("endDate") or details.get("end_date")
                if not end_date_str:
                    continue
                
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    # Convert to naive datetime for comparison
                    end_date = end_date.replace(tzinfo=None)
                except:
                    continue
                
                # Skip expired markets
                if end_date <= datetime.now():
                    continue
                
                # Detect category
                tags = getattr(market, 'tags', []) or []
                category = self.detect_category(market.market_name, tags)
                config = self.get_config(category)
                
                # Calculate analysis time
                analysis_time = end_date - timedelta(hours=config.analysis_hours_before)
                
                # If analysis time is in the past but event is future, analyze now
                if analysis_time < datetime.now() < end_date:
                    analysis_time = datetime.now()
                
                # Get current odds
                odds = None
                if details.get("outcomes"):
                    for outcome in details["outcomes"]:
                        if outcome.get("name", "").upper() == "YES":
                            odds = float(outcome.get("price", 0))
                            break
                
                # Create scheduled event
                event = ScheduledEvent(
                    market_id=market.market_id,
                    market_name=market.market_name,
                    category=category,
                    end_date=end_date,
                    analysis_time=analysis_time,
                    current_odds=odds
                )
                
                self._scheduled_events[market.market_id] = event
                
            except Exception as e:
                logger.debug("schedule_event_error", market_id=market.market_id, error=str(e))
                continue
        
        self._last_refresh = datetime.now()
        
        logger.info(
            "schedule_refreshed",
            total_events=len(self._scheduled_events),
            by_category={cat.value: sum(1 for e in self._scheduled_events.values() if e.category == cat) 
                        for cat in MarketCategory}
        )
        
        return len(self._scheduled_events)
    
    def get_upcoming_events(self, limit: int = 5) -> List[ScheduledEvent]:
        """Get upcoming events sorted by analysis time."""
        events = [e for e in self._scheduled_events.values() if not e.is_expired]
        events.sort(key=lambda e: e.analysis_time)
        return events[:limit]
    
    def get_due_events(self) -> List[ScheduledEvent]:
        """Get events that are due for analysis."""
        return [e for e in self._scheduled_events.values() if e.is_due and not e.is_expired]
    
    def get_event(self, market_id: str) -> Optional[ScheduledEvent]:
        """Get scheduled event by market ID."""
        return self._scheduled_events.get(market_id)
    
    def format_upcoming_telegram(self, limit: int = 5) -> str:
        """Format upcoming events for Telegram."""
        events = self.get_upcoming_events(limit)
        
        if not events:
            return "📅 *Upcoming Events*\n\n_No upcoming events scheduled._"
        
        lines = ["📅 *Upcoming Events*", ""]
        
        for i, event in enumerate(events, 1):
            config = self.get_config(event.category)
            
            # Time formatting
            if event.time_until_event.days > 0:
                time_str = f"{event.time_until_event.days}d"
            else:
                hours = event.time_until_event.seconds // 3600
                time_str = f"{hours}h"
            
            # Category emoji
            cat_emoji = {
                MarketCategory.SPORTS: "⚽",
                MarketCategory.CRYPTO: "🪙",
                MarketCategory.POLITICS: "🏛️",
                MarketCategory.TECH: "🤖",
                MarketCategory.GEOPOLITICS: "🌍",
                MarketCategory.OTHER: "📊"
            }.get(event.category, "📊")
            
            # Odds display
            odds_str = f"{event.current_odds*100:.0f}%" if event.current_odds else "?"
            
            # Analysis status
            if event.is_due:
                status = "🔔 ANALYZE NOW"
            else:
                analysis_hours = event.time_until_analysis.seconds // 3600
                analysis_days = event.time_until_analysis.days
                if analysis_days > 0:
                    status = f"⏰ Analyze in {analysis_days}d"
                else:
                    status = f"⏰ Analyze in {analysis_hours}h"
            
            lines.extend([
                f"**{i}. {cat_emoji} {event.market_name[:40]}...**",
                f"├ Ends: {time_str} | Odds: {odds_str}",
                f"├ Threshold: {config.threshold}",
                f"└ {status}",
                ""
            ])
        
        # Position sizing info
        sizing = self.position_sizing
        lines.extend([
            "**💰 Position Sizing:**",
            f"├ Per trade: ${sizing.per_trade:.2f}",
            f"├ Available: ${sizing.remaining_budget:.2f}",
            f"└ Can trade: {'✅' if sizing.can_trade else '❌'}"
        ])
        
        return "\n".join(lines)
    
    async def get_status(self) -> Dict:
        """Get scheduler status."""
        return {
            "total_scheduled": len(self._scheduled_events),
            "due_for_analysis": len(self.get_due_events()),
            "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
            "position_sizing": self.position_sizing.to_dict()
        }
