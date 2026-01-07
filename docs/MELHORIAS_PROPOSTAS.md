# ExaSignal - Melhorias Propostas

## 1. Anti-False Positives: Filtro de Liquidez Mínima

### Problema
Alertas em mercados com liquidez muito baixa podem não ser executáveis ou ter slippage extremo.

### Solução
```python
# Em enriched_signal.py ou research_loop.py
MIN_LIQUIDITY_THRESHOLD = 10000  # $10k USD

def should_alert(market_data, signal_score):
    if market_data['liquidity'] < MIN_LIQUIDITY_THRESHOLD:
        logger.info(f"Skipping alert: liquidity ${market_data['liquidity']} < ${MIN_LIQUIDITY_THRESHOLD}")
        return False
    
    if signal_score >= 70:
        return True
    
    return False
```

### Benefício
- Evita alertas em mercados ilíquidos
- Melhora qualidade dos sinais
- Reduz noise no Telegram

---

## 2. Correlation Tracking: Backtesting Passivo

### Problema
Não sabemos qual % dos nossos sinais são realmente profitable.

### Solução
Criar tabela para tracking histórico:
```sql
-- signals_performance.sql
CREATE TABLE signal_performance (
    id INTEGER PRIMARY KEY,
    market_id TEXT,
    signal_timestamp DATETIME,
    signal_direction TEXT,  -- YES/NO
    odds_at_signal REAL,
    signal_score INTEGER,
    
    -- Resolution data (preenchido depois)
    resolved_at DATETIME,
    final_outcome TEXT,     -- YES/NO
    was_correct BOOLEAN,
    
    -- Performance metrics
    odds_movement_24h REAL, -- Mudança de odds nas próximas 24h
    max_profit_window REAL  -- Melhor momento para ter saído
);
```

```python
# Em core/performance_tracker.py
class PerformanceTracker:
    def log_signal(self, market_id, direction, odds, score):
        """Registar sinal quando é emitido"""
        self.db.insert({
            'market_id': market_id,
            'signal_direction': direction,
            'odds_at_signal': odds,
            'signal_score': score,
            'signal_timestamp': datetime.now()
        })
    
    def update_resolution(self, market_id, outcome):
        """Atualizar quando mercado resolve"""
        signal = self.db.get_signal(market_id)
        was_correct = (signal['direction'] == outcome)
        
        self.db.update({
            'was_correct': was_correct,
            'final_outcome': outcome,
            'resolved_at': datetime.now()
        })
    
    def get_performance_stats(self):
        """Stats gerais"""
        return {
            'total_signals': self.db.count(),
            'win_rate': self.db.avg('was_correct'),
            'avg_score_winners': self.db.avg('score', where='was_correct=1'),
            'avg_score_losers': self.db.avg('score', where='was_correct=0')
        }
```

### Integração
- Adicionar chamada em `research_loop.py` após enviar alerta
- Criar cronjob diário para verificar mercados resolvidos
- Dashboard Telegram semanal com stats: `/stats`

### Benefício
- Saber empiricamente se score ≥70 é bom threshold
- Identificar que tipos de mercados funcionam melhor
- Ajustar scoring system baseado em dados reais

---

## 3. Whale Behavior Patterns: Timing & Category Context

### 3A. Bet Timing Pattern

**Early vs Late Whales:**
```python
# Em models/whale_event.py
class BetTimingProfile:
    def __init__(self, wallet_history):
        self.avg_time_to_close = self._calculate_avg_timing(wallet_history)
        self.timing_type = self._classify_timing()
    
    def _calculate_avg_timing(self, history):
        """
        Calcula média de quando whale aposta
        (dias antes do close)
        """
        timings = []
        for bet in history:
            days_before_close = (bet['market_close'] - bet['bet_time']).days
            timings.append(days_before_close)
        
        return sum(timings) / len(timings)
    
    def _classify_timing(self):
        if self.avg_time_to_close > 30:
            return "🔮 EARLY_BIRD"    # Aposta muito antes
        elif self.avg_time_to_close > 7:
            return "⚡ MOMENTUM"      # Aposta após news
        else:
            return "🎯 SNIPER"        # Aposta perto do close
```

**Adicionar ao Whale Alert:**
```
**👤 WHALE PROFILE:**
├ Timing Style: 🔮 EARLY_BIRD (avg 45 days before close)
├ Best with: News-driven markets
```

### 3B. Market Category Specialization
```python
# Tracking de performance por categoria
class CategoryPerformance:
    CATEGORIES = ['crypto', 'politics', 'sports', 'ai', 'business']
    
    def get_whale_specialty(self, wallet_address):
        """
        Retorna categoria onde whale tem melhor win rate
        """
        history = self.get_wallet_history(wallet_address)
        
        category_stats = {}
        for cat in self.CATEGORIES:
            cat_bets = [b for b in history if b['category'] == cat]
            if len(cat_bets) >= 5:  # Mínimo 5 bets
                win_rate = sum(b['won'] for b in cat_bets) / len(cat_bets)
                category_stats[cat] = {
                    'win_rate': win_rate,
                    'total_bets': len(cat_bets)
                }
        
        best_cat = max(category_stats.items(), key=lambda x: x[1]['win_rate'])
        return best_cat
```

**Filtro de Relevância:**
```python
def is_whale_relevant(whale_profile, market_category):
    """
    Só alertar se whale é especialista na categoria do market
    """
    specialty, stats = whale_profile.get_specialty()
    
    # Whale tem specialty E market match
    if specialty == market_category and stats['win_rate'] > 0.70:
        return True
    
    # Ou é um mega whale consistente em tudo
    if whale_profile.type == "MEGA_WHALE" and whale_profile.overall_win_rate > 0.75:
        return True
    
    return False
```

### Benefício
- Reduz false positives de whales irrelevantes
- Identifica verdadeiros "smart money" por nicho
- Melhora confiança nos alerts

---

## 4. Market Momentum: Velocidade de Mudança das Odds

### Problema
News signal pode ser importante, mas se odds não se movem = mercado não acredita.

### Solução
```python
# Em core/momentum_tracker.py
class MomentumTracker:
    def __init__(self):
        self.odds_history = {}  # {market_id: [(timestamp, odds), ...]}
    
    def track_odds(self, market_id, current_odds):
        """Guardar histórico de odds"""
        if market_id not in self.odds_history:
            self.odds_history[market_id] = []
        
        self.odds_history[market_id].append((datetime.now(), current_odds))
        
        # Manter só últimas 24h
        cutoff = datetime.now() - timedelta(hours=24)
        self.odds_history[market_id] = [
            (ts, odds) for ts, odds in self.odds_history[market_id]
            if ts > cutoff
        ]
    
    def get_momentum_score(self, market_id):
        """
        Calcula velocidade de mudança
        Score: 0-10
        """
        if market_id not in self.odds_history:
            return 0
        
        history = self.odds_history[market_id]
        if len(history) < 2:
            return 0
        
        # Mudança nas últimas 1h, 6h, 24h
        now = datetime.now()
        
        def get_change(hours_ago):
            cutoff = now - timedelta(hours=hours_ago)
            past_odds = next((odds for ts, odds in history if ts <= cutoff), None)
            current_odds = history[-1][1]
            
            if past_odds is None:
                return 0
            return abs(current_odds - past_odds)
        
        change_1h = get_change(1) * 10    # Peso maior para mudanças recentes
        change_6h = get_change(6) * 5
        change_24h = get_change(24) * 2
        
        momentum = (change_1h + change_6h + change_24h) / 100
        return min(momentum, 10)  # Cap em 10
```

**Integração com News Signals:**
```python
def calculate_final_score(news_score, momentum_score):
    """
    Combinar score de news com momentum
    """
    base_score = news_score  # 0-100
    
    # Momentum boost
    if momentum_score >= 7:      # Movimento rápido
        boost = 10
    elif momentum_score >= 4:    # Movimento moderado
        boost = 5
    else:                        # Sem movimento
        boost = -5               # Penalizar
    
    final_score = base_score + boost
    return max(0, min(100, final_score))
```

**Adicionar ao Alert:**
```
📊 Odds: 65.0% ➜ 68.5% 📈
🚀 Momentum: ████████░░ (8/10)
   └ Fast movement in last hour
```

### Benefício
- Filtra news que mercado ignora
- Identifica quando há genuine conviction
- Combina fundamental (news) com technical (price action)

---

## 5. Prioridade de Implementação

| Prioridade | Feature | Razão |
|------------|---------|-------|
| 🔴 **Alta** | Filtro de liquidez mínima | Rápido, impacto imediato |
| 🔴 **Alta** | Category specialization whales | Reduz noise significativamente |
| 🟡 **Média** | Momentum tracking | Requer mais integração |
| 🟡 **Média** | Bet timing patterns | Complementa whale analysis |
| 🟢 **Baixa** | Performance tracker | Precisa semanas para ter dados |

---

## 6. Métricas de Sucesso

Após implementação, trackear:

| Métrica | Target | Descrição |
|---------|--------|-----------|
| **Alert Quality** | >60% | % de alerts que são profitable |
| **False Positive Rate** | <10% | % de alerts em mercados ilíquidos |
| **Whale Relevance** | >80% | % de whale alerts com categoria match |
| **Momentum Correlation** | >0.5 | Correlação entre momentum e profit |

---

## 7. Notas Finais

> [!TIP]
> Todas as melhorias são **não-breaking**: podem ser adicionadas sem afetar código existente

> [!IMPORTANT]
> Foco em **reduzir noise** mantendo os sinais fortes

> [!NOTE]
> Sistema já é bom, estas melhorias são **polish** para aumentar edge
