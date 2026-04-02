"""
KingK Final 5-Pair Backtest
Runs final backtest on all 5 pairs with the assigned optimal strategies.
Displays clean summary table.
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

# Strategy assignments from backtest
STRATEGY_ASSIGNMENT = {
    "BTCUSDT": "funding_rate_divergence",
    "ETHUSDT": "funding_rate_divergence",
    "SOLUSDT": "liquidation_cascade",
    "XRPUSDT": "funding_rate_divergence",
    "SUIUSDT": "liquidation_cascade",
}


def load(symbol: str, interval: str = "240") -> pd.DataFrame:
    """Load OHLCV data."""
    path = DATA_DIR / f"{symbol}_{interval}.csv"
    if not path.exists():
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


def run_final_backtest():
    """Run final backtest on all 5 pairs with assigned strategies."""
    
    results = []
    portfolio_trades = []

    print("\n" + "=" * 130)
    print("  KingK Final 5-Pair Backtest — Assigned Strategies | 4h | 2yr | $1000 per pair")
    print("=" * 130)
    print(f"  {'Pair':<10} {'Strategy':<30} {'Trades':>7} {'P&L $':>10} {'Sharpe':>8} {'WinRate':>8} {'MaxDD%':>7}")
    print("-" * 130)

    total_pnl = 0.0
    all_sharpes = []
    
    for symbol, strategy in STRATEGY_ASSIGNMENT.items():
        label = symbol.replace("USDT", "")

        # Load data
        df = load(symbol)
        if df is None:
            print(f"  ❌ {label:<10} — Missing OHLCV data")
            continue

        df_funding = load_funding(symbol)
        df_liquidations = load_liquidations(symbol)

        # --- Merge funding data ---
        if df_funding is not None:
            df = pd.merge_asof(
                df.sort_values("timestamp"),
                df_funding[["timestamp", "funding_rate", "open_interest"]].sort_values("timestamp"),
                on="timestamp",
                direction="backward"
            )
        else:
            df["funding_rate"] = 0.0
            df["open_interest"] = 0.0

        # --- Merge liquidation data ---
        if df_liquidations is not None:
            df = pd.merge_asof(
                df.sort_values("timestamp"),
                df_liquidations[["timestamp", "liquidation_volume_usd", "is_cluster"]].sort_values("timestamp"),
                on="timestamp",
                direction="backward"
            )
        else:
            df["liquidation_volume_usd"] = 0.0
            df["is_cluster"] = False

        # --- Run the assigned strategy ---
        if strategy == "funding_rate_divergence":
            from strategies.funding_rate_divergence import generate_signals
            df_signals = generate_signals(
                df.copy(),
                funding_threshold=-0.00005,
                oi_drop_pct=0.02,
                use_price_filter=False,
                use_rsi_filter=True,
            )
        elif strategy == "liquidation_cascade":
            from strategies.liquidation_cascade import generate_signals
            df_signals = generate_signals(
                df.copy(),
                cluster_pct_threshold=0.90,
                funding_threshold=-0.00005,
                use_rsi_filter=False,
            )
        else:
            print(f"  ❌ {label:<10} — Unknown strategy: {strategy}")
            continue

        # --- Simulate trades ---
        r = simulate(df_signals)
        results.append({
            "symbol": symbol,
            "label": label,
            "strategy": strategy,
            **r
        })
        
        portfolio_trades.append(r["total_pnl"])
        all_sharpes.append(r["sharpe"])
        total_pnl += r["total_pnl"]

        # Print row
        strategy_short = strategy.replace("_", " ").title()
        print(f"  {label:<10} {strategy_short:<30} {r['num_trades']:>7} "
              f"  ${r['total_pnl']:>9.2f} {r['sharpe']:>8.4f} "
              f"  {r['win_rate']:>6.1f}% {r['max_dd']:>7.1f}%")

    print("=" * 130)
    
    # Portfolio summary
    avg_sharpe = np.mean(all_sharpes) if all_sharpes else 0.0
    print(f"\n  📊 PORTFOLIO SUMMARY (5 pairs × $1000 each):")
    print(f"     Total P&L across all pairs:  ${total_pnl:,.2f}")
    print(f"     Average Sharpe per pair:     {avg_sharpe:.4f}")
    print(f"     Total capital deployed:      $5000")
    print(f"     Portfolio return:            {(total_pnl / 5000) * 100:.2f}%")
    
    print(f"\n  ✅ Final backtest complete.\n")
    return results, total_pnl, avg_sharpe


if __name__ == "__main__":
    run_final_backtest()
