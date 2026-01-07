"""
ExaSignal - Enriched Signal Model
Combina Signal + ScoreResult + ResearchResults num único modelo unificado.

Este modelo é o output de qualquer trigger (Whale ou News) após passar
pela pipeline completa de enriquecimento.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional

from src.utils.logger import logger


@dataclass
class EnrichedSignal:
    """
    Signal enriquecido com todas as dimensões de análise.
    
    Combina:
    - Trigger (whale ou news)
    - AI Analysis (Groq LLM)
    - 5-Dimension Score (AlignmentScorer)
    - Research Results (multi-source)
    """
    
    # === Required Fields (no defaults) ===
    market_id: str
    market_name: str
    direction: str  # "YES", "NO", "HOLD"
    trigger_type: str  # "whale" | "news"
    
    # === Optional Fields (with defaults) ===
    market_slug: str = ""
    should_alert: bool = False
    
    # === Trigger Source ===
    trigger_data: Dict[str, Any] = field(default_factory=dict)
    
    # === AI Analysis (from Groq) ===
    confidence: int = 0  # 0-100 from LLM
    reasoning: str = ""
    key_points: List[str] = field(default_factory=list)
    
    # === 5-Dimension Score (from AlignmentScorer) ===
    score_total: int = 0  # 0-100
    score_credibility: int = 0  # 0-30 - Hierarquia: arxiv > exa > rss > newsapi
    score_recency: int = 0  # 0-20 - NewsAPI penalizada 50%
    score_consensus: int = 0  # 0-25 - % alinhamento research/direction
    score_specificity: int = 0  # 0-15 - Fontes técnicas vs genéricas
    score_divergence: int = 0  # 0-10 - Direction vs odds do mercado
    
    # === Research Backing ===
    sources: List[Dict[str, Any]] = field(default_factory=list)
    source_breakdown: Dict[str, int] = field(default_factory=dict)  # {arxiv: 2, rss: 5}
    
    # === Market Context ===
    current_odds: Optional[float] = None
    market_liquidity: Optional[float] = None  # USD liquidity (None = unknown)
    momentum_score: int = 0  # 0-10 momentum from MomentumTracker
    
    # === Metadata ===
    timestamp: datetime = field(default_factory=datetime.now)
    processing_time_ms: int = 0
    
    # === Thresholds ===
    MIN_LIQUIDITY_USD: float = 10000  # $10k minimum
    
    def is_actionable(self, min_score: int = 70, min_confidence: int = 60) -> bool:
        """
        Verifica se o sinal é acionável.
        
        Critérios:
        - Direção clara (YES ou NO)
        - Score total >= min_score (default 70)
        - Confidence LLM >= min_confidence (default 60)
        """
        return (
            self.direction in ["YES", "NO"]
            and self.score_total >= min_score
            and self.confidence >= min_confidence
        )
    
    def get_composite_score(self) -> int:
        """
        Calcula score composto: média ponderada de score_total + confidence.
        
        Peso: 60% AlignmentScore, 40% LLM Confidence
        """
        return int(self.score_total * 0.6 + self.confidence * 0.4)
    
    def get_score_breakdown(self) -> Dict[str, Dict[str, int]]:
        """Retorna breakdown detalhado dos scores."""
        return {
            "credibility": {"score": self.score_credibility, "max": 30},
            "recency": {"score": self.score_recency, "max": 20},
            "consensus": {"score": self.score_consensus, "max": 25},
            "specificity": {"score": self.score_specificity, "max": 15},
            "divergence": {"score": self.score_divergence, "max": 10},
            "total": {"score": self.score_total, "max": 100},
        }
    
    def to_dict(self) -> dict:
        """Serializa para dict."""
        return {
            "market_id": self.market_id,
            "market_name": self.market_name,
            "market_slug": self.market_slug,
            "direction": self.direction,
            "should_alert": self.should_alert,
            "trigger_type": self.trigger_type,
            "trigger_data": self.trigger_data,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "key_points": self.key_points,
            "score_total": self.score_total,
            "score_credibility": self.score_credibility,
            "score_recency": self.score_recency,
            "score_consensus": self.score_consensus,
            "score_specificity": self.score_specificity,
            "score_divergence": self.score_divergence,
            "sources": self.sources,
            "source_breakdown": self.source_breakdown,
            "current_odds": self.current_odds,
            "timestamp": self.timestamp.isoformat(),
            "processing_time_ms": self.processing_time_ms,
            "composite_score": self.get_composite_score(),
            "actionable": self.is_actionable(),
        }
    
    def to_telegram_message(self) -> str:
        """Formata para notificação Telegram."""
        emoji = "🟢" if self.direction == "YES" else "🔴" if self.direction == "NO" else "⚪"
        trigger_emoji = "🐋" if self.trigger_type == "whale" else "📰"
        
        # Score bar visual
        score_bar = self._score_bar(self.score_total, 100)
        
        # Momentum indicator
        momentum_indicator = ""
        if self.momentum_score >= 9:
            momentum_indicator = " 🚀🚀 FAST MOVE"
        elif self.momentum_score >= 7:
            momentum_indicator = " 🚀"
        
        lines = [
            f"{emoji} **{self.direction}** | {self.market_name}{momentum_indicator}",
            "",
            f"{trigger_emoji} Trigger: {self.trigger_type.upper()}",
            f"📊 Odds: {self.current_odds:.1f}%" if self.current_odds else "",
            "",
            f"**🎯 Score: {self.score_total}/100** {score_bar}",
            f"├ Credibilidade: {self.score_credibility}/30",
            f"├ Recência: {self.score_recency}/20",
            f"├ Consenso: {self.score_consensus}/25",
            f"├ Especificidade: {self.score_specificity}/15",
            f"└ Divergência: {self.score_divergence}/10",
            "",
            f"**🤖 AI Confidence: {self.confidence}%**",
            f"_{self.reasoning[:200]}{'...' if len(self.reasoning) > 200 else ''}_",
            "",
        ]
        
        # Key points
        if self.key_points:
            lines.append("**📋 Key Points:**")
            for point in self.key_points[:3]:
                lines.append(f"• {point}")
            lines.append("")
        
        # Sources summary
        if self.source_breakdown:
            sources_str = " | ".join([f"{k}: {v}" for k, v in self.source_breakdown.items()])
            lines.append(f"**📚 Sources:** {sources_str}")
        
        # Top source links (max 3)
        if self.sources:
            lines.append("")
            lines.append("**🔗 Read More:**")
            seen_urls = set()
            link_count = 0
            for src in self.sources[:10]:  # Check first 10
                url = src.get("url", "")
                title = src.get("title", "Source")[:50]
                if url and url not in seen_urls and link_count < 3:
                    seen_urls.add(url)
                    lines.append(f"• [{title}]({url})")
                    link_count += 1
        
        # Polymarket link
        if self.market_slug:
            lines.append("")
            lines.append(f"**📈 Trade:** [Polymarket](https://polymarket.com/event/{self.market_slug})")
        
        lines.append("")
        lines.append(f"⏰ {self.timestamp.strftime('%Y-%m-%d %H:%M')}")
        
        return "\n".join(lines)
    
    def _score_bar(self, value: int, max_value: int, width: int = 10) -> str:
        """Cria barra de progresso visual."""
        filled = int((value / max_value) * width)
        empty = width - filled
        return f"[{'█' * filled}{'░' * empty}]"
    
    @classmethod
    def from_analysis(
        cls,
        market_id: str,
        market_name: str,
        trigger_type: str,
        trigger_data: Dict,
        llm_result: Dict,  # {direction, confidence, reasoning, key_points}
        score_result: Any,  # ScoreResult from AlignmentScorer
        research_results: Any,  # ResearchResults from ResearchLoop
        current_odds: float = None,
        processing_time_ms: int = 0,
        market_slug: str = "",
        market_liquidity: float = None,
        momentum_score: int = 0,
        **kwargs,  # Allow additional fields
    ) -> "EnrichedSignal":
        """
        Factory method para criar EnrichedSignal a partir de resultados de análise.
        """
        # Extrair scores dos componentes
        score_credibility = 0
        score_recency = 0
        score_consensus = 0
        score_specificity = 0
        score_divergence = 0
        
        if score_result and hasattr(score_result, 'components'):
            for comp in score_result.components:
                if comp.name == "Credibilidade":
                    score_credibility = int(comp.score)
                elif comp.name == "Recência":
                    score_recency = int(comp.score)
                elif comp.name == "Consenso":
                    score_consensus = int(comp.score)
                elif comp.name == "Especificidade":
                    score_specificity = int(comp.score)
                elif comp.name == "Divergência":
                    score_divergence = int(comp.score)
        
        # Calcular should_alert
        score_total = int(score_result.total_score) if score_result else 0
        llm_confidence = int(llm_result.get("confidence", 0)) if llm_result else 0
        direction = llm_result.get("direction", "HOLD") if llm_result else "HOLD"
        
        # Base criteria
        base_criteria = (
            score_total >= 70 
            and llm_confidence >= 60 
            and direction in ["YES", "NO"]
        )
        
        # Liquidity check (fail-open: if unknown, allow)
        liquidity_ok = True
        market_liquidity = kwargs.get("market_liquidity")
        if market_liquidity is not None and market_liquidity < 10000:  # $10k threshold
            liquidity_ok = False
            logger.info(
                "liquidity_filter_triggered",
                market_id=market_id,
                market_name=market_name,
                liquidity=market_liquidity,
                threshold=10000
            )
        
        should_alert = base_criteria and liquidity_ok
        
        return cls(
            market_id=market_id,
            market_name=market_name,
            market_slug=market_slug,
            direction=direction,
            should_alert=should_alert,
            trigger_type=trigger_type,
            trigger_data=trigger_data,
            confidence=llm_confidence,
            reasoning=llm_result.get("reasoning", "") if llm_result else "",
            key_points=llm_result.get("key_points", []) if llm_result else [],
            score_total=score_total,
            score_credibility=score_credibility,
            score_recency=score_recency,
            score_consensus=score_consensus,
            score_specificity=score_specificity,
            score_divergence=score_divergence,
            sources=[r.to_dict() if hasattr(r, 'to_dict') else r for r in (research_results.results if research_results else [])],
            source_breakdown=research_results.source_breakdown if research_results else {},
            current_odds=current_odds,
            market_liquidity=market_liquidity,
            momentum_score=momentum_score,
            processing_time_ms=processing_time_ms,
        )
