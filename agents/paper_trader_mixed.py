#!/usr/bin/env python3
"""
KingK Paper Trader - MIXED PORTFOLIO (Long + Short)
70% long allocation, 30% short allocation
All strategies on 4h timeframe.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from data.fetcher import get_klines, get_ticker
from agents.failsafe import safe_call

# Import mixed config
sys.path.insert(0, str(Path(__file__).parent.parent / "config"))
try:
    from settings_mixed import *
    print("✅ Loaded mixed portfolio config")
except ImportError:
    # Fallback to default config
    from config.settings import *
    print("⚠️  Using default config (no mixed portfolio)")

PORTFOLIO_FILE = Path(__file__).parent.parent / "logs" / "paper_portfolio_mixed.json"
LOG_FILE       = Path(__file__).parent.parent / "logs" / "paper_trades_mixed.log"
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
    with open(LOG_FILE, 'a') as f:
        f.write(line + "\n")

def load_portfolio() -> dict:
    if PORTFOLIO_FILE.exists():
        return json.loads(PORTFOLIO_FILE.read_text())
    # Fresh portfolio with mixed allocation
    return {
        "cash": 2000.0,  # $1000 per pair × 2 pairs
        "positions": {},   # symbol_side → {qty, entry_price, tp, sl, entry_time, side}
        "closed_trades": [],
        "total_pnl": 0.0,
        "long_pnl": 0.0,
        "short_pnl": 0.0,
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

def get_signal(symbol_side: str) -> dict | None:
    """Get signal for a symbol+side combination."""
    import pandas as pd
    
    # Parse symbol and side
    if symbol_side.endswith("_LONG"):
        symbol = symbol_side.replace("_LONG", "")
        side = "long"
    elif symbol_side.endswith("_SHORT"):
        symbol = symbol_side.replace("_SHORT", "")
        side = "short"
    else:
        symbol = symbol_side
        side = "long"  # default
    
    cfg = STRATEGY[symbol_side]
    module_name = STRATEGY_MODULE[symbol_side]
    interval = cfg.get("interval", "240")  # Default to 4h
    
    df = get_klines(symbol, interval=interval, limit=150)
    
    # Merge funding rate data if needed
    if "funding" in module_name or "liquidation" in module_name:
        funding_path = Path(__file__).parent.parent / "data" / "historical" / f"{symbol}_funding_4h.csv"
        if funding_path.exists():
            funding_df = pd.read_csv(funding_path)
            funding_df["datetime"] = pd.to_datetime(funding_df["datetime"])
            df["datetime"] = pd.to_datetime(df["datetime"])
            df = pd.merge(df, funding_df[["datetime", "funding_rate"]], on="datetime", how="left")
            df["funding_rate"] = df["funding_rate"].fillna(0)
        else:
            df["funding_rate"] = 0
    
    # Merge liquidation data if needed
    if "liquidation" in module_name:
        liq_path = Path(__file__).parent.parent / "data" / "historical" / f"{symbol}_liquidation_4h.csv"
        if liq_path.exists():
            liq_df = pd.read_csv(liq_path)
            liq_df["datetime"] = pd.to_datetime(liq_df["datetime"])
            df = pd.merge(df, liq_df[["datetime", "liquidation_volume_usd"]], on="datetime", how="left")
            df["liquidation_volume_usd"] = df["liquidation_volume_usd"].fillna(0)
        else:
            df["liquidation_volume_usd"] = 0
    
    # Load strategy and generate signals
    try:
        module = load_strategy_module(module_name)
        df = module.generate_signals(df)
    except Exception as e:
        log(f"  {symbol_side} ❌ Strategy error: {e}")
        return None
    
    last = df.iloc[-1]
    price = float(last["close"])
    
    # Get signal: -1=SHORT, 1=LONG, 0=HOLD
    entry_signal = int(last["signal"])
    
    return {
        "symbol": symbol,
        "side": side,
        "price": price,
        "entry_signal": entry_signal,  # -1=SHORT, 1=LONG, 0=HOLD
        "cfg": cfg,
        "module": module_name,
        "interval": interval,
    }

def confirm_testnet_order(symbol: str, side: str, qty: float, tp: float, sl: float, price: float) -> bool:
    """Ask user for confirmation before submitting testnet order."""
    if AUTO_CONFIRM_TESTNET:
        return True
    
    print(f"\n⚠️  TESTNET MODE — Order about to submit:")
    print(f"    Symbol: {symbol}")
    print(f"    Side: {side.upper()}")
    print(f"    Qty: {qty}")
    print(f"    Entry Price: ${price}")
    print(f"    TP: ${tp}")
    print(f"    SL: ${sl}")
    response = input("Proceed? (y/n): ").strip().lower()
    return response == "y"

def run_paper_trader():
    p = load_portfolio()
    log("=" * 60)
    
    if TRADING_MODE == "testnet" and TESTNET_ENABLED:
        log("⚠️  TRADING MODE: TESTNET (Mixed Portfolio - 70% Long / 30% Short)")
    else:
        log("📋 KingK Paper Trader - MIXED PORTFOLIO (70% Long / 30% Short)")
    
    # Process all symbol+side combinations
    symbol_sides = [f"{pair}_{side}" for pair in ["XRPUSDT", "SUIUSDT"] for side in ["LONG", "SHORT"]]
    
    for i, symbol_side in enumerate(symbol_sides):
        if i > 0:
            time.sleep(3)  # Rate limit
        
        data = safe_call("bybit", get_signal, symbol_side)
        if data is None:
            log(f"  {symbol_side}: skipped (circuit open)")
            continue
        
        symbol = data["symbol"]
        side = data["side"]
        cfg = data["cfg"]
        price = data["price"]
        alloc = ALLOCATION[symbol_side]
        module_name = data["module"]
        entry_signal = data["entry_signal"]
        
        # --- Check exits first ---
        if symbol_side in p["positions"]:
            pos = p["positions"][symbol_side]
            
            # Calculate exit conditions based on side
            if side == "long":
                hit_tp = price >= pos["tp"]
                hit_sl = price <= pos["sl"]
            else:  # short
                hit_tp = price <= pos["tp"]  # For short: TP is BELOW entry
                hit_sl = price >= pos["sl"]  # For short: SL is ABOVE entry
            
            # Strategy exit signal
            if side == "long":
                strategy_exit = entry_signal == -1  # Sell signal exits long
            else:
                strategy_exit = entry_signal == 1   # Cover signal exits short

            if hit_tp or hit_sl or strategy_exit:
                reason = "TP 🎯" if hit_tp else ("SL 🛑" if hit_sl else "STRATEGY_EXIT")
                
                if side == "long":
                    exit_price = pos["tp"] if hit_tp else (pos["sl"] if hit_sl else price)
                    pnl = (exit_price - pos["entry_price"]) / pos["entry_price"] * alloc
                    p["long_pnl"] += pnl
                else:  # short
                    exit_price = pos["tp"] if hit_tp else (pos["sl"] if hit_sl else price)
                    pnl = (pos["entry_price"] - exit_price) / pos["entry_price"] * alloc
                    p["short_pnl"] += pnl
                
                # Update portfolio
                p["cash"] += alloc + pnl
                p["total_pnl"] += pnl
                p["closed_trades"].append({
                    "symbol": symbol,
                    "side": side,
                    "entry_price": pos["entry_price"],
                    "exit_price": round(exit_price, 6),
                    "entry_time": pos["entry_time"],
                    "exit_time": now_utc(),
                    "pnl_usd": round(pnl, 2),
                    "reason": reason,
                    "strategy": module_name,
                    "allocation": alloc,
                    "mode": pos.get("mode", "paper"),
                })
                del p["positions"][symbol_side]
                emoji = "✅" if pnl > 0 else "❌"
                
                log_entry = f"  {symbol_side} CLOSED {reason} — P&L: ${pnl:+.2f} {emoji}"
                if pos.get("mode") == "testnet":
                    log_entry += " [TESTNET]"
                log(log_entry)

        # --- Check entries ---
        if symbol_side not in p["positions"] and p["cash"] >= alloc:
            if (side == "long" and entry_signal == 1) or (side == "short" and entry_signal == -1):
                # Calculate TP/SL based on side
                if side == "long":
                    tp_price = round(price * (1 + cfg["tp"]), 6)
                    sl_price = round(price * (1 - cfg["sl"]), 6)
                else:  # short
                    tp_price = round(price * (1 - cfg["tp"]), 6)  # Price goes DOWN for profit
                    sl_price = round(price * (1 + cfg["sl"]), 6)  # Price goes UP for loss
                
                qty = round(alloc / price, 4)
                
                # Handle entry
                handle_entry(symbol_side, symbol, side, qty, price, tp_price, sl_price, 
                           module_name, p, alloc)
                
            else:
                log(f"  {symbol_side} ⚪ HOLD — signal:{entry_signal} | via {module_name}")

        elif symbol_side in p["positions"]:
            pos = p["positions"][symbol_side]
            if side == "long":
                unrealised = (price - pos["entry_price"]) / pos["entry_price"] * alloc
            else:  # short
                unrealised = (pos["entry_price"] - price) / pos["entry_price"] * alloc
            
            log(f"  {symbol_side} 📊 IN {side.upper()} POSITION @ ${pos['entry_price']} | Now ${price} | Unrealised ${unrealised:+.2f}")

    # --- Portfolio summary ---
    total_open_value = 0
    long_positions = 0
    short_positions = 0
    
    for pos_key, pos in p["positions"].items():
        alloc = ALLOCATION.get(pos_key, 0)
        symbol = pos_key.replace("_LONG", "").replace("_SHORT", "")
        current_price = float(get_ticker(symbol)["lastPrice"])
        
        if "LONG" in pos_key:
            unrealised = (current_price - pos["entry_price"]) / pos["entry_price"] * alloc
            long_positions += 1
        else:
            unrealised = (pos["entry_price"] - current_price) / pos["entry_price"] * alloc
            short_positions += 1
        
        total_open_value += alloc + unrealised

    portfolio_value = round(p["cash"] + total_open_value, 2)
    trades_done = len(p["closed_trades"])
    
    # Calculate win rates by side
    long_trades = [t for t in p["closed_trades"] if t["side"] == "long"]
    short_trades = [t for t in p["closed_trades"] if t["side"] == "short"]
    
    long_wins = len([t for t in long_trades if t["pnl_usd"] > 0])
    short_wins = len([t for t in short_trades if t["pnl_usd"] > 0])
    
    long_win_rate = round(long_wins / len(long_trades) * 100, 1) if long_trades else 0
    short_win_rate = round(short_wins / len(short_trades) * 100, 1) if short_trades else 0
    overall_win_rate = round((long_wins + short_wins) / trades_done * 100, 1) if trades_done else 0

    log(f"\n  💼 MIXED PORTFOLIO SNAPSHOT")
    log(f"     Cash:          ${p['cash']:.2f}")
    log(f"     Open positions: {long_positions} long, {short_positions} short")
    log(f"     Portfolio value: ${portfolio_value}")
    log(f"     Total P&L:      ${p['total_pnl']:+.2f}")
    log(f"     Long P&L:       ${p['long_pnl']:+.2f} (Win rate: {long_win_rate}%)")
    log(f"     Short P&L:      ${p['short_pnl']:+.2f} (Win rate: {short_win_rate}%)")
    log(f"     Closed trades:  {trades_done} | Overall win rate: {overall_win_rate}%")
    log("=" * 60)

    save_portfolio(p)

def handle_entry(symbol_side, symbol, side, qty, price, tp_price, sl_price, module_name, portfolio, alloc):
    """Handle entry logging and portfolio update."""
    if TRADING_MODE == "testnet" and TESTNET_ENABLED:
        log(f"\n⚠️  TESTNET ORDER PENDING CONFIRMATION")
        log(f"    Symbol: {symbol} | Side: {side.upper()} | Qty: {qty} | Price: ${price}")
        log(f"    TP: ${tp_price} | SL: ${sl_price}")
        
        if confirm_testnet_order(symbol, side.upper(), qty, tp_price, sl_price, price):
            try:
                trader = get_testnet_trader()
                if side == "long":
                    result = trader.place_market_buy(symbol, qty, tp_price, sl_price)
                else:
                    result = trader.place_market_sell(symbol, qty, tp_price, sl_price)
                
                if result["status"] != "Error":
                    portfolio["cash"] -= alloc
                    portfolio["positions"][symbol_side] = {
                        "qty": qty,
                        "entry_price": price,
                        "tp": tp_price,
                        "sl": sl_price,
                        "entry_time": now_utc(),
                        "strategy": module_name,
                        "order_id": result["order_id"],
                        "side": side,
                        "mode": "testnet",
                    }
                    log(f"  {symbol_side} ✅ TESTNET {side.upper()} ORDER SUBMITTED")
                    log(f"     Order ID: {result['order_id']}")
                    log(f"     Qty: {qty} | Entry: ${price} | TP: ${tp_price} | SL: ${sl_price}")
                else:
                    log(f"  {symbol_side} ❌ TESTNET ORDER FAILED: {result['error']}")
            except Exception as e:
                log(f"  {symbol_side} ❌ TESTNET ERROR: {str(e)}")
        else:
            log(f"  {symbol_side} ⚪ TESTNET ORDER CANCELLED BY USER")
    else:
        # PAPER MODE
        portfolio["cash"] -= alloc
        portfolio["positions"][symbol_side] = {
            "qty": qty,
            "entry_price": price,
            "tp": tp_price,
            "sl": sl_price,
            "entry_time": now_utc(),
            "strategy": module_name,
            "side": side,
        }
        emoji = "🟢" if side == "long" else "🔴"
        log(f"  {symbol_side} {emoji} {side.upper()} {qty} @ ${price} | TP ${tp_price} | SL ${sl_price} | via {module_name}")