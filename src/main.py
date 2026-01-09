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
        
        # NEW: News Monitor for automatic signal detection
        # Signal callback will be set after telegram_bot is ready
        self.news_monitor = NewsMonitor(
            newsapi=self.newsapi,
            finnhub_client=self.finnhub,
            groq=self.groq,
            gamma=self.gamma,
            search_func=self._search_markets_for_signal,
            signal_callback=None,  # Set in start() after bot is ready
            poll_interval_seconds=300,  # 5 minutes
            min_score=70,
            min_confidence=60,
            max_news_age_minutes=30,
            use_enriched=True
        )
        
        # NEW: Correlation Detector for arbitrage opportunities (SwissTony-inspired)
        # Detects mispricings between correlated markets
        self.correlation_detector = CorrelationDetector(
            gamma=self.gamma,
            groq=self.groq,
            callback=None,  # Set in start() after bot is ready
            min_edge=2.0,  # Minimum 2% edge to alert
            min_confidence=70,
            scan_interval=600,  # 10 minutes (more intensive AI usage)
        )
        
        # NEW: Safe Bets Scanner (SwissTony vacuum cleaner strategy)
        # Finds markets with 97%+ odds for small consistent profits
        self.safe_bets_scanner = SafeBetsScanner(
            gamma=self.gamma,
            callback=None,  # Set in start() after bot is ready
            min_odds_threshold=97.0,  # Only 97%+ certainty
            min_liquidity=1000,  # Minimum $1k liquidity
            min_expected_value=0.5,  # Minimum 0.5% EV
            scan_interval=1800,  # 30 minutes (less frequent)
            excluded_categories=["Sports"],  # Sports too volatile during games
        )
        
        # Weather Value Scanner (Meteorological Bot strategy)
        # Finds undervalued weather markets for $1 underdog bets
        # NOTE: Uses cached forecasts (2h TTL) to minimize API calls
        self.weather_scanner = WeatherValueScanner(
            callback=None,  # Set in start() after bot is ready
            max_entry_price=10.0,  # Only bet on ≤10¢ outcomes (underdogs)
            min_edge=5.0,  # Minimum 5% edge over market
            min_confidence=60,
            scan_interval=10800,  # 3 hours (free tier friendly - ~8 API batches/day)
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
        users = await self.telegram_bot.user_db.get_active_users()
        message = safe_bet.to_telegram()
        
        sent_count = 0
        for user in users:
            try:
                await self.telegram_bot.bot.send_message(
                    chat_id=user.user_id,
                    text=message.strip(),
                    parse_mode="Markdown",
                    disable_web_page_preview=False  # Show market link preview
                )
                sent_count += 1
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
        logger.info("correlation_detector_callback_connected")
        
        # Connect safe bets callback to Telegram broadcast
        self.safe_bets_scanner.callback = self._broadcast_safe_bet
        logger.info("safe_bets_scanner_callback_connected")
        
        # Connect weather scanner callback to Telegram broadcast
        self.weather_scanner.callback = self._broadcast_weather_bet
        logger.info("weather_scanner_callback_connected")
        
        # Iniciar polling do bot em background
        await self.telegram_bot.run_polling()
        
        # Start news monitoring in background
        asyncio.create_task(self.news_monitor.start_monitoring())
        logger.info("news_monitor_started", 
                   poll_interval=self.news_monitor.poll_interval,
                   min_score=self.news_monitor.min_score,
                   finnhub_available=self.news_monitor.finnhub.is_available if hasattr(self.news_monitor.finnhub, 'is_available') else 'unknown')
        
        # Start correlation detector in background (arbitrage detection)
        asyncio.create_task(self.correlation_detector.start_monitoring())
        logger.info("correlation_detector_started",
                   min_edge=self.correlation_detector.min_edge,
                   scan_interval=self.correlation_detector.scan_interval)
        
        # Start safe bets scanner in background (vacuum cleaner strategy)
        asyncio.create_task(self.safe_bets_scanner.start_monitoring())
        logger.info("safe_bets_scanner_started",
                   min_odds=self.safe_bets_scanner.min_odds_threshold,
                   min_liquidity=self.safe_bets_scanner.min_liquidity,
                   scan_interval=self.safe_bets_scanner.scan_interval)
        
        # Start weather value scanner in background (meteorological bot strategy)
        asyncio.create_task(self.weather_scanner.start_monitoring())
        logger.info("weather_scanner_started",
                   max_entry_price=self.weather_scanner.max_entry_price,
                   min_edge=self.weather_scanner.min_edge,
                   scan_interval=self.weather_scanner.scan_interval)
        
        self._running = True
        logger.info("exasignal_started")
    
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
