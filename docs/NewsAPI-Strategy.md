# Uso da News API (Free Tier) no ExaSignal — Análise e Decisão Técnica

Este documento clarifica **se a limitação de 24h da News API free afeta o produto**, e **como desenhar o sistema corretamente** para evitar problemas de edge, qualidade e coerência estratégica.

---

## 1. Pergunta Central

> A limitação de notícias com ~24h de atraso e 100 requests/dia da News API free compromete o research do ExaSignal?

**Resposta curta:**  
❌ Não compromete o MVP.  
✅ É compatível com o tipo de sinal que o ExaSignal produz.

---

## 2. Natureza do ExaSignal (Ponto-chave)

O ExaSignal **não é um sistema de breaking news**.

É um sistema de:
- Validação de convicção informacional
- Confirmação de narrativa
- Avaliação de consenso recente

Horizonte implícito:
- **Dias / semanas**
- Não minutos ou horas

> Whale move é o trigger.  
> Research serve para validar razões, não velocidade.

---

## 3. O Que a News API Free Limita (e o que não)

### Limitações reais
- Notícias não são do próprio dia (≈24h de atraso)
- Máx. 100 requests/dia

### O que NÃO é afetado
- Entrevistas
- Análises
- Opiniões de researchers
- Artigos técnicos
- Narrativas e consensos recentes

👉 Estes são exatamente os sinais relevantes para mercados AI / frontier tech.

---

## 4. Onde Isto Seria um Problema (fora do escopo)

A limitação seria crítica se o produto fosse:
- Trading reativo a breaking news
- Eventos binários imediatos
- Arbitragem informacional de curto prazo

⚠️ Estes casos **já estão fora do escopo do ExaSignal**.

---

## 5. Estratégia Correta de Uso da News API

### 5.1 Regra de Ouro

> **A notícia nunca é o trigger.  
O trigger é sempre o movimento do whale.**

Pipeline correto:
1. Whale move detectado
2. Sistema pergunta:  
   "Existe base informacional recente que sustente isto?"
3. News API entra apenas como **contexto adicional**

---

### 5.2 Hierarquia de Fontes (Obrigatória)

1. **Exa semantic search** (fonte principal)
2. Blogs, entrevistas, posts técnicos
3. **News API (free)** como camada auxiliar

A News API:
- Nunca decide sozinha
- Nunca gera alerta direta
- Apenas reforça ou enfraquece o score

---

## 6. Ajuste Obrigatório no Alignment Score

Quando uma fonte vem da **News API free**:

- Penalizar recência automaticamente  
  (ex: tratar como 8–30 dias, mesmo que seja "ontem")
- Nunca atribuir score máximo de recência
- Usar sobretudo para:
  - Consenso
  - Direcionalidade
  - Confirmação cruzada

Isto torna o sistema honesto e robusto.

---

## 7. Uso Correto da Ideia "Notícia → Exa"

É válido usar uma notícia recente para:
- Gerar uma hipótese
- Disparar uma pesquisa semântica no Exa

Mas:
- ❌ Nunca gerar alerta só com base na notícia
- ❌ Nunca tratar notícia como sinal primário

Forma correta:
- Notícia identifica tópico → Exa valida profundidade
