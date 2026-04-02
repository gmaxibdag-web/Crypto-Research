"""
KingK Strategy Tuner — All Strategies
Sweeps key parameters for MACD+RSI, Bollinger MR, and RSI Divergence.
Tests on XRPUSDT + SUIUSDT 4h, tracks best Sharpe per strategy.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import math
import pandas as pd
import numpy as np
from pathlib import Path
from itertools import product

DATA_DIR = Path(__file__).parent.parent / "data" / "historical"
CAPITAL = 400


def load(symbol: str, interval: str = "240") -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / f"{symbol}_{interval}.csv", parse_dates=["datetime"])
    return df.sort_values("datetime").reset_index(drop=True)


def sharpe(pnl_series: pd.Series, periods_per_year: int = 252) -> float:
    if len(pnl_series) < 3:
        return -99.0
    mean_ret = pnl_series.mean()
    std_ret = pnl_series.std()
    if std_ret == 0:
        return 0.0
    return round((mean_ret / std_ret) * math.sqrt(periods_per_year / len(pnl_series)), 4)


def simulate_trades(df: pd.DataFrame, tp: float = 0.06, sl: float = 0.03) -> list:
    """Run basic TP/SL simulation on a signal-bearing df."""
    trades = []
    in_trade = False
    entry_price = tp_price = sl_price = 0.0

    for _, row in df.iterrows():
        if not in_trade:
            if row["signal"] == 1:
                in_trade = True
                entry_price = float(row["close"])
                tp_price = entry_price * (1 + tp)
                sl_price = entry_price * (1 - sl)
        else:
            hit_tp = float(row["high"]) >= tp_price
            hit_sl = float(row["low"]) <= sl_price
            exit_sig = row["signal"] == -1
            if hit_tp or hit_sl or exit_sig:
                if hit_tp:
                    exit_price = tp_price
                elif hit_sl:
                    exit_price = sl_price
                else:
                    exit_price = float(row["close"])
                pnl_pct = (exit_price - entry_price) / entry_price
                trades.append({"pnl_pct": pnl_pct, "pnl_usd": CAPITAL * pnl_pct})
                in_trade = False
    return trades


def score_trades(trades: list) -> dict:
    if len(trades) < 3:
        return None
    t = pd.DataFrame(trades)
    total_pnl = t["pnl_usd"].sum()
    sr = sharpe(t["pnl_pct"])
    wins = t[t["pnl_usd"] > 0]
    win_rate = len(wins) / len(t) * 100
    return {
        "num_trades": len(t),
        "total_pnl": round(total_pnl, 2),
        "sharpe": sr,
        "win_rate": round(win_rate, 1),
    }


# ─── MACD + RSI Tuner ────────────────────────────────────────────────────────

def tune_macd_rsi(df_xrp, df_sui):
    from strategies.macd_rsi import generate_signals

    rsi_max_vals   = [60, 65, 70]
    macd_pairs     = [(12, 26), (9, 21), (8, 17)]

    results = []
    for rsi_max, (mf, ms) in product(rsi_max_vals, macd_pairs):
        row = {"rsi_max": rsi_max, "macd_fast": mf, "macd_slow": ms}
        combined_pnl = 0
        combined_trades = []
        valid = True
        for sym, df in [("XRP", df_xrp), ("SUI", df_sui)]:
            try:
                sdf = generate_signals(df.copy(), macd_fast=mf, macd_slow=ms,
                                       macd_signal_period=9, rsi_max=rsi_max)
                trades = simulate_trades(sdf)
                s = score_trades(trades)
                if s:
                    row[f"{sym}_pnl"] = s["total_pnl"]
                    row[f"{sym}_sharpe"] = s["sharpe"]
                    row[f"{sym}_trades"] = s["num_trades"]
                    combined_pnl += s["total_pnl"]
                    combined_trades.extend([t["pnl_pct"] for t in trades])
                else:
                    row[f"{sym}_pnl"] = 0
                    row[f"{sym}_sharpe"] = -99
                    row[f"{sym}_trades"] = 0
            except Exception as e:
                valid = False
                break
        if not valid:
            continue
        if combined_trades:
            row["combined_pnl"] = round(combined_pnl, 2)
            row["combined_sharpe"] = sharpe(pd.Series(combined_trades))
        else:
            row["combined_sharpe"] = -99
            row["combined_pnl"] = 0
        results.append(row)

    return pd.DataFrame(results).sort_values("combined_sharpe", ascending=False)


# ─── Bollinger MR Tuner ──────────────────────────────────────────────────────

def tune_bollinger(df_xrp, df_sui):
    from strategies.bollinger_mean_reversion import generate_signals

    bb_periods  = [15, 20, 25]
    bb_stds     = [1.5, 2.0, 2.5]
    rsi_ranges  = [(25, 50), (30, 55), (35, 60)]

    results = []
    for bb_period, bb_std, (rsi_min, rsi_max) in product(bb_periods, bb_stds, rsi_ranges):
        row = {"bb_period": bb_period, "bb_std": bb_std, "rsi_min": rsi_min, "rsi_max": rsi_max}
        combined_pnl = 0
        combined_trades = []
        valid = True
        for sym, df in [("XRP", df_xrp), ("SUI", df_sui)]:
            try:
                sdf = generate_signals(df.copy(), bb_period=bb_period, bb_std=bb_std,
                                       rsi_min=rsi_min, rsi_max=rsi_max)
                trades = simulate_trades(sdf)
                s = score_trades(trades)
                if s:
                    row[f"{sym}_pnl"] = s["total_pnl"]
                    row[f"{sym}_sharpe"] = s["sharpe"]
                    row[f"{sym}_trades"] = s["num_trades"]
                    combined_pnl += s["total_pnl"]
                    combined_trades.extend([t["pnl_pct"] for t in trades])
                else:
                    row[f"{sym}_pnl"] = 0
                    row[f"{sym}_sharpe"] = -99
                    row[f"{sym}_trades"] = 0
            except Exception as e:
                valid = False
                break
        if not valid:
            continue
        if combined_trades:
            row["combined_pnl"] = round(combined_pnl, 2)
            row["combined_sharpe"] = sharpe(pd.Series(combined_trades))
        else:
            row["combined_sharpe"] = -99
            row["combined_pnl"] = 0
        results.append(row)

    return pd.DataFrame(results).sort_values("combined_sharpe", ascending=False)


# ─── RSI Divergence Tuner ────────────────────────────────────────────────────

def tune_rsi_divergence(df_xrp, df_sui):
    from strategies.rsi_divergence_breakout import generate_signals

    rsi_oversold_vals = [35, 40, 45, 50]
    vol_mult_vals     = [1.2, 1.5, 1.8]

    results = []
    for rsi_oversold, vol_mult in product(rsi_oversold_vals, vol_mult_vals):
        row = {"rsi_oversold": rsi_oversold, "vol_mult": vol_mult}
        combined_pnl = 0
        combined_trades = []
        valid = True
        for sym, df in [("XRP", df_xrp), ("SUI", df_sui)]:
            try:
                sdf = generate_signals(df.copy(), rsi_oversold=rsi_oversold, vol_mult=vol_mult)
                trades = simulate_trades(sdf)
                s = score_trades(trades)
                if s:
                    row[f"{sym}_pnl"] = s["total_pnl"]
                    row[f"{sym}_sharpe"] = s["sharpe"]
                    row[f"{sym}_trades"] = s["num_trades"]
                    combined_pnl += s["total_pnl"]
                    combined_trades.extend([t["pnl_pct"] for t in trades])
                else:
                    row[f"{sym}_pnl"] = 0
                    row[f"{sym}_sharpe"] = -99
                    row[f"{sym}_trades"] = 0
            except Exception as e:
                valid = False
                break
        if not valid:
            continue
        if combined_trades:
            row["combined_pnl"] = round(combined_pnl, 2)
            row["combined_sharpe"] = sharpe(pd.Series(combined_trades))
        else:
            row["combined_sharpe"] = -99
            row["combined_pnl"] = 0
        results.append(row)

    return pd.DataFrame(results).sort_values("combined_sharpe", ascending=False)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("📊 KingK Multi-Strategy Tuner — 4h 2yr data")
    print("=" * 65)

    df_xrp = load("XRPUSDT", "240")
    df_sui = load("SUIUSDT", "240")

    best_configs = {}

    # ── MACD + RSI ──
    print("\n🔬 Tuning MACD + RSI...")
    macd_res = tune_macd_rsi(df_xrp, df_sui)
    if not macd_res.empty:
        top3 = macd_res.head(3)
        print("\n  Top 3 MACD+RSI configs (by combined Sharpe):")
        cols = ["macd_fast", "macd_slow", "rsi_max", "XRP_pnl", "XRP_sharpe",
                "SUI_pnl", "SUI_sharpe", "combined_pnl", "combined_sharpe"]
        print(top3[cols].to_string(index=False))
        best = macd_res.iloc[0]
        best_configs["macd_rsi"] = {
            "macd_fast": int(best["macd_fast"]),
            "macd_slow": int(best["macd_slow"]),
            "rsi_max": float(best["rsi_max"]),
            "combined_sharpe": float(best["combined_sharpe"]),
            "combined_pnl": float(best["combined_pnl"]),
            "SUI_pnl": float(best.get("SUI_pnl", 0)),
            "SUI_sharpe": float(best.get("SUI_sharpe", 0)),
        }
        print(f"\n  🏆 Best: fast={int(best['macd_fast'])} slow={int(best['macd_slow'])} rsi_max={best['rsi_max']}")
        print(f"     Combined Sharpe={best['combined_sharpe']:.3f} | P&L=${best['combined_pnl']:.2f}")

    # ── Bollinger MR ──
    print("\n🔬 Tuning Bollinger Mean Reversion...")
    boll_res = tune_bollinger(df_xrp, df_sui)
    if not boll_res.empty:
        top3 = boll_res.head(3)
        print("\n  Top 3 Bollinger MR configs (by combined Sharpe):")
        cols = ["bb_period", "bb_std", "rsi_min", "rsi_max", "XRP_pnl", "XRP_sharpe",
                "SUI_pnl", "SUI_sharpe", "combined_pnl", "combined_sharpe"]
        print(top3[cols].to_string(index=False))
        best = boll_res.iloc[0]
        best_configs["bollinger_mr"] = {
            "bb_period": int(best["bb_period"]),
            "bb_std": float(best["bb_std"]),
            "rsi_min": float(best["rsi_min"]),
            "rsi_max": float(best["rsi_max"]),
            "combined_sharpe": float(best["combined_sharpe"]),
            "combined_pnl": float(best["combined_pnl"]),
            "SUI_pnl": float(best.get("SUI_pnl", 0)),
            "SUI_sharpe": float(best.get("SUI_sharpe", 0)),
        }
        print(f"\n  🏆 Best: period={int(best['bb_period'])} std={best['bb_std']} RSI={best['rsi_min']}-{best['rsi_max']}")
        print(f"     Combined Sharpe={best['combined_sharpe']:.3f} | P&L=${best['combined_pnl']:.2f}")

    # ── RSI Divergence ──
    print("\n🔬 Tuning RSI Divergence Breakout...")
    rsi_res = tune_rsi_divergence(df_xrp, df_sui)
    if not rsi_res.empty:
        top3 = rsi_res.head(3)
        print("\n  Top 3 RSI Divergence configs (by combined Sharpe):")
        cols = ["rsi_oversold", "vol_mult", "XRP_pnl", "XRP_sharpe",
                "SUI_pnl", "SUI_sharpe", "combined_pnl", "combined_sharpe"]
        print(top3[cols].to_string(index=False))
        best = rsi_res.iloc[0]
        best_configs["rsi_divergence"] = {
            "rsi_oversold": float(best["rsi_oversold"]),
            "vol_mult": float(best["vol_mult"]),
            "combined_sharpe": float(best["combined_sharpe"]),
            "combined_pnl": float(best["combined_pnl"]),
            "SUI_pnl": float(best.get("SUI_pnl", 0)),
            "SUI_sharpe": float(best.get("SUI_sharpe", 0)),
        }
        print(f"\n  🏆 Best: rsi_oversold={best['rsi_oversold']} vol_mult={best['vol_mult']}")
        print(f"     Combined Sharpe={best['combined_sharpe']:.3f} | P&L=${best['combined_pnl']:.2f}")

    print("\n" + "=" * 65)
    print("✅ Tuning complete. Best configs saved.")
    return best_configs


if __name__ == "__main__":
    best = main()
    print("\nBest configs summary:")
    for k, v in best.items():
        print(f"  {k}: {v}")
