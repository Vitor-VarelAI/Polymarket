"""
ExaSignal - Cliente RSS Feeds
16+ feeds de qualidade para AI/frontier tech + Google News RSS.

Fontes: TechCrunch, Wired, MIT Tech Review, OpenAI Blog, DeepMind, Google News, etc.
Custo: 100% GRÁTIS
"""
import asyncio
import feedparser
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List, Any

from src.utils.logger import logger


# Lista de RSS feeds de qualidade
RSS_FEEDS = [
    # Tech & AI News
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://www.wired.com/feed/rss",
    "https://www.technologyreview.com/feed/",
    "https://spectrum.ieee.org/rss",
    
    # AI Research & Labs
    "https://openai.com/blog/rss.xml",
    "https://deepmind.com/blog/feed/basic/",
    "https://www.anthropic.com/index.xml",
    "https://ai.googleblog.com/feeds/posts/default",
    "https://ai.meta.com/blog/feed/",
    
    # Academic & Research
    "http://arxiv.org/rss/cs.AI",
    "http://arxiv.org/rss/cs.LG",
    "https://hnrss.org/newest?q=AI",
    "https://www.lesswrong.com/feed.xml",
    
    # Industry Analysis
    "https://venturebeat.com/ai/feed/",
    "https://www.artificialintelligence-news.com/feed/",
]

# Google News RSS base URL
GOOGLE_NEWS_RSS_BASE = "https://news.google.com/rss/search"


class RSSClient:
    """Cliente para múltiplos RSS feeds incluindo Google News."""
    
    def __init__(self, feeds: List[str] = None):
        """Inicializa com lista de feeds."""
        self.feeds = feeds or RSS_FEEDS
    
    async def search_google_news(
        self,
        query: str,
        max_results: int = 15,
        language: str = "en",
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Pesquisa Google News RSS (GRÁTIS, SEM LIMITES).
        
        Args:
            query: Termo de pesquisa
            max_results: Máximo de resultados
            language: Código de idioma (en, pt, es, etc)
            days_back: Filtrar por dias
        
        Returns:
            Lista de resultados de notícias
        """
        results = []
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        try:
            # Encode query for URL
            encoded_query = urllib.parse.quote(query)
            feed_url = f"{GOOGLE_NEWS_RSS_BASE}?q={encoded_query}&hl={language}&gl=US&ceid=US:{language}"
            
            # Parse feed
            feed = await asyncio.get_event_loop().run_in_executor(
                None, feedparser.parse, feed_url
            )
            
            for entry in feed.entries[:max_results * 2]:  # Get extra, filter later
                pub_date = self._parse_date(entry)
                
                # Filtrar por data se possível
                if pub_date and pub_date < cutoff_date:
                    continue
                
                # Extrair fonte do título (Google News format: "Title - Source")
                title = entry.get("title", "")
                source = "Google News"
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    if len(parts) == 2:
                        title = parts[0]
                        source = parts[1]
                
                results.append({
                    "title": title,
                    "url": entry.get("link", ""),
                    "excerpt": entry.get("summary", "")[:300] if entry.get("summary") else "",
                    "published_date": pub_date.isoformat() if pub_date else "",
                    "source": f"google_news:{source}",
                    "source_name": source,
                })
                
                if len(results) >= max_results:
                    break
            
            logger.info(
                "google_news_rss_complete",
                query=query[:50],
                results=len(results)
            )
            
        except Exception as e:
            logger.error("google_news_rss_error", query=query[:50], error=str(e))
        
        return results
    
    async def search_feeds(
        self,
        keywords: List[str],
        max_results: int = 10,
        days_back: int = 7,
        include_google_news: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Busca em múltiplos RSS feeds por keywords.
        
        Args:
            keywords: Lista de palavras-chave
            max_results: Máximo de resultados
            days_back: Dias para trás
            include_google_news: Se deve incluir Google News RSS
        """
        results = []
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # 1. Google News RSS (paralelo)
        google_results = []
        if include_google_news:
            query = " ".join(keywords[:5])  # Limitar query
            google_results = await self.search_google_news(query, max_results=max_results)
        
        # 2. RSS feeds tradicionais
        for feed_url in self.feeds:
            try:
                feed = await asyncio.get_event_loop().run_in_executor(
                    None, feedparser.parse, feed_url
                )
                
                for entry in feed.entries[:20]:
                    text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
                    if any(kw.lower() in text for kw in keywords):
                        pub_date = self._parse_date(entry)
                        if pub_date and pub_date >= cutoff_date:
                            results.append({
                                "title": entry.get("title", ""),
                                "url": entry.get("link", ""),
                                "excerpt": entry.get("summary", "")[:300],
                                "published_date": pub_date.isoformat(),
                                "source": feed_url
                            })
            except Exception as e:
                logger.warning("rss_feed_error", feed=feed_url, error=str(e))
                continue
        
        # Combinar resultados (Google News primeiro)
        all_results = google_results + results
        
        logger.info(
            "rss_search_complete",
            keywords=keywords,
            results=len(all_results),
            google_news=len(google_results),
            traditional=len(results)
        )
        
        return all_results[:max_results]
    
    def _parse_date(self, entry) -> datetime:
        """Tenta parsear data do entry."""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime(*entry.published_parsed[:6])
        return None

