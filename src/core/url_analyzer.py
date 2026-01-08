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
            is_binary = len(event.get("markets", [])) == 1  # Single market = binary Yes/No
            
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
                
                # Get candidate name
                if is_binary:
                    # Binary market: use "Yes" as name, show question
                    name = "Yes"
                else:
                    # Multi-candidate: use groupItemTitle or question
                    name = market.get("groupItemTitle") or market.get("question", "Unknown")
                    # Clean up name if it's a question
                    if name.startswith("Will "):
                        name = name.replace("Will ", "").split(" win")[0].strip()
                
                candidates.append({
                    "name": name,
                    "odds": odds * 100,  # Convert to percentage
                    "volume_24h": market.get("volume24hr", 0),
                    "change_week": market.get("oneWeekPriceChange", 0) * 100 if market.get("oneWeekPriceChange") else 0,
                    "liquidity": market.get("liquidityNum", 0)
                })
            
            # Sort by odds (highest first)
            candidates.sort(key=lambda x: x["odds"], reverse=True)
            
            # Generate recommendation
            recommendation = self._generate_recommendation(candidates, end_date, is_binary)
            
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
    
    def _generate_recommendation(self, candidates: List[Dict], end_date: Optional[datetime], is_binary: bool = False) -> str:
        """Generate a recommendation including WHO to bet on."""
        if not candidates:
            return "⚠️ No active candidates found."
        
        top = candidates[0]
        
        # Time until event
        days_left = "?"
        if end_date:
            delta = end_date.replace(tzinfo=None) - datetime.now()
            days_left = max(0, delta.days)
        
        lines = []
        
        # Binary market handling
        if is_binary:
            yes_odds = top["odds"]
            no_odds = 100 - yes_odds
            
            lines.append(f"📊 **Yes**: {yes_odds:.1f}% | **No**: {no_odds:.1f}%")
            lines.append(f"⏰ {days_left} days until resolution")
            
            # Suggest based on odds
            lines.append("")
            lines.append("**🎯 BET SUGGESTION:**")
            
            change = top.get("change_week", 0)
            
            if yes_odds > 50:
                payout = 1.50 * (100 / yes_odds)
                lines.append(f"→ **YES** at {yes_odds:.1f}%")
                lines.append(f"  🛡️ Market favorite")
                lines.append(f"  $1.50 bet → ${payout:.2f} if wins")
            elif no_odds > 50:
                payout = 1.50 * (100 / no_odds)
                lines.append(f"→ **NO** at {no_odds:.1f}%")
                lines.append(f"  🛡️ Market favorite")
                lines.append(f"  $1.50 bet → ${payout:.2f} if wins")
            else:
                if change > 5:
                    payout = 1.50 * (100 / yes_odds)
                    lines.append(f"→ **YES** at {yes_odds:.1f}%")
                    lines.append(f"  📈 Momentum rising (+{change:.1f}% 7d)")
                    lines.append(f"  $1.50 bet → ${payout:.2f} if wins")
                elif change < -5:
                    payout = 1.50 * (100 / no_odds)
                    lines.append(f"→ **NO** at {no_odds:.1f}%")
                    lines.append(f"  📈 Momentum falling (Yes {change:.1f}% 7d)")
                    lines.append(f"  $1.50 bet → ${payout:.2f} if wins")
                else:
                    lines.append(f"→ **SKIP** - 50/50 odds, wait for clearer signal")
            
            return "\n".join(lines)
        
        # Multi-candidate market handling
        # Find value bets
        risers = [c for c in candidates if c.get("change_week", 0) > 5 and c["odds"] < 40]
        stable_fav = [c for c in candidates if c["odds"] > 40 and abs(c.get("change_week", 0)) < 5]
        
        # Favorite status
        if top["odds"] > 50:
            lines.append(f"🏆 Favorite: {top['name']} ({top['odds']:.1f}%)")
        else:
            lines.append(f"🤔 Close race - no clear favorite")
        
        lines.append(f"⏰ {days_left} days until resolution")
        
        # SPECIFIC BET RECOMMENDATION
        lines.append("")
        lines.append("**🎯 BET SUGGESTION:**")
        
        best_bet = None
        bet_reason = ""
        
        # Priority 1: Rising underdog with momentum
        if risers:
            best_bet = risers[0]
            bet_reason = f"📈 MOMENTUM PLAY - up {best_bet['change_week']:+.1f}% this week"
        # Priority 2: Stable favorite
        elif stable_fav:
            best_bet = stable_fav[0]
            bet_reason = "🛡️ SAFE PLAY - stable favorite"
        # Priority 3: Top candidate
        else:
            best_bet = top
            bet_reason = "📊 LEADING ODDS"
        
        if best_bet:
            payout = 1.50 * (100 / best_bet["odds"]) if best_bet["odds"] > 0 else 0
            lines.append(f"→ **{best_bet['name']}** at {best_bet['odds']:.1f}%")
            lines.append(f"  {bet_reason}")
            lines.append(f"  $1.50 bet → ${payout:.2f} if wins")
        
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
