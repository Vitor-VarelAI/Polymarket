# 🐋 ExaSignal: AI-Powered Polymarket Trading Bot

ExaSignal é um sistema automatizado de trading signals para Polymarket, com **digest diário curado por AI** para evitar spam e hallucinations.

## 🎯 O que faz

O bot corre 24/7, acumula oportunidades de múltiplos scanners, e envia **3 digests por dia** com os 10 melhores picks:

| Horário | Digest |
|---------|--------|
| 11:00 UTC | Morning Digest |
| 16:00 UTC | Afternoon Digest |
| 20:00 UTC | Evening Digest |

### Scanners Activos (todos alimentam o digest)

| Scanner | Estratégia | O que encontra |
|---------|------------|----------------|
| **ValueBets** | Underdogs (2-50% odds) | Bets com alto payout |
| **SafeBets** | 97%+ odds | Lucros pequenos mas seguros |
| **Correlation** | Arbitragem | Mercados correlacionados |
| **Weather** | Weather forecast vs market | Edge meteorológico |
| **NewsMonitor** | Notícias + mercados | Alpha de notícias |

## 📱 Comandos Telegram

| Comando | Descrição |
|---------|-----------|
| `/start` | Registo no bot |
| `/test_digest` | 🆕 Gerar digest agora |
| `/scanner_status` | Ver queue e candidatos |
| `/debug` | Diagnóstico detalhado |
| `/test_alert` | Testar conexão |
| `/markets` | Ver mercados |
| `/investigate` | Investigar mercado específico |

## 🚀 Quick Start

### 1. Clonar e Instalar

```bash
git clone https://github.com/Vitor-VarelAI/Polymarket.git
cd Polymarket
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configurar `.env`

```bash
cp .env.example .env
```

**OBRIGATÓRIAS:**
- `TELEGRAM_BOT_TOKEN` - @BotFather
- `TELEGRAM_ADMIN_ID` - @userinfobot (recebe alertas mesmo após reset)
- `GROQ_API_KEY` - console.groq.com

**RECOMENDADAS (grátis):**
- `NEWSAPI_KEY`, `FINNHUB_API_KEY`, `BRAVE_API_KEY`
- Weather: `TOMORROW_API_KEY`, `OPENWEATHER_API_KEY`, `WEATHERAPI_KEY`

### 3. Correr

```bash
python -m src.main
```

### 4. Deploy Railway

1. Fork → Railway.app → Deploy from GitHub
2. Adicionar variáveis de ambiente
3. Deploy automático!

## 📊 Sistema Anti-Hallucination

O digest usa um sistema estrito para evitar informação inventada:

```
Scanners → Acumulam candidatos
              ↓
    EV e Confidence calculados por FÓRMULA
              ↓
    LLM só SELECCIONA (não inventa)
              ↓
    Validação pós-LLM (detecta números falsos)
              ↓
    Digest com timestamps e fontes
```

### Métricas Calculadas (não LLM)

| Métrica | Fórmula |
|---------|---------|
| **EV Score** | `(win_prob × payout) - (lose_prob × loss)` |
| **Confidence** | Baseado em liquidity + categoria + dias |

## 📈 Exemplo de Digest

```
🎯 POLYMARKET DIGEST
📅 Morning • Jan 10, 2026 • 11:00 UTC

From 45 scanned markets, selected 10 data-driven picks.

━━━━━━━━━━━━━━━━━━━━━

#1 🟢 HIGH

📊 Will ETH hit $10k in 2026?
   Odds: YES 15% | Liquidity: $85,000
   Resolves: 45 days | EV: +0.12

💵 $1 Bet: Win $5.67 (6.7x) or Lose $1

🧠 HIGH confidence, diversified category, positive EV.

🔗 Place Bet

━━━━━━━━━━━━━━━━━━━━━

📊 SUMMARY
• Invested: $10 | Max Return: $58
• Average EV: +0.08
• Break-even: ~10% win rate

⚠️ Not financial advice. Data from Polymarket at 11:00 UTC.
```

## 🛠️ Arquitectura

```
src/
├── main.py                    # Entry point
├── core/
│   ├── digest_scheduler.py    # 🆕 Anti-hallucination digest
│   ├── value_bets_scanner.py  # 🆕 Underdog scanner
│   ├── telegram_bot.py        # Bot + commands
│   ├── safe_bets_scanner.py   # 97%+ odds
│   ├── correlation_detector.py# Arbitrage
│   ├── weather_scanner.py     # Weather value
│   └── news_monitor.py        # News alpha
├── api/
│   ├── gamma_client.py        # Polymarket API
│   ├── groq_client.py         # LLM
│   └── weather_client.py      # Multi-source weather
└── storage/
    ├── user_db.py             # Users
    └── rate_limiter.py        # Rate limiting
```

## ⚙️ Configuração Avançada

No `src/main.py` podes ajustar:

```python
# ValueBetsScanner
min_odds=2.0,        # Odds mínimas (%)
max_odds=50.0,       # Odds máximas (%)
min_liquidity=1000,  # Liquidez mínima ($)

# DigestScheduler
picks_per_digest=10, # Picks por digest
```

## ⚠️ Disclaimer

Projecto educacional. Trading envolve risco. Não apostes dinheiro que não podes perder.

## 📜 License

MIT
