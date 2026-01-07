"""
ExaSignal - Logging Estruturado com Structlog
"""
import logging
import sys
from typing import Optional

import structlog
from src.utils.config import Config


def setup_logging(log_level: Optional[str] = None) -> structlog.BoundLogger:
    """Configura e retorna logger estruturado."""
    
    level = log_level or Config.LOG_LEVEL
    
    # Configurar logging padrão do Python
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    
    # Configurar structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # Usar JSON em produção, console colorido em dev
            structlog.dev.ConsoleRenderer() if level == "DEBUG" 
                else structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    return structlog.get_logger()


# Logger global
logger = setup_logging()
