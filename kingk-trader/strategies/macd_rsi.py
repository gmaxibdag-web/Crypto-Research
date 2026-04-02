"""
MACD + RSI Strategy (v2 — trend-filtered)
------------------------------------------
Entry:  MACD histogram crosses from negative to positive (MACD crosses signal line)
        RSI(14) < rsi_max (not overbought)
        Price > EMA100 (trend filter — only longs in uptrends)
        Minimum 5 bars since last trade (cooldown)
Exit:   MACD histogram crosses from positive to negative
        OR -1 signal from strategy
"""
import pandas as pd
import numpy as np


def add_indicators(df: pd.DataFrame,
                   macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9,
                   rsi_period: int = 14, ema_trend: int = 100) -> pd.DataFrame:
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

    # EMA100 trend filter
    df[f"ema{ema_trend}"] = df["close"].ewm(span=ema_trend, adjust=False).mean()

    return df


def generate_signals(df: pd.DataFrame,
                     macd_fast: int = 12, macd_slow: int = 26, macd_signal_period: int = 9,
                     rsi_period: int = 14, rsi_max: float = 70,
                     ema_trend: int = 100, min_bars_between_trades: int = 5) -> pd.DataFrame:
    """
    Generate signals for MACD + RSI strategy with EMA100 trend filter and trade cooldown.
    signal: 1=buy, -1=sell, 0=hold
    """
    df = add_indicators(df, macd_fast=macd_fast, macd_slow=macd_slow,
                         macd_signal=macd_signal_period, rsi_period=rsi_period,
                         ema_trend=ema_trend)
    ema_col = f"ema{ema_trend}"
    df["signal"] = 0

    last_trade_bar = -999  # track bar index of last entry

    for i in range(len(df)):
        row = df.iloc[i]

        # Buy: MACD histogram crosses zero upward AND RSI < rsi_max
        #      AND price > EMA100 (trend filter)
        #      AND minimum bars since last trade
        hist_cross_up = (row["macd_hist"] > 0) and (df.iloc[i - 1]["macd_hist"] <= 0) if i > 0 else False
        rsi_ok = row["rsi"] < rsi_max
        trend_ok = row["close"] > row[ema_col]
        cooldown_ok = (i - last_trade_bar) >= min_bars_between_trades

        if hist_cross_up and rsi_ok and trend_ok and cooldown_ok:
            df.at[df.index[i], "signal"] = 1
            last_trade_bar = i

        # Sell: MACD histogram crosses zero downward
        elif i > 0:
            hist_cross_down = (row["macd_hist"] < 0) and (df.iloc[i - 1]["macd_hist"] >= 0)
            if hist_cross_down:
                df.at[df.index[i], "signal"] = -1

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
        "ema100": round(last["ema100"], 6),
        "signal": int(last["signal"]),
        "datetime": last["datetime"],
    }
