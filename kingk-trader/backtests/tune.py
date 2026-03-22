"""
Strategy Tuner — KingK-Swing-v1
Tests multiple parameter combinations on deep historical data.
Adds 50 EMA trend filter + tighter RSI.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "historical"

def load(symbol: str, interval: str = "240") -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / f"{symbol}_{interval}.csv", parse_dates=["datetime"])

def add_indicators(df, ema_fast, ema_slow, ema_trend, rsi_period):
    df = df.copy()
    df["ema_fast"]  = df["close"].ewm(span=ema_fast,  adjust=False).mean()
    df["ema_slow"]  = df["close"].ewm(span=ema_slow,  adjust=False).mean()
    df["ema_trend"] = df["close"].ewm(span=ema_trend, adjust=False).mean()

    delta = df["close"].diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_g = gain.ewm(com=rsi_period-1, adjust=False).mean()
    avg_l = loss.ewm(com=rsi_period-1, adjust=False).mean()
    rs    = avg_g / avg_l.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    df["vol_ma20"] = df["volume"].rolling(20).mean()

    df["cross_up"]   = (df["ema_fast"] > df["ema_slow"]) & (df["ema_fast"].shift(1) <= df["ema_slow"].shift(1))
    df["cross_down"] = (df["ema_fast"] < df["ema_slow"]) & (df["ema_fast"].shift(1) >= df["ema_slow"].shift(1))
    return df

def backtest(df, params) -> dict:
    ema_fast   = params["ema_fast"]
    ema_slow   = params["ema_slow"]
    ema_trend  = params["ema_trend"]
    rsi_min    = params["rsi_min"]
    rsi_max    = params["rsi_max"]
    vol_mult   = params["vol_mult"]
    tp         = params["tp"]
    sl         = params["sl"]
    capital    = 400

    df = add_indicators(df, ema_fast, ema_slow, ema_trend, 14)

    trades = []
    in_trade = False
    entry_price = tp_price = sl_price = 0

    for _, row in df.iterrows():
        if pd.isna(row["rsi"]) or pd.isna(row["vol_ma20"]):
            continue
        if not in_trade:
            # Trend filter: price must be above trend EMA
            trend_ok = row["close"] > row["ema_trend"]
            rsi_ok   = rsi_min <= row["rsi"] <= rsi_max
            vol_ok   = row["volume"] > row["vol_ma20"] * vol_mult
            if row["cross_up"] and trend_ok and rsi_ok and vol_ok:
                in_trade    = True
                entry_price = row["close"]
                tp_price    = entry_price * (1 + tp)
                sl_price    = entry_price * (1 - sl)
        else:
            hit_tp = row["high"] >= tp_price
            hit_sl = row["low"]  <= sl_price
            exit_x = row["cross_down"]
            if hit_tp or hit_sl or exit_x:
                exit_price = tp_price if hit_tp else (sl_price if hit_sl else row["close"])
                reason     = "TP" if hit_tp else ("SL" if hit_sl else "EMA_X")
                pnl_pct    = (exit_price - entry_price) / entry_price
                trades.append({"pnl_pct": pnl_pct, "pnl_usd": capital * pnl_pct, "reason": reason})
                in_trade = False

    if len(trades) < 5:
        return None  # not enough trades to be meaningful

    t         = pd.DataFrame(trades)
    wins      = t[t["pnl_usd"] > 0]
    losses    = t[t["pnl_usd"] < 0]
    win_rate  = len(wins) / len(t) * 100
    total_pnl = t["pnl_usd"].sum()
    avg_win   = wins["pnl_usd"].mean() if len(wins) else 0
    avg_loss  = losses["pnl_usd"].mean() if len(losses) else 0
    expectancy = (win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss)

    return {
        "trades":     len(t),
        "win_rate":   round(win_rate, 1),
        "total_pnl":  round(total_pnl, 2),
        "expectancy": round(expectancy, 2),
        "avg_win":    round(avg_win, 2),
        "avg_loss":   round(avg_loss, 2),
        "tp_exits":   len(t[t["reason"]=="TP"]),
        "sl_exits":   len(t[t["reason"]=="SL"]),
    }

def run_tuner():
    param_grid = [
        {"ema_fast": f, "ema_slow": s, "ema_trend": tr,
         "rsi_min": rmin, "rsi_max": rmax,
         "vol_mult": vm, "tp": tp, "sl": sl}
        for f    in [9, 12]
        for s    in [21, 26]
        for tr   in [50, 100]
        for rmin in [45, 50]
        for rmax in [65, 70]
        for vm   in [1.0, 1.2]
        for tp   in [0.05, 0.06, 0.08]
        for sl   in [0.025, 0.03]
    ]

    print(f"Testing {len(param_grid)} parameter combinations...\n")

    for symbol in ["XRPUSDT", "SUIUSDT"]:
        df = load(symbol)
        results = []

        for params in param_grid:
            r = backtest(df, params)
            if r:
                r.update(params)
                results.append(r)

        if not results:
            print(f"{symbol}: No valid results found.")
            continue

        res_df = pd.DataFrame(results)
        # Sort by expectancy * win_rate (composite score)
        res_df["score"] = res_df["expectancy"] * res_df["win_rate"]
        best = res_df.sort_values("score", ascending=False).head(5)

        print(f"\n{'='*65}")
        print(f"  TOP 5 CONFIGS — {symbol}")
        print(f"{'='*65}")
        cols = ["ema_fast","ema_slow","ema_trend","rsi_min","rsi_max",
                "tp","sl","trades","win_rate","total_pnl","expectancy","score"]
        print(best[cols].to_string(index=False))

        top = best.iloc[0]
        print(f"\n  🏆 BEST: EMA {int(top['ema_fast'])}/{int(top['ema_slow'])} | "
              f"Trend EMA {int(top['ema_trend'])} | RSI {int(top['rsi_min'])}-{int(top['rsi_max'])} | "
              f"TP {top['tp']*100:.0f}% SL {top['sl']*100:.1f}% | "
              f"Win {top['win_rate']}% | P&L ${top['total_pnl']} | "
              f"Expectancy ${top['expectancy']}/trade")

if __name__ == "__main__":
    print("🔬 KingK Strategy Tuner — 2 years deep history")
    run_tuner()
