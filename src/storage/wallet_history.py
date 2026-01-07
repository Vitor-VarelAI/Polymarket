"""
ExaSignal - Persistência do Histórico de Wallets
Evita perder histórico quando o sistema reinicia.
"""
import aiosqlite
from datetime import datetime, timedelta
from typing import Dict, Optional, Set

from src.utils.config import Config
from src.utils.logger import logger


class WalletHistory:
    """Persiste histórico de wallets em SQLite."""
    
    def __init__(self, db_path: str = None):
        """Inicializa wallet history."""
        self.db_path = db_path or Config.DATABASE_PATH
        self._initialized = False
    
    async def init_db(self):
        """Inicializa tabela de histórico."""
        if self._initialized:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS wallet_history (
                    wallet_address TEXT,
                    market_id TEXT,
                    last_seen TIMESTAMP,
                    trade_count INTEGER DEFAULT 1,
                    PRIMARY KEY (wallet_address, market_id)
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_wallet_market 
                ON wallet_history(market_id, last_seen)
            """)
            await db.commit()
        
        self._initialized = True
    
    async def get_last_seen(self, wallet: str, market_id: str) -> Optional[datetime]:
        """Obtém última vez que wallet fez trade neste mercado."""
        await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT last_seen FROM wallet_history WHERE wallet_address = ? AND market_id = ?",
                (wallet, market_id)
            )
            row = await cursor.fetchone()
            
            if row:
                return datetime.fromisoformat(row[0])
        
        return None
    
    async def update_wallet(self, wallet: str, market_id: str):
        """Atualiza ou cria registo de wallet."""
        await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO wallet_history (wallet_address, market_id, last_seen, trade_count)
                   VALUES (?, ?, ?, 1)
                   ON CONFLICT(wallet_address, market_id) DO UPDATE SET 
                   last_seen = ?,
                   trade_count = trade_count + 1""",
                (wallet, market_id, datetime.now().isoformat(), datetime.now().isoformat())
            )
            await db.commit()
    
    async def is_wallet_inactive(
        self, 
        wallet: str, 
        market_id: str, 
        inactivity_days: int = 14
    ) -> bool:
        """Verifica se wallet está inativa há X dias neste mercado."""
        last_seen = await self.get_last_seen(wallet, market_id)
        
        if not last_seen:
            return True  # Nunca visto = inativo
        
        days_inactive = (datetime.now() - last_seen).days
        return days_inactive >= inactivity_days
    
    async def get_wallet_age_days(self, wallet: str, market_id: str) -> int:
        """Retorna dias desde última atividade."""
        last_seen = await self.get_last_seen(wallet, market_id)
        
        if not last_seen:
            return 0
        
        return (datetime.now() - last_seen).days
    
    async def cleanup_old_records(self, days: int = 90):
        """Remove registos mais antigos que X dias."""
        await self.init_db()
        
        cutoff = datetime.now() - timedelta(days=days)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM wallet_history WHERE last_seen < ?",
                (cutoff.isoformat(),)
            )
            deleted = cursor.rowcount
            await db.commit()
        
        if deleted:
            logger.info("wallet_history_cleanup", deleted=deleted)
