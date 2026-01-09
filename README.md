# 🐋 ExaSignal: AI-Powered Polymarket Trading Bot

ExaSignal é um sistema automatizado de trading signals para Polymarket, inspirado em bots lendários como **SwissTony** (que fez $3.7M em 6 meses).

## 🎯 O que faz

O bot corre 24/7 e envia alertas para **Telegram** quando encontra oportunidades:

| Scanner | Estratégia | Intervalo |
|---------|------------|-----------|
| **NewsMonitor** | Notícias que impactam mercados | 5 min |
| **CorrelationDetector** | Arbitragem entre mercados correlacionados | 10 min |
| **SafeBetsScanner** | Mercados com 97%+ odds (lucro 1-3%) | 30 min |
| **WeatherScanner** | Weather markets undervalued (≤10¢) | 3 horas |

## 📱 Comandos Telegram

| Comando | Descrição |
|---------|-----------|
| `/start` | Registo no bot |
| `/test_alert` | Testar se broadcasts funcionam |
| `/scanner_status` | Ver estado dos scanners |
| `/markets` | Ver mercados monitorizados |
| `/status` | Estado do sistema |
| `/health` | Verificar saúde |
| `/signals` | Ver sinais recentes |
| `/investigate` | Investigar mercado específico |

## 🚀 Quick Start

### 1. Clonar e Instalar

```bash
git clone https://github.com/Vitor-VarelAI/Polymarket.git
cd Polymarket
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 2. Configurar `.env`

Copia `.env.example` para `.env` e preenche as API keys:

```bash
cp .env.example .env
```

**APIs OBRIGATÓRIAS:**
- `TELEGRAM_BOT_TOKEN` - Criar bot em @BotFather
- `GROQ_API_KEY` - https://console.groq.com

**APIs RECOMENDADAS (grátis):**
- `NEWSAPI_KEY` - https://newsapi.org
- `FINNHUB_API_KEY` - https://finnhub.io
- `BRAVE_API_KEY` - https://brave.com/search/api

**APIs WEATHER (todas grátis):**
- `TOMORROW_API_KEY` - https://www.tomorrow.io
- `OPENWEATHER_API_KEY` - https://openweathermap.org/api
- `WEATHERAPI_KEY` - https://www.weatherapi.com

### 3. Correr Localmente

```bash
python -m src.main
```

### 4. Deploy no Railway (Recomendado)

1. Fork este repo para a tua conta GitHub
2. Vai a [Railway.app](https://railway.app)
3. New Project → Deploy from GitHub
4. Seleciona o repo
5. Adiciona as variáveis de ambiente
6. Deploy automático!

## 📊 Estratégias Implementadas

### 1. 📰 News Alpha (NewsMonitor)
- Busca notícias de múltiplas fontes (NewsAPI, Finnhub, RSS, Google News)
- Match com mercados Polymarket
- Gera sinais quando há divergência entre notícia e odds

### 2. ⚡ Arbitragem de Correlação (CorrelationDetector)
- Usa AI para identificar mercados correlacionados
- Ex: "Trump wins" deve ter odds similares a "Republican wins"
- Alerta quando há divergência >2%

### 3. 💰 Safe Bets / Vacuum Cleaner (SafeBetsScanner)
- Encontra mercados com 97%+ de probabilidade
- Lucro pequeno mas "garantido" (1-3¢ por share)
- Inspirado na estratégia SwissTony

### 4. 🌦️ Weather Value (WeatherScanner)
- Foca em weather markets (temperatura, chuva, etc.)
- Só aposta em outcomes ≤10¢ (underdogs)
- Usa 4 APIs weather para consenso de previsão
- Alerta quando forecast diz probabilidade diferente do mercado

## 🔧 Configuração Avançada

### Ajustar Thresholds

No `src/main.py` podes ajustar:

```python
# NewsMonitor
min_score=70,          # Score mínimo para alertar
min_confidence=60,     # Confiança mínima

# CorrelationDetector
min_edge=2.0,          # Edge mínimo (%)

# SafeBetsScanner
min_odds_threshold=97.0,  # Odds mínimas (%)
min_liquidity=1000,       # Liquidez mínima ($)

# WeatherScanner
max_entry_price=10.0,  # Preço máximo (¢)
min_edge=5.0,          # Edge mínimo (%)
```

## 📈 Exemplos de Alertas

### News Signal
```
🟢 NEW TRADING SIGNAL 📊

📰 Breaking: Fed announces rate cut...
📊 Market: Will Fed cut rates in January?
🎯 Direction: YES
📈 Confidence: 85%
```

### Arbitrage
```
⚡ ARBITRAGE OPPORTUNITY

📊 Market A: Trump wins (62.5%)
📊 Market B: Republican wins (58.0%)
💰 Potential Edge: 4.5%
```

### Safe Bet
```
💰 SAFE BET FOUND 🟢

📊 Market: Will Bitcoin exist in 2025?
📈 YES: 99.5% | NO: 0.5%
🎯 Trade: BET YES @ 99.5¢
💵 Profit if wins: 0.5¢ per share
```

### Weather Bet
```
🌦️ WEATHER VALUE BET 🟠

📍 Location: New York
🌡️ Tomorrow's High: 68°F (3 sources agree)
🎯 Market says: 8% | Our forecast: 22%
💰 $1 → $12.50 if wins (1150% profit)
```

## 🛠️ Arquitetura

```
src/
├── main.py              # Entry point (Railway)
├── api/
│   ├── weather_client.py   # Multi-source weather
│   ├── finnhub_client.py   # Real-time news
│   ├── gamma_client.py     # Polymarket API
│   └── ...
├── core/
│   ├── telegram_bot.py         # Bot + commands
│   ├── news_monitor.py         # News scanning
│   ├── correlation_detector.py # Arbitrage detection
│   ├── safe_bets_scanner.py    # 97%+ odds
│   ├── weather_scanner.py      # Weather value
│   └── ...
└── storage/
    ├── user_db.py        # User management
    └── rate_limiter.py   # API rate limiting
```

## 📝 Limites das APIs Gratuitas

| API | Limite Gratuito | Uso Estimado/Dia |
|-----|-----------------|------------------|
| Tomorrow.io | 500/dia | ~40 ✓ |
| OpenWeatherMap | 1,000/dia | ~40 ✓ |
| WeatherAPI.com | 1M/mês | ~40 ✓ |
| NewsAPI | 100/dia | ~50 ✓ |
| Finnhub | 60/min | ~200 ✓ |
| Groq | 30/min | Variable ✓ |

## ⚠️ Disclaimer

Este é um projeto educacional. Trading envolve risco. Não apostes dinheiro que não podes perder.

## 📜 License

MIT
