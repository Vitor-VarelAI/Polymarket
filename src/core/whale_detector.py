"""
ExaSignal - Detector de Eventos Whale
Baseado em PRD-02-Whale-Event-Detection e PRD-02b-Whale-Exclusion-Filters

Regras de detecção (TODAS devem ser verdade):
1. Nova posição (não top-up)
2. Size >= max($10k, 2% da liquidez)
3. Wallet inativa >= 14 dias nesse mercado
4. Exposição direcional (sem hedge)
5. Wallet NÃO é arbitragem/HFT (filtro de exclusão)

Regra de Ouro:
"Se o edge não depende de saber algo que o mercado ainda não precificou, não é sinal."
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.api.gamma_client import GammaClient
from src.api.clob_client import CLOBClient
from src.core.market_manager import MarketManager
from src.core.whale_filter import WhaleFilter
from src.storage.wallet_history import WalletHistory
from src.models.whale_event import WhaleEvent
from src.utils.logger import logger
from src.utils.config import Config


class WhaleDetector:
    """Detecta eventos de whale baseado em comportamento."""
    
    # Configurações
    MIN_SIZE_USD = 10_000  # Mínimo $10k
    LIQUIDITY_PERCENT = 0.02  # 2% da liquidez
    INACTIVITY_DAYS = 14  # Dias de inatividade
    
    def __init__(
        self,
        market_manager: MarketManager,
        gamma_client: GammaClient,
        clob_client: CLOBClient,
        whale_filter: WhaleFilter = None,
        wallet_history: WalletHistory = None
    ):
        """Inicializa detector com dependências."""
        self.market_manager = market_manager
        self.gamma = gamma_client
        self.clob = clob_client
        self.whale_filter = whale_filter or WhaleFilter()
        self.wallet_history = wallet_history or WalletHistory()
    
    async def check_market(self, market_id: str) -> List[WhaleEvent]:
        """Verifica um mercado e retorna eventos whale detectados."""
        events = []
        
        # Verificar se mercado é válido
        market = self.market_manager.get_market_by_id(market_id)
        if not market:
            logger.warning("invalid_market", market_id=market_id)
            return events
        
        # [NOVO] Excluir mercados Up/Down
        if self.whale_filter.is_excluded_market(market.market_name):
            logger.debug("market_excluded", market_id=market_id, reason="up_down_market")
            return events
        
        # Obter liquidez do mercado
        liquidity = await self.gamma.get_market_liquidity(market_id)
        if not liquidity:
            logger.warning("no_liquidity_data", market_id=market_id)
            return events
        
        # Calcular threshold
        threshold = max(self.MIN_SIZE_USD, liquidity * self.LIQUIDITY_PERCENT)
        
        # Buscar trades grandes
        large_trades = await self.clob.get_large_trades(
            token_id=market_id,
            min_size_usd=threshold
        )
        
        # Avaliar cada trade
        for trade in large_trades:
            event = await self._evaluate_trade(trade, market_id, liquidity, threshold)
            if event:
                events.append(event)
        
        if events:
            logger.info(
                "whale_events_detected",
                market_id=market_id,
                count=len(events)
            )
        
        return events
    
    async def _evaluate_trade(
        self,
        trade: Dict,
        market_id: str,
        liquidity: float,
        threshold: float
    ) -> Optional[WhaleEvent]:
        """Avalia se um trade é um evento whale válido."""
        wallet = trade.get("maker") or trade.get("taker", "unknown")
        size_usd = trade.get("size_usd", 0)
        
        # [NOVO] Regra 0: Verificar se wallet é excluída (arbitragem/HFT)
        is_excluded, reason = self.whale_filter.is_excluded(wallet)
        if is_excluded:
            logger.debug("wallet_excluded", wallet=wallet[:10] + "...", reason=reason)
            return None
        
        # Regra 1: Size >= threshold (já filtrado, mas verificar)
        if size_usd < threshold:
            return None
        
        # Regra 2: Wallet inativa >= 14 dias
        if not await self._is_wallet_inactive(wallet, market_id):
            return None
        
        # Regra 3: Nova posição (simplificado - verificar histórico)
        is_new = await self._is_new_position(wallet, market_id)
        if not is_new:
            return None
        
        # Determinar direção
        direction = "YES" if trade.get("side", "").upper() == "BUY" else "NO"
        
        # Atualizar histórico
        await self._update_wallet_history(wallet, market_id)
        
        # Criar evento
        return WhaleEvent(
            market_id=market_id,
            direction=direction,
            size_usd=size_usd,
            wallet_address=wallet,
            wallet_age_days=await self._get_wallet_age(wallet, market_id),
            liquidity_ratio=size_usd / liquidity if liquidity > 0 else 0,
            timestamp=datetime.now(),
            is_new_position=True,
            previous_position_size=0.0
        )
    
    async def _is_wallet_inactive(self, wallet: str, market_id: str) -> bool:
        """Verifica se wallet está inativa há >= 14 dias (persistido)."""
        return await self.wallet_history.is_wallet_inactive(
            wallet, market_id, self.INACTIVITY_DAYS
        )
    
    async def _is_new_position(self, wallet: str, market_id: str) -> bool:
        """Verifica se é nova posição (não top-up)."""
        # Simplificado: se wallet está inativa, é nova posição
        return await self._is_wallet_inactive(wallet, market_id)
    
    async def _get_wallet_age(self, wallet: str, market_id: str) -> int:
        """Retorna dias desde última atividade (persistido)."""
        return await self.wallet_history.get_wallet_age_days(wallet, market_id)
    
    async def _update_wallet_history(self, wallet: str, market_id: str) -> None:
        """Atualiza histórico de wallet (persistido)."""
        await self.wallet_history.update_wallet(wallet, market_id)
