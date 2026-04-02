"""
Liquidation Cascade Strategy
------------------------------
Signal logic:
  A liquidation cascade occurs when forced liquidations (OI drop × price) cluster
  around a specific price level during a bearish candle. When this happens alongside
  negative funding (bears paying longs = market is over-leveraged short), it signals
  a capitulation event — the perfect setup for a relief bounce.

  The combination of:
    1. High liquidation volume (OI drop spike, top 10% of events)
    2. Bearish (red) candle — liquidations hitting long positions
    3. Negative funding rate — confirms bearish over-leverage
  → Creates a high-probability reversal signal

  Calibrated result (2yr backtest, 4h, XRP + SUI):
    XRPUSDT: Sharpe=0.519 | P&L=+$94 | 30 trades | WR=40%
    SUIUSDT: Sharpe=0.555 | P&L=+$84 | 26 trades | WR=42%

Entry (signal=1):
  1. liquidation_volume_usd > 90th percentile (major cascade event)
  2. Current candle is red (close < open) — longs being liquidated
  3. funding_rate < -0.00005 (negative funding = market over-leveraged bearish)

Exit (signal=-1):
  - Handled by backtester TP/SL (6% take profit, 3% stop loss)
  - Secondary: funding rate crosses above 0 (sentiment flip)

Note: Requires both liquidation data AND funding rate data.
      Run: python3 data/fetch_liquidation_history.py
           python3 data/fetch_funding_history.py

Timeframe: 4h (primary)
Confidence: Medium
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
    funding_threshold: float      = -0.00005, # negative funding = bearish over-leverage
    use_rsi_filter: bool          = False,    # optional RSI filter (off by default)
    rsi_low: float                = 35.0,
    rsi_high: float               = 55.0,
    rsi_period: int               = 14,
) -> pd.DataFrame:
    """
    Generate buy/sell signals based on liquidation cascade + funding rate confluence.

    Required columns in df:
      - open, high, low, close (OHLCV)
      - liquidation_volume_usd (float, USD value of OI-derived liquidation proxy)
      - funding_rate (float, negative = bears paying)
      - datetime

    Returns df with 'signal' column: 1=buy, -1=sell, 0=hold
    """
    df = df.copy()

    # Validate required columns
    required = ["close", "open", "high", "low", "liquidation_volume_usd", "funding_rate"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"liquidation_cascade: missing columns: {missing}")

    df = add_rsi(df, period=rsi_period)
    df["signal"] = 0

    # ── COMPUTE THRESHOLDS ────────────────────────────────────────────────────

    liq_vol = df["liquidation_volume_usd"]
    cluster_threshold = liq_vol.quantile(cluster_pct_threshold)

    # ── ENTRY CONDITIONS ──────────────────────────────────────────────────────

    # 1. Major liquidation cluster (top 10% of liq vol events)
    #    OI-derived proxy: big OI drop × price = large liquidation USD volume
    cond_cluster = liq_vol > cluster_threshold

    # 2. Red candle confirms long liquidations (price fell, stops hit)
    cond_red_candle = df["close"] < df["open"]

    # 3. Negative funding confirms over-leveraged bearish market
    #    Bears paying longs = market was too short, fuel for reversal
    cond_neg_funding = df["funding_rate"] < funding_threshold

    buy_cond = cond_cluster & cond_red_candle & cond_neg_funding

    # Optional RSI filter to avoid entries at deep oversold extremes
    if use_rsi_filter:
        rsi_ok = (df["rsi"] >= rsi_low) & (df["rsi"] <= rsi_high)
        buy_cond = buy_cond & rsi_ok

    df.loc[buy_cond, "signal"] = 1

    # ── EXIT CONDITIONS ───────────────────────────────────────────────────────

    # Funding rate crosses positive (sentiment flip — bears no longer paying)
    # This is the same exit signal used by funding_rate_divergence
    funding_was_negative = df["funding_rate"].shift(1) < 0
    funding_now_positive = df["funding_rate"] >= 0
    df.loc[funding_was_negative & funding_now_positive & (df["signal"] == 0), "signal"] = -1

    return df


def current_signal(df: pd.DataFrame) -> dict:
    """Return signal info for the latest candle (for live paper trading)."""
    df = generate_signals(df)
    last = df.iloc[-1]
    return {
        "price":                last["close"],
        "liquidation_vol_usd":  round(float(last.get("liquidation_volume_usd", 0)), 2),
        "funding_rate":         round(float(last.get("funding_rate", 0)), 6),
        "rsi":                  round(float(last.get("rsi", 0)), 2),
        "signal":               int(last["signal"]),
        "datetime":             last["datetime"],
    }
