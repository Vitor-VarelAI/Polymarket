"""
ExaSignal - Research Agent (Dexter-inspired)
Agente autónomo multi-fase para investigação profunda de mercados.

Arquitetura:
1. UNDERSTAND → Extrai entidades e intenção
2. PLAN → Decompõe em tarefas de research
3. EXECUTE → Executa cada tarefa com tools (Exa, NewsAPI, etc.)
4. REFLECT → Valida se tem dados suficientes
5. ANSWER → Sintetiza resposta estruturada
"""
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from src.api.groq_client import GroqClient
from src.api.exa_client import ExaClient
from src.api.newsapi_client import NewsAPIClient
from src.api.gamma_client import GammaClient
from src.models.market import Market
from src.utils.logger import logger


@dataclass
class Task:
    """Uma tarefa de investigação."""
    id: str
    description: str
    task_type: str  # "fetch_data" ou "analyze"
    depends_on: List[str] = field(default_factory=list)
    result: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed


@dataclass
class Understanding:
    """Compreensão da query."""
    intent: str
    entities: List[str]
    market_name: str
    time_frame: str
    key_questions: List[str]


@dataclass
class ResearchResult:
    """Resultado final da investigação."""
    market_name: str
    current_odds: Optional[float]
    direction: str  # YES, NO, NEUTRAL
    confidence: int  # 0-100
    summary: str
    key_findings: List[str]
    sources: List[Dict[str, str]]
    reasoning: str


# Prompts do sistema
UNDERSTAND_PROMPT = """You are analyzing a financial research query about prediction markets.

Extract the following from the query:
1. Intent: What does the user want to know?
2. Entities: Key companies, people, technologies mentioned
3. Market Name: The prediction market being analyzed
4. Time Frame: When is this expected to resolve?
5. Key Questions: 2-3 specific questions to research

Query: {query}

Respond in JSON format:
{{
  "intent": "...",
  "entities": ["...", "..."],
  "market_name": "...",
  "time_frame": "...",
  "key_questions": ["...", "...", "..."]
}}"""

PLAN_PROMPT = """You are planning research tasks for a prediction market analysis.

Market: {market_name}
Current Odds: {odds}%
Key Questions: {questions}

Create 3-5 focused research tasks. Each task should be:
- Maximum 8 words
- Either "fetch_data" (needs web search) or "analyze" (needs reasoning)
- "analyze" tasks should depend on "fetch_data" tasks

Respond in JSON:
{{
  "tasks": [
    {{"id": "task_1", "description": "...", "task_type": "fetch_data", "depends_on": []}},
    {{"id": "task_2", "description": "...", "task_type": "fetch_data", "depends_on": []}},
    {{"id": "task_3", "description": "...", "task_type": "analyze", "depends_on": ["task_1", "task_2"]}}
  ]
}}"""

REFLECT_PROMPT = """Evaluate if we have enough data to answer the research question.

Question: {question}
Market: {market_name}
Data Collected:
{data_summary}

Respond in JSON:
{{
  "is_sufficient": true/false,
  "confidence": 0-100,
  "missing": ["what's still needed if insufficient"],
  "direction": "YES" or "NO" or "NEUTRAL"
}}"""

ANSWER_PROMPT = """You are synthesizing research findings into a clear analysis.

Market: {market_name}
Current Odds: {odds}% YES
Research Data:
{research_data}

Create a comprehensive but concise analysis with:
1. A clear YES/NO/NEUTRAL recommendation with confidence
2. 3-4 key findings that support your conclusion
3. Brief reasoning explaining why

Be specific. Cite data. No hedging.

Format your response as:
DIRECTION: [YES/NO/NEUTRAL]
CONFIDENCE: [0-100]

KEY FINDINGS:
• [Finding 1]
• [Finding 2]
• [Finding 3]

REASONING:
[2-3 sentences explaining your conclusion]"""


class ResearchAgent:
    """Agente de investigação multi-fase inspirado no Dexter."""
    
    MAX_ITERATIONS = 3
    
    def __init__(
        self,
        groq: GroqClient,
        exa: ExaClient,
        newsapi: NewsAPIClient = None,
        gamma: GammaClient = None
    ):
        self.groq = groq
        self.exa = exa
        self.newsapi = newsapi
        self.gamma = gamma
        
        if not self.groq.enabled:
            logger.warning("research_agent_no_llm", message="Groq not configured")
    
    async def investigate(self, market: Market) -> ResearchResult:
        """
        Executa investigação completa multi-fase num mercado.
        
        Returns:
            ResearchResult com análise estruturada
        """
        logger.info("research_agent_start", market_id=market.market_id)
        
        # Obter odds atuais
        current_odds = None
        if self.gamma:
            current_odds = await self.gamma.get_market_odds(market.market_id)
        
        # ====================================================================
        # Phase 1: UNDERSTAND
        # ====================================================================
        understanding = await self._understand(market.market_name)
        logger.debug("phase_understand_complete", intent=understanding.intent)
        
        # ====================================================================
        # Phase 2: PLAN
        # ====================================================================
        tasks = await self._plan(
            market.market_name, 
            current_odds, 
            understanding.key_questions
        )
        logger.debug("phase_plan_complete", task_count=len(tasks))
        
        # ====================================================================
        # Phase 3: EXECUTE
        # ====================================================================
        task_results = {}
        sources = []
        
        for task in tasks:
            if task.task_type == "fetch_data":
                result, task_sources = await self._execute_fetch(task, understanding)
                task_results[task.id] = result
                sources.extend(task_sources)
            else:  # analyze
                # Esperar por dependências
                deps_data = {dep: task_results.get(dep, "") for dep in task.depends_on}
                result = await self._execute_analyze(task, deps_data)
                task_results[task.id] = result
        
        logger.debug("phase_execute_complete", results=len(task_results))
        
        # ====================================================================
        # Phase 4: REFLECT
        # ====================================================================
        reflection = await self._reflect(
            understanding.key_questions[0] if understanding.key_questions else market.market_name,
            market.market_name,
            task_results
        )
        logger.debug("phase_reflect_complete", confidence=reflection.get("confidence", 0))
        
        # ====================================================================
        # Phase 5: ANSWER
        # ====================================================================
        answer = await self._answer(market.market_name, current_odds, task_results)
        
        # Parse answer
        result = self._parse_answer(answer, market.market_name, current_odds, sources)
        
        logger.info(
            "research_agent_complete",
            market_id=market.market_id,
            direction=result.direction,
            confidence=result.confidence
        )
        
        return result
    
    async def _understand(self, market_name: str) -> Understanding:
        """Phase 1: Extrai entidades e intenção."""
        # Fallback se Groq não estiver disponível
        if not self.groq or not self.groq.enabled:
            return Understanding(
                intent="Analyze market probability",
                entities=[],
                market_name=market_name,
                time_frame="Unknown",
                key_questions=[f"What is the likelihood of: {market_name}?"]
            )
        
        prompt = UNDERSTAND_PROMPT.format(query=market_name)
        response = await self.groq.quick_prompt(prompt)
        
        # Se não teve resposta, usar fallback
        if not response:
            return Understanding(
                intent="Analyze market probability",
                entities=[],
                market_name=market_name,
                time_frame="Unknown",
                key_questions=[f"What is the likelihood of: {market_name}?"]
            )
        
        try:
            # Limpar resposta para extrair JSON
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1]
                if clean_response.startswith("json"):
                    clean_response = clean_response[4:]
            
            data = json.loads(clean_response)
            return Understanding(
                intent=data.get("intent", "Analyze market probability"),
                entities=data.get("entities", []),
                market_name=data.get("market_name", market_name),
                time_frame=data.get("time_frame", "Unknown"),
                key_questions=data.get("key_questions", [market_name])
            )
        except Exception as e:
            logger.debug("understand_parse_error", error=str(e))
            return Understanding(
                intent="Analyze market probability",
                entities=[],
                market_name=market_name,
                time_frame="Unknown",
                key_questions=[f"What is the likelihood of: {market_name}?"]
            )
    
    async def _plan(
        self, 
        market_name: str, 
        odds: Optional[float],
        questions: List[str]
    ) -> List[Task]:
        """Phase 2: Decompõe em tarefas."""
        prompt = PLAN_PROMPT.format(
            market_name=market_name,
            odds=odds or 50,
            questions=", ".join(questions[:3])
        )
        response = await self.groq.quick_prompt(prompt)
        
        try:
            data = json.loads(response)
            tasks = []
            for t in data.get("tasks", []):
                tasks.append(Task(
                    id=t.get("id", f"task_{len(tasks)}"),
                    description=t.get("description", "Research task"),
                    task_type=t.get("task_type", "fetch_data"),
                    depends_on=t.get("depends_on", [])
                ))
            return tasks
        except:
            # Fallback: tarefas default
            return [
                Task(id="task_1", description="Search recent news", task_type="fetch_data"),
                Task(id="task_2", description="Analyze findings", task_type="analyze", depends_on=["task_1"])
            ]
    
    async def _execute_fetch(
        self, 
        task: Task, 
        understanding: Understanding
    ) -> tuple[str, List[Dict]]:
        """Executa tarefa de fetch de dados."""
        sources = []
        results = []
        
        # Usar Exa para pesquisa
        if self.exa and self.exa.enabled:
            query = f"{understanding.market_name} {task.description}"
            exa_results = await self.exa.search(query, max_results=3)
            
            for r in exa_results:
                sources.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "source": "exa"
                })
                results.append(f"- {r.get('title', '')}: {r.get('excerpt', '')[:200]}")
        
        return "\n".join(results) if results else "No data found", sources
    
    async def _execute_analyze(self, task: Task, deps_data: Dict[str, str]) -> str:
        """Executa tarefa de análise com LLM."""
        data_summary = "\n".join([f"{k}: {v}" for k, v in deps_data.items()])
        
        prompt = f"""Analyze this data for the task: {task.description}

Data:
{data_summary}

Provide a brief analysis (2-3 sentences)."""
        
        return await self.groq.quick_prompt(prompt) or "Analysis unavailable"
    
    async def _reflect(
        self, 
        question: str, 
        market_name: str,
        task_results: Dict[str, str]
    ) -> Dict:
        """Phase 4: Valida se tem dados suficientes."""
        data_summary = "\n".join([f"{k}: {v[:300]}..." for k, v in task_results.items()])
        
        prompt = REFLECT_PROMPT.format(
            question=question,
            market_name=market_name,
            data_summary=data_summary
        )
        response = await self.groq.quick_prompt(prompt)
        
        try:
            return json.loads(response)
        except:
            return {"is_sufficient": True, "confidence": 50, "direction": "NEUTRAL"}
    
    async def _answer(
        self, 
        market_name: str, 
        odds: Optional[float],
        task_results: Dict[str, str]
    ) -> str:
        """Phase 5: Sintetiza resposta final."""
        research_data = "\n\n".join([f"### {k}\n{v}" for k, v in task_results.items()])
        
        prompt = ANSWER_PROMPT.format(
            market_name=market_name,
            odds=odds or 50,
            research_data=research_data
        )
        
        return await self.groq.quick_prompt(prompt) or "Analysis failed"
    
    def _parse_answer(
        self, 
        answer: str, 
        market_name: str,
        odds: Optional[float],
        sources: List[Dict]
    ) -> ResearchResult:
        """Parse da resposta do LLM para ResearchResult."""
        # Extrair componentes
        direction = "NEUTRAL"
        confidence = 50
        key_findings = []
        reasoning = ""
        
        lines = answer.split("\n")
        in_findings = False
        in_reasoning = False
        
        for line in lines:
            line = line.strip()
            if line.startswith("DIRECTION:"):
                direction = line.replace("DIRECTION:", "").strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = int(line.replace("CONFIDENCE:", "").strip())
                except:
                    pass
            elif "KEY FINDINGS" in line:
                in_findings = True
                in_reasoning = False
            elif "REASONING" in line:
                in_findings = False
                in_reasoning = True
            elif in_findings and line.startswith("•"):
                key_findings.append(line[1:].strip())
            elif in_reasoning and line:
                reasoning += line + " "
        
        return ResearchResult(
            market_name=market_name,
            current_odds=odds,
            direction=direction,
            confidence=confidence,
            summary=f"{direction} with {confidence}% confidence",
            key_findings=key_findings[:4],
            sources=sources[:5],
            reasoning=reasoning.strip()
        )
    
    def format_telegram_message(self, result: ResearchResult) -> str:
        """Formata resultado para mensagem Telegram."""
        emoji = "🟢" if result.direction == "YES" else "🔴" if result.direction == "NO" else "⚪"
        odds_str = f"{result.current_odds:.0f}%" if result.current_odds else "N/A"
        
        lines = [
            f"📊 **Análise de Mercado**",
            "",
            f"**{result.market_name}**",
            "",
            f"📈 **Odds Atuais:** {odds_str}",
            f"{emoji} **Direção:** {result.direction}",
            f"🎯 **Confiança:** {result.confidence}/100",
            "",
            "**📋 Key Findings:**"
        ]
        
        for finding in result.key_findings[:3]:
            lines.append(f"• {finding}")
        
        lines.extend([
            "",
            "**💡 Reasoning:**",
            f"_{result.reasoning[:300]}..._" if len(result.reasoning) > 300 else f"_{result.reasoning}_",
            "",
            "**🔗 Sources:**"
        ])
        
        for src in result.sources[:3]:
            lines.append(f"• [{src.get('title', 'Source')[:40]}...]({src.get('url', '')})")
        
        lines.append("")
        lines.append("⚠️ _Análise automatizada, não conselho financeiro._")
        
        return "\n".join(lines)
