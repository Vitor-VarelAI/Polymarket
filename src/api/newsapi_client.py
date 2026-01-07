"""
ExaSignal - Cliente NewsAPI
Para buscar notícias sobre AI/tech.

URL: https://newsapi.org/
Documentação: https://newsapi.org/docs
Tier Gratuito: 100 requests/dia
"""
import httpx
from datetime import datetime, timedelta
from typing import Dict, List, Any

from src.utils.config import Config
from src.utils.logger import logger


class NewsAPIClient:
    """Cliente para NewsAPI (tier gratuito)."""
    
    BASE_URL = "https://newsapi.org/v2"
    TIMEOUT = 30.0
    
    def __init__(self, api_key: str = None):
        """Inicializa cliente com API key."""
        self.api_key = api_key or Config.NEWSAPI_KEY
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=self.TIMEOUT,
            headers={"X-Api-Key": self.api_key}
        )
    
    async def close(self):
        """Fecha conexão do cliente."""
        await self.client.aclose()
    
    async def search_articles(
        self,
        query: str,
        max_results: int = 10,
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """Busca artigos recentes sobre um tema."""
        try:
            from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            
            response = await self.client.get(
                "/everything",
                params={
                    "q": query,
                    "language": "en",
                    "sortBy": "relevancy",
                    "pageSize": max_results,
                    "from": from_date
                }
            )
            response.raise_for_status()
            data = response.json()
            
            articles = data.get("articles", [])
            logger.info(
                "newsapi_search_complete",
                query=query,
                results=len(articles)
            )
            return articles
            
        except httpx.HTTPError as e:
            logger.error("newsapi_search_error", query=query, error=str(e))
            return []
