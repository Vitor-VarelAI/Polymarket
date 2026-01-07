# ExaSignal — Guia Completo de Setup e Implementação

Este documento contém **tudo que você precisa** para implementar o projeto ExaSignal do zero, incluindo APIs, configurações, dependências e passos detalhados.

---

## 📋 Índice

1. [APIs Necessárias](#1-apis-necessárias)
2. [Criar Bot Telegram](#2-criar-bot-telegram)
3. [Dependências e Bibliotecas](#3-dependências-e-bibliotecas)
4. [Estrutura do Projeto](#4-estrutura-do-projeto)
5. [Configuração Inicial](#5-configuração-inicial)
6. [Variáveis de Ambiente](#6-variáveis-de-ambiente)
7. [Passos para Começar](#7-passos-para-começar)
8. [Testes e Validação](#8-testes-e-validação)
9. [Deploy](#9-deploy)

---

## 1. APIs Necessárias

### 1.1 APIs de Pesquisa (Estratégia Híbrida para Minimizar Custos)

**⚠️ IMPORTANTE:** Para minimizar custos, usar APIs gratuitas primeiro, Exa apenas como fallback.

#### 1.1.1 NewsAPI (Obrigatória - Primeira Escolha)

**O que é:** API de notícias com tier gratuito generoso.

**Como obter:**
1. Acesse: https://newsapi.org/
2. Crie uma conta gratuita
3. Obtenha API key no dashboard
4. **Guarde a chave** - você precisará dela como `NEWSAPI_KEY`

**Documentação:** https://newsapi.org/docs

**Tier Gratuito:**
- 100 requests/dia
- Headlines e artigos recentes
- Filtros por categoria, país, idioma
- **Custo: GRÁTIS** (suficiente para MVP)

**Biblioteca Python:** `httpx` (REST simples)

---

#### 1.1.2 RSS Feeds Expandidos (Gratuito - 15-20 Feeds de Qualidade)

**O que é:** RSS feeds diretos de fontes confiáveis de AI/frontier tech.

**Lista Completa:** Ver `RSS_FEEDS.md` para lista completa de 15-20 feeds recomendados.

**Categorias:**
- Tech & AI News (TechCrunch, The Verge, Wired, MIT Tech Review, IEEE Spectrum)
- AI Research & Labs (OpenAI, DeepMind, Anthropic, Google AI, Meta AI)
- Academic & Research (ArXiv AI, ArXiv ML, Hacker News AI, LessWrong)
- Industry Analysis (VentureBeat AI, AI News)

**Custo:** 100% GRÁTIS

**Biblioteca Python:** `feedparser`

**⚠️ IMPORTANTE:** Usar 15-20 feeds de qualidade para máxima cobertura sem custos.

---

#### 1.1.3 Reddit API (Gratuito - Insights de Comunidade)

**O que é:** API oficial do Reddit para acessar subreddits.

**Como usar:**
- Sem autenticação necessária para leitura pública
- 60 requests/minuto
- **Custo: GRÁTIS**
- **⚠️ IMPORTANTE:** Sempre usar User-Agent apropriado + delays entre requests

**Subreddits Úteis:**
- `/r/MachineLearning`
- `/r/artificial`
- `/r/singularity`
- `/r/agi`

**Exemplo de User-Agent:**
```python
headers = {
    "User-Agent": "ExaSignal/1.0 (Research Bot; contact: your-email@example.com)"
}
```

**Delays Recomendados:**
- 1 segundo entre requests
- 1 segundo adicional entre subreddits diferentes

**Documentação:** https://www.reddit.com/dev/api/

---

#### 1.1.4 ArXiv API (Gratuito - Papers Acadêmicos)

**O que é:** API para papers acadêmicos do ArXiv.

**Como usar:**
- Sem autenticação necessária
- Sem limites conhecidos
- **Custo: GRÁTIS**

**Documentação:** http://arxiv.org/help/api

---

#### 1.1.5 Exa API (Opcional - Fallback)

**O que é:** API de pesquisa semântica para encontrar conteúdo relevante na web.

**Quando usar (Regras Específicas):**
- **Apenas se:**
  - APIs gratuitas retornarem **<5 resultados** OU
  - Evento for **muito grande/importante** (ex: size >$50k, múltiplos whales)
- Configurável via `USE_EXA_FALLBACK=true/false`
- **Meta Fase 3:** Se <20% dos casos precisarem de Exa, considerar remover completamente

**Como obter:**
1. Acesse: https://exa.ai/
2. Crie uma conta
3. Vá para Dashboard → API Keys
4. Gere uma nova API key
5. **Guarde a chave** - você precisará dela como `EXA_API_KEY` (opcional)

**Documentação:** https://docs.exa.ai/
**Biblioteca Python:** `exa-py`

**Custo estimado:** $0.01-0.05 por pesquisa (apenas quando usado)

**⚠️ Estratégia Recomendada (Exata):**

**Fase 1 (Agora - $0):**
- NewsAPI (principal)
- RSS expandido (15-20 feeds - ver `RSS_FEEDS.md`)
- ArXiv
- Reddit (com User-Agent + delays)
- **Começar SEM Exa**

**Fase 2 (Depois de validar):**
- Adicionar Exa como fallback opcional
- Regra: só usa se <5 resultados OU evento muito grande (>$50k)

**Fase 3 (Análise):**
- Analisar logs: % de casos que precisaram de Exa
- Se <20%: considerar remover Exa completamente, ficar 100% free

**🆕 CNN Integration:**
- **Não quebra setup existente** - expansão opcional
- **Usa dados das APIs gratuitas** - não adiciona custos
- **Melhora decisões** - mais confiança nos alertas
- **Configurável** - `ENABLE_CNN_ANALYSIS=false` por padrão

---

### 1.2 Polymarket APIs (Múltiplas Necessárias)

**O que é:** APIs para obter dados de mercados, odds, trades e posições do Polymarket.

**⚠️ IMPORTANTE:** Para detecção de whales comportamentais, você precisa de **múltiplas APIs**:

#### 1.2.1 Gamma API (Mercados e Odds) - Obrigatória

**O que é:** API oficial para dados de mercados, odds atuais, volume agregado e metadados.

**URL Base:** `https://gamma-api.polymarket.com`

**Endpoints Principais:**
- `/markets` - Lista de mercados (com filtros: `?active=true`, `?tags=ai`)
- `/events` - Eventos e mercados
- `/markets/{market_id}` - Dados específicos de um mercado

**Como usar:**
- **Sem autenticação necessária** (endpoints públicos)
- REST simples, perfeito para polling a cada 5-10 minutos
- Use para carregar `markets.yaml` dinamicamente ou validar
- Use para obter odds atuais nos alertas (`/markets` command)

**Documentação:** https://docs.polymarket.com/developers/gamma-markets-api/overview

**Exemplo de uso:**
```python
import httpx

async def get_market_data(market_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://gamma-api.polymarket.com/markets/{market_id}"
        )
        return response.json()

async def get_active_ai_markets():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://gamma-api.polymarket.com/markets",
            params={"active": "true", "tags": "ai"}
        )
        return response.json()
```

---

#### 1.2.2 CLOB API (Trades e Whale Detection) - ⚠️ OBRIGATÓRIA

**O que é:** API para dados de trades individuais, orders e order book. **Essencial para detecção de whales comportamentais.**

**Por que é obrigatória:**
- Gamma API só fornece volume agregado, não trades individuais
- Para detectar "nova posição grande", "wallet inativa", "exposição direcional", você precisa de dados de trades
- Sem CLOB API, detecção fica limitada a mudanças bruscas de odds (proxy fraco, muitos falsos positivos)

**URL Base:** `https://clob.polymarket.com`

**Endpoints Principais:**
- `/trades` - Trades recentes com size, price, side, maker/taker
- `/orders` - Orders ativas
- `/prices` - Preços atuais
- **WebSocket:** Para trades em tempo real (recomendado!)

**Biblioteca Python:** `py-clob-client`
```bash
pip install py-clob-client
```

**Como usar:**
- **Read-only não precisa API key** (para consultas públicas)
- WebSocket reduz latency e melhora performance (<20s decisão)
- Mais confiável que polling puro

**Documentação:** https://docs.polymarket.com/developers/CLOB/introduction

**Exemplo de uso:**
```python
from py_clob_client.client import ClobClient

# Cliente read-only (sem auth necessária)
client = ClobClient()

# Obter trades recentes de um mercado
trades = client.get_trades(market_id="0x...")

# WebSocket para trades em tempo real (recomendado)
async def listen_trades(market_id: str):
    async for trade in client.ws_trades(market_id):
        # Processar trade em tempo real
        process_trade(trade)
```

---

#### 1.2.3 Polymarket Subgraph (Alternativa On-Chain)

**O que é:** GraphQL endpoint hospedado no Goldsky para dados on-chain mais robustos.

**Quando usar:**
- Se precisar de precisão on-chain sem depender de CLOB off-chain
- Para queries complexas de trades, positions por user, volume por market, user PnL
- Real-time (atualiza com blocks)

**GraphQL Endpoint:**
```
https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/polymarket-subgraph/gn
```

**Vantagens:**
- Dados on-chain verificáveis
- Queries complexas via GraphQL
- Real-time updates

**Desvantagens:**
- Mais complexo que CLOB REST
- Requer conhecimento de GraphQL

**Recomendação:** Começar com CLOB API, considerar Subgraph se precisar de dados on-chain específicos.

**Documentação:** Verificar repositórios GitHub da comunidade Polymarket para exemplos de queries.

---

### 1.3 Telegram Bot API

**O que é:** API oficial do Telegram para criar bots.

**Como obter:**
1. Abra o Telegram
2. Procure por `@BotFather`
3. Envie `/newbot`
4. Siga as instruções:
   - Escolha um nome para o bot (ex: "ExaSignal Bot")
   - Escolha um username (deve terminar em `bot`, ex: `exasignal_bot`)
5. **BotFather retornará um token** - guarde como `TELEGRAM_BOT_TOKEN`

**Documentação:** https://core.telegram.org/bots/api
**Biblioteca Python:** `python-telegram-bot`

**Limites:**
- Mensagens: 30 por segundo por bot
- Para grupos: 20 mensagens por minuto

---

## 2. Criar Bot Telegram

### 2.1 Passo a Passo Completo

1. **Abra o Telegram** (app ou web)

2. **Procure por BotFather:**
   - Na busca, digite: `@BotFather`
   - Clique no bot oficial (verificado com ✓)

3. **Inicie conversa e envie:**
   ```
   /start
   ```

4. **Criar novo bot:**
   ```
   /newbot
   ```

5. **Siga as instruções:**
   - **Nome do bot:** `ExaSignal` (ou qualquer nome)
   - **Username:** `exasignal_bot` (deve terminar em `bot` e ser único)

6. **BotFather retornará:**
   ```
   Done! Congratulations on your new bot. You will find it at t.me/exasignal_bot.
   
   Use this token to access the HTTP API:
   123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   
   Keep your token secure and store it safely, it can be used by anyone to control your bot.
   ```

7. **Guarde o token** - você precisará dele como `TELEGRAM_BOT_TOKEN`

8. **Testar o bot:**
   - Procure pelo username do bot no Telegram
   - Envie `/start` para ele
   - Se responder, está funcionando!

### 2.2 Comandos Úteis do BotFather

- `/setdescription` - Definir descrição do bot
- `/setabouttext` - Definir texto "sobre"
- `/setcommands` - Definir lista de comandos
- `/setuserpic` - Definir foto do bot

**Exemplo de comandos para definir:**
```
/setcommands

start - Iniciar bot e ver informações
markets - Listar mercados monitorados
status - Status do sistema
settings - Configurar threshold de score
```

---

## 3. Dependências e Bibliotecas

### 3.1 Requisitos Python

- **Python:** 3.11 ou superior
- **Gerenciador de pacotes:** `pip` ou `poetry`

### 3.2 Arquivo requirements.txt

Crie um arquivo `requirements.txt` na raiz do projeto:

```txt
# Telegram Bot
python-telegram-bot==20.7

# Exa API
exa-py==1.0.0

# Polymarket APIs
py-clob-client==1.0.0  # CLOB API para trades e whale detection

# HTTP Client (async)
httpx==0.25.2
aiohttp==3.9.1

# Configuração
pyyaml==6.0.1
python-dotenv==1.0.0

# Data handling
pydantic==2.5.3

# Date/time
python-dateutil==2.8.2

# Database (persistência mínima)
aiosqlite==0.19.0  # Async SQLite para rate limits e cooldowns

# Logging
loguru==0.7.2
structlog==23.2.0  # Logging estruturado (opcional mas recomendado)

# Error tracking
sentry-sdk==1.38.0  # Para erros de APIs externas (opcional)

# Testes
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-mock==3.12.0
```

**Nota:** `asyncio` já vem com Python 3.11+, não precisa instalar.

### 3.3 Instalação

```bash
# Criar ambiente virtual
python -m venv venv

# Ativar ambiente virtual
# No macOS/Linux:
source venv/bin/activate
# No Windows:
# venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt
```

---

## 4. Estrutura do Projeto

### 4.1 Estrutura de Diretórios Recomendada

```
POLYMARKET/
├── README.md
├── SETUP_GUIDE.md
├── requirements.txt
├── .env.example
├── .env                    # Não commitar (gitignore)
├── .gitignore
├── markets.yaml
├── config.yaml             # Configurações gerais (opcional)
│
├── src/
│   ├── __init__.py
│   ├── main.py             # Entry point
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── market_manager.py
│   │   ├── whale_detector.py
│   │   ├── research_loop.py
│   │   ├── alignment_scorer.py
│   │   ├── alert_generator.py
│   │   └── telegram_bot.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── polymarket.py    # Cliente Polymarket/Gamma
│   │   └── exa_client.py     # Cliente Exa
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── market.py
│   │   ├── whale_event.py
│   │   ├── research_result.py
│   │   └── alert.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── rate_limiter.py
│   │   ├── logger.py
│   │   └── config.py
│   │
│   └── storage/
│       ├── __init__.py
│       └── user_db.py        # SQLite ou em memória
│
├── docs/
│   └── prds/                # PRDs já criados
│
└── tests/
    ├── __init__.py
    ├── test_market_manager.py
    ├── test_whale_detector.py
    └── ...
```

### 4.2 Criar Estrutura

```bash
# Criar diretórios
mkdir -p src/core src/api src/models src/utils src/storage docs/prds tests

# Criar arquivos __init__.py
touch src/__init__.py
touch src/core/__init__.py
touch src/api/__init__.py
touch src/models/__init__.py
touch src/utils/__init__.py
touch src/storage/__init__.py
touch tests/__init__.py
```

---

## 5. Configuração Inicial

### 5.1 Arquivo markets.yaml

Crie `markets.yaml` na raiz do projeto:

```yaml
markets:
  - market_id: "0x1234567890abcdef1234567890abcdef12345678"
    market_name: "Best AI Model by End of 2025"
    yes_definition: "Modelo líder em benchmarks e adoção"
    no_definition: "Qualquer outro resultado"
    category: "AI"
    description: "Mercado para determinar qual modelo de IA será considerado o melhor até o final de 2025"
    tags:
      - "AI"
      - "models"
      - "2025"
  
  - market_id: "0xabcdef1234567890abcdef1234567890abcdef12"
    market_name: "OpenAI vs Google vs Anthropic Outcomes"
    yes_definition: "OpenAI mantém liderança"
    no_definition: "Google ou Anthropic assumem liderança"
    category: "AI"
    tags:
      - "AI"
      - "companies"
      - "competition"
  
  - market_id: "0x9876543210fedcba9876543210fedcba98765432"
    market_name: "First AGI Claim"
    yes_definition: "Primeira reivindicação credível de AGI até 2026"
    no_definition: "Nenhuma reivindicação credível até 2026"
    category: "frontier_tech"
    tags:
      - "AGI"
      - "frontier"
      - "2026"

# Adicionar mais mercados conforme necessário (máximo 15)
```

**Nota:** Substitua os `market_id` pelos IDs reais dos mercados do Polymarket. Você pode encontrá-los:
- Na URL do mercado no Polymarket
- Via Gamma API
- Inspecionando o código da página do mercado

### 5.2 Arquivo .env.example

Crie `.env.example` como template:

```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# APIs de Pesquisa (Estratégia Híbrida)
NEWSAPI_KEY=your_newsapi_key_here  # Obrigatória - Grátis até 100 req/dia
EXA_API_KEY=your_exa_api_key_here  # Opcional - Apenas fallback
USE_EXA_FALLBACK=false  # true para usar Exa quando necessário
MIN_FREE_RESULTS=5  # Mínimo de resultados antes de usar Exa

# Polymarket/Gamma API (se necessário)
POLYMARKET_API_KEY=optional_if_needed

# Configurações
SCORE_THRESHOLD=70
POLLING_INTERVAL_SECONDS=300
MAX_ALERTS_PER_DAY=2
COOLDOWN_HOURS=24

# Logging
LOG_LEVEL=INFO
```

### 5.3 Arquivo .env

Copie `.env.example` para `.env` e preencha com suas chaves reais:

```bash
cp .env.example .env
# Edite .env com suas chaves reais
```

**⚠️ IMPORTANTE:** Adicione `.env` ao `.gitignore` para não commitar credenciais!

### 5.4 Arquivo .gitignore

Crie `.gitignore`:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# Environment variables
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
*.log
logs/

# Database
*.db
*.sqlite
*.sqlite3

# OS
.DS_Store
Thumbs.db
```

---

## 6. Variáveis de Ambiente

### 6.1 Carregar Variáveis

Crie `src/utils/config.py`:

```python
import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # APIs de Pesquisa (Estratégia Híbrida)
    NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY", "")  # Obrigatória
    EXA_API_KEY: Optional[str] = os.getenv("EXA_API_KEY")  # Opcional - fallback
    USE_EXA_FALLBACK: bool = os.getenv("USE_EXA_FALLBACK", "false").lower() == "true"
    MIN_FREE_RESULTS: int = int(os.getenv("MIN_FREE_RESULTS", "5"))
    
    # Polymarket (opcional)
    POLYMARKET_API_KEY: Optional[str] = os.getenv("POLYMARKET_API_KEY")
    
    # Configurações
    SCORE_THRESHOLD: float = float(os.getenv("SCORE_THRESHOLD", "70"))
    POLLING_INTERVAL_SECONDS: int = int(os.getenv("POLLING_INTERVAL_SECONDS", "300"))
    MAX_ALERTS_PER_DAY: int = int(os.getenv("MAX_ALERTS_PER_DAY", "2"))
    COOLDOWN_HOURS: int = int(os.getenv("COOLDOWN_HOURS", "24"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls) -> bool:
        """Valida se todas as variáveis obrigatórias estão definidas."""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN não definido")
        if not cls.NEWSAPI_KEY:
            raise ValueError("NEWSAPI_KEY não definido (obrigatório para pesquisa)")
        # EXA_API_KEY é opcional (apenas fallback)
        return True
```

---

## 7. Passos para Começar

### 7.1 Checklist Inicial

- [ ] Obter API key da Exa
- [ ] Criar bot Telegram e obter token
- [ ] Verificar acesso à Polymarket/Gamma API
- [ ] Instalar Python 3.11+
- [ ] Criar ambiente virtual
- [ ] Instalar dependências
- [ ] Criar estrutura de diretórios
- [ ] Criar `markets.yaml` com mercados reais
- [ ] Criar `.env` com todas as chaves
- [ ] Testar conexões individuais

### 7.2 Teste de Conexões

Crie `test_connections.py` na raiz para testar:

```python
"""Script para testar conexões com APIs."""
import asyncio
from src.utils.config import Config
from telegram import Bot
from exa_py import Exa

async def test_telegram():
    """Testa conexão com Telegram."""
    print("Testando Telegram Bot...")
    try:
        bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
        me = await bot.get_me()
        print(f"✅ Telegram conectado: @{me.username}")
        return True
    except Exception as e:
        print(f"❌ Erro Telegram: {e}")
        return False

def test_exa():
    """Testa conexão com Exa."""
    print("Testando Exa API...")
    try:
        exa = Exa(api_key=Config.EXA_API_KEY)
        # Teste simples
        results = exa.search(
            "AI expert prediction 2025",
            num_results=1
        )
        print(f"✅ Exa conectado: {len(results.results)} resultado(s)")
        return True
    except Exception as e:
        print(f"❌ Erro Exa: {e}")
        return False

async def main():
    Config.validate()
    print("=" * 50)
    telegram_ok = await test_telegram()
    exa_ok = test_exa()
    print("=" * 50)
    
    if telegram_ok and exa_ok:
        print("✅ Todas as conexões funcionando!")
    else:
        print("❌ Algumas conexões falharam. Verifique suas chaves.")

if __name__ == "__main__":
    asyncio.run(main())
```

Execute:
```bash
python test_connections.py
```

### 7.3 Implementação Incremental

Siga esta ordem de implementação:

1. **Market Manager** (`src/core/market_manager.py`)
   - Carregar `markets.yaml`
   - Validar estrutura
   - Testar com mercado de exemplo

2. **Cliente Polymarket** (`src/api/polymarket.py`)
   - Conectar com Gamma API
   - Obter dados de mercado
   - Testar com market_id real

3. **Cliente Exa** (`src/api/exa_client.py`)
   - Conectar com Exa API
   - Executar pesquisa de teste
   - Validar resultados

4. **Whale Detector** (`src/core/whale_detector.py`)
   - Implementar regras de detecção
   - Testar com dados reais
   - Validar eventos gerados

5. **Research Loop** (`src/core/research_loop.py`)
   - Construir queries
   - Executar pesquisas
   - Processar resultados

6. **Alignment Scorer** (`src/core/alignment_scorer.py`)
   - Implementar cálculo de score
   - Testar com dados de exemplo
   - Validar top 2 razões

7. **Alert Generator** (`src/core/alert_generator.py`)
   - Formatar alertas
   - Implementar rate limiting
   - Testar formatação

8. **Telegram Bot** (`src/core/telegram_bot.py`)
   - Implementar comandos básicos
   - Integrar com Alert Generator
   - Testar end-to-end

9. **Main Loop** (`src/main.py`)
   - Integrar todos os componentes
   - Implementar polling
   - Testar fluxo completo

---

## 8. Melhorias Recomendadas (Não Essenciais, mas Úteis)

### 8.1 Persistência SQLite

**Por que:** Evita perder estado em restarts (rate limits, cooldowns, settings de usuário).

**O que persistir:**
- Rate limits (alertas enviados hoje)
- Cooldowns por mercado (último alerta por market_id)
- Settings por usuário (threshold personalizado)

**Biblioteca recomendada:** `aiosqlite` (async) ou `SQLAlchemy`

**Exemplo de estrutura:**
```python
# src/storage/database.py
import aiosqlite
from datetime import datetime

class Database:
    def __init__(self, db_path: str = "exasignal.db"):
        self.db_path = db_path
    
    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS alerts_sent (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    user_id INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    threshold REAL DEFAULT 70.0,
                    updated_at DATETIME NOT NULL
                )
            """)
            await db.commit()
    
    async def record_alert_sent(self, market_id: str, user_id: int = None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO alerts_sent (market_id, timestamp, user_id) VALUES (?, ?, ?)",
                (market_id, datetime.now(), user_id)
            )
            await db.commit()
    
    async def get_alerts_today(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM alerts_sent WHERE DATE(timestamp) = DATE('now')"
            )
            result = await cursor.fetchone()
            return result[0] if result else 0
```

**Adicionar ao requirements.txt:**
```txt
aiosqlite==0.19.0
```

---

### 8.2 Cache de Pesquisas Exa

**Por que:** Economiza API calls e velocidade. Para eventos similares em mercados relacionados, cacheia resultados por 1-2h.

**Implementação:**
```python
# src/utils/cache.py
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import hashlib
import json

class ResearchCache:
    def __init__(self, ttl_hours: int = 2):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = timedelta(hours=ttl_hours)
    
    def _generate_key(self, market_id: str, direction: str, query_templates: list) -> str:
        """Gera chave única baseada em mercado, direção e queries."""
        data = f"{market_id}:{direction}:{json.dumps(query_templates)}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def get(self, market_id: str, direction: str, query_templates: list) -> Optional[Dict]:
        """Obtém resultado do cache se ainda válido."""
        key = self._generate_key(market_id, direction, query_templates)
        
        if key in self.cache:
            cached = self.cache[key]
            if datetime.now() - cached['timestamp'] < self.ttl:
                return cached['results']
            else:
                # Expirou, remover
                del self.cache[key]
        
        return None
    
    def set(self, market_id: str, direction: str, query_templates: list, results: Dict):
        """Armazena resultado no cache."""
        key = self._generate_key(market_id, direction, query_templates)
        self.cache[key] = {
            'results': results,
            'timestamp': datetime.now()
        }
```

**Uso no Research Loop:**
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

### 8.3 Health Checks e Monitoring

**Health Check Endpoint no Bot:**

Adicione comando `/health` ou endpoint HTTP simples:

```python
# src/core/telegram_bot.py
async def handle_health(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para comando /health."""
    checks = {
        "telegram": await self._check_telegram(),
        "exa_api": await self._check_exa(),
        "polymarket": await self._check_polymarket(),
        "database": await self._check_database()
    }
    
    status = "✅ Healthy" if all(checks.values()) else "⚠️ Issues"
    message = f"🏥 Health Status: {status}\n\n"
    
    for service, healthy in checks.items():
        emoji = "✅" if healthy else "❌"
        message += f"{emoji} {service.capitalize()}\n"
    
    await update.message.reply_text(message)
```

**Logging Estruturado (structlog):**

```python
# src/utils/logger.py
import structlog

logger = structlog.get_logger()

# Uso
logger.info("whale_event_detected", 
           market_id=market_id, 
           size_usd=size_usd,
           direction=direction)
```

**Sentry para Erros de APIs Externas:**

```python
# src/utils/error_tracking.py
import sentry_sdk

sentry_sdk.init(
    dsn="your-sentry-dsn",
    traces_sample_rate=1.0,
)

# Capturar erros de APIs
try:
    results = await exa_api.search(...)
except Exception as e:
    sentry_sdk.capture_exception(e)
    logger.error("exa_api_error", error=str(e))
```

**Adicionar ao requirements.txt:**
```txt
structlog==23.2.0
sentry-sdk==1.38.0
```

---

## 9. Testes e Validação

### 9.1 Testes Unitários

**Framework:** `pytest`

**Testes para Alignment Scorer (Determinístico):**

```python
# tests/test_alignment_scorer.py
import pytest
from src.core.alignment_scorer import AlignmentScorer
from src.models.whale_event import WhaleEvent
from src.models.research_result import ResearchResults

def test_score_calculation_deterministic():
    """Testa que mesmo input sempre produz mesmo score."""
    scorer = AlignmentScorer()
    
    # Criar dados de teste
    whale_event = WhaleEvent(...)
    research_results = ResearchResults(...)
    
    # Calcular score duas vezes
    score1 = scorer.calculate_score(whale_event, research_results)
    score2 = scorer.calculate_score(whale_event, research_results)
    
    assert score1.score == score2.score
    assert score1.components == score2.components

def test_score_components():
    """Testa cálculo de cada componente."""
    scorer = AlignmentScorer()
    
    # Testar componente A: Credibilidade
    results = create_test_results_with_source_types(["researcher", "lab_blog"])
    credibility = scorer._calculate_credibility(results)
    assert 0 <= credibility <= 30
    
    # Testar componente B: Recência
    results = create_test_results_recent(days=5)
    recency = scorer._calculate_recency(results)
    assert recency == 20  # ≤7 dias = +20
```

**Mocks para APIs Externas:**

```python
# tests/mocks.py
from unittest.mock import AsyncMock, MagicMock

class MockExaClient:
    def __init__(self):
        self.search = AsyncMock()
    
    def set_search_results(self, results):
        self.search.return_value = results

class MockPolymarketClient:
    def __init__(self):
        self.get_market_data = AsyncMock()
        self.get_trades = AsyncMock()
    
    def set_market_data(self, data):
        self.get_market_data.return_value = data

# tests/test_research_loop.py
@pytest.mark.asyncio
async def test_research_loop_with_mock():
    mock_exa = MockExaClient()
    mock_exa.set_search_results([...])
    
    research_loop = ResearchLoop(exa_client=mock_exa)
    results = await research_loop.execute_research(whale_event)
    
    assert len(results.results) > 0
    mock_exa.search.assert_called_once()
```

**Adicionar ao requirements.txt:**
```txt
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-mock==3.12.0
```

### 9.2 Testes de Integração

Teste o fluxo completo com dados mockados primeiro, depois com dados reais.

### 9.3 Validação Manual

- [ ] Bot responde a `/start`
- [ ] Bot lista mercados com `/markets`
- [ ] Bot mostra status com `/status`
- [ ] Bot permite alterar settings com `/settings`
- [ ] Bot responde a `/health` (se implementado)
- [ ] Alertas são formatados corretamente
- [ ] Rate limiting funciona
- [ ] Cooldown funciona
- [ ] Cache funciona (pesquisas similares retornam do cache)
- [ ] Persistência funciona (restart mantém estado)

---

## 9. Deploy

### 9.1 Opções de Deploy

#### Opção A: Railway (Recomendado para MVP)

1. Acesse https://railway.app/
2. Crie conta (pode usar GitHub)
3. New Project → Deploy from GitHub
4. Conecte seu repositório
5. Adicione variáveis de ambiente no dashboard
6. Railway detecta Python automaticamente
7. Deploy!

**Vantagens:**
- Grátis para começar
- Fácil configuração
- Suporta Python nativamente

#### Opção B: Fly.io

1. Instale CLI: `curl -L https://fly.io/install.sh | sh`
2. Login: `fly auth login`
3. Criar app: `fly launch`
4. Adicionar secrets: `fly secrets set TELEGRAM_BOT_TOKEN=...`
5. Deploy: `fly deploy`

#### Opção C: Render

1. Acesse https://render.com/
2. New → Web Service
3. Conecte repositório
4. Configure:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python src/main.py`
5. Adicione variáveis de ambiente
6. Deploy

### 9.2 Arquivo para Deploy (Railway/Render)

Crie `Procfile` na raiz:

```
worker: python src/main.py
```

Ou `railway.json`:

```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python src/main.py",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### 9.3 Variáveis de Ambiente no Deploy

Certifique-se de adicionar todas as variáveis no painel de deploy:
- `TELEGRAM_BOT_TOKEN`
- `EXA_API_KEY`
- `SCORE_THRESHOLD`
- `POLLING_INTERVAL_SECONDS`
- etc.

---

## 10. Recursos Adicionais

### 10.1 Documentação das APIs

- **Exa API:** https://docs.exa.ai/
- **Telegram Bot API:** https://core.telegram.org/bots/api
- **python-telegram-bot:** https://python-telegram-bot.org/
- **Gamma API:** https://docs.gamma.io/ (verificar documentação atual)

### 10.2 Comunidades e Suporte

- **Telegram Bot Development:** https://t.me/BotDevelopment
- **Polymarket Community:** Discord/GitHub
- **Exa AI:** Suporte via email ou dashboard

### 10.3 Troubleshooting Comum

**Problema:** Bot não responde
- Verificar token no `.env`
- Verificar se bot está ativo no Telegram
- Verificar logs de erro

**Problema:** Exa API retorna erro
- Verificar API key
- Verificar rate limits
- Verificar formato da query

**Problema:** Não consegue obter dados do Polymarket
- Verificar se market_id está correto
- Tentar Gamma API ao invés de GraphQL
- Verificar se mercado existe e está ativo

---

## 11. Próximos Passos

1. ✅ Seguir este guia passo a passo
2. ✅ Implementar componentes incrementalmente
3. ✅ Testar cada componente isoladamente
4. ✅ Integrar componentes gradualmente
5. ✅ Testar fluxo end-to-end
6. ✅ Deploy em ambiente de produção
7. ✅ Monitorar e iterar

---

## 📝 Notas Finais

- **Comece simples:** Implemente o mínimo viável primeiro
- **Teste frequentemente:** Valide cada componente antes de avançar
- **Mantenha logs:** Facilita debugging
- **Documente decisões:** Anote escolhas importantes
- **Itere rápido:** MVP deve ser funcional, não perfeito

**Boa sorte com a implementação! 🚀**

