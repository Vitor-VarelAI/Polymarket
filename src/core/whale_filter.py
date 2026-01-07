"""
ExaSignal - Filtro de Whales Não-Informacionais
Baseado em PRD-02b-Whale-Exclusion-Filters

Regra de Ouro:
"Se o edge não depende de saber algo que o mercado ainda não precificou, não é sinal."

Extended with:
- Category relevance filtering: Whale specialty vs market category match
- One-sided trader detection: Whales that only bet YES or NO
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, TYPE_CHECKING
from dataclasses import dataclass, field

from src.utils.logger import logger

if TYPE_CHECKING:
    from src.models.whale_event import WhaleProfile


@dataclass
class TraderStats:
    """Estatísticas de um trader para classificação."""
    wallet_address: str
    total_trades_30d: int = 0
    trades_today: int = 0
    has_yes_and_no: bool = False  # Comprou YES e NO no mesmo mercado
    avg_holding_minutes: float = 0.0
    markets_traded: Set[str] = field(default_factory=set)
    is_excluded: bool = False
    exclusion_reason: Optional[str] = None


class WhaleFilter:
    """
    Filtra traders não-informacionais (arbitragem/HFT).
    
    Extended with category relevance filtering.
    """
    
    # Thresholds de exclusão
    MAX_TRADES_PER_DAY = 50
    MAX_TRADES_30_DAYS = 500
    MIN_HOLDING_MINUTES = 15
    
    # Padrões de mercado a excluir
    EXCLUDED_MARKET_PATTERNS = [
        "up/down",
        "up or down",
        "above",
        "below",
        "price",
    ]
    
    def __init__(self):
        """Inicializa filtro."""
        # Cache de traders já analisados: {wallet: TraderStats}
        self._trader_cache: Dict[str, TraderStats] = {}
        # Wallets na blacklist
        self._blacklist: Set[str] = set()
    
    def is_excluded(self, wallet: str, trades: List[Dict] = None) -> tuple[bool, str]:
        """
        Verifica se wallet deve ser excluída.
        Retorna (is_excluded, reason).
        """
        # Verificar blacklist primeiro
        if wallet in self._blacklist:
            return True, "blacklisted"
        
        # Verificar cache
        if wallet in self._trader_cache:
            stats = self._trader_cache[wallet]
            if stats.is_excluded:
                return True, stats.exclusion_reason
        
        # Se não há trades para analisar, não excluir
        if not trades:
            return False, ""
        
        # Analisar trades
        stats = self._analyze_trades(wallet, trades)
        
        # Aplicar regras de exclusão
        excluded, reason = self._apply_exclusion_rules(stats)
        
        # Guardar resultado
        stats.is_excluded = excluded
        stats.exclusion_reason = reason
        self._trader_cache[wallet] = stats
        
        if excluded:
            self._blacklist.add(wallet)
            logger.info(
                "whale_excluded",
                wallet=wallet[:10] + "...",
                reason=reason
            )
        
        return excluded, reason
    
    def is_relevant_for_market(
        self,
        whale_profile: "WhaleProfile",
        market_category: str
    ) -> tuple[bool, str]:
        """
        Check if whale is relevant for this specific market category.
        
        Uses WhaleProfile.is_relevant_for_category() but adds additional logic:
        - One-sided traders get lower priority
        - Specialty mismatch gets warning but not exclusion
        
        Returns:
            (is_relevant, reason_if_not)
        """
        if whale_profile is None:
            return True, ""  # No profile = benefit of doubt
        
        # Check one-sided trading (always YES or always NO)
        if whale_profile.is_one_sided:
            bias_dir = "YES" if whale_profile.directional_bias_score > 0 else "NO"
            logger.info(
                "whale_one_sided",
                wallet=whale_profile.wallet_address[:10],
                bias=bias_dir,
                bias_score=whale_profile.directional_bias_score
            )
            # Don't exclude, but flag it
            # The whale alert will show warning in Telegram
        
        # Check category relevance
        if not whale_profile.is_relevant_for_category(market_category):
            specialty = whale_profile.specialty_category
            logger.info(
                "whale_category_mismatch",
                wallet=whale_profile.wallet_address[:10],
                specialty=specialty,
                market_category=market_category
            )
            return False, f"specialty_mismatch:{specialty}!={market_category}"
        
        return True, ""
    
    def _analyze_trades(self, wallet: str, trades: List[Dict]) -> TraderStats:
        """Analisa trades de um wallet."""
        stats = TraderStats(wallet_address=wallet)
        
        now = datetime.now()
        today = now.date()
        thirty_days_ago = now - timedelta(days=30)
        
        sides_seen = set()  # Para detectar YES + NO
        holding_times = []
        
        for trade in trades:
            trade_time = trade.get("timestamp")
            if isinstance(trade_time, str):
                try:
                    trade_time = datetime.fromisoformat(trade_time.replace("Z", "+00:00"))
                except:
                    trade_time = now
            
            # Contar trades nos últimos 30 dias
            if trade_time and trade_time > thirty_days_ago:
                stats.total_trades_30d += 1
            
            # Contar trades hoje
            if trade_time and trade_time.date() == today:
                stats.trades_today += 1
            
            # Detectar YES + NO
            side = trade.get("side", "").upper()
            if side in ["BUY", "SELL", "YES", "NO"]:
                sides_seen.add(side)
            
            # Guardar mercado
            market = trade.get("market_id") or trade.get("token_id")
            if market:
                stats.markets_traded.add(market)
        
        # YES + NO no mesmo mercado?
        stats.has_yes_and_no = len(sides_seen) >= 2
        
        return stats
    
    def _apply_exclusion_rules(self, stats: TraderStats) -> tuple[bool, str]:
        """Aplica regras de exclusão. Retorna (excluded, reason)."""
        
        # Regra 1: >50 trades/dia
        if stats.trades_today > self.MAX_TRADES_PER_DAY:
            return True, f"high_frequency_today:{stats.trades_today}"
        
        # Regra 2: >500 trades em 30 dias
        if stats.total_trades_30d > self.MAX_TRADES_30_DAYS:
            return True, f"high_frequency_30d:{stats.total_trades_30d}"
        
        # Regra 3: Hedging (YES + NO)
        if stats.has_yes_and_no:
            return True, "hedging_detected"
        
        return False, ""
    
    def is_excluded_market(self, market_name: str) -> bool:
        """Verifica se mercado é do tipo a excluir (Up/Down, etc.)."""
        name_lower = market_name.lower()
        for pattern in self.EXCLUDED_MARKET_PATTERNS:
            if pattern in name_lower:
                return True
        return False
    
    def add_to_blacklist(self, wallet: str, reason: str = "manual") -> None:
        """Adiciona wallet à blacklist manualmente."""
        self._blacklist.add(wallet)
        logger.info("wallet_blacklisted", wallet=wallet[:10] + "...", reason=reason)

