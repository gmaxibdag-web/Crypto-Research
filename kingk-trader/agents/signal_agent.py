"""
KingK Signal Agent — with circuit breaker & failsafes
Runs every 4h, checks XRP + SUI for buy/sell signals.
All external calls wrapped in safe_call() — no runaway token burn.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timezone
from data.fetcher import get_klines, get_ticker
from strategies.ema_swing import current_signal
from agents.failsafe import safe_call, get_circuit_status
from config.settings import PAIRS, ALLOCATION, TAKE_PROFIT_PCT, STOP_LOSS_PCT

LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "signals.log")

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def fetch_symbol_data(symbol: str) -> dict | None:
    """Wrapped fetcher — if Bybit is down, circuit opens, we skip cleanly."""
    df = get_klines(symbol, interval="240", limit=100)
    ticker = get_ticker(symbol)
    sig = current_signal(df)
    return {"sig": sig, "ticker": ticker}

def run_agent():
    log("=" * 60)
    log("KingK Signal Agent firing...")

    # Show circuit status first
    status = get_circuit_status()
    if status:
        log(f"Circuit status:\n{status}")

    any_signal = False

    for symbol in PAIRS:
        # Wrap the entire fetch+signal block in failsafe
        result = safe_call("bybit", fetch_symbol_data, symbol)

        if result is None:
            log(f"  {symbol}: skipped (circuit open or limit hit)")
            continue

        sig    = result["sig"]
        capital = ALLOCATION.get(symbol, 400)
        action  = {1: "🟢 BUY", -1: "🔴 SELL", 0: "⚪ HOLD"}[sig["signal"]]

        log(f"\n  {symbol}")
        log(f"    Price:  ${sig['price']}")
        log(f"    EMA9:   {sig['ema9']}  EMA21: {sig['ema21']}")
        log(f"    RSI:    {sig['rsi']}")
        log(f"    Volume: {sig['volume']:.0f} (MA20: {sig['vol_ma20']:.0f})")
        log(f"    Signal: {action}")

        if sig["signal"] == 1:
            any_signal = True
            tp  = round(sig["price"] * (1 + TAKE_PROFIT_PCT), 6)
            sl  = round(sig["price"] * (1 - STOP_LOSS_PCT), 6)
            qty = round(capital / sig["price"], 2)
            log(f"    📌 TRADE: Buy {qty} {symbol[:3]} @ ${sig['price']}")
            log(f"    🎯 TP: ${tp}  🛑 SL: ${sl}")
            # TODO: escalate to Haiku/Gemini for confirmation, then place_order()

        elif sig["signal"] == -1:
            any_signal = True
            log(f"    📌 CLOSE position if held")

    if not any_signal:
        log("\n  No signals — all HOLD. Standing by.")

    log("=" * 60)

if __name__ == "__main__":
    run_agent()
