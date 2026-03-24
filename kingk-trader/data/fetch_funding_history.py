"""
Fetch funding rate history from Bybit V5 API.
Aligns 8h funding intervals to 4h candle timestamps via forward-fill.

Usage:
  python3 data/fetch_funding_history.py
  python3 data/fetch_funding_history.py --symbol XRPUSDT

Output:
  data/historical/{SYMBOL}_funding_4h.csv
  Columns: timestamp, datetime, funding_rate, open_interest
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
import pandas as pd
import time
import argparse
from pathlib import Path

DATA_DIR = Path(__file__).parent / "historical"
DATA_DIR.mkdir(exist_ok=True)

FUNDING_URL = "https://api.bybit.com/v5/market/funding/history"
OI_URL      = "https://api.bybit.com/v5/market/open-interest"


def fetch_funding_page(symbol: str, start_ms: int, end_ms: int, limit: int = 200) -> list:
    """Fetch one page of funding rate history."""
    params = {
        "category": "linear",
        "symbol":   symbol,
        "startTime": start_ms,
        "endTime":   end_ms,
        "limit":     limit,
    }
    r = requests.get(FUNDING_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("retCode") != 0:
        raise ValueError(f"Bybit API error: {data.get('retMsg')}")
    return data["result"]["list"]


def fetch_oi_page(symbol: str, start_ms: int, end_ms: int, interval: str = "4h", limit: int = 200) -> list:
    """Fetch one page of open interest history."""
    params = {
        "category":      "linear",
        "symbol":        symbol,
        "intervalTime":  interval,
        "startTime":     start_ms,
        "endTime":       end_ms,
        "limit":         limit,
    }
    r = requests.get(OI_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("retCode") != 0:
        print(f"  ⚠ OI API warning: {data.get('retMsg')} — continuing without OI")
        return []
    return data["result"]["list"]


def fetch_funding_history(symbol: str, days: int = 730) -> pd.DataFrame:
    """
    Paginate through funding rate history for the given symbol.
    Bybit funding occurs every 8h; we collect and forward-fill to 4h candles.
    """
    print(f"\n📡 Fetching funding rate history for {symbol} ({days} days)...")

    end_ms   = int(time.time() * 1000)
    start_ms = end_ms - (days * 24 * 3600 * 1000)

    all_funding = []
    cursor_end = end_ms

    while True:
        page = fetch_funding_page(symbol, start_ms, cursor_end, limit=200)
        if not page:
            break
        all_funding.extend(page)
        # page is newest-first; oldest is last entry
        oldest_ts = int(page[-1]["fundingRateTimestamp"])
        if oldest_ts <= start_ms:
            break
        cursor_end = oldest_ts - 1
        print(f"  {len(all_funding)} funding records...", end="\r")
        time.sleep(0.15)

    if not all_funding:
        print(f"  ⚠ No funding data returned for {symbol}")
        return pd.DataFrame()

    df_f = pd.DataFrame(all_funding)
    df_f["timestamp"] = df_f["fundingRateTimestamp"].astype("int64")
    df_f["funding_rate"] = df_f["fundingRate"].astype("float64")
    df_f = df_f[["timestamp", "funding_rate"]].drop_duplicates("timestamp")
    df_f = df_f.sort_values("timestamp").reset_index(drop=True)
    df_f["datetime"] = pd.to_datetime(df_f["timestamp"], unit="ms")

    print(f"  ✅ {len(df_f)} funding records fetched (start: {df_f['datetime'].iloc[0]}, end: {df_f['datetime'].iloc[-1]})")
    return df_f


def fetch_open_interest(symbol: str, days: int = 730) -> pd.DataFrame:
    """
    Fetch 4h open interest history.
    Returns df with timestamp, open_interest columns.
    """
    print(f"📡 Fetching open interest for {symbol} ({days} days)...")

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
        print(f"  {len(all_oi)} OI records...", end="\r")
        time.sleep(0.15)

    if not all_oi:
        print(f"  ⚠ No OI data for {symbol}")
        return pd.DataFrame()

    df_oi = pd.DataFrame(all_oi)
    df_oi["timestamp"] = df_oi["timestamp"].astype("int64")
    df_oi["open_interest"] = df_oi["openInterest"].astype("float64")
    df_oi = df_oi[["timestamp", "open_interest"]].drop_duplicates("timestamp")
    df_oi = df_oi.sort_values("timestamp").reset_index(drop=True)
    df_oi["datetime"] = pd.to_datetime(df_oi["timestamp"], unit="ms")

    print(f"  ✅ {len(df_oi)} OI records fetched")
    return df_oi


def build_funding_4h(symbol: str, days: int = 730) -> pd.DataFrame:
    """
    Build a 4h-aligned funding rate + open interest DataFrame.
    - Funding rates (8h) are forward-filled to match 4h candle timestamps
    - Open interest comes in 4h natively
    - Both are aligned to a 4h timestamp grid
    """
    # Build 4h timestamp grid over the date range
    end_ms   = int(time.time() * 1000)
    start_ms = end_ms - (days * 24 * 3600 * 1000)

    # Snap to 4h boundary
    four_h_ms = 4 * 3600 * 1000
    start_snapped = (start_ms // four_h_ms) * four_h_ms
    end_snapped   = (end_ms   // four_h_ms) * four_h_ms

    timestamps = list(range(start_snapped, end_snapped + four_h_ms, four_h_ms))
    grid = pd.DataFrame({"timestamp": timestamps})
    grid["datetime"] = pd.to_datetime(grid["timestamp"], unit="ms")

    # Fetch funding (8h intervals)
    df_f = fetch_funding_history(symbol, days=days)
    if df_f.empty:
        print("  ⚠ Funding data unavailable — creating synthetic zeros")
        df_f = grid[["timestamp", "datetime"]].copy()
        df_f["funding_rate"] = 0.0

    # Merge funding onto 4h grid with forward-fill (funding persists until next update)
    # Use merge_asof: for each 4h candle, find the most recent funding timestamp
    df_f_sorted = df_f.sort_values("timestamp")
    merged = pd.merge_asof(
        grid.sort_values("timestamp"),
        df_f_sorted[["timestamp", "funding_rate"]].rename(columns={"timestamp": "fund_ts"}),
        left_on="timestamp",
        right_on="fund_ts",
        direction="backward"
    ).drop(columns=["fund_ts"])

    # Fetch open interest (4h native)
    df_oi = fetch_open_interest(symbol, days=days)
    if not df_oi.empty:
        df_oi_sorted = df_oi.sort_values("timestamp")
        merged = pd.merge_asof(
            merged.sort_values("timestamp"),
            df_oi_sorted[["timestamp", "open_interest"]].rename(columns={"timestamp": "oi_ts"}),
            left_on="timestamp",
            right_on="oi_ts",
            direction="backward"
        ).drop(columns=["oi_ts"])
    else:
        merged["open_interest"] = float("nan")

    merged = merged.sort_values("timestamp").reset_index(drop=True)

    # Final output: timestamp, datetime, funding_rate, open_interest
    out_cols = ["timestamp", "datetime", "funding_rate", "open_interest"]
    result = merged[out_cols].copy()
    result["funding_rate"] = result["funding_rate"].fillna(0.0)
    result["open_interest"] = result["open_interest"].ffill()

    out_path = DATA_DIR / f"{symbol}_funding_4h.csv"
    result.to_csv(out_path, index=False)
    print(f"  💾 Saved → {out_path} ({len(result)} rows)")
    print(f"     funding_rate range: [{result['funding_rate'].min():.6f}, {result['funding_rate'].max():.6f}]")
    if not result["open_interest"].isna().all():
        print(f"     open_interest range: [{result['open_interest'].min():.0f}, {result['open_interest'].max():.0f}]")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Bybit funding rate + OI history")
    parser.add_argument("--symbol", "-s", type=str, default=None, help="Symbol (default: XRPUSDT and SUIUSDT)")
    parser.add_argument("--days",   "-d", type=int, default=730,  help="Days of history (default: 730)")
    args = parser.parse_args()

    symbols = [args.symbol] if args.symbol else ["XRPUSDT", "SUIUSDT"]
    for sym in symbols:
        build_funding_4h(sym, days=args.days)
        time.sleep(1)

    print("\n✅ Funding history fetch complete.")
