"""
Fetch liquidation history proxy from Bybit V5 API.

Bybit's public /v5/public/liquidation endpoint does NOT support historical data.
We derive a synthetic liquidation volume using the standard industry proxy:

  liquidation_volume_usd ≈ max(0, OI_prev - OI_curr) × close_price

Rationale:
  - Forced liquidations reduce open interest (positions are closed by the exchange)
  - When OI drops sharply in a period of high price volatility, it signals cascading
    liquidations rather than voluntary unwinding
  - OI drop × mark price = approximate USD value forcibly liquidated

This proxy is used by Glassnode, CryptoQuant, and other on-chain analytics platforms
when tick-level liquidation feeds are unavailable.

Usage:
  python3 data/fetch_liquidation_history.py
  python3 data/fetch_liquidation_history.py --symbol XRPUSDT

Output:
  data/historical/{SYMBOL}_liquidations_4h.csv
  Columns: timestamp, datetime, liquidation_volume_usd, is_cluster
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
import pandas as pd
import numpy as np
import time
import argparse
from pathlib import Path

DATA_DIR = Path(__file__).parent / "historical"
DATA_DIR.mkdir(exist_ok=True)

KLINE_URL = "https://api.bybit.com/v5/market/kline"
OI_URL    = "https://api.bybit.com/v5/market/open-interest"


def fetch_kline_page(symbol: str, start_ms: int, end_ms: int,
                     interval: str = "240", limit: int = 200) -> list:
    """Fetch one page of OHLCV kline data."""
    params = {
        "category": "linear",
        "symbol":   symbol,
        "interval": interval,
        "start":    start_ms,
        "end":      end_ms,
        "limit":    limit,
    }
    r = requests.get(KLINE_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("retCode") != 0:
        raise ValueError(f"Bybit kline API error: {data.get('retMsg')}")
    return data["result"]["list"]  # [timestamp, open, high, low, close, volume, turnover]


def fetch_oi_page(symbol: str, start_ms: int, end_ms: int,
                  interval: str = "4h", limit: int = 200) -> list:
    """Fetch one page of open interest history."""
    params = {
        "category":     "linear",
        "symbol":       symbol,
        "intervalTime": interval,
        "startTime":    start_ms,
        "endTime":      end_ms,
        "limit":        limit,
    }
    r = requests.get(OI_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("retCode") != 0:
        print(f"  ⚠ OI API warning: {data.get('retMsg')}")
        return []
    return data["result"]["list"]


def fetch_klines(symbol: str, days: int = 730) -> pd.DataFrame:
    """Paginate through 4h kline history."""
    print(f"  📡 Fetching 4h klines for {symbol} ({days} days)...")

    end_ms   = int(time.time() * 1000)
    start_ms = end_ms - (days * 24 * 3600 * 1000)

    all_klines = []
    cursor_end = end_ms
    four_h_ms  = 4 * 3600 * 1000

    while True:
        page = fetch_kline_page(symbol, start_ms, cursor_end, interval="240", limit=200)
        if not page:
            break
        all_klines.extend(page)
        oldest_ts = int(page[-1][0])
        if oldest_ts <= start_ms:
            break
        cursor_end = oldest_ts - 1
        print(f"    {len(all_klines)} kline records...", end="\r")
        time.sleep(0.1)

    if not all_klines:
        return pd.DataFrame()

    df = pd.DataFrame(all_klines, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
    df["timestamp"] = df["timestamp"].astype("int64")
    df["close"]     = df["close"].astype("float64")
    df["high"]      = df["high"].astype("float64")
    df["low"]       = df["low"].astype("float64")
    df["volume"]    = df["volume"].astype("float64")
    df = df[["timestamp", "close", "high", "low", "volume"]].drop_duplicates("timestamp")
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    print(f"    ✅ {len(df)} kline records (start: {df['datetime'].iloc[0]}, end: {df['datetime'].iloc[-1]})")
    return df


def fetch_open_interest(symbol: str, days: int = 730) -> pd.DataFrame:
    """Paginate through 4h OI history."""
    print(f"  📡 Fetching 4h OI for {symbol}...")

    end_ms   = int(time.time() * 1000)
    start_ms = end_ms - (days * 24 * 3600 * 1000)

    all_oi = []
    cursor_end = end_ms

    while True:
        page = fetch_oi_page(symbol, start_ms, cursor_end, interval="4h", limit=200)
        if not page:
            break
        all_oi.extend(page)
        oldest_ts = int(page[-1]["timestamp"])
        if oldest_ts <= start_ms:
            break
        cursor_end = oldest_ts - 1
        print(f"    {len(all_oi)} OI records...", end="\r")
        time.sleep(0.1)

    if not all_oi:
        return pd.DataFrame()

    df = pd.DataFrame(all_oi)
    df["timestamp"]     = df["timestamp"].astype("int64")
    df["open_interest"] = df["openInterest"].astype("float64")
    df = df[["timestamp", "open_interest"]].drop_duplicates("timestamp")
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    print(f"    ✅ {len(df)} OI records")
    return df


def compute_liquidation_proxy(df_kline: pd.DataFrame, df_oi: pd.DataFrame) -> pd.DataFrame:
    """
    Compute synthetic liquidation volume using OI drop × close price.

    liquidation_volume_usd = max(0, OI_prev - OI_curr) × close_price

    Additional amplification signal:
      - candle_range = (high - low) / low — wide-range candles indicate forced moves
      - volume_zscore — volume spike confirms liquidation cascade
    """
    # Merge OI onto kline timestamps
    merged = pd.merge_asof(
        df_kline.sort_values("timestamp"),
        df_oi[["timestamp", "open_interest"]].rename(columns={"timestamp": "oi_ts"}).sort_values("oi_ts"),
        left_on="timestamp",
        right_on="oi_ts",
        direction="nearest",
        tolerance=4 * 3600 * 1000,  # max 4h gap
    ).drop(columns=["oi_ts"])

    merged["open_interest"] = merged["open_interest"].ffill()

    # OI decrease = positions force-closed = liquidations
    oi_prev = merged["open_interest"].shift(1)
    oi_drop = (oi_prev - merged["open_interest"]).clip(lower=0)  # only drops count

    # USD value of liquidated positions (contracts × price)
    merged["liquidation_volume_usd"] = oi_drop * merged["close"]

    # Candle body range as confirmation (wide candle = volatile = liquidations)
    merged["candle_range_pct"] = (merged["high"] - merged["low"]) / merged["low"]

    # Volume z-score (rolling 48 candles = 8 days)
    vol_roll = merged["volume"].rolling(48, min_periods=10)
    merged["volume_zscore"] = (merged["volume"] - vol_roll.mean()) / vol_roll.std()

    # Enhanced signal: amplify liq volume during high-volatility spikes
    # If candle_range > 2× rolling avg AND volume spike → boost liq signal
    avg_range = merged["candle_range_pct"].rolling(48, min_periods=10).mean()
    vol_spike = merged["volume_zscore"] > 1.5
    range_spike = merged["candle_range_pct"] > (avg_range * 2.0)
    boost = (vol_spike | range_spike).astype(float) * 0.5 + 1.0  # 1x or 1.5x

    merged["liquidation_volume_usd"] = merged["liquidation_volume_usd"] * boost

    # Fill NaN (first row has no prior OI)
    merged["liquidation_volume_usd"] = merged["liquidation_volume_usd"].fillna(0.0)

    return merged


def build_liquidation_4h(symbol: str, days: int = 730) -> pd.DataFrame:
    """
    Build 4h liquidation volume proxy for a symbol.
    Saves to data/historical/{SYMBOL}_liquidations_4h.csv.
    """
    print(f"\n🔥 Building liquidation history for {symbol} ({days} days)...")

    df_kline = fetch_klines(symbol, days=days)
    if df_kline.empty:
        print(f"  ❌ No kline data for {symbol}")
        return pd.DataFrame()

    df_oi = fetch_open_interest(symbol, days=days)
    if df_oi.empty:
        print(f"  ⚠ No OI data — using volume-only proxy")
        df_kline["open_interest"] = df_kline["volume"]  # fallback
        df_oi = df_kline[["timestamp", "volume"]].rename(columns={"volume": "open_interest"})

    result = compute_liquidation_proxy(df_kline, df_oi)

    # Identify liquidation clusters: periods with liq_vol > 75th percentile
    liq_75th = result["liquidation_volume_usd"].quantile(0.75)
    liq_50th = result["liquidation_volume_usd"].quantile(0.50)
    result["is_cluster"] = result["liquidation_volume_usd"] > liq_75th

    print(f"  📊 Liquidation stats:")
    print(f"     50th pct: ${liq_50th:,.0f}")
    print(f"     75th pct: ${liq_75th:,.0f}")
    print(f"     Max:      ${result['liquidation_volume_usd'].max():,.0f}")
    print(f"     Clusters: {result['is_cluster'].sum()} periods ({result['is_cluster'].mean()*100:.1f}%)")

    # Output columns
    out = result[["timestamp", "datetime", "liquidation_volume_usd", "is_cluster"]].copy()
    out["is_cluster"] = out["is_cluster"].astype(int)

    out_path = DATA_DIR / f"{symbol}_liquidations_4h.csv"
    out.to_csv(out_path, index=False)
    print(f"  💾 Saved → {out_path} ({len(out)} rows)")

    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch/derive liquidation volume proxy for Bybit perps")
    parser.add_argument("--symbol", "-s", type=str, default=None, help="Symbol (default: XRPUSDT and SUIUSDT)")
    parser.add_argument("--days",   "-d", type=int, default=730,  help="Days of history (default: 730)")
    args = parser.parse_args()

    symbols = [args.symbol] if args.symbol else ["XRPUSDT", "SUIUSDT"]
    for sym in symbols:
        build_liquidation_4h(sym, days=args.days)
        time.sleep(1)

    print("\n✅ Liquidation history fetch complete.")
