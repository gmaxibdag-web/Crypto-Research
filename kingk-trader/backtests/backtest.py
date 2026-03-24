"""
KingK Backtester — Multi-Strategy
Simulates trades on historical candles loaded from CSV.

Usage:
  python3 backtests/backtest.py                         # runs default (ema_swing, all symbols/intervals)
  python3 backtests/backtest.py --symbol XRPUSDT --interval 240 --strategy macd_rsi
  python3 backtests/backtest.py --symbol SUIUSDT --interval 240 --strategy bollinger_mean_reversion --tp 0.05 --sl 0.025 --json-output
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import argparse
import importlib
import json
import math
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "historical"
STRATEGIES_DIR = Path(__file__).parent.parent / "strategies"


# ── Data Loading ──────────────────────────────────────────────────────────────

def load_csv(symbol: str, interval: str) -> pd.DataFrame:
    path = DATA_DIR / f"{symbol}_{interval}.csv"
    if not path.exists():
        raise FileNotFoundError(f"No CSV found: {path}. Run data/fetch_history.py first.")
    df = pd.read_csv(path, parse_dates=["datetime"])
    return df.sort_values("datetime").reset_index(drop=True)


# ── Strategy Loader ───────────────────────────────────────────────────────────

def load_strategy_module(strategy_name: str):
    """Dynamically import a strategy module from strategies/."""
    strategy_path = STRATEGIES_DIR / f"{strategy_name}.py"
    if not strategy_path.exists():
        raise FileNotFoundError(f"Strategy not found: {strategy_path}")

    spec = importlib.util.spec_from_file_location(strategy_name, strategy_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── Metrics ───────────────────────────────────────────────────────────────────

def calculate_sharpe(pnl_series: pd.Series, periods_per_year: int = 252) -> float:
    """
    Annualised Sharpe ratio from a series of trade P&L percentages.
    Uses 0% as risk-free rate.
    """
    if len(pnl_series) < 2:
        return 0.0
    mean_ret = pnl_series.mean()
    std_ret = pnl_series.std()
    if std_ret == 0:
        return 0.0
    # Annualise: sqrt(periods_per_year / num_trades) is a common approximation for trade-level Sharpe
    sharpe = (mean_ret / std_ret) * math.sqrt(periods_per_year / len(pnl_series))
    return round(sharpe, 4)


def calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """Max drawdown as a fraction (e.g. 0.15 = 15%)."""
    roll_max = equity_curve.cummax()
    drawdown = (equity_curve - roll_max) / roll_max
    return float(drawdown.min())


# ── Core Backtest ─────────────────────────────────────────────────────────────

def run_backtest(symbol: str, capital: float = 400, interval: str = "240",
                 strategy_name: str = "ema_swing",
                 tp: float = None, sl: float = None,
                 json_output: bool = False):
    """
    Run a backtest for a given symbol/interval/strategy.

    Args:
        symbol: e.g. "XRPUSDT"
        capital: starting capital in USD
        interval: candle interval — "60", "240", etc.
        strategy_name: module name in strategies/ (without .py)
        tp: take profit fraction (e.g. 0.06 for 6%). Defaults to 0.06.
        sl: stop loss fraction (e.g. 0.03 for 3%). Defaults to 0.03.
        json_output: if True, print single JSON line and return dict

    Returns:
        dict of results (or None if no trades)
    """
    # Defaults
    if tp is None:
        tp = 0.06
    if sl is None:
        sl = 0.03

    # Load data
    df = load_csv(symbol, interval)

    # Load and apply strategy
    module = load_strategy_module(strategy_name)
    df = module.generate_signals(df)

    # Simulate trades
    trades = []
    in_trade = False
    entry_price = 0.0
    entry_time = None
    tp_price = 0.0
    sl_price = 0.0

    for i, row in df.iterrows():
        if not in_trade:
            if row["signal"] == 1:
                in_trade = True
                entry_price = float(row["close"])
                entry_time  = row["datetime"]
                tp_price    = entry_price * (1 + tp)
                sl_price    = entry_price * (1 - sl)
        else:
            hit_tp = float(row["high"]) >= tp_price
            hit_sl = float(row["low"]) <= sl_price
            exit_signal = row["signal"] == -1

            if hit_tp or hit_sl or exit_signal:
                if hit_tp:
                    exit_price = tp_price
                    reason = "TP"
                elif hit_sl:
                    exit_price = sl_price
                    reason = "SL"
                else:
                    exit_price = float(row["close"])
                    reason = "EXIT_SIGNAL"

                pnl_pct = (exit_price - entry_price) / entry_price
                pnl_usd = capital * pnl_pct

                trades.append({
                    "entry_time":  str(entry_time),
                    "exit_time":   str(row["datetime"]),
                    "entry_price": round(entry_price, 6),
                    "exit_price":  round(exit_price, 6),
                    "pnl_pct":     round(pnl_pct * 100, 4),
                    "pnl_usd":     round(pnl_usd, 2),
                    "reason":      reason,
                })
                in_trade = False

    if not trades:
        result = {
            "symbol": symbol, "interval": interval, "strategy": strategy_name,
            "capital": capital, "tp": tp, "sl": sl,
            "num_trades": 0, "total_pnl_usd": 0, "total_pnl_pct": 0,
            "win_rate": 0, "sharpe_ratio": 0, "max_drawdown": 0,
            "avg_win_usd": 0, "avg_loss_usd": 0,
            "best_trade_usd": 0, "worst_trade_usd": 0,
            "exit_reasons": {},
        }
        if json_output:
            print(json.dumps(result))
        else:
            tf_label = {"60": "1h", "240": "4h"}.get(interval, interval)
            print(f"\n{symbol} | {tf_label} | {strategy_name}: No trades generated.")
        return result

    results_df = pd.DataFrame(trades)

    total_pnl_usd  = results_df["pnl_usd"].sum()
    total_pnl_pct  = total_pnl_usd / capital * 100
    win_trades     = results_df[results_df["pnl_usd"] > 0]
    loss_trades    = results_df[results_df["pnl_usd"] < 0]
    win_rate       = len(win_trades) / len(results_df) if len(results_df) else 0
    avg_win_usd    = float(win_trades["pnl_usd"].mean()) if len(win_trades) else 0
    avg_loss_usd   = float(loss_trades["pnl_usd"].mean()) if len(loss_trades) else 0

    # Sharpe ratio (trade-level)
    sharpe = calculate_sharpe(results_df["pnl_pct"] / 100)

    # Equity curve & max drawdown
    equity = capital + results_df["pnl_usd"].cumsum()
    max_dd = calculate_max_drawdown(equity)

    exit_reasons = results_df["reason"].value_counts().to_dict()

    output = {
        "symbol":          symbol,
        "interval":        interval,
        "strategy":        strategy_name,
        "capital":         capital,
        "tp":              tp,
        "sl":              sl,
        "num_bars":        len(df),
        "num_trades":      len(results_df),
        "total_pnl_usd":   round(total_pnl_usd, 2),
        "total_pnl_pct":   round(total_pnl_pct, 2),
        "win_rate":        round(win_rate, 4),
        "sharpe_ratio":    sharpe,
        "max_drawdown":    round(max_dd, 4),
        "avg_win_usd":     round(avg_win_usd, 2),
        "avg_loss_usd":    round(avg_loss_usd, 2),
        "best_trade_usd":  round(float(results_df["pnl_usd"].max()), 2),
        "worst_trade_usd": round(float(results_df["pnl_usd"].min()), 2),
        "exit_reasons":    exit_reasons,
    }

    if json_output:
        print(json.dumps(output))
        return output

    # Pretty print
    tf_label = {"60": "1h", "240": "4h"}.get(interval, interval)
    print(f"\n{'='*60}")
    print(f"  BACKTEST: {symbol} | {tf_label} | strategy={strategy_name} | {len(df)} bars")
    print(f"{'='*60}")
    print(f"  Trades:       {len(results_df)}")
    print(f"  Win Rate:     {win_rate*100:.1f}%")
    print(f"  Total P&L:    ${total_pnl_usd:.2f} ({total_pnl_pct:.1f}% on ${capital})")
    print(f"  Sharpe Ratio: {sharpe:.3f}")
    print(f"  Max Drawdown: {max_dd*100:.1f}%")
    print(f"  Avg Win:      ${avg_win_usd:.2f}")
    print(f"  Avg Loss:     ${avg_loss_usd:.2f}")
    print(f"  Best Trade:   ${output['best_trade_usd']:.2f}")
    print(f"  Worst Trade:  ${output['worst_trade_usd']:.2f}")
    print(f"  Exit Reasons: {exit_reasons}")
    print(f"{'='*60}")
    print(f"\n  Last 5 trades:")
    cols = ["entry_time", "exit_time", "entry_price", "exit_price", "pnl_pct", "pnl_usd", "reason"]
    print(results_df[cols].tail(5).to_string(index=False))

    return output


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="KingK Multi-Strategy Backtester")
    parser.add_argument("--symbol",      "-s", type=str,   default=None,      help="Symbol e.g. XRPUSDT")
    parser.add_argument("--interval",    "-i", type=str,   default="240",     help="Candle interval: 60, 240")
    parser.add_argument("--strategy",         type=str,   default="ema_swing", help="Strategy module name (without .py)")
    parser.add_argument("--tp",               type=float, default=None,       help="Take profit fraction e.g. 0.06")
    parser.add_argument("--sl",               type=float, default=None,       help="Stop loss fraction e.g. 0.03")
    parser.add_argument("--capital",          type=float, default=400,        help="Starting capital USD")
    parser.add_argument("--json-output",      action="store_true",            help="Print single JSON result line")
    args = parser.parse_args()

    if args.symbol:
        run_backtest(
            symbol=args.symbol,
            capital=args.capital,
            interval=args.interval,
            strategy_name=args.strategy,
            tp=args.tp,
            sl=args.sl,
            json_output=args.json_output,
        )
    else:
        # Default: run all symbols on all intervals with ema_swing
        print("🔬 Running KingK-Swing-v1 Backtest — 2yr historical data")
        for interval in ["60", "240"]:
            for sym, cap in [("XRPUSDT", 400), ("SUIUSDT", 400)]:
                run_backtest(sym, capital=cap, interval=interval)


if __name__ == "__main__":
    main()
