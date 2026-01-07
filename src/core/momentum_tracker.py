"""
ExaSignal - Momentum Tracker
Tracks odds velocity to identify fast-moving markets.

Momentum Score (0-10):
- 1h change: weight 10x (most important)
- 6h change: weight 5x
- 24h change: weight 2x
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.utils.logger import logger


class MomentumTracker:
    """
    Tracks market odds changes over time to calculate momentum.
    
    High momentum = market is moving fast (good confirmation for news signals)
    Low momentum = market ignoring news (potential false positive)
    """
    
    def __init__(self, max_history_hours: int = 24):
        """Initialize tracker with configurable history window."""
        self._odds_history: Dict[str, List[Tuple[datetime, float]]] = {}
        self._max_history_hours = max_history_hours
    
    def track_odds(self, market_id: str, current_odds: float) -> None:
        """
        Store current odds for a market.
        
        Args:
            market_id: Market identifier
            current_odds: Current YES probability (0-100)
        """
        if market_id not in self._odds_history:
            self._odds_history[market_id] = []
        
        now = datetime.now()
        self._odds_history[market_id].append((now, current_odds))
        
        # Cleanup old data
        self._cleanup(market_id)
    
    def _cleanup(self, market_id: str) -> None:
        """Remove data older than max_history_hours."""
        cutoff = datetime.now() - timedelta(hours=self._max_history_hours)
        self._odds_history[market_id] = [
            (ts, odds) for ts, odds in self._odds_history[market_id]
            if ts > cutoff
        ]
    
    def get_momentum_score(self, market_id: str) -> int:
        """
        Calculate momentum score (0-10) based on odds velocity.
        
        Returns:
            0: No data or no movement
            1-3: Slow movement
            4-6: Moderate movement
            7-10: Fast movement (high conviction)
        """
        if market_id not in self._odds_history:
            return 0
        
        history = self._odds_history[market_id]
        if len(history) < 2:
            return 0
        
        now = datetime.now()
        current_odds = history[-1][1]
        
        # Calculate changes at different time windows
        change_1h = self._get_change(market_id, hours_ago=1)
        change_6h = self._get_change(market_id, hours_ago=6)
        change_24h = self._get_change(market_id, hours_ago=24)
        
        # Weighted sum (recent changes matter more)
        weighted_change = (
            abs(change_1h) * 10 +   # 1h change weighted 10x
            abs(change_6h) * 5 +    # 6h change weighted 5x
            abs(change_24h) * 2     # 24h change weighted 2x
        )
        
        # Normalize to 0-10 scale
        # A 10% change in 1h = 100 points → score 10
        # A 5% change in 6h = 25 points → score ~2.5
        momentum_score = min(int(weighted_change / 10), 10)
        
        logger.debug(
            "momentum_calculated",
            market_id=market_id[:20],
            change_1h=change_1h,
            change_6h=change_6h,
            change_24h=change_24h,
            score=momentum_score
        )
        
        return momentum_score
    
    def _get_change(self, market_id: str, hours_ago: int) -> float:
        """
        Get odds change from X hours ago to now.
        
        Returns:
            Difference in percentage points (can be negative)
        """
        history = self._odds_history.get(market_id, [])
        if not history:
            return 0.0
        
        cutoff = datetime.now() - timedelta(hours=hours_ago)
        current_odds = history[-1][1]
        
        # Find closest reading to cutoff time
        past_reading = None
        for ts, odds in history:
            if ts <= cutoff:
                past_reading = odds
        
        if past_reading is None:
            return 0.0
        
        return current_odds - past_reading
    
    def get_momentum_boost(self, market_id: str) -> int:
        """
        Calculate score boost/penalty based on momentum.
        
        Returns:
            +10: Fast movement (high conviction)
            +5: Moderate movement
            -5: No movement (market ignoring signal)
        """
        score = self.get_momentum_score(market_id)
        
        if score >= 7:
            return 10  # Fast movement = boost
        elif score >= 4:
            return 5   # Moderate movement
        else:
            return -5  # No movement = penalty
    
    def get_momentum_display(self, market_id: str) -> Tuple[str, str]:
        """
        Get display strings for Telegram message.
        
        Returns:
            (bar_visual, description)
        """
        score = self.get_momentum_score(market_id)
        
        # Visual bar
        filled = score
        empty = 10 - score
        bar = "█" * filled + "░" * empty
        
        # Description
        if score >= 7:
            desc = "🚀 Fast movement"
        elif score >= 4:
            desc = "📈 Moderate movement"
        else:
            desc = "😴 Slow/no movement"
        
        return f"[{bar}]", desc
    
    def clear_market(self, market_id: str) -> None:
        """Clear history for a specific market."""
        if market_id in self._odds_history:
            del self._odds_history[market_id]
    
    def get_stats(self) -> Dict:
        """Get tracker statistics."""
        return {
            "markets_tracked": len(self._odds_history),
            "total_datapoints": sum(
                len(h) for h in self._odds_history.values()
            ),
        }
