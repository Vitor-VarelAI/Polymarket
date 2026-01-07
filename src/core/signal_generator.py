"""
ExaSignal - Signal Generator
Gera sinais de trading baseados em notícias e mercados.

Flow SIMPLE: News + Market → AI Analysis → YES/NO Signal
Flow ENRICHED: Trigger → ResearchLoop → AlignmentScorer → AI → EnrichedSignal
"""
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

from src.api.groq_client import GroqClient
from src.core.research_loop import ResearchLoop
from src.core.alignment_scorer import AlignmentScorer
from src.core.momentum_tracker import MomentumTracker
from src.models.enriched_signal import EnrichedSignal
from src.models.market import Market
from src.models.research_result import ResearchResults
from src.utils.logger import logger


@dataclass
class Signal:
    """Trading signal with direction and reasoning (simple version)."""
    market_id: str
    market_name: str
    direction: str  # "YES", "NO", or "HOLD"
    confidence: int  # 0-100
    current_odds: Optional[float]
    news_title: str
    news_source: str
    reasoning: str
    key_points: List[str]
    timestamp: str
    
    def is_actionable(self, min_confidence: int = 70) -> bool:
        """Check if signal meets confidence threshold."""
        return self.confidence >= min_confidence and self.direction in ["YES", "NO"]
    
    def to_dict(self) -> dict:
        return {
            "market_id": self.market_id,
            "market_name": self.market_name,
            "direction": self.direction,
            "confidence": self.confidence,
            "current_odds": self.current_odds,
            "news_title": self.news_title,
            "news_source": self.news_source,
            "reasoning": self.reasoning,
            "key_points": self.key_points,
            "timestamp": self.timestamp,
            "actionable": self.is_actionable(),
        }
    
    def to_telegram_message(self) -> str:
        """Format for Telegram notification."""
        emoji = "🟢" if self.direction == "YES" else "🔴" if self.direction == "NO" else "⚪"
        
        msg = f"""
{emoji} **NEW SIGNAL: {self.direction}** ({self.confidence}%)

📊 **Market:** {self.market_name}

📰 **News:** {self.news_title}
_Source: {self.news_source}_

💡 **Reasoning:** {self.reasoning}

📈 Current odds: {self.current_odds:.1f}% if self.current_odds else "N/A"

⏰ {self.timestamp}
"""
        return msg.strip()


SIGNAL_PROMPT = """You are a prediction market analyst. Given a news headline and a prediction market, decide if the news makes YES or NO more likely.

NEWS:
Title: {news_title}
Source: {news_source}
Published: {news_time}

MARKET:
Question: {market_name}
Current YES odds: {current_odds}%

TASK:
1. Analyze if this news impacts the market
2. Determine if it favors YES or NO
3. Estimate your confidence (0-100)

Respond in JSON:
{{
    "direction": "YES" or "NO" or "HOLD",
    "confidence": 0-100,
    "reasoning": "Brief explanation",
    "key_points": ["point1", "point2", "point3"]
}}

If the news is not relevant to this market, respond with:
{{
    "direction": "HOLD",
    "confidence": 0,
    "reasoning": "News not relevant to this market",
    "key_points": []
}}
"""

# Prompt enriquecido com contexto de research
ENRICHED_SIGNAL_PROMPT = """You are a prediction market analyst with research data. Analyze the trigger event and research to make a trading decision.

TRIGGER EVENT:
Type: {trigger_type}
{trigger_details}

MARKET:
Question: {market_name}
Current YES odds: {current_odds}%

RESEARCH DATA (from multiple sources):
{research_summary}

Sources breakdown: {source_breakdown}

TASK:
1. Analyze if the research supports or contradicts the trigger event
2. Consider source credibility (arxiv > exa > rss > newsapi)
3. Determine if it favors YES or NO
4. Estimate your confidence (0-100) based on research quality

Respond in JSON:
{{
    "direction": "YES" or "NO" or "HOLD",
    "confidence": 0-100,
    "reasoning": "Brief explanation considering research quality",
    "key_points": ["point1", "point2", "point3"]
}}
"""


class SignalGenerator:
    """
    Generates trading signals from triggers (news or whale events).
    
    Modes:
    - Simple: News → LLM → Signal (backward compatible)
    - Enriched: Trigger → ResearchLoop → AlignmentScorer → LLM → EnrichedSignal
    """
    
    def __init__(
        self,
        groq: Optional[GroqClient] = None,
        research_loop: Optional[ResearchLoop] = None,
        alignment_scorer: Optional[AlignmentScorer] = None,
        momentum_tracker: Optional[MomentumTracker] = None,
    ):
        """
        Initialize SignalGenerator.
        
        Args:
            groq: Groq LLM client
            research_loop: For multi-source research (optional for enriched mode)
            alignment_scorer: For 5-dimension scoring (optional for enriched mode)
            momentum_tracker: For tracking odds velocity (optional)
        """
        self.groq = groq or GroqClient()
        self.research = research_loop  # Lazy init if needed
        self.scorer = alignment_scorer  # Lazy init if needed
        self.momentum = momentum_tracker or MomentumTracker()
        self.recent_signals: List[Union[Signal, EnrichedSignal]] = []
        self.recent_enriched: List[EnrichedSignal] = []
        self.max_stored_signals = 50
    
    def _ensure_research_loop(self) -> ResearchLoop:
        """Lazy init ResearchLoop."""
        if not self.research:
            self.research = ResearchLoop()
        return self.research
    
    def _ensure_scorer(self) -> AlignmentScorer:
        """Lazy init AlignmentScorer."""
        if not self.scorer:
            self.scorer = AlignmentScorer()
        return self.scorer
    
    async def analyze_enriched(
        self,
        trigger_type: str,  # "whale" | "news"
        trigger_data: Dict[str, Any],
        market: Dict[str, Any],
        current_odds: Optional[float] = None,
    ) -> EnrichedSignal:
        """
        FULL ENRICHED ANALYSIS PIPELINE.
        
        Flow:
        1. Run ResearchLoop for multi-source research
        2. Run AlignmentScorer for 5-dimension scoring
        3. Run LLM analysis with research context
        4. Merge all into EnrichedSignal
        
        Args:
            trigger_type: "whale" or "news"
            trigger_data: Original trigger data (WhaleEvent dict or news dict)
            market: Market data {id, name, slug, ...}
            current_odds: Current YES probability (0-100)
        
        Returns:
            EnrichedSignal with full analysis
        """
        start_time = datetime.now()
        
        # Extract market info
        market_id = market.get("id") or market.get("slug", "unknown")
        market_name = market.get("name") or market.get("title") or market.get("question", "Unknown")
        market_slug = market.get("slug", "")
        
        logger.info(
            "enriched_analysis_start",
            trigger_type=trigger_type,
            market_id=market_id
        )
        
        # Convert to Market object for ResearchLoop
        market_obj = self._to_market_object(market)
        
        # ====================================================================
        # Step 1: Run ResearchLoop (multi-source research)
        # ====================================================================
        research_loop = self._ensure_research_loop()
        
        if trigger_type == "whale":
            # For whale triggers, need to import and create WhaleEvent
            from src.models.whale_event import WhaleEvent
            whale_event = self._to_whale_event(trigger_data)
            research_results = await research_loop.execute(market_obj, whale_event)
        else:
            # For news triggers, use execute_for_news
            # Passar odds para lógica de Exa (mercados incertos 40-60% usam Exa)
            trigger_data_with_odds = {**trigger_data, "_market_odds": current_odds}
            research_results = await research_loop.execute_for_news(market_obj, trigger_data_with_odds)
        
        logger.info(
            "research_complete",
            total_results=len(research_results.results),
            sources=research_results.source_breakdown
        )
        
        # ====================================================================
        # Step 2: Run AlignmentScorer (5-dimension scoring)
        # ====================================================================
        scorer = self._ensure_scorer()
        
        if trigger_type == "whale":
            whale_event = self._to_whale_event(trigger_data)
            score_result = scorer.calculate(whale_event, research_results, current_odds)
        else:
            # For news, use the direction from LLM or research consensus
            preliminary_direction = self._get_research_consensus(research_results)
            score_result = scorer.calculate_for_news(
                market_id, 
                preliminary_direction, 
                research_results, 
                current_odds
            )
        
        logger.info(
            "scoring_complete",
            total_score=score_result.total_score,
            should_alert=score_result.should_alert
        )
        
        # ====================================================================
        # Step 3: Run LLM Analysis WITH research context
        # ====================================================================
        llm_result = await self._analyze_with_context(
            trigger_type=trigger_type,
            trigger_data=trigger_data,
            market_name=market_name,
            current_odds=current_odds,
            research_results=research_results
        )
        
        # ====================================================================
        # Step 4: Create EnrichedSignal
        # ====================================================================
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Track odds for momentum calculation
        momentum_score = 0
        if current_odds is not None:
            self.momentum.track_odds(market_id, current_odds)
            momentum_score = self.momentum.get_momentum_score(market_id)
            logger.debug(
                "momentum_tracked",
                market_id=market_id,
                momentum_score=momentum_score
            )
        
        # Get market liquidity if available
        market_liquidity = market.get("liquidity") or market.get("volume")
        
        enriched = EnrichedSignal.from_analysis(
            market_id=market_id,
            market_name=market_name,
            market_slug=market_slug,
            trigger_type=trigger_type,
            trigger_data=trigger_data,
            llm_result=llm_result,
            score_result=score_result,
            research_results=research_results,
            current_odds=current_odds,
            processing_time_ms=processing_time,
            market_liquidity=market_liquidity,
            momentum_score=momentum_score
        )
        
        # Store in history
        self._store_enriched(enriched)
        
        logger.info(
            "enriched_signal_generated",
            market_id=market_id,
            direction=enriched.direction,
            score_total=enriched.score_total,
            confidence=enriched.confidence,
            should_alert=enriched.should_alert,
            processing_ms=processing_time
        )
        
        return enriched
    
    async def _analyze_with_context(
        self,
        trigger_type: str,
        trigger_data: Dict,
        market_name: str,
        current_odds: Optional[float],
        research_results: ResearchResults
    ) -> Dict:
        """Run LLM analysis with research context."""
        
        # Build trigger details
        if trigger_type == "whale":
            trigger_details = f"""
Direction: {trigger_data.get('direction', 'Unknown')}
Size: ${trigger_data.get('size_usd', 0):,.0f}
Wallet Age: {trigger_data.get('wallet_age_days', 0)} days inactive
"""
        else:
            trigger_details = f"""
News Title: {trigger_data.get('title', 'Unknown')}
Source: {trigger_data.get('source', 'Unknown')}
Published: {trigger_data.get('publishedAt', 'Unknown')}
"""
        
        # Build research summary
        research_summary = ""
        for r in research_results.results[:5]:  # Top 5 results
            direction_emoji = "🟢" if r.direction == "YES" else "🔴" if r.direction == "NO" else "⚪"
            research_summary += f"{direction_emoji} [{r.source}] {r.title[:80]}\n"
        
        if not research_summary:
            research_summary = "No research data available."
        
        # Format prompt
        prompt = ENRICHED_SIGNAL_PROMPT.format(
            trigger_type=trigger_type.upper(),
            trigger_details=trigger_details,
            market_name=market_name,
            current_odds=f"{current_odds:.1f}" if current_odds else "Unknown",
            research_summary=research_summary,
            source_breakdown=research_results.source_breakdown
        )
        
        try:
            response = await self.groq.quick_prompt(prompt)
            if not response:
                return self._default_llm_result()
            
            return self._parse_response(response)
            
        except Exception as e:
            logger.error("enriched_llm_error", error=str(e))
            return self._default_llm_result()
    
    def _to_market_object(self, market: Dict) -> Market:
        """Convert market dict to Market object."""
        market_name = market.get("name") or market.get("title") or market.get("question", "Unknown")
        return Market(
            market_id=market.get("id") or market.get("slug", "unknown"),
            market_name=market_name,
            yes_definition=f"YES: {market_name}",  # Auto-generate from name
            no_definition=f"NO: {market_name}",    # Auto-generate from name
            category=market.get("category", "other"),
            tags=market.get("tags", [])
        )
    
    def _to_whale_event(self, data: Dict):
        """Convert dict to WhaleEvent."""
        from src.models.whale_event import WhaleEvent
        
        return WhaleEvent(
            market_id=data.get("market_id", "unknown"),
            direction=data.get("direction", "YES"),
            size_usd=data.get("size_usd", 0),
            wallet_address=data.get("wallet_address", "unknown"),
            wallet_age_days=data.get("wallet_age_days", 0),
            liquidity_ratio=data.get("liquidity_ratio", 0),
            timestamp=datetime.fromisoformat(data["timestamp"]) if isinstance(data.get("timestamp"), str) else data.get("timestamp", datetime.now()),
            is_new_position=data.get("is_new_position", True),
            previous_position_size=data.get("previous_position_size", 0)
        )
    
    def _get_research_consensus(self, research: ResearchResults) -> str:
        """Get consensus direction from research results."""
        yes_count = len([r for r in research.results if r.direction == "YES"])
        no_count = len([r for r in research.results if r.direction == "NO"])
        
        if yes_count > no_count:
            return "YES"
        elif no_count > yes_count:
            return "NO"
        return "NEUTRAL"
    
    def _default_llm_result(self) -> Dict:
        """Default result when LLM fails."""
        return {
            "direction": "HOLD",
            "confidence": 0,
            "reasoning": "Could not complete analysis",
            "key_points": []
        }
    
    def _store_enriched(self, signal: EnrichedSignal):
        """Store enriched signal in history."""
        self.recent_enriched.insert(0, signal)
        if len(self.recent_enriched) > self.max_stored_signals:
            self.recent_enriched = self.recent_enriched[:self.max_stored_signals]
    
    def get_recent_enriched(self, limit: int = 10) -> List[EnrichedSignal]:
        """Get most recent enriched signals."""
        return self.recent_enriched[:limit]
    
    def get_actionable_enriched(self, min_score: int = 70) -> List[EnrichedSignal]:
        """Get enriched signals that meet score threshold."""
        return [s for s in self.recent_enriched if s.is_actionable(min_score)]
    
    # ========================================================================
    # BACKWARD COMPATIBLE METHODS (simple analysis)
    # ========================================================================
    
    async def analyze(
        self,
        news: Dict[str, Any],
        market: Dict[str, Any],
        current_odds: Optional[float] = None
    ) -> Signal:
        """
        Analyze news + market and generate trading signal.
        
        Args:
            news: {"title": str, "source": str, "publishedAt": str}
            market: {"id": str, "name": str, ...}
            current_odds: Current YES probability (0-100)
        
        Returns:
            Signal with direction, confidence, reasoning
        """
        market_name = market.get("name") or market.get("title") or market.get("question", "Unknown")
        market_id = market.get("id") or market.get("slug", "unknown")
        news_title = news.get("title", "Unknown news")
        news_source = news.get("source", {})
        if isinstance(news_source, dict):
            news_source = news_source.get("name", "Unknown")
        news_time = news.get("publishedAt", datetime.now().isoformat())
        
        # Format prompt
        prompt = SIGNAL_PROMPT.format(
            news_title=news_title,
            news_source=news_source,
            news_time=news_time,
            market_name=market_name,
            current_odds=f"{current_odds:.1f}" if current_odds else "Unknown"
        )
        
        try:
            # Get AI analysis
            response = await self.groq.quick_prompt(prompt)
            
            if not response:
                return self._create_error_signal(market_id, market_name, news_title, news_source)
            
            # Parse JSON response
            data = self._parse_response(response)
            
            signal = Signal(
                market_id=market_id,
                market_name=market_name,
                direction=data.get("direction", "HOLD"),
                confidence=int(data.get("confidence", 0)),
                current_odds=current_odds,
                news_title=news_title,
                news_source=news_source,
                reasoning=data.get("reasoning", "No reasoning provided"),
                key_points=data.get("key_points", []),
                timestamp=datetime.now().isoformat()
            )
            
            # Store in history
            self._store_signal(signal)
            
            logger.info("signal_generated",
                       market=market_id,
                       direction=signal.direction,
                       confidence=signal.confidence)
            
            return signal
            
        except Exception as e:
            logger.error("signal_generation_error", error=str(e))
            return self._create_error_signal(market_id, market_name, news_title, news_source)
    
    def _parse_response(self, response: str) -> dict:
        """Parse LLM response to extract JSON."""
        try:
            # Clean markdown if present
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            
            return json.loads(clean)
        except:
            # Try to find JSON in text
            try:
                start = response.find("{")
                end = response.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(response[start:end])
            except:
                pass
        
        return {
            "direction": "HOLD",
            "confidence": 0,
            "reasoning": "Could not parse AI response",
            "key_points": []
        }
    
    def _create_error_signal(
        self, 
        market_id: str, 
        market_name: str, 
        news_title: str,
        news_source: str
    ) -> Signal:
        """Create a HOLD signal for error cases."""
        return Signal(
            market_id=market_id,
            market_name=market_name,
            direction="HOLD",
            confidence=0,
            current_odds=None,
            news_title=news_title,
            news_source=news_source,
            reasoning="Error during analysis",
            key_points=[],
            timestamp=datetime.now().isoformat()
        )
    
    def _store_signal(self, signal: Signal):
        """Store signal in history, removing old ones."""
        self.recent_signals.insert(0, signal)
        if len(self.recent_signals) > self.max_stored_signals:
            self.recent_signals = self.recent_signals[:self.max_stored_signals]
    
    def get_recent_signals(self, limit: int = 10) -> List[Signal]:
        """Get most recent signals."""
        return self.recent_signals[:limit]
    
    def get_actionable_signals(self, min_confidence: int = 70) -> List[Signal]:
        """Get signals that meet confidence threshold."""
        return [s for s in self.recent_signals if s.is_actionable(min_confidence)]
