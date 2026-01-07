"""
ExaSignal - Gestor de Mercados
Baseado em PRD-01-Market-Management
"""
from pathlib import Path
from typing import List, Optional

import yaml

from src.models.market import Market
from src.utils.logger import logger


class MarketManager:
    """Carrega e gerencia mercados pré-definidos de markets.yaml."""
    
    MIN_MARKETS = 1   # Mínimo flexível
    MAX_MARKETS = 1000  # Suporte para whale tracking em grande escala
    
    def __init__(self, config_path: str = "markets.yaml"):
        """Inicializa e carrega mercados do arquivo YAML."""
        self.config_path = Path(config_path)
        self.markets: List[Market] = []
        self._market_index: dict = {}  # market_id -> Market (para lookup rápido)
        self._load_markets()
    
    def _load_markets(self) -> None:
        """Carrega e valida mercados do arquivo YAML."""
        # Verificar se arquivo existe
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"markets.yaml não encontrado em {self.config_path}"
            )
        
        # Carregar YAML
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        if "markets" not in data:
            raise ValueError("markets.yaml deve conter chave 'markets'")
        
        markets_data = data["markets"]
        
        if not isinstance(markets_data, list):
            raise ValueError("'markets' deve ser uma lista")
        
        # Validar quantidade
        count = len(markets_data)
        if count < self.MIN_MARKETS or count > self.MAX_MARKETS:
            raise ValueError(
                f"Deve ter {self.MIN_MARKETS}-{self.MAX_MARKETS} mercados, "
                f"encontrou {count}"
            )
        
        # Carregar e validar cada mercado
        market_ids = set()
        for m_data in markets_data:
            market = Market(**m_data)
            
            # Validar campos
            is_valid, errors = market.validate()
            if not is_valid:
                raise ValueError(f"Mercado inválido: {', '.join(errors)}")
            
            # Verificar duplicatas
            if market.market_id in market_ids:
                raise ValueError(f"market_id duplicado: {market.market_id}")
            
            market_ids.add(market.market_id)
            self.markets.append(market)
            self._market_index[market.market_id] = market
        
        logger.info(
            "markets_loaded",
            count=len(self.markets),
            categories=[m.category for m in self.markets]
        )
    
    def get_all_markets(self) -> List[Market]:
        """Retorna lista completa de mercados válidos."""
        return self.markets.copy()
    
    def get_market_by_id(self, market_id: str) -> Optional[Market]:
        """Retorna mercado específico por ID, ou None se não existir."""
        return self._market_index.get(market_id)
    
    def is_valid_market(self, market_id: str) -> bool:
        """Verifica se market_id existe na lista de mercados."""
        return market_id in self._market_index
