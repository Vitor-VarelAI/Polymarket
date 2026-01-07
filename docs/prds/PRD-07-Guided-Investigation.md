# PRD — Guided Investigation Feature (Telegram Bot)

## Produto
**Nome:** ExaSignal  
**Funcionalidade:** Guided Investigation (Investigação Guiada via Bot)  
**Versão:** MVP v0  
**Canal:** Telegram (privado)

---

## 1. Objetivo da Funcionalidade

Permitir que utilizadores **investiguem contextos relevantes** (mercados, narrativas ou movimentos recentes)  
**sem transformar o ExaSignal num motor genérico de research**  
e **sem revelar o método interno**.

A investigação:
- ❌ Não gera alertas
- ❌ Não recomenda apostas
- ❌ Não expõe o scoring completo
- ✅ Reforça confiança, contexto e retenção

---

## 2. Princípios de Design (Não Negociáveis)

1. **Investigação ≠ Sinal**
2. **Escolhas fechadas, nunca input livre**
3. **Menos detalhe que o pipeline automático**
4. **Sempre marcada como "Not an Alert"**
5. **Rate-limited e premium-only**

> O bot responde perguntas que reforçam o produto,  
> não perguntas que substituem o produto.

---

## 3. Escopo do MVP

### Incluído
- Comando `/investigate`
- Menu guiado com opções fechadas
- Research resumido (snapshot)
- Execução on-demand
- Resposta privada ao utilizador

### Excluído
- Texto livre ("investiga X")
- Geração de sinais
- Probabilidades explícitas
- Odds recomendadas
- Execução automática

---

## 4. UX / Fluxos

### Comando Principal
`/investigate`

**Menu:**
1️⃣ Um mercado específico
2️⃣ Um movimento recente
3️⃣ Uma narrativa geral (AI / Tech)

### Fluxo 1 — Mercado Específico
1. `/investigate`
2. Escolher mercado (lista fechada dos Top 5)
3. Escolher direção (YES / NO / Ambos)
4. → Executa research
5. → Responde snapshot

**Exemplo de Output:**
```
🔬 Research Snapshot — Not an Alert

Market: Best AI Model by End of 2025

Resumo:
• Narrativa bullish mantém-se dominante
• Nenhuma fonte forte recente em sentido contrário
• Odds atuais ainda não refletem consenso técnico

Nota: Isto é contexto, não uma recomendação.
```

### Fluxo 2 — Movimento Recente
1. `/investigate`
2. "Investigar último whale event?"
3. → Sim
4. → Explicação detalhada do evento anterior (se houver)

### Fluxo 3 — Narrativa Geral
1. `/investigate`
2. "Estado atual da narrativa AI / Tech"
3. → 3-5 bullets neutros sobre o setor

---

## 5. Limites Obrigatórios

### Rate Limiting
- Máx **1–2 investigações / dia / utilizador**
- Apenas utilizadores premium (simulado no MVP)

### Profundidade
- Menos fontes que alertas automáticos
- Resumos mais vagos
- Sem alignment score explícito

---

## 6. Regras de Conteúdo (Importante)

O bot **nunca** deve responder a:
- "Vale a pena apostar?"
- "Qual a probabilidade?"
- "O que devo comprar?"

### Flags internas
- `investigation_mode = true`
- `alert_mode = false`

---

## 8. Critérios de Sucesso

A funcionalidade é bem-sucedida se:
- Não aumentar número de alertas
- Aumentar retenção
- Não gerar confusão entre "investigar" e "apostar"

---

## Regra Final

> **Investigação guiada serve para dar contexto.  
Alertas existem para decisão.**

Misturar os dois destrói o produto.
