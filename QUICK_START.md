# 🐋 ExaSignal - Quick Start

Guia rápido para pôr o ExaSignal a funcionar com alertas Telegram.

---

## 1. Configurar .env

```bash
cp .env.example .env
```

Edita `.env` com as tuas keys:
```bash
TELEGRAM_BOT_TOKEN=xxx       # @BotFather
GROQ_API_KEY=xxx             # groq.com (grátis)
BRAVE_API_KEY=xxx            # api.search.brave.com (grátis)
NEWSAPI_KEY=xxx              # newsapi.org (grátis)
EXA_API_KEY=xxx              # Opcional, só backup
```

---

## 2. Instalar

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 3. Iniciar Alertas

### Modo Contínuo (Recomendado)
```bash
python -m src.core.scheduler
```

O scheduler:
- ✅ Monitoriza news a cada 5 min (market hours) / 30 min (off-hours)
- ✅ Envia alertas automáticos para Telegram
- ✅ Score ≥70 + Confidence ≥60 = Alert!

### Modo Background (Produção)
```bash
nohup python -m src.core.scheduler > scheduler.log 2>&1 &
```

---

## 4. Comandos Telegram

| Comando | Descrição |
|---------|-----------|
| `/start` | Registo |
| `/markets` | Ver mercados |
| `/signals` | Sinais recentes |
| `/status` | Estado do sistema |

---

## 5. Formatos de Alerta

### News Alert:
```
🟢 YES | Will GPT-5 be released?
📰 Trigger: NEWS | 📊 Odds: 65%
🎯 Score: 79/100
🤖 AI Confidence: 80%
📚 Sources: brave: 10 | rss: 10
🔗 Read More: [links]
📈 Trade: [Polymarket link]
```

### Whale Alert:
```
🐋 WHALE ALERT 🐋
🟢 YES | Will Bitcoin reach 100k?
🚨💰 MASSIVE BET: $150k
👤 Type: 🦈 SHARK | Win Rate: 78%
🔗 Polygonscan: [link]
```

---

## 6. Testar Sistema

```bash
python test_connections.py
```

---

## Suporte

Logs: `tail -f scheduler.log`
