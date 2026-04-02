#!/usr/bin/env python3
"""
Multi-Strategy Comparison — KingK Crypto Trader
Runs all strategies on XRPUSDT 4h and SUIUSDT 4h and prints a summary table.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backtests.backtest import run_backtest

STRATEGIES = [
    ("ema_swing",                 0.06, 0.03),
    ("macd_rsi",                  0.06, 0.03),
    ("bollinger_mean_reversion",  0.05, 0.025),
    ("rsi_divergence_breakout",   0.08, 0.04),
]

PAIRS = [
    ("XRPUSDT", "240", 400),
    ("SUIUSDT", "240", 400),
]

def run_comparison():
    results = []

    for symbol, interval, capital in PAIRS:
        for strategy_name, tp, sl in STRATEGIES:
            tf_label = {"60": "1h", "240": "4h"}.get(interval, interval)
            try:
                r = run_backtest(
                    symbol=symbol,
                    capital=capital,
                    interval=interval,
                    strategy_name=strategy_name,
                    tp=tp,
                    sl=sl,
                    json_output=False,
                )
                if r:
                    results.append({
                        "symbol":    symbol,
                        "interval":  tf_label,
                        "strategy":  strategy_name,
                        "trades":    r["num_trades"],
                        "win_rate":  r["win_rate"] * 100,
                        "pnl_usd":   r["total_pnl_usd"],
                        "pnl_pct":   r["total_pnl_pct"],
                        "sharpe":    r["sharpe_ratio"],
                        "max_dd":    r["max_drawdown"] * 100,
                    })
            except Exception as e:
                print(f"  ERROR: {symbol} {strategy_name}: {e}")

    # Print summary table
    print("\n")
    print("=" * 110)
    print("  MULTI-STRATEGY COMPARISON — XRPUSDT & SUIUSDT | 4h | 2yr Data | $400 Capital")
    print("=" * 110)

    header = (f"  {'Symbol':<10} {'Strategy':<30} {'Trades':>6} {'Win%':>6} "
              f"{'P&L $':>8} {'P&L %':>7} {'Sharpe':>8} {'MaxDD%':>7}")
    print(header)
    print("  " + "-" * 106)

    # Sort by Sharpe descending
    results_sorted = sorted(results, key=lambda x: x["sharpe"], reverse=True)

    for r in results_sorted:
        pnl_sign = "+" if r["pnl_usd"] >= 0 else ""
        sharpe_flag = " 🏆" if r["sharpe"] == max(x["sharpe"] for x in results_sorted) else ""
        print(
            f"  {r['symbol']:<10} {r['strategy']:<30} {r['trades']:>6} "
            f"{r['win_rate']:>5.1f}% {pnl_sign}{r['pnl_usd']:>7.2f} "
            f"{pnl_sign}{r['pnl_pct']:>5.1f}% {r['sharpe']:>8.3f} "
            f"{r['max_dd']:>6.1f}%{sharpe_flag}"
        )

    print("=" * 110)
    print(f"  Best Sharpe overall: {results_sorted[0]['strategy']} on {results_sorted[0]['symbol']}")
    print("=" * 110)

    return results


if __name__ == "__main__":
    run_comparison()
