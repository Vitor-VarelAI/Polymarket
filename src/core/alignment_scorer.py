"""
ExaSignal - Alignment Scorer
Baseado em PRD-04-Alignment-Score

Score determinístico 0-100 com 5 componentes:
A. Credibilidade da Fonte (0-30)
B. Recência (0-20) - NewsAPI penalizada
C. Consenso Direcional (0-25)
D. Especificidade (0-15)
E. Divergência vs Odds (0-10)

Regra de Ouro:
> "A notícia nunca é o trigger. O trigger é sempre o movimento do whale."
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.models.whale_event import WhaleEvent
from src.models.research_result import ResearchResult, ResearchResults
from src.models.score_result import ScoreComponent, ScoreResult
from src.utils.config import Config
from src.utils.logger import logger


# Hierarquia de credibilidade de fontes
SOURCE_CREDIBILITY = {
    # Alta credibilidade (researchers, labs)
    "arxiv": 30,
    "exa": 28,  # Depende do conteúdo
    
    # Média credibilidade (blogs técnicos, RSS de labs)
    "rss": 20,
    
    # Baixa credibilidade (notícias genéricas)
    "newsapi": 12,  # Penalizada - nunca fonte primária
}

# Penalização de recência por fonte
SOURCE_RECENCY_PENALTY = {
    "newsapi": 0.5,  # 50% de desconto na recência (24h delay)
    "rss": 1.0,
    "arxiv": 0.9,  # Papers podem ser mais antigos
    "exa": 1.0,
}


class AlignmentScorer:
    """Calcula score de alinhamento entre whale event e research."""
    
    THRESHOLD = 70  # Mínimo para gerar alerta
    
    def __init__(self, current_odds: float = None):
        """Inicializa scorer."""
        self.current_odds = current_odds or 50.0  # % de YES
    
    def calculate(
        self,
        whale_event: WhaleEvent,
        research: ResearchResults,
        current_odds: float = None
    ) -> ScoreResult:
        """Calcula score completo."""
        if current_odds:
            self.current_odds = current_odds
        
        components = []
        
        # A. Credibilidade da Fonte (0-30)
        cred = self._calc_credibility(research)
        components.append(cred)
        
        # B. Recência (0-20)
        recency = self._calc_recency(research)
        components.append(recency)
        
        # C. Consenso Direcional (0-25)
        consensus = self._calc_consensus(whale_event.direction, research)
        components.append(consensus)
        
        # D. Especificidade (0-15)
        specificity = self._calc_specificity(research)
        components.append(specificity)
        
        # E. Divergência vs Odds (0-10)
        divergence = self._calc_divergence(whale_event.direction)
        components.append(divergence)
        
        # Calcular total
        total_score = sum(c.score for c in components)
        
        # Identificar top 2 razões
        top_reasons = self._get_top_reasons(components)
        
        # Decisão de alerta
        should_alert = total_score >= self.THRESHOLD
        
        result = ScoreResult(
            market_id=whale_event.market_id,
            whale_direction=whale_event.direction,
            total_score=total_score,
            components=components,
            top_reasons=top_reasons,
            should_alert=should_alert
        )
        
        logger.info(
            "alignment_score_calculated",
            market_id=whale_event.market_id,
            score=total_score,
            should_alert=should_alert
        )
        
        return result
    
    def calculate_for_news(
        self,
        market_id: str,
        news_direction: str,  # Detected from news sentiment or LLM
        research: ResearchResults,
        current_odds: float = None
    ) -> ScoreResult:
        """
        Calcula score para sinais originados de notícias (não whale).
        
        Cria um WhaleEvent sintético para usar a mesma lógica de scoring.
        
        Args:
            market_id: ID do mercado
            news_direction: Direção inferida da notícia ("YES", "NO", "NEUTRAL")
            research: Resultados de pesquisa
            current_odds: Odds atuais do mercado
        
        Returns:
            ScoreResult com as 5 dimensões de score
        """
        from src.models.whale_event import WhaleEvent
        
        # Criar whale event sintético
        synthetic_whale = WhaleEvent(
            market_id=market_id,
            direction=news_direction if news_direction in ["YES", "NO"] else "YES",
            size_usd=0,  # Sem whale size (é um trigger de notícia)
            wallet_address="news_trigger",
            wallet_age_days=0,
            liquidity_ratio=0,
            timestamp=datetime.now(),
            is_new_position=True,
            previous_position_size=0
        )
        
        result = self.calculate(synthetic_whale, research, current_odds)
        
        logger.info(
            "alignment_score_for_news",
            market_id=market_id,
            direction=news_direction,
            score=result.total_score
        )
        
        return result
    
    def _calc_credibility(self, research: ResearchResults) -> ScoreComponent:
        """A. Credibilidade da Fonte (0-30)."""
        if not research.results:
            return ScoreComponent("Credibilidade", 0, 30, "Sem resultados")
        
        # Média ponderada das credibilidades
        total_cred = 0
        for r in research.results:
            total_cred += SOURCE_CREDIBILITY.get(r.source, 10)
        
        avg_cred = total_cred / len(research.results)
        score = min(avg_cred, 30)
        
        best_source = max(research.results, key=lambda r: SOURCE_CREDIBILITY.get(r.source, 0))
        reason = f"Melhor fonte: {best_source.source}"
        
        return ScoreComponent("Credibilidade", score, 30, reason)
    
    def _calc_recency(self, research: ResearchResults) -> ScoreComponent:
        """B. Recência (0-20) - NewsAPI penalizada."""
        if not research.results:
            return ScoreComponent("Recência", 0, 20, "Sem resultados")
        
        now = datetime.now()
        total_score = 0
        count = 0
        
        for r in research.results:
            if not r.published_date:
                continue
            
            days_old = (now - r.published_date).days
            
            # Score base por dias
            if days_old <= 1:
                base = 20
            elif days_old <= 3:
                base = 17
            elif days_old <= 7:
                base = 14
            elif days_old <= 14:
                base = 10
            elif days_old <= 30:
                base = 5
            else:
                base = 2
            
            # Aplicar penalização por fonte (NewsAPI = 50%)
            penalty = SOURCE_RECENCY_PENALTY.get(r.source, 1.0)
            total_score += base * penalty
            count += 1
        
        avg_score = (total_score / count) if count > 0 else 0
        score = min(avg_score, 20)
        
        return ScoreComponent("Recência", score, 20, f"{count} fontes analisadas")
    
    def _calc_consensus(self, whale_dir: str, research: ResearchResults) -> ScoreComponent:
        """C. Consenso Direcional (0-25)."""
        if not research.results:
            return ScoreComponent("Consenso", 0, 25, "Sem resultados")
        
        # Contar direções
        directional = [r for r in research.results if r.direction in ["YES", "NO"]]
        if not directional:
            return ScoreComponent("Consenso", 5, 25, "Sem direção clara")
        
        aligned = sum(1 for r in directional if r.direction == whale_dir)
        consensus_pct = (aligned / len(directional)) * 100
        
        # Score baseado em % de alinhamento
        if consensus_pct >= 80:
            score = 25
            reason = f"{consensus_pct:.0f}% alinhado - Forte"
        elif consensus_pct >= 60:
            score = 18
            reason = f"{consensus_pct:.0f}% alinhado - Moderado"
        elif consensus_pct >= 40:
            score = 10
            reason = f"{consensus_pct:.0f}% alinhado - Misto"
        else:
            score = 3
            reason = f"{consensus_pct:.0f}% alinhado - Contra"
        
        return ScoreComponent("Consenso", score, 25, reason)
    
    def _calc_specificity(self, research: ResearchResults) -> ScoreComponent:
        """D. Especificidade (0-15)."""
        if not research.results:
            return ScoreComponent("Especificidade", 0, 15, "Sem resultados")
        
        # Verificar tipos de fonte de alta especificidade
        high_spec = ["arxiv"]
        med_spec = ["exa", "rss"]
        
        high_count = sum(1 for r in research.results if r.source in high_spec)
        med_count = sum(1 for r in research.results if r.source in med_spec)
        
        if high_count >= 2:
            score = 15
            reason = f"{high_count} fontes de alta especificidade"
        elif high_count >= 1:
            score = 12
            reason = f"{high_count} fonte técnica encontrada"
        elif med_count >= 2:
            score = 8
            reason = "Fontes de média especificidade"
        else:
            score = 4
            reason = "Fontes genéricas apenas"
        
        return ScoreComponent("Especificidade", score, 15, reason)
    
    def _calc_divergence(self, whale_dir: str) -> ScoreComponent:
        """E. Divergência vs Odds (0-10)."""
        # Se whale aposta YES mas odds são baixas (mercado discorda)
        # = maior potencial de alpha
        
        if whale_dir == "YES":
            divergence = 100 - self.current_odds  # Quanto menor odds, maior divergência
        else:
            divergence = self.current_odds  # Quanto maior odds, maior divergência
        
        if divergence >= 40:
            score = 10
            reason = f"Alta divergência ({divergence:.0f}%)"
        elif divergence >= 25:
            score = 7
            reason = f"Divergência moderada ({divergence:.0f}%)"
        elif divergence >= 15:
            score = 4
            reason = f"Baixa divergência ({divergence:.0f}%)"
        else:
            score = 1
            reason = "Whale segue consenso"
        
        return ScoreComponent("Divergência", score, 10, reason)
    
    def _get_top_reasons(self, components: List[ScoreComponent]) -> List[str]:
        """Identifica top 2 razões para o score."""
        # Ordenar por score relativo ao máximo
        sorted_comps = sorted(
            components,
            key=lambda c: c.score / c.max_score if c.max_score > 0 else 0,
            reverse=True
        )
        
        return [
            f"{c.name}: {c.reason}"
            for c in sorted_comps[:2]
        ]
