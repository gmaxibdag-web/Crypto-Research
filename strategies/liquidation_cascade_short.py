"""
Liquidation Cascade SHORT Strategy
-----------------------------------
INVERSE of long strategy: Short when liquidation cascade hits SHORT positions.

Signal logic:
  A liquidation cascade hitting SHORT positions occurs when:
    1. High liquidation volume (OI drop spike, top 10% of events)
    2. BULLISH (green) candle — SHORTS being liquidated (price rose, stops hit)
    3. POSITIVE funding rate — confirms bullish over-leverage (bulls paying)

  The combination creates a high-probability reversal DOWN signal.

  Calibration needed: Inverse logic may perform differently than long version.

Entry (signal=-1 for SHORT):
  1. liquidation_volume_usd > 90th percentile (major cascade event)
  2. Current candle is GREEN (close > open) — SHORTS being liquidated
  3. funding_rate > 0.00005 (positive funding = market over-leveraged bullish)

Exit (signal=1 for COVER):
  - Handled by backtester TP/SL (6% take profit, 3% stop loss)
  - Secondary: funding rate crosses below 0 (sentiment flip)

Note: Requires both liquidation data AND funding rate data.
      Run: python3 data/fetch_liquidation_history.py
           python3 data/fetch_funding_history.py

Timeframe: 4h (primary)
Confidence: Medium (needs backtest validation)
"""
import pandas as pd
import numpy as np


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Add RSI to dataframe."""
    delta    = df["close"].diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


def generate_signals(
    df: pd.DataFrame,
    cluster_pct_threshold: float  = 0.90,    # top 10% liq vol = major cascade
    funding_threshold: float      = 0.00005, # POSITIVE funding = bullish over-leverage
    use_rsi_filter: bool          = False,    # optional RSI filter (off by default)
    rsi_low: float                = 45.0,     # adjusted for short entries
    rsi_high: float               = 65.0,     # RSI > 45 but < 65 for short
    rsi_period: int               = 14,
) -> pd.DataFrame:
    """
    Generate SHORT signals based on inverse liquidation cascade.
    
    Required columns in df:
      - open, high, low, close (OHLCV)
      - liquidation_volume_usd (float, USD value of OI-derived liquidation proxy)
      - funding_rate (float, positive = bulls paying)
      - datetime

    Returns df with 'signal' column: -1=SHORT, 1=COVER, 0=hold
    """
    df = df.copy()

    # Validate required columns
    required = ["close", "open", "high", "low", "liquidation_volume_usd", "funding_rate"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"liquidation_cascade_short: missing columns: {missing}")

    df = add_rsi(df, period=rsi_period)
    df["signal"] = 0

    # ── COMPUTE THRESHOLDS ────────────────────────────────────────────────────

    liq_vol = df["liquidation_volume_usd"]
    cluster_threshold = liq_vol.quantile(cluster_pct_threshold)

    # ── SHORT ENTRY CONDITIONS ────────────────────────────────────────────────

    # 1. Major liquidation cluster (top 10% of liq vol events)
    #    OI-derived proxy: big OI drop × price = large liquidation USD volume
    cond_cluster = liq_vol > cluster_threshold

    # 2. GREEN candle confirms SHORT liquidations (price rose, short stops hit)
    cond_green_candle = df["close"] > df["open"]

    # 3. POSITIVE funding confirms over-leveraged bullish market
    #    Bulls paying bears = market was too long, fuel for reversal DOWN
    cond_pos_funding = df["funding_rate"] > funding_threshold

    short_cond = cond_cluster & cond_green_candle & cond_pos_funding

    # Optional RSI filter to avoid entries at deep overbought extremes
    if use_rsi_filter:
        rsi_ok = (df["rsi"] >= rsi_low) & (df["rsi"] <= rsi_high)
        short_cond = short_cond & rsi_ok

    df.loc[short_cond, "signal"] = -1  # SHORT signal

    # ── COVER CONDITIONS ──────────────────────────────────────────────────────

    # Funding rate crosses negative (sentiment flip — bulls no longer paying)
    funding_was_positive = df["funding_rate"].shift(1) > 0
    funding_now_negative = df["funding_rate"] <= 0
    df.loc[funding_was_positive & funding_now_negative & (df["signal"] == 0), "signal"] = 1  # COVER

    return df


def current_signal(df: pd.DataFrame) -> dict:
    """Return signal info for the latest candle."""
    df = generate_signals(df)
    last = df.iloc[-1]
    return {
        "price":                last["close"],
        "liquidation_vol_usd":  round(float(last.get("liquidation_volume_usd", 0)), 2),
        "funding_rate":         round(float(last.get("funding_rate", 0)), 6),
        "rsi":                  round(float(last.get("rsi", 0)), 2),
        "signal":               int(last["signal"]),  # -1=SHORT, 1=COVER, 0=hold
        "datetime":             last["datetime"],
    }