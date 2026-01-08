"""
ExaSignal - Performance Tracker
Tracks signal performance for backtesting and win rate calculation.

Tables:
- signal_performance: Records each signal sent and its eventual outcome
"""
import aiosqlite
from datetime import datetime
from typing import Dict, List, Optional

from src.utils.config import Config
from src.utils.logger import logger


class PerformanceTracker:
    """
    Tracks signal performance over time.
    
    Flow:
    1. log_signal() - Called when signal is broadcast via Telegram
    2. update_resolution() - Called when market resolves (external process)
    3. get_performance_stats() - Retrieve win rate and other metrics
    """
    
    def __init__(self, db_path: str = None):
        """Initialize performance tracker."""
        self.db_path = db_path or Config.DATABASE_PATH
        self._initialized = False
    
    async def init_db(self) -> None:
        """Initialize signal_performance table."""
        if self._initialized:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS signal_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT NOT NULL,
                    market_name TEXT,
                    signal_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    signal_direction TEXT NOT NULL,
                    odds_at_signal REAL,
                    signal_score INTEGER,
                    trigger_type TEXT,
                    
                    -- Bet tracking (NEW for ROI)
                    bet_amount REAL DEFAULT 0,
                    payout REAL DEFAULT 0,
                    
                    -- Resolution data (filled later)
                    resolved_at TIMESTAMP,
                    final_outcome TEXT,
                    was_correct BOOLEAN,
                    
                    -- For analysis
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Try to add columns if table already exists (migration)
            try:
                await db.execute("ALTER TABLE signal_performance ADD COLUMN bet_amount REAL DEFAULT 0")
            except:
                pass
            try:
                await db.execute("ALTER TABLE signal_performance ADD COLUMN payout REAL DEFAULT 0")
            except:
                pass
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_signal_market 
                ON signal_performance(market_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_signal_timestamp 
                ON signal_performance(signal_timestamp DESC)
            """)
            await db.commit()
        
        self._initialized = True
        logger.info("performance_tracker_initialized")
    
    async def log_signal(
        self,
        market_id: str,
        market_name: str,
        direction: str,
        odds: float,
        score: int,
        trigger_type: str = "unknown"
    ) -> int:
        """
        Record a signal when it's sent.
        
        Returns:
            Signal ID in database
        """
        await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO signal_performance 
                   (market_id, market_name, signal_direction, odds_at_signal, 
                    signal_score, trigger_type, signal_timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (market_id, market_name, direction, odds, score, 
                 trigger_type, datetime.now().isoformat())
            )
            await db.commit()
            
            signal_id = cursor.lastrowid
            
            logger.info(
                "signal_logged",
                signal_id=signal_id,
                market_id=market_id[:20],
                direction=direction,
                score=score
            )
            
            return signal_id
    
    async def update_resolution(
        self,
        market_id: str,
        final_outcome: str  # "YES" or "NO"
    ) -> int:
        """
        Update all unresolved signals for a market when it resolves.
        
        Returns:
            Number of signals updated
        """
        await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Get unresolved signals for this market
            cursor = await db.execute(
                """SELECT id, signal_direction FROM signal_performance 
                   WHERE market_id = ? AND resolved_at IS NULL""",
                (market_id,)
            )
            rows = await cursor.fetchall()
            
            updated = 0
            for signal_id, direction in rows:
                was_correct = (direction == final_outcome)
                
                await db.execute(
                    """UPDATE signal_performance 
                       SET resolved_at = ?, final_outcome = ?, was_correct = ?
                       WHERE id = ?""",
                    (datetime.now().isoformat(), final_outcome, was_correct, signal_id)
                )
                updated += 1
            
            await db.commit()
            
            if updated > 0:
                logger.info(
                    "signals_resolved",
                    market_id=market_id[:20],
                    outcome=final_outcome,
                    count=updated
                )
            
            return updated
    
    async def get_performance_stats(self) -> Dict:
        """
        Get overall performance statistics.
        
        Returns:
            Dict with win_rate, total_signals, avg_score_winners, etc.
        """
        await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Total signals
            cursor = await db.execute("SELECT COUNT(*) FROM signal_performance")
            total = (await cursor.fetchone())[0]
            
            # Resolved signals
            cursor = await db.execute(
                "SELECT COUNT(*) FROM signal_performance WHERE resolved_at IS NOT NULL"
            )
            resolved = (await cursor.fetchone())[0]
            
            # Win rate
            cursor = await db.execute(
                "SELECT COUNT(*) FROM signal_performance WHERE was_correct = 1"
            )
            wins = (await cursor.fetchone())[0]
            
            win_rate = (wins / resolved * 100) if resolved > 0 else 0
            
            # Avg score winners vs losers
            cursor = await db.execute(
                "SELECT AVG(signal_score) FROM signal_performance WHERE was_correct = 1"
            )
            avg_score_winners = (await cursor.fetchone())[0] or 0
            
            cursor = await db.execute(
                "SELECT AVG(signal_score) FROM signal_performance WHERE was_correct = 0"
            )
            avg_score_losers = (await cursor.fetchone())[0] or 0
            
            # Pending (unresolved)
            pending = total - resolved
            
            # === NEW: Time-based stats ===
            # Last 7 days
            cursor = await db.execute(
                """SELECT COUNT(*), SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END)
                   FROM signal_performance 
                   WHERE resolved_at IS NOT NULL
                   AND signal_timestamp >= datetime('now', '-7 days')"""
            )
            row = await cursor.fetchone()
            last_7d_total, last_7d_wins = row[0] or 0, row[1] or 0
            last_7d_rate = (last_7d_wins / last_7d_total * 100) if last_7d_total > 0 else 0
            
            # Last 30 days
            cursor = await db.execute(
                """SELECT COUNT(*), SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END)
                   FROM signal_performance 
                   WHERE resolved_at IS NOT NULL
                   AND signal_timestamp >= datetime('now', '-30 days')"""
            )
            row = await cursor.fetchone()
            last_30d_total, last_30d_wins = row[0] or 0, row[1] or 0
            last_30d_rate = (last_30d_wins / last_30d_total * 100) if last_30d_total > 0 else 0
            
            return {
                "total_signals": total,
                "resolved": resolved,
                "pending": pending,
                "wins": wins,
                "losses": resolved - wins,
                "win_rate": round(win_rate, 1),
                "avg_score_winners": round(avg_score_winners, 1),
                "avg_score_losers": round(avg_score_losers, 1),
                # Time-based
                "last_7d": {
                    "resolved": last_7d_total,
                    "wins": last_7d_wins,
                    "win_rate": round(last_7d_rate, 1)
                },
                "last_30d": {
                    "resolved": last_30d_total,
                    "wins": last_30d_wins,
                    "win_rate": round(last_30d_rate, 1)
                },
            }
    
    async def get_recent_signals(self, limit: int = 10) -> List[Dict]:
        """Get most recent signals."""
        await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT market_id, market_name, signal_direction, odds_at_signal,
                          signal_score, trigger_type, signal_timestamp, 
                          final_outcome, was_correct
                   FROM signal_performance 
                   ORDER BY signal_timestamp DESC 
                   LIMIT ?""",
                (limit,)
            )
            rows = await cursor.fetchall()
            
            return [
                {
                    "market_id": row[0],
                    "market_name": row[1],
                    "direction": row[2],
                    "odds": row[3],
                    "score": row[4],
                    "trigger": row[5],
                    "timestamp": row[6],
                    "outcome": row[7],
                    "correct": row[8],
                }
                for row in rows
            ]
    
    async def get_stats_by_trigger(self) -> Dict[str, Dict]:
        """Get win rate breakdown by trigger type (whale vs news)."""
        await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            result = {}
            
            for trigger in ["whale", "news"]:
                cursor = await db.execute(
                    """SELECT COUNT(*), SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END)
                       FROM signal_performance 
                       WHERE trigger_type = ? AND resolved_at IS NOT NULL""",
                    (trigger,)
                )
                row = await cursor.fetchone()
                total, wins = row[0] or 0, row[1] or 0
                
                result[trigger] = {
                    "total": total,
                    "wins": wins,
                    "win_rate": round(wins / total * 100, 1) if total > 0 else 0
                }
            
            return result
    
    def format_stats_telegram(self, stats: Dict) -> str:
        """Format stats for Telegram message."""
        lines = [
            "📊 **Signal Performance Stats**",
            "",
            f"**Total Signals:** {stats['total_signals']}",
            f"├ Resolved: {stats['resolved']}",
            f"└ Pending: {stats['pending']}",
            "",
        ]
        
        if stats['resolved'] > 0:
            # Win rate visual
            win_pct = int(stats['win_rate'])
            bar_filled = win_pct // 10
            bar_empty = 10 - bar_filled
            bar = "█" * bar_filled + "░" * bar_empty
            
            lines.extend([
                f"**Win Rate:** {stats['win_rate']}% [{bar}]",
                f"├ ✅ Wins: {stats['wins']}",
                f"└ ❌ Losses: {stats['losses']}",
                "",
                f"**Avg Score (Winners):** {stats['avg_score_winners']}",
                f"**Avg Score (Losers):** {stats['avg_score_losers']}",
            ])
            
            # Time-based breakdown
            if 'last_7d' in stats and 'last_30d' in stats:
                lines.extend([
                    "",
                    "**📅 Win Rate Over Time:**",
                ])
                
                # 7 days
                s7 = stats['last_7d']
                if s7['resolved'] > 0:
                    lines.append(f"├ Last 7 days: {s7['win_rate']}% ({s7['wins']}/{s7['resolved']})")
                else:
                    lines.append("├ Last 7 days: _No data_")
                
                # 30 days
                s30 = stats['last_30d']
                if s30['resolved'] > 0:
                    lines.append(f"└ Last 30 days: {s30['win_rate']}% ({s30['wins']}/{s30['resolved']})")
                else:
                    lines.append("└ Last 30 days: _No data_")
        else:
            lines.append("_No resolved signals yet._")
        
        return "\n".join(lines)
    
    # ==========================================
    # ROI TRACKING (NEW)
    # ==========================================
    
    async def log_bet(
        self,
        signal_id: int,
        bet_amount: float
    ) -> bool:
        """
        Record bet amount for a signal.
        
        Call this when user actually places a bet.
        """
        await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE signal_performance SET bet_amount = ? WHERE id = ?",
                (bet_amount, signal_id)
            )
            await db.commit()
            
            logger.info("bet_logged", signal_id=signal_id, amount=bet_amount)
            return True
    
    async def update_payout(
        self,
        market_id: str,
        payout_multiplier: float = 2.0  # Typical binary market payout
    ) -> int:
        """
        Update payouts for resolved signals.
        
        For winning bets: payout = bet_amount * multiplier
        For losing bets: payout = 0
        """
        await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Update winning bets
            cursor = await db.execute(
                """UPDATE signal_performance 
                   SET payout = bet_amount * ?
                   WHERE market_id = ? AND was_correct = 1 AND bet_amount > 0""",
                (payout_multiplier, market_id)
            )
            wins_updated = cursor.rowcount
            
            # Losing bets already have payout = 0 (default)
            await db.commit()
            
            return wins_updated
    
    async def get_roi_stats(self) -> Dict:
        """
        Calculate ROI statistics.
        
        Returns:
            Dict with total_bet, total_payout, profit, roi_percent
        """
        await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Total bet amount
            cursor = await db.execute(
                "SELECT COALESCE(SUM(bet_amount), 0) FROM signal_performance WHERE bet_amount > 0"
            )
            total_bet = (await cursor.fetchone())[0]
            
            # Total payout (resolved only)
            cursor = await db.execute(
                """SELECT COALESCE(SUM(payout), 0) FROM signal_performance 
                   WHERE resolved_at IS NOT NULL AND bet_amount > 0"""
            )
            total_payout = (await cursor.fetchone())[0]
            
            # Pending bets (not resolved)
            cursor = await db.execute(
                """SELECT COALESCE(SUM(bet_amount), 0) FROM signal_performance 
                   WHERE resolved_at IS NULL AND bet_amount > 0"""
            )
            pending_bet = (await cursor.fetchone())[0]
            
            # Count bets
            cursor = await db.execute(
                "SELECT COUNT(*) FROM signal_performance WHERE bet_amount > 0"
            )
            total_bets = (await cursor.fetchone())[0]
            
            # Calculate profit and ROI
            resolved_bet = total_bet - pending_bet
            profit = total_payout - resolved_bet
            roi_percent = (profit / resolved_bet * 100) if resolved_bet > 0 else 0
            
            return {
                "total_bet": round(total_bet, 2),
                "total_payout": round(total_payout, 2),
                "pending_bet": round(pending_bet, 2),
                "profit": round(profit, 2),
                "roi_percent": round(roi_percent, 1),
                "total_bets": total_bets
            }
    
    def format_roi_telegram(self, roi_stats: Dict) -> str:
        """Format ROI stats for Telegram."""
        profit = roi_stats['profit']
        roi = roi_stats['roi_percent']
        
        # Profit emoji
        if profit > 0:
            emoji = "📈"
            status = "🟢"
        elif profit < 0:
            emoji = "📉"
            status = "🔴"
        else:
            emoji = "➖"
            status = "⚪"
        
        lines = [
            f"{emoji} **ROI Tracking**",
            "",
            f"**💰 Total Bet:** ${roi_stats['total_bet']:.2f}",
            f"**💵 Total Payout:** ${roi_stats['total_payout']:.2f}",
            f"**⏳ Pending:** ${roi_stats['pending_bet']:.2f}",
            "",
            f"**{status} Profit:** ${profit:+.2f}",
            f"**📊 ROI:** {roi:+.1f}%",
            "",
            f"_Based on {roi_stats['total_bets']} bets_"
        ]
        
        return "\n".join(lines)
