"""
ExaSignal - Cliente ArXiv API
Para buscar papers acadêmicos sobre AI/ML.

URL: http://arxiv.org/help/api
Custo: 100% GRÁTIS
"""
import httpx
import xml.etree.ElementTree as ET
from typing import Dict, List, Any

from src.utils.logger import logger


class ArXivClient:
    """Cliente para ArXiv API (papers acadêmicos)."""
    
    BASE_URL = "https://export.arxiv.org/api/query"  # HTTPS to avoid 301 redirects
    TIMEOUT = 30.0
    
    def __init__(self):
        """Inicializa cliente HTTP."""
        self.client = httpx.AsyncClient(timeout=self.TIMEOUT)
    
    async def close(self):
        """Fecha conexão do cliente."""
        await self.client.aclose()
    
    async def search_papers(
        self,
        query: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Busca papers no ArXiv."""
        try:
            response = await self.client.get(
                self.BASE_URL,
                params={
                    "search_query": f"all:{query}",
                    "start": 0,
                    "max_results": max_results,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending"
                }
            )
            response.raise_for_status()
            
            # Parse XML
            papers = self._parse_response(response.text)
            logger.info("arxiv_search_complete", query=query, results=len(papers))
            return papers
            
        except Exception as e:
            logger.error("arxiv_search_error", query=query, error=str(e))
            return []
    
    def _parse_response(self, xml_text: str) -> List[Dict[str, Any]]:
        """Parse XML response do ArXiv."""
        papers = []
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        
        root = ET.fromstring(xml_text)
        
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns)
            url = entry.find("atom:id", ns)
            summary = entry.find("atom:summary", ns)
            published = entry.find("atom:published", ns)
            
            authors = []
            for author in entry.findall("atom:author", ns):
                name = author.find("atom:name", ns)
                if name is not None:
                    authors.append(name.text)
            
            papers.append({
                "title": title.text.strip() if title is not None else "",
                "url": url.text if url is not None else "",
                "excerpt": summary.text.strip()[:300] if summary is not None else "",
                "authors": authors,
                "published_date": published.text if published is not None else "",
                "source": "arxiv"
            })
        
        return papers
