# ExaSignal — Estratégia de Otimização de Custos

Este documento descreve estratégias para minimizar custos de APIs, especialmente da Exa API, usando uma abordagem híbrida com APIs gratuitas/baratas.

---

## 📊 Análise de Custos

### Custo Estimado da Exa API

- **Por pesquisa:** $0.01-0.05
- **Por evento de whale:** 3 queries × $0.01-0.05 = **$0.03-0.15**
- **Cenário conservador (1-2 eventos/dia):**
  - 1 evento/dia × $0.10 = **$3/mês**
  - 2 eventos/dia × $0.10 = **$6/mês**
- **Cenário realista (3-5 eventos/dia):**
  - 3 eventos/dia × $0.10 = **$9/mês**
  - 5 eventos/dia × $0.10 = **$15/mês**

**⚠️ Com cache (50% hit rate):** Reduz para **$4.50-7.50/mês**

---

## 🎯 Estratégia Híbrida: Pesquisa em Camadas

### Abordagem: Free First, Paid When Needed

**Fase 1: APIs Gratuitas** (sempre tentar primeiro)
- NewsAPI (tier gratuito)
- RSS feeds diretos (15-20 feeds de qualidade)
- Reddit API (gratuito) - **REMOVIDO por complexidade**
- ArXiv API (gratuito)
- **CNN usa estes dados como entrada** - análise visual dos resultados

**Fase 2: Exa API** (apenas se necessário)
- Usar apenas se APIs gratuitas não retornarem resultados suficientes
- Ou para eventos muito importantes (>$50k)
- CNN pode validar quando Exa é realmente necessário

**🆕 CNN Integration:**
- **Não adiciona custos**: usa dados das APIs gratuitas existentes
- **Melhora qualidade**: detecta padrões que APIs textuais perdem
- **Reduz chamadas Exa**: identifica quando pesquisa adicional é valiosa

**🆕 Fontes de Dados Avançadas (Próximas Fases):**
- **Sentiment (Stocktwits/X)**: APIs gratuitas disponíveis
- **On-Chain (Etherscan/Whale Alert)**: Dados gratuitos via APIs públicas
- **Oracles (UMA/Chainlink)**: On-chain data gratuito
- **News Terminals**: APIs pagas, usar apenas para eventos >$100k
- **Estratégia**: Começar com gratuitas, adicionar pagas apenas se provar valor
- **Mantém estratégia free-first**: CNN analisa dados gratuitos primeiro

---

## 📰 APIs Gratuitas/Baratas Disponíveis

### 1. NewsAPI (Recomendado - Primeira Escolha)

**URL:** https://newsapi.org/

**Tier Gratuito:**
- 100 requests/dia
- Headlines e artigos recentes
- Filtros por categoria, país, idioma
- **Custo: GRÁTIS** (até 100 req/dia)

**Como usar:**
```python
import httpx

class NewsAPIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2"
    
    async def search_articles(
        self,
        query: str,
        max_results: int = 10,
        days_back: int = 7
    ):
        """Busca artigos recentes."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/everything",
                params={
                    "q": query,
                    "apiKey": self.api_key,
                    "language": "en",
                    "sortBy": "relevancy",
                    "pageSize": max_results,
                    "from": (datetime.now() - timedelta(days=days_back)).isoformat()
                }
            )
            return response.json()
```

**Limitações:**
- Apenas 100 requests/dia (suficiente para MVP)
- Não filtra por autoridade automaticamente
- Requer análise manual de fonte

**Quando usar:**
- Primeira tentativa para todas as pesquisas
- Perfeito para notícias recentes e artigos

---

### 2. RSS Feeds Expandidos (Gratuito - 15-20 Feeds de Qualidade)

**Lista Completa Recomendada:**

#### Tech & AI News
- TechCrunch: `https://techcrunch.com/feed/`
- The Verge: `https://www.theverge.com/rss/index.xml`
- Wired: `https://www.wired.com/feed/rss`
- MIT Technology Review: `https://www.technologyreview.com/feed/`
- IEEE Spectrum: `https://spectrum.ieee.org/rss`

#### AI Research & Labs
- OpenAI Blog: `https://openai.com/blog/rss.xml`
- DeepMind Blog: `https://deepmind.com/blog/feed/basic/`
- Anthropic Blog: `https://www.anthropic.com/index.xml`
- Google AI Blog: `https://ai.googleblog.com/feeds/posts/default`
- Meta AI Research: `https://ai.meta.com/blog/feed/`

#### Academic & Research
- ArXiv AI: `http://arxiv.org/rss/cs.AI`
- ArXiv Machine Learning: `http://arxiv.org/rss/cs.LG`
- Hacker News AI: `https://hnrss.org/newest?q=AI`
- LessWrong: `https://www.lesswrong.com/feed.xml` (AGI discussions)

#### Industry Analysis
- VentureBeat AI: `https://venturebeat.com/ai/feed/`
- AI News: `https://www.artificialintelligence-news.com/feed/`
- The Information: `https://www.theinformation.com/feed` (se tiver acesso)

**Total: 15-20 feeds de qualidade**

**Como usar:**
```python
class RSSClient:
    def __init__(self):
        self.feeds = [
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
```

**Como usar:**
```python
import feedparser
from datetime import datetime, timedelta

class RSSClient:
    def __init__(self):
        self.feeds = [
            "https://techcrunch.com/feed/",
            "http://arxiv.org/rss/cs.AI",
            # Adicionar mais feeds relevantes
        ]
    
    async def search_feeds(
        self,
        keywords: list,
        max_results: int = 10,
        days_back: int = 7
    ):
        """Busca em múltiplos RSS feeds."""
        results = []
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        for feed_url in self.feeds:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                # Verificar se contém keywords
                text = f"{entry.title} {entry.get('summary', '')}".lower()
                if any(kw.lower() in text for kw in keywords):
                    # Verificar data
                    pub_date = datetime(*entry.published_parsed[:6])
                    if pub_date >= cutoff_date:
                        results.append({
                            "title": entry.title,
                            "url": entry.link,
                            "excerpt": entry.get("summary", ""),
                            "published_date": pub_date,
                            "source": feed_url
                        })
        
        return results[:max_results]
```

**Vantagens:**
- **100% gratuito**
- Sem rate limits
- Fontes conhecidas e confiáveis

**Desvantagens:**
- Requer parsing manual
- Não há busca semântica
- Limitado a feeds específicos

---

### 3. Reddit API (Gratuito - Com User-Agent + Delays)

**URL:** https://www.reddit.com/dev/api/

**Tier Gratuito:**
- 60 requests/minuto
- Acesso a subreddits específicos
- **Custo: GRÁTIS**

**⚠️ IMPORTANTE:** Sempre usar User-Agent apropriado e delays entre requests para respeitar rate limits.

**Como usar:**
```python
import httpx
import asyncio

class RedditClient:
    def __init__(self):
        self.base_url = "https://www.reddit.com/r"
        self.headers = {
            "User-Agent": "ExaSignal/1.0 (Research Bot; contact: your-email@example.com)"
        }
        self.delay_seconds = 1  # Delay entre requests para respeitar rate limits
    
    async def search_subreddit(
        self,
        subreddit: str,
        query: str,
        limit: int = 10
    ):
        """Busca em subreddit específico."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/{subreddit}/search.json",
                params={"q": query, "limit": limit, "sort": "relevance"},
                headers=self.headers
            )
            # Delay para respeitar rate limits
            await asyncio.sleep(self.delay_seconds)
            return response.json()
    
    async def search_ai_communities(self, query: str):
        """Busca em múltiplos subreddits de AI."""
        subreddits = ["MachineLearning", "artificial", "singularity", "agi"]
        results = []
        
        for subreddit in subreddits:
            data = await self.search_subreddit(subreddit, query)
            results.extend(data.get("data", {}).get("children", []))
            # Delay adicional entre subreddits
            await asyncio.sleep(self.delay_seconds)
        
        return results
```

**Quando usar:**
- Insights de comunidades técnicas
- Discussões sobre papers/tecnologia
- Opiniões de pesquisadores ativos

---

### 4. ArXiv API (Gratuito - Para Papers)

**URL:** http://arxiv.org/help/api

**Tier Gratuito:**
- Sem limites conhecidos
- Acesso a papers acadêmicos
- **Custo: GRÁTIS**

**Como usar:**
```python
import httpx
import xml.etree.ElementTree as ET

class ArXivClient:
    def __init__(self):
        self.base_url = "http://export.arxiv.org/api/query"
    
    async def search_papers(
        self,
        query: str,
        max_results: int = 10
    ):
        """Busca papers no ArXiv."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.base_url,
                params={
                    "search_query": f"all:{query}",
                    "start": 0,
                    "max_results": max_results,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending"
                }
            )
            # Parse XML response
            root = ET.fromstring(response.text)
            papers = []
            
            for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
                papers.append({
                    "title": entry.find("{http://www.w3.org/2005/Atom}title").text,
                    "url": entry.find("{http://www.w3.org/2005/Atom}id").text,
                    "authors": [a.text for a in entry.findall("{http://www.w3.org/2005/Atom}author/{http://www.w3.org/2005/Atom}name")],
                    "published_date": entry.find("{http://www.w3.org/2005/Atom}published").text,
                    "summary": entry.find("{http://www.w3.org/2005/Atom}summary").text
                })
            
            return papers
```

**Quando usar:**
- Pesquisas acadêmicas recentes
- Papers de pesquisadores conhecidos
- Validação técnica profunda

---

### 5. Hacker News API (Gratuito)

**URL:** https://github.com/HackerNews/API

**Tier Gratuito:**
- Sem limites conhecidos
- Acesso a stories e comments
- **Custo: GRÁTIS**

**Como usar:**
```python
class HackerNewsClient:
    def __init__(self):
        self.base_url = "https://hacker-news.firebaseio.com/v0"
    
    async def search_stories(self, keywords: list, limit: int = 10):
        """Busca stories no Hacker News."""
        # Obter top stories
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/topstories.json")
            story_ids = response.json()[:100]  # Top 100
            
            results = []
            for story_id in story_ids[:limit]:
                story = await client.get(f"{self.base_url}/item/{story_id}.json")
                story_data = story.json()
                
                if story_data and story_data.get("title"):
                    text = story_data["title"].lower()
                    if any(kw.lower() in text for kw in keywords):
                        results.append(story_data)
            
            return results
```

---

## 🏗️ Arquitetura Híbrida Recomendada

### Estratégia de Pesquisa em Camadas

```python
class HybridResearchLoop:
    def __init__(
        self,
        newsapi_key: str,
        exa_api_key: str = None,  # Opcional
        use_exa_fallback: bool = False,  # Começar com False (Fase 1)
        min_free_results: int = 5,
        important_event_threshold: float = 50000  # $50k
    ):
        self.newsapi = NewsAPIClient(newsapi_key)
        self.rss = RSSClient()  # 15-20 feeds (ver RSS_FEEDS.md)
        self.reddit = RedditClient()  # Com User-Agent + delays
        self.arxiv = ArXivClient()
        self.exa = ExaAPIClient(exa_api_key) if exa_api_key else None
        self.use_exa_fallback = use_exa_fallback
        self.min_free_results = min_free_results
        self.important_event_threshold = important_event_threshold
        
        # Métricas para Fase 3 (análise)
        self.exa_usage_count = 0
        self.total_researches = 0
    
    async def execute_research(
        self,
        whale_event: WhaleEvent,
        min_results: int = 5
    ) -> ResearchResults:
        """Executa pesquisa híbrida seguindo estratégia exata."""
        self.total_researches += 1
        queries = self._build_queries(whale_event)
        all_results = []
        
        # Fase 1: APIs Gratuitas (sempre primeiro)
        logger.info("Starting research with free APIs", event_id=whale_event.id)
        
        for query in queries:
            # NewsAPI
            news_results = await self.newsapi.search_articles(query)
            all_results.extend(self._format_newsapi_results(news_results))
            
            # RSS Feeds
            rss_results = await self.rss.search_feeds(
                self._extract_keywords(query)
            )
            all_results.extend(self._format_rss_results(rss_results))
            
            # Reddit (para insights de comunidade)
            reddit_results = await self.reddit.search_ai_communities(query)
            all_results.extend(self._format_reddit_results(reddit_results))
            
            # ArXiv (para papers acadêmicos)
            arxiv_results = await self.arxiv.search_papers(query)
            all_results.extend(self._format_arxiv_results(arxiv_results))
        
        # Remover duplicatas
        all_results = self._deduplicate_results(all_results)
        
        # Verificar se temos resultados suficientes
        if len(all_results) >= min_results:
            logger.info(
                "Sufficient free results",
                event_id=whale_event.id,
                free_results=len(all_results)
            )
            return ResearchResults(
                results=all_results[:10],
                source="hybrid_free"
            )
        
        # Fase 2: Exa API (apenas se necessário)
        # Regra: usar se <5 resultados OU evento muito grande/importante (>$50k)
        should_use_exa = (
            self.use_exa_fallback and 
            self.exa and 
            (
                len(all_results) < self.min_free_results or 
                self._is_important_event(whale_event)
            )
        )
        
        if should_use_exa:
            self.exa_usage_count += 1
            reason = "insufficient_results" if len(all_results) < self.min_free_results else "important_event"
            
            logger.info(
                "Using Exa API fallback",
                event_id=whale_event.id,
                reason=reason,
                free_results=len(all_results),
                event_size_usd=whale_event.size_usd,
                exa_usage_rate=f"{self.get_exa_usage_rate():.1f}%"
            )
            
            exa_results = await self.exa.search(query)
            all_results.extend(self._format_exa_results(exa_results))
        
        return ResearchResults(
            results=all_results[:10],
            source="hybrid_with_exa" if should_use_exa else "hybrid_free"
        )
    
    def _is_important_event(self, whale_event: WhaleEvent) -> bool:
        """Determina se evento é importante o suficiente para usar Exa."""
        # Evento muito grande: >$50k OU múltiplos whales no mesmo mercado
        return whale_event.size_usd > self.important_event_threshold
    
    def get_exa_usage_rate(self) -> float:
        """Retorna % de pesquisas que usaram Exa (para Fase 3 - análise)."""
        if self.total_researches == 0:
            return 0.0
        return (self.exa_usage_count / self.total_researches) * 100
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Retorna resumo de métricas para análise Fase 3."""
        return {
            "total_researches": self.total_researches,
            "exa_usage_count": self.exa_usage_count,
            "exa_usage_rate": self.get_exa_usage_rate(),
            "recommendation": (
                "Remove Exa - usage <20%" if self.get_exa_usage_rate() < 20 
                else "Keep Exa as fallback"
            )
        }
        
        return ResearchResults(
            results=all_results[:10],
            source="hybrid_with_exa" if self.exa else "hybrid_free"
        )
```

---

## 💰 Comparação de Custos

### Cenário 1: Apenas Exa API
- **Custo/mês:** $9-15 (3-5 eventos/dia)
- **Qualidade:** Alta (busca semântica)
- **Limitação:** Custo cresce com uso

### Cenário 2: Híbrido (Free First)
- **Custo/mês:** $0-3 (Exa apenas quando necessário)
- **Qualidade:** Boa (combinação de fontes)
- **Vantagem:** 70-80% de redução de custos

### Cenário 3: Apenas APIs Gratuitas
- **Custo/mês:** $0
- **Qualidade:** Média-Alta (depende de fontes)
- **Limitação:** Requer mais processamento

---

## 📋 Recomendação Final de Implementação

### Fase 1: MVP com APIs Gratuitas (Custo $0)

**Prioridades:**
1. **NewsAPI** - Fonte principal
2. **RSS Expandido** - 15-20 feeds de qualidade (ver lista abaixo)
3. **ArXiv** - Papers acadêmicos
4. **Reddit** - Insights de comunidade (com User-Agent + delays para respeitar rate limits)

**Implementação:**
- Começar SEM Exa API
- Focar em qualidade das fontes gratuitas
- Validar se resultados são suficientes

**Custo:** $0/mês

---

### Fase 2: Adicionar Exa como Fallback Opcional (Após Validar Qualidade)

**Regras de Uso:**
- Usar Exa **apenas se:**
  - APIs gratuitas retornarem **<5 resultados** OU
  - Evento for **muito grande/importante** (ex: size >$50k, múltiplos whales)
- Ativado via config: `USE_EXA_FALLBACK=true`
- Monitorar quando Exa é usado (logging)

**Custo estimado:** $1-3/mês (dependendo de frequência)

---

### Fase 3: Análise e Otimização

**Métricas a Acompanhar:**
- % de casos que precisaram da Exa
- Qualidade dos resultados free vs Exa
- Custo mensal real

**Decisão:**
- Se **<20% dos casos** precisaram da Exa:
  - Considerar remover Exa completamente
  - Ficar 100% free
  - Silêncio ainda mais valioso (menos dependências)

**Objetivo:** Sistema sustentável e confiável sem dependência de APIs pagas

---

## 🔧 Configuração Recomendada

### Variáveis de Ambiente

```bash
# APIs Gratuitas (obrigatórias)
NEWSAPI_KEY=your_newsapi_key  # Grátis até 100 req/dia

# Exa API (opcional - fallback)
EXA_API_KEY=your_exa_key  # Opcional

# Configuração
USE_EXA_FALLBACK=true  # Usar Exa apenas se necessário
MIN_FREE_RESULTS=5     # Mínimo de resultados antes de usar Exa
```

### Estratégia de Cache

- Cache resultados de APIs gratuitas também
- TTL: 2-4 horas (mais longo que Exa)
- Reduz ainda mais chamadas de API

---

## 📊 Monitoramento de Custos e Decisões

### Métricas Críticas a Acompanhar

1. **Taxa de uso de Exa:**
   - % de pesquisas que usam Exa
   - **Meta: <20% das pesquisas**
   - Se <20%: considerar remover Exa completamente

2. **Custo mensal:**
   - Tracking de custos por fonte
   - Alertas se exceder threshold
   - **Objetivo: $0/mês (100% free)**

3. **Qualidade de resultados:**
   - Comparar qualidade free vs Exa
   - Score médio de alertas gerados
   - Taxa de falsos positivos

4. **Logging Detalhado:**
   ```python
   # Registrar sempre que Exa é usado
   logger.info(
       "exa_api_used",
       event_id=whale_event.id,
       free_results_count=len(free_results),
       reason="insufficient_results" | "important_event",
       event_size_usd=whale_event.size_usd
   )
   ```

### Decisão Fase 3

**Se <20% dos casos precisaram da Exa:**
- ✅ Remover Exa completamente
- ✅ Ficar 100% free
- ✅ Silêncio ainda mais valioso (menos dependências)
- ✅ Sistema mais robusto e sustentável

**Se >20% dos casos precisaram da Exa:**
- Manter Exa como fallback
- Analisar quais casos precisam
- Otimizar queries gratuitas para cobrir mais casos

---

## 🎯 Conclusão e Estratégia Final

**Implementação Recomendada (Exata):**

### Fase 1 (Agora - Custo $0):
1. ✅ **NewsAPI** - Principal fonte
2. ✅ **RSS Expandido** - 15-20 feeds de qualidade (ver `RSS_FEEDS.md`)
3. ✅ **ArXiv** - Papers acadêmicos
4. ✅ **Reddit** - Comunidades técnicas (com User-Agent + delays)

**Começar SEM Exa API**

### Fase 2 (Depois de Validar Qualidade):
- ✅ Adicionar Exa como fallback opcional (ativado via config)
- ✅ **Regra:** Só usa se <5 resultados OU evento muito grande/importante (>$50k)
- ✅ Logging detalhado de quando e por quê Exa foi usado

### Fase 3 (Análise):
- ✅ Analisar logs: qual % de casos precisou da Exa?
- ✅ **Se <20%:** Considerar remover Exa completamente
- ✅ Ficar 100% free (silêncio ainda mais valioso)
- ✅ Sistema mais robusto e sustentável

**Redução de custos esperada:** 70-90% comparado a usar apenas Exa, potencialmente 100% se <20% precisar de Exa

**Benefícios:**
- ✅ Menos dependência de APIs pagas
- ✅ Sistema mais robusto
- ✅ Custos mínimos ou zero
- ✅ Silêncio ainda mais valioso (menos dependências)

**Próximos passos:**
- ✅ Ver `RSS_FEEDS.md` para lista completa de feeds
- ✅ Implementar camada de abstração para múltiplas fontes
- ✅ Adicionar métricas de custo e qualidade
- ✅ Logging detalhado para análise Fase 3

