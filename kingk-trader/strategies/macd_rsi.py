"""
MACD + RSI Strategy
-------------------
Entry:  MACD histogram crosses from negative to positive (MACD crosses signal line)
        RSI(14) < 70 (not overbought)
Exit:   MACD histogram crosses from positive to negative
        OR -1 signal from strategy
"""
import pandas as pd
import numpy as np


def add_indicators(df: pd.DataFrame,
                   macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9,
                   rsi_period: int = 14) -> pd.DataFrame:
    df = df.copy()

    # MACD
    ema_fast = df["close"].ewm(span=macd_fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=macd_slow, adjust=False).mean()
    df["macd_line"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd_line"].ewm(span=macd_signal, adjust=False).mean()
    df["macd_hist"] = df["macd_line"] - df["macd_signal"]

    # RSI
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=rsi_period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=rsi_period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    return df


def generate_signals(df: pd.DataFrame,
                     macd_fast: int = 12, macd_slow: int = 26, macd_signal_period: int = 9,
                     rsi_period: int = 14, rsi_max: float = 70) -> pd.DataFrame:
    """
    Generate signals for MACD + RSI strategy.
    signal: 1=buy, -1=sell, 0=hold
    """
    df = add_indicators(df, macd_fast=macd_fast, macd_slow=macd_slow,
                         macd_signal=macd_signal_period, rsi_period=rsi_period)
    df["signal"] = 0

    # Buy: MACD histogram crosses zero upward (MACD crosses above signal line) AND RSI < rsi_max
    hist_cross_up = (df["macd_hist"] > 0) & (df["macd_hist"].shift(1) <= 0)
    buy_cond = hist_cross_up & (df["rsi"] < rsi_max)
    df.loc[buy_cond, "signal"] = 1

    # Sell: MACD histogram crosses zero downward
    hist_cross_down = (df["macd_hist"] < 0) & (df["macd_hist"].shift(1) >= 0)
    df.loc[hist_cross_down, "signal"] = -1

    return df


def current_signal(df: pd.DataFrame) -> dict:
    df = generate_signals(df)
    last = df.iloc[-1]
    return {
        "price": last["close"],
        "macd_line": round(last["macd_line"], 6),
        "macd_signal": round(last["macd_signal"], 6),
        "macd_hist": round(last["macd_hist"], 6),
        "rsi": round(last["rsi"], 2),
        "signal": int(last["signal"]),
        "datetime": last["datetime"],
    }
