"""
KingK Paper Trader — simulates live trading with real prices, zero risk.
Tracks open positions, P&L, portfolio value in real time.
State persists in logs/paper_portfolio.json

Per-pair strategy routing: each symbol uses its configured strategy module
to generate entry signals via generate_signals(df). Exit logic (TP/SL/EMA
cross for ema_swing) remains hardcoded here for all pairs.

Supports two modes:
- paper: pure simulation (default)
- testnet: submit orders to Bybit testnet demo account
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from data.fetcher import get_klines, get_ticker
from agents.failsafe import safe_call
from config.settings import PAIRS, ALLOCATION, STRATEGY, STRATEGY_MODULE, TRADING_MODE, TESTNET_ENABLED, AUTO_CONFIRM_TESTNET

PORTFOLIO_FILE = Path(__file__).parent.parent / "logs" / "paper_portfolio.json"
LOG_FILE       = Path(__file__).parent.parent / "logs" / "paper_trades.log"
STRATEGIES_DIR = Path(__file__).parent.parent / "strategies"

# Testnet trader (lazy-loaded if needed)
_testnet_trader = None

def get_testnet_trader():
    """Lazy-load testnet trader instance."""
    global _testnet_trader
    if _testnet_trader is None:
        from agents.bybit_trader import BybitTestnetTrader
        api_key = os.getenv("BYBIT_API_KEY")
        api_secret = os.getenv("BYBIT_API_SECRET")
        if not api_key or not api_secret:
            log("❌ ERROR: BYBIT_API_KEY or BYBIT_API_SECRET not set in .env")
            raise ValueError("Bybit credentials missing")
        _testnet_trader = BybitTestnetTrader(api_key, api_secret)
    return _testnet_trader

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

def load_strategy_module(module_name: str):
    """Dynamically import a strategy module from strategies/."""
    strategy_path = STRATEGIES_DIR / f"{module_name}.py"
    if not strategy_path.exists():
        raise FileNotFoundError(f"Strategy not found: {strategy_path}")
    spec = importlib.util.spec_from_file_location(module_name, strategy_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def add_ema_cross_indicators(df, cfg):
    """Add EMA cross indicators used for exit logic on EMA-based strategies."""
    import numpy as np
    df = df.copy()
    ema_fast_span = cfg.get("ema_fast", 9)
    ema_slow_span = cfg.get("ema_slow", 21)
    df["_ema_fast"] = df["close"].ewm(span=ema_fast_span, adjust=False).mean()
    df["_ema_slow"] = df["close"].ewm(span=ema_slow_span, adjust=False).mean()
    df["cross_down"] = (df["_ema_fast"] < df["_ema_slow"]) & \
                       (df["_ema_fast"].shift(1) >= df["_ema_slow"].shift(1))
    return df

def get_signal(symbol: str) -> dict | None:
    import pandas as pd
    cfg = STRATEGY[symbol]
    module_name = STRATEGY_MODULE.get(symbol, "ema_swing")
    df = get_klines(symbol, interval="240", limit=150)

    # --- Merge funding rate data (for funding_rate_divergence & liquidation_cascade) ---
    if module_name in ["funding_rate_divergence", "liquidation_cascade"]:
        funding_path = Path(__file__).parent.parent / "data" / "historical" / f"{symbol}_funding_4h.csv"
        if funding_path.exists():
            df_funding = pd.read_csv(funding_path, parse_dates=["datetime"])
            # Merge on timestamp (backward fill for latest available)
            df = pd.merge_asof(
                df.sort_values("timestamp"),
                df_funding[["timestamp", "funding_rate", "open_interest"]].sort_values("timestamp"),
                on="timestamp",
                direction="backward"
            )
        else:
            # Fallback: add zero columns
            df["funding_rate"] = 0.0
            df["open_interest"] = 0.0

    # --- Merge liquidation data (for liquidation_cascade) ---
    if module_name == "liquidation_cascade":
        liq_path = Path(__file__).parent.parent / "data" / "historical" / f"{symbol}_liquidations_4h.csv"
        if liq_path.exists():
            df_liq = pd.read_csv(liq_path, parse_dates=["datetime"])
            # Merge on timestamp (backward fill)
            df = pd.merge_asof(
                df.sort_values("timestamp"),
                df_liq[["timestamp", "liquidation_volume_usd", "is_cluster"]].sort_values("timestamp"),
                on="timestamp",
                direction="backward"
            )
        else:
            # Fallback: add zero columns
            df["liquidation_volume_usd"] = 0.0
            df["is_cluster"] = False

    # Load the correct strategy module dynamically
    strategy_mod = load_strategy_module(module_name)
    df_with_signals = strategy_mod.generate_signals(df)

    # Get last row signal: 1=buy, -1=sell, 0=hold
    last = df_with_signals.iloc[-1]
    entry_signal = int(last["signal"])  # 1=buy, -1=sell, 0=hold

    # Add EMA cross for exit logic (available for all strategies)
    df_with_cross = add_ema_cross_indicators(df, cfg)
    last_cross = df_with_cross.iloc[-1]
    cross_down = bool(last_cross["cross_down"])

    ticker = get_ticker(symbol)
    price  = float(ticker["lastPrice"])

    return {
        "price":        price,
        "entry_signal": entry_signal,   # 1=buy, -1=sell, 0=hold from strategy
        "cross_down":   cross_down,     # EMA cross exit signal
        "cfg":          cfg,
        "module":       module_name,
    }

def confirm_testnet_order(symbol: str, qty: float, tp: float, sl: float, price: float) -> bool:
    """
    Ask user for confirmation before submitting testnet order.
    Auto-confirm if AUTO_CONFIRM_TESTNET=True.
    """
    if AUTO_CONFIRM_TESTNET:
        return True
    
    print(f"\n⚠️  TESTNET MODE — Order about to submit:")
    print(f"    Symbol: {symbol}")
    print(f"    Side: BUY")
    print(f"    Qty: {qty}")
    print(f"    Entry Price: ${price}")
    print(f"    TP: ${tp}")
    print(f"    SL: ${sl}")
    response = input("Proceed? (y/n): ").strip().lower()
    return response == "y"

def run_paper_trader():
    p = load_portfolio()
    log("=" * 60)
    
    # Log trading mode
    if TRADING_MODE == "testnet":
        if TESTNET_ENABLED:
            log("⚠️  TRADING MODE: TESTNET (orders will be submitted to Bybit demo account)")
        else:
            log("❌ TESTNET MODE DISABLED — Set TESTNET_ENABLED=True to trade")
            log("📋 KingK Paper Trader (TESTNET DISABLED — simulation mode)")
    else:
        log("📋 KingK Paper Trader (PAPER MODE — simulation only)")

    for i, symbol in enumerate(PAIRS):
        # Rate limit: sleep 3 seconds between pairs to avoid Bybit testnet limits
        if i > 0:
            time.sleep(3)
        
        data = safe_call("bybit", get_signal, symbol)
        if data is None:
            log(f"  {symbol}: skipped (circuit open)")
            continue

        cfg   = data["cfg"]
        price = data["price"]
        alloc = ALLOCATION[symbol]
        module_name = data["module"]

        # --- Check exits first ---
        if symbol in p["positions"]:
            pos = p["positions"][symbol]
            hit_tp = price >= pos["tp"]
            hit_sl = price <= pos["sl"]
            # Exit on strategy sell signal OR EMA cross down (whichever fires first)
            strategy_exit = data["entry_signal"] == -1
            hit_x  = data["cross_down"] or strategy_exit

            if hit_tp or hit_sl or hit_x:
                reason    = "TP 🎯" if hit_tp else ("SL 🛑" if hit_sl else "EMA_X")
                exit_price = pos["tp"] if hit_tp else (pos["sl"] if hit_sl else price)
                pnl       = (exit_price - pos["entry_price"]) / pos["entry_price"] * alloc
                
                # --- TESTNET MODE: Submit real exit order ---
                if pos.get("mode") == "testnet" and TRADING_MODE == "testnet" and TESTNET_ENABLED:
                    try:
                        trader = get_testnet_trader()
                        result = trader.place_market_sell(symbol, pos["qty"])
                        
                        if result["status"] != "Error":
                            log(f"  {symbol} CLOSED {reason} — TESTNET SELL EXECUTED")
                            log(f"     Order ID: {result['order_id']}")
                            log(f"     Est. P&L: ${pnl:+.2f} {'✅' if pnl > 0 else '❌'}")
                        else:
                            log(f"  {symbol} ❌ TESTNET EXIT FAILED: {result['error']}")
                    except Exception as e:
                        log(f"  {symbol} ❌ TESTNET EXIT ERROR: {str(e)}")
                
                # Update portfolio regardless of mode
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
                    "mode":        pos.get("mode", "paper"),
                })
                del p["positions"][symbol]
                emoji = "✅" if pnl > 0 else "❌"
                
                # Log differently for paper vs testnet
                if pos.get("mode") == "testnet":
                    log(f"  {symbol} CLOSED {reason} — P&L: ${pnl:+.2f} {emoji} [TESTNET]")
                else:
                    log(f"  {symbol} CLOSED {reason} — P&L: ${pnl:+.2f} {emoji}")

        # --- Check entries ---
        if symbol not in p["positions"] and p["cash"] >= alloc:
            buy = data["entry_signal"] == 1
            if buy:
                tp_price = round(price * (1 + cfg["tp"]), 6)
                sl_price = round(price * (1 - cfg["sl"]), 6)
                qty      = round(alloc / price, 4)
                
                # --- TESTNET MODE: Submit real order ---
                if TRADING_MODE == "testnet" and TESTNET_ENABLED:
                    log(f"\n⚠️  TESTNET ORDER PENDING CONFIRMATION")
                    log(f"    Symbol: {symbol} | Qty: {qty} | Price: ${price}")
                    log(f"    TP: ${tp_price} | SL: ${sl_price}")
                    
                    if confirm_testnet_order(symbol, qty, tp_price, sl_price, price):
                        try:
                            trader = get_testnet_trader()
                            result = trader.place_market_buy(symbol, qty, tp_price, sl_price)
                            
                            if result["status"] != "Error":
                                p["cash"] -= alloc
                                p["positions"][symbol] = {
                                    "qty":         qty,
                                    "entry_price": price,
                                    "tp":          tp_price,
                                    "sl":          sl_price,
                                    "entry_time":  now_utc(),
                                    "strategy":    module_name,
                                    "order_id":    result["order_id"],
                                    "mode":        "testnet",
                                }
                                log(f"  {symbol} ✅ TESTNET BUY ORDER SUBMITTED")
                                log(f"     Order ID: {result['order_id']}")
                                log(f"     Qty: {qty} | Entry: ${price} | TP: ${tp_price} | SL: ${sl_price}")
                            else:
                                log(f"  {symbol} ❌ TESTNET ORDER FAILED: {result['error']}")
                        except Exception as e:
                            log(f"  {symbol} ❌ TESTNET ERROR: {str(e)}")
                    else:
                        log(f"  {symbol} ⚪ TESTNET ORDER CANCELLED BY USER")
                
                # --- PAPER MODE: Simulate order ---
                else:
                    p["cash"] -= alloc
                    p["positions"][symbol] = {
                        "qty":         qty,
                        "entry_price": price,
                        "tp":          tp_price,
                        "sl":          sl_price,
                        "entry_time":  now_utc(),
                        "strategy":    module_name,
                    }
                    log(f"  {symbol} 🟢 BUY {qty} @ ${price} | TP ${tp_price} | SL ${sl_price} | via {module_name}")
            else:
                log(f"  {symbol} ⚪ HOLD — signal:{data['entry_signal']} cross_down:{data['cross_down']} | via {module_name}")

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
