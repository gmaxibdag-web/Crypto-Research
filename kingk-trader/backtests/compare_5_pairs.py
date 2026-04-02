"""
KingK 5-Pair Backtest Comparison
Tests both Funding Rate Divergence and Liquidation Cascade on all 5 pairs (BTC, ETH, SOL, XRP, SUI).
Generates a clean comparison table to determine the best strategy per pair.

Usage:
  python3 backtests/compare_5_pairs.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import math
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "historical"
CAPITAL = 1000  # Per-pair capital
TP = 0.06       # 6% take profit
SL = 0.03       # 3% stop loss


def load(symbol: str, interval: str = "240") -> pd.DataFrame:
    """Load OHLCV data."""
    path = DATA_DIR / f"{symbol}_{interval}.csv"
    if not path.exists():
        print(f"❌ Missing: {path}")
        return None
    df = pd.read_csv(path, parse_dates=["datetime"])
    return df.sort_values("datetime").reset_index(drop=True)


def load_funding(symbol: str) -> pd.DataFrame:
    """Load funding rate + OI data."""
    path = DATA_DIR / f"{symbol}_funding_4h.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["datetime"])
    return df.sort_values("datetime").reset_index(drop=True)


def load_liquidations(symbol: str) -> pd.DataFrame:
    """Load liquidation proxy data."""
    path = DATA_DIR / f"{symbol}_liquidations_4h.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["datetime"])
    return df.sort_values("datetime").reset_index(drop=True)


def sharpe(pnl_series: pd.Series, periods_per_year: int = 252) -> float:
    """Calculate Sharpe ratio."""
    if len(pnl_series) < 3:
        return 0.0
    mean_ret = pnl_series.mean()
    std_ret = pnl_series.std()
    if std_ret == 0:
        return 0.0
    return round((mean_ret / std_ret) * math.sqrt(periods_per_year / len(pnl_series)), 4)


def max_drawdown(equity: pd.Series) -> float:
    """Calculate max drawdown %."""
    if len(equity) < 2:
        return 0.0
    roll_max = equity.cummax()
    dd = (equity - roll_max) / roll_max
    return float(dd.min())


def simulate(df: pd.DataFrame, tp: float = TP, sl: float = SL) -> dict:
    """Simulate trades based on signal column."""
    trades = []
    in_trade = False
    entry_price = tp_price = sl_price = 0.0

    for _, row in df.iterrows():
        if not in_trade:
            if row.get("signal") == 1:
                in_trade = True
                entry_price = float(row["close"])
                tp_price = entry_price * (1 + tp)
                sl_price = entry_price * (1 - sl)
        else:
            hit_tp = float(row["high"]) >= tp_price
            hit_sl = float(row["low"]) <= sl_price
            exit_sig = row.get("signal") == -1
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


def run_backtest_all_pairs():
    """Run backtests on all 5 pairs with both strategies."""
    
    PAIRS = [
        ("BTCUSDT", "BTC"),
        ("ETHUSDT", "ETH"),
        ("SOLUSDT", "SOL"),
        ("XRPUSDT", "XRP"),
        ("SUIUSDT", "SUI"),
    ]

    results = []

    print("\n🔄 Running backtests for all 5 pairs...\n")

    for symbol, label in PAIRS:
        print(f"  Processing {label}...")

        # Load data
        df = load(symbol)
        if df is None:
            continue

        df_funding = load_funding(symbol)
        df_liquidations = load_liquidations(symbol)

        # --- Merge funding data into OHLCV ---
        if df_funding is not None:
            df_with_funding = pd.merge_asof(
                df.sort_values("timestamp"),
                df_funding[["timestamp", "funding_rate", "open_interest"]].sort_values("timestamp"),
                on="timestamp",
                direction="backward"
            )
        else:
            df_with_funding = df.copy()
            df_with_funding["funding_rate"] = 0.0
            df_with_funding["open_interest"] = 0.0

        # --- Merge liquidation data into OHLCV ---
        if df_liquidations is not None:
            df_with_all = pd.merge_asof(
                df_with_funding.sort_values("timestamp"),
                df_liquidations[["timestamp", "liquidation_volume_usd", "is_cluster"]].sort_values("timestamp"),
                on="timestamp",
                direction="backward"
            )
        else:
            df_with_all = df_with_funding.copy()
            df_with_all["liquidation_volume_usd"] = 0.0
            df_with_all["is_cluster"] = False

        # --- Strategy 1: Funding Rate Divergence ---
        if df_funding is not None:
            from strategies.funding_rate_divergence import generate_signals as frd_signals
            df_frd = frd_signals(
                df_with_all.copy(),
                funding_threshold=-0.00005,
                oi_drop_pct=0.02,
                use_price_filter=False,
                use_rsi_filter=True,
            )
            r_frd = simulate(df_frd)
            results.append({
                "Symbol": label,
                "Strategy": "Funding Rate Divergence",
                **r_frd
            })
        else:
            results.append({
                "Symbol": label,
                "Strategy": "Funding Rate Divergence",
                "num_trades": 0,
                "total_pnl": 0.0,
                "sharpe": 0.0,
                "win_rate": 0.0,
                "max_dd": 0.0,
                "error": "Missing funding data"
            })

        # --- Strategy 2: Liquidation Cascade ---
        if df_liquidations is not None:
            from strategies.liquidation_cascade import generate_signals as lc_signals
            df_lc = lc_signals(
                df_with_all.copy(),
                cluster_pct_threshold=0.90,
                funding_threshold=-0.00005,
                use_rsi_filter=False,
            )
            r_lc = simulate(df_lc)
            results.append({
                "Symbol": label,
                "Strategy": "Liquidation Cascade",
                **r_lc
            })
        else:
            results.append({
                "Symbol": label,
                "Strategy": "Liquidation Cascade",
                "num_trades": 0,
                "total_pnl": 0.0,
                "sharpe": 0.0,
                "win_rate": 0.0,
                "max_dd": 0.0,
                "error": "Missing liquidation data"
            })

    # Print results
    print("\n" + "=" * 120)
    print("  KingK 5-Pair Backtest Comparison — 4h | 2yr | $1000 capital per pair")
    print("=" * 120)
    print(f"  {'Pair':<6} {'Strategy':<28} {'Trades':>7} {'P&L $':>10} {'Sharpe':>8} {'WinRate':>8} {'MaxDD%':>7}")
    print("-" * 120)

    # Group by pair and show winner
    pair_winners = {}
    for label in ["BTC", "ETH", "SOL", "XRP", "SUI"]:
        pair_results = [r for r in results if r["Symbol"] == label]
        if not pair_results:
            continue

        # Print both strategies
        for r in pair_results:
            error_flag = f" ⚠ {r.get('error', '')}" if "error" in r else ""
            print(f"  {r['Symbol']:<6} {r['Strategy']:<28} {r['num_trades']:>7} "
                  f"  ${r['total_pnl']:>9.2f} {r['sharpe']:>8.4f} "
                  f"  {r['win_rate']:>6.1f}% {r['max_dd']:>7.1f}%{error_flag}")

        # Determine winner for this pair
        valid = [r for r in pair_results if "error" not in r]
        if valid:
            winner = max(valid, key=lambda x: x["sharpe"])
            pair_winners[label] = winner["Strategy"]
            print(f"  → {label} winner: {winner['Strategy']} (Sharpe={winner['sharpe']:.4f})")

        print()

    print("=" * 120)
    print("\n📋 STRATEGY ASSIGNMENT (recommended for config/settings.py):\n")
    for label in ["BTC", "ETH", "SOL", "XRP", "SUI"]:
        if label in pair_winners:
            strategy_module = {
                "Funding Rate Divergence": "funding_rate_divergence",
                "Liquidation Cascade": "liquidation_cascade"
            }.get(pair_winners[label], "unknown")
            symbol = f"{label}USDT"
            print(f'    "{symbol}": "{strategy_module}",  # Sharpe={[r["sharpe"] for r in results if r["Symbol"] == label and r["Strategy"] == pair_winners[label]][0]:.4f}')

    print("\n✅ Backtest complete.\n")
    return results, pair_winners


if __name__ == "__main__":
    run_backtest_all_pairs()
