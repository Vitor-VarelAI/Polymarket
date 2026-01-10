"""
ExaSignal - Digest Scheduler v2.0
Hybrid approach: LLM for Selection, Templates for Reasoning.

Architecture:
- Hard Logic: EV, Confidence, Reasoning (Python - no hallucinations)
- LLM: Selection only (diversity, pattern detection)
- Validation: Strict JSON parsing, no invented data
"""
import asyncio
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any
from datetime import datetime, timezone, time
import json
import re

from src.core.value_bets_scanner import ValueBet, ValueBetsScanner
from src.api.groq_client import GroqClient
from src.utils.logger import logger


@dataclass
class CuratedPick:
    """A curated pick with template-based reasoning."""
    bet: ValueBet
    reasoning: str  # Template-generated, NOT LLM
    rank: int
    ev_score: float
    confidence: str
    risk_context: str  # Template-generated insight


class DigestScheduler:
    """
    Hybrid Digest Scheduler:
    - LLM: ONLY for selection (which IDs to pick)
    - Python: ALL reasoning and metrics (no hallucinations)
    """
    
    DIGEST_TIMES = [
        time(11, 0),
        time(16, 0),
        time(20, 0),
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
        
        # Future: Store for feedback loop
        self.prediction_history: List[Dict[str, Any]] = []
    
    # =========================================
    # HARD LOGIC: All calculations in Python
    # =========================================
    
    def _calculate_ev(self, bet: ValueBet) -> float:
        """Calculate Expected Value (pure math, no LLM)."""
        win_prob = bet.entry_price / 100
        payout_if_win = bet.win_amount - 1
        loss_if_lose = 1.0
        ev = (win_prob * payout_if_win) - ((1 - win_prob) * loss_if_lose)
        return round(ev, 3)
    
    def _calculate_confidence(self, bet: ValueBet) -> str:
        """Calculate confidence level (pure logic, no LLM)."""
        score = 0
        
        if bet.liquidity >= 50000:
            score += 3
        elif bet.liquidity >= 10000:
            score += 2
        elif bet.liquidity >= 1000:
            score += 1
        
        if bet.days_to_resolution <= 14:
            score += 2
        elif bet.days_to_resolution <= 30:
            score += 1
        
        if bet.category in ["Politics", "Crypto"]:
            score += 2
        elif bet.category in ["Weather", "AI/Tech"]:
            score += 1
        
        if score >= 5:
            return "HIGH"
        elif score >= 3:
            return "MEDIUM"
        return "LOW"
    
    def _generate_reasoning(self, bet: ValueBet) -> str:
        """
        Template-based reasoning (NO LLM).
        This is the key anti-hallucination feature.
        """
        parts = []
        
        # Liquidity insight
        if bet.liquidity >= 50000:
            parts.append("High liquidity ($50k+) ensures easy entry/exit")
        elif bet.liquidity >= 10000:
            parts.append("Decent liquidity ($10k+)")
        else:
            parts.append("Lower liquidity - consider position size")
        
        # Timeframe insight
        if bet.days_to_resolution <= 7:
            parts.append("resolves within a week (fast feedback)")
        elif bet.days_to_resolution <= 30:
            parts.append(f"resolves in {bet.days_to_resolution} days")
        else:
            parts.append(f"longer-term ({bet.days_to_resolution} days)")
        
        return ", ".join(parts) + "."
    
    def _generate_risk_context(self, bet: ValueBet) -> str:
        """
        Template-based risk context (NO LLM).
        Provides insight that math doesn't capture.
        """
        # Category-based risk
        category_risk = {
            "Politics": "Political markets can be binary - careful with timing around events.",
            "Crypto": "High volatility expected. Price can move rapidly.",
            "Weather": "Weather forecasts beyond 7 days have lower accuracy.",
            "AI/Tech": "Tech announcements can cause sudden resolution.",
            "Arbitrage": "Multi-leg trade - ensure both sides execute.",
            "Other": "General market - verify resolution criteria.",
        }
        
        base_risk = category_risk.get(bet.category, category_risk["Other"])
        
        # Add EV-specific context
        ev = getattr(bet, 'calculated_ev', 0)
        if ev > 0.1:
            return f"Strong edge detected. {base_risk}"
        elif ev > 0:
            return f"Marginal edge. {base_risk}"
        else:
            return f"Negative EV - included for diversity. {base_risk}"
    
    # =========================================
    # LLM: ONLY for Selection (IDs)
    # =========================================
    
    async def _llm_select_ids(self, candidates: List[ValueBet]) -> List[int]:
        """
        LLM ONLY selects which IDs to include.
        No reasoning, no text generation - just IDs.
        """
        if not candidates:
            return []
        
        # Prepare minimal data for selection
        candidate_summary = []
        for i, c in enumerate(candidates[:30]):
            candidate_summary.append({
                "id": i,
                "market": c.market_name[:50],
                "category": c.category,
                "confidence": getattr(c, 'confidence', 'MEDIUM'),
                "ev": getattr(c, 'calculated_ev', 0),
                "liquidity": int(c.liquidity),
                "days": c.days_to_resolution,
            })
        
        # Minimal prompt - selection only
        prompt = f"""Select {self.picks_per_digest} market IDs from this list.

RULES:
1. MAX 3 from same category (diversity)
2. Prefer HIGH confidence
3. Prefer positive EV
4. Prefer higher liquidity
5. Skip duplicates/similar markets

CANDIDATES:
{json.dumps(candidate_summary, indent=1)}

OUTPUT JSON ONLY (just IDs, no reasoning):
{{"ids": [0, 3, 7, 12, ...]}}"""

        try:
            response = await self.groq.chat([
                {"role": "system", "content": "Output only valid JSON with selected IDs."},
                {"role": "user", "content": prompt}
            ])
            
            content = response.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content)
            ids = data.get("ids", [])
            
            # Validate IDs are in range
            valid_ids = [i for i in ids if isinstance(i, int) and 0 <= i < len(candidates)]
            return valid_ids[:self.picks_per_digest]
            
        except Exception as e:
            logger.error("llm_selection_error", error=str(e))
            return []
    
    async def curate_picks(self, candidates: List[ValueBet]) -> List[CuratedPick]:
        """
        Hybrid curation:
        1. Python calculates all metrics
        2. LLM selects IDs only
        3. Python generates all text (templates)
        """
        if not candidates:
            return []
        
        # Step 0: PRE-FILTER only broken/unusable entries
        filtered = []
        for c in candidates:
            # Skip arbitrage (multi-leg, format broken)
            if c.category == "Arbitrage" or c.bet_side == "ARBITRAGE":
                continue
            # Skip already resolved (0 days)
            if c.days_to_resolution <= 0:
                continue
            # Skip placeholder entries (broken data)
            if c.entry_price == 50 and c.potential_multiplier == 1:
                continue
            # NOTE: Sports NOT filtered - let selection criteria decide
            filtered.append(c)
        
        candidates = filtered
        if not candidates:
            logger.info("all_candidates_filtered_out")
            return []
        
        # Step 1: Calculate all metrics in Python (HARD LOGIC)
        for c in candidates:
            c.calculated_ev = self._calculate_ev(c)
            c.confidence = self._calculate_confidence(c)
        
        # Step 1.5: Filter by EV (only positive or near-zero)
        candidates = [c for c in candidates if c.calculated_ev >= -0.1]
        
        # Step 2: LLM selects IDs (or fallback to formula)
        selected_ids = await self._llm_select_ids(candidates)
        
        if not selected_ids:
            # Fallback: Pure formula selection
            logger.info("using_fallback_selection")
            selected_ids = self._formula_select_ids(candidates)
        
        # Step 3: Build picks with TEMPLATE reasoning (NO LLM)
        curated = []
        for rank, idx in enumerate(selected_ids, 1):
            if 0 <= idx < len(candidates):
                bet = candidates[idx]
                curated.append(CuratedPick(
                    bet=bet,
                    reasoning=self._generate_reasoning(bet),
                    rank=rank,
                    ev_score=bet.calculated_ev,
                    confidence=bet.confidence,
                    risk_context=self._generate_risk_context(bet),
                ))
        
        return curated
    
    def _formula_select_ids(self, candidates: List[ValueBet]) -> List[int]:
        """Pure formula selection (no LLM, no hallucination risk)."""
        def score(c):
            conf = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(getattr(c, 'confidence', 'LOW'), 1)
            liq = min(3, c.liquidity / 20000)
            ev = getattr(c, 'calculated_ev', 0) * 10
            return conf + liq + ev
        
        # Sort by score
        indexed = [(i, score(c)) for i, c in enumerate(candidates)]
        indexed.sort(key=lambda x: x[1], reverse=True)
        
        # Enforce category diversity
        selected = []
        category_count = {}
        for idx, _ in indexed:
            cat = candidates[idx].category
            if category_count.get(cat, 0) < 3:
                selected.append(idx)
                category_count[cat] = category_count.get(cat, 0) + 1
            if len(selected) >= self.picks_per_digest:
                break
        
        return selected
    
    # =========================================
    # DIGEST FORMATTING (Templates only)
    # =========================================
    
    def format_digest(self, picks: List[CuratedPick], edition: str = "Morning") -> str:
        """Format digest using templates (no LLM text)."""
        now = datetime.now(timezone.utc)
        fetch_time = now.strftime("%H:%M UTC")
        date_str = now.strftime("%b %d, %Y")
        
        queue_size = len(self.scanner.candidates) if hasattr(self.scanner, 'candidates') else 0
        
        lines = [
            f"🎯 *POLYMARKET DIGEST*",
            f"📅 {edition} • {date_str} • {fetch_time}",
            f"",
            f"Scanned {queue_size + len(picks)} markets → {len(picks)} selected",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
        ]
        
        total_invested = 0
        total_potential = 0
        
        for pick in picks:
            bet = pick.bet
            total_invested += 1
            total_potential += bet.win_amount
            
            conf_emoji = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(pick.confidence, "⚪")
            
            lines.extend([
                "",
                f"*#{pick.rank}* {conf_emoji} {pick.confidence} | EV: {pick.ev_score:+.2f}",
                f"",
                f"📊 *{bet.market_name[:55]}*",
                f"   {bet.bet_side} @ {bet.entry_price:.1f}% | ${bet.liquidity:,.0f} liq",
                "",
                f"💵 *$1 →* ${bet.win_amount:.2f} win ({bet.potential_multiplier:.1f}x) or -$1",
                "",
                f"📝 _{pick.reasoning}_",
                f"⚠️ _{pick.risk_context[:60]}_",
                "",
                f"🔗 [Bet](https://polymarket.com/event/{bet.slug}) | ⏱️ {bet.days_to_resolution}d",
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
            ])
        
        # Summary
        avg_ev = sum(p.ev_score for p in picks) / len(picks) if picks else 0
        
        lines.extend([
            "",
            f"📊 *SUMMARY*",
            f"• ${total_invested} → ${total_potential:.2f} max",
            f"• Avg EV: {avg_ev:+.3f}",
            "",
            f"_Data: Polymarket @ {fetch_time}. Not advice._",
            f"⏰ Next: {self._get_next_digest_time()}",
        ])
        
        return "\n".join(lines)
    
    def _get_next_digest_time(self) -> str:
        now = datetime.now(timezone.utc)
        current_minutes = now.hour * 60 + now.minute
        
        for dt in sorted(self.DIGEST_TIMES, key=lambda t: t.hour * 60 + t.minute):
            if dt.hour * 60 + dt.minute > current_minutes:
                return f"{dt.hour:02d}:{dt.minute:02d} UTC"
        
        return f"{self.DIGEST_TIMES[0].hour:02d}:{self.DIGEST_TIMES[0].minute:02d} UTC"
    
    def _get_edition_name(self) -> str:
        now = datetime.now(timezone.utc)
        if now.hour < 13:
            return "Morning"
        elif now.hour < 18:
            return "Afternoon"
        return "Evening"
    
    # =========================================
    # SCHEDULER LOGIC
    # =========================================
    
    def _is_digest_time(self) -> bool:
        now = datetime.now(timezone.utc)
        current_minutes = now.hour * 60 + now.minute
        
        for dt in self.DIGEST_TIMES:
            dt_minutes = dt.hour * 60 + dt.minute
            if abs(dt_minutes - current_minutes) <= 5:
                if self.last_digest_time:
                    if (now - self.last_digest_time).total_seconds() < 3600:
                        return False
                return True
        return False
    
    async def check_and_send_digest(self) -> bool:
        if not self._is_digest_time():
            return False
        
        logger.info("digest_time_triggered")
        
        candidates = self.scanner.get_candidates()
        if not candidates:
            logger.info("no_candidates_for_digest")
            return False
        
        picks = await self.curate_picks(candidates)
        if not picks:
            logger.info("no_picks_selected")
            return False
        
        message = self.format_digest(picks, self._get_edition_name())
        
        if self.send_callback:
            try:
                await self.send_callback(message)
                logger.info("digest_sent", picks=len(picks))
                
                # Store for future feedback loop
                self._store_predictions(picks)
                
            except Exception as e:
                logger.error("digest_send_error", error=str(e))
                return False
        
        sent_ids = [p.bet.market_id for p in picks]
        self.scanner.clear_candidates(sent_ids)
        self.last_digest_time = datetime.now(timezone.utc)
        
        return True
    
    def _store_predictions(self, picks: List[CuratedPick]):
        """Store predictions for future feedback loop (resolution tracking)."""
        for pick in picks:
            self.prediction_history.append({
                "market_id": pick.bet.market_id,
                "market_name": pick.bet.market_name,
                "bet_side": pick.bet.bet_side,
                "entry_price": pick.bet.entry_price,
                "predicted_ev": pick.ev_score,
                "confidence": pick.confidence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "resolved": False,
                "actual_pnl": None,  # To be filled when market resolves
            })
        
        # Keep last 100 predictions
        self.prediction_history = self.prediction_history[-100:]
    
    async def start(self):
        self._running = True
        logger.info("digest_scheduler_started", times=[str(t) for t in self.DIGEST_TIMES])
        
        while self._running:
            try:
                await self.check_and_send_digest()
            except Exception as e:
                logger.error("scheduler_error", error=str(e))
            
            await asyncio.sleep(60)
    
    def stop(self):
        self._running = False
    
    async def send_test_digest(self) -> str:
        candidates = self.scanner.get_candidates()
        
        if not candidates:
            await self.scanner.scan_markets()
            candidates = self.scanner.get_candidates()
        
        if not candidates:
            return "No candidates found."
        
        picks = await self.curate_picks(candidates)
        
        if not picks:
            return "No picks selected."
        
        message = self.format_digest(picks, "Test")
        
        if self.send_callback:
            await self.send_callback(message)
            sent_ids = [p.bet.market_id for p in picks]
            self.scanner.clear_candidates(sent_ids)
        
        return f"Sent digest with {len(picks)} picks."
