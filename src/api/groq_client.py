"""
ExaSignal - Groq LLM Client
Cliente para interação com Groq API (Llama 3.3 70B grátis).
"""
import os
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from groq import Groq

from src.utils.logger import logger

# Garantir que .env está carregado
load_dotenv()


class GroqClient:
    """Cliente para Groq API com Llama 3.3."""
    
    MODEL = "llama-3.3-70b-versatile"  # Modelo grátis e rápido
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.client = None
        self.enabled = False
        
        if self.api_key:
            try:
                self.client = Groq(api_key=self.api_key)
                self.enabled = True
                logger.info("groq_client_initialized", model=self.MODEL)
            except Exception as e:
                logger.error("groq_client_init_error", error=str(e))
    
    async def chat(
        self, 
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> Optional[str]:
        """
        Envia mensagens ao LLM e retorna resposta.
        
        Args:
            messages: Lista de {"role": "system"|"user"|"assistant", "content": "..."}
            temperature: Criatividade (0.0 = determinístico, 1.0 = criativo)
            max_tokens: Limite de tokens na resposta
        """
        if not self.enabled:
            logger.warning("groq_not_enabled")
            return None
        
        try:
            response = self.client.chat.completions.create(
                model=self.MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            content = response.choices[0].message.content
            logger.debug(
                "groq_chat_success",
                tokens_used=response.usage.total_tokens if response.usage else 0
            )
            return content
            
        except Exception as e:
            logger.error("groq_chat_error", error=str(e))
            return None
    
    async def quick_prompt(self, prompt: str, system: str = None) -> Optional[str]:
        """Atalho para prompts simples."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages)
