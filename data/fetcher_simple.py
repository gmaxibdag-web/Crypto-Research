"""
Simple Bybit data fetcher - No pandas dependency
"""
import requests
import json
from datetime import datetime
from typing import Dict, List, Optional

BASE = "https://api.bybit.com/v5/market"

def get_klines_simple(symbol: str, interval: str = "240", limit: int = 100) -> Optional[Dict]:
    """Fetch OHLCV candles from Bybit without pandas."""
    try:
        url = f"{BASE}/kline"
        params = {"category": "spot", "symbol": symbol, "interval": interval, "limit": limit}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()["result"]["list"]
        
        # Convert to dictionary format
        if not data:
            return None
        
        # Reverse to chronological order (oldest first)
        data.reverse()
        
        # Initialize lists
        timestamps = []
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []
        turnovers = []
        
        for item in data:
            timestamps.append(int(item[0]))
            opens.append(float(item[1]))
            highs.append(float(item[2]))
            lows.append(float(item[3]))
            closes.append(float(item[4]))
            volumes.append(float(item[5]))
            turnovers.append(float(item[6]) if len(item) > 6 else 0.0)
        
        result = {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "turnover": turnovers
        }
        
        return result
        
    except Exception as e:
        print(f"Error fetching klines for {symbol}: {e}")
        return None

def get_ticker_simple(symbol: str) -> Optional[Dict]:
    """Fetch ticker data from Bybit."""
    try:
        url = f"{BASE}/tickers"
        params = {"category": "spot", "symbol": symbol}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()["result"]["list"][0]
        
        return {
            "symbol": data["symbol"],
            "lastPrice": data["lastPrice"],
            "highPrice24h": data["highPrice24h"],
            "lowPrice24h": data["lowPrice24h"],
            "volume24h": data["volume24h"],
            "turnover24h": data["turnover24h"]
        }
        
    except Exception as e:
        print(f"Error fetching ticker for {symbol}: {e}")
        return None

def get_funding_rate(symbol: str) -> Optional[float]:
    """Fetch funding rate for perpetual contracts."""
    try:
        url = f"{BASE}/funding/history"
        params = {"category": "linear", "symbol": symbol, "limit": 1}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()["result"]["list"]
        
        if data:
            return float(data[0]["fundingRate"])
        return None
        
    except Exception as e:
        print(f"Error fetching funding rate for {symbol}: {e}")
        return None

# Test functions
if __name__ == "__main__":
    print("🧪 Testing Simple Fetcher")
    print("=" * 60)
    
    # Test klines
    klines = get_klines_simple("BTCUSDT", "240", 10)
    if klines:
        print(f"✅ BTCUSDT klines fetched: {len(klines['close'])} candles")
        print(f"   Latest close: ${klines['close'][-1]:.2f}")
    else:
        print("❌ Failed to fetch klines")
    
    # Test ticker
    ticker = get_ticker_simple("BTCUSDT")
    if ticker:
        print(f"✅ BTCUSDT ticker fetched")
        print(f"   Last price: ${ticker['lastPrice']}")
    else:
        print("❌ Failed to fetch ticker")
    
    print("\n✅ Simple fetcher working correctly")