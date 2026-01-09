"""
ExaSignal - Correlation Arbitrage Detector
Detects mispricings between correlated markets on Polymarket.

Strategy: SwissTony-inspired
If A implies B, but odds(A) ≠ odds(B), there's arbitrage.
Example: "Trump wins" at 60% but "Republican wins" at 55% = mispricing

Flow:
1. Fetch active markets from Polymarket
2. Use AI to identify correlated pairs
3. Monitor odds continuously
4. Alert when divergence exceeds threshold
"""
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Tuple
from datetime import datetime, timezone
import json

from src.api.gamma_client import GammaClient
from src.api.groq_client import GroqClient
from src.utils.logger import logger


@dataclass
class CorrelatedPair:
    """A pair of correlated markets."""
    market_a_id: str
    market_a_name: str
    market_b_id: str
    market_b_name: str
    correlation_type: str  # "implies", "inverse", "same_outcome"
    expected_relationship: str  # "A >= B", "A == B", "A + B == 100"
    category: str = ""
    
    def to_dict(self) -> dict:
        return {
            "market_a_id": self.market_a_id,
            "market_a_name": self.market_a_name,
            "market_b_id": self.market_b_id,
            "market_b_name": self.market_b_name,
            "correlation_type": self.correlation_type,
            "expected_relationship": self.expected_relationship,
            "category": self.category,
        }


@dataclass
class ArbitrageOpportunity:
    """Detected arbitrage opportunity."""
    pair: CorrelatedPair
    odds_a: float
    odds_b: float
    divergence: float  # Percentage points difference
    expected_divergence: float  # What it should be
    edge: float  # Potential profit percentage
    recommendation: str  # "BUY A, SELL B" etc
    confidence: int  # 0-100
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> dict:
        return {
            "pair": self.pair.to_dict(),
            "odds_a": self.odds_a,
            "odds_b": self.odds_b,
            "divergence": self.divergence,
            "expected_divergence": self.expected_divergence,
            "edge": self.edge,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }
    
    def to_telegram(self) -> str:
        """Format for Telegram notification."""
        emoji = "🔥" if self.edge > 5 else "⚡" if self.edge > 2 else "💡"
        
        return f"""
{emoji} *ARBITRAGE OPPORTUNITY*

📊 *Market A:* {self.pair.market_a_name[:50]}...
   Odds: {self.odds_a:.1f}%

📊 *Market B:* {self.pair.market_b_name[:50]}...
   Odds: {self.odds_b:.1f}%

🔗 *Correlation:* {self.pair.correlation_type}
📏 *Expected:* {self.pair.expected_relationship}

⚠️ *Divergence:* {self.divergence:.1f}% (expected ~{self.expected_divergence:.1f}%)
💰 *Potential Edge:* {self.edge:.1f}%

🎯 *Action:* {self.recommendation}
📈 *Confidence:* {self.confidence}%

⏰ {self.timestamp[:19]}
"""


class CorrelationDetector:
    """
    Detects arbitrage opportunities between correlated markets.
    
    Uses AI to identify correlations and monitors for mispricings.
    """
    
    def __init__(
        self,
        gamma: Optional[GammaClient] = None,
        groq: Optional[GroqClient] = None,
        callback: Optional[Callable] = None,
        min_edge: float = 2.0,  # Minimum edge to alert (%)
        min_confidence: int = 70,
        scan_interval: int = 300,  # 5 minutes
    ):
        self.gamma = gamma or GammaClient()
        self.groq = groq or GroqClient()
        self.callback = callback
        self.min_edge = min_edge
        self.min_confidence = min_confidence
        self.scan_interval = scan_interval
        
        self.known_pairs: List[CorrelatedPair] = []
        self.recent_opportunities: List[ArbitrageOpportunity] = []
        self._running = False
        
        # Stats
        self.stats = {
            "scans": 0,
            "pairs_found": 0,
            "opportunities_found": 0,
        }
    
    async def fetch_active_markets(self, limit: int = 200) -> List[dict]:
        """Fetch active markets from Polymarket."""
        import httpx
        
        markets = []
        
        async with httpx.AsyncClient(
            base_url="https://gamma-api.polymarket.com",
            timeout=60
        ) as client:
            # Fetch events
            r = await client.get("/events", params={
                "limit": limit,
                "active": "true",
                "order": "volume",
                "ascending": "false"
            })
            
            if r.status_code == 200:
                events = r.json()
                for e in events:
                    markets.append({
                        "id": e.get("slug", e.get("id", "")),
                        "name": e.get("title", ""),
                        "category": self._detect_category(e.get("title", "")),
                        "volume": e.get("volume", 0),
                        "description": e.get("description", "")[:200],
                    })
        
        logger.info("markets_fetched", count=len(markets))
        return markets
    
    def _detect_category(self, title: str) -> str:
        """Detect market category from title."""
        title_lower = title.lower()
        
        if any(w in title_lower for w in ["trump", "biden", "election", "president", "congress", "governor"]):
            return "Politics"
        elif any(w in title_lower for w in ["bitcoin", "ethereum", "crypto", "btc", "eth"]):
            return "Crypto"
        elif any(w in title_lower for w in ["nba", "nfl", "mlb", "soccer", "game", "match", "win"]):
            return "Sports"
        elif any(w in title_lower for w in ["ai", "openai", "gpt", "claude", "gemini"]):
            return "AI"
        else:
            return "Other"
    
    async def find_correlated_pairs(self, markets: List[dict]) -> List[CorrelatedPair]:
        """Use AI to identify correlated market pairs."""
        
        # Group by category for better matching
        by_category: Dict[str, List[dict]] = {}
        for m in markets:
            cat = m.get("category", "Other")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(m)
        
        all_pairs = []
        
        for category, cat_markets in by_category.items():
            if len(cat_markets) < 2:
                continue
            
            # Prepare market list for AI
            market_list = "\n".join([
                f"- ID: {m['id']}, Name: {m['name']}"
                for m in cat_markets[:30]  # Limit to top 30 per category
            ])
            
            prompt = f"""Analyze these Polymarket prediction markets and identify PAIRS that are LOGICALLY CORRELATED.

Category: {category}

Markets:
{market_list}

Find pairs where:
1. IMPLIES: If A happens, B must also happen (e.g., "Trump wins presidency" implies "Republican wins presidency")
2. INVERSE: If A happens, B cannot happen (e.g., "Biden wins" vs "Trump wins" in same race)
3. SAME_OUTCOME: Both markets are asking about the same underlying event with different framing

For each correlated pair, output JSON:
{{
    "pairs": [
        {{
            "market_a_id": "...",
            "market_a_name": "...",
            "market_b_id": "...", 
            "market_b_name": "...",
            "correlation_type": "implies|inverse|same_outcome",
            "expected_relationship": "A >= B" or "A == B" or "A + B == 100",
            "reasoning": "..."
        }}
    ]
}}

Only include pairs with STRONG logical correlation. Output ONLY valid JSON."""

            try:
                response = await self.groq.chat([
                    {"role": "system", "content": "You are an expert at identifying correlated prediction markets for arbitrage detection. Output only valid JSON."},
                    {"role": "user", "content": prompt}
                ])
                
                # Parse response
                content = response.strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                data = json.loads(content)
                pairs = data.get("pairs", [])
                
                for p in pairs:
                    all_pairs.append(CorrelatedPair(
                        market_a_id=p.get("market_a_id", ""),
                        market_a_name=p.get("market_a_name", ""),
                        market_b_id=p.get("market_b_id", ""),
                        market_b_name=p.get("market_b_name", ""),
                        correlation_type=p.get("correlation_type", "implies"),
                        expected_relationship=p.get("expected_relationship", "A == B"),
                        category=category,
                    ))
                
                logger.info("pairs_found", category=category, count=len(pairs))
                
            except Exception as e:
                logger.error("pair_detection_error", category=category, error=str(e))
        
        self.known_pairs = all_pairs
        self.stats["pairs_found"] = len(all_pairs)
        return all_pairs
    
    async def check_pair_for_arbitrage(self, pair: CorrelatedPair) -> Optional[ArbitrageOpportunity]:
        """Check a specific pair for arbitrage opportunity."""
        
        # Get current odds for both markets
        odds_a = await self.gamma.get_market_odds(pair.market_a_id)
        odds_b = await self.gamma.get_market_odds(pair.market_b_id)
        
        if odds_a is None or odds_b is None:
            return None
        
        # Calculate divergence based on relationship type
        divergence = 0.0
        expected_divergence = 0.0
        edge = 0.0
        recommendation = ""
        
        if pair.correlation_type == "implies":
            # If A implies B, then odds(A) <= odds(B)
            # Divergence = how much A exceeds B (should be negative or 0)
            divergence = odds_a - odds_b
            expected_divergence = 0.0
            
            if divergence > self.min_edge:
                # A is overpriced relative to B
                edge = divergence
                recommendation = f"BUY NO on {pair.market_a_name[:20]}... OR BUY YES on {pair.market_b_name[:20]}..."
        
        elif pair.correlation_type == "inverse":
            # If A and B are mutually exclusive, A + B <= 100
            combined = odds_a + odds_b
            divergence = combined - 100
            expected_divergence = 0.0
            
            if divergence > self.min_edge:
                # Combined odds > 100%, there's arb
                edge = divergence
                recommendation = f"BUY NO on BOTH markets"
            elif divergence < -self.min_edge:
                # Combined odds < 100%, both underpriced
                edge = abs(divergence)
                recommendation = f"BUY YES on BOTH markets"
        
        elif pair.correlation_type == "same_outcome":
            # Same event, odds should be equal
            divergence = abs(odds_a - odds_b)
            expected_divergence = 0.0
            
            if divergence > self.min_edge:
                edge = divergence
                if odds_a > odds_b:
                    recommendation = f"BUY YES on {pair.market_b_name[:20]}... (cheaper), SELL on {pair.market_a_name[:20]}..."
                else:
                    recommendation = f"BUY YES on {pair.market_a_name[:20]}... (cheaper), SELL on {pair.market_b_name[:20]}..."
        
        if edge < self.min_edge:
            return None
        
        # Calculate confidence based on edge size and category reliability
        confidence = min(95, int(50 + edge * 5))
        if pair.category == "Politics":
            confidence += 10  # Politics correlations are stronger
        elif pair.category == "Sports":
            confidence -= 10  # Sports can have more variance
        
        if confidence < self.min_confidence:
            return None
        
        opportunity = ArbitrageOpportunity(
            pair=pair,
            odds_a=odds_a,
            odds_b=odds_b,
            divergence=divergence,
            expected_divergence=expected_divergence,
            edge=edge,
            recommendation=recommendation,
            confidence=confidence,
        )
        
        return opportunity
    
    async def scan_once(self) -> List[ArbitrageOpportunity]:
        """Run a single scan for arbitrage opportunities."""
        logger.info("arbitrage_scan_starting")
        self.stats["scans"] += 1
        
        opportunities = []
        
        # If no known pairs, discover them first
        if not self.known_pairs:
            markets = await self.fetch_active_markets()
            await self.find_correlated_pairs(markets)
        
        # Check each pair
        for pair in self.known_pairs:
            try:
                opp = await self.check_pair_for_arbitrage(pair)
                if opp:
                    opportunities.append(opp)
                    self.stats["opportunities_found"] += 1
                    
                    # Call callback
                    if self.callback:
                        try:
                            await self.callback(opp)
                        except Exception as e:
                            logger.error("arb_callback_error", error=str(e))
                    
                    logger.info("arbitrage_found",
                               edge=opp.edge,
                               pair_a=pair.market_a_name[:30],
                               pair_b=pair.market_b_name[:30])
                
                # Small delay between checks
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error("pair_check_error", 
                           pair=pair.market_a_name[:30],
                           error=str(e))
        
        # Keep recent opportunities (last 20)
        self.recent_opportunities = (opportunities + self.recent_opportunities)[:20]
        
        logger.info("arbitrage_scan_complete",
                   pairs_checked=len(self.known_pairs),
                   opportunities=len(opportunities))
        
        return opportunities
    
    async def start_monitoring(self):
        """Start continuous monitoring loop."""
        self._running = True
        logger.info("correlation_detector_started",
                   min_edge=self.min_edge,
                   scan_interval=self.scan_interval)
        
        while self._running:
            try:
                await self.scan_once()
            except Exception as e:
                logger.error("monitor_error", error=str(e))
            
            await asyncio.sleep(self.scan_interval)
    
    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self._running = False
        logger.info("correlation_detector_stopped")
    
    async def refresh_pairs(self):
        """Force refresh of known pairs."""
        self.known_pairs = []
        markets = await self.fetch_active_markets()
        await self.find_correlated_pairs(markets)
        return self.known_pairs
    
    def get_status(self) -> dict:
        """Get detector status."""
        return {
            "running": self._running,
            "known_pairs": len(self.known_pairs),
            "recent_opportunities": len(self.recent_opportunities),
            "min_edge": self.min_edge,
            "scan_interval": self.scan_interval,
            "stats": self.stats,
        }
