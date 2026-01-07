"""
ExaSignal - Modelo de Mercado
Baseado em PRD-01-Market-Management
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Market:
    """Representa um mercado do Polymarket monitorado pelo ExaSignal."""
    
    market_id: str
    market_name: str
    yes_definition: str
    no_definition: str
    category: str  # "AI" ou "frontier_tech"
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    def validate(self) -> Tuple[bool, List[str]]:
        """Valida campos do mercado. Retorna (is_valid, errors)."""
        errors = []
        
        # Campos obrigatórios
        if not self.market_id:
            errors.append("market_id é obrigatório")
        if not self.market_name:
            errors.append("market_name é obrigatório")
        if not self.yes_definition:
            errors.append("yes_definition é obrigatório")
        if not self.no_definition:
            errors.append("no_definition é obrigatório")
        
        # Categoria válida (qualquer string não vazia)
        if not self.category or not self.category.strip():
            errors.append("category é obrigatório")
        
        # Limites de tamanho
        if len(self.market_name) > 200:
            errors.append("market_name excede 200 caracteres")
        if len(self.yes_definition) > 500:
            errors.append("yes_definition excede 500 caracteres")
        if len(self.no_definition) > 500:
            errors.append("no_definition excede 500 caracteres")
        
        return (len(errors) == 0, errors)
    
    def to_dict(self) -> dict:
        """Converte mercado para dicionário."""
        return {
            "market_id": self.market_id,
            "market_name": self.market_name,
            "yes_definition": self.yes_definition,
            "no_definition": self.no_definition,
            "category": self.category,
            "description": self.description,
            "tags": self.tags,
        }
