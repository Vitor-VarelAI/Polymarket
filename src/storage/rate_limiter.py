"""
ExaSignal - Rate Limiter Persistido
Baseado em PRD-05-Alert-Generation

Regras:
- Máximo 2 alertas/dia (global)
- Cooldown 24h por mercado
"""
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, Tuple

from src.utils.config import Config
from src.utils.logger import logger


class RateLimiter:
    """Rate limiter persistido em SQLite."""
    
    def __init__(self, db_path: str = None):
        """Inicializa rate limiter."""
        self.db_path = db_path or Config.DATABASE_PATH
        self._initialized = False
    
    async def init_db(self):
        """Inicializa tabelas do banco de dados."""
        if self._initialized:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS alerts_sent (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT NOT NULL,
                    alert_id TEXT UNIQUE,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_market 
                ON alerts_sent(market_id, sent_at)
            """)
            await db.commit()
        
        self._initialized = True
        logger.info("rate_limiter_initialized", db_path=self.db_path)
    
    async def can_send_alert(self, market_id: str) -> Tuple[bool, str]:
        """
        Verifica se pode enviar alerta.
        Retorna (can_send, reason).
        """
        await self.init_db()
        
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        cooldown_cutoff = now - timedelta(hours=Config.COOLDOWN_HOURS)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Verificar limite global diário
            cursor = await db.execute(
                "SELECT COUNT(*) FROM alerts_sent WHERE sent_at >= ?",
                (today_start.isoformat(),)
            )
            row = await cursor.fetchone()
            daily_count = row[0] if row else 0
            
            if daily_count >= Config.MAX_ALERTS_PER_DAY:
                return False, f"Limite diário atingido ({daily_count}/{Config.MAX_ALERTS_PER_DAY})"
            
            # Verificar cooldown do mercado
            cursor = await db.execute(
                "SELECT sent_at FROM alerts_sent WHERE market_id = ? ORDER BY sent_at DESC LIMIT 1",
                (market_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                last_sent = datetime.fromisoformat(row[0])
                if last_sent > cooldown_cutoff:
                    hours_remaining = (last_sent + timedelta(hours=Config.COOLDOWN_HOURS) - now).total_seconds() / 3600
                    return False, f"Cooldown ativo ({hours_remaining:.1f}h restantes)"
        
        return True, "OK"
    
    async def record_alert(self, market_id: str, alert_id: str) -> bool:
        """Registra alerta enviado."""
        await self.init_db()
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO alerts_sent (market_id, alert_id, sent_at) VALUES (?, ?, ?)",
                    (market_id, alert_id, datetime.now().isoformat())
                )
                await db.commit()
            
            logger.info("alert_recorded", market_id=market_id, alert_id=alert_id)
            return True
        except Exception as e:
            logger.error("alert_record_error", error=str(e))
            return False
    
    async def get_daily_count(self) -> int:
        """Retorna quantidade de alertas enviados hoje."""
        await self.init_db()
        
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM alerts_sent WHERE sent_at >= ?",
                (today_start.isoformat(),)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0
