# ExaSignal - Princípios de Design

Regras fundamentais que guiam todas as decisões do produto.

---

## Regra Principal

> **"Se precisares de correr 24/7 para o ExaSignal funcionar, o problema não é a infraestrutura — é o design do produto."**

---

## Regras de Produto

### 1. Silêncio > Spam
- Máximo 1-2 alertas por dia
- Se não houver convicção, não há alerta
- Menos sinais, mais clareza

### 2. Convicção > Cobertura
- Não seguir whales cegamente
- Validar com research independente
- Score >= 70 ou silêncio

### 3. Razões > Dinheiro
- Lucro do trader não é sinal
- Se não depende de informação futura, não é sinal
- Arbitragem e HFT são excluídos

---

## Regras Técnicas

### NewsAPI
> "Se precisares de chamar a News API muitas vezes, o problema não é a quota — é o design do produto."

- 2 snapshots por dia (máximo)
- Cache de 24h
- Nunca é trigger, só contexto

### Execução
> "Se precisares de correr 24/7, o problema é o design."

- 3 runs agendados por dia
- Cada run ~5 minutos
- Sem dependência de uptime

### Whales
> "Se o edge não depende de saber algo que o mercado ainda não precificou, não é sinal."

- Filtrar arbitragem/HFT
- Excluir mercados Up/Down
- Wallet inativa >= 14 dias

---

## Hierarquia de Fontes

1. **ArXiv** - Papers acadêmicos (máxima credibilidade)
2. **Exa** - Pesquisa semântica (alta qualidade)
3. **RSS Feeds** - Blogs de labs, tech news
4. **NewsAPI** - Contexto adicional (nunca primário)

---

## Guardar Esta Filosofia

Estas regras existem para manter o ExaSignal diferente de whale trackers genéricos.

Se uma feature viola estes princípios → **não implementar**.
