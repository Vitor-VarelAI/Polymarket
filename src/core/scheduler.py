"""
ExaSignal - Smart Scheduler
Scheduler híbrido que ajusta polling baseado em horário de mercado US.

Lógica:
- US Market Hours (13h-02h PT / 18h-07h UTC): Polling a cada 5 min
- Off-Hours: Polling a cada 30 min
- Telegram alerts imediatos quando should_alert=True

Uso:
    python -m src.core.scheduler
    
    ou dentro do código:
        scheduler = SmartScheduler(news_monitor, telegram_bot)
        await scheduler.start()
"""
import asyncio
from datetime import datetime, time, timezone
from typing import Optional, Callable, Any
from dataclasses import dataclass

from src.core.news_monitor import NewsMonitor
from src.models.enriched_signal import EnrichedSignal
from src.utils.logger import logger


@dataclass
class ScheduleConfig:
    """Configuração do scheduler."""
    
    # Horário de mercado US (em UTC)
    # US East: 9:30-16:00 EST = 14:30-21:00 UTC
    # Mas news podem mover mercados até mais tarde
    # Usamos janela expandida: 13:00-02:00 UTC (8AM-9PM EST)
    market_start_utc: time = time(13, 0)  # 13:00 UTC = 8AM EST
    market_end_utc: time = time(2, 0)     # 02:00 UTC = 9PM EST (next day)
    
    # Intervalos de polling (segundos)
    poll_interval_market_hours: int = 300   # 5 minutos
    poll_interval_off_hours: int = 1800     # 30 minutos
    
    # Limites de segurança
    max_signals_per_hour: int = 10
    cooldown_after_alert_seconds: int = 60  # Esperar após enviar alert


class SmartScheduler:
    """
    Scheduler inteligente que ajusta frequência de polling
    baseado em horário de mercado US.
    """
    
    def __init__(
        self,
        news_monitor: NewsMonitor,
        telegram_callback: Optional[Callable[[EnrichedSignal], Any]] = None,
        config: ScheduleConfig = None,
    ):
        """
        Inicializa scheduler.
        
        Args:
            news_monitor: Monitor de notícias configurado
            telegram_callback: Função async para enviar alerts Telegram
            config: Configuração de horários/intervalos
        """
        self.monitor = news_monitor
        self.telegram_callback = telegram_callback
        self.config = config or ScheduleConfig()
        
        self._running = False
        self._signals_this_hour = 0
        self._last_hour = -1
        
        # Stats
        self.stats = {
            "scans_total": 0,
            "scans_market_hours": 0,
            "scans_off_hours": 0,
            "signals_generated": 0,
            "alerts_sent": 0,
            "errors": 0,
            "started_at": None,
        }
    
    def is_market_hours(self, now: datetime = None) -> bool:
        """
        Verifica se estamos em horário de mercado US.
        
        Considera a janela expandida 13:00-02:00 UTC que cobre:
        - Pre-market (8AM EST)
        - Market hours (9:30AM-4PM EST)
        - After-hours até 9PM EST
        """
        now = now or datetime.now(timezone.utc)
        current_time = now.time()
        
        start = self.config.market_start_utc
        end = self.config.market_end_utc
        
        # Handle overnight window (13:00 -> 02:00)
        if start > end:
            # Overnight: is_market if current >= start OR current < end
            return current_time >= start or current_time < end
        else:
            # Normal: is_market if start <= current < end
            return start <= current_time < end
    
    def get_current_interval(self) -> int:
        """Retorna intervalo de polling atual em segundos."""
        if self.is_market_hours():
            return self.config.poll_interval_market_hours
        return self.config.poll_interval_off_hours
    
    async def _send_alert(self, signal: EnrichedSignal) -> bool:
        """Envia alert via Telegram."""
        if not self.telegram_callback:
            logger.warning("scheduler_no_telegram", msg="Telegram callback not configured")
            return False
        
        try:
            await self.telegram_callback(signal)
            self.stats["alerts_sent"] += 1
            logger.info(
                "alert_sent",
                market=signal.market_id,
                direction=signal.direction,
                score=signal.score_total
            )
            return True
        except Exception as e:
            logger.error("alert_send_error", error=str(e))
            self.stats["errors"] += 1
            return False
    
    async def _run_scan(self) -> int:
        """
        Executa um scan de notícias.
        
        Returns:
            Número de signals acionáveis encontrados
        """
        try:
            signals = await self.monitor.scan_once()
            self.stats["scans_total"] += 1
            
            if self.is_market_hours():
                self.stats["scans_market_hours"] += 1
            else:
                self.stats["scans_off_hours"] += 1
            
            # Processar signals acionáveis
            actionable_count = 0
            for signal in signals:
                if hasattr(signal, 'should_alert') and signal.should_alert:
                    actionable_count += 1
                    self.stats["signals_generated"] += 1
                    self._signals_this_hour += 1
                    
                    # Rate limit check
                    if self._signals_this_hour > self.config.max_signals_per_hour:
                        logger.warning(
                            "rate_limit_exceeded",
                            signals_this_hour=self._signals_this_hour,
                            max=self.config.max_signals_per_hour
                        )
                        continue
                    
                    # Send alert
                    await self._send_alert(signal)
                    
                    # Cooldown after alert
                    await asyncio.sleep(self.config.cooldown_after_alert_seconds)
            
            return actionable_count
            
        except Exception as e:
            logger.error("scan_error", error=str(e))
            self.stats["errors"] += 1
            return 0
    
    async def start(self):
        """Inicia o scheduler loop."""
        self._running = True
        self.stats["started_at"] = datetime.now(timezone.utc).isoformat()
        
        logger.info(
            "scheduler_started",
            market_hours_interval=self.config.poll_interval_market_hours,
            off_hours_interval=self.config.poll_interval_off_hours,
            market_start=str(self.config.market_start_utc),
            market_end=str(self.config.market_end_utc)
        )
        
        while self._running:
            # Reset hourly counter
            current_hour = datetime.now(timezone.utc).hour
            if current_hour != self._last_hour:
                self._signals_this_hour = 0
                self._last_hour = current_hour
            
            # Get current interval
            interval = self.get_current_interval()
            is_market = self.is_market_hours()
            
            logger.info(
                "scan_starting",
                is_market_hours=is_market,
                interval_seconds=interval,
                signals_this_hour=self._signals_this_hour
            )
            
            # Run scan
            actionable = await self._run_scan()
            
            if actionable > 0:
                logger.info("actionable_signals_found", count=actionable)
            
            # Wait for next interval
            logger.debug("waiting_next_scan", seconds=interval)
            await asyncio.sleep(interval)
    
    def stop(self):
        """Para o scheduler."""
        self._running = False
        logger.info("scheduler_stopped", stats=self.stats)
    
    def get_status(self) -> dict:
        """Retorna status atual do scheduler."""
        return {
            "running": self._running,
            "is_market_hours": self.is_market_hours(),
            "current_interval_seconds": self.get_current_interval(),
            "signals_this_hour": self._signals_this_hour,
            "max_signals_per_hour": self.config.max_signals_per_hour,
            "stats": self.stats,
            "config": {
                "market_start_utc": str(self.config.market_start_utc),
                "market_end_utc": str(self.config.market_end_utc),
                "poll_market_hours": self.config.poll_interval_market_hours,
                "poll_off_hours": self.config.poll_interval_off_hours,
            }
        }


# ============================================================================
# Standalone runner
# ============================================================================

async def run_scheduler():
    """Run scheduler as standalone daemon."""
    from src.api.newsapi_client import NewsAPIClient
    from src.api.finnhub_client import finnhub
    from src.api.groq_client import GroqClient
    from src.api.gamma_client import GammaClient
    from src.core.telegram_bot import TelegramBot
    from src.core.market_manager import MarketManager
    
    logger.info("initializing_scheduler_daemon")
    
    # Initialize clients
    newsapi = NewsAPIClient()
    groq = GroqClient()
    gamma = GammaClient()
    market_manager = MarketManager()
    
    # Initialize Telegram bot with required dependencies
    telegram_bot = TelegramBot(market_manager=market_manager)
    
    # Search function for market matching
    async def search_markets(query: str, limit: int = 50):
        import httpx
        async with httpx.AsyncClient(base_url="https://gamma-api.polymarket.com", timeout=60) as client:
            r = await client.get("/events", params={"limit": 500, "active": "true"})
            events = r.json() if r.status_code == 200 else []
            
            query_lower = query.lower()
            results = [
                {"id": e.get("id"), "slug": e.get("slug"), "name": e.get("title"), "title": e.get("title")}
                for e in events
                if query_lower in e.get("title", "").lower()
            ]
            return results[:limit]
    
    # Telegram alert callback
    async def send_telegram_alert(signal: EnrichedSignal):
        message = signal.to_telegram_message()
        await telegram_bot.broadcast_signal(signal)
        logger.info("telegram_alert_sent", market=signal.market_id, direction=signal.direction)
    
    # Create news monitor with enriched pipeline
    monitor = NewsMonitor(
        newsapi=newsapi,
        finnhub_client=finnhub,
        groq=groq,
        gamma=gamma,
        search_func=search_markets,
        min_score=70,
        min_confidence=60,
        use_enriched=True,
    )
    
    # Create and start scheduler
    scheduler = SmartScheduler(
        news_monitor=monitor,
        telegram_callback=send_telegram_alert,
    )
    
    print()
    print("=" * 60)
    print("       🚀 EXASIGNAL SCHEDULER STARTED")
    print("=" * 60)
    print(f"  Market Hours: 13:00 - 02:00 UTC")
    print(f"  Current Mode: {'MARKET HOURS (5min)' if scheduler.is_market_hours() else 'OFF-HOURS (30min)'}")
    print(f"  Telegram: Enabled")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    try:
        await scheduler.start()
    except KeyboardInterrupt:
        scheduler.stop()
        await gamma.close()
        logger.info("scheduler_shutdown_complete")


if __name__ == "__main__":
    asyncio.run(run_scheduler())

