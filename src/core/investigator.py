"""
ExaSignal - Investigator (Guided Investigation)
Enhanced version with odds, scores, and direction suggestions.

Features:
- Odds em tempo real via Gamma API
- Score de confiança 0-100
- Sugestão de direção YES/NO
- Análise de sentimento dos excerpts
"""
from typing import Dict, List, Optional
from datetime import datetime
import re

from src.core.market_manager import MarketManager
from src.core.research_loop import ResearchLoop
from src.api.gamma_client import GammaClient
from src.models.research_result import ResearchResults, ResearchResult
from src.models.market import Market
from src.utils.logger import logger


# Keywords para análise de sentimento
BULLISH_KEYWORDS = [
    "breakthrough", "success", "approved", "launch", "release", "achieved",
    "milestone", "positive", "progress", "advance", "confirmed", "will",
    "expect", "likely", "soon", "imminent", "ready", "bullish", "strong"
]

BEARISH_KEYWORDS = [
    "delay", "failed", "canceled", "unlikely", "delayed", "setback",
    "problem", "issue", "concern", "doubt", "bearish", "weak", "risk",
    "obstacle", "challenged", "uncertain", "won't", "negative"
]


class Investigator:
    """Motor de investigação on-demand com análise completa."""
    
    def __init__(
        self,
        market_manager: MarketManager,
        research_loop: ResearchLoop,
        gamma_client: GammaClient = None
    ):
        self.market_manager = market_manager
        self.research_loop = research_loop
        self.gamma = gamma_client
    
    async def investigate_market(self, market_id: str) -> str:
        """
        Executa investigação completa num mercado com odds, score e sugestão.
        """
        market = self.market_manager.get_market_by_id(market_id)
        if not market:
            return "❌ Mercado não encontrado."
        
        # 1. Buscar odds atuais
        current_odds = None
        if self.gamma:
            current_odds = await self.gamma.get_market_odds(market_id)
        
        # 2. Buscar research via Exa
        results = []
        if self.research_loop.exa.enabled:
            exa_results = await self.research_loop.exa.search(
                market.market_name, 
                max_results=5
            )
            for r in exa_results:
                # Analisar sentimento do excerpt
                direction = self._analyze_sentiment(r.get("excerpt", ""))
                results.append(ResearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    excerpt=r.get("excerpt", "")[:400],
                    source="exa",
                    direction=direction
                ))
        
        # Fallback
        if not results:
            fallback_res = await self.research_loop._search_newsapi([market.market_name])
            results.extend(fallback_res)
        
        # 3. Calcular análise
        analysis = self._calculate_analysis(results, current_odds)
        
        # 4. Formatar output rico
        return self._format_full_analysis(market, results, current_odds, analysis)
    
    async def investigate_narrative(self) -> str:
        """
        Investiga narrativa geral AI/Tech com overview de mercados.
        """
        query = "State of AI and Frontier Tech progress 2024 2025"
        results = []
        
        if self.research_loop.exa.enabled:
            exa_results = await self.research_loop.exa.search(query, max_results=3)
            for r in exa_results:
                direction = self._analyze_sentiment(r.get("excerpt", ""))
                results.append(ResearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    excerpt=r.get("excerpt", "")[:300],
                    source="exa",
                    direction=direction
                ))
        
        # Obter overview dos top 5 mercados
        market_overview = await self._get_markets_overview()
        
        return self._format_narrative_analysis(results, market_overview)
    
    def _analyze_sentiment(self, text: str) -> str:
        """Analisa sentimento do texto para determinar direção."""
        if not text:
            return "NEUTRAL"
        
        text_lower = text.lower()
        
        bullish_count = sum(1 for kw in BULLISH_KEYWORDS if kw in text_lower)
        bearish_count = sum(1 for kw in BEARISH_KEYWORDS if kw in text_lower)
        
        if bullish_count > bearish_count + 1:
            return "YES"
        elif bearish_count > bullish_count + 1:
            return "NO"
        return "NEUTRAL"
    
    def _calculate_analysis(
        self, 
        results: List[ResearchResult], 
        current_odds: Optional[float]
    ) -> Dict:
        """Calcula score e análise baseado nos resultados."""
        if not results:
            return {
                "score": 0,
                "confidence": "Baixa",
                "direction": "NEUTRAL",
                "direction_emoji": "⚪",
                "consensus": 0,
                "source_quality": 0
            }
        
        # Contar direções
        yes_count = sum(1 for r in results if r.direction == "YES")
        no_count = sum(1 for r in results if r.direction == "NO")
        neutral_count = sum(1 for r in results if r.direction == "NEUTRAL")
        total = len(results)
        
        # Determinar direção majoritária
        if yes_count > no_count:
            direction = "YES"
            direction_emoji = "🟢"
            consensus = (yes_count / total) * 100
        elif no_count > yes_count:
            direction = "NO"
            direction_emoji = "🔴"
            consensus = (no_count / total) * 100
        else:
            direction = "NEUTRAL"
            direction_emoji = "⚪"
            consensus = 50
        
        # Calcular score (simplificado)
        # Base: qualidade das fontes (Exa = alta qualidade)
        source_quality = sum(28 for r in results if r.source == "exa") / max(len(results), 1)
        
        # Bonus por consenso forte
        consensus_bonus = min(25, consensus / 4) if consensus > 60 else 0
        
        # Bonus por número de fontes
        volume_bonus = min(15, len(results) * 3)
        
        # Divergência com odds (se whale vai contra mercado)
        divergence_bonus = 0
        if current_odds and direction != "NEUTRAL":
            if direction == "YES" and current_odds < 40:
                divergence_bonus = 10  # Apostando YES quando mercado diz NO
            elif direction == "NO" and current_odds > 60:
                divergence_bonus = 10  # Apostando NO quando mercado diz YES
        
        total_score = min(100, source_quality + consensus_bonus + volume_bonus + divergence_bonus)
        
        # Nível de confiança
        if total_score >= 75:
            confidence = "Alta"
        elif total_score >= 50:
            confidence = "Média"
        else:
            confidence = "Baixa"
        
        return {
            "score": round(total_score),
            "confidence": confidence,
            "direction": direction,
            "direction_emoji": direction_emoji,
            "consensus": round(consensus),
            "source_quality": round(source_quality),
            "yes_count": yes_count,
            "no_count": no_count,
            "neutral_count": neutral_count
        }
    
    async def _get_markets_overview(self) -> List[Dict]:
        """Obtém overview dos top mercados com odds."""
        overview = []
        markets = self.market_manager.get_all_markets()[:5]
        
        for market in markets:
            odds = None
            if self.gamma:
                odds = await self.gamma.get_market_odds(market.market_id)
            
            overview.append({
                "name": market.market_name[:40],
                "odds": odds,
                "category": market.category
            })
        
        return overview
    
    def _format_full_analysis(
        self, 
        market: Market, 
        results: List[ResearchResult],
        current_odds: Optional[float],
        analysis: Dict
    ) -> str:
        """Formata análise completa para Telegram."""
        
        # Header com mercado
        lines = [
            "📊 **Análise de Mercado**",
            "",
            f"**{market.market_name}**",
            ""
        ]
        
        # Odds e Score
        odds_str = f"{current_odds:.0f}%" if current_odds else "N/A"
        lines.extend([
            f"📈 **Odds Atuais:** {odds_str}",
            f"🎯 **Score:** {analysis['score']}/100 ({analysis['confidence']})",
            ""
        ])
        
        # Sugestão de direção
        if analysis['direction'] != "NEUTRAL":
            lines.extend([
                f"{analysis['direction_emoji']} **Tendência:** {analysis['direction']}",
                f"   _Consenso: {analysis['consensus']}% das fontes_",
                ""
            ])
        else:
            lines.extend([
                "⚪ **Tendência:** Inconclusiva",
                "   _Fontes não mostram direção clara_",
                ""
            ])
        
        # Breakdown
        lines.extend([
            "**📋 Breakdown:**",
            f"• Fontes YES: {analysis.get('yes_count', 0)}",
            f"• Fontes NO: {analysis.get('no_count', 0)}",
            f"• Neutras: {analysis.get('neutral_count', 0)}",
            ""
        ])
        
        # Top fontes
        lines.append("**🔗 Fontes:**")
        if results:
            for r in results[:3]:
                icon = "🟢" if r.direction == "YES" else "🔴" if r.direction == "NO" else "⚪"
                lines.append(f"• {icon} [{r.title[:50]}...]({r.url})")
        else:
            lines.append("• Nenhuma fonte encontrada")
        
        # Footer
        lines.extend([
            "",
            f"[Ver no Polymarket](https://polymarket.com/event/{market.market_id})",
            "",
            "⚠️ _Isto é análise automatizada, não conselho financeiro._"
        ])
        
        return "\n".join(lines)
    
    def _format_narrative_analysis(
        self, 
        results: List[ResearchResult],
        market_overview: List[Dict]
    ) -> str:
        """Formata análise de narrativa com overview de mercados."""
        
        lines = [
            "🌍 **Narrativa AI/Tech — Overview**",
            ""
        ]
        
        # Market Overview
        if market_overview:
            lines.append("**📊 Top Mercados:**")
            for m in market_overview:
                odds_str = f"{m['odds']:.0f}%" if m['odds'] else "N/A"
                emoji = "🤖" if m['category'] == "AI" else "🚀"
                lines.append(f"• {emoji} {m['name']}... ({odds_str})")
            lines.append("")
        
        # Análise de sentimento geral
        yes_trend = sum(1 for r in results if r.direction == "YES")
        no_trend = sum(1 for r in results if r.direction == "NO")
        
        if yes_trend > no_trend:
            lines.append("📈 **Sentimento Geral:** Bullish")
        elif no_trend > yes_trend:
            lines.append("📉 **Sentimento Geral:** Bearish")
        else:
            lines.append("➡️ **Sentimento Geral:** Neutro")
        
        lines.append("")
        
        # Fontes
        lines.append("**🔗 Fontes Recentes:**")
        if results:
            for r in results:
                icon = "🧠"
                lines.append(f"• {icon} [{r.title[:45]}...]({r.url})")
        else:
            lines.append("• Nenhuma fonte encontrada")
        
        lines.extend([
            "",
            "⚠️ _Análise automatizada, não conselho financeiro._"
        ])
        
        return "\n".join(lines)
