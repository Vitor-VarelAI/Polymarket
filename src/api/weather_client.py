"""
ExaSignal - Multi-Source Weather Client
Combines 3 weather APIs for consensus-based forecasting.

Sources:
1. Tomorrow.io - Best accuracy, hourly data
2. OpenWeatherMap - Global coverage, good for most locations
3. WeatherAPI.com - Very accurate, good historical data

Strategy:
- Query all available sources in parallel
- Calculate consensus (average) temperature
- Use confidence from source agreement
- Fallback to Open-Meteo if no API keys configured
"""
import asyncio
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone

from src.utils.logger import logger


@dataclass
class WeatherForecast:
    """Standardized weather forecast from any source."""
    source: str
    location: str
    date: str
    
    # Temperature (always in Fahrenheit)
    temp_high_f: float
    temp_low_f: float
    temp_avg_f: float
    
    # Precipitation
    precipitation_chance: float  # 0-100 %
    precipitation_inches: float
    
    # Conditions
    condition: str  # "sunny", "cloudy", "rain", "snow", etc.
    humidity: float  # 0-100 %
    
    # Confidence
    source_confidence: float = 0.8  # How reliable is this source
    
    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "location": self.location,
            "date": self.date,
            "temp_high_f": self.temp_high_f,
            "temp_low_f": self.temp_low_f,
            "temp_avg_f": self.temp_avg_f,
            "precipitation_chance": self.precipitation_chance,
            "precipitation_inches": self.precipitation_inches,
            "condition": self.condition,
            "humidity": self.humidity,
        }


@dataclass
class ConsensusForecast:
    """Combined forecast from multiple sources."""
    location: str
    date: str
    
    # Consensus temperatures (weighted average)
    temp_high_f: float
    temp_low_f: float
    temp_avg_f: float
    
    # Consensus precipitation
    precipitation_chance: float
    precipitation_inches: float
    
    # Agreement stats
    num_sources: int
    sources_used: List[str]
    temp_spread: float  # Max - Min across sources
    agreement_score: float  # 0-100, how much sources agree
    
    # Individual forecasts
    individual_forecasts: List[WeatherForecast] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "location": self.location,
            "date": self.date,
            "temp_high_f": self.temp_high_f,
            "temp_low_f": self.temp_low_f,
            "temp_avg_f": self.temp_avg_f,
            "precipitation_chance": self.precipitation_chance,
            "precipitation_inches": self.precipitation_inches,
            "num_sources": self.num_sources,
            "sources_used": self.sources_used,
            "temp_spread": self.temp_spread,
            "agreement_score": self.agreement_score,
        }


class WeatherClient:
    """
    Multi-source weather client for accurate forecasting.
    
    Combines Tomorrow.io, OpenWeatherMap, and WeatherAPI.com
    with Open-Meteo as a free fallback.
    """
    
    def __init__(self):
        """Initialize with API keys from environment."""
        self.tomorrow_key = os.getenv("TOMORROW_API_KEY", "")
        self.openweather_key = os.getenv("OPENWEATHER_API_KEY", "")
        self.weatherapi_key = os.getenv("WEATHERAPI_KEY", "")
        
        # Check which sources are available
        self.sources_available = []
        if self.tomorrow_key and self.tomorrow_key != "your_tomorrow_api_key_here":
            self.sources_available.append("tomorrow")
        if self.openweather_key and self.openweather_key != "your_openweather_api_key_here":
            self.sources_available.append("openweather")
        if self.weatherapi_key and self.weatherapi_key != "your_weatherapi_key_here":
            self.sources_available.append("weatherapi")
        
        # Always have Open-Meteo as fallback
        self.sources_available.append("open-meteo")
        
        logger.info("weather_client_initialized", 
                   sources=self.sources_available,
                   has_premium=len(self.sources_available) > 1)
    
    async def _fetch_tomorrow(self, lat: float, lon: float) -> Optional[WeatherForecast]:
        """Fetch from Tomorrow.io API."""
        if not self.tomorrow_key:
            return None
        
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = "https://api.tomorrow.io/v4/weather/forecast"
                params = {
                    "location": f"{lat},{lon}",
                    "apikey": self.tomorrow_key,
                    "units": "imperial",
                    "timesteps": "1d"
                }
                
                r = await client.get(url, params=params)
                
                if r.status_code == 200:
                    data = r.json()
                    daily = data.get("timelines", {}).get("daily", [])
                    
                    if daily:
                        day = daily[0].get("values", {})
                        
                        return WeatherForecast(
                            source="Tomorrow.io",
                            location=f"{lat},{lon}",
                            date=daily[0].get("time", "")[:10],
                            temp_high_f=day.get("temperatureMax", 70),
                            temp_low_f=day.get("temperatureMin", 50),
                            temp_avg_f=(day.get("temperatureMax", 70) + day.get("temperatureMin", 50)) / 2,
                            precipitation_chance=day.get("precipitationProbabilityAvg", 0),
                            precipitation_inches=day.get("precipitationIntensityAvg", 0) * 0.0394,  # mm to inches
                            condition=self._map_tomorrow_condition(day.get("weatherCodeMax", 1000)),
                            humidity=day.get("humidityAvg", 50),
                            source_confidence=0.95,  # Tomorrow.io is very accurate
                        )
        except Exception as e:
            logger.error("tomorrow_api_error", error=str(e))
        
        return None
    
    def _map_tomorrow_condition(self, code: int) -> str:
        """Map Tomorrow.io weather code to condition string."""
        if code <= 1000:
            return "clear"
        elif code <= 1100:
            return "partly_cloudy"
        elif code <= 2000:
            return "cloudy"
        elif code <= 4000:
            return "fog"
        elif code <= 5000:
            return "drizzle"
        elif code <= 6000:
            return "rain"
        elif code <= 7000:
            return "snow"
        else:
            return "unknown"
    
    async def _fetch_openweather(self, lat: float, lon: float) -> Optional[WeatherForecast]:
        """Fetch from OpenWeatherMap API."""
        if not self.openweather_key:
            return None
        
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = "https://api.openweathermap.org/data/2.5/forecast"
                params = {
                    "lat": lat,
                    "lon": lon,
                    "appid": self.openweather_key,
                    "units": "imperial",
                    "cnt": 8  # 24 hours of 3-hour forecasts
                }
                
                r = await client.get(url, params=params)
                
                if r.status_code == 200:
                    data = r.json()
                    forecasts = data.get("list", [])
                    
                    if forecasts:
                        # Calculate daily high/low from 3-hour forecasts
                        temps = [f.get("main", {}).get("temp", 70) for f in forecasts]
                        precip_probs = [f.get("pop", 0) * 100 for f in forecasts]
                        
                        return WeatherForecast(
                            source="OpenWeatherMap",
                            location=f"{lat},{lon}",
                            date=forecasts[0].get("dt_txt", "")[:10],
                            temp_high_f=max(temps),
                            temp_low_f=min(temps),
                            temp_avg_f=sum(temps) / len(temps),
                            precipitation_chance=max(precip_probs),
                            precipitation_inches=0,  # Not easily available
                            condition=forecasts[0].get("weather", [{}])[0].get("main", "Clear").lower(),
                            humidity=forecasts[0].get("main", {}).get("humidity", 50),
                            source_confidence=0.85,
                        )
        except Exception as e:
            logger.error("openweather_api_error", error=str(e))
        
        return None
    
    async def _fetch_weatherapi(self, lat: float, lon: float) -> Optional[WeatherForecast]:
        """Fetch from WeatherAPI.com."""
        if not self.weatherapi_key:
            return None
        
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = "http://api.weatherapi.com/v1/forecast.json"
                params = {
                    "key": self.weatherapi_key,
                    "q": f"{lat},{lon}",
                    "days": 2,
                    "aqi": "no",
                }
                
                r = await client.get(url, params=params)
                
                if r.status_code == 200:
                    data = r.json()
                    forecast_days = data.get("forecast", {}).get("forecastday", [])
                    
                    if forecast_days:
                        # Use tomorrow's forecast (index 1) or today if not available
                        day_data = forecast_days[1] if len(forecast_days) > 1 else forecast_days[0]
                        day = day_data.get("day", {})
                        
                        return WeatherForecast(
                            source="WeatherAPI",
                            location=f"{lat},{lon}",
                            date=day_data.get("date", ""),
                            temp_high_f=day.get("maxtemp_f", 70),
                            temp_low_f=day.get("mintemp_f", 50),
                            temp_avg_f=day.get("avgtemp_f", 60),
                            precipitation_chance=day.get("daily_chance_of_rain", 0),
                            precipitation_inches=day.get("totalprecip_in", 0),
                            condition=day.get("condition", {}).get("text", "Clear").lower(),
                            humidity=day.get("avghumidity", 50),
                            source_confidence=0.90,
                        )
        except Exception as e:
            logger.error("weatherapi_error", error=str(e))
        
        return None
    
    async def _fetch_openmeteo(self, lat: float, lon: float) -> Optional[WeatherForecast]:
        """Fetch from Open-Meteo (free, no API key)."""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = "https://api.open-meteo.com/v1/forecast"
                params = {
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
                    "timezone": "auto",
                    "forecast_days": 2,
                    "temperature_unit": "fahrenheit"
                }
                
                r = await client.get(url, params=params)
                
                if r.status_code == 200:
                    data = r.json()
                    daily = data.get("daily", {})
                    
                    # Use tomorrow's forecast (index 1)
                    idx = 1 if len(daily.get("temperature_2m_max", [])) > 1 else 0
                    
                    temp_high = daily.get("temperature_2m_max", [70])[idx]
                    temp_low = daily.get("temperature_2m_min", [50])[idx]
                    
                    return WeatherForecast(
                        source="Open-Meteo",
                        location=f"{lat},{lon}",
                        date=daily.get("time", [""])[idx],
                        temp_high_f=temp_high,
                        temp_low_f=temp_low,
                        temp_avg_f=(temp_high + temp_low) / 2,
                        precipitation_chance=daily.get("precipitation_probability_max", [0])[idx],
                        precipitation_inches=daily.get("precipitation_sum", [0])[idx] * 0.0394,
                        condition="unknown",  # Open-Meteo doesn't provide condition text
                        humidity=50,  # Not available in basic API
                        source_confidence=0.75,  # Free tier, less reliable
                    )
        except Exception as e:
            logger.error("openmeteo_api_error", error=str(e))
        
        return None
    
    async def get_forecast(self, lat: float, lon: float) -> ConsensusForecast:
        """
        Get consensus forecast from all available sources.
        
        Returns weighted average with agreement scoring.
        """
        # Fetch from all sources in parallel
        tasks = []
        
        if "tomorrow" in self.sources_available:
            tasks.append(("tomorrow", self._fetch_tomorrow(lat, lon)))
        if "openweather" in self.sources_available:
            tasks.append(("openweather", self._fetch_openweather(lat, lon)))
        if "weatherapi" in self.sources_available:
            tasks.append(("weatherapi", self._fetch_weatherapi(lat, lon)))
        if "open-meteo" in self.sources_available:
            tasks.append(("open-meteo", self._fetch_openmeteo(lat, lon)))
        
        # Execute all in parallel
        results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
        
        # Collect successful forecasts
        forecasts: List[WeatherForecast] = []
        for i, result in enumerate(results):
            if isinstance(result, WeatherForecast):
                forecasts.append(result)
        
        if not forecasts:
            # Return a default forecast if all sources failed
            logger.error("all_weather_sources_failed", lat=lat, lon=lon)
            return ConsensusForecast(
                location=f"{lat},{lon}",
                date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                temp_high_f=70,
                temp_low_f=50,
                temp_avg_f=60,
                precipitation_chance=20,
                precipitation_inches=0,
                num_sources=0,
                sources_used=[],
                temp_spread=0,
                agreement_score=0,
            )
        
        # Calculate weighted consensus
        total_weight = sum(f.source_confidence for f in forecasts)
        
        temp_high = sum(f.temp_high_f * f.source_confidence for f in forecasts) / total_weight
        temp_low = sum(f.temp_low_f * f.source_confidence for f in forecasts) / total_weight
        temp_avg = sum(f.temp_avg_f * f.source_confidence for f in forecasts) / total_weight
        precip_chance = sum(f.precipitation_chance * f.source_confidence for f in forecasts) / total_weight
        precip_inches = sum(f.precipitation_inches * f.source_confidence for f in forecasts) / total_weight
        
        # Calculate agreement (spread in temperatures)
        temp_highs = [f.temp_high_f for f in forecasts]
        temp_spread = max(temp_highs) - min(temp_highs) if temp_highs else 0
        
        # Agreement score: 100 if all agree exactly, lower as spread increases
        # Assume 10°F spread = 50% agreement
        agreement_score = max(0, 100 - (temp_spread * 5))
        
        consensus = ConsensusForecast(
            location=f"{lat},{lon}",
            date=forecasts[0].date,
            temp_high_f=round(temp_high, 1),
            temp_low_f=round(temp_low, 1),
            temp_avg_f=round(temp_avg, 1),
            precipitation_chance=round(precip_chance, 1),
            precipitation_inches=round(precip_inches, 2),
            num_sources=len(forecasts),
            sources_used=[f.source for f in forecasts],
            temp_spread=round(temp_spread, 1),
            agreement_score=round(agreement_score, 1),
            individual_forecasts=forecasts,
        )
        
        logger.info("consensus_forecast_generated",
                   location=f"{lat},{lon}",
                   sources=len(forecasts),
                   temp_high=temp_high,
                   agreement=agreement_score)
        
        return consensus
    
    def format_forecast_telegram(self, forecast: ConsensusForecast) -> str:
        """Format consensus forecast for Telegram."""
        sources_emoji = "🌡️" * min(forecast.num_sources, 4)
        
        individual = ""
        for f in forecast.individual_forecasts:
            individual += f"\n   • {f.source}: {f.temp_high_f:.0f}°F high"
        
        return f"""
📡 *Weather Forecast Consensus*
{sources_emoji}

📍 *Location:* {forecast.location}
📅 *Date:* {forecast.date}

🌡️ *Temperature:*
   High: *{forecast.temp_high_f:.0f}°F*
   Low: *{forecast.temp_low_f:.0f}°F*
   Avg: {forecast.temp_avg_f:.0f}°F

🌧️ *Precipitation:*
   Chance: {forecast.precipitation_chance:.0f}%
   Expected: {forecast.precipitation_inches:.2f}"

📊 *Reliability:*
   Sources: {forecast.num_sources}
   Spread: ±{forecast.temp_spread:.0f}°F
   Agreement: {forecast.agreement_score:.0f}%

🔍 *Individual Forecasts:*{individual}
"""
