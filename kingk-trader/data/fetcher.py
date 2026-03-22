"""
Bybit public API data fetcher.
No API key needed for historical + ticker data.
"""
import requests
import pandas as pd
from datetime import datetime

BASE = "https://api.bybit.com/v5/market"

def get_klines(symbol: str, interval: str = "240", limit: int = 200) -> pd.DataFrame:
    """Fetch OHLCV candles from Bybit. interval: 1,5,15,30,60,120,240,D,W"""
    url = f"{BASE}/kline"
    params = {"category": "spot", "symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()["result"]["list"]

    df = pd.DataFrame(data, columns=["timestamp","open","high","low","close","volume","turnover"])
    df = df.astype({
        "timestamp": "int64",
        "open": "float64", "high": "float64",
        "low": "float64", "close": "float64",
        "volume": "float64"
    })
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.sort_values("datetime").reset_index(drop=True)
    return df

def get_ticker(symbol: str) -> dict:
    """Get latest ticker for a symbol."""
    url = f"{BASE}/tickers"
    r = requests.get(url, params={"category": "spot", "symbol": symbol}, timeout=10)
    r.raise_for_status()
    return r.json()["result"]["list"][0]

if __name__ == "__main__":
    for sym in ["XRPUSDT", "SUIUSDT"]:
        df = get_klines(sym, interval="240", limit=5)
        t = get_ticker(sym)
        print(f"\n{sym} — Last: ${t['lastPrice']}  24h: {float(t['price24hPcnt'])*100:.2f}%")
        print(df[["datetime","open","high","low","close","volume"]].tail(3).to_string(index=False))
