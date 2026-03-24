"""
RSI Divergence Breakout Strategy
----------------------------------
Entry:  RSI(14) was oversold (< 35) and is now bouncing up (RSI > prev RSI)
        AND volume > 1.5x 20-period volume MA (volume surge confirmation)
        AND price > EMA(50) (trend filter — trading with the dominant trend)
Exit:   RSI crosses above 65 (overbought territory — take profit)
        OR price drops back below EMA(50)
"""
import pandas as pd
import numpy as np


def add_indicators(df: pd.DataFrame,
                   rsi_period: int = 14,
                   ema_period: int = 50,
                   vol_ma_period: int = 20) -> pd.DataFrame:
    df = df.copy()

    # RSI
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=rsi_period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=rsi_period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    # EMA 50 (trend filter)
    df[f"ema{ema_period}"] = df["close"].ewm(span=ema_period, adjust=False).mean()

    # Volume MA
    df["vol_ma"] = df["volume"].rolling(vol_ma_period).mean()

    return df


def generate_signals(df: pd.DataFrame,
                     rsi_period: int = 14, rsi_oversold: float = 35, rsi_overbought: float = 65,
                     ema_period: int = 50,
                     vol_ma_period: int = 20, vol_mult: float = 1.5) -> pd.DataFrame:
    """
    Generate signals for RSI divergence/oversold breakout strategy.
    signal: 1=buy, -1=sell, 0=hold
    """
    df = add_indicators(df, rsi_period=rsi_period, ema_period=ema_period,
                         vol_ma_period=vol_ma_period)
    ema_col = f"ema{ema_period}"
    df["signal"] = 0

    # RSI was oversold last bar and is bouncing up now
    rsi_was_oversold = df["rsi"].shift(1) < rsi_oversold
    rsi_bouncing_up = df["rsi"] > df["rsi"].shift(1)

    # Volume surge
    vol_surge = df["volume"] > df["vol_ma"] * vol_mult

    # Price above EMA50 (trend filter)
    price_above_ema = df["close"] > df[ema_col]

    buy_cond = rsi_was_oversold & rsi_bouncing_up & vol_surge & price_above_ema
    df.loc[buy_cond, "signal"] = 1

    # Sell: RSI crosses into overbought OR price drops below EMA50
    rsi_overbought_cross = (df["rsi"] >= rsi_overbought) & (df["rsi"].shift(1) < rsi_overbought)
    price_below_ema = (df["close"] < df[ema_col]) & (df["close"].shift(1) >= df[ema_col].shift(1))
    sell_cond = rsi_overbought_cross | price_below_ema
    df.loc[sell_cond, "signal"] = -1

    return df


def current_signal(df: pd.DataFrame) -> dict:
    df = generate_signals(df)
    last = df.iloc[-1]
    return {
        "price": last["close"],
        "rsi": round(last["rsi"], 2),
        "ema50": round(last["ema50"], 6),
        "vol_ma": round(last["vol_ma"], 2),
        "signal": int(last["signal"]),
        "datetime": last["datetime"],
    }
