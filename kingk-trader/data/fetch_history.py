"""
Fetch deep historical OHLCV data from Bybit.
Bybit caps at 1000 candles per request — we paginate backwards to get 2 years.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
import pandas as pd
import time
from pathlib import Path

DATA_DIR = Path(__file__).parent / "historical"
DATA_DIR.mkdir(exist_ok=True)

BASE = "https://api.bybit.com/v5/market/kline"

def fetch_page(symbol: str, interval: str, end_ms: int, limit: int = 1000) -> list:
    params = {
        "category": "spot",
        "symbol":   symbol,
        "interval": interval,
        "limit":    limit,
        "end":      end_ms,
    }
    r = requests.get(BASE, params=params, timeout=10)
    r.raise_for_status()
    return r.json()["result"]["list"]

def fetch_deep(symbol: str, interval: str = "240", days: int = 730) -> pd.DataFrame:
    """Paginate backwards to collect `days` worth of candles."""
    interval_ms = {"60": 3600000, "240": 14400000, "D": 86400000}.get(interval, 14400000)
    total_candles = (days * 86400000) // interval_ms
    
    print(f"Fetching {symbol} {interval}h — targeting ~{total_candles} candles ({days} days)...")
    
    all_data = []
    end_ms = int(time.time() * 1000)
    fetched = 0

    while fetched < total_candles:
        page = fetch_page(symbol, interval, end_ms, limit=1000)
        if not page:
            break
        all_data.extend(page)
        fetched += len(page)
        # oldest candle in this page becomes next end
        end_ms = int(page[-1][0]) - 1
        print(f"  {fetched} candles fetched...", end="\r")
        time.sleep(0.2)  # be polite to the API

    df = pd.DataFrame(all_data, columns=["timestamp","open","high","low","close","volume","turnover"])
    df = df.astype({
        "timestamp": "int64",
        "open": "float64", "high": "float64",
        "low": "float64", "close": "float64",
        "volume": "float64"
    })
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.drop_duplicates("timestamp").sort_values("datetime").reset_index(drop=True)

    out = DATA_DIR / f"{symbol}_{interval}.csv"
    df.to_csv(out, index=False)
    print(f"\n  ✅ Saved {len(df)} candles → {out}")
    return df

if __name__ == "__main__":
    for sym in ["XRPUSDT", "SUIUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        fetch_deep(sym, interval="240", days=730)
        time.sleep(1)
