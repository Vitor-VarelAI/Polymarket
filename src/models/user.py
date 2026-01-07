"""
ExaSignal - Modelo de Utilizador
Baseado em PRD-06-Telegram-Bot
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class User:
    """Representa um utilizador do bot Telegram."""
    
    user_id: int  # Telegram user ID
    username: Optional[str] = None
    first_name: Optional[str] = None
    is_active: bool = True
    score_threshold: int = 70  # Configurável pelo utilizador
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    investigations_today: int = 0
    last_investigation_date: Optional[str] = None  # YYYY-MM-DD
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "first_name": self.first_name,
            "is_active": self.is_active,
            "score_threshold": self.score_threshold,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "investigations_today": self.investigations_today,
            "last_investigation_date": self.last_investigation_date
        }
    
    @property
    def display_name(self) -> str:
        """Nome para exibição."""
        if self.first_name:
            return self.first_name
        if self.username:
            return f"@{self.username}"
        return f"User {self.user_id}"
