"""
ExaSignal - Modelo de Evento Whale
Baseado em PRD-02-Whale-Event-Detection

Extended with:
- BetTimingProfile: Classifies whale betting timing (early/momentum/sniper)
- Category Specialization: Tracks whale performance per market category
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ============================================================
# Timing Profile
# ============================================================

@dataclass
class BetTimingProfile:
    """
    Classifies whale betting timing patterns.
    
    Types:
    - EARLY_BIRD: Bets very early (>30 days before close)
    - MOMENTUM: Bets after news (7-30 days before close)
    - SNIPER: Bets close to resolution (<7 days)
    """
    avg_days_before_close: float = 0.0
    total_bets_analyzed: int = 0
    
    @property
    def timing_type(self) -> str:
        """Classify timing based on average days before close."""
        if self.avg_days_before_close > 30:
            return "🔮 EARLY_BIRD"
        elif self.avg_days_before_close > 7:
            return "⚡ MOMENTUM"
        else:
            return "🎯 SNIPER"
    
    @property
    def timing_description(self) -> str:
        """Human-readable description."""
        t = self.timing_type
        if "EARLY_BIRD" in t:
            return f"Bets early (avg {self.avg_days_before_close:.0f}d before close)"
        elif "MOMENTUM" in t:
            return f"Bets on momentum (avg {self.avg_days_before_close:.0f}d before close)"
        else:
            return f"Sniper (avg {self.avg_days_before_close:.0f}d before close)"


# ============================================================
# Category Performance
# ============================================================

@dataclass
class CategoryPerformance:
    """Win rate tracking for a specific category."""
    category: str
    total_bets: int = 0
    wins: int = 0
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate as percentage."""
        if self.total_bets == 0:
            return 0.0
        return (self.wins / self.total_bets) * 100


# ============================================================
# Enhanced Whale Profile
# ============================================================

@dataclass
class WhaleProfile:
    """
    Enhanced whale profile with timing and category specialization.
    
    Usage:
    - Check timing_profile.timing_type for betting style
    - Check specialty_category for best performing category
    - Use is_relevant_for_category() to filter by market
    """
    wallet_address: str
    total_trades: int = 0
    total_volume_usd: float = 0.0
    win_rate: float = 0.0  # 0-100%
    avg_position_size: float = 0.0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    markets_traded: int = 0
    
    # === NEW: Timing Profile ===
    timing_profile: Optional[BetTimingProfile] = None
    
    # === NEW: Category Performance ===
    category_stats: Dict[str, CategoryPerformance] = field(default_factory=dict)
    
    # === NEW: Directional Bias ===
    yes_bets: int = 0
    no_bets: int = 0
    
    # === NEW: Smart Money Score (from leaderboard) ===
    smart_score: int = 0  # 0-100, from SmartMoneyService
    leaderboard_rank: Optional[int] = None  # Rank on Polymarket leaderboard
    is_smart_money: bool = False  # True if in top traders list
    
    @property
    def profile_type(self) -> str:
        """Classifica o tipo de whale."""
        if self.total_trades >= 50 and self.win_rate >= 70:
            return "🦈 SHARK"  # High-frequency winner
        elif self.total_volume_usd >= 500_000:
            return "🐋 MEGA WHALE"
        elif self.total_volume_usd >= 100_000:
            return "🐳 WHALE"
        elif self.total_trades >= 20:
            return "🐬 DOLPHIN"
        return "🐟 NEW TRADER"
    
    @property
    def risk_level(self) -> str:
        """Avalia confiabilidade do trader."""
        if self.win_rate >= 70 and self.total_trades >= 10:
            return "🟢 HIGH"
        elif self.win_rate >= 50:
            return "🟡 MEDIUM"
        return "🔴 LOW"
    
    @property
    def directional_bias_score(self) -> float:
        """
        Calculates directional bias: -1 (all NO) to +1 (all YES).
        
        Score between -0.6 and 0.6 is considered balanced.
        """
        total = self.yes_bets + self.no_bets
        if total == 0:
            return 0.0
        return (self.yes_bets - self.no_bets) / total
    
    @property
    def is_one_sided(self) -> bool:
        """True if whale only bets one direction (bias > 0.8 or < -0.8)."""
        return abs(self.directional_bias_score) > 0.8
    
    @property
    def specialty_category(self) -> Optional[str]:
        """Returns category where whale has best win rate (min 5 bets)."""
        if not self.category_stats:
            return None
        
        # Filter categories with at least 5 bets
        qualified = [
            cat for cat in self.category_stats.values()
            if cat.total_bets >= 5
        ]
        
        if not qualified:
            return None
        
        # Return highest win rate
        best = max(qualified, key=lambda x: x.win_rate)
        return best.category if best.win_rate >= 60 else None
    
    def get_category_win_rate(self, category: str) -> float:
        """Get win rate for specific category."""
        if category in self.category_stats:
            return self.category_stats[category].win_rate
        return 0.0
    
    def is_relevant_for_category(self, market_category: str) -> bool:
        """
        Check if whale is relevant for this market category.
        
        Relevant if:
        - Has specialty AND it matches market category
        - OR is MEGA_WHALE with 75%+ overall win rate
        - OR has no specialty (new whale, give benefit of doubt)
        """
        specialty = self.specialty_category
        
        # No specialty = allow (benefit of doubt)
        if specialty is None:
            return True
        
        # Specialty matches market
        if specialty.lower() == market_category.lower():
            return True
        
        # Mega whale exception with high win rate
        if "MEGA" in self.profile_type and self.win_rate >= 75:
            return True
        
        # Has specialty but doesn't match - less relevant
        return False
    
    def add_category_result(self, category: str, won: bool) -> None:
        """Record a bet result for category tracking."""
        if category not in self.category_stats:
            self.category_stats[category] = CategoryPerformance(category=category)
        
        self.category_stats[category].total_bets += 1
        if won:
            self.category_stats[category].wins += 1


# ============================================================
# Whale Event
# ============================================================

@dataclass
class WhaleEvent:
    """Representa um evento de whale detectado."""
    
    market_id: str
    direction: str  # "YES" ou "NO"
    size_usd: float
    wallet_address: str
    wallet_age_days: int  # Idade da wallet
    liquidity_ratio: float  # size_usd / liquidez_total
    timestamp: datetime
    is_new_position: bool
    previous_position_size: float = 0.0
    
    # Whale profile (optional, populated from history)
    profile: Optional[WhaleProfile] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte evento para dicionário JSON."""
        result = {
            "market_id": self.market_id,
            "direction": self.direction,
            "size_usd": self.size_usd,
            "wallet_address": self.wallet_address,
            "wallet_age_days": self.wallet_age_days,
            "liquidity_ratio": self.liquidity_ratio,
            "timestamp": self.timestamp.isoformat(),
            "is_new_position": self.is_new_position,
            "previous_position_size": self.previous_position_size,
        }
        
        if self.profile:
            result["profile"] = {
                "type": self.profile.profile_type,
                "total_trades": self.profile.total_trades,
                "win_rate": self.profile.win_rate,
                "risk_level": self.profile.risk_level,
                "timing_type": self.profile.timing_profile.timing_type if self.profile.timing_profile else None,
                "specialty_category": self.profile.specialty_category,
                "is_one_sided": self.profile.is_one_sided,
            }
        
        return result
    
    @property
    def size_formatted(self) -> str:
        """Retorna size formatado (ex: $25k)."""
        if self.size_usd >= 1_000_000:
            return f"${self.size_usd / 1_000_000:.1f}M"
        elif self.size_usd >= 1_000:
            return f"${self.size_usd / 1_000:.0f}k"
        return f"${self.size_usd:.0f}"
    
    @property
    def liquidity_percent(self) -> str:
        """Retorna ratio de liquidez em %."""
        return f"{self.liquidity_ratio * 100:.1f}%"
    
    @property
    def wallet_short(self) -> str:
        """Retorna endereço abreviado."""
        if len(self.wallet_address) > 12:
            return f"{self.wallet_address[:6]}...{self.wallet_address[-4:]}"
        return self.wallet_address
    
    def to_telegram_report(self, market_name: str = "", current_odds: float = None) -> str:
        """Gera relatório completo para Telegram."""
        emoji = "🟢" if self.direction == "YES" else "🔴"
        
        # Bet size prominence based on amount
        if self.size_usd >= 100_000:
            size_emoji = "🚨💰"
            size_label = "MASSIVE BET"
        elif self.size_usd >= 50_000:
            size_emoji = "💰💰"
            size_label = "HUGE BET"
        elif self.size_usd >= 25_000:
            size_emoji = "💰"
            size_label = "BIG BET"
        else:
            size_emoji = "💵"
            size_label = "BET"
        
        lines = [
            f"🐋 **WHALE ALERT** 🐋",
            "",
            f"{emoji} **{self.direction}** | {market_name or self.market_id}",
            "",
            f"{size_emoji} **{size_label}: {self.size_formatted}**",
            f"├ % of Liquidity: {self.liquidity_percent}",
            f"├ Position Type: {'🆕 New Position' if self.is_new_position else '📈 Top-up'}",
        ]
        
        # Add odds if available
        if current_odds:
            lines.append(f"└ Current Odds: {current_odds:.1f}%")
        
        lines.append("")
        
        # Enhanced whale profile section
        if self.profile:
            lines.extend([
                "**👤 WALLET PROFILE:**",
                f"├ Type: {self.profile.profile_type}",
            ])
            
            # Add smart money indicator if available
            if self.profile.is_smart_money:
                lines.append(f"├ 💎 SMART MONEY (Rank #{self.profile.leaderboard_rank})")
                lines.append(f"├ Smart Score: {self.profile.smart_score}/100")
            
            lines.extend([
                f"├ Total Trades: {self.profile.total_trades}",
                f"├ Win Rate: {self.profile.win_rate:.0f}%",
                f"├ Total Volume: ${self.profile.total_volume_usd:,.0f}",
                f"├ Avg Position: ${self.profile.avg_position_size:,.0f}",
                f"├ Reliability: {self.profile.risk_level}",
            ])
            
            # Add timing profile if available
            if self.profile.timing_profile:
                lines.append(f"├ Timing: {self.profile.timing_profile.timing_type}")
            
            # Add specialty if available
            if self.profile.specialty_category:
                lines.append(f"├ Specialty: {self.profile.specialty_category.upper()}")
            
            # Add one-sided warning
            if self.profile.is_one_sided:
                bias_dir = "YES" if self.profile.directional_bias_score > 0 else "NO"
                lines.append(f"├ ⚠️ One-sided: Always {bias_dir}")
            
            lines.append(f"└ Wallet: `{self.wallet_short}`")
            lines.append("")
        else:
            lines.extend([
                f"**👤 Wallet:** `{self.wallet_short}`",
                f"├ Days Inactive: {self.wallet_age_days}",
                f"└ Profile: 🐟 NEW (first time in this market)",
                "",
            ])
        
        # Links
        lines.append(f"🔗 [View on Polygonscan](https://polygonscan.com/address/{self.wallet_address})")
        lines.append("")
        lines.append(f"⏰ {self.timestamp.strftime('%Y-%m-%d %H:%M')}")
        
        return "\n".join(lines)
