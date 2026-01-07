"""
ExaSignal - Cliente Exa API (Fallback)
Pesquisa semântica - usar apenas quando APIs gratuitas não retornam resultados suficientes.

URL: https://exa.ai/
Documentação: https://docs.exa.ai/
Custo: ~$0.01-0.05 por pesquisa
"""
from typing import Dict, List, Any, Optional

from src.utils.config import Config
from src.utils.logger import logger

try:
    from exa_py import Exa
    EXA_AVAILABLE = True
except ImportError:
    EXA_AVAILABLE = False


class ExaClient:
    """Cliente para Exa API (fallback para pesquisa semântica)."""
    
    def __init__(self, api_key: str = None):
        """Inicializa cliente Exa."""
        self.api_key = api_key or Config.EXA_API_KEY
        self.enabled = Config.USE_EXA_FALLBACK and EXA_AVAILABLE and self.api_key
        
        if self.enabled:
            self.client = Exa(api_key=self.api_key)
        else:
            self.client = None
            if not EXA_AVAILABLE:
                logger.warning("exa_not_available", reason="exa_py not installed")
            elif not self.api_key:
                logger.warning("exa_not_available", reason="no API key")
    
    async def search(
        self,
        query: str,
        max_results: int = 10,
        days_back: int = 90
    ) -> List[Dict[str, Any]]:
        """Executa pesquisa semântica na Exa."""
        if not self.enabled:
            logger.debug("exa_disabled", query=query)
            return []
        
        try:
            # Calcular data mínima
            from datetime import datetime, timedelta
            start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            
            response = self.client.search(
                query=query,
                num_results=max_results,
                start_published_date=start_date,
                use_autoprompt=True,
                category="research"
            )
            
            results = []
            for r in response.results:
                results.append({
                    "title": r.title or "",
                    "url": r.url or "",
                    "excerpt": (r.text or "")[:300],
                    "published_date": r.published_date or "",
                    "source": "exa",
                    "score": r.score or 0.0
                })
            
            logger.info("exa_search_complete", query=query, results=len(results))
            return results
            
        except Exception as e:
            logger.error("exa_search_error", query=query, error=str(e))
            return []
