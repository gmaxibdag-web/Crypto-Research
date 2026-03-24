"""
Bollinger Bands Mean Reversion Strategy
-----------------------------------------
Entry:  Price closes below/touches lower Bollinger Band (20 period, 2 std)
        AND volume > 1.2x 20-period volume MA (confirmation)
Exit:   Price reaches middle band (20 SMA) — mean reversion complete
        OR -1 signal
"""
import pandas as pd
import numpy as np


def add_indicators(df: pd.DataFrame,
                   bb_period: int = 20, bb_std: float = 2.0,
                   vol_ma_period: int = 20) -> pd.DataFrame:
    df = df.copy()

    # Bollinger Bands
    df["bb_mid"] = df["close"].rolling(bb_period).mean()
    bb_rolling_std = df["close"].rolling(bb_period).std()
    df["bb_upper"] = df["bb_mid"] + bb_std * bb_rolling_std
    df["bb_lower"] = df["bb_mid"] - bb_std * bb_rolling_std

    # Volume MA
    df["vol_ma"] = df["volume"].rolling(vol_ma_period).mean()

    # %B (price position within BB) — 0 = lower band, 1 = upper band
    bb_range = df["bb_upper"] - df["bb_lower"]
    df["pct_b"] = (df["close"] - df["bb_lower"]) / bb_range.replace(0, np.nan)

    return df


def generate_signals(df: pd.DataFrame,
                     bb_period: int = 20, bb_std: float = 2.0,
                     vol_ma_period: int = 20, vol_mult: float = 1.2) -> pd.DataFrame:
    """
    Generate signals for Bollinger Bands mean reversion strategy.
    signal: 1=buy (at lower band), -1=sell (at middle band / exit), 0=hold
    """
    df = add_indicators(df, bb_period=bb_period, bb_std=bb_std, vol_ma_period=vol_ma_period)
    df["signal"] = 0

    # Buy: close touches or goes below lower band + volume spike
    touch_lower = df["close"] <= df["bb_lower"]
    vol_spike = df["volume"] > df["vol_ma"] * vol_mult
    buy_cond = touch_lower & vol_spike
    df.loc[buy_cond, "signal"] = 1

    # Sell: price crosses back up through the middle band (mean reversion complete)
    # close crosses above middle band from below
    cross_mid = (df["close"] >= df["bb_mid"]) & (df["close"].shift(1) < df["bb_mid"].shift(1))
    df.loc[cross_mid, "signal"] = -1

    return df


def current_signal(df: pd.DataFrame) -> dict:
    df = generate_signals(df)
    last = df.iloc[-1]
    return {
        "price": last["close"],
        "bb_upper": round(last["bb_upper"], 6),
        "bb_mid": round(last["bb_mid"], 6),
        "bb_lower": round(last["bb_lower"], 6),
        "pct_b": round(last.get("pct_b", float("nan")), 4),
        "vol_ma": round(last["vol_ma"], 2),
        "signal": int(last["signal"]),
        "datetime": last["datetime"],
    }
