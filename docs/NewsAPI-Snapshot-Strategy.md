# Estratégia de Uso da News API — 2 Requests por Dia

Este documento define a **forma correta de usar a News API (free tier)** no ExaSignal.

---

## 1. Decisão

Usar a **News API apenas 2 vezes por dia**, em horas diferentes.

Isto é uma **escolha de design**, não uma limitação técnica.

> News API = fotografia do dia  
> Não é feed, não é trigger, não é tempo real

---

## 2. Objetivo da News API no ExaSignal

A News API serve apenas para:
- Captar **narrativa dominante**
- Medir **consenso direcional**
- Fornecer **contexto adicional** (nunca primário)

---

## 3. Horários Recomendados

| Snapshot | Hora (UTC) | Razão |
|----------|------------|-------|
| Manhã | 08:00 | Captar notícias overnight |
| Tarde | 16:00 | Captar desenvolvimentos do dia |

---

## 4. O que cada snapshot faz

1. Busca notícias para **todos os mercados** (12-15)
2. Guarda em **cache de 24h**
3. Quando há whale event, usa **cache** (não faz request)

---

## 5. Implementação

```python
# Não fazer request por evento
# Fazer 2 scans gerais por dia

async def daily_news_snapshot():
    for market in markets:
        articles = await newsapi.search(market.name)
        await cache.set(market.name, articles, ttl=24h)
```

---

## 6. Quota Usage

- 2 scans × 15 mercados = **30 requests/dia**
- Limite free tier = 100/dia
- **Margem de segurança: 70%**

---

## 7. Regra Final

> Se precisares de chamar a News API muitas vezes,
> o problema não é a quota — é o design do produto.

---

## 8. Hierarquia de Fontes (Para Scoring)

1. **ArXiv** - Papers acadêmicos (alta credibilidade)
2. **Exa** - Pesquisa semântica (alta qualidade)
3. **RSS Feeds** - Blogs de labs, tech news
4. **News API** - Contexto adicional apenas

A News API **nunca decide sozinha**. Apenas reforça ou enfraquece.
