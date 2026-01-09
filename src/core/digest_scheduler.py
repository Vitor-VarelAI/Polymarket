"""
ExaSignal - Digest Scheduler
Schedules and curates value bet digests at 11:00 and 20:00.

Uses LLM to select top 4-5 picks with reasoning.
"""
import asyncio
from dataclasses import dataclass
from typing import List, Optional, Callable
from datetime import datetime, timezone, time
import json

from src.core.value_bets_scanner import ValueBet, ValueBetsScanner
from src.api.groq_client import GroqClient
from src.utils.logger import logger


@dataclass
class CuratedPick:
    """A curated pick with LLM reasoning."""
    bet: ValueBet
    reasoning: str
    rank: int


class DigestScheduler:
    """
    Schedules digest delivery at specific times.
    Uses LLM to curate top picks.
    """
    
    # Digest times in UTC (Portugal winter time = UTC)
    DIGEST_TIMES = [
        time(11, 0),  # 11:00
        time(20, 0),  # 20:00
    ]
    
    def __init__(
        self,
        scanner: ValueBetsScanner,
        groq: Optional[GroqClient] = None,
        send_callback: Optional[Callable] = None,
        picks_per_digest: int = 4,
    ):
        self.scanner = scanner
        self.groq = groq or GroqClient()
        self.send_callback = send_callback
        self.picks_per_digest = picks_per_digest
        
        self._running = False
        self.last_digest_time: Optional[datetime] = None
    
    async def curate_picks(self, candidates: List[ValueBet]) -> List[CuratedPick]:
        """Use LLM to select and rank top picks."""
        if not candidates:
            return []
        
        # Prepare candidate list for LLM
        candidate_list = []
        for i, c in enumerate(candidates[:20]):  # Limit to 20
            candidate_list.append({
                "id": i,
                "market": c.market_name,
                "category": c.category,
                "odds": f"{c.entry_price:.1f}%",
                "side": c.bet_side,
                "multiplier": f"{c.potential_multiplier:.1f}x",
                "win_if_correct": f"${c.win_amount:.2f}",
                "days_to_resolution": c.days_to_resolution,
                "liquidity": f"${c.liquidity:,.0f}",
            })
        
        prompt = f"""You are a prediction market analyst. Select the TOP {self.picks_per_digest} value bets from this list.

CRITERIA for selection:
1. EDGE: Is there a reason the market might be mispricing this? (news, logic, data)
2. TIMING: Prefer markets resolving within 30 days
3. CATEGORY: Politics and Crypto tend to be more predictable than random events
4. LIQUIDITY: Higher is better (easier to trade)
5. AVOID: Duplicate/similar markets, random events, sports

CANDIDATES:
{json.dumps(candidate_list, indent=2)}

For each pick, provide:
1. The candidate ID
2. A 1-2 sentence reasoning why this is a good value bet

Output JSON:
{{
    "picks": [
        {{"id": 0, "reasoning": "..."}},
        {{"id": 1, "reasoning": "..."}},
        ...
    ]
}}

Select exactly {self.picks_per_digest} picks. Output ONLY valid JSON."""

        try:
            response = await self.groq.chat([
                {"role": "system", "content": "You are a prediction market expert. Output only valid JSON."},
                {"role": "user", "content": prompt}
            ])
            
            # Parse response
            content = response.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content)
            picks = data.get("picks", [])
            
            curated = []
            for rank, pick in enumerate(picks[:self.picks_per_digest], 1):
                idx = pick.get("id", 0)
                if 0 <= idx < len(candidates):
                    curated.append(CuratedPick(
                        bet=candidates[idx],
                        reasoning=pick.get("reasoning", "Selected by AI analysis."),
                        rank=rank,
                    ))
            
            return curated
            
        except Exception as e:
            logger.error("curation_error", error=str(e))
            # Fallback: return first N by liquidity
            sorted_candidates = sorted(candidates, key=lambda x: x.liquidity, reverse=True)
            return [
                CuratedPick(bet=c, reasoning="High liquidity market.", rank=i+1)
                for i, c in enumerate(sorted_candidates[:self.picks_per_digest])
            ]
    
    def format_digest(self, picks: List[CuratedPick], is_morning: bool) -> str:
        """Format the digest message for Telegram."""
        edition = "Morning" if is_morning else "Evening"
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%b %d, %Y")
        
        lines = [
            f"🎯 *VALUE BETS DIGEST*",
            f"📅 {edition} Edition • {date_str}",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
        ]
        
        total_win = 0
        total_cost = 0
        
        for pick in picks:
            bet = pick.bet
            total_win += bet.win_amount
            total_cost += bet.lose_amount
            
            lines.extend([
                "",
                f"💎 *PICK {pick.rank}/{len(picks)}*",
                "",
                f"📊 {bet.market_name[:55]}",
                f"   Current: {bet.entry_price:.1f}% {bet.bet_side}",
                "",
                f"💵 *$1 Bet Analysis:*",
                f"   • Buy: {bet.shares_for_dollar} shares @ ${bet.entry_price/100:.2f}",
                f"   • If {bet.bet_side}: Win ${bet.win_amount - 1:.2f} (+{(bet.potential_multiplier-1)*100:.0f}%)",
                f"   • If wrong: Lose $1.00",
                "",
                f"🧠 _{pick.reasoning}_",
                "",
                f"📅 Resolves in {bet.days_to_resolution} days",
                f"🔗 [Place Bet](https://polymarket.com/event/{bet.slug})",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
            ])
        
        # Summary
        next_time = "20:00" if is_morning else "11:00"
        lines.extend([
            "",
            f"📊 *Summary (if $1 each):*",
            f"• Total invested: ${total_cost:.2f}",
            f"• If ALL win: ${total_win:.2f}",
            f"• Break-even: 1 in {len(picks)} correct",
            "",
            f"⏰ Next digest: {next_time} UTC",
        ])
        
        return "\n".join(lines)
    
    def _is_digest_time(self) -> Optional[bool]:
        """Check if it's time for a digest. Returns True for morning, False for evening, None if not time."""
        now = datetime.now(timezone.utc)
        current_time = now.time()
        
        # Check each digest time with 5 min window
        for digest_time in self.DIGEST_TIMES:
            # Within 5 minutes of scheduled time
            digest_minutes = digest_time.hour * 60 + digest_time.minute
            current_minutes = current_time.hour * 60 + current_time.minute
            
            if abs(digest_minutes - current_minutes) <= 5:
                # Check we haven't sent this digest already
                if self.last_digest_time:
                    time_since_last = now - self.last_digest_time
                    if time_since_last.total_seconds() < 3600:  # 1 hour cooldown
                        return None
                
                return digest_time.hour < 15  # Morning if before 15:00
        
        return None
    
    async def check_and_send_digest(self) -> bool:
        """Check if it's digest time and send if so."""
        is_morning = self._is_digest_time()
        
        if is_morning is None:
            return False
        
        logger.info("digest_time_triggered", is_morning=is_morning)
        
        # Get candidates
        candidates = self.scanner.get_candidates()
        
        if not candidates:
            logger.info("no_candidates_for_digest")
            return False
        
        # Curate picks
        picks = await self.curate_picks(candidates)
        
        if not picks:
            logger.info("no_picks_selected")
            return False
        
        # Format message
        message = self.format_digest(picks, is_morning)
        
        # Send via callback
        if self.send_callback:
            try:
                await self.send_callback(message)
                logger.info("digest_sent", picks=len(picks), is_morning=is_morning)
            except Exception as e:
                logger.error("digest_send_error", error=str(e))
                return False
        
        # Mark as sent
        sent_ids = [p.bet.market_id for p in picks]
        self.scanner.clear_candidates(sent_ids)
        self.last_digest_time = datetime.now(timezone.utc)
        
        return True
    
    async def start(self):
        """Start the digest scheduler."""
        self._running = True
        logger.info("digest_scheduler_started", times=[str(t) for t in self.DIGEST_TIMES])
        
        while self._running:
            try:
                await self.check_and_send_digest()
            except Exception as e:
                logger.error("scheduler_error", error=str(e))
            
            # Check every minute
            await asyncio.sleep(60)
    
    def stop(self):
        """Stop the scheduler."""
        self._running = False
    
    async def send_test_digest(self) -> str:
        """Send a test digest immediately (for debugging)."""
        candidates = self.scanner.get_candidates()
        
        if not candidates:
            # Do a quick scan first
            await self.scanner.scan_markets()
            candidates = self.scanner.get_candidates()
        
        if not candidates:
            return "No candidates found."
        
        picks = await self.curate_picks(candidates)
        
        if not picks:
            return "No picks selected."
        
        message = self.format_digest(picks, is_morning=True)
        
        # Send via callback
        if self.send_callback:
            await self.send_callback(message)
            
            # Mark as sent
            sent_ids = [p.bet.market_id for p in picks]
            self.scanner.clear_candidates(sent_ids)
        
        return f"Sent digest with {len(picks)} picks."
