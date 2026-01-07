"""
ExaSignal - Gestão de Utilizadores (SQLite)
Baseado em PRD-06-Telegram-Bot
"""
import aiosqlite
from datetime import datetime
from typing import List, Optional

from src.models.user import User
from src.utils.config import Config
from src.utils.logger import logger


class UserDB:
    """Gestão de utilizadores em SQLite."""
    
    def __init__(self, db_path: str = None):
        """Inicializa user database."""
        self.db_path = db_path or Config.DATABASE_PATH
        self._initialized = False
    
    async def init_db(self):
        """Inicializa tabela de utilizadores."""
        if self._initialized:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    score_threshold INTEGER DEFAULT 70,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            try:
                # Migração: Tentar adicionar colunas novas se não existirem
                await db.execute("ALTER TABLE users ADD COLUMN investigations_today INTEGER DEFAULT 0")
                await db.execute("ALTER TABLE users ADD COLUMN last_investigation_date TEXT")
            except Exception:
                pass  # Colunas já existem
                
            await db.commit()
        
        self._initialized = True
    
    async def get_or_create(self, user_id: int, username: str = None, first_name: str = None) -> User:
        """Obtém ou cria utilizador."""
        await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            
            if row:
                # Atualizar last_active e resetar investigations se dia mudou
                today = datetime.now().strftime("%Y-%m-%d")
                
                # Check se precisa resetar contador diário
                # row[0]=id, [1]=user, [2]=first, [3]=active, [4]=thresh, [5]=created, [6]=last_active
                # [7]=investigations_today, [8]=last_investigation_date (se existirem)
                
                # Para evitar complexidade de índices flutuantes, vamos resetar na leitura se necessário
                # Mas para manter performance, fazemos isso no check_quota
                
                await db.execute(
                    "UPDATE users SET last_active = ? WHERE user_id = ?",
                    (datetime.now().isoformat(), user_id)
                )
                await db.commit()
                
                # Como adicionamos colunas depois, row pode não ter todos os campos se não fizermos SELECT * again
                # Mas sqlite retorna None para novas colunas em SELECT *
                
                investigations_today = row[7] if len(row) > 7 else 0
                last_inv_date = row[8] if len(row) > 8 else None
                
                return User(
                    user_id=row[0],
                    username=row[1],
                    first_name=row[2],
                    is_active=bool(row[3]),
                    score_threshold=row[4],
                    investigations_today=investigations_today,
                    last_investigation_date=last_inv_date
                )
            
            # Criar novo utilizador
            await db.execute(
                """INSERT INTO users (user_id, username, first_name, investigations_today, last_investigation_date) 
                   VALUES (?, ?, ?, 0, NULL)""",
                (user_id, username, first_name)
            )
            await db.commit()
            
            logger.info("new_user_created", user_id=user_id, username=username)
            return User(user_id=user_id, username=username, first_name=first_name)
    
    async def check_investigation_quota(self, user_id: int, max_daily: int = 10) -> bool:
        """
        Verifica se utilizador pode investigar. 
        Reseta contador se for novo dia.
        """
        await self.init_db()
        today = datetime.now().strftime("%Y-%m-%d")
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT investigations_today, last_investigation_date FROM users WHERE user_id = ?", 
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return False
                
            count = row[0] or 0
            last_date = row[1]
            
            # Resetar se dia mudou
            if last_date != today:
                await db.execute(
                    "UPDATE users SET investigations_today = 0, last_investigation_date = ? WHERE user_id = ?",
                    (today, user_id)
                )
                await db.commit()
                return True
            
            # Verificar limite
            return count < max_daily

    async def increment_investigation(self, user_id: int):
        """Incrementa contador de investigações."""
        await self.init_db()
        today = datetime.now().strftime("%Y-%m-%d")
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE users 
                   SET investigations_today = investigations_today + 1, 
                       last_investigation_date = ? 
                   WHERE user_id = ?""",
                (today, user_id)
            )
            await db.commit()
    
    async def get_active_users(self) -> List[User]:
        """Retorna todos os utilizadores ativos."""
        await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM users WHERE is_active = 1")
            rows = await cursor.fetchall()
            
            return [
                User(
                    user_id=row[0],
                    username=row[1],
                    first_name=row[2],
                    is_active=bool(row[3]),
                    score_threshold=row[4]
                )
                for row in rows
            ]
    
    async def update_threshold(self, user_id: int, threshold: int) -> bool:
        """Atualiza threshold do utilizador."""
        await self.init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET score_threshold = ? WHERE user_id = ?",
                (threshold, user_id)
            )
            await db.commit()
        
        return True
