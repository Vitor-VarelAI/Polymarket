"""
ExaSignal - Configuração e Variáveis de Ambiente
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Carregar .env
load_dotenv()


class Config:
    """Configurações carregadas de variáveis de ambiente."""
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # APIs de Pesquisa
    NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY", "")
    EXA_API_KEY: Optional[str] = os.getenv("EXA_API_KEY")
    USE_EXA_FALLBACK: bool = os.getenv("USE_EXA_FALLBACK", "false").lower() == "true"
    MIN_FREE_RESULTS: int = int(os.getenv("MIN_FREE_RESULTS", "5"))
    
    # Configurações do Sistema
    SCORE_THRESHOLD: float = float(os.getenv("SCORE_THRESHOLD", "70"))
    POLLING_INTERVAL_SECONDS: int = int(os.getenv("POLLING_INTERVAL_SECONDS", "300"))
    MAX_ALERTS_PER_DAY: int = int(os.getenv("MAX_ALERTS_PER_DAY", "2"))
    COOLDOWN_HOURS: int = int(os.getenv("COOLDOWN_HOURS", "24"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "exasignal.db")
    
    @classmethod
    def validate(cls) -> bool:
        """Valida se variáveis obrigatórias estão definidas."""
        errors = []
        
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN não definido")
        if not cls.NEWSAPI_KEY:
            errors.append("NEWSAPI_KEY não definido (obrigatório para pesquisa)")
        
        if errors:
            for error in errors:
                print(f"❌ {error}")
            raise ValueError("Configuração inválida. Verifique o .env")
        
        return True
