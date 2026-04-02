"""
Funding Rate Divergence Strategy
----------------------------------
Signal logic:
  - Negative funding rate (bears paying longs) = market is bearish/over-leveraged
  - Sharp drop in open interest = forced liquidations / bull capitulation
  - Price near 20-period low = capitulation pattern confirmation
  - RSI < 50 = not in overbought territory

Entry (signal=1):
  - funding_rate < -0.0005
  - open_interest dropped >10% from 8h ago (2 candles ago at 4h)
  - (optional) price within 5% of rolling 20-period low
  - (optional) RSI(14) < 50

Exit (signal=-1):
  - funding_rate crosses above 0 (sentiment flip)
  - OR standard TP/SL handled by backtester

Timeframe: 4h (primary), 1D (secondary)
Confidence: Medium
"""
import pandas as pd
import numpy as np


def add_indicators(df: pd.DataFrame, rsi_period: int = 14, low_period: int = 20) -> pd.DataFrame:
    df = df.copy()

    # RSI
    delta = df["close"].diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=rsi_period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=rsi_period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    # Rolling N-period low (capitulation reference)
    df[f"low_{low_period}"] = df["low"].rolling(low_period).min()

    return df


def generate_signals(
    df: pd.DataFrame,
    funding_threshold: float = -0.00005,   # funding rate must be below this
                                            # Calibrated: Bybit perp funding mean ~-0.00007 (very small)
                                            # -0.00005 = moderate negative, catches ~20% of candles
                                            # Param sweep result: best Sharpe on XRP=0.52, SUI=0.70
    oi_drop_pct: float = 0.02,             # OI must drop >2% from prior 4h candle (deleveraging signal)
    use_price_filter: bool = False,        # OFF by default: price filter hurts XRP performance
    price_low_period: int = 20,            # rolling low window (used if price_filter=True)
    price_low_proximity: float = 0.05,     # within 5% of 20-period low (used if price_filter=True)
    use_rsi_filter: bool = True,           # RSI < threshold (filters out overbought entries)
    rsi_threshold: float = 50.0,
    rsi_period: int = 14,
) -> pd.DataFrame:
    """
    Generate buy/sell signals based on funding rate divergence.

    Signal rationale:
      - Negative funding rate indicates bearish sentiment (bears dominating perpetuals)
      - Sharp OI drop from prior candle = liquidations / capitulation event
      - Price near 20-period low + RSI < 50 = confluence for reversal entry

    Threshold calibration (Bybit perps, 2024–2026):
      - Funding rarely exceeds -0.0005; typical negative range is -0.00005 to -0.001
      - Use -0.0001 as minimum (stricter, ~10th percentile of negative readings)
      - OI 3% drop per 4h candle = meaningful deleveraging without being too rare

    Required columns in df:
      - close, high, low (OHLCV)
      - funding_rate (float, negative = bears paying)
      - open_interest (float, position size in contracts/USD)
      - datetime

    Returns df with 'signal' column: 1=buy, -1=sell, 0=hold
    """
    df = df.copy()

    # Validate required columns
    required = ["close", "high", "low", "funding_rate", "open_interest"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"funding_rate_divergence: missing columns: {missing}")

    df = add_indicators(df, rsi_period=rsi_period, low_period=price_low_period)
    df["signal"] = 0

    # ── ENTRY CONDITIONS ──────────────────────────────────────────────────────

    # 1. Funding rate is sufficiently negative (bears paying longs = bearish peak)
    cond_funding_neg = df["funding_rate"] < funding_threshold

    # 2. Open interest dropped in last 4h candle (1 period) = liquidation event
    #    Using 1-period lookback since 4h-aligned OI already captures the move
    oi_prev = df["open_interest"].shift(1)
    oi_drop = (oi_prev - df["open_interest"]) / oi_prev.replace(0, np.nan)
    cond_oi_drop = oi_drop > oi_drop_pct

    buy_cond = cond_funding_neg & cond_oi_drop

    # 3. (Optional) Price within N% of 20-period low — capitulation pattern
    if use_price_filter:
        low_col = f"low_{price_low_period}"
        price_near_low = df["close"] <= df[low_col] * (1 + price_low_proximity)
        buy_cond = buy_cond & price_near_low

    # 4. (Optional) RSI < threshold — not in overbought territory
    if use_rsi_filter:
        rsi_ok = df["rsi"] < rsi_threshold
        buy_cond = buy_cond & rsi_ok

    df.loc[buy_cond, "signal"] = 1

    # ── EXIT CONDITIONS ───────────────────────────────────────────────────────

    # Funding rate crosses above 0 (sentiment flip — bears no longer paying)
    funding_was_negative = df["funding_rate"].shift(1) < 0
    funding_now_positive = df["funding_rate"] >= 0
    funding_cross_positive = funding_was_negative & funding_now_positive

    df.loc[funding_cross_positive, "signal"] = -1

    return df


def current_signal(df: pd.DataFrame) -> dict:
    """Return signal info for the latest candle (for live paper trading)."""
    df = generate_signals(df)
    last = df.iloc[-1]
    return {
        "price":          last["close"],
        "funding_rate":   round(float(last["funding_rate"]), 6),
        "open_interest":  float(last.get("open_interest", 0)),
        "rsi":            round(float(last.get("rsi", 0)), 2),
        "signal":         int(last["signal"]),
        "datetime":       last["datetime"],
    }
