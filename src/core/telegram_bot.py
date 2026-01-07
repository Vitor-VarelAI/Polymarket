"""
ExaSignal - Telegram Bot
Baseado em PRD-06-Telegram-Bot

Comandos:
- /start - Registo e boas-vindas
- /markets - Lista mercados monitorizados
- /status - Estado do sistema
- /settings - Configurações do utilizador
- /health - Verificação de saúde
"""
from typing import List, Optional

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.core.market_manager import MarketManager
from src.core.alert_generator import AlertGenerator
from src.core.investigator import Investigator
from src.storage.user_db import UserDB
from src.storage.rate_limiter import RateLimiter
from src.storage.performance_tracker import PerformanceTracker
from src.models.alert import Alert
from src.utils.config import Config
from src.utils.logger import logger


# Estados da conversação
CHOOSING_FLOW, CHOOSING_MARKET = range(2)

class TelegramBot:
    """Bot Telegram para ExaSignal."""
    
    def __init__(
        self,
        market_manager: MarketManager,
        alert_generator: AlertGenerator = None,
        user_db: UserDB = None,
        investigator: Investigator = None,
        research_agent = None,  # ResearchAgent opcional (Dexter-style)
        performance_tracker: PerformanceTracker = None  # NEW: Track signal performance
    ):
        """Inicializa bot com dependências."""
        self.market_manager = market_manager
        self.alert_generator = alert_generator or AlertGenerator()
        self.user_db = user_db or UserDB()
        self.investigator = investigator # Injetado depois if None
        self.research_agent = research_agent  # Dexter-style agent
        self.performance_tracker = performance_tracker or PerformanceTracker()  # NEW
        
        self.app: Optional[Application] = None
        self.bot: Optional[Bot] = None
    
    async def start(self):
        """Inicia o bot."""
        self.app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        self.bot = self.app.bot
        
        # Registar handlers
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("markets", self._cmd_markets))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("settings", self._cmd_settings))
        self.app.add_handler(CommandHandler("health", self._cmd_health))
        self.app.add_handler(CommandHandler("signals", self._cmd_signals))
        self.app.add_handler(CommandHandler("stats", self._cmd_stats))  # NEW
        
        # Guided Investigation Handler
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("investigate", self._cmd_investigate)],
            states={
                CHOOSING_FLOW: [CallbackQueryHandler(self._handle_flow_choice)],
                CHOOSING_MARKET: [CallbackQueryHandler(self._handle_market_choice)],
            },
            fallbacks=[CommandHandler("cancel", self._cancel)]
        )
        self.app.add_handler(conv_handler)
        
    async def _cmd_investigate(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Inicia fluxo de investigação."""
        user = update.effective_user
        
        # Verificar quota
        can_investigate = await self.user_db.check_investigation_quota(user.id)
        if not can_investigate:
            await update.message.reply_text(
                "🔒 **Limite Diário Atingido**\n"
                "Apenas 2 investigações guiadas por dia.\n"
                "Tente novamente amanhã.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
            
        # Menu Principal
        keyboard = [
            [InlineKeyboardButton("📊 Investigar Mercado Específico", callback_data="flow_market")],
            [InlineKeyboardButton("🌍 Narrativa Geral AI/Tech", callback_data="flow_narrative")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🕵️ **Investigação Guiada**\n\n"
            "Escolha o tipo de research que deseja gerar.\n"
            "⚠️ _Isto consome 1 crédito diário._",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return CHOOSING_FLOW

    async def _handle_flow_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Trata escolha inicial do menu."""
        query = update.callback_query
        await query.answer()
        
        if query.data == "cancel":
            await query.edit_message_text("Investigação cancelada. Quota intacta.")
            return ConversationHandler.END
            
        if query.data == "flow_narrative":
            # Executar research narrativa imediato
            await query.edit_message_text("🔄 Analisando narrativa global com Exa... aguarde")
            
            try:
                # Executar PRIMEIRO
                if self.investigator:
                    report = await self.investigator.investigate_narrative()
                    
                    # Se sucesso, incrementa quota
                    await self.user_db.increment_investigation(update.effective_user.id)
                    
                    await query.edit_message_text(report, parse_mode="Markdown")
                else:
                    await query.edit_message_text("❌ Erro interno: Investigator not initialized")
                    
            except Exception as e:
                logger.error("investigation_error", error=str(e))
                await query.edit_message_text("❌ Erro na investigação. Quota não consumida.")
                
            return ConversationHandler.END
            
        if query.data == "flow_market":
            # Listar mercados para escolha (Top 10 para mais opções)
            markets = self.market_manager.get_all_markets()[:10]
            # Guardar mapeamento no contexto
            context.user_data["market_map"] = {str(i): m.market_id for i, m in enumerate(markets)}
            keyboard = []
            for i, m in enumerate(markets):
                emoji = "🤖" if m.category == "AI" else "🚀"
                keyboard.append([InlineKeyboardButton(f"{emoji} {m.market_name[:35]}...", callback_data=f"mkt_{i}")])
            
            keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "Escolha o mercado para investigar:",
                reply_markup=reply_markup
            )
            return CHOOSING_MARKET
            
        return ConversationHandler.END

    async def _handle_market_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Trata escolha do mercado."""
        query = update.callback_query
        await query.answer()
        
        if query.data == "cancel":
            await query.edit_message_text("Investigação cancelada. Quota intacta.")
            return ConversationHandler.END
        
        # Obter market_id do mapeamento
        market_idx = query.data.replace("mkt_", "")
        market_map = context.user_data.get("market_map", {})
        market_id = market_map.get(market_idx)
        
        if not market_id:
            await query.edit_message_text("❌ Mercado não encontrado.")
            return ConversationHandler.END
        
        await query.edit_message_text(f"🔄 Analisando mercado com AI... aguarde")
        
        try:
            market = self.market_manager.get_market_by_id(market_id)
            
            # Usar Research Agent se disponível (análise profunda multi-fase)
            if self.research_agent and market:
                result = await self.research_agent.investigate(market)
                report = self.research_agent.format_telegram_message(result)
                
                # Se sucesso, incrementa quota
                await self.user_db.increment_investigation(update.effective_user.id)
                
                await query.edit_message_text(report, parse_mode="Markdown")
            
            # Fallback para investigator simples
            elif self.investigator:
                report = await self.investigator.investigate_market(market_id)
                await self.user_db.increment_investigation(update.effective_user.id)
                await query.edit_message_text(report, parse_mode="Markdown")
            
            else:
                await query.edit_message_text("❌ Erro interno: Investigator not initialized")
                
        except Exception as e:
            import traceback
            logger.error("investigation_error", error=str(e), market_id=market_id, traceback=traceback.format_exc())
            await query.edit_message_text("❌ Erro na investigação. Quota não consumida.")
            
        return ConversationHandler.END

    async def _cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancela conversação."""
        await update.message.reply_text("Investigação cancelada.")
        return ConversationHandler.END
    
    async def run_polling(self):
        """Inicia polling para receber mensagens."""
        logger.info("telegram_bot_started")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
    
    async def stop(self):
        """Para o bot."""
        if self.app:
            if self.app.updater and self.app.updater.running:
                await self.app.updater.stop()
            if self.app.running:
                await self.app.stop()
                await self.app.shutdown()
    
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /start."""
        user = update.effective_user
        
        # Registar utilizador
        await self.user_db.get_or_create(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name
        )
        
        await update.message.reply_text(
            f"👋 Olá {user.first_name}!\n\n"
            "🐋 **ExaSignal** - Alertas de whale validados por research\n\n"
            "Comandos:\n"
            "/markets - Ver mercados\n"
            "/status - Estado do sistema\n"
            "/settings - Configurações\n"
            "/health - Verificar saúde\n\n"
            "Vais receber alertas quando houver movimentos interessantes!",
            parse_mode="Markdown"
        )
    
    async def _cmd_markets(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /markets."""
        markets = self.market_manager.get_all_markets()
        
        lines = ["📊 **Mercados Monitorizados:**\n"]
        for i, m in enumerate(markets[:10], 1):
            emoji = "🤖" if m.category == "AI" else "🚀"
            lines.append(f"{i}. {emoji} {m.market_name[:40]}")
        
        if len(markets) > 10:
            lines.append(f"\n... e mais {len(markets) - 10} mercados")
        
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    
    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /status."""
        status = await self.alert_generator.get_status()
        
        await update.message.reply_text(
            "📈 **Estado do Sistema:**\n\n"
            f"Alertas hoje: {status['daily_alerts']}/{status['daily_limit']}\n"
            f"Restantes: {status['remaining']}\n\n"
            f"Mercados: {len(self.market_manager.markets)}\n"
            "Status: 🟢 Online",
            parse_mode="Markdown"
        )
    
    async def _cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /settings."""
        user = await self.user_db.get_or_create(update.effective_user.id)
        
        await update.message.reply_text(
            "⚙️ **Configurações:**\n\n"
            f"Threshold mínimo: {user.score_threshold}/100\n\n"
            "Para alterar, use:\n"
            "`/settings 75` (mínimo 60)",
            parse_mode="Markdown"
        )
    
    async def _cmd_health(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /health."""
        await update.message.reply_text(
            "🏥 **Health Check:**\n\n"
            "Bot: 🟢 OK\n"
            "Database: 🟢 OK\n"
            "APIs: 🟢 Ready",
            parse_mode="Markdown"
        )
    
    async def _cmd_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /signals - mostra sinais recentes."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get("http://localhost:8000/api/signals/recent?limit=5")
                if r.status_code == 200:
                    data = r.json()
                    signals = data.get("signals", [])
                    
                    if not signals:
                        await update.message.reply_text(
                            "📊 **No recent signals**\n\n"
                            "Use /scan to trigger a news scan.",
                            parse_mode="Markdown"
                        )
                        return
                    
                    # Format signals
                    text = "📊 **Recent Trading Signals:**\n\n"
                    
                    for s in signals[:5]:
                        emoji = "🟢" if s["direction"] == "YES" else "🔴" if s["direction"] == "NO" else "⚪"
                        text += f"{emoji} *{s['direction']}* ({s['confidence']}%)\n"
                        text += f"📊 {s['market_name'][:40]}...\n"
                        text += f"📰 {s['news_title'][:40]}...\n\n"
                    
                    await update.message.reply_text(text, parse_mode="Markdown")
                else:
                    await update.message.reply_text("⚠️ Signal API not available")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)[:50]}")
    
    async def broadcast_alert(self, alert: Alert):
        """Envia alerta para todos os utilizadores ativos."""
        users = await self.user_db.get_active_users()
        message = alert.to_telegram_message()
        
        sent_count = 0
        for user in users:
            if alert.score >= user.score_threshold:
                try:
                    await self.bot.send_message(
                        chat_id=user.user_id,
                        text=message,
                        parse_mode="Markdown",
                        disable_web_page_preview=False
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error("broadcast_error", user_id=user.user_id, error=str(e))
        
        logger.info("alert_broadcast_complete", alert_id=alert.alert_id, sent_to=sent_count)
    
    async def broadcast_signal(self, signal):
        """
        Envia sinal de trading para todos os utilizadores ativos.
        
        Args:
            signal: Signal object from SignalGenerator
        """
        users = await self.user_db.get_active_users()
        
        # Log signal for performance tracking
        try:
            score = getattr(signal, 'score_total', signal.confidence)
            trigger_type = getattr(signal, 'trigger_type', 'news')
            odds = getattr(signal, 'current_odds', None)
            
            await self.performance_tracker.log_signal(
                market_id=signal.market_id,
                market_name=signal.market_name,
                direction=signal.direction,
                odds=odds or 0,
                score=score,
                trigger_type=trigger_type
            )
        except Exception as e:
            logger.error("performance_tracking_error", error=str(e))
        
        # Format signal message
        emoji = "🟢" if signal.direction == "YES" else "🔴" if signal.direction == "NO" else "⚪"
        confidence_bar = "█" * (signal.confidence // 10) + "░" * (10 - signal.confidence // 10)
        
        message = f"""
{emoji} *NEW TRADING SIGNAL*

📊 *Market:* {signal.market_name[:60]}...

📰 *News:* {signal.news_title[:80]}
_Source: {signal.news_source}_

🎯 *Direction:* *{signal.direction}*
📈 *Confidence:* {signal.confidence}%
{confidence_bar}

💡 *Reasoning:*
{signal.reasoning[:200]}...

⏰ {signal.timestamp[:19]}
"""
        
        sent_count = 0
        for user in users:
            # Only send if confidence meets threshold (default 70)
            if signal.confidence >= getattr(user, 'score_threshold', 70):
                try:
                    await self.bot.send_message(
                        chat_id=user.user_id,
                        text=message.strip(),
                        parse_mode="Markdown",
                        disable_web_page_preview=True
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error("signal_broadcast_error", user_id=user.user_id, error=str(e))
        
        logger.info("signal_broadcast_complete", 
                   market=signal.market_id,
                   direction=signal.direction,
                   sent_to=sent_count)
        
        return sent_count
    
    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /stats - mostra performance dos sinais."""
        try:
            stats = await self.performance_tracker.get_performance_stats()
            message = self.performance_tracker.format_stats_telegram(stats)
            
            # Add trigger breakdown if available
            trigger_stats = await self.performance_tracker.get_stats_by_trigger()
            if trigger_stats:
                message += "\n\n**📊 By Trigger Type:**"
                for trigger, data in trigger_stats.items():
                    if data['total'] > 0:
                        emoji = "🐋" if trigger == "whale" else "📰"
                        message += f"\n{emoji} {trigger.upper()}: {data['win_rate']}% win ({data['wins']}/{data['total']})"
            
            await update.message.reply_text(message, parse_mode="Markdown")
            
        except Exception as e:
            logger.error("stats_command_error", error=str(e))
            await update.message.reply_text(
                "❌ Erro ao obter estatísticas. Tenta novamente mais tarde."
            )
