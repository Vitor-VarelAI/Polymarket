"""
ExaSignal - Value Bets Scanner
Finds undervalued markets (underdogs) with potential edge.

Strategy: Find markets at 5-30% odds that are underpriced.
With $1 bets, a win at 10% odds = $9 profit.
"""
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime, timezone, timedelta

from src.api.gamma_client import GammaClient
from src.utils.logger import logger


@dataclass
class ValueBet:
    """A value bet opportunity (underdog)."""
    market_id: str
    market_name: str
    slug: str
    category: str
    
    # Odds
    yes_odds: float  # Current YES price (e.g., 12%)
    no_odds: float
    
    # Trade details
    bet_side: str  # "YES" or "NO"
    entry_price: float  # Price per share in cents
    potential_multiplier: float  # e.g., 8x for 12% odds
    
    # For $1 bet
    shares_for_dollar: int  # How many shares $1 buys
    win_amount: float  # Total if wins
    lose_amount: float = 1.0  # Always $1
    
    # Metadata
    liquidity: float = 0
    volume: float = 0
    end_date: Optional[str] = None
    days_to_resolution: int = 0
    
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ValueBetsScanner:
    """
    Scans for undervalued markets (5-30% odds).
    
    Collects opportunities for digest curation.
    """
    
    EXCLUDED_CATEGORIES = ["Sports"]
    
    def __init__(
        self,
        gamma: Optional[GammaClient] = None,
        min_odds: float = 5.0,  # Minimum odds to consider
        max_odds: float = 30.0,  # Maximum odds (above = too risky)
        min_liquidity: float = 5000,  # $5k minimum
        max_days_to_resolution: int = 60,  # Max 60 days out
        scan_interval: int = 7200,  # 2 hours
    ):
        self.gamma = gamma or GammaClient()
        self.min_odds = min_odds
        self.max_odds = max_odds
        self.min_liquidity = min_liquidity
        self.max_days_to_resolution = max_days_to_resolution
        self.scan_interval = scan_interval
        
        # Candidate queue - collected between digests
        self.candidates: List[ValueBet] = []
        
        # Track sent markets to avoid duplicates
        self.sent_markets: Set[str] = set()
        
        self._running = False
        self.stats = {
            "scans": 0,
            "markets_checked": 0,
            "candidates_found": 0,
        }
    
    def _detect_category(self, title: str) -> str:
        """Detect market category from title."""
        title_lower = title.lower()
        
        if any(w in title_lower for w in ["trump", "biden", "election", "president", "congress", "governor", "senate"]):
            return "Politics"
        elif any(w in title_lower for w in ["bitcoin", "ethereum", "crypto", "btc", "eth", "solana", "xrp"]):
            return "Crypto"
        elif any(w in title_lower for w in ["ai", "openai", "gpt", "claude", "gemini", "anthropic"]):
            return "AI/Tech"
        elif any(w in title_lower for w in ["nba", "nfl", "mlb", "soccer", "football", "game", "match", "championship"]):
            return "Sports"
        elif any(w in title_lower for w in ["weather", "temperature", "snow", "rain"]):
            return "Weather"
        else:
            return "Other"
    
    def _calculate_days_to_resolution(self, end_date: Optional[str]) -> int:
        """Calculate days until market resolves."""
        if not end_date:
            return 999  # Unknown
        
        try:
            end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = end - now
            return max(0, delta.days)
        except Exception:
            return 999
    
    async def scan_markets(self) -> List[ValueBet]:
        """Scan all markets for value bet opportunities."""
        import httpx
        
        logger.info("value_scan_starting")
        self.stats["scans"] += 1
        
        new_candidates = []
        
        async with httpx.AsyncClient(
            base_url="https://gamma-api.polymarket.com",
            timeout=60
        ) as client:
            # Fetch active events
            r = await client.get("/events", params={
                "limit": 200,
                "active": "true",
                "order": "volume",
                "ascending": "false"
            })
            
            if r.status_code != 200:
                logger.error("gamma_fetch_error", status=r.status_code)
                return []
            
            events = r.json()
            self.stats["markets_checked"] += len(events)
            
            for event in events:
                try:
                    bet = self._analyze_event(event)
                    if bet:
                        new_candidates.append(bet)
                        self.stats["candidates_found"] += 1
                except Exception as e:
                    logger.error("event_analysis_error", error=str(e))
        
        # Add to candidates queue (avoiding duplicates)
        for candidate in new_candidates:
            if candidate.market_id not in self.sent_markets:
                # Check if already in queue
                existing_ids = {c.market_id for c in self.candidates}
                if candidate.market_id not in existing_ids:
                    self.candidates.append(candidate)
        
        logger.info("value_scan_complete", 
                   new_candidates=len(new_candidates),
                   queue_size=len(self.candidates))
        
        return new_candidates
    
    def _analyze_event(self, event: dict) -> Optional[ValueBet]:
        """Analyze an event for value bet potential."""
        # Get market data
        markets = event.get("markets", [])
        if not markets:
            return None
        
        market = markets[0]  # Primary market
        
        # Get odds
        outcomes = market.get("outcomes", [])
        if len(outcomes) < 2:
            return None
        
        yes_outcome = next((o for o in outcomes if o.get("name", "").lower() == "yes"), None)
        no_outcome = next((o for o in outcomes if o.get("name", "").lower() == "no"), None)
        
        if not yes_outcome or not no_outcome:
            # Multi-outcome market, skip for now
            return None
        
        yes_price = float(yes_outcome.get("price", 0.5)) * 100
        no_price = float(no_outcome.get("price", 0.5)) * 100
        
        # Get other data
        title = event.get("title", "")
        slug = event.get("slug", "")
        category = self._detect_category(title)
        liquidity = float(event.get("liquidity", 0))
        volume = float(event.get("volume", 0))
        end_date = event.get("endDate")
        
        # Skip excluded categories
        if category in self.EXCLUDED_CATEGORIES:
            return None
        
        # Skip low liquidity
        if liquidity < self.min_liquidity:
            return None
        
        # Check resolution time
        days_to_res = self._calculate_days_to_resolution(end_date)
        if days_to_res > self.max_days_to_resolution:
            return None
        
        # Find the underdog side
        bet_side = None
        entry_price = None
        
        if self.min_odds <= yes_price <= self.max_odds:
            bet_side = "YES"
            entry_price = yes_price
        elif self.min_odds <= no_price <= self.max_odds:
            bet_side = "NO"
            entry_price = no_price
        else:
            return None  # No underdog in range
        
        # Calculate $1 bet details
        price_per_share = entry_price / 100  # Convert to dollars
        shares_for_dollar = int(1.0 / price_per_share) if price_per_share > 0 else 0
        win_amount = shares_for_dollar * 1.0  # Each share pays $1 if wins
        potential_multiplier = 100 / entry_price if entry_price > 0 else 0
        
        return ValueBet(
            market_id=slug,
            market_name=title,
            slug=slug,
            category=category,
            yes_odds=yes_price,
            no_odds=no_price,
            bet_side=bet_side,
            entry_price=entry_price,
            potential_multiplier=potential_multiplier,
            shares_for_dollar=shares_for_dollar,
            win_amount=win_amount,
            lose_amount=1.0,
            liquidity=liquidity,
            volume=volume,
            end_date=end_date,
            days_to_resolution=days_to_res,
        )
    
    def get_candidates(self) -> List[ValueBet]:
        """Get current candidate queue."""
        return self.candidates.copy()
    
    def clear_candidates(self, sent_ids: List[str]):
        """Clear sent candidates and track them."""
        self.sent_markets.update(sent_ids)
        self.candidates = [c for c in self.candidates if c.market_id not in sent_ids]
        
        # Limit sent_markets size
        if len(self.sent_markets) > 500:
            self.sent_markets = set(list(self.sent_markets)[-250:])
    
    async def start_scanning(self):
        """Start continuous scanning loop."""
        self._running = True
        logger.info("value_bets_scanner_started",
                   min_odds=self.min_odds,
                   max_odds=self.max_odds,
                   scan_interval=self.scan_interval)
        
        while self._running:
            try:
                await self.scan_markets()
            except Exception as e:
                logger.error("scan_error", error=str(e))
            
            await asyncio.sleep(self.scan_interval)
    
    def stop_scanning(self):
        """Stop the scanning loop."""
        self._running = False
    
    def get_status(self) -> dict:
        """Get scanner status."""
        return {
            "running": self._running,
            "candidates_in_queue": len(self.candidates),
            "sent_markets": len(self.sent_markets),
            "stats": self.stats,
        }
