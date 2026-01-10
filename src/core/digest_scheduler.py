"""
ExaSignal - Digest Scheduler
Anti-hallucination digest system with strict data grounding.

Principles:
1. Data-First: All metrics are fetched, never LLM-guessed
2. LLM as Selector: Only picks from provided data
3. Validation: Post-LLM checks against input data
4. Transparency: Timestamps and sources included
"""
import asyncio
from dataclasses import dataclass
from typing import List, Optional, Callable
from datetime import datetime, timezone, time
import json
import re

from src.core.value_bets_scanner import ValueBet, ValueBetsScanner
from src.api.groq_client import GroqClient
from src.utils.logger import logger


@dataclass
class CuratedPick:
    """A curated pick with LLM reasoning."""
    bet: ValueBet
    reasoning: str
    rank: int
    ev_score: float  # Calculated EV, not LLM-generated
    confidence: str  # LOW/MEDIUM/HIGH based on formula


class DigestScheduler:
    """
    Anti-hallucination digest scheduler.
    LLM only selects from explicit data - no creative liberty.
    """
    
    # Digest times in UTC (Portugal winter time = UTC)
    DIGEST_TIMES = [
        time(11, 0),  # 11:00 - Morning
        time(16, 0),  # 16:00 - Afternoon
        time(20, 0),  # 20:00 - Evening
    ]
    
    def __init__(
        self,
        scanner: ValueBetsScanner,
        groq: Optional[GroqClient] = None,
        send_callback: Optional[Callable] = None,
        picks_per_digest: int = 10,
    ):
        self.scanner = scanner
        self.groq = groq or GroqClient()
        self.send_callback = send_callback
        self.picks_per_digest = picks_per_digest
        
        self._running = False
        self.last_digest_time: Optional[datetime] = None
    
    def _calculate_ev(self, bet: ValueBet) -> float:
        """Calculate Expected Value formulaically (not LLM)."""
        # EV = (Win Probability * Net Profit) - (Lose Probability * Loss)
        # For underdogs: probability is low but payout is high
        win_prob = bet.entry_price / 100  # Entry price IS the implied probability
        payout_if_win = bet.win_amount - 1  # Net profit per $1
        loss_if_lose = 1.0  # $1 bet
        
        ev = (win_prob * payout_if_win) - ((1 - win_prob) * loss_if_lose)
        return round(ev, 3)
    
    def _calculate_confidence(self, bet: ValueBet) -> str:
        """Calculate confidence level based on metrics (not LLM)."""
        score = 0
        
        # Liquidity factor (higher = better)
        if bet.liquidity >= 50000:
            score += 3
        elif bet.liquidity >= 10000:
            score += 2
        elif bet.liquidity >= 1000:
            score += 1
        
        # Resolution time factor (sooner = better for tracking)
        if bet.days_to_resolution <= 14:
            score += 2
        elif bet.days_to_resolution <= 30:
            score += 1
        
        # Category reliability factor
        if bet.category in ["Politics", "Crypto"]:
            score += 2
        elif bet.category in ["Weather", "AI/Tech"]:
            score += 1
        
        # Classify
        if score >= 5:
            return "HIGH"
        elif score >= 3:
            return "MEDIUM"
        else:
            return "LOW"
    
    async def curate_picks(self, candidates: List[ValueBet]) -> List[CuratedPick]:
        """Use LLM as a SELECTOR with strict data grounding."""
        if not candidates:
            return []
        
        # Pre-calculate all metrics (data-first, not LLM)
        for c in candidates:
            c.calculated_ev = self._calculate_ev(c)
            c.confidence = self._calculate_confidence(c)
        
        # Prepare candidate list with ALL data for LLM
        candidate_list = []
        for i, c in enumerate(candidates[:30]):  # Limit to 30
            candidate_list.append({
                "id": i,
                "market": c.market_name,
                "category": c.category,
                "odds": round(c.entry_price, 1),
                "side": c.bet_side,
                "payout_multiplier": round(c.potential_multiplier, 2),
                "liquidity_usd": round(c.liquidity, 0),
                "days_to_resolve": c.days_to_resolution,
                "ev_score": c.calculated_ev,  # Pre-calculated
                "confidence": c.confidence,  # Pre-calculated
            })
        
        # STRICT prompt - LLM can ONLY reference provided data
        prompt = f"""You are a Polymarket analyst. From this list of candidates, select exactly {self.picks_per_digest} (or fewer if not enough qualify).

SELECTION RULES (use ONLY provided data):
1. Prioritize DIVERSE categories (max 3 from same category)
2. Prefer HIGH confidence candidates
3. Prefer positive EV scores
4. Prefer higher liquidity (>$5000)
5. Prefer sooner resolution (<30 days)

CANDIDATES (all data is real-time from Polymarket):
{json.dumps(candidate_list, indent=2)}

For each selection, provide:
- The candidate ID (must match list)
- A 1-sentence rationale using ONLY the provided metrics

OUTPUT STRICT JSON ONLY:
{{
  "selections": [
    {{"id": 0, "rationale": "Selected due to HIGH confidence, $X liquidity, and Y days to resolve."}},
    {{"id": 5, "rationale": "Category diversity (Weather), positive EV of Z."}},
  ]
}}

RULES:
- Reference ONLY numbers from the provided data
- Do NOT invent facts or news
- Do NOT make price predictions
- If fewer than {self.picks_per_digest} qualify, return fewer"""

        try:
            response = await self.groq.chat([
                {"role": "system", "content": "You are a data analyst. Output ONLY valid JSON. Never invent facts."},
                {"role": "user", "content": prompt}
            ])
            
            # Parse response
            content = response.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content)
            selections = data.get("selections", data.get("picks", []))
            
            # VALIDATION: Check LLM output against input data
            curated = []
            for rank, pick in enumerate(selections[:self.picks_per_digest], 1):
                idx = pick.get("id", -1)
                reasoning = pick.get("rationale", pick.get("reasoning", ""))
                
                # Validate ID exists
                if not (0 <= idx < len(candidates)):
                    logger.warning("invalid_pick_id", id=idx)
                    continue
                
                candidate = candidates[idx]
                
                # Validation: Check rationale doesn't contain hallucinated numbers
                # (basic check - could be more sophisticated)
                if self._validate_reasoning(reasoning, candidate_list[idx]):
                    curated.append(CuratedPick(
                        bet=candidate,
                        reasoning=reasoning,
                        rank=rank,
                        ev_score=candidate.calculated_ev,
                        confidence=candidate.confidence,
                    ))
                else:
                    # Use fallback reasoning if validation fails
                    curated.append(CuratedPick(
                        bet=candidate,
                        reasoning=f"{candidate.confidence} confidence, ${candidate.liquidity:,.0f} liquidity.",
                        rank=rank,
                        ev_score=candidate.calculated_ev,
                        confidence=candidate.confidence,
                    ))
            
            return curated
            
        except Exception as e:
            logger.error("curation_error", error=str(e))
            # FALLBACK: Sort by formula, no LLM
            return self._fallback_selection(candidates)
    
    def _validate_reasoning(self, reasoning: str, candidate_data: dict) -> bool:
        """Validate LLM reasoning against actual data (anti-hallucination)."""
        # Extract numbers from reasoning
        numbers_in_reasoning = re.findall(r'\$?[\d,]+\.?\d*', reasoning)
        
        # For now, basic validation - could be enhanced
        # Check it's not making up large numbers
        for num_str in numbers_in_reasoning:
            try:
                num = float(num_str.replace('$', '').replace(',', ''))
                # Flag if number is suspiciously large and not in data
                if num > 1000000 and num not in [candidate_data.get('liquidity_usd', 0)]:
                    return False
            except:
                pass
        
        return True
    
    def _fallback_selection(self, candidates: List[ValueBet]) -> List[CuratedPick]:
        """Formula-based selection when LLM fails (no hallucination risk)."""
        # Score by: confidence + liquidity + EV
        def score(c):
            conf_score = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(getattr(c, 'confidence', 'LOW'), 1)
            liq_score = min(3, c.liquidity / 20000)  # Max 3 for 60k+
            ev_score = getattr(c, 'calculated_ev', 0) * 10  # Weight EV
            return conf_score + liq_score + ev_score
        
        sorted_candidates = sorted(candidates, key=score, reverse=True)
        
        return [
            CuratedPick(
                bet=c, 
                reasoning=f"Formula selection: {getattr(c, 'confidence', 'N/A')} confidence, ${c.liquidity:,.0f} liquidity.",
                rank=i+1,
                ev_score=getattr(c, 'calculated_ev', 0),
                confidence=getattr(c, 'confidence', 'LOW'),
            )
            for i, c in enumerate(sorted_candidates[:self.picks_per_digest])
        ]
    
    def format_digest(self, picks: List[CuratedPick], is_morning: bool) -> str:
        """Format digest with timestamps and sources (anti-hallucination)."""
        now = datetime.now(timezone.utc)
        fetch_time = now.strftime("%H:%M UTC")
        date_str = now.strftime("%b %d, %Y")
        
        edition_map = {True: "Morning", False: "Evening"}
        edition = edition_map.get(is_morning, "Afternoon")
        
        lines = [
            f"🎯 *POLYMARKET DIGEST*",
            f"📅 {edition} • {date_str} • {fetch_time}",
            f"",
            f"From {len(self.scanner.candidates)} scanned markets, selected {len(picks)} data-driven picks.",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
        ]
        
        total_invested = 0
        total_potential = 0
        
        for pick in picks:
            bet = pick.bet
            total_invested += 1  # $1 per bet
            total_potential += bet.win_amount
            
            # Confidence emoji
            conf_emoji = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(pick.confidence, "⚪")
            
            lines.extend([
                "",
                f"*#{pick.rank}* {conf_emoji} {pick.confidence}",
                f"",
                f"📊 *{bet.market_name[:60]}*",
                f"   Odds: {bet.bet_side} {bet.entry_price:.1f}% | Liquidity: ${bet.liquidity:,.0f}",
                f"   Resolves: {bet.days_to_resolution} days | EV: {pick.ev_score:+.2f}",
                "",
                f"💵 *$1 Bet:* Win ${bet.win_amount - 1:.2f} ({bet.potential_multiplier:.1f}x) or Lose $1",
                "",
                f"🧠 _{pick.reasoning}_",
                "",
                f"🔗 [Place Bet](https://polymarket.com/event/{bet.slug})",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
            ])
        
        # Summary with calculated metrics
        avg_ev = sum(p.ev_score for p in picks) / len(picks) if picks else 0
        
        lines.extend([
            "",
            f"📊 *SUMMARY*",
            f"• Invested: ${total_invested:.2f} | Max Return: ${total_potential:.2f}",
            f"• Average EV: {avg_ev:+.3f}",
            f"• Break-even: ~{int(100/len(picks))}% win rate",
            "",
            f"⚠️ *Not financial advice. Data from Polymarket at {fetch_time}.*",
            f"",
            f"⏰ Next digest: {self._get_next_digest_time()}",
        ])
        
        return "\n".join(lines)
    
    def _get_next_digest_time(self) -> str:
        """Get next scheduled digest time."""
        now = datetime.now(timezone.utc)
        current_minutes = now.hour * 60 + now.minute
        
        for dt in sorted(self.DIGEST_TIMES, key=lambda t: t.hour * 60 + t.minute):
            dt_minutes = dt.hour * 60 + dt.minute
            if dt_minutes > current_minutes:
                return f"{dt.hour:02d}:{dt.minute:02d} UTC"
        
        # Wrap to next day
        return f"{self.DIGEST_TIMES[0].hour:02d}:{self.DIGEST_TIMES[0].minute:02d} UTC"
    
    def _is_digest_time(self) -> Optional[bool]:
        """Check if it's time for a digest."""
        now = datetime.now(timezone.utc)
        current_time = now.time()
        
        for digest_time in self.DIGEST_TIMES:
            digest_minutes = digest_time.hour * 60 + digest_time.minute
            current_minutes = current_time.hour * 60 + current_time.minute
            
            if abs(digest_minutes - current_minutes) <= 5:
                if self.last_digest_time:
                    time_since_last = now - self.last_digest_time
                    if time_since_last.total_seconds() < 3600:
                        return None
                
                return digest_time.hour < 15
        
        return None
    
    async def check_and_send_digest(self) -> bool:
        """Check if it's digest time and send if so."""
        is_morning = self._is_digest_time()
        
        if is_morning is None:
            return False
        
        logger.info("digest_time_triggered", is_morning=is_morning)
        
        candidates = self.scanner.get_candidates()
        
        if not candidates:
            logger.info("no_candidates_for_digest")
            return False
        
        picks = await self.curate_picks(candidates)
        
        if not picks:
            logger.info("no_picks_selected")
            return False
        
        message = self.format_digest(picks, is_morning)
        
        if self.send_callback:
            try:
                await self.send_callback(message)
                logger.info("digest_sent", picks=len(picks), is_morning=is_morning)
            except Exception as e:
                logger.error("digest_send_error", error=str(e))
                return False
        
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
            
            await asyncio.sleep(60)
    
    def stop(self):
        """Stop the scheduler."""
        self._running = False
    
    async def send_test_digest(self) -> str:
        """Send a test digest immediately."""
        candidates = self.scanner.get_candidates()
        
        if not candidates:
            await self.scanner.scan_markets()
            candidates = self.scanner.get_candidates()
        
        if not candidates:
            return "No candidates found."
        
        picks = await self.curate_picks(candidates)
        
        if not picks:
            return "No picks selected."
        
        message = self.format_digest(picks, is_morning=True)
        
        if self.send_callback:
            await self.send_callback(message)
            
            sent_ids = [p.bet.market_id for p in picks]
            self.scanner.clear_candidates(sent_ids)
        
        return f"Sent digest with {len(picks)} picks."
