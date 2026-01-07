"""
ExaSignal - Cache de Pesquisa e Quota Tracking
Guardrails para NewsAPI:
- Máx 3 requests por whale event
- Máx 1 scan geral / dia
- Cache de 24h por keyword
- Se quota <20% → desligar silenciosamente

Regra final:
"Se precisares de chamar a News API muitas vezes,
o problema não é a quota — é o design do produto."
"""
import aiosqlite
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.utils.config import Config
from src.utils.logger import logger


class ResearchCache:
    """Cache de pesquisas com quota tracking para NewsAPI."""
    
    # Configurações de quota
    NEWSAPI_DAILY_LIMIT = 100
    NEWSAPI_MIN_QUOTA_PERCENT = 20  # Desligar se <20%
    MAX_REQUESTS_PER_EVENT = 3
    CACHE_TTL_HOURS = 24
    
    def __init__(self, db_path: str = None):
        """Inicializa cache."""
        self.db_path = db_path or Config.DATABASE_PATH
        self._initialized = False
    
    async def init_db(self):
        """Inicializa tabelas de cache."""
        if self._initialized:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            # Cache de resultados
            await db.execute("""
                CREATE TABLE IF NOT EXISTS research_cache (
                    cache_key TEXT PRIMARY KEY,
                    results TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tracking de quota NewsAPI
            await db.execute("""
                CREATE TABLE IF NOT EXISTS newsapi_quota (
                    date TEXT PRIMARY KEY,
                    requests_count INTEGER DEFAULT 0,
                    last_request TIMESTAMP
                )
            """)
            
            # Tracking de requests por evento
            await db.execute("""
                CREATE TABLE IF NOT EXISTS event_requests (
                    event_id TEXT,
                    source TEXT,
                    request_count INTEGER DEFAULT 0,
                    PRIMARY KEY (event_id, source)
                )
            """)
            
            await db.commit()
        
        self._initialized = True
    
    async def get_cached(self, query: str, source: str) -> Optional[List[Dict]]:
        """Obtém resultados em cache se ainda válidos (24h)."""
        await self.init_db()
        
        cache_key = self._make_key(query, source)
        cutoff = datetime.now() - timedelta(hours=self.CACHE_TTL_HOURS)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT results FROM research_cache WHERE cache_key = ? AND created_at > ?",
                (cache_key, cutoff.isoformat())
            )
            row = await cursor.fetchone()
            
            if row:
                logger.debug("cache_hit", query=query[:30], source=source)
                return json.loads(row[0])
        
        return None
    
    async def set_cached(self, query: str, source: str, results: List[Dict]):
        """Guarda resultados em cache."""
        await self.init_db()
        
        cache_key = self._make_key(query, source)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO research_cache (cache_key, results, source, created_at)
                   VALUES (?, ?, ?, ?)""",
                (cache_key, json.dumps(results), source, datetime.now().isoformat())
            )
            await db.commit()
    
    async def can_use_newsapi(self) -> Tuple[bool, str]:
        """
        Verifica se pode usar NewsAPI.
        Retorna (can_use, reason).
        """
        await self.init_db()
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT requests_count FROM newsapi_quota WHERE date = ?",
                (today,)
            )
            row = await cursor.fetchone()
            
            count = row[0] if row else 0
            remaining = self.NEWSAPI_DAILY_LIMIT - count
            percent_remaining = (remaining / self.NEWSAPI_DAILY_LIMIT) * 100
            
            if percent_remaining < self.NEWSAPI_MIN_QUOTA_PERCENT:
                logger.warning(
                    "newsapi_disabled_low_quota",
                    remaining=remaining,
                    percent=percent_remaining
                )
                return False, f"Quota baixa ({remaining} restantes)"
        
        return True, "OK"
    
    async def record_newsapi_request(self):
        """Regista um request à NewsAPI."""
        await self.init_db()
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO newsapi_quota (date, requests_count, last_request)
                   VALUES (?, 1, ?)
                   ON CONFLICT(date) DO UPDATE SET 
                   requests_count = requests_count + 1,
                   last_request = ?""",
                (today, datetime.now().isoformat(), datetime.now().isoformat())
            )
            await db.commit()
    
    async def can_request_for_event(self, event_id: str, source: str = "newsapi") -> bool:
        """Verifica se pode fazer mais requests para este evento (máx 3)."""
        await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT request_count FROM event_requests WHERE event_id = ? AND source = ?",
                (event_id, source)
            )
            row = await cursor.fetchone()
            
            count = row[0] if row else 0
            return count < self.MAX_REQUESTS_PER_EVENT
    
    async def record_event_request(self, event_id: str, source: str = "newsapi"):
        """Regista request para um evento."""
        await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO event_requests (event_id, source, request_count)
                   VALUES (?, ?, 1)
                   ON CONFLICT(event_id, source) DO UPDATE SET 
                   request_count = request_count + 1""",
                (event_id, source)
            )
            await db.commit()
    
    async def get_newsapi_status(self) -> Dict[str, Any]:
        """Retorna status atual da quota NewsAPI."""
        await self.init_db()
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT requests_count FROM newsapi_quota WHERE date = ?",
                (today,)
            )
            row = await cursor.fetchone()
            
            count = row[0] if row else 0
            remaining = self.NEWSAPI_DAILY_LIMIT - count
            
            return {
                "used": count,
                "remaining": remaining,
                "limit": self.NEWSAPI_DAILY_LIMIT,
                "percent_remaining": (remaining / self.NEWSAPI_DAILY_LIMIT) * 100,
                "enabled": remaining > (self.NEWSAPI_DAILY_LIMIT * self.NEWSAPI_MIN_QUOTA_PERCENT / 100)
            }
    
    def _make_key(self, query: str, source: str) -> str:
        """Cria chave de cache única."""
        content = f"{source}:{query.lower().strip()}"
        return hashlib.md5(content.encode()).hexdigest()
