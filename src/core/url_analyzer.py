"""
ExaSignal - URL Analyzer
Analyzes Polymarket URLs and provides instant research/odds analysis.

Features:
- Parse Polymarket URLs to extract event slug
- Fetch market data from Gamma API
- Show candidates with odds
- Provide quick analysis
"""
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import httpx

from src.utils.logger import logger


@dataclass
class MarketAnalysis:
    """Analysis result for a Polymarket event."""
    event_title: str
    event_description: str
    end_date: Optional[datetime]
    total_volume: float
    total_liquidity: float
    candidates: List[Dict]  # [{name, odds, volume_24h, change_week}]
    recommendation: Optional[str] = None
    

class URLAnalyzer:
    """
    Analyzes Polymarket URLs to provide instant insights.
    
    Usage:
        analyzer = URLAnalyzer()
        result = await analyzer.analyze("https://polymarket.com/event/portugal-presidential-election")
    """
    
    GAMMA_API_BASE = "https://gamma-api.polymarket.com"
    URL_PATTERN = re.compile(r"polymarket\.com/event/([^?/]+)")
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    def extract_slug(self, url: str) -> Optional[str]:
        """Extract event slug from Polymarket URL."""
        match = self.URL_PATTERN.search(url)
        return match.group(1) if match else None
    
    async def analyze(self, url: str) -> Optional[MarketAnalysis]:
        """
        Analyze a Polymarket URL.
        
        Args:
            url: Full Polymarket URL or just event slug
            
        Returns:
            MarketAnalysis with odds and insights
        """
        # Extract slug
        slug = self.extract_slug(url) if "polymarket.com" in url else url
        if not slug:
            logger.warning("url_analysis_no_slug", url=url)
            return None
        
        try:
            # Fetch from Gamma API
            response = await self.client.get(
                f"{self.GAMMA_API_BASE}/events",
                params={"slug": slug}
            )
            response.raise_for_status()
            
            events = response.json()
            if not events:
                logger.warning("url_analysis_no_events", slug=slug)
                return None
            
            event = events[0]
            
            # Parse end date
            end_date = None
            if event.get("endDate"):
                try:
                    end_date = datetime.fromisoformat(event["endDate"].replace("Z", "+00:00"))
                except:
                    pass
            
            # Parse candidates/markets
            candidates = []
            for market in event.get("markets", []):
                if not market.get("active"):
                    continue
                
                # Parse odds (YES price)
                odds = 0.0
                price_str = market.get("outcomePrices", "[]")
                try:
                    import json
                    prices = json.loads(price_str)
                    if prices:
                        odds = float(prices[0])
                except:
                    pass
                
                if odds < 0.001:  # Skip negligible candidates
                    continue
                
                candidates.append({
                    "name": market.get("groupItemTitle", market.get("question", "Unknown")),
                    "odds": odds * 100,  # Convert to percentage
                    "volume_24h": market.get("volume24hr", 0),
                    "change_week": market.get("oneWeekPriceChange", 0) * 100 if market.get("oneWeekPriceChange") else 0,
                    "liquidity": market.get("liquidityNum", 0)
                })
            
            # Sort by odds (highest first)
            candidates.sort(key=lambda x: x["odds"], reverse=True)
            
            # Generate recommendation
            recommendation = self._generate_recommendation(candidates, end_date)
            
            analysis = MarketAnalysis(
                event_title=event.get("title", "Unknown"),
                event_description=event.get("description", "")[:200],
                end_date=end_date,
                total_volume=event.get("volume", 0),
                total_liquidity=event.get("liquidity", 0),
                candidates=candidates[:10],  # Top 10
                recommendation=recommendation
            )
            
            logger.info("url_analysis_complete", slug=slug, candidates=len(candidates))
            return analysis
            
        except Exception as e:
            logger.error("url_analysis_error", slug=slug, error=str(e))
            return None
    
    def _generate_recommendation(self, candidates: List[Dict], end_date: Optional[datetime]) -> str:
        """Generate a simple recommendation based on odds."""
        if not candidates:
            return "⚠️ No active candidates found."
        
        top = candidates[0]
        
        # Time until event
        days_left = "?"
        if end_date:
            delta = end_date.replace(tzinfo=None) - datetime.now()
            days_left = max(0, delta.days)
        
        # Check for value bets (high weekly movement)
        movers = [c for c in candidates if abs(c.get("change_week", 0)) > 5]
        
        lines = []
        
        # Favorite
        if top["odds"] > 50:
            lines.append(f"🏆 Clear favorite: {top['name']} ({top['odds']:.1f}%)")
        else:
            lines.append(f"🤔 Competitive race - no clear favorite")
        
        # Time
        lines.append(f"⏰ {days_left} days until resolution")
        
        # Movers
        if movers:
            for m in movers[:2]:
                direction = "📈" if m["change_week"] > 0 else "📉"
                lines.append(f"{direction} {m['name']}: {m['change_week']:+.1f}% this week")
        
        return "\n".join(lines)
    
    def format_telegram(self, analysis: MarketAnalysis) -> str:
        """Format analysis for Telegram."""
        lines = [
            f"🔍 **{analysis.event_title}**",
            "",
            f"💰 Volume: ${analysis.total_volume:,.0f}",
            f"💧 Liquidity: ${analysis.total_liquidity:,.0f}",
            ""
        ]
        
        # Top candidates
        lines.append("**📊 Top Candidates:**")
        for i, c in enumerate(analysis.candidates[:5], 1):
            change = ""
            if c.get("change_week"):
                sign = "+" if c["change_week"] > 0 else ""
                change = f" ({sign}{c['change_week']:.1f}% 7d)"
            lines.append(f"{i}. {c['name']}: **{c['odds']:.1f}%**{change}")
        
        # Recommendation
        if analysis.recommendation:
            lines.extend(["", "**💡 Quick Analysis:**", analysis.recommendation])
        
        # Position sizing reminder
        lines.extend([
            "",
            "💵 _Suggested bet: $1.50_",
            "📍 _Use /upcoming for timing_"
        ])
        
        return "\n".join(lines)
    
    async def close(self):
        """Close client connection."""
        if self._client:
            await self._client.aclose()
