"""
ExaSignal - Modelo de Score de Alinhamento
Baseado em PRD-04-Alignment-Score
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class ScoreComponent:
    """Componente individual do score."""
    name: str
    score: float
    max_score: float
    reason: str
    
    @property
    def percentage(self) -> float:
        return (self.score / self.max_score * 100) if self.max_score > 0 else 0


@dataclass
class ScoreResult:
    """Resultado completo do cálculo de alignment score."""
    
    market_id: str
    whale_direction: str  # "YES" ou "NO"
    total_score: float  # 0-100
    components: List[ScoreComponent] = field(default_factory=list)
    top_reasons: List[str] = field(default_factory=list)  # Top 2 razões
    should_alert: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "market_id": self.market_id,
            "whale_direction": self.whale_direction,
            "total_score": self.total_score,
            "should_alert": self.should_alert,
            "components": [
                {
                    "name": c.name,
                    "score": c.score,
                    "max_score": c.max_score,
                    "reason": c.reason
                }
                for c in self.components
            ],
            "top_reasons": self.top_reasons
        }
    
    @property
    def score_formatted(self) -> str:
        """Score formatado com cor emoji."""
        if self.total_score >= 80:
            return f"🟢 {self.total_score:.0f}/100"
        elif self.total_score >= 60:
            return f"🟡 {self.total_score:.0f}/100"
        return f"🔴 {self.total_score:.0f}/100"
