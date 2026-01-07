"""
ExaSignal - Cliente CLOB API (Polymarket)
Para whale tracking e dados de trading em tempo real.

Requer POLYMARKET_PRIVATE_KEY no .env
"""
import os
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

load_dotenv()

from src.utils.logger import logger

# Check if private key is available
PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")
HAS_AUTH = bool(PRIVATE_KEY and len(PRIVATE_KEY) > 10)


class CLOBClient:
    """
    Cliente para Polymarket CLOB API.
    
    Features:
    - Get trades for any market
    - Detect whale trades (large movements)
    - Get order book (bids/asks)
    - Get last trade price
    """
    
    def __init__(self, whale_threshold_usd: float = 500):
        self.client = None
        self.is_authenticated = False
        self.whale_threshold = whale_threshold_usd
        
        if HAS_AUTH:
            try:
                from py_clob_client.client import ClobClient
                
                self.client = ClobClient(
                    host="https://clob.polymarket.com",
                    key=PRIVATE_KEY,
                    chain_id=137  # Polygon
                )
                
                # Derive API credentials
                creds = self.client.derive_api_key()
                self.client.set_api_creds(creds)
                
                self.is_authenticated = True
                logger.info("clob_ready", api_key=creds.api_key[:10] + "...")
                
            except Exception as e:
                logger.error("clob_init_error", error=str(e))
        else:
            logger.warning("clob_no_key", 
                          hint="Add POLYMARKET_PRIVATE_KEY to .env for whale tracking")
    
    def get_last_price(self, token_id: str) -> Optional[float]:
        """Get last trade price for a token (0-1 scale)."""
        if not self.is_authenticated:
            return None
        
        try:
            result = self.client.get_last_trade_price(token_id)
            if result and 'price' in result:
                return float(result['price'])
        except Exception as e:
            logger.debug("clob_price_error", token_id=token_id[:20], error=str(e))
        return None
    
    def get_trades(self, token_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent trades for a token.
        
        Returns list of trades with: side, size, price, timestamp
        """
        if not self.is_authenticated:
            return []
        
        try:
            from py_clob_client.clob_types import TradeParams
            
            params = TradeParams(asset_id=token_id)
            trades = self.client.get_trades(params)
            
            if not trades:
                return []
            
            # Convert to dicts
            result = []
            for t in trades[:limit]:
                result.append({
                    "side": t.side,
                    "size": float(t.size),
                    "price": float(t.price),
                    "size_usd": float(t.size) * float(t.price),
                    "outcome": t.outcome if hasattr(t, 'outcome') else "",
                    "timestamp": t.match_time if hasattr(t, 'match_time') else None,
                })
            
            return result
            
        except Exception as e:
            logger.debug("clob_trades_error", token_id=token_id[:20], error=str(e))
            return []
    
    def get_whale_trades(
        self, 
        token_id: str, 
        min_usd: Optional[float] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get only large trades (whale movements).
        
        Args:
            token_id: The token to check
            min_usd: Minimum trade size in USD (default: self.whale_threshold)
            limit: Max trades to check
        
        Returns:
            List of whale trades
        """
        threshold = min_usd or self.whale_threshold
        trades = self.get_trades(token_id, limit=limit)
        
        whales = [t for t in trades if t.get("size_usd", 0) >= threshold]
        
        if whales:
            logger.info("whales_detected", 
                       token=token_id[:20], 
                       count=len(whales),
                       threshold=threshold)
        
        return whales
    
    def get_order_book(self, token_id: str) -> Dict[str, Any]:
        """
        Get order book (bids and asks) for a token.
        
        Returns:
            {
                "bids": [{"price": 0.45, "size": 100}, ...],
                "asks": [{"price": 0.55, "size": 50}, ...],
                "spread": 0.10
            }
        """
        if not self.is_authenticated:
            return {"bids": [], "asks": [], "spread": None, "error": "Not authenticated"}
        
        try:
            book = self.client.get_order_book(token_id)
            
            if not book:
                return {"bids": [], "asks": [], "spread": None}
            
            bids = [{"price": float(b.price), "size": float(b.size)} 
                   for b in (book.bids or [])]
            asks = [{"price": float(a.price), "size": float(a.size)} 
                   for a in (book.asks or [])]
            
            # Calculate spread
            spread = None
            if bids and asks:
                best_bid = max(b["price"] for b in bids)
                best_ask = min(a["price"] for a in asks)
                spread = round(best_ask - best_bid, 4)
            
            return {
                "bids": bids[:20],  # Top 20
                "asks": asks[:20],
                "spread": spread,
                "best_bid": bids[0]["price"] if bids else None,
                "best_ask": asks[0]["price"] if asks else None,
            }
            
        except Exception as e:
            logger.debug("clob_orderbook_error", error=str(e))
            return {"bids": [], "asks": [], "spread": None, "error": str(e)}
    
    def get_market_summary(self, token_id: str) -> Dict[str, Any]:
        """
        Complete market summary with trades, whales, and order book.
        """
        if not self.is_authenticated:
            return {
                "available": False,
                "error": "CLOB requires POLYMARKET_PRIVATE_KEY",
            }
        
        last_price = self.get_last_price(token_id)
        trades = self.get_trades(token_id, limit=50)
        whales = self.get_whale_trades(token_id)
        book = self.get_order_book(token_id)
        
        # Calculate sentiment
        buys = sum(1 for t in trades if t.get("side") == "BUY")
        sells = len(trades) - buys
        
        return {
            "available": True,
            "token_id": token_id,
            "last_price": last_price,
            "last_price_pct": round(last_price * 100, 1) if last_price else None,
            "trades_count": len(trades),
            "whale_count": len(whales),
            "whale_threshold_usd": self.whale_threshold,
            "buy_count": buys,
            "sell_count": sells,
            "sentiment": "bullish" if buys > sells else "bearish" if sells > buys else "neutral",
            "order_book": book,
            "recent_whales": whales[:5],
        }


# Singleton - configure threshold via env
WHALE_THRESHOLD = float(os.getenv("WHALE_THRESHOLD_USD", "500"))
clob = CLOBClient(whale_threshold_usd=WHALE_THRESHOLD)
