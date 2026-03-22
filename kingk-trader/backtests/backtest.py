"""
KingK Backtester - EMA Swing v1
Simulates trades on historical 4h candles.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import numpy as np
from data.fetcher import get_klines
from strategies.ema_swing import generate_signals
from config.settings import TAKE_PROFIT_PCT, STOP_LOSS_PCT

def run_backtest(symbol: str, capital: float = 400, interval: str = "240",
                 limit: int = 500, tp: float = TAKE_PROFIT_PCT, sl: float = STOP_LOSS_PCT):

    df = get_klines(symbol, interval=interval, limit=limit)
    df = generate_signals(df)

    trades = []
    in_trade = False
    entry_price = 0
    entry_time = None
    tp_price = 0
    sl_price = 0

    for i, row in df.iterrows():
        if not in_trade:
            if row["signal"] == 1:
                in_trade = True
                entry_price = row["close"]
                entry_time  = row["datetime"]
                tp_price    = entry_price * (1 + tp)
                sl_price    = entry_price * (1 - sl)
        else:
            # Check TP/SL on this candle
            hit_tp = row["high"] >= tp_price
            hit_sl = row["low"]  <= sl_price
            exit_signal = row["signal"] == -1

            if hit_tp or hit_sl or exit_signal:
                if hit_tp:
                    exit_price = tp_price
                    reason = "TP"
                elif hit_sl:
                    exit_price = sl_price
                    reason = "SL"
                else:
                    exit_price = row["close"]
                    reason = "EMA_X"

                pnl_pct = (exit_price - entry_price) / entry_price
                pnl_usd = capital * pnl_pct

                trades.append({
                    "entry_time":  entry_time,
                    "exit_time":   row["datetime"],
                    "entry_price": round(entry_price, 6),
                    "exit_price":  round(exit_price, 6),
                    "pnl_pct":     round(pnl_pct * 100, 2),
                    "pnl_usd":     round(pnl_usd, 2),
                    "reason":      reason,
                })
                in_trade = False

    if not trades:
        print(f"\n{symbol}: No trades generated in this period.")
        return

    results = pd.DataFrame(trades)
    total_pnl   = results["pnl_usd"].sum()
    win_trades  = results[results["pnl_usd"] > 0]
    loss_trades = results[results["pnl_usd"] < 0]
    win_rate    = len(win_trades) / len(results) * 100
    avg_win     = win_trades["pnl_usd"].mean() if len(win_trades) else 0
    avg_loss    = loss_trades["pnl_usd"].mean() if len(loss_trades) else 0

    print(f"\n{'='*55}")
    print(f"  BACKTEST: {symbol} | {interval}h candles | {len(df)} bars")
    print(f"{'='*55}")
    print(f"  Trades:       {len(results)}")
    print(f"  Win Rate:     {win_rate:.1f}%")
    print(f"  Total P&L:    ${total_pnl:.2f} ({total_pnl/capital*100:.1f}% on ${capital})")
    print(f"  Avg Win:      ${avg_win:.2f}")
    print(f"  Avg Loss:     ${avg_loss:.2f}")
    print(f"  Best Trade:   ${results['pnl_usd'].max():.2f}")
    print(f"  Worst Trade:  ${results['pnl_usd'].min():.2f}")
    print(f"\n  Exit Reasons: {results['reason'].value_counts().to_dict()}")
    print(f"{'='*55}")
    print(f"\n  Last 5 trades:")
    print(results[["entry_time","exit_time","entry_price","exit_price","pnl_pct","pnl_usd","reason"]].tail(5).to_string(index=False))
    return results

if __name__ == "__main__":
    print("🔬 Running KingK-Swing-v1 Backtest...")
    for sym, cap in [("XRPUSDT", 400), ("SUIUSDT", 400)]:
        run_backtest(sym, capital=cap, limit=500)
