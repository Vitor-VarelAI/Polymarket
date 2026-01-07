"""
ExaSignal - Brave Search API Client
Pesquisa web gratuita de alta qualidade.

Free Tier: 
- 2000 queries/mês
- 1 request/segundo
- Web, News, Images, Videos

Docs: https://api.search.brave.com/
"""
import os
import asyncio
import httpx
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.utils.logger import logger


class BraveSearchClient:
    """
    Cliente para Brave Search API.
    
    Free tier: 2000 queries/mês, 1 req/segundo
    Qualidade: Alta (comparable to Google)
    """
    
    BASE_URL = "https://api.search.brave.com/res/v1"
    TIMEOUT = 30.0
    RATE_LIMIT_DELAY = 1.1  # 1.1s entre requests para evitar 429
    
    def __init__(self, api_key: str = None):
        """
        Inicializa cliente Brave Search.
        
        Args:
            api_key: API key do Brave Search (ou BRAVE_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("BRAVE_API_KEY")
        self.enabled = bool(self.api_key)
        self._last_request_time = 0
        
        if self.enabled:
            self.client = httpx.AsyncClient(
                timeout=self.TIMEOUT,
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self.api_key
                }
            )
            logger.info("brave_client_initialized")
        else:
            self.client = None
            logger.warning("brave_client_disabled", reason="No BRAVE_API_KEY")
    
    async def _wait_for_rate_limit(self):
        """Espera para respeitar rate limit de 1 req/segundo."""
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            wait_time = self.RATE_LIMIT_DELAY - elapsed
            await asyncio.sleep(wait_time)
        self._last_request_time = time.time()
    
    async def close(self):
        """Fecha conexão do cliente."""
        if self.client:
            await self.client.aclose()
    
    async def search(
        self,
        query: str,
        count: int = 10,
        freshness: str = "pw",  # past week
        search_type: str = "web"  # web, news
    ) -> List[Dict[str, Any]]:
        """
        Pesquisa no Brave Search.
        
        Args:
            query: Termo de pesquisa
            count: Número de resultados (max 20)
            freshness: pd (day), pw (week), pm (month), py (year)
            search_type: "web" ou "news"
        
        Returns:
            Lista de resultados {title, url, description, published_date}
        """
        if not self.enabled:
            return []
        
        try:
            # Respeitar rate limit (1 req/segundo)
            await self._wait_for_rate_limit()
            
            endpoint = f"{self.BASE_URL}/web/search" if search_type == "web" else f"{self.BASE_URL}/news/search"
            
            response = await self.client.get(
                endpoint,
                params={
                    "q": query,
                    "count": min(count, 20),
                    "freshness": freshness,
                    "text_decorations": False,
                    "safesearch": "off"
                }
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            
            # Parse web results
            if search_type == "web" and "web" in data:
                for item in data["web"].get("results", [])[:count]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "description": item.get("description", "")[:300],
                        "source": "brave",
                        "published_date": item.get("age", ""),
                    })
            
            # Parse news results
            elif search_type == "news" and "news" in data:
                for item in data["news"].get("results", [])[:count]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "description": item.get("description", "")[:300],
                        "source": "brave",
                        "published_date": item.get("age", ""),
                        "meta_url": item.get("meta_url", {}).get("hostname", "")
                    })
            
            logger.info(
                "brave_search_complete",
                query=query[:50],
                results=len(results),
                type=search_type
            )
            
            return results
            
        except Exception as e:
            logger.error("brave_search_error", query=query[:50], error=str(e))
            return []
    
    async def search_news(self, query: str, count: int = 10) -> List[Dict[str, Any]]:
        """Atalho para pesquisa de notícias."""
        return await self.search(query, count=count, search_type="news")
    
    async def search_web(self, query: str, count: int = 10) -> List[Dict[str, Any]]:
        """Atalho para pesquisa web."""
        return await self.search(query, count=count, search_type="web")


# Singleton instance
brave = BraveSearchClient()
