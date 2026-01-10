"""
ExaSignal - Entry Point Principal
Motor de convicção validada para mercados AI/frontier tech no Polymarket.

Modos de execução:
- Daemon (default): Corre em loop contínuo (para cloud/produção)
- Once: Executa uma vez e sai (para testes)

Uso:
    python -m src.main              # Modo daemon (24/7)
    python -m src.main --once       # Modo único (teste)
    python -m src.main --help       # Ajuda
"""
import asyncio
import argparse
import signal
import sys
from datetime import datetime
from typing import Optional

from src.core.market_manager import MarketManager
from src.core.whale_detector import WhaleDetector
from src.core.whale_filter import WhaleFilter
from src.core.research_loop import ResearchLoop
from src.core.investigator import Investigator
from src.core.alignment_scorer import AlignmentScorer
from src.core.alert_generator import AlertGenerator
from src.core.telegram_bot import TelegramBot
from src.core.event_scheduler import EventScheduler
from src.core.news_monitor import NewsMonitor  # NEW: News monitoring
from src.core.signal_generator import SignalGenerator  # NEW: Signal generation
from src.api.gamma_client import GammaClient
from src.api.clob_client import CLOBClient
from src.api.newsapi_client import NewsAPIClient
from src.api.rss_client import RSSClient
from src.api.arxiv_client import ArXivClient
from src.api.exa_client import ExaClient
from src.api.groq_client import GroqClient
from src.api.finnhub_client import FinnhubClient  # Finnhub for fast news
from src.core.research_agent import ResearchAgent
from src.core.correlation_detector import CorrelationDetector  # Arbitrage detection
from src.core.safe_bets_scanner import SafeBetsScanner  # Safe bets (99% odds)
from src.core.weather_scanner import WeatherValueScanner  # NEW: Weather underdog bets
from src.core.value_bets_scanner import ValueBetsScanner  # NEW: Value bets (underdogs)
from src.core.digest_scheduler import DigestScheduler  # NEW: Scheduled digests
from src.storage.rate_limiter import RateLimiter
from src.storage.user_db import UserDB
from src.utils.config import Config
from src.utils.logger import logger


class ExaSignal:
    """Motor principal do ExaSignal."""
    
    def __init__(self):
        """Inicializa todos os componentes."""
        # Validar configuração
        Config.validate()
        
        # Componentes core
        self.market_manager = MarketManager()
        self.whale_filter = WhaleFilter()
        
        # API Clients
        self.gamma = GammaClient()
        self.clob = CLOBClient()
        self.newsapi = NewsAPIClient()
        self.rss = RSSClient()
        self.arxiv = ArXivClient()
        self.exa = ExaClient()
        self.finnhub = FinnhubClient()  # NEW: Fast news from Finnhub
        
        # Detector
        self.whale_detector = WhaleDetector(
            market_manager=self.market_manager,
            gamma_client=self.gamma,
            clob_client=self.clob,
            whale_filter=self.whale_filter
        )
        
        # Research & Scoring
        self.research_loop = ResearchLoop(
            newsapi=self.newsapi,
            rss=self.rss,
            arxiv=self.arxiv,
            exa=self.exa
        )
        self.alignment_scorer = AlignmentScorer()
        self.investigator = Investigator(
            market_manager=self.market_manager,
            research_loop=self.research_loop,
            gamma_client=self.gamma
        )
        
        # Research Agent (Dexter-style com Groq)
        self.groq = GroqClient()
        self.research_agent = ResearchAgent(
            groq=self.groq,
            exa=self.exa,
            newsapi=self.newsapi,
            gamma=self.gamma
        )
        
        # Event Scheduler (pre-event analysis)
        self.event_scheduler = EventScheduler(
            market_manager=self.market_manager,
            gamma_client=self.gamma
        )
        
        # Alert & Bot
        self.rate_limiter = RateLimiter()
        self.alert_generator = AlertGenerator(rate_limiter=self.rate_limiter)
        self.telegram_bot = TelegramBot(
            market_manager=self.market_manager,
            alert_generator=self.alert_generator,
            investigator=self.investigator,
            research_agent=self.research_agent,
            event_scheduler=self.event_scheduler
        )
        
        # News Monitor for automatic signal detection
        # Signal callback will be set after telegram_bot is ready
        # NOTE: Thresholds LOWERED to ensure alerts are generated
        self.news_monitor = NewsMonitor(
            newsapi=self.newsapi,
            finnhub_client=self.finnhub,
            groq=self.groq,
            gamma=self.gamma,
            search_func=self._search_markets_for_signal,
            signal_callback=None,  # Set in start() after bot is ready
            poll_interval_seconds=300,  # 5 minutes
            min_score=50,  # LOWERED from 70 - more alerts
            min_confidence=40,  # LOWERED from 60 - more alerts
            max_news_age_minutes=60,  # INCREASED from 30 - capture more news
            use_enriched=True
        )
        
        # Correlation Detector for arbitrage opportunities (SwissTony-inspired)
        # Detects mispricings between correlated markets
        self.correlation_detector = CorrelationDetector(
            gamma=self.gamma,
            groq=self.groq,
            callback=None,  # Set in start() after bot is ready
            min_edge=1.5,  # LOWERED from 2.0 - more alerts
            min_confidence=60,  # LOWERED from 70
            scan_interval=600,  # 10 minutes
        )
        
        # Safe Bets Scanner (SwissTony vacuum cleaner strategy)
        # Finds markets with high odds for small consistent profits
        # Settings optimized for quality over quantity
        self.safe_bets_scanner = SafeBetsScanner(
            gamma=self.gamma,
            callback=None,  # Set in start() after bot is ready
            min_odds_threshold=97.0,  # 97%+ odds for safe bets
            min_liquidity=5000,  # $5k+ liquidity to ensure exit
            min_expected_value=0.5,  # Must have positive EV
            scan_interval=1800,  # 30 minutes
            excluded_categories=["Sports"],
        )
        
        # Weather Value Scanner (Meteorological Bot strategy)
        # Finds undervalued weather markets for $1 underdog bets
        # NOTE: Thresholds LOWERED to find more opportunities
        self.weather_scanner = WeatherValueScanner(
            callback=None,  # Set in start() after bot is ready
            max_entry_price=15.0,  # INCREASED from 10.0 - more markets
            min_edge=3.0,  # LOWERED from 5.0 - more alerts
            min_confidence=50,  # LOWERED from 60
            scan_interval=7200,  # 2 hours (was 3 hours)
        )
        
        # =======================================================
        # NEW: Value Bets Digest System (replaces instant alerts)
        # =======================================================
        # Collects value bet opportunities (broader range to find more)
        self.value_bets_scanner = ValueBetsScanner(
            gamma=self.gamma,
            min_odds=2.0,  # EXPANDED: from 5% to 2% (more underdogs)
            max_odds=50.0,  # EXPANDED: from 30% to 50% (moderate risk too)
            min_liquidity=1000,  # LOWERED: from $5k to $1k (more markets)
            max_days_to_resolution=90,  # EXPANDED: from 60 to 90 days
            scan_interval=3600,  # Scan every 1 hour (was 2)
        )
        
        # Digest scheduler - sends curated picks at 11:00 and 20:00 UTC
        self.digest_scheduler = DigestScheduler(
            scanner=self.value_bets_scanner,
            groq=self.groq,
            send_callback=None,  # Set in start()
            picks_per_digest=10,  # 10 best picks per digest
        )
        
        # Estado
        self._running = False
    
    async def _search_markets_for_signal(self, query: str, limit: int = 50):
        """Search Polymarket for signal matching - combines events + markets."""
        import httpx
        
        async with httpx.AsyncClient(base_url="https://gamma-api.polymarket.com", timeout=60) as client:
            # Fetch both endpoints in parallel
            async def get_events():
                r = await client.get("/events", params={
                    "limit": 500, 
                    "active": "true",
                    "order": "startDate",
                    "ascending": "false"
                })
                return r.json() if r.status_code == 200 else []
            
            async def get_markets():
                r = await client.get("/markets", params={
                    "closed": "false", 
                    "limit": 500,
                    "order": "createdAt",
                    "ascending": "false"
                })
                return r.json() if r.status_code == 200 else []
            
            events, markets = await asyncio.gather(get_events(), get_markets())
            
            # Combine all items
            all_items = []
            seen = set()
            
            for e in events:
                slug = e.get("slug", "")
                if slug and slug not in seen:
                    seen.add(slug)
                    all_items.append({
                        "id": e.get("id", slug),
                        "slug": slug,
                        "title": e.get("title", ""),
                        "name": e.get("title", ""),
                        "description": e.get("description", "") or "",
                    })
            
            for m in markets:
                q = m.get("question", "")
                if q and q not in seen:
                    seen.add(q)
                    all_items.append({
                        "id": m.get("id", ""),
                        "slug": m.get("slug", m.get("conditionId", "")),
                        "title": q,
                        "name": q,
                        "description": m.get("description", "") or "",
                    })
            
            # Filter by query keywords
            query_lower = query.lower()
            query_words = query_lower.split()
            
            results = []
            for item in all_items:
                text = (item.get("title", "") + " " + item.get("description", "")).lower()
                if any(word in text for word in query_words):
                    results.append(item)
            
            logger.debug("signal_search", query=query, found=len(results), total=len(all_items))
            return results[:limit]
    
    async def _broadcast_arbitrage(self, opportunity):
        """Broadcast arbitrage opportunity to Telegram users."""
        users = await self.telegram_bot.user_db.get_active_users()
        message = opportunity.to_telegram()
        
        sent_count = 0
        for user in users:
            try:
                await self.telegram_bot.bot.send_message(
                    chat_id=user.user_id,
                    text=message.strip(),
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
                sent_count += 1
            except Exception as e:
                logger.error("arb_broadcast_error", user_id=user.user_id, error=str(e))
        
        logger.info("arbitrage_broadcast_complete", 
                   edge=opportunity.edge,
                   sent_to=sent_count)
    
    async def _broadcast_safe_bet(self, safe_bet):
        """Broadcast safe bet opportunity to Telegram users."""
        logger.info("_broadcast_safe_bet_called", market=safe_bet.market_name[:30])
        
        users = await self.telegram_bot.user_db.get_active_users()
        logger.info("_broadcast_safe_bet_users", user_count=len(users))
        
        if not users:
            logger.warning("_broadcast_safe_bet_no_users")
            return
        
        message = safe_bet.to_telegram()
        
        sent_count = 0
        for user in users:
            try:
                await self.telegram_bot.bot.send_message(
                    chat_id=user.user_id,
                    text=message.strip(),
                    parse_mode="Markdown",
                    disable_web_page_preview=False
                )
                sent_count += 1
                logger.info("safe_bet_sent_to_user", user_id=user.user_id)
            except Exception as e:
                logger.error("safe_bet_broadcast_error", user_id=user.user_id, error=str(e))
        
        logger.info("safe_bet_broadcast_complete", 
                   market=safe_bet.market_name[:30],
                   entry_price=safe_bet.entry_price,
                   sent_to=sent_count)
    
    async def _broadcast_weather_bet(self, weather_bet):
        """Broadcast weather value bet to Telegram users."""
        users = await self.telegram_bot.user_db.get_active_users()
        message = weather_bet.to_telegram()
        
        sent_count = 0
        for user in users:
            try:
                await self.telegram_bot.bot.send_message(
                    chat_id=user.user_id,
                    text=message.strip(),
                    parse_mode="Markdown",
                    disable_web_page_preview=False
                )
                sent_count += 1
            except Exception as e:
                logger.error("weather_broadcast_error", user_id=user.user_id, error=str(e))
        
        logger.info("weather_bet_broadcast_complete", 
                   market=weather_bet.market_name[:30],
                   entry_price=weather_bet.entry_price,
                   edge=weather_bet.edge,
                   sent_to=sent_count)
    
    async def _broadcast_digest(self, digest_message: str):
        """Broadcast digest message to all Telegram users."""
        users = await self.telegram_bot.user_db.get_active_users()
        
        if not users:
            logger.warning("digest_broadcast_no_users")
            return
        
        sent_count = 0
        for user in users:
            try:
                await self.telegram_bot.bot.send_message(
                    chat_id=user.user_id,
                    text=digest_message.strip(),
                    parse_mode="Markdown",
                    disable_web_page_preview=False
                )
                sent_count += 1
            except Exception as e:
                logger.error("digest_broadcast_error", user_id=user.user_id, error=str(e))
        
        logger.info("digest_broadcast_complete", sent_to=sent_count)
    
    async def _add_to_digest_queue(self, safe_bet):
        """Convert SafeBet to ValueBet format and add to digest queue."""
        from src.core.value_bets_scanner import ValueBet
        
        # Convert to unified ValueBet format
        vb = ValueBet(
            market_id=safe_bet.market_id,
            market_name=safe_bet.market_name,
            slug=safe_bet.slug,
            category=safe_bet.category,
            yes_odds=safe_bet.yes_odds,
            no_odds=safe_bet.no_odds,
            bet_side=safe_bet.bet_side,
            entry_price=safe_bet.entry_price,
            potential_multiplier=100 / safe_bet.entry_price if safe_bet.entry_price > 0 else 1,
            shares_for_dollar=int(100 / safe_bet.entry_price) if safe_bet.entry_price > 0 else 0,
            win_amount=(100 / safe_bet.entry_price) if safe_bet.entry_price > 0 else 0,
            liquidity=safe_bet.liquidity,
            volume=safe_bet.volume,
        )
        
        # Add to scanner queue (avoiding duplicates)
        if vb.market_id not in self.value_bets_scanner.sent_markets:
            existing = {c.market_id for c in self.value_bets_scanner.candidates}
            if vb.market_id not in existing:
                self.value_bets_scanner.candidates.append(vb)
                logger.info("safe_bet_added_to_digest_queue", market=vb.market_name[:30])
    
    async def _add_arbitrage_to_digest_queue(self, opportunity):
        """Convert ArbitrageOpportunity to ValueBet format and add to digest queue."""
        from src.core.value_bets_scanner import ValueBet
        
        # Create a combined bet for arbitrage
        vb = ValueBet(
            market_id=f"arb_{opportunity.pair.market_a_id}_{opportunity.pair.market_b_id}",
            market_name=f"ARBITRAGE: {opportunity.pair.market_a_name[:25]} vs {opportunity.pair.market_b_name[:25]}",
            slug=opportunity.pair.market_a_id,
            category="Arbitrage",
            yes_odds=opportunity.odds_a,
            no_odds=opportunity.odds_b,
            bet_side="ARBITRAGE",
            entry_price=50,  # Placeholder
            potential_multiplier=1 + (opportunity.edge / 100),
            shares_for_dollar=1,
            win_amount=1 + (opportunity.edge / 100),
            liquidity=10000,  # Assume good liquidity
        )
        
        if vb.market_id not in self.value_bets_scanner.sent_markets:
            existing = {c.market_id for c in self.value_bets_scanner.candidates}
            if vb.market_id not in existing:
                self.value_bets_scanner.candidates.append(vb)
                logger.info("arbitrage_added_to_digest_queue", edge=opportunity.edge)
    
    async def _add_weather_to_digest_queue(self, weather_bet):
        """Convert WeatherValueBet to ValueBet format and add to digest queue."""
        from src.core.value_bets_scanner import ValueBet
        
        vb = ValueBet(
            market_id=weather_bet.market_id,
            market_name=f"🌦️ {weather_bet.market_name}",
            slug=weather_bet.slug,
            category="Weather",
            yes_odds=weather_bet.market_odds,
            no_odds=100 - weather_bet.market_odds,
            bet_side=weather_bet.bet_side,
            entry_price=weather_bet.entry_price,
            potential_multiplier=100 / weather_bet.entry_price if weather_bet.entry_price > 0 else 1,
            shares_for_dollar=int(100 / weather_bet.entry_price) if weather_bet.entry_price > 0 else 0,
            win_amount=(100 / weather_bet.entry_price) if weather_bet.entry_price > 0 else 0,
            liquidity=weather_bet.liquidity,
        )
        
        if vb.market_id not in self.value_bets_scanner.sent_markets:
            existing = {c.market_id for c in self.value_bets_scanner.candidates}
            if vb.market_id not in existing:
                self.value_bets_scanner.candidates.append(vb)
                logger.info("weather_bet_added_to_digest_queue", market=vb.market_name[:30])
    
    async def start(self):
        """Inicia o sistema."""
        logger.info("exasignal_starting", markets=len(self.market_manager.markets))
        
        # Inicializar databases
        await self.rate_limiter.init_db()
        await self.telegram_bot.user_db.init_db()
        
        # Iniciar bot Telegram (registrar handlers)
        await self.telegram_bot.start()
        
        # Connect signal callback to Telegram broadcast AFTER bot is ready
        self.news_monitor.signal_callback = self.telegram_bot.broadcast_signal
        logger.info("news_monitor_callback_connected")
        
        # Connect arbitrage callback to Telegram broadcast
        self.correlation_detector.callback = self._broadcast_arbitrage
        logger.info("correlation_detector_callback_connected", callback_set=self.correlation_detector.callback is not None)
        
        # Connect safe bets callback to Telegram broadcast
        self.safe_bets_scanner.callback = self._broadcast_safe_bet
        logger.info("safe_bets_scanner_callback_connected", 
                   callback_set=self.safe_bets_scanner.callback is not None,
                   callback_name=str(self._broadcast_safe_bet))
        
        # Connect weather scanner callback to Telegram broadcast
        self.weather_scanner.callback = self._broadcast_weather_bet
        logger.info("weather_scanner_callback_connected", callback_set=self.weather_scanner.callback is not None)
        
        # Inject scanner references for /debug command
        self.telegram_bot.news_monitor = self.news_monitor
        self.telegram_bot.correlation_detector = self.correlation_detector
        self.telegram_bot.safe_bets_scanner = self.safe_bets_scanner
        self.telegram_bot.weather_scanner = self.weather_scanner
        self.telegram_bot.value_bets_scanner = self.value_bets_scanner  # NEW
        self.telegram_bot.digest_scheduler = self.digest_scheduler  # NEW
        logger.info("scanners_injected_to_telegram_bot")
        
        # Iniciar polling do bot em background
        await self.telegram_bot.run_polling()
        
        # Start news monitoring in background
        asyncio.create_task(self.news_monitor.start_monitoring())
        logger.info("news_monitor_started", 
                   poll_interval=self.news_monitor.poll_interval,
                   min_score=self.news_monitor.min_score,
                   finnhub_available=self.news_monitor.finnhub.is_available if hasattr(self.news_monitor.finnhub, 'is_available') else 'unknown')
        
        # =======================================================
        # ALL SCANNERS NOW FEED INTO DIGEST (no instant spam)
        # LLM picks the best 4 from ALL sources
        # =======================================================
        
        # Connect digest broadcast callback
        self.digest_scheduler.send_callback = self._broadcast_digest
        
        # Re-enable SafeBetsScanner but connect to digest queue
        self.safe_bets_scanner.callback = self._add_to_digest_queue
        asyncio.create_task(self.safe_bets_scanner.start_monitoring())
        logger.info("safe_bets_scanner_started_for_digest")
        
        # Re-enable CorrelationDetector but connect to digest queue
        self.correlation_detector.callback = self._add_arbitrage_to_digest_queue
        asyncio.create_task(self.correlation_detector.start_monitoring())
        logger.info("correlation_detector_started_for_digest")
        
        # Re-enable WeatherScanner but connect to digest queue
        self.weather_scanner.callback = self._add_weather_to_digest_queue
        asyncio.create_task(self.weather_scanner.start_monitoring())
        logger.info("weather_scanner_started_for_digest")
        
        # Start value bets scanner (also feeds digest)
        asyncio.create_task(self.value_bets_scanner.start_scanning())
        logger.info("value_bets_scanner_started",
                   min_odds=self.value_bets_scanner.min_odds,
                   max_odds=self.value_bets_scanner.max_odds,
                   scan_interval=self.value_bets_scanner.scan_interval)
        
        # Start digest scheduler (sends at 11:00, 16:00, 20:00)
        asyncio.create_task(self.digest_scheduler.start())
        logger.info("digest_scheduler_started",
                   times=["11:00", "20:00"],
                   picks_per_digest=self.digest_scheduler.picks_per_digest)
        
        self._running = True
        logger.info("exasignal_started")
        
        # Send startup notification to all active users
        await self._send_startup_notification()
    
    async def _send_startup_notification(self):
        """Send notification to all users that the system is now running."""
        try:
            users = await self.telegram_bot.user_db.get_active_users()
            
            if not users:
                logger.warning("no_active_users_for_startup_notification")
                return
            
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            
            startup_msg = f"""
🚀 *ExaSignal Online!*

O sistema arrancou às {now}

📡 *Scanners Ativos:*
• NewsMonitor (cada 5 min)
• CorrelationDetector (cada 10 min)  
• SafeBetsScanner (cada 30 min)
• WeatherScanner (cada 2 horas)

✅ Vais receber alertas automaticamente.
Use /debug para ver o estado dos scanners.
"""
            
            sent_count = 0
            for user in users:
                try:
                    await self.telegram_bot.bot.send_message(
                        chat_id=user.user_id,
                        text=startup_msg.strip(),
                        parse_mode="Markdown"
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error("startup_notification_error", user_id=user.user_id, error=str(e))
            
            logger.info("startup_notification_sent", users=sent_count)
            
        except Exception as e:
            logger.error("startup_notification_failed", error=str(e))
    
    async def stop(self):
        """Para o sistema graciosamente."""
        logger.info("exasignal_stopping")
        self._running = False
        
        # Stop all monitors
        self.news_monitor.stop_monitoring()
        self.correlation_detector.stop_monitoring()
        self.safe_bets_scanner.stop_monitoring()
        self.weather_scanner.stop_monitoring()
        
        # Fechar conexões
        await self.telegram_bot.stop()
        await self.gamma.close()
        await self.clob.close()
        await self.newsapi.close()
        await self.arxiv.close()
        
        logger.info("exasignal_stopped")
    
    async def run_once(self):
        """Executa uma vez todos os mercados."""
        logger.info("run_once_starting")
        
        for market in self.market_manager.get_all_markets():
            await self._process_market(market.market_id)
        
        logger.info("run_once_complete")
    
    async def run_daemon(self):
        """Executa em loop contínuo."""
        logger.info(
            "daemon_starting",
            interval_seconds=Config.POLLING_INTERVAL_SECONDS
        )
        
        while self._running:
            try:
                cycle_start = datetime.now()
                
                # Processar todos os mercados
                for market in self.market_manager.get_all_markets():
                    if not self._running:
                        break
                    await self._process_market(market.market_id)
                
                # Esperar próximo ciclo
                elapsed = (datetime.now() - cycle_start).total_seconds()
                sleep_time = max(0, Config.POLLING_INTERVAL_SECONDS - elapsed)
                
                logger.debug("cycle_complete", elapsed=elapsed, sleeping=sleep_time)
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                logger.error("daemon_error", error=str(e))
                await asyncio.sleep(60)  # Esperar 1 min em caso de erro
    
    async def _process_market(self, market_id: str):
        """Processa um mercado: whale → research → score → alert."""
        try:
            # 1. Detectar eventos whale
            whale_events = await self.whale_detector.check_market(market_id)
            
            if not whale_events:
                return
            
            market = self.market_manager.get_market_by_id(market_id)
            current_odds = await self.gamma.get_market_odds(market_id) or 50.0
            
            for event in whale_events:
                # 2. Executar research
                research = await self.research_loop.execute(market, event)
                
                # 3. Calcular score
                score_result = self.alignment_scorer.calculate(
                    whale_event=event,
                    research=research,
                    current_odds=current_odds
                )
                
                # 4. Gerar alerta (se passar threshold e rate limits)
                alert = await self.alert_generator.generate(
                    market=market,
                    whale_event=event,
                    score_result=score_result,
                    current_odds=current_odds
                )
                
                # 5. Enviar via Telegram
                if alert:
                    await self.telegram_bot.broadcast_alert(alert)
                    logger.info(
                        "alert_sent",
                        market_id=market_id,
                        direction=alert.direction,
                        score=alert.score
                    )
        
        except Exception as e:
            logger.error("market_processing_error", market_id=market_id, error=str(e))


async def main():
    """Entry point principal."""
    parser = argparse.ArgumentParser(
        description="ExaSignal - Motor de convicção para Polymarket"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Executar uma vez e sair (modo teste)"
    )
    args = parser.parse_args()
    
    # Criar instância
    engine = ExaSignal()
    
    # Configurar signal handlers para shutdown gracioso
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        logger.info("shutdown_signal_received")
        asyncio.create_task(engine.stop())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        await engine.start()
        
        if args.once:
            await engine.run_once()
        else:
            await engine.run_daemon()
    
    finally:
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(main())
