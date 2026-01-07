"""
ExaSignal - Cliente Gamma API (Polymarket)
Para obter dados de mercados, odds e volume agregado.

URL Base: https://gamma-api.polymarket.com
Documentação: https://docs.polymarket.com/developers/gamma-markets-api/overview
"""
import httpx
from typing import Dict, List, Optional, Any

from src.utils.logger import logger


class GammaClient:
    """Cliente para Gamma API do Polymarket (read-only, sem auth)."""
    
    BASE_URL = "https://gamma-api.polymarket.com"
    TIMEOUT = 30.0
    
    def __init__(self):
        """Inicializa cliente HTTP."""
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=self.TIMEOUT,
            headers={"Accept": "application/json"}
        )
    
    async def close(self):
        """Fecha conexão do cliente."""
        await self.client.aclose()
    
    async def get_market(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Obtém dados de um mercado/evento específico pelo slug."""
        try:
            # Use events endpoint with slug parameter
            response = await self.client.get("/events", params={"slug": market_id})
            response.raise_for_status()
            events = response.json()
            if events and len(events) > 0:
                return events[0]  # Return first matching event
            return None
        except httpx.HTTPError as e:
            logger.error("gamma_get_market_error", market_id=market_id, error=str(e))
            return None
    
    async def get_markets(
        self,
        active: bool = True,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Obtém lista de mercados."""
        try:
            params = {"limit": limit}
            if active:
                params["active"] = "true"
            
            response = await self.client.get("/markets", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error("gamma_get_markets_error", error=str(e))
            return []
    
    async def get_market_odds(self, market_id: str) -> Optional[float]:
        """Obtém odds atuais (YES %) de um mercado."""
        import json
        
        event = await self.get_market(market_id)
        if not event:
            return None
        
        # Estrutura: event > markets[] > outcomePrices
        markets = event.get("markets", [])
        if not markets:
            return None
        
        # Usar o primeiro market (para mercados YES/NO simples)
        market = markets[0]
        prices = market.get("outcomePrices", [])
        
        # outcomePrices pode ser string JSON ou lista
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except json.JSONDecodeError:
                return None
        
        if prices and len(prices) > 0:
            try:
                # Preços são strings como "0.28" ou "0"
                yes_price = float(prices[0])
                return yes_price * 100  # Converter para percentagem
            except (ValueError, TypeError):
                pass
        
        return None
    
    async def get_market_liquidity(self, market_id: str) -> Optional[float]:
        """Obtém liquidez total do mercado em USD."""
        market = await self.get_market(market_id)
        if market:
            return market.get("liquidity", 0.0)
        return None
