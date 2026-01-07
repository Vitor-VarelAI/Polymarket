"""
ExaSignal - Research Loop (Híbrido)
Baseado em PRD-03-Research-Loop

Estratégia ATUALIZADA:
1. Brave Search (grátis, 2000/mês) - NOVO
2. Google News RSS (grátis, ilimitado) - NOVO
3. RSS Tech feeds (grátis)
4. ArXiv papers (grátis)
5. Exa apenas se score < 60 ou < 5 resultados (pago)

Prioridade: Brave > Google News > RSS > ArXiv > Exa (backup)
"""
import asyncio
import re
from datetime import datetime
from typing import Dict, List, Optional

from src.api.newsapi_client import NewsAPIClient
from src.api.rss_client import RSSClient
from src.api.arxiv_client import ArXivClient
from src.api.exa_client import ExaClient
from src.api.brave_client import BraveSearchClient, brave
from src.storage.cache import ResearchCache
from src.models.market import Market
from src.models.whale_event import WhaleEvent
from src.models.research_result import ResearchResult, ResearchResults
from src.utils.config import Config
from src.utils.logger import logger


# Keywords para análise de direção
BULLISH_KEYWORDS = [
    "breakthrough", "success", "approved", "confirmed", "achieved",
    "launches", "releases", "partnership", "funding", "raised",
    "positive", "growth", "exceeds", "surpasses", "first"
]

BEARISH_KEYWORDS = [
    "fails", "delayed", "cancelled", "rejected", "denied",
    "lawsuit", "investigation", "concerns", "risks", "warns",
    "layoffs", "downsizing", "negative", "struggles", "behind"
]


class ResearchLoop:
    """
    Executa pesquisa híbrida para validar eventos.
    
    Nova ordem de prioridade:
    1. Brave Search (grátis, web + news)
    2. Google News RSS (grátis, breaking news)
    3. RSS Tech feeds (grátis, AI/Tech específico)
    4. ArXiv (grátis, papers acadêmicos)
    5. Exa (pago, backup quando resultados < threshold)
    """
    
    MIN_FREE_RESULTS = 5  # Mínimo de resultados antes de usar Exa
    EXA_THRESHOLD_USD = 50_000  # Usar Exa se evento >= $50k
    
    def __init__(
        self,
        newsapi: NewsAPIClient = None,
        rss: RSSClient = None,
        arxiv: ArXivClient = None,
        exa: ExaClient = None,
        brave_client: BraveSearchClient = None,
        cache: ResearchCache = None
    ):
        """Inicializa com clientes de API e cache."""
        self.newsapi = newsapi or NewsAPIClient()
        self.rss = rss or RSSClient()
        self.arxiv = arxiv or ArXivClient()
        self.exa = exa or ExaClient()
        self.brave = brave_client or brave  # Usa singleton por defeito
        self.cache = cache or ResearchCache()
    
    async def close(self):
        """Fecha todas as conexões."""
        await self.newsapi.close()
        await self.arxiv.close()
    
    async def execute(
        self,
        market: Market,
        whale_event: WhaleEvent
    ) -> ResearchResults:
        """Executa pesquisa completa para um evento whale."""
        start_time = datetime.now()
        
        # Construir queries
        queries = self._build_queries(market)
        
        # Executar pesquisas gratuitas em paralelo
        all_results: List[ResearchResult] = []
        source_breakdown = {}
        
        # NewsAPI
        news_results = await self._search_newsapi(queries)
        all_results.extend(news_results)
        source_breakdown["newsapi"] = len(news_results)
        
        # RSS
        rss_results = await self._search_rss(queries)
        all_results.extend(rss_results)
        source_breakdown["rss"] = len(rss_results)
        
        # ArXiv
        arxiv_results = await self._search_arxiv(queries)
        all_results.extend(arxiv_results)
        source_breakdown["arxiv"] = len(arxiv_results)
        
        logger.info(
            "free_research_complete",
            market_id=market.market_id,
            total=len(all_results)
        )
        
        # Decidir se usar Exa (fallback pago)
        should_use_exa = (
            len(all_results) < self.MIN_FREE_RESULTS
            or whale_event.size_usd >= self.EXA_THRESHOLD_USD
        )
        
        if should_use_exa and self.exa.enabled:
            exa_results = await self._search_exa(queries)
            all_results.extend(exa_results)
            source_breakdown["exa"] = len(exa_results)
            logger.info("exa_fallback_used", results=len(exa_results))
        
        # Calcular tempo de execução
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return ResearchResults(
            market_id=market.market_id,
            whale_event_id=f"{whale_event.wallet_address[:10]}_{whale_event.timestamp.isoformat()}",
            queries_executed=queries,
            results=all_results,
            execution_time_ms=int(execution_time),
            source_breakdown=source_breakdown
        )
    
    async def execute_for_news(
        self,
        market: Market,
        news: Dict,  # {title, source, publishedAt, url, description}
        use_exa: bool = False  # Default: don't use Exa (só backup)
    ) -> ResearchResults:
        """
        Executa pesquisa para validar/enriquecer uma notícia.
        
        NOVA ORDEM DE PRIORIDADE (tudo grátis):
        1. Brave Search (web + news) - NOVO
        2. Google News RSS - NOVO
        3. RSS Tech feeds
        4. ArXiv papers
        5. Exa (apenas backup se < 5 resultados)
        
        Args:
            market: Market objeto
            news: Dict com {title, source, publishedAt, url, description}
            use_exa: Se deve forçar uso de Exa
        
        Returns:
            ResearchResults com a notícia original + pesquisas de confirmação
        """
        start_time = datetime.now()
        
        # Construir queries baseadas no mercado + notícia
        queries = self._build_queries(market)
        news_title = news.get("title", "")
        if news_title:
            queries.insert(0, news_title)
        
        all_results: List[ResearchResult] = []
        source_breakdown = {}
        
        # 1. Adicionar notícia original como primeiro resultado
        original_news = ResearchResult(
            title=news.get("title", "Unknown"),
            url=news.get("url", ""),
            excerpt=news.get("description", "")[:300] if news.get("description") else "",
            author=news.get("author"),
            source="newsapi",
            source_type="news",
            direction=self._analyze_direction(
                news.get("title", "") + " " + (news.get("description") or "")
            ),
            published_date=self._parse_date(news.get("publishedAt")),
            relevance_score=1.0
        )
        all_results.append(original_news)
        source_breakdown["newsapi"] = 1
        
        # 2. Pesquisas PARALELAS - Brave + Google News RSS + ArXiv
        search_tasks = [
            self._search_brave(queries),  # NOVO: Brave first
            self._search_rss(queries),    # Agora inclui Google News RSS
            self._search_arxiv(queries),
        ]
        
        results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Process Brave results
        brave_results = results[0] if not isinstance(results[0], Exception) else []
        if isinstance(results[0], Exception):
            logger.warning("brave_search_failed", error=str(results[0]))
        all_results.extend(brave_results)
        source_breakdown["brave"] = len(brave_results)
        
        # Process RSS results (now includes Google News)
        rss_results = results[1] if not isinstance(results[1], Exception) else []
        if isinstance(results[1], Exception):
            logger.warning("rss_search_failed", error=str(results[1]))
        all_results.extend(rss_results)
        source_breakdown["rss"] = len(rss_results)
        
        # Process ArXiv results
        arxiv_results = results[2] if not isinstance(results[2], Exception) else []
        if isinstance(results[2], Exception):
            logger.warning("arxiv_search_failed", error=str(results[2]))
        all_results.extend(arxiv_results)
        source_breakdown["arxiv"] = len(arxiv_results)
        
        # 3. EXA BACKUP - Lógica inteligente
        total_free = len(brave_results) + len(rss_results) + len(arxiv_results)
        
        # Decidir se usa Exa baseado em múltiplos fatores
        exa_reasons = []
        
        # Condição 1: Poucos resultados grátis
        if total_free < self.MIN_FREE_RESULTS:
            exa_reasons.append(f"low_results:{total_free}")
        
        # Condição 2: Mercado de alto valor (odds extremas = mais incerto)
        # Odds 45-55% = muito incerto, vale gastar Exa
        # Odds < 10% ou > 90% = já decidido, não precisa
        market_odds = news.get("_market_odds", 50)  # Passado opcionalmente
        if 40 <= market_odds <= 60:
            exa_reasons.append(f"uncertain_market:{market_odds}%")
        
        # Condição 3: Query contém termos importantes
        important_terms = ["breaking", "urgent", "just announced", "confirmed"]
        news_lower = news_title.lower()
        if any(term in news_lower for term in important_terms):
            exa_reasons.append("important_news")
        
        # Condição 4: Forçado externamente
        if use_exa:
            exa_reasons.append("forced")
        
        # Usar Exa se qualquer razão existir
        should_use_exa = len(exa_reasons) > 0
        
        if should_use_exa and self.exa.enabled:
            exa_results = await self._search_exa(queries)
            all_results.extend(exa_results)
            source_breakdown["exa"] = len(exa_results)
            logger.info(
                "exa_backup_used",
                reasons=exa_reasons,
                results=len(exa_results),
                total_free=total_free
            )
        else:
            source_breakdown["exa"] = 0
            if exa_reasons:
                logger.debug("exa_would_be_used_but_disabled", reasons=exa_reasons)
        
        # Calcular tempo de execução
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        logger.info(
            "news_research_complete",
            market_id=market.market_id,
            news_title=news_title[:50],
            total_results=len(all_results),
            source_breakdown=source_breakdown,
            brave_count=len(brave_results),
            google_news_in_rss=True
        )
        
        return ResearchResults(
            market_id=market.market_id,
            whale_event_id=f"news_{hash(news_title) % 100000}",
            queries_executed=queries,
            results=all_results,
            execution_time_ms=int(execution_time),
            source_breakdown=source_breakdown
        )
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None
        try:
            # ISO format
            if "T" in date_str:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            # Other formats
            from dateutil.parser import parse
            return parse(date_str)
        except Exception:
            return None
    
    def _build_queries(self, market: Market) -> List[str]:
        """Constrói queries baseadas no mercado."""
        queries = []
        
        # Query principal do nome do mercado
        queries.append(market.market_name)
        
        # Queries baseadas em tags
        if market.tags:
            tag_query = " ".join(market.tags[:3])
            queries.append(tag_query)
        
        return queries
    
    async def _search_newsapi(self, queries: List[str], event_id: str = "") -> List[ResearchResult]:
        """Pesquisa via NewsAPI com guardrails."""
        results = []
        
        # Guardrail 1: Verificar quota
        can_use, reason = await self.cache.can_use_newsapi()
        if not can_use:
            logger.debug("newsapi_skipped_quota", reason=reason)
            return results
        
        # Guardrail 2: Verificar limite por evento (máx 3)
        if event_id and not await self.cache.can_request_for_event(event_id, "newsapi"):
            logger.debug("newsapi_skipped_event_limit", event_id=event_id)
            return results
        
        for query in queries[:1]:  # Limitar a 1 query
            # Guardrail 3: Verificar cache (24h)
            cached = await self.cache.get_cached(query, "newsapi")
            if cached:
                for article in cached:
                    results.append(ResearchResult(
                        title=article.get("title", ""),
                        url=article.get("url", ""),
                        excerpt=article.get("description", "")[:300],
                        author=article.get("author"),
                        source="newsapi",
                        direction=self._analyze_direction(
                            article.get("title", "") + " " + article.get("description", "")
                        )
                    ))
                continue
            
            # Fazer request real
            articles = await self.newsapi.search_articles(query, max_results=5)
            
            # Registar request
            await self.cache.record_newsapi_request()
            if event_id:
                await self.cache.record_event_request(event_id, "newsapi")
            
            # Guardar em cache
            await self.cache.set_cached(query, "newsapi", articles)
            
            for article in articles:
                results.append(ResearchResult(
                    title=article.get("title", ""),
                    url=article.get("url", ""),
                    excerpt=article.get("description", "")[:300],
                    author=article.get("author"),
                    source="newsapi",
                    direction=self._analyze_direction(
                        article.get("title", "") + " " + article.get("description", "")
                    )
                ))
        
        return results
    
    async def _search_brave(self, queries: List[str]) -> List[ResearchResult]:
        """
        Pesquisa via Brave Search API (GRÁTIS - 2000/mês).
        
        Usa apenas Web Search (mais estável) com 10 resultados.
        News endpoint tem rate limit mais agressivo no free tier.
        """
        if not self.brave.enabled:
            logger.debug("brave_search_disabled", reason="No API key")
            return []
        
        results = []
        
        # Usar apenas WEB search (1 request, mais estável)
        # News endpoint tem rate limit mais agressivo
        for query in queries[:1]:
            web_results = await self.brave.search_web(query, count=10)
            for item in web_results:
                results.append(ResearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    excerpt=item.get("description", "")[:300],
                    source="brave",
                    source_type="web",
                    direction=self._analyze_direction(
                        item.get("title", "") + " " + item.get("description", "")
                    )
                ))
        
        logger.info("brave_search_complete", results=len(results))
        return results
    
    async def _search_rss(self, queries: List[str]) -> List[ResearchResult]:
        """Pesquisa via RSS Feeds."""
        keywords = []
        for q in queries:
            keywords.extend(q.split()[:5])
        
        articles = await self.rss.search_feeds(keywords, max_results=10)
        results = []
        for article in articles:
            results.append(ResearchResult(
                title=article.get("title", ""),
                url=article.get("url", ""),
                excerpt=article.get("excerpt", "")[:300],
                source="rss",
                direction=self._analyze_direction(article.get("title", "") + " " + article.get("excerpt", ""))
            ))
        return results
    
    async def _search_arxiv(self, queries: List[str]) -> List[ResearchResult]:
        """Pesquisa via ArXiv."""
        results = []
        for query in queries[:1]:  # Limitar a 1 query
            papers = await self.arxiv.search_papers(query, max_results=5)
            for paper in papers:
                results.append(ResearchResult(
                    title=paper.get("title", ""),
                    url=paper.get("url", ""),
                    excerpt=paper.get("excerpt", "")[:300],
                    author=", ".join(paper.get("authors", [])[:2]),
                    source_type="researcher",
                    source="arxiv",
                    direction=self._analyze_direction(paper.get("title", "") + " " + paper.get("excerpt", ""))
                ))
        return results
    
    async def _search_exa(self, queries: List[str]) -> List[ResearchResult]:
        """Pesquisa via Exa API (fallback pago)."""
        results = []
        for query in queries[:1]:  # Limitar para economizar
            exa_results = await self.exa.search(query, max_results=5)
            for r in exa_results:
                results.append(ResearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    excerpt=r.get("excerpt", "")[:300],
                    source="exa",
                    relevance_score=r.get("score", 0.0),
                    direction=self._analyze_direction(r.get("title", "") + " " + r.get("excerpt", ""))
                ))
        return results
    
    def _analyze_direction(self, text: str) -> str:
        """Analisa direção (YES/NO/NEUTRAL) baseado em keywords."""
        text_lower = text.lower()
        
        bullish_count = sum(1 for kw in BULLISH_KEYWORDS if kw in text_lower)
        bearish_count = sum(1 for kw in BEARISH_KEYWORDS if kw in text_lower)
        
        if bullish_count > bearish_count and bullish_count >= 2:
            return "YES"
        elif bearish_count > bullish_count and bearish_count >= 2:
            return "NO"
        return "NEUTRAL"
