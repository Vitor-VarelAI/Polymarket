# ExaSignal — Índice de Documentação

Guia rápido para encontrar a documentação que você precisa.

---

## 📚 Documentos Principais

### Visão e Planejamento
- **[README.md](README.md)** - Visão geral do produto, escopo do MVP, filosofia
- **[QUICK_START.md](QUICK_START.md)** - Guia rápido para começar em 5 minutos

### Setup e Implementação
- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Guia completo de setup com todas as APIs e configurações
- **[COST_OPTIMIZATION.md](COST_OPTIMIZATION.md)** - ⭐ Estratégia híbrida para minimizar custos
- **[RSS_FEEDS.md](RSS_FEEDS.md)** - Lista completa de 15-20 feeds de qualidade
- **[IMPROVEMENTS.md](IMPROVEMENTS.md)** - Melhorias recomendadas (SQLite, cache, health checks, testes)

### Análise CNN (Nova Funcionalidade Avançada)
- **[CNN_MARKET_ANALYSIS.md](docs/CNN_MARKET_ANALYSIS.md)** - ⭐ Integração CNN para análise visual de mercados
- **[cnn_test.py](src/cnn_test.py)** - Teste inicial de validação CNN (1 canal + 8 canais multi-source)

### PRDs (Product Requirements Documents)
- **[PRD-00-Overview.md](docs/prds/PRD-00-Overview.md)** - Visão geral e arquitetura
- **[PRD-01-Market-Management.md](docs/prds/PRD-01-Market-Management.md)** - Gestão de mercados
- **[PRD-02-Whale-Event-Detection.md](docs/prds/PRD-02-Whale-Event-Detection.md)** - Detecção de whales (CLOB API)
- **[PRD-03-Research-Loop.md](docs/prds/PRD-03-Research-Loop.md)** - ⭐ Pesquisa híbrida (free first)
- **[PRD-04-Alignment-Score.md](docs/prds/PRD-04-Alignment-Score.md)** - Sistema de scoring
- **[PRD-05-Alert-Generation.md](docs/prds/PRD-05-Alert-Generation.md)** - Geração de alertas
- **[PRD-06-Telegram-Bot.md](docs/prds/PRD-06-Telegram-Bot.md)** - Bot Telegram

---

## 🎯 Estratégia de Custos (Resumo)

### Fase 1 (Agora - $0/mês)
- ✅ NewsAPI (principal)
- ✅ RSS expandido (15-20 feeds - ver `RSS_FEEDS.md`)
- ✅ ArXiv
- ✅ Reddit (com User-Agent + delays)
- **Começar SEM Exa**

### Fase 2 (Depois de validar)
- ✅ Adicionar Exa como fallback opcional
- ✅ Regra: só usa se <5 resultados OU evento >$50k
- ✅ Logging detalhado

### Fase 3 (Análise)
- ✅ Analisar logs: % de casos que precisaram de Exa
- ✅ Se <20%: considerar remover Exa completamente
- ✅ Ficar 100% free

**Documentação completa:** [COST_OPTIMIZATION.md](COST_OPTIMIZATION.md)

---

## 🔧 APIs Necessárias

### Obrigatórias (Gratuitas)
1. **NewsAPI** - 100 req/dia grátis
2. **RSS Feeds** - 15-20 feeds (ver `RSS_FEEDS.md`)
3. **Reddit API** - Gratuito
4. **ArXiv API** - Gratuito
5. **Telegram Bot API** - Gratuito
6. **Gamma API** - Mercados e odds (gratuito)
7. **CLOB API** - Trades e whale detection (gratuito, read-only)

### Opcionais
- **Exa API** - Apenas fallback (ver estratégia acima)

**Documentação completa:** [SETUP_GUIDE.md](SETUP_GUIDE.md)

---

## 📖 Ordem de Leitura Recomendada

1. **Começar:** [README.md](README.md) - Entender o produto
2. **Setup:** [SETUP_GUIDE.md](SETUP_GUIDE.md) - Como configurar tudo
3. **Custos:** [COST_OPTIMIZATION.md](COST_OPTIMIZATION.md) - Estratégia híbrida
4. **Feeds:** [RSS_FEEDS.md](RSS_FEEDS.md) - Lista de feeds
5. **Implementar:** [PRDs](docs/prds/) - Especificações detalhadas
6. **Melhorias:** [IMPROVEMENTS.md](IMPROVEMENTS.md) - Após MVP básico

---

## 🚀 Quick Links

- **Testar conexões:** `python test_connections.py`
- **Lista de feeds:** [RSS_FEEDS.md](RSS_FEEDS.md)
- **Estratégia de custos:** [COST_OPTIMIZATION.md](COST_OPTIMIZATION.md)
- **Guia rápido:** [QUICK_START.md](QUICK_START.md)

---

---

## 🆕 Atualizações Recentes

### CNN Market Analysis Integration
**Status:** ✅ Implementado e documentado

**O que foi adicionado:**
- ✅ **CNN_MARKET_ANALYSIS.md** - Documentação técnica completa
- ✅ **src/cnn_test.py** - Teste de validação inicial
- ✅ **requirements.txt** - Dependências TensorFlow adicionadas
- ✅ **Compatibilidade verificada** - mantém filosofia do projeto
- ✅ **Integração opcional** - não quebra MVP existente

**Compatibilidade:**
- ✅ Mantém runs agendados (2-3x/dia)
- ✅ Usa APIs gratuitas existentes
- ✅ Adiciona qualidade sem gerar spam
- ✅ Custos $0 inicialmente
- ✅ Configurável via `ENABLE_CNN_ANALYSIS=false`

**Próximo passo:**
```bash
# Testar conceito CNN
pip install tensorflow scikit-learn numpy pandas
python src/cnn_test.py  # Meta: >50% accuracy
```

**Última atualização:** CNN Integration completa - pronto para teste e expansão incremental.

