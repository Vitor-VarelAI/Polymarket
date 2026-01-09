"""
ExaSignal - Weather Value Scanner (Meteorological Bot Strategy)
Finds undervalued weather markets for $1 bets.

Strategy (inspired by the meteorological bot):
- Only bet on outcomes with odds ≤10¢ (10% or less)
- Use MULTIPLE weather APIs for consensus forecasting
- Focus on daily weather markets (quick resolution)
- $1 bets = 10 shares at 10¢ each
- High risk, high reward (18,000%+ possible)

Weather Data Sources (Multi-API Consensus):
1. Tomorrow.io - Best accuracy, hourly data
2. OpenWeatherMap - Global coverage
3. WeatherAPI.com - Very accurate
4. Open-Meteo - Free fallback

Flow:
1. Fetch weather markets from Polymarket
2. Get consensus forecasts from MULTIPLE sources
3. Compare market odds vs forecast probability
4. Alert when market is underpriced (cheap outcome + higher real probability)
"""
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Tuple
from datetime import datetime, timezone, timedelta
import json
import re

from src.api.weather_client import WeatherClient, ConsensusForecast
from src.utils.logger import logger


@dataclass
class WeatherForecast:
    """Weather forecast data."""
    location: str
    date: str
    
    # Temperature
    temp_high: Optional[float] = None  # Celsius
    temp_low: Optional[float] = None
    temp_avg: Optional[float] = None
    
    # Precipitation
    precipitation_probability: Optional[float] = None  # 0-100
    precipitation_mm: Optional[float] = None
    
    # Conditions
    condition: str = ""  # "sunny", "cloudy", "rain", etc.
    
    # Source
    source: str = "open-meteo"


@dataclass
class WeatherBet:
    """A weather betting opportunity."""
    market_id: str
    market_name: str
    slug: str
    
    # What we're betting on
    bet_type: str  # "temperature", "precipitation", "condition"
    bet_target: str  # e.g., "temp > 80F", "rain > 0.1in"
    location: str
    resolve_date: str
    
    # Market odds
    market_odds: float  # Current market probability (%)
    entry_price: float  # Price in cents
    
    # Our forecast
    forecast_probability: float  # Our calculated probability (%)
    forecast_source: str
    forecast_data: Dict
    
    # Value calculation
    edge: float  # forecast_prob - market_odds (%)
    expected_value: float  # EV per $1 bet
    potential_return: float  # If we win, return per $1
    
    # Risk
    risk_level: str  # "extreme", "high", "medium"
    confidence: int  # 0-100
    
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> dict:
        return {
            "market_id": self.market_id,
            "market_name": self.market_name,
            "slug": self.slug,
            "bet_type": self.bet_type,
            "bet_target": self.bet_target,
            "location": self.location,
            "resolve_date": self.resolve_date,
            "market_odds": self.market_odds,
            "entry_price": self.entry_price,
            "forecast_probability": self.forecast_probability,
            "edge": self.edge,
            "expected_value": self.expected_value,
            "potential_return": self.potential_return,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }
    
    def to_telegram(self) -> str:
        """Format for Telegram notification with detailed context."""
        risk_emoji = {"extreme": "🔴", "high": "🟠", "medium": "🟡"}.get(self.risk_level, "⚪")
        
        # Calculate shares per $1
        shares_per_dollar = int(100 / self.entry_price) if self.entry_price > 0 else 0
        
        # Format forecast details
        forecast_high = self.forecast_data.get("high_f", "N/A")
        forecast_low = self.forecast_data.get("low_f", "N/A")
        target = self.forecast_data.get("target_f", "N/A")
        sources_count = self.forecast_data.get("num_sources", 1)
        agreement = self.forecast_data.get("agreement_score", 0)
        sources_list = self.forecast_data.get("sources_used", ["Open-Meteo"])
        
        sources_emoji = "🌡️" * min(sources_count, 4)
        
        return f"""
🌦️ *WEATHER VALUE BET* {risk_emoji}

📍 *Location:* {self.location}
📅 *Resolves:* {self.resolve_date}

📊 *Market Question:*
_{self.market_name[:70]}_

🎯 *Our Bet:* {self.bet_target}

━━━━━━━━━━━━━━━━━━━━━
💰 *TRADE DETAILS*
━━━━━━━━━━━━━━━━━━━━━
   Entry: *{self.entry_price:.1f}¢* per share
   $1 gets you: *{shares_per_dollar} shares*
   
   If you WIN: *${self.potential_return:.2f}*
   Profit: *{(self.potential_return - 1) * 100:.0f}%* 🎉

━━━━━━━━━━━━━━━━━━━━━
📡 *WEATHER FORECAST* {sources_emoji}
━━━━━━━━━━━━━━━━━━━━━
   🌡️ Tomorrow's High: *{forecast_high}°F*
   🌡️ Tomorrow's Low: *{forecast_low}°F*
   🎯 Target Temp: *{target}°F*
   
   Sources: {', '.join(sources_list)}
   Agreement: *{agreement:.0f}%*

━━━━━━━━━━━━━━━━━━━━━
⚖️ *EDGE ANALYSIS*
━━━━━━━━━━━━━━━━━━━━━
   Market says: {self.market_odds:.1f}%
   Our forecast: *{self.forecast_probability:.1f}%*
   🔥 *Edge: +{self.edge:.1f}%*

🎲 *Confidence:* {self.confidence}%
⚠️ *Risk Level:* {self.risk_level.upper()}

_Underdog bet - bet only what you can lose!_

🔗 [Open Market](https://polymarket.com/event/{self.slug})

⏰ {self.timestamp[:16]} UTC
"""


class WeatherValueScanner:
    """
    Scans for undervalued weather markets.
    
    Uses free weather APIs to identify when market odds
    are mispriced relative to actual forecast data.
    
    Strategy:
    - Only consider odds ≤10¢ (underdog bets)
    - Look for forecast probability > market probability
    - $1 bets on high-edge opportunities
    """
    
    def __init__(
        self,
        callback: Optional[Callable] = None,
        max_entry_price: float = 10.0,  # Max 10¢ per share
        min_edge: float = 5.0,  # Minimum 5% edge
        min_confidence: int = 60,
        scan_interval: int = 3600,  # 1 hour (weather updates)
    ):
        self.callback = callback
        self.max_entry_price = max_entry_price
        self.min_edge = min_edge
        self.min_confidence = min_confidence
        self.scan_interval = scan_interval
        
        # Multi-source weather client
        self.weather_client = WeatherClient()
        
        self.found_bets: List[WeatherBet] = []
        self.seen_markets: set = set()
        self._running = False
        
        # Major cities for weather markets
        self.city_coords = {
            "new york": (40.7128, -74.0060),
            "nyc": (40.7128, -74.0060),
            "los angeles": (34.0522, -118.2437),
            "la": (34.0522, -118.2437),
            "chicago": (41.8781, -87.6298),
            "miami": (25.7617, -80.1918),
            "dallas": (32.7767, -96.7970),
            "phoenix": (33.4484, -112.0740),
            "denver": (39.7392, -104.9903),
            "seattle": (47.6062, -122.3321),
            "atlanta": (33.7490, -84.3880),
            "boston": (42.3601, -71.0589),
            "washington": (38.9072, -77.0369),
            "dc": (38.9072, -77.0369),
            "san francisco": (37.7749, -122.4194),
            "sf": (37.7749, -122.4194),
            "las vegas": (36.1699, -115.1398),
            "vegas": (36.1699, -115.1398),
            "london": (51.5074, -0.1278),
            "paris": (48.8566, 2.3522),
            "tokyo": (35.6762, 139.6503),
            "houston": (29.7604, -95.3698),
            "philadelphia": (39.9526, -75.1652),
            "philly": (39.9526, -75.1652),
            "san diego": (32.7157, -117.1611),
            "austin": (30.2672, -97.7431),
            "orlando": (28.5383, -81.3792),
            "detroit": (42.3314, -83.0458),
            "minneapolis": (44.9778, -93.2650),
            "portland": (45.5152, -122.6784),
        }
        
        # Stats
        self.stats = {
            "scans": 0,
            "markets_checked": 0,
            "value_bets_found": 0,
            "weather_api_calls": 0,
            "sources_used": [],
        }
        
        logger.info("weather_scanner_initialized",
                   sources=self.weather_client.sources_available,
                   cities_supported=len(self.city_coords))
    
    async def fetch_weather_forecast(self, lat: float, lon: float, days: int = 3) -> Optional[Dict]:
        """
        Fetch weather forecast from Open-Meteo (free, no API key).
        
        Returns forecast for the next N days.
        """
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Open-Meteo free API
                url = "https://api.open-meteo.com/v1/forecast"
                params = {
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
                    "timezone": "auto",
                    "forecast_days": days
                }
                
                r = await client.get(url, params=params)
                
                if r.status_code == 200:
                    self.stats["weather_api_calls"] += 1
                    return r.json()
        
        except Exception as e:
            logger.error("weather_api_error", error=str(e))
        
        return None
    
    def parse_location_from_market(self, market_name: str) -> Optional[Tuple[str, float, float]]:
        """Extract location from market name and return coordinates."""
        market_lower = market_name.lower()
        
        for city, (lat, lon) in self.city_coords.items():
            if city in market_lower:
                return (city.title(), lat, lon)
        
        return None
    
    def parse_temperature_target(self, market_name: str) -> Optional[Tuple[str, float]]:
        """
        Extract temperature target from market name.
        
        Examples:
        - "NYC temp above 80°F" -> ("above", 80)
        - "Will LA high be over 90" -> ("above", 90)
        - "Temperature below 50°F" -> ("below", 50)
        """
        market_lower = market_name.lower()
        
        # Pattern: "above/over/exceed X" or "below/under X"
        patterns = [
            (r'above\s+(\d+)', "above"),
            (r'over\s+(\d+)', "above"),
            (r'exceed\s+(\d+)', "above"),
            (r'reach\s+(\d+)', "above"),
            (r'hit\s+(\d+)', "above"),
            (r'below\s+(\d+)', "below"),
            (r'under\s+(\d+)', "below"),
            (r'(\d+)\s*°?\s*f', None),  # Generic temp mention
        ]
        
        for pattern, direction in patterns:
            match = re.search(pattern, market_lower)
            if match:
                temp = float(match.group(1))
                # Infer direction from context if not explicit
                if direction is None:
                    if "above" in market_lower or "over" in market_lower or "high" in market_lower:
                        direction = "above"
                    else:
                        direction = "below"
                return (direction, temp)
        
        return None
    
    def calculate_temperature_probability(
        self, 
        forecast_high: float, 
        forecast_low: float,
        target_temp: float,
        direction: str
    ) -> float:
        """
        Calculate probability of temperature being above/below target.
        
        Uses normal distribution assumption around forecast.
        """
        import math
        
        # Assume actual temp follows normal distribution
        # Mean = forecast, std dev = ~3°F (typical forecast error)
        forecast_avg = (forecast_high + forecast_low) / 2
        std_dev = 3.0  # Fahrenheit
        
        # For "above" target, calculate P(temp > target)
        # Using simplified normal CDF approximation
        z = (target_temp - forecast_high) / std_dev
        
        # Simple approximation of normal CDF
        if direction == "above":
            # P(temp > target) when forecast_high is our reference
            if forecast_high >= target_temp:
                # Forecast already above target
                prob = 80 + min(20, (forecast_high - target_temp) * 5)
            else:
                # Forecast below target
                diff = target_temp - forecast_high
                prob = max(5, 50 - diff * 10)
        else:  # below
            if forecast_low <= target_temp:
                prob = 80 + min(20, (target_temp - forecast_low) * 5)
            else:
                diff = forecast_low - target_temp
                prob = max(5, 50 - diff * 10)
        
        return min(95, max(5, prob))
    
    async def fetch_weather_markets(self, limit: int = 100) -> List[dict]:
        """Fetch weather-related markets from Polymarket."""
        import httpx
        
        markets = []
        
        # Weather-related keywords
        weather_keywords = [
            "temperature", "temp", "weather", "rain", "precipitation",
            "snow", "heat", "cold", "high", "low", "fahrenheit", "celsius",
            "°f", "°c", "degrees"
        ]
        
        try:
            async with httpx.AsyncClient(
                base_url="https://gamma-api.polymarket.com",
                timeout=60
            ) as client:
                # Fetch active markets
                r = await client.get("/markets", params={
                    "limit": 500,
                    "closed": "false",
                    "order": "createdAt",
                    "ascending": "false"
                })
                
                if r.status_code == 200:
                    data = r.json()
                    
                    for m in data:
                        question = (m.get("question", "") or "").lower()
                        
                        # Check if weather-related
                        if any(kw in question for kw in weather_keywords):
                            try:
                                prices = m.get("outcomePrices", "[]")
                                if isinstance(prices, str):
                                    prices = json.loads(prices)
                                
                                yes_price = float(prices[0]) * 100 if prices else None
                            except:
                                continue
                            
                            if yes_price is None:
                                continue
                            
                            markets.append({
                                "id": m.get("conditionId", m.get("id", "")),
                                "slug": m.get("slug", ""),
                                "name": m.get("question", ""),
                                "yes_odds": yes_price,
                                "no_odds": 100 - yes_price,
                                "liquidity": float(m.get("liquidity", 0) or 0),
                                "end_date": m.get("endDate", ""),
                            })
                
                # Also check events
                r = await client.get("/events", params={
                    "limit": 200,
                    "active": "true"
                })
                
                if r.status_code == 200:
                    events = r.json()
                    seen_ids = {m["id"] for m in markets}
                    
                    for e in events:
                        title = (e.get("title", "") or "").lower()
                        
                        if any(kw in title for kw in weather_keywords):
                            for m in e.get("markets", []):
                                if m.get("conditionId") in seen_ids:
                                    continue
                                
                                try:
                                    prices = m.get("outcomePrices", "[]")
                                    if isinstance(prices, str):
                                        prices = json.loads(prices)
                                    yes_price = float(prices[0]) * 100 if prices else None
                                except:
                                    continue
                                
                                if yes_price is None:
                                    continue
                                
                                markets.append({
                                    "id": m.get("conditionId", ""),
                                    "slug": e.get("slug", ""),
                                    "name": m.get("question", e.get("title", "")),
                                    "yes_odds": yes_price,
                                    "no_odds": 100 - yes_price,
                                    "liquidity": float(m.get("liquidity", 0) or 0),
                                    "end_date": m.get("endDate", ""),
                                })
        
        except Exception as e:
            logger.error("fetch_weather_markets_error", error=str(e))
        
        logger.info("weather_markets_fetched", count=len(markets))
        return markets[:limit]
    
    async def analyze_market(self, market: dict) -> Optional[WeatherBet]:
        """Analyze a weather market for value betting opportunity using multi-source consensus."""
        market_name = market.get("name", "")
        yes_odds = market.get("yes_odds", 50)
        no_odds = market.get("no_odds", 50)
        
        # Determine which side is the underdog (≤10¢)
        if yes_odds <= self.max_entry_price:
            bet_side = "YES"
            entry_price = yes_odds
            market_prob = yes_odds
        elif no_odds <= self.max_entry_price:
            bet_side = "NO"
            entry_price = no_odds
            market_prob = no_odds
        else:
            # No cheap underdog bet available
            return None
        
        # Extract location
        location_data = self.parse_location_from_market(market_name)
        if not location_data:
            return None
        
        city, lat, lon = location_data
        
        # Extract temperature target
        temp_data = self.parse_temperature_target(market_name)
        if not temp_data:
            # TODO: Add precipitation parsing
            return None
        
        direction, target_temp = temp_data
        
        # Fetch CONSENSUS weather forecast from MULTIPLE sources
        consensus = await self.weather_client.get_forecast(lat, lon)
        
        if consensus.num_sources == 0:
            return None
        
        self.stats["weather_api_calls"] += consensus.num_sources
        self.stats["sources_used"] = consensus.sources_used
        
        # Use consensus temperatures (already in Fahrenheit)
        forecast_high_f = consensus.temp_high_f
        forecast_low_f = consensus.temp_low_f
        
        # Calculate our probability estimate
        forecast_prob = self.calculate_temperature_probability(
            forecast_high_f, forecast_low_f, target_temp, direction
        )
        
        # Boost confidence based on source agreement
        agreement_bonus = (consensus.agreement_score / 100) * 20  # Up to +20
        source_bonus = min(15, consensus.num_sources * 5)  # +5 per source, max +15
        
        # Adjust for bet side
        if bet_side == "NO":
            forecast_prob = 100 - forecast_prob
        
        # Calculate edge
        edge = forecast_prob - market_prob
        
        if edge < self.min_edge:
            return None
        
        # Calculate expected value per $1 bet
        shares_per_dollar = 100 / entry_price if entry_price > 0 else 0
        win_payout = shares_per_dollar * 1  # $1 per share if wins
        
        # EV = P(win) × payout - P(lose) × bet
        ev = (forecast_prob / 100 * win_payout) - ((100 - forecast_prob) / 100 * 1)
        
        # Potential return if wins
        potential_return = win_payout
        
        # Confidence based on edge, agreement, and number of sources
        base_confidence = 40 + edge
        confidence = min(95, int(base_confidence + agreement_bonus + source_bonus))
        
        # Risk level - lower if many sources agree
        if entry_price <= 3:
            risk_level = "extreme"
        elif entry_price <= 7:
            risk_level = "high"
        else:
            risk_level = "medium"
        
        # Lower risk if high source agreement
        if consensus.agreement_score >= 90 and risk_level == "high":
            risk_level = "medium"
        
        if confidence < self.min_confidence:
            return None
        
        # Build rich forecast data for Telegram
        forecast_data = {
            "high_f": round(forecast_high_f, 1),
            "low_f": round(forecast_low_f, 1),
            "target_f": target_temp,
            "direction": direction,
            "num_sources": consensus.num_sources,
            "sources_used": consensus.sources_used,
            "agreement_score": consensus.agreement_score,
            "temp_spread": consensus.temp_spread,
        }
        
        # Add individual source data for transparency
        for f in consensus.individual_forecasts:
            forecast_data[f"source_{f.source.lower().replace('.', '_')}"] = {
                "high": f.temp_high_f,
                "low": f.temp_low_f,
            }
        
        return WeatherBet(
            market_id=market.get("id", ""),
            market_name=market_name,
            slug=market.get("slug", ""),
            bet_type="temperature",
            bet_target=f"Temp {direction} {target_temp}°F ({bet_side})",
            location=city,
            resolve_date=market.get("end_date", "")[:10],
            market_odds=market_prob,
            entry_price=entry_price,
            forecast_probability=forecast_prob,
            forecast_source=f"{consensus.num_sources} sources",
            forecast_data=forecast_data,
            edge=edge,
            expected_value=ev,
            potential_return=potential_return,
            risk_level=risk_level,
            confidence=confidence,
        )
    
    async def scan_once(self) -> List[WeatherBet]:
        """Run a single scan for weather value bets."""
        logger.info("weather_scan_starting")
        self.stats["scans"] += 1
        
        # Fetch weather markets
        markets = await self.fetch_weather_markets()
        self.stats["markets_checked"] += len(markets)
        
        value_bets = []
        
        for market in markets:
            market_id = market.get("id", "")
            
            # Skip already seen
            if market_id in self.seen_markets:
                continue
            
            bet = await self.analyze_market(market)
            
            if bet:
                value_bets.append(bet)
                self.seen_markets.add(market_id)
                self.stats["value_bets_found"] += 1
                
                # Callback
                if self.callback:
                    try:
                        await self.callback(bet)
                    except Exception as e:
                        logger.error("weather_callback_error", error=str(e))
                
                logger.info("weather_value_bet_found",
                           market=market.get("name", "")[:40],
                           entry_price=bet.entry_price,
                           edge=bet.edge,
                           potential_return=bet.potential_return)
            
            # Small delay between API calls
            await asyncio.sleep(0.3)
        
        # Keep seen set manageable
        if len(self.seen_markets) > 500:
            self.seen_markets = set(list(self.seen_markets)[-250:])
        
        # Keep recent bets
        self.found_bets = (value_bets + self.found_bets)[:30]
        
        logger.info("weather_scan_complete",
                   markets_checked=len(markets),
                   value_bets=len(value_bets))
        
        return value_bets
    
    async def start_monitoring(self):
        """Start continuous monitoring loop."""
        self._running = True
        logger.info("weather_scanner_started",
                   max_entry_price=self.max_entry_price,
                   min_edge=self.min_edge,
                   scan_interval=self.scan_interval)
        
        while self._running:
            try:
                await self.scan_once()
            except Exception as e:
                logger.error("weather_monitor_error", error=str(e))
            
            await asyncio.sleep(self.scan_interval)
    
    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self._running = False
        logger.info("weather_scanner_stopped")
    
    def get_status(self) -> dict:
        """Get scanner status."""
        return {
            "running": self._running,
            "recent_bets": len(self.found_bets),
            "seen_markets": len(self.seen_markets),
            "max_entry_price": self.max_entry_price,
            "min_edge": self.min_edge,
            "scan_interval": self.scan_interval,
            "stats": self.stats,
        }
