"""
Funding Rate Divergence SHORT Strategy
----------------------------------------
INVERSE of long strategy: Short when market is over-leveraged LONG.

Signal logic:
  - Positive funding rate (bulls paying bears) = market is bullish/over-leveraged
  - Sharp INCREASE in open interest = new longs entering, over-extension
  - Price near 20-period HIGH = overbought pattern confirmation
  - RSI > 50 = not in oversold territory

Entry (signal=-1 for SHORT):
  - funding_rate > 0.00005 (bulls paying)
  - open_interest INCREASED >2% from 8h ago (new longs entering)
  - (optional) price within 5% of rolling 20-period HIGH
  - (optional) RSI(14) > 50

Exit (signal=1 for COVER):
  - funding_rate crosses below 0 (sentiment flip)
  - OR standard TP/SL handled by backtester

Timeframe: 4h (primary), 1D (secondary)
Confidence: Medium (inverse logic needs validation)
"""
import pandas as pd
import numpy as np


def add_indicators(df: pd.DataFrame, rsi_period: int = 14, high_period: int = 20) -> pd.DataFrame:
    df = df.copy()

    # RSI
    delta = df["close"].diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=rsi_period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=rsi_period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    # Rolling N-period HIGH (overbought reference)
    df[f"high_{high_period}"] = df["high"].rolling(high_period).max()

    return df


def generate_signals(
    df: pd.DataFrame,
    funding_threshold: float = 0.00005,    # funding rate must be ABOVE this (bulls paying)
    oi_increase_pct: float = 0.02,         # OI must INCREASE >2% from prior 4h candle
    use_price_filter: bool = False,        # OFF by default
    price_high_period: int = 20,           # rolling high window
    price_high_proximity: float = 0.05,    # within 5% of 20-period high
    use_rsi_filter: bool = True,           # RSI > threshold (filters out oversold entries)
    rsi_threshold: float = 50.0,
    rsi_period: int = 14,
) -> pd.DataFrame:
    """
    Generate SHORT signals based on inverse funding rate divergence.
    
    Signal rationale:
      - Positive funding rate indicates bullish sentiment (bulls dominating perpetuals)
      - Sharp OI INCREASE from prior candle = new longs entering, over-extension
      - Price near 20-period high + RSI > 50 = confluence for reversal DOWN

    Returns df with 'signal' column: -1=SHORT, 1=COVER, 0=hold
    """
    df = df.copy()

    # Validate required columns (open_interest is optional)
    required = ["close", "high", "low", "funding_rate", "datetime"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"funding_rate_divergence_short: missing columns: {missing}")
    
    # Add open_interest if missing
    if "open_interest" not in df.columns:
        df["open_interest"] = 0

    df = add_indicators(df, rsi_period=rsi_period, high_period=price_high_period)
    df["signal"] = 0

    # ── SHORT ENTRY CONDITIONS ────────────────────────────────────────────────

    # 1. Funding rate is sufficiently POSITIVE (bulls paying bears = bullish peak)
    cond_funding_pos = df["funding_rate"] > funding_threshold

    # 2. Open interest INCREASED in last 4h candle = new longs entering
    #    Handle missing OI data
    if "open_interest" not in df.columns or df["open_interest"].isna().all():
        # If no OI data, skip this condition
        cond_oi_increase = pd.Series(True, index=df.index)
    else:
        oi_prev = df["open_interest"].shift(1)
        oi_increase = (df["open_interest"] - oi_prev) / oi_prev.replace(0, np.nan)
        cond_oi_increase = oi_increase > oi_increase_pct

    short_cond = cond_funding_pos & cond_oi_increase

    # 3. (Optional) Price within N% of 20-period HIGH — overbought pattern
    if use_price_filter:
        high_col = f"high_{price_high_period}"
        price_near_high = df["close"] >= df[high_col] * (1 - price_high_proximity)
        short_cond = short_cond & price_near_high

    # 4. (Optional) RSI > threshold — not in oversold territory
    if use_rsi_filter:
        rsi_ok = df["rsi"] > rsi_threshold
        short_cond = short_cond & rsi_ok

    df.loc[short_cond, "signal"] = -1  # SHORT signal

    # ── COVER CONDITIONS ──────────────────────────────────────────────────────

    # Funding rate crosses below 0 (sentiment flip — bulls no longer paying)
    funding_was_positive = df["funding_rate"].shift(1) > 0
    funding_now_negative = df["funding_rate"] <= 0
    funding_cross_negative = funding_was_positive & funding_now_negative

    df.loc[funding_cross_negative, "signal"] = 1  # COVER signal

    return df


def current_signal(df: pd.DataFrame) -> dict:
    """Return signal info for the latest candle."""
    df = generate_signals(df)
    last = df.iloc[-1]
    return {
        "price":          last["close"],
        "funding_rate":   round(float(last["funding_rate"]), 6),
        "open_interest":  float(last.get("open_interest", 0)),
        "rsi":            round(float(last.get("rsi", 0)), 2),
        "signal":         int(last["signal"]),  # -1=SHORT, 1=COVER, 0=hold
        "datetime":       last["datetime"],
    }