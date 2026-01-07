"""
ExaSignal - FastAPI Backend para Dashboard
API REST para servir dados ao frontend Next.js

Endpoints:
- GET /api/markets - Lista mercados com odds
- GET /api/markets/{id} - Detalhe de um mercado
- GET /api/markets/{id}/investigate - Investigação profunda
"""
import asyncio
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.core.market_manager import MarketManager
from src.api.gamma_client import GammaClient
from src.api.exa_client import ExaClient
from src.api.groq_client import GroqClient
from src.api.newsapi_client import NewsAPIClient
from src.api.clob_client import clob
from src.core.research_agent import ResearchAgent
from src.core.signal_generator import SignalGenerator
from src.core.market_matcher import MarketMatcher
from src.core.news_monitor import NewsMonitor
from src.utils.logger import logger


# ============================================================================
# Models
# ============================================================================

class MarketResponse(BaseModel):
    id: str
    name: str
    slug: str
    category: str
    odds: Optional[float] = None
    interpretation: str = "Unknown"

class MarketDetailResponse(MarketResponse):
    liquidity: Optional[float] = None
    source_url: str = ""

class InvestigationResponse(BaseModel):
    market_name: str
    direction: str
    confidence: int
    key_findings: List[str]
    reasoning: str
    sources: List[dict]
    current_odds: Optional[float] = None


# ============================================================================
# Application
# ============================================================================

# Global state
state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources."""
    # Startup
    logger.info("api_starting")
    state["market_manager"] = MarketManager()
    state["gamma"] = GammaClient()
    state["exa"] = ExaClient()
    state["groq"] = GroqClient()
    state["newsapi"] = NewsAPIClient()
    state["research_agent"] = ResearchAgent(
        groq=state["groq"],
        exa=state["exa"],
        newsapi=state["newsapi"],
        gamma=state["gamma"]
    )
    
    # Search function for signal detection
    async def search_markets_for_signal(query: str, limit: int = 50):
        """Search Polymarket for signal matching - combines events + markets."""
        import httpx
        import asyncio
        
        async with httpx.AsyncClient(base_url="https://gamma-api.polymarket.com", timeout=60) as client:
            # Fetch both endpoints in parallel - ORDER BY startDate DESC for recent events!
            async def get_events():
                r = await client.get("/events", params={
                    "limit": 500, 
                    "active": "true",
                    "order": "startDate",
                    "ascending": "false"  # Most recent first!
                })
                return r.json() if r.status_code == 200 else []
            
            async def get_markets():
                r = await client.get("/markets", params={
                    "closed": "false", 
                    "limit": 500,
                    "order": "createdAt",
                    "ascending": "false"  # Most recent first!
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
            
            logger.info("signal_search", query=query, found=len(results), total=len(all_items))
            return results[:limit]
    
    # Signal detection system with ENRICHED PIPELINE
    state["signal_generator"] = SignalGenerator(state["groq"])
    state["news_monitor"] = NewsMonitor(
        newsapi=state["newsapi"],
        groq=state["groq"],
        gamma=state["gamma"],  # For fetching current odds
        search_func=search_markets_for_signal,
        min_score=70,       # Minimum composite score for alerts
        min_confidence=60,  # Minimum LLM confidence
        use_enriched=True,  # Use full research + scoring pipeline
    )
    
    logger.info("api_ready", markets=len(state["market_manager"].markets))
    
    yield
    
    # Shutdown
    state["news_monitor"].stop_monitoring()
    await state["gamma"].close()
    logger.info("api_stopped")

app = FastAPI(
    title="ExaSignal API",
    description="AI-powered prediction market analysis",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Helpers
# ============================================================================

def get_interpretation(odds: Optional[float]) -> str:
    """Convert odds to human-readable interpretation."""
    if odds is None:
        return "Unknown"
    if odds >= 70:
        return "Very Likely"
    elif odds >= 55:
        return "Likely"
    elif odds >= 45:
        return "Uncertain"
    elif odds >= 30:
        return "Unlikely"
    else:
        return "Very Unlikely"


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "markets": len(state["market_manager"].markets)}


@app.get("/api/markets", response_model=List[MarketResponse])
async def list_markets(category: Optional[str] = None):
    """List all monitored markets with current odds."""
    market_manager = state["market_manager"]
    gamma = state["gamma"]
    
    markets = market_manager.markets
    if category:
        markets = [m for m in markets if m.category.lower() == category.lower()]
    
    # Fetch odds for each market (in parallel)
    async def get_market_data(market):
        odds = await gamma.get_market_odds(market.market_id)
        return MarketResponse(
            id=market.market_id,
            name=market.market_name,
            slug=market.market_id,
            category=market.category,
            odds=round(odds, 1) if odds else None,
            interpretation=get_interpretation(odds)
        )
    
    results = await asyncio.gather(*[get_market_data(m) for m in markets])
    return results


@app.get("/api/markets/{market_id}", response_model=MarketDetailResponse)
async def get_market(market_id: str):
    """Get details for a specific market."""
    market_manager = state["market_manager"]
    gamma = state["gamma"]
    
    market = market_manager.get_market_by_id(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    odds = await gamma.get_market_odds(market_id)
    liquidity = await gamma.get_market_liquidity(market_id)
    
    return MarketDetailResponse(
        id=market.market_id,
        name=market.market_name,
        slug=market.market_id,
        category=market.category,
        odds=round(odds, 1) if odds else None,
        interpretation=get_interpretation(odds),
        liquidity=liquidity,
        source_url=f"https://polymarket.com/event/{market_id}" 
    )


@app.get("/api/markets/{market_id}/investigate", response_model=InvestigationResponse)
async def investigate_market(market_id: str):
    """Run deep AI investigation on a market."""
    market_manager = state["market_manager"]
    research_agent = state["research_agent"]
    
    market = market_manager.get_market_by_id(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    try:
        result = await research_agent.investigate(market)
        
        return InvestigationResponse(
            market_name=result.market_name,
            direction=result.direction,
            confidence=result.confidence,
            key_findings=result.key_findings,
            reasoning=result.reasoning,
            sources=[{"title": s.get("title", ""), "url": s.get("url", "")} for s in result.sources],
            current_odds=result.current_odds
        )
    except Exception as e:
        logger.error("investigate_api_error", error=str(e), market_id=market_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/categories")
async def list_categories():
    """List available market categories."""
    market_manager = state["market_manager"]
    categories = list(set(m.category for m in market_manager.markets))
    return [
        {"id": cat.lower(), "label": cat, "emoji": _get_emoji(cat)}
        for cat in sorted(categories)
    ]


def _get_emoji(category: str) -> str:
    """Get emoji for category."""
    emojis = {
        "AI": "🤖",
        "Autonomous": "🚗",
        "Crypto": "💰",
        "Politics": "🗳️",
        "Tech": "💻",
        "Sports": "⚽",
        "Science": "🔬",
        "Entertainment": "🎬",
    }
    return emojis.get(category, "📊")


# ============================================================================
# Whale Tracking (CLOB API)
# ============================================================================

@app.get("/api/whales/status")
async def whale_status():
    """Check if whale tracking is available."""
    return {
        "available": clob.is_authenticated,
        "whale_threshold_usd": clob.whale_threshold,
        "message": "CLOB connected - whale tracking enabled" if clob.is_authenticated 
                   else "Add POLYMARKET_PRIVATE_KEY to .env for whale tracking"
    }


@app.get("/api/clob/{token_id}/trades")
async def get_token_trades(token_id: str, limit: int = 50):
    """
    Get recent trades for a token.
    
    Returns list of trades with side, size, price, and USD value.
    """
    if not clob.is_authenticated:
        raise HTTPException(
            status_code=503, 
            detail="CLOB not configured. Add POLYMARKET_PRIVATE_KEY to .env"
        )
    
    trades = clob.get_trades(token_id, limit=limit)
    return {
        "token_id": token_id,
        "trades_count": len(trades),
        "trades": trades
    }


@app.get("/api/clob/{token_id}/whales")
async def get_whale_trades(token_id: str, min_usd: float = 500, limit: int = 50):
    """
    Get whale trades (large movements) for a token.
    
    Args:
        token_id: The CLOB token ID
        min_usd: Minimum trade size to consider as whale (default: $500)
        limit: Max trades to check
    """
    if not clob.is_authenticated:
        raise HTTPException(status_code=503, detail="CLOB not configured")
    
    whales = clob.get_whale_trades(token_id, min_usd=min_usd, limit=limit)
    
    return {
        "token_id": token_id,
        "threshold_usd": min_usd,
        "whale_count": len(whales),
        "whales": whales
    }


@app.get("/api/clob/{token_id}/orderbook")
async def get_order_book(token_id: str):
    """
    Get order book (bids and asks) for a token.
    """
    if not clob.is_authenticated:
        raise HTTPException(status_code=503, detail="CLOB not configured")
    
    book = clob.get_order_book(token_id)
    return {
        "token_id": token_id,
        **book
    }


@app.get("/api/clob/{token_id}/summary")
async def get_market_clob_summary(token_id: str):
    """
    Complete CLOB summary: trades, whales, order book, sentiment.
    """
    if not clob.is_authenticated:
        raise HTTPException(status_code=503, detail="CLOB not configured")
    
    summary = clob.get_market_summary(token_id)
    return summary


# ============================================================================
# Signal Detection (News → Market → AI Decision)
# ============================================================================

@app.get("/api/signals/status")
async def signal_status():
    """Get signal detection system status including scheduler info."""
    from src.core.scheduler import SmartScheduler, ScheduleConfig
    
    monitor = state.get("news_monitor")
    if not monitor:
        return {"available": False, "error": "Signal system not initialized"}
    
    # Create temp scheduler just for status check
    temp_config = ScheduleConfig()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    current_time = now.time()
    
    # Check if in market hours
    start = temp_config.market_start_utc
    end = temp_config.market_end_utc
    if start > end:
        is_market = current_time >= start or current_time < end
    else:
        is_market = start <= current_time < end
    
    return {
        "available": True,
        "is_market_hours": is_market,
        "current_time_utc": now.strftime("%H:%M:%S"),
        "market_hours_utc": f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}",
        "current_poll_interval_seconds": temp_config.poll_interval_market_hours if is_market else temp_config.poll_interval_off_hours,
        "current_poll_interval_minutes": (temp_config.poll_interval_market_hours if is_market else temp_config.poll_interval_off_hours) // 60,
        **monitor.get_status()
    }


@app.get("/api/signals/recent")
async def get_recent_signals(limit: int = 10, enriched_only: bool = True):
    """
    Get list of recent signals.
    
    Args:
        limit: Max signals to return
        enriched_only: If true, returns only enriched signals with full scoring
    """
    monitor = state.get("news_monitor")
    sg = state.get("signal_generator")
    
    if not monitor:
        raise HTTPException(status_code=503, detail="Signal system not initialized")
    
    if enriched_only and sg:
        # Get enriched signals with full score breakdowns
        signals = sg.get_recent_enriched(limit)
    else:
        # Fallback to monitor signals
        signals = monitor.get_recent_signals(limit)
    
    return {
        "count": len(signals),
        "enriched": enriched_only,
        "signals": [s.to_dict() for s in signals]
    }


@app.post("/api/signals/scan")
async def trigger_news_scan():
    """
    Manually trigger a news scan.
    
    Returns any generated signals.
    """
    monitor = state.get("news_monitor")
    if not monitor:
        raise HTTPException(status_code=503, detail="Signal system not initialized")
    
    logger.info("manual_scan_triggered")
    
    # Run scan
    signals = await monitor.scan_once()
    
    return {
        "scanned": True,
        "signals_generated": len(signals),
        "signals": [s.to_dict() for s in signals]
    }


class ManualSignalRequest(BaseModel):
    """Request body for manual signal analysis."""
    news_title: str
    news_source: str = "Manual Input"


@app.post("/api/signals/analyze")
async def analyze_news_manually(request: ManualSignalRequest):
    """
    Manually analyze a news headline.
    
    Finds matching markets and generates signals.
    """
    monitor = state.get("news_monitor")
    if not monitor:
        raise HTTPException(status_code=503, detail="Signal system not initialized")
    
    from src.core.news_monitor import NewsItem
    from datetime import datetime
    
    news = NewsItem(
        title=request.news_title,
        source=request.news_source,
        published_at=datetime.now().isoformat(),
        url=""
    )
    
    # Process the news
    signals = await monitor.process_news(news)
    
    return {
        "news": request.news_title,
        "markets_matched": len(signals),
        "signals": [s.to_dict() for s in signals]
    }


# ============================================================================
# Dynamic Polymarket Search (ALL markets)
# ============================================================================

class PolymarketEvent(BaseModel):
    """Event from Polymarket API."""
    id: str
    slug: str
    title: str
    description: Optional[str] = None
    category: str = "Other"
    volume: Optional[float] = None
    liquidity: Optional[float] = None
    active: bool = True


@app.get("/api/search", response_model=List[PolymarketEvent])
async def search_polymarket(
    query: Optional[str] = None,
    limit: int = 50,
    active: bool = True
):
    """
    Search ALL Polymarket markets dynamically.
    
    - query: Search term (optional, returns top markets if empty)
    - limit: Max results to return (default 50)
    - active: Only active markets (default true)
    
    Searches across 500+ markets from both /events and /markets endpoints.
    """
    import httpx
    import asyncio
    
    limit = min(limit, 200)  # Allow more results
    
    async with httpx.AsyncClient(base_url="https://gamma-api.polymarket.com", timeout=60) as client:
        # Fetch from multiple sources in parallel for better coverage
        async def fetch_events():
            params = {
                "limit": 500,
                "order": "startDate",
                "ascending": "false"  # Most recent first!
            }
            if active:
                params["active"] = "true"
            r = await client.get("/events", params=params)
            return r.json() if r.status_code == 200 else []
        
        async def fetch_markets():
            params = {
                "closed": "false", 
                "limit": 500,
                "order": "createdAt",
                "ascending": "false"  # Most recent first!
            }
            r = await client.get("/markets", params=params)
            return r.json() if r.status_code == 200 else []
        
        # Fetch both in parallel
        events_data, markets_data = await asyncio.gather(fetch_events(), fetch_markets())
        
        # Combine and deduplicate
        all_items = []
        seen_slugs = set()
        
        # Add events
        for e in events_data:
            slug = e.get("slug", "")
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                all_items.append({
                    "slug": slug,
                    "title": e.get("title", ""),
                    "description": e.get("description", ""),
                    "id": e.get("id", ""),
                    "volume": e.get("volume"),
                    "liquidity": e.get("liquidity"),
                    "active": e.get("active", True)
                })
        
        # Add markets (may have different questions)
        for m in markets_data:
            slug = m.get("slug", m.get("conditionId", ""))
            question = m.get("question", "")
            if question and slug not in seen_slugs:
                all_items.append({
                    "slug": slug,
                    "title": question,
                    "description": m.get("description", ""),
                    "id": m.get("id", ""),
                    "volume": m.get("volume"),
                    "liquidity": m.get("liquidity"),
                    "active": not m.get("closed", False)
                })
        
        logger.info("search_data_fetched", events=len(events_data), markets=len(markets_data), total=len(all_items))
        
        # Filter by query if provided
        if query:
            query_lower = query.lower()
            query_words = query_lower.split()
            
            # Score-based matching for better results
            scored_items = []
            for item in all_items:
                title = item.get("title", "").lower()
                desc = item.get("description", "").lower()
                slug = item.get("slug", "").lower()
                
                # Calculate match score
                score = 0
                for word in query_words:
                    if word in title:
                        score += 10
                    if word in slug:
                        score += 5
                    if word in desc:
                        score += 2
                
                if score > 0:
                    scored_items.append((score, item))
            
            # Sort by score (best matches first)
            scored_items.sort(key=lambda x: x[0], reverse=True)
            all_items = [item for _, item in scored_items]
        
        # Limit results
        all_items = all_items[:limit]
        
        # Map to response model with category detection
        results = []
        for item in all_items:
            title = item.get("title", "").lower()
            
            # Category detection
            if any(w in title for w in ["bitcoin", "ethereum", "crypto", "solana", "btc", "eth", "xrp", "doge"]):
                category = "Crypto"
            elif any(w in title for w in ["trump", "biden", "election", "president", "congress", "senate", "governor", "maduro", "putin", "zelensky"]):
                category = "Politics"
            elif any(w in title for w in ["ai", "openai", "claude", "gpt", "llm", "artificial", "gemini", "grok"]):
                category = "AI"
            elif any(w in title for w in ["nba", "nfl", "mlb", "soccer", "sports", "lakers", "celtics", "warriors", "chiefs"]):
                category = "Sports"
            elif any(w in title for w in ["tesla", "spacex", "robot", "autonomous", "self-driving"]):
                category = "Tech"
            else:
                category = "Other"
            
            results.append(PolymarketEvent(
                id=item.get("id", ""),
                slug=item.get("slug", ""),
                title=item.get("title", ""),
                description=item.get("description", ""),
                category=category,
                volume=item.get("volume"),
                liquidity=item.get("liquidity"),
                active=item.get("active", True)
            ))
        
        return results



@app.get("/api/polymarket/{slug}")
async def get_polymarket_event(slug: str):
    """
    Get details for ANY Polymarket event by slug.
    Works for all markets, not just curated ones.
    """
    import httpx
    import json
    
    gamma = state["gamma"]
    
    async with httpx.AsyncClient(base_url="https://gamma-api.polymarket.com", timeout=30) as client:
        response = await client.get("/events", params={"slug": slug})
        response.raise_for_status()
        events = response.json()
        
        if not events:
            raise HTTPException(status_code=404, detail="Event not found")
        
        event = events[0]
        markets = event.get("markets", [])
        
        # Get odds from first market
        odds = None
        if markets:
            prices = markets[0].get("outcomePrices", "[]")
            if isinstance(prices, str):
                try:
                    prices = json.loads(prices)
                except:
                    prices = []
            if prices:
                try:
                    odds = float(prices[0]) * 100
                except:
                    pass
        
        return {
            "id": event.get("id"),
            "slug": event.get("slug"),
            "title": event.get("title"),
            "description": event.get("description"),
            "odds": round(odds, 1) if odds else None,
            "interpretation": get_interpretation(odds),
            "volume": event.get("volume"),
            "liquidity": event.get("liquidity"),
            "markets_count": len(markets),
            "source_url": f"https://polymarket.com/event/{slug}"
        }


@app.get("/api/polymarket/{slug}/investigate", response_model=InvestigationResponse)
async def investigate_dynamic_market(slug: str):
    """
    Investigate ANY Polymarket market by slug using AI.
    
    Works with any market - doesn't need to be in markets.yaml.
    Example: /api/polymarket/2nd-largest-company-end-of-january/investigate
    """
    import httpx
    import json
    from src.models.market import Market
    
    research_agent = state["research_agent"]
    
    # Fetch market from Polymarket
    async with httpx.AsyncClient(base_url="https://gamma-api.polymarket.com", timeout=30) as client:
        response = await client.get("/events", params={"slug": slug})
        response.raise_for_status()
        events = response.json()
        
        if not events:
            raise HTTPException(status_code=404, detail=f"Market '{slug}' not found on Polymarket")
        
        event = events[0]
    
    # Create a temporary Market object for investigation
    temp_market = Market(
        market_id=slug,
        market_name=event.get("title", slug),
        yes_definition="Yes outcome",
        no_definition="No outcome",
        category="Dynamic",
        description=event.get("description", "")
    )
    
    try:
        # Run full AI investigation
        result = await research_agent.investigate(temp_market)
        
        return InvestigationResponse(
            market_name=result.market_name,
            direction=result.direction,
            confidence=result.confidence,
            key_findings=result.key_findings,
            reasoning=result.reasoning,
            sources=[{"title": s.get("title", ""), "url": s.get("url", "")} for s in result.sources],
            current_odds=result.current_odds
        )
    except Exception as e:
        logger.error("investigate_dynamic_error", error=str(e), slug=slug)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/investigate-query")
async def investigate_by_query(query: str):
    """
    Investigate a market by searching for it first.
    
    Usage: POST /api/investigate-query?query=bitcoin+150000
    
    This will:
    1. Search Polymarket for the query
    2. Take the first matching result
    3. Run full AI investigation on it
    """
    import httpx
    from src.models.market import Market
    
    research_agent = state["research_agent"]
    
    # Search for matching markets
    async with httpx.AsyncClient(base_url="https://gamma-api.polymarket.com", timeout=30) as client:
        response = await client.get("/events", params={"limit": 100, "active": "true"})
        response.raise_for_status()
        events = response.json()
        
        # Filter by query
        query_lower = query.lower()
        matching = [
            e for e in events 
            if query_lower in e.get("title", "").lower() 
            or query_lower in e.get("description", "").lower()
        ]
        
        if not matching:
            raise HTTPException(
                status_code=404, 
                detail=f"No markets found matching '{query}'. Try different keywords."
            )
        
        event = matching[0]
    
    # Create temp market and investigate
    temp_market = Market(
        market_id=event.get("slug", "unknown"),
        market_name=event.get("title", query),
        yes_definition="Yes outcome",
        no_definition="No outcome",
        category="Dynamic",
        description=event.get("description", "")
    )
    
    try:
        result = await research_agent.investigate(temp_market)
        
        return {
            "query": query,
            "matched_market": {
                "slug": event.get("slug"),
                "title": event.get("title"),
                "url": f"https://polymarket.com/event/{event.get('slug')}"
            },
            "investigation": {
                "direction": result.direction,
                "confidence": result.confidence,
                "current_odds": result.current_odds,
                "key_findings": result.key_findings,
                "reasoning": result.reasoning,
                "sources": [{"title": s.get("title", ""), "url": s.get("url", "")} for s in result.sources]
            }
        }
    except Exception as e:
        logger.error("investigate_query_error", error=str(e), query=query)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Entry point for standalone running
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)

