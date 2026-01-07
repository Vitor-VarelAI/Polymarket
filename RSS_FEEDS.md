# ExaSignal — Lista de RSS Feeds Recomendados

Lista completa de 15-20 feeds de qualidade para pesquisa sobre AI/frontier tech.

---

## 📰 Tech & AI News (5 feeds)

1. **TechCrunch**
   - URL: `https://techcrunch.com/feed/`
   - Foco: Notícias de tecnologia e startups
   - Qualidade: Alta

2. **The Verge**
   - URL: `https://www.theverge.com/rss/index.xml`
   - Foco: Tech news e reviews
   - Qualidade: Alta

3. **Wired**
   - URL: `https://www.wired.com/feed/rss`
   - Foco: Tech, science, culture
   - Qualidade: Alta

4. **MIT Technology Review**
   - URL: `https://www.technologyreview.com/feed/`
   - Foco: Tech research e inovação
   - Qualidade: Muito Alta

5. **IEEE Spectrum**
   - URL: `https://spectrum.ieee.org/rss`
   - Foco: Engineering e tech avançada
   - Qualidade: Muito Alta

---

## 🤖 AI Research & Labs (5 feeds)

6. **OpenAI Blog**
   - URL: `https://openai.com/blog/rss.xml`
   - Foco: Anúncios e research da OpenAI
   - Qualidade: Muito Alta (fonte autoritária)

7. **DeepMind Blog**
   - URL: `https://deepmind.com/blog/feed/basic/`
   - Foco: Research e breakthroughs da DeepMind
   - Qualidade: Muito Alta (fonte autoritária)

8. **Anthropic Blog**
   - URL: `https://www.anthropic.com/index.xml`
   - Foco: Research e filosofia de AI safety
   - Qualidade: Muito Alta (fonte autoritária)

9. **Google AI Blog**
   - URL: `https://ai.googleblog.com/feeds/posts/default`
   - Foco: Research e produtos de AI do Google
   - Qualidade: Muito Alta (fonte autoritária)

10. **Meta AI Research**
    - URL: `https://ai.meta.com/blog/feed/`
    - Foco: Research de AI do Meta
    - Qualidade: Muito Alta (fonte autoritária)

---

## 📚 Academic & Research (4 feeds)

11. **ArXiv AI (Computer Science - AI)**
    - URL: `http://arxiv.org/rss/cs.AI`
    - Foco: Papers acadêmicos de AI
    - Qualidade: Muito Alta

12. **ArXiv Machine Learning**
    - URL: `http://arxiv.org/rss/cs.LG`
    - Foco: Papers de machine learning
    - Qualidade: Muito Alta

13. **Hacker News AI**
    - URL: `https://hnrss.org/newest?q=AI`
    - Foco: Discussões sobre AI no HN
    - Qualidade: Alta

14. **LessWrong**
    - URL: `https://www.lesswrong.com/feed.xml`
    - Foco: Discussões sobre AGI e AI safety
    - Qualidade: Alta (comunidade técnica)

---

## 💼 Industry Analysis (2-3 feeds)

15. **VentureBeat AI**
    - URL: `https://venturebeat.com/ai/feed/`
    - Foco: Business e AI industry
    - Qualidade: Alta

16. **AI News**
    - URL: `https://www.artificialintelligence-news.com/feed/`
    - Foco: Notícias específicas de AI
    - Qualidade: Média-Alta

17. **The Information** (Opcional - pode requerer acesso)
    - URL: `https://www.theinformation.com/feed`
    - Foco: Tech industry insights
    - Qualidade: Muito Alta (se tiver acesso)

---

## 📋 Lista Completa para Código

```python
RSS_FEEDS = [
    # Tech & AI News
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://www.wired.com/feed/rss",
    "https://www.technologyreview.com/feed/",
    "https://spectrum.ieee.org/rss",
    
    # AI Research & Labs
    "https://openai.com/blog/rss.xml",
    "https://deepmind.com/blog/feed/basic/",
    "https://www.anthropic.com/index.xml",
    "https://ai.googleblog.com/feeds/posts/default",
    "https://ai.meta.com/blog/feed/",
    
    # Academic & Research
    "http://arxiv.org/rss/cs.AI",
    "http://arxiv.org/rss/cs.LG",
    "https://hnrss.org/newest?q=AI",
    "https://www.lesswrong.com/feed.xml",
    
    # Industry Analysis
    "https://venturebeat.com/ai/feed/",
    "https://www.artificialintelligence-news.com/feed/",
    # "https://www.theinformation.com/feed",  # Opcional
]
```

**Total: 16-17 feeds de qualidade**

---

## 🔧 Implementação

Ver exemplo completo em `COST_OPTIMIZATION.md` - Seção 2 (RSS Feeds Expandidos).

---

## 📝 Notas

- **Prioridade:** Feeds de labs (OpenAI, DeepMind, etc.) têm maior autoridade
- **Frequência:** Verificar feeds diariamente ou a cada pesquisa
- **Cache:** Cachear resultados por 2-4 horas
- **Fallback:** Se feed estiver offline, pular e continuar com outros

---

## 🔄 Manutenção

- Verificar feeds mensalmente
- Remover feeds que pararam de atualizar
- Adicionar novos feeds de qualidade quando disponíveis
- Monitorar taxa de sucesso de cada feed

