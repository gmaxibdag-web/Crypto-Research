"""
KingK Paper Trader — simulates live trading with real prices, zero risk.
Tracks open positions, P&L, portfolio value in real time.
State persists in logs/paper_portfolio.json
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
from datetime import datetime, timezone
from pathlib import Path
from data.fetcher import get_klines, get_ticker
from agents.failsafe import safe_call
from config.settings import PAIRS, ALLOCATION, STRATEGY

PORTFOLIO_FILE = Path(__file__).parent.parent / "logs" / "paper_portfolio.json"
LOG_FILE       = Path(__file__).parent.parent / "logs" / "paper_trades.log"

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def log(msg: str):
    line = f"[{now_utc()}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def load_portfolio() -> dict:
    if PORTFOLIO_FILE.exists():
        return json.loads(PORTFOLIO_FILE.read_text())
    # Fresh portfolio
    return {
        "cash": 1000.0,
        "positions": {},   # symbol → {qty, entry_price, tp, sl, entry_time}
        "closed_trades": [],
        "total_pnl": 0.0,
    }

def save_portfolio(p: dict):
    PORTFOLIO_FILE.parent.mkdir(exist_ok=True)
    PORTFOLIO_FILE.write_text(json.dumps(p, indent=2))

def add_indicators(df, cfg):
    import numpy as np
    df = df.copy()
    df["ema_fast"]  = df["close"].ewm(span=cfg["ema_fast"],  adjust=False).mean()
    df["ema_slow"]  = df["close"].ewm(span=cfg["ema_slow"],  adjust=False).mean()
    df["ema_trend"] = df["close"].ewm(span=cfg["ema_trend"], adjust=False).mean()
    delta = df["close"].diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    ag    = gain.ewm(com=13, adjust=False).mean()
    al    = loss.ewm(com=13, adjust=False).mean()
    rs    = ag / al.replace(0, np.nan)
    df["rsi"]      = 100 - (100 / (1 + rs))
    df["vol_ma20"] = df["volume"].rolling(20).mean()
    df["cross_up"]   = (df["ema_fast"] > df["ema_slow"]) & (df["ema_fast"].shift(1) <= df["ema_slow"].shift(1))
    df["cross_down"] = (df["ema_fast"] < df["ema_slow"]) & (df["ema_fast"].shift(1) >= df["ema_slow"].shift(1))
    return df

def get_signal(symbol: str) -> dict | None:
    cfg = STRATEGY[symbol]
    df  = get_klines(symbol, interval="240", limit=150)
    df  = add_indicators(df, cfg)
    last = df.iloc[-1]
    ticker = get_ticker(symbol)
    price  = float(ticker["lastPrice"])

    return {
        "price":      price,
        "ema_fast":   round(last["ema_fast"], 5),
        "ema_slow":   round(last["ema_slow"], 5),
        "ema_trend":  round(last["ema_trend"], 5),
        "rsi":        round(last["rsi"], 2),
        "volume":     last["volume"],
        "vol_ma20":   round(last["vol_ma20"], 2),
        "cross_up":   bool(last["cross_up"]),
        "cross_down": bool(last["cross_down"]),
        "trend_ok":   price > last["ema_trend"],
        "rsi_ok":     cfg["rsi_min"] <= last["rsi"] <= cfg["rsi_max"],
        "vol_ok":     last["volume"] > last["vol_ma20"] * cfg["vol_mult"],
        "cfg":        cfg,
    }

def run_paper_trader():
    p = load_portfolio()
    log("=" * 60)
    log("📋 KingK Paper Trader")

    for symbol in PAIRS:
        data = safe_call("bybit", get_signal, symbol)
        if data is None:
            log(f"  {symbol}: skipped (circuit open)")
            continue

        cfg   = data["cfg"]
        price = data["price"]
        alloc = ALLOCATION[symbol]

        # --- Check exits first ---
        if symbol in p["positions"]:
            pos = p["positions"][symbol]
            hit_tp = price >= pos["tp"]
            hit_sl = price <= pos["sl"]
            hit_x  = data["cross_down"]

            if hit_tp or hit_sl or hit_x:
                reason    = "TP 🎯" if hit_tp else ("SL 🛑" if hit_sl else "EMA_X")
                exit_price = pos["tp"] if hit_tp else (pos["sl"] if hit_sl else price)
                pnl       = (exit_price - pos["entry_price"]) / pos["entry_price"] * alloc
                p["cash"] += alloc + pnl
                p["total_pnl"] += pnl
                p["closed_trades"].append({
                    "symbol":      symbol,
                    "entry_price": pos["entry_price"],
                    "exit_price":  round(exit_price, 6),
                    "entry_time":  pos["entry_time"],
                    "exit_time":   now_utc(),
                    "pnl_usd":     round(pnl, 2),
                    "reason":      reason,
                })
                del p["positions"][symbol]
                emoji = "✅" if pnl > 0 else "❌"
                log(f"  {symbol} CLOSED {reason} — P&L: ${pnl:+.2f} {emoji}")

        # --- Check entries ---
        if symbol not in p["positions"] and p["cash"] >= alloc:
            buy = data["cross_up"] and data["trend_ok"] and data["rsi_ok"] and data["vol_ok"]
            if buy:
                tp_price = round(price * (1 + cfg["tp"]), 6)
                sl_price = round(price * (1 - cfg["sl"]), 6)
                qty      = round(alloc / price, 4)
                p["cash"] -= alloc
                p["positions"][symbol] = {
                    "qty":         qty,
                    "entry_price": price,
                    "tp":          tp_price,
                    "sl":          sl_price,
                    "entry_time":  now_utc(),
                }
                log(f"  {symbol} 🟢 BUY {qty} @ ${price} | TP ${tp_price} | SL ${sl_price}")
            else:
                log(f"  {symbol} ⚪ HOLD — trend:{data['trend_ok']} rsi:{data['rsi_ok']} vol:{data['vol_ok']} cross:{data['cross_up']}")

        elif symbol in p["positions"]:
            pos = p["positions"][symbol]
            unrealised = (price - pos["entry_price"]) / pos["entry_price"] * alloc
            log(f"  {symbol} 📊 IN POSITION @ ${pos['entry_price']} | Now ${price} | Unrealised ${unrealised:+.2f}")

    # --- Portfolio summary ---
    total_open_value = sum(
        ALLOCATION[s] + (float(get_ticker(s)["lastPrice"]) - p["positions"][s]["entry_price"])
        / p["positions"][s]["entry_price"] * ALLOCATION[s]
        for s in p["positions"]
    ) if p["positions"] else 0

    portfolio_value = round(p["cash"] + total_open_value, 2)
    trades_done     = len(p["closed_trades"])
    wins            = [t for t in p["closed_trades"] if t["pnl_usd"] > 0]
    win_rate        = round(len(wins) / trades_done * 100, 1) if trades_done else 0

    log(f"\n  💼 PORTFOLIO SNAPSHOT")
    log(f"     Cash:          ${p['cash']:.2f}")
    log(f"     Open positions: {list(p['positions'].keys()) or 'None'}")
    log(f"     Portfolio value: ${portfolio_value}")
    log(f"     Total P&L:      ${p['total_pnl']:+.2f}")
    log(f"     Closed trades:  {trades_done} | Win rate: {win_rate}%")
    log("=" * 60)

    save_portfolio(p)

if __name__ == "__main__":
    run_paper_trader()
