"""
ExaSignal - Modelo de Alerta
Baseado em PRD-05-Alert-Generation
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Alert:
    """Representa um alerta formatado para Telegram."""
    
    market_id: str
    market_name: str
    direction: str  # "YES" ou "NO"
    direction_emoji: str = ""  # 🟢 ou 🔴
    size_formatted: str = ""  # "$25k"
    current_odds: float = 0.0
    score: float = 0.0
    top_reasons: List[str] = field(default_factory=list)
    polymarket_url: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    alert_id: str = ""
    
    def __post_init__(self):
        """Inicializa campos derivados."""
        if not self.direction_emoji:
            self.direction_emoji = "🟢" if self.direction == "YES" else "🔴"
        if not self.alert_id:
            self.alert_id = f"{self.market_id}_{self.timestamp.strftime('%Y%m%d%H%M%S')}"
        if not self.polymarket_url:
            self.polymarket_url = f"https://polymarket.com/event/{self.market_id}"
    
    def to_telegram_message(self) -> str:
        """Formata alerta para mensagem Telegram."""
        lines = [
            f"{self.direction_emoji} **{self.direction}** | {self.market_name}",
            "",
            f"💰 Whale: {self.size_formatted}",
            f"📊 Odds: {self.current_odds:.0f}%",
            f"🎯 Score: {self.score:.0f}/100",
            "",
            "**Razões:**",
        ]
        
        for reason in self.top_reasons[:2]:
            lines.append(f"• {reason}")
        
        lines.extend([
            "",
            f"[Ver no Polymarket]({self.polymarket_url})"
        ])
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "alert_id": self.alert_id,
            "market_id": self.market_id,
            "market_name": self.market_name,
            "direction": self.direction,
            "size_formatted": self.size_formatted,
            "current_odds": self.current_odds,
            "score": self.score,
            "top_reasons": self.top_reasons,
            "polymarket_url": self.polymarket_url,
            "timestamp": self.timestamp.isoformat()
        }
