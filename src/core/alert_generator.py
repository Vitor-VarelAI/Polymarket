"""
ExaSignal - Alert Generator
Baseado em PRD-05-Alert-Generation

Responsabilidades:
1. Validar se score >= threshold
2. Verificar rate limits
3. Formatar alerta para Telegram
4. Registrar envio
"""
from datetime import datetime
from typing import Optional

from src.models.market import Market
from src.models.whale_event import WhaleEvent
from src.models.score_result import ScoreResult
from src.models.alert import Alert
from src.storage.rate_limiter import RateLimiter
from src.utils.config import Config
from src.utils.logger import logger


class AlertGenerator:
    """Gera alertas formatados com rate limiting."""
    
    def __init__(self, rate_limiter: RateLimiter = None):
        """Inicializa generator com rate limiter."""
        self.rate_limiter = rate_limiter or RateLimiter()
    
    async def generate(
        self,
        market: Market,
        whale_event: WhaleEvent,
        score_result: ScoreResult,
        current_odds: float
    ) -> Optional[Alert]:
        """
        Gera alerta se todas as condições forem satisfeitas.
        Retorna None se bloqueado por rate limit ou score baixo.
        """
        # 1. Verificar score
        if not score_result.should_alert:
            logger.debug(
                "alert_blocked_score",
                market_id=market.market_id,
                score=score_result.total_score
            )
            return None
        
        # 2. Verificar rate limits
        can_send, reason = await self.rate_limiter.can_send_alert(market.market_id)
        if not can_send:
            logger.info(
                "alert_blocked_rate_limit",
                market_id=market.market_id,
                reason=reason
            )
            return None
        
        # 3. Criar alerta
        alert = Alert(
            market_id=market.market_id,
            market_name=market.market_name,
            direction=whale_event.direction,
            size_formatted=whale_event.size_formatted,
            current_odds=current_odds,
            score=score_result.total_score,
            top_reasons=score_result.top_reasons
        )
        
        # 4. Registrar alerta
        await self.rate_limiter.record_alert(market.market_id, alert.alert_id)
        
        logger.info(
            "alert_generated",
            alert_id=alert.alert_id,
            market_id=market.market_id,
            direction=alert.direction,
            score=alert.score
        )
        
        return alert
    
    async def get_status(self) -> dict:
        """Retorna status atual do rate limiter."""
        daily_count = await self.rate_limiter.get_daily_count()
        return {
            "daily_alerts": daily_count,
            "daily_limit": Config.MAX_ALERTS_PER_DAY,
            "remaining": max(0, Config.MAX_ALERTS_PER_DAY - daily_count)
        }
