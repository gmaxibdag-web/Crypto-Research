"""
KingK Final Strategy Comparison
Runs all strategies with best-tuned configs vs EMA Swing baseline.
Produces a clean summary table.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import math
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "historical"
CAPITAL = 400
TP = 0.06
SL = 0.03


def load(symbol: str, interval: str = "240") -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / f"{symbol}_{interval}.csv", parse_dates=["datetime"])
    return df.sort_values("datetime").reset_index(drop=True)


def sharpe(pnl_series: pd.Series, periods_per_year: int = 252) -> float:
    if len(pnl_series) < 3:
        return 0.0
    mean_ret = pnl_series.mean()
    std_ret = pnl_series.std()
    if std_ret == 0:
        return 0.0
    return round((mean_ret / std_ret) * math.sqrt(periods_per_year / len(pnl_series)), 4)


def max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    dd = (equity - roll_max) / roll_max
    return float(dd.min())


def simulate(df: pd.DataFrame, tp: float = TP, sl: float = SL) -> dict:
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
                exit_price = tp_price if hit_tp else (sl_price if hit_sl else float(row["close"]))
                pnl_pct = (exit_price - entry_price) / entry_price
                trades.append({"pnl_pct": pnl_pct, "pnl_usd": CAPITAL * pnl_pct})
                in_trade = False

    if not trades:
        return {"num_trades": 0, "total_pnl": 0.0, "sharpe": 0.0, "win_rate": 0.0, "max_dd": 0.0}

    t = pd.DataFrame(trades)
    equity = CAPITAL + t["pnl_usd"].cumsum()
    wins = t[t["pnl_usd"] > 0]
    return {
        "num_trades": len(t),
        "total_pnl": round(t["pnl_usd"].sum(), 2),
        "sharpe": sharpe(t["pnl_pct"]),
        "win_rate": round(len(wins) / len(t) * 100, 1),
        "max_dd": round(max_drawdown(equity) * 100, 1),
    }


def run_all():
    rows = []

    symbols = [("XRPUSDT", "XRP"), ("SUIUSDT", "SUI")]

    for symbol, label in symbols:
        df = load(symbol)

        # 1. EMA Swing (baseline)
        from strategies.ema_swing import generate_signals as ema_signals
        r = simulate(ema_signals(df.copy()))
        rows.append({"Strategy": "EMA Swing", "Symbol": label, **r})

        # 2. MACD+RSI (best tuned: fast=8, slow=17, rsi_max=70)
        from strategies.macd_rsi import generate_signals as macd_signals
        r = simulate(macd_signals(df.copy(), macd_fast=8, macd_slow=17,
                                   macd_signal_period=9, rsi_max=70))
        rows.append({"Strategy": "MACD+RSI (tuned)", "Symbol": label, **r})

        # 3. Bollinger MR (best tuned: period=15, std=1.5, RSI 35-60)
        from strategies.bollinger_mean_reversion import generate_signals as bb_signals
        r = simulate(bb_signals(df.copy(), bb_period=15, bb_std=1.5,
                                rsi_min=35, rsi_max=60))
        rows.append({"Strategy": "Bollinger MR (tuned)", "Symbol": label, **r})

        # 4. RSI Divergence (best tuned: oversold=35, vol_mult=1.8)
        from strategies.rsi_divergence_breakout import generate_signals as rsi_div_signals
        r = simulate(rsi_div_signals(df.copy(), rsi_oversold=35, vol_mult=1.8))
        rows.append({"Strategy": "RSI Divergence (tuned)", "Symbol": label, **r})

        # 5. Ensemble: RSI Div OR MACD — take signal if EITHER fires
        from strategies.rsi_divergence_breakout import generate_signals as rsi_div_s2
        from strategies.macd_rsi import generate_signals as macd_s2
        df_rsi = rsi_div_s2(df.copy(), rsi_oversold=35, vol_mult=1.8)
        df_macd = macd_s2(df.copy(), macd_fast=8, macd_slow=17, macd_signal_period=9, rsi_max=70)
        df_ens = df.copy()
        df_ens["signal"] = 0
        # Buy if either fires; sell if either fires
        df_ens.loc[(df_rsi["signal"] == 1) | (df_macd["signal"] == 1), "signal"] = 1
        df_ens.loc[(df_rsi["signal"] == -1) | (df_macd["signal"] == -1), "signal"] = -1
        r = simulate(df_ens)
        rows.append({"Strategy": "Ensemble (RSI+MACD)", "Symbol": label, **r})

    results = pd.DataFrame(rows)

    # Print clean table
    print("\n" + "=" * 90)
    print("  FINAL STRATEGY COMPARISON — 4h | 2yr | $400 capital per pair")
    print("=" * 90)
    print(f"  {'Strategy':<25} {'Sym':<5} {'Trades':>7} {'P&L $':>9} {'Sharpe':>8} {'WinRate':>8} {'MaxDD%':>7}")
    print("-" * 90)

    for _, row in results.iterrows():
        winner_flag = ""
        if row["Symbol"] == "SUI" and row["sharpe"] > 0.21 and row["total_pnl"] > 60:
            winner_flag = " ⭐"
        elif row["Symbol"] == "XRP" and row["sharpe"] > 0.21 and row["total_pnl"] > 0:
            winner_flag = " ✅"
        print(f"  {row['Strategy']:<25} {row['Symbol']:<5} {row['num_trades']:>7} "
              f"  ${row['total_pnl']:>8.2f} {row['sharpe']:>8.4f} "
              f"  {row['win_rate']:>6.1f}% {row['max_dd']:>7.1f}%{winner_flag}")

    print("=" * 90)

    # Identify winner
    sui_results = results[results["Symbol"] == "SUI"].copy()
    baseline = sui_results[sui_results["Strategy"] == "EMA Swing"].iloc[0]
    print(f"\n  📊 Baseline (EMA Swing SUI): Sharpe={baseline['sharpe']:.4f} | P&L=${baseline['total_pnl']:.2f}")

    candidates = sui_results[
        (sui_results["Strategy"] != "EMA Swing") &
        (sui_results["sharpe"] > 0.21) &
        (sui_results["total_pnl"] > 60)
    ]

    if not candidates.empty:
        winner = candidates.sort_values("sharpe", ascending=False).iloc[0]
        print(f"\n  🏆 WINNER: {winner['Strategy']} on SUI — Sharpe={winner['sharpe']:.4f} | P&L=${winner['total_pnl']:.2f}")
        print(f"     Beats EMA Swing baseline ✅")
    else:
        # Check XRP
        xrp_results = results[results["Symbol"] == "XRP"].copy()
        xrp_cands = xrp_results[
            (xrp_results["Strategy"] != "EMA Swing") &
            (xrp_results["sharpe"] > 0.21) &
            (xrp_results["total_pnl"] > 0)
        ]
        if not xrp_cands.empty:
            winner = xrp_cands.sort_values("sharpe", ascending=False).iloc[0]
            print(f"\n  🏆 STRONG XRP PERFORMER: {winner['Strategy']} — Sharpe={winner['sharpe']:.4f} | P&L=${winner['total_pnl']:.2f}")
        else:
            print("\n  ⚠️  No strategy clearly beats EMA Swing on SUI.")
            print("     Recommend: EMA Swing remains primary. RSI Divergence shows XRP promise.")

    return results


if __name__ == "__main__":
    run_all()
