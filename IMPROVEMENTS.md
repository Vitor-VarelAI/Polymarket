# ExaSignal — Melhorias Recomendadas

Este documento descreve melhorias sugeridas que não são essenciais para o MVP, mas são úteis para produção e melhor experiência do usuário.

---

## 📋 Índice

1. [Persistência SQLite](#1-persistência-sqlite)
2. [Cache de Pesquisas Exa](#2-cache-de-pesquisas-exa)
3. [Health Checks e Monitoring](#3-health-checks-e-monitoring)
4. [Testes](#4-testes)
5. [Implementação Incremental](#5-implementação-incremental)

---

## 1. Persistência SQLite

### Por que é útil

- **Evita perda de estado em restarts:** Rate limits, cooldowns e settings de usuário são mantidos
- **Leve e simples:** SQLite não requer servidor separado
- **Async-friendly:** `aiosqlite` permite operações assíncronas

### O que persistir

1. **Rate Limits**
   - Timestamp de alertas enviados
   - Contagem de alertas por dia
   - Limpeza automática de dados antigos (>7 dias)

2. **Cooldowns por Mercado**
   - Último alerta por `market_id`
   - Timestamp para cálculo de cooldown de 24h

3. **Settings por Usuário**
   - Threshold personalizado por usuário
   - Outras preferências futuras

### Estrutura do Banco

```sql
-- Alertas enviados
CREATE TABLE alerts_sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    user_id INTEGER
);

-- Settings de usuário
CREATE TABLE user_settings (
    user_id INTEGER PRIMARY KEY,
    threshold REAL DEFAULT 70.0,
    updated_at DATETIME NOT NULL
);

-- Índices para performance
CREATE INDEX idx_market_timestamp ON alerts_sent(market_id, timestamp);
CREATE INDEX idx_timestamp ON alerts_sent(timestamp);
```

### Implementação

Ver exemplos em:
- `SETUP_GUIDE.md` - Seção 8.1
- `PRD-05-Alert-Generation.md` - Sistema de Rate Limiting com SQLite

### Dependência

```txt
aiosqlite==0.19.0
```

---

## 2. Cache de Pesquisas Exa

### Por que é útil

- **Economiza API calls:** Reduz custos da Exa API
- **Melhora velocidade:** Evita pesquisas duplicadas (<20s decisão)
- **Consistência:** Eventos similares em mercados relacionados retornam resultados consistentes

### Como funciona

- Cache por **1-2 horas** (TTL configurável)
- Chave de cache baseada em: `market_id`, `direction`, `query_templates`
- Para eventos similares em mercados relacionados, retorna do cache
- Invalidar automaticamente após TTL expirar

### Implementação

Ver exemplos em:
- `SETUP_GUIDE.md` - Seção 8.2
- `PRD-03-Research-Loop.md` - Sistema de Cache

### Exemplo de Uso

```python
# Verificar cache antes de pesquisar
cached = research_cache.get(market_id, direction, queries)
if cached:
    return cached

# Se não em cache, pesquisar
results = await execute_research(...)

# Armazenar no cache
research_cache.set(market_id, direction, queries, results)
```

---

## 3. Health Checks e Monitoring

### Health Check Endpoint

Adicionar comando `/health` no bot para verificar status de componentes:

- ✅ Telegram API
- ✅ Exa API
- ✅ Polymarket APIs (Gamma, CLOB)
- ✅ Database (SQLite)

### Logging Estruturado

Usar `structlog` para logging estruturado:

**Benefícios:**
- Logs em formato JSON (fácil parsing)
- Contexto rico (user_id, market_id, etc.)
- Melhor debugging

**Exemplo:**
```python
logger.info(
    "whale_event_detected",
    market_id=market_id,
    size_usd=size_usd,
    direction=direction
)
```

### Error Tracking (Sentry)

Capturar erros de APIs externas com Sentry:

**Benefícios:**
- Alertas automáticos de erros
- Stack traces completos
- Contexto adicional

**Exemplo:**
```python
try:
    results = await exa_api.search(...)
except Exception as e:
    sentry_sdk.capture_exception(e)
    logger.error("exa_api_error", error=str(e))
```

### Implementação

Ver exemplos em:
- `SETUP_GUIDE.md` - Seção 8.3
- `PRD-06-Telegram-Bot.md` - Health Checks e Monitoring

### Dependências

```txt
structlog==23.2.0
sentry-sdk==1.38.0  # Opcional
```

---

## 4. Testes

### Testes Unitários

**Framework:** `pytest`

**Foco:**
- **Alignment Scorer (determinístico):** Mesmo input sempre produz mesmo score
- **Cálculo de componentes:** Validar cada componente (A-E) individualmente
- **Formatação de alertas:** Validar schema exato

### Mocks para APIs Externas

Criar mocks para:
- Exa API
- Polymarket APIs (Gamma, CLOB)
- Telegram Bot API

**Benefícios:**
- Testes rápidos (sem chamadas reais)
- Testes determinísticos
- Não consome créditos de API

### Exemplo de Teste

```python
# tests/test_alignment_scorer.py
def test_score_calculation_deterministic():
    """Testa que mesmo input sempre produz mesmo score."""
    scorer = AlignmentScorer()
    whale_event = create_test_whale_event()
    research_results = create_test_research_results()
    
    score1 = scorer.calculate_score(whale_event, research_results)
    score2 = scorer.calculate_score(whale_event, research_results)
    
    assert score1.score == score2.score
    assert score1.components == score2.components
```

### Implementação

Ver exemplos em:
- `SETUP_GUIDE.md` - Seção 9.1
- Criar arquivos em `tests/` seguindo estrutura sugerida

### Dependências

```txt
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-mock==3.12.0
```

---

## 5. Implementação Incremental

### Ordem Recomendada

1. **MVP Básico** (Essencial)
   - Funcionalidade core sem melhorias
   - Rate limiting em memória
   - Sem cache
   - Logging básico

2. **Persistência SQLite** (Primeira melhoria)
   - Implementar após MVP básico funcionando
   - Adicionar `aiosqlite`
   - Migrar rate limiting para SQLite
   - Adicionar settings de usuário

3. **Cache Exa** (Segunda melhoria)
   - Implementar após persistência
   - Adicionar cache de pesquisas
   - Ajustar TTL conforme necessário

4. **Health Checks** (Terceira melhoria)
   - Adicionar comando `/health`
   - Implementar checks básicos
   - Expandir conforme necessário

5. **Logging e Monitoring** (Quarta melhoria)
   - Migrar para `structlog`
   - Adicionar Sentry (opcional)
   - Melhorar contexto dos logs

6. **Testes** (Contínuo)
   - Adicionar testes incrementais
   - Começar com scorer (determinístico)
   - Expandir para outros componentes

### Priorização

**Alta Prioridade:**
- ✅ Persistência SQLite (evita perda de estado)
- ✅ Cache Exa (economiza custos)

**Média Prioridade:**
- ⚠️ Health Checks (útil para debugging)
- ⚠️ Logging estruturado (melhora debugging)

**Baixa Prioridade:**
- 📝 Testes extensivos (pode vir depois do MVP)
- 📝 Sentry (opcional, depende de necessidade)

---

## 📝 Notas Finais

- **Comece simples:** Implemente MVP básico primeiro
- **Itere incrementalmente:** Adicione melhorias uma de cada vez
- **Valide cada melhoria:** Teste antes de adicionar próxima
- **Documente decisões:** Anote por que cada melhoria foi adicionada

**Lembre-se:** MVP deve ser funcional, não perfeito. Melhorias podem vir depois! 🚀

---

## 🔗 Referências

- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Guia completo com exemplos de implementação
- [PRDs](docs/prds/) - Documentação detalhada de cada componente
- [README.md](README.md) - Visão geral do projeto

