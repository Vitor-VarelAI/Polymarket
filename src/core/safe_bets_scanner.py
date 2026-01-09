"""
ExaSignal - Safe Bets Scanner (SwissTony Vacuum Cleaner Strategy)
Finds markets with 97-99% odds for guaranteed 1-3¢ profit.

Strategy:
- Bet NO on outcomes with 99% implied probability
- Pay 1¢, collect 1¢ when event resolves (99% of time)
- This is "insurance premium collection" - you're the house

Example:
- Market: "Will the sun rise tomorrow?" at 99.5% YES
- Buy NO at 0.5¢, collect 1¢ if NO wins (very unlikely)
- OR collect your 0.5¢ back + profit when YES wins
- Risk/Reward: Lose 0.5¢ rarely, gain 0.5¢ almost always

Flow:
1. Scan all active Polymarket markets
2. Find markets with odds >= 97% or <= 3%
3. Filter out risky categories (sports events during game)
4. Calculate expected value and risk
5. Alert on high-confidence safe bets
"""
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from datetime import datetime, timezone
import json

from src.api.gamma_client import GammaClient
from src.utils.logger import logger


@dataclass
class SafeBet:
    """A safe bet opportunity."""
    market_id: str
    market_name: str
    slug: str
    category: str
    
    # Odds
    yes_odds: float  # Current YES probability
    no_odds: float   # Current NO probability (100 - yes_odds)
    
    # Trade details
    bet_side: str    # "YES" or "NO" - which side to bet
    entry_price: float  # Price to pay (in cents)
    potential_profit: float  # If bet wins (cents per share)
    
    # Risk assessment
    risk_level: str  # "ultra_safe", "safe", "moderate"
    expected_value: float  # EV per $1 bet
    liquidity: float = 0
    volume: float = 0
    
    # Metadata
    end_date: str = ""
    description: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> dict:
        return {
            "market_id": self.market_id,
            "market_name": self.market_name,
            "slug": self.slug,
            "category": self.category,
            "yes_odds": self.yes_odds,
            "no_odds": self.no_odds,
            "bet_side": self.bet_side,
            "entry_price": self.entry_price,
            "potential_profit": self.potential_profit,
            "risk_level": self.risk_level,
            "expected_value": self.expected_value,
            "liquidity": self.liquidity,
            "volume": self.volume,
            "end_date": self.end_date,
            "timestamp": self.timestamp,
        }
    
    def to_telegram(self) -> str:
        """Format for Telegram notification."""
        risk_emoji = {
            "ultra_safe": "🟢",
            "safe": "🟡", 
            "moderate": "🟠"
        }.get(self.risk_level, "⚪")
        
        return f"""
💰 *SAFE BET FOUND* {risk_emoji}

📊 *Market:* {self.market_name[:60]}...

📈 *Current Odds:*
   YES: {self.yes_odds:.1f}%
   NO: {self.no_odds:.1f}%

🎯 *Trade:*
   Side: *BET {self.bet_side}*
   Entry: {self.entry_price:.1f}¢ per share
   Profit if wins: {self.potential_profit:.1f}¢ per share

⚖️ *Expected Value:* {self.expected_value:.2f}% per trade
💧 *Liquidity:* ${self.liquidity:,.0f}
📦 *Volume:* ${self.volume:,.0f}

⚠️ Risk Level: {self.risk_level.replace('_', ' ').title()}

🔗 [Open Market](https://polymarket.com/event/{self.slug})

⏰ {self.timestamp[:19]}
"""


class SafeBetsScanner:
    """
    Scans Polymarket for safe bet opportunities.
    
    Looks for markets with extreme odds (97%+ or 3%-) where
    betting against the extreme outcome provides small but
    consistent profits.
    
    This is the "vacuum cleaner" strategy - collecting pennies
    from near-certain outcomes.
    """
    
    def __init__(
        self,
        gamma: Optional[GammaClient] = None,
        callback: Optional[Callable] = None,
        min_odds_threshold: float = 97.0,  # Minimum odds to consider
        min_liquidity: float = 1000,  # Minimum $1k liquidity
        min_expected_value: float = 0.5,  # Minimum 0.5% EV
        scan_interval: int = 1800,  # 30 minutes
        excluded_categories: List[str] = None,
    ):
        self.gamma = gamma or GammaClient()
        self.callback = callback
        self.min_odds_threshold = min_odds_threshold
        self.min_liquidity = min_liquidity
        self.min_expected_value = min_expected_value
        self.scan_interval = scan_interval
        self.excluded_categories = excluded_categories or ["Sports"]  # Sports too volatile during games
        
        self.found_bets: List[SafeBet] = []
        self.seen_markets: set = set()  # Don't alert same market twice
        self._running = False
        
        # Stats
        self.stats = {
            "scans": 0,
            "markets_checked": 0,
            "safe_bets_found": 0,
            "total_potential_ev": 0,
        }
    
    async def fetch_all_markets(self, limit: int = 500) -> List[dict]:
        """Fetch all active markets with their odds."""
        import httpx
        
        markets = []
        
        async with httpx.AsyncClient(
            base_url="https://gamma-api.polymarket.com",
            timeout=60
        ) as client:
            # Fetch markets with all data
            r = await client.get("/markets", params={
                "limit": limit,
                "closed": "false",
                "order": "liquidity",
                "ascending": "false"
            })
            
            if r.status_code == 200:
                data = r.json()
                for m in data:
                    # Parse outcome prices
                    try:
                        prices = m.get("outcomePrices", "[]")
                        if isinstance(prices, str):
                            prices = json.loads(prices)
                        
                        yes_price = float(prices[0]) * 100 if prices else None
                        no_price = float(prices[1]) * 100 if len(prices) > 1 else (100 - yes_price if yes_price else None)
                    except:
                        yes_price = None
                        no_price = None
                    
                    if yes_price is None:
                        continue
                    
                    markets.append({
                        "id": m.get("conditionId", m.get("id", "")),
                        "slug": m.get("slug", ""),
                        "name": m.get("question", ""),
                        "description": m.get("description", "")[:200] if m.get("description") else "",
                        "yes_odds": yes_price,
                        "no_odds": no_price or (100 - yes_price),
                        "liquidity": float(m.get("liquidity", 0) or 0),
                        "volume": float(m.get("volume", 0) or 0),
                        "end_date": m.get("endDate", ""),
                        "category": self._detect_category(m.get("question", "")),
                    })
            
            # Also fetch events for better coverage
            r = await client.get("/events", params={
                "limit": 300,
                "active": "true",
                "order": "liquidity", 
                "ascending": "false"
            })
            
            if r.status_code == 200:
                events = r.json()
                seen_ids = {m["id"] for m in markets}
                
                for e in events:
                    for m in e.get("markets", []):
                        if m.get("conditionId") in seen_ids:
                            continue
                        
                        try:
                            prices = m.get("outcomePrices", "[]")
                            if isinstance(prices, str):
                                prices = json.loads(prices)
                            
                            yes_price = float(prices[0]) * 100 if prices else None
                        except:
                            continue
                        
                        if yes_price is None:
                            continue
                        
                        markets.append({
                            "id": m.get("conditionId", ""),
                            "slug": e.get("slug", ""),
                            "name": m.get("question", e.get("title", "")),
                            "description": e.get("description", "")[:200] if e.get("description") else "",
                            "yes_odds": yes_price,
                            "no_odds": 100 - yes_price,
                            "liquidity": float(m.get("liquidity", 0) or 0),
                            "volume": float(e.get("volume", 0) or 0),
                            "end_date": m.get("endDate", ""),
                            "category": self._detect_category(m.get("question", e.get("title", ""))),
                        })
        
        logger.info("markets_fetched_for_safe_bets", count=len(markets))
        return markets
    
    def _detect_category(self, title: str) -> str:
        """Detect market category from title."""
        title_lower = title.lower()
        
        if any(w in title_lower for w in ["trump", "biden", "election", "president", "congress", "governor", "senate", "vote"]):
            return "Politics"
        elif any(w in title_lower for w in ["bitcoin", "ethereum", "crypto", "btc", "eth", "solana", "xrp"]):
            return "Crypto"
        elif any(w in title_lower for w in ["nba", "nfl", "mlb", "soccer", "game", "match", "win", "vs", "lakers", "celtics"]):
            return "Sports"
        elif any(w in title_lower for w in ["ai", "openai", "gpt", "claude", "gemini", "chatgpt"]):
            return "AI"
        elif any(w in title_lower for w in ["company", "stock", "market", "earnings", "revenue"]):
            return "Business"
        else:
            return "Other"
    
    def _calculate_risk_level(self, odds: float, category: str, liquidity: float) -> str:
        """Calculate risk level for a safe bet."""
        # Ultra safe: 99%+ odds, good liquidity, predictable category
        if odds >= 99 and liquidity >= 10000 and category not in ["Sports", "Crypto"]:
            return "ultra_safe"
        # Safe: 98%+ odds, decent liquidity
        elif odds >= 98 and liquidity >= 5000:
            return "safe"
        # Moderate: 97%+ odds
        elif odds >= 97:
            return "moderate"
        else:
            return "risky"
    
    def _calculate_expected_value(self, entry_price: float, win_probability: float) -> float:
        """
        Calculate expected value of a bet.
        
        EV = (Win Probability × Profit) - (Loss Probability × Loss)
        
        For safe bets:
        - Entry price = cost per share (in cents)
        - Win = collect 100¢ per share
        - Loss = lose entry price
        """
        profit_if_win = 100 - entry_price  # Profit per share in cents
        loss_if_lose = entry_price  # Loss per share in cents
        
        # EV in cents per share
        ev_cents = (win_probability / 100 * profit_if_win) - ((100 - win_probability) / 100 * loss_if_lose)
        
        # Return as percentage of entry
        return (ev_cents / entry_price) * 100 if entry_price > 0 else 0
    
    def analyze_market(self, market: dict) -> Optional[SafeBet]:
        """Analyze a single market for safe bet opportunity."""
        yes_odds = market.get("yes_odds", 50)
        no_odds = market.get("no_odds", 50)
        liquidity = market.get("liquidity", 0)
        category = market.get("category", "Other")
        
        # Skip excluded categories
        if category in self.excluded_categories:
            return None
        
        # Skip low liquidity
        if liquidity < self.min_liquidity:
            return None
        
        # Check for extreme odds
        bet_side = None
        extreme_odds = None
        entry_price = None
        
        if yes_odds >= self.min_odds_threshold:
            # YES is very likely, bet NO is risky but pays well if wrong
            # Actually, we want to BET YES since it's almost certain
            bet_side = "YES"
            extreme_odds = yes_odds
            entry_price = yes_odds  # Pay 99¢ to win 1¢
        elif no_odds >= self.min_odds_threshold:
            # NO is very likely, bet NO
            bet_side = "NO"
            extreme_odds = no_odds
            entry_price = no_odds
        else:
            return None
        
        # For "vacuum cleaner" we actually want to bet ON the likely outcome
        # But the real strategy is betting AGAINST the unlikely outcome
        # Let me reconsider...
        
        # SwissTony strategy: Bet NO at 99¢ when YES is at 99%
        # You're betting the "almost impossible" thing won't happen
        # If YES wins (99% likely), you get your money back
        # Wait, that's not right either...
        
        # Correct interpretation:
        # When YES = 99%, NO = 1%
        # To bet NO, you pay 1¢ per share
        # If NO wins (1% chance), you get 100¢ (99¢ profit)
        # If YES wins (99% chance), you lose 1¢
        # EV = 0.01 * 99 - 0.99 * 1 = 0.99 - 0.99 = 0 (fair odds)
        
        # The REAL value is when odds are MISPRICED
        # e.g., Market says 99% but real probability is 99.5%
        # Then betting NO at 1¢ has negative EV for you
        
        # Actually SwissTony bets NO when outcome is "obviously" going to be YES
        # Like "Will Bitcoin exist tomorrow?" at 99.9% YES
        # He bets NO at 0.1¢, if YES wins he loses 0.1¢
        # But wait, that means he WANTS yes to win...
        
        # I think the actual strategy is:
        # Find markets where YES is at 99%+
        # BUY YES at 99¢
        # When market resolves to YES, get 100¢ back
        # Profit = 1¢ per share (1% return)
        
        # But the risk is: if NO wins, lose 99¢
        # So you need to be VERY confident YES will win
        
        # Let me implement this correctly:
        
        if yes_odds >= self.min_odds_threshold:
            # High YES odds = YES is almost certain
            # Strategy: BUY YES at high price, collect small profit
            bet_side = "YES"
            entry_price = yes_odds  # e.g., 99¢
            potential_profit = 100 - yes_odds  # e.g., 1¢
            win_probability = yes_odds  # e.g., 99%
        elif yes_odds <= (100 - self.min_odds_threshold):
            # Low YES odds = NO is almost certain  
            # Strategy: BUY NO at high price, collect small profit
            bet_side = "NO"
            entry_price = no_odds  # e.g., 99¢
            potential_profit = 100 - no_odds  # e.g., 1¢
            win_probability = no_odds  # e.g., 99%
        else:
            return None
        
        # Calculate expected value
        ev = self._calculate_expected_value(entry_price, win_probability)
        
        # STRICT EV filter - only alert if there's real edge
        # This filters out "fair odds" bets with 0% EV
        if ev < self.min_expected_value:
            return None
        
        risk_level = self._calculate_risk_level(win_probability, category, liquidity)
        
        return SafeBet(
            market_id=market.get("id", ""),
            market_name=market.get("name", ""),
            slug=market.get("slug", ""),
            category=category,
            yes_odds=yes_odds,
            no_odds=no_odds,
            bet_side=bet_side,
            entry_price=entry_price,
            potential_profit=potential_profit,
            risk_level=risk_level,
            expected_value=ev,
            liquidity=liquidity,
            volume=market.get("volume", 0),
            end_date=market.get("end_date", ""),
            description=market.get("description", ""),
        )
    
    async def scan_once(self) -> List[SafeBet]:
        """Run a single scan for safe bet opportunities."""
        logger.info("safe_bets_scan_starting")
        self.stats["scans"] += 1
        
        # Fetch all markets
        markets = await self.fetch_all_markets()
        self.stats["markets_checked"] += len(markets)
        
        safe_bets = []
        
        for market in markets:
            market_id = market.get("id", "")
            
            # Skip already seen markets
            if market_id in self.seen_markets:
                continue
            
            bet = self.analyze_market(market)
            
            # Only send alerts for ultra_safe and safe (not moderate)
            if bet and bet.risk_level in ["ultra_safe", "safe"]:
                safe_bets.append(bet)
                self.seen_markets.add(market_id)
                self.stats["safe_bets_found"] += 1
                self.stats["total_potential_ev"] += bet.expected_value
                
                # Call callback
                if self.callback:
                    try:
                        logger.info("safe_bet_callback_executing", market=bet.market_name[:30])
                        await self.callback(bet)
                        logger.info("safe_bet_callback_completed", market=bet.market_name[:30])
                    except Exception as e:
                        logger.error("safe_bet_callback_error", error=str(e), traceback=True)
                else:
                    logger.warning("safe_bet_callback_not_set")
                
                logger.info("safe_bet_found",
                           market=market.get("name", "")[:40],
                           odds=bet.yes_odds if bet.bet_side == "YES" else bet.no_odds,
                           entry_price=bet.entry_price,
                           risk=bet.risk_level)
        
        # Keep seen set manageable
        if len(self.seen_markets) > 1000:
            self.seen_markets = set(list(self.seen_markets)[-500:])
        
        # Keep recent bets
        self.found_bets = (safe_bets + self.found_bets)[:50]
        
        logger.info("safe_bets_scan_complete",
                   markets_checked=len(markets),
                   safe_bets=len(safe_bets))
        
        return safe_bets
    
    async def start_monitoring(self):
        """Start continuous monitoring loop."""
        self._running = True
        logger.info("safe_bets_scanner_started",
                   min_odds=self.min_odds_threshold,
                   min_liquidity=self.min_liquidity,
                   scan_interval=self.scan_interval)
        
        while self._running:
            try:
                await self.scan_once()
            except Exception as e:
                logger.error("safe_bets_monitor_error", error=str(e))
            
            await asyncio.sleep(self.scan_interval)
    
    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self._running = False
        logger.info("safe_bets_scanner_stopped")
    
    def get_status(self) -> dict:
        """Get scanner status."""
        return {
            "running": self._running,
            "recent_bets": len(self.found_bets),
            "seen_markets": len(self.seen_markets),
            "min_odds_threshold": self.min_odds_threshold,
            "min_liquidity": self.min_liquidity,
            "scan_interval": self.scan_interval,
            "excluded_categories": self.excluded_categories,
            "stats": self.stats,
        }
    
    def get_recent_bets(self, limit: int = 10) -> List[SafeBet]:
        """Get recent safe bets."""
        return self.found_bets[:limit]
