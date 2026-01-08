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
from src.core.event_scheduler import EventScheduler  # NEW
from src.api.gamma_client import GammaClient
from src.api.clob_client import CLOBClient
from src.api.newsapi_client import NewsAPIClient
from src.api.rss_client import RSSClient
from src.api.arxiv_client import ArXivClient
from src.api.exa_client import ExaClient
from src.api.groq_client import GroqClient
from src.core.research_agent import ResearchAgent
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
        
        # Event Scheduler (NEW - pre-event analysis)
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
            event_scheduler=self.event_scheduler  # NEW
        )
        
        # Estado
        self._running = False
    
    async def start(self):
        """Inicia o sistema."""
        logger.info("exasignal_starting", markets=len(self.market_manager.markets))
        
        # Inicializar databases
        await self.rate_limiter.init_db()
        await self.telegram_bot.user_db.init_db()
        
        # Iniciar bot Telegram (registrar handlers)
        await self.telegram_bot.start()
        
        # Iniciar polling do bot em background
        await self.telegram_bot.run_polling()
        
        self._running = True
        logger.info("exasignal_started")
    
    async def stop(self):
        """Para o sistema graciosamente."""
        logger.info("exasignal_stopping")
        self._running = False
        
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
