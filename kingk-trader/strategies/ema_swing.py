"""
KingK-Swing-v1: EMA Crossover + RSI + Volume Filter
-----------------------------------------------------
Entry:  9 EMA crosses above 21 EMA
        RSI(14) between 45-65
        Volume > 1.2x 20-period average
Exit:   +6% TP or -3% SL or 9 EMA crosses below 21 EMA
"""
import pandas as pd
import numpy as np

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # EMAs
    df["ema9"]  = df["close"].ewm(span=9, adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()

    # RSI
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    # Volume MA
    df["vol_ma20"] = df["volume"].rolling(20).mean()

    # EMA cross signal
    df["ema_cross_up"]   = (df["ema9"] > df["ema21"]) & (df["ema9"].shift(1) <= df["ema21"].shift(1))
    df["ema_cross_down"] = (df["ema9"] < df["ema21"]) & (df["ema9"].shift(1) >= df["ema21"].shift(1))

    return df

def generate_signals(df: pd.DataFrame,
                     rsi_min: float = 45, rsi_max: float = 65,
                     vol_mult: float = 1.2) -> pd.DataFrame:
    df = add_indicators(df)
    df["signal"] = 0  # 0=hold, 1=buy, -1=sell
    df.loc[
        df["ema_cross_up"] &
        df["rsi"].between(rsi_min, rsi_max) &
        (df["volume"] > df["vol_ma20"] * vol_mult),
        "signal"
    ] = 1
    df.loc[df["ema_cross_down"], "signal"] = -1
    return df

def current_signal(df: pd.DataFrame) -> dict:
    """Return the signal for the latest completed candle."""
    df = generate_signals(df)
    last = df.iloc[-1]
    prev = df.iloc[-2]
    return {
        "price":    last["close"],
        "ema9":     round(last["ema9"], 4),
        "ema21":    round(last["ema21"], 4),
        "rsi":      round(last["rsi"], 2),
        "volume":   last["volume"],
        "vol_ma20": round(last["vol_ma20"], 2),
        "signal":   int(last["signal"]),
        "datetime": last["datetime"],
    }
