"""
ExaSignal - Modelo de Resultado de Pesquisa
Baseado em PRD-03-Research-Loop
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ResearchResult:
    """Representa um resultado individual de pesquisa."""
    
    title: str
    url: str
    excerpt: str
    author: Optional[str] = None
    source_type: str = "unknown"  # "researcher", "lab_blog", "analyst", "anonymous"
    published_date: Optional[datetime] = None
    relevance_score: float = 0.0
    direction: str = "NEUTRAL"  # "YES", "NO", "NEUTRAL"
    source: str = ""  # "newsapi", "rss", "arxiv", "exa"
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "title": self.title,
            "url": self.url,
            "excerpt": self.excerpt,
            "author": self.author,
            "source_type": self.source_type,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "relevance_score": self.relevance_score,
            "direction": self.direction,
            "source": self.source
        }


@dataclass
class ResearchResults:
    """Representa resultados agregados de pesquisa para um evento."""
    
    market_id: str
    whale_event_id: str
    queries_executed: List[str] = field(default_factory=list)
    results: List[ResearchResult] = field(default_factory=list)
    execution_time_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    source_breakdown: Dict[str, int] = field(default_factory=dict)  # {source: count}
    
    @property
    def total_results(self) -> int:
        return len(self.results)
    
    def get_by_direction(self, direction: str) -> List[ResearchResult]:
        """Filtra resultados por direção."""
        return [r for r in self.results if r.direction == direction]
    
    def get_by_source(self, source: str) -> List[ResearchResult]:
        """Filtra resultados por fonte."""
        return [r for r in self.results if r.source == source]
    
    def get_consensus_percent(self, direction: str) -> float:
        """Calcula % de consenso para uma direção."""
        directional = [r for r in self.results if r.direction in ["YES", "NO"]]
        if not directional:
            return 0.0
        aligned = sum(1 for r in directional if r.direction == direction)
        return (aligned / len(directional)) * 100
