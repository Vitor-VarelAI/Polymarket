"""
ExaSignal - Smart Money Service
Tracks top traders from Polymarket leaderboard for smart money scoring.

Based on poly-sdk SmartMoneyService concept.
API: https://data-api.polymarket.com/v1/leaderboard
"""
import httpx
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

from src.utils.logger import logger


@dataclass
class SmartTrader:
    """A trader from the leaderboard with smart money scoring."""
    address: str
    rank: int
    pnl: float  # Profit/Loss in USD
    volume: float  # Total volume traded
    win_rate: float = 0.0
    markets_traded: int = 0
    
    @property
    def smart_score(self) -> int:
        """
        Calculate smart score 0-100 based on:
        - Rank (top 10 = high score)
        - PnL (profitable = higher)
        - Win rate
        """
        score = 0
        
        # Rank contribution (max 40 points)
        if self.rank <= 10:
            score += 40
        elif self.rank <= 25:
            score += 30
        elif self.rank <= 50:
            score += 20
        elif self.rank <= 100:
            score += 10
        
        # PnL contribution (max 30 points)
        if self.pnl >= 100_000:
            score += 30
        elif self.pnl >= 50_000:
            score += 25
        elif self.pnl >= 10_000:
            score += 20
        elif self.pnl >= 1_000:
            score += 10
        elif self.pnl > 0:
            score += 5
        
        # Win rate contribution (max 30 points)
        if self.win_rate >= 70:
            score += 30
        elif self.win_rate >= 60:
            score += 20
        elif self.win_rate >= 50:
            score += 10
        
        return min(score, 100)
    
    @property
    def tier(self) -> str:
        """Get tier based on smart score."""
        s = self.smart_score
        if s >= 80:
            return "🦈 SHARK"
        elif s >= 60:
            return "🐋 WHALE"
        elif s >= 40:
            return "🐬 DOLPHIN"
        else:
            return "🐟 FISH"


class SmartMoneyService:
    """
    Service to track and identify smart money traders.
    
    Usage:
        smart = SmartMoneyService()
        await smart.refresh_leaderboard()
        
        # Check if wallet is smart money
        is_smart = smart.is_smart_money("0x123...")
        score = smart.get_smart_score("0x123...")
    """
    
    LEADERBOARD_URL = "https://data-api.polymarket.com/v1/leaderboard"
    CACHE_TTL_HOURS = 1  # Refresh every hour
    
    def __init__(self):
        """Initialize smart money service."""
        self._smart_wallets: Dict[str, SmartTrader] = {}
        self._smart_addresses: Set[str] = set()
        self._last_refresh: Optional[datetime] = None
        self._top_n = 100  # Track top 100 traders
    
    async def refresh_leaderboard(self, force: bool = False) -> int:
        """
        Fetch latest leaderboard data.
        
        Returns:
            Number of smart wallets loaded
        """
        # Check cache
        if not force and self._last_refresh:
            age = datetime.now() - self._last_refresh
            if age < timedelta(hours=self.CACHE_TTL_HOURS):
                return len(self._smart_wallets)
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Fetch by PnL (most profitable)
                response = await client.get(
                    self.LEADERBOARD_URL,
                    params={
                        "timePeriod": "ALL",
                        "orderBy": "PNL",
                        "limit": self._top_n
                    }
                )
                
                if response.status_code != 200:
                    logger.warning("leaderboard_fetch_failed", status=response.status_code)
                    return len(self._smart_wallets)
                
                data = response.json()
                traders = data if isinstance(data, list) else data.get("traders", [])
                
                # Clear and rebuild
                self._smart_wallets.clear()
                self._smart_addresses.clear()
                
                for i, trader in enumerate(traders):
                    address = trader.get("address", "").lower()
                    if not address:
                        continue
                    
                    smart_trader = SmartTrader(
                        address=address,
                        rank=i + 1,
                        pnl=float(trader.get("pnl", 0)),
                        volume=float(trader.get("volume", 0)),
                        win_rate=float(trader.get("winRate", 0)) * 100 if trader.get("winRate") else 0,
                        markets_traded=int(trader.get("marketsTraded", 0))
                    )
                    
                    self._smart_wallets[address] = smart_trader
                    self._smart_addresses.add(address)
                
                self._last_refresh = datetime.now()
                
                logger.info(
                    "leaderboard_refreshed",
                    count=len(self._smart_wallets),
                    top_pnl=traders[0].get("pnl") if traders else 0
                )
                
                return len(self._smart_wallets)
                
        except Exception as e:
            logger.error("leaderboard_refresh_error", error=str(e))
            return len(self._smart_wallets)
    
    def is_smart_money(self, address: str) -> bool:
        """Check if address is in smart money list."""
        return address.lower() in self._smart_addresses
    
    def get_smart_score(self, address: str) -> int:
        """Get smart score for address (0 if not in list)."""
        trader = self._smart_wallets.get(address.lower())
        return trader.smart_score if trader else 0
    
    def get_trader(self, address: str) -> Optional[SmartTrader]:
        """Get full trader info."""
        return self._smart_wallets.get(address.lower())
    
    def get_top_traders(self, limit: int = 10) -> List[SmartTrader]:
        """Get top N traders by rank."""
        traders = sorted(self._smart_wallets.values(), key=lambda t: t.rank)
        return traders[:limit]
    
    def enrich_whale_profile(self, wallet_address: str, profile: dict) -> dict:
        """
        Enrich whale profile with smart money data.
        
        Call this when building WhaleProfile to add smart score.
        """
        trader = self.get_trader(wallet_address)
        
        if trader:
            profile["smart_score"] = trader.smart_score
            profile["smart_tier"] = trader.tier
            profile["leaderboard_rank"] = trader.rank
            profile["leaderboard_pnl"] = trader.pnl
            profile["is_smart_money"] = True
        else:
            profile["smart_score"] = 0
            profile["smart_tier"] = "🐟 UNKNOWN"
            profile["is_smart_money"] = False
        
        return profile
    
    async def get_status(self) -> Dict:
        """Get service status."""
        return {
            "smart_wallets_tracked": len(self._smart_wallets),
            "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
            "cache_ttl_hours": self.CACHE_TTL_HOURS,
            "top_trader_pnl": self.get_top_traders(1)[0].pnl if self._smart_wallets else 0
        }
