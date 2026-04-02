# Bybit Testnet Trading Integration

## Overview

The paper trader now supports **optional testnet mode** to submit real orders to Bybit's demo account. This lets you test strategies with actual API execution without risking real capital.

- **Paper mode** (default): Pure simulation, no API calls
- **Testnet mode**: Real orders submitted to Bybit demo account (fake balance, zero risk)

## Quick Start

### Enable Testnet Mode

```bash
cd /root/.openclaw/workspace/kingk-trader
source venv/bin/activate

# Run with testnet enabled (auto-confirm orders)
TRADING_MODE=testnet TESTNET_ENABLED=true AUTO_CONFIRM_TESTNET=true python3 agents/paper_trader.py
```

### Require Confirmation Per Order

```bash
# Run with testnet but require 'y' confirmation for each order
TRADING_MODE=testnet TESTNET_ENABLED=true AUTO_CONFIRM_TESTNET=false python3 agents/paper_trader.py
```

### Default (Paper Mode)

```bash
# Default: pure simulation, no API calls
python3 agents/paper_trader.py
```

## Configuration

### Environment Variables

Set these to control trading mode:

```bash
export TRADING_MODE=paper          # "paper" or "testnet"
export TESTNET_ENABLED=false       # Safety flag; must be True to trade
export AUTO_CONFIRM_TESTNET=false  # Auto-confirm orders (true) or prompt (false)
export BYBIT_API_KEY=...           # Demo account API key (from .env)
export BYBIT_API_SECRET=...        # Demo account API secret (from .env)
```

### Config File (config/settings.py)

```python
TRADING_MODE = "paper"  # Switch to "testnet" to use Bybit demo account
TESTNET_ENABLED = False  # Safety flag — must be True to trade
AUTO_CONFIRM_TESTNET = False  # Auto-confirm testnet orders
```

## How It Works

### Paper Mode (Default)

```python
# Simulates orders — no API calls, instant "fill"
if TRADING_MODE == "paper" or not TESTNET_ENABLED:
    p["positions"][symbol] = {
        "qty": qty,
        "entry_price": price,
        "tp": tp_price,
        "sl": sl_price,
        "entry_time": now_utc(),
    }
    log(f"{symbol} 🟢 BUY {qty} @ ${price} | TP ${tp_price} | SL ${sl_price}")
```

Output:
```
[2026-03-24 11:21 UTC] XRPUSDT 🟢 BUY 160.0 @ $2.5 | TP $2.65 | SL $2.425 | via funding_rate_divergence
```

### Testnet Mode

```python
# Submits real order to Bybit testnet
if TRADING_MODE == "testnet" and TESTNET_ENABLED:
    trader = get_testnet_trader()
    result = trader.place_market_buy(symbol, qty, tp_price, sl_price)
    
    if result["status"] != "Error":
        # Track order ID for later reference
        p["positions"][symbol]["order_id"] = result["order_id"]
        p["positions"][symbol]["mode"] = "testnet"
        log(f"✅ TESTNET BUY ORDER SUBMITTED")
        log(f"   Order ID: {result['order_id']}")
```

Output:
```
[2026-03-24 11:21 UTC] ⚠️  TESTNET ORDER PENDING CONFIRMATION
[2026-03-24 11:21 UTC]     Symbol: XRPUSDT | Qty: 160.0 | Price: $2.5
[2026-03-24 11:21 UTC]     TP: $2.65 | SL: $2.425
[2026-03-24 11:21 UTC]   XRPUSDT ✅ TESTNET BUY ORDER SUBMITTED
[2026-03-24 11:21 UTC]      Order ID: 0a1b2c3d...
[2026-03-24 11:21 UTC]      Qty: 160.0 | Entry: $2.5 | TP: $2.65 | SL: $2.425
```

## API Details

### BybitTestnetTrader Class

**Location:** `agents/bybit_trader.py`

#### Methods

```python
class BybitTestnetTrader:
    def place_market_buy(self, symbol: str, qty: float, tp: float, sl: float) -> dict:
        """Submit BUY order with take profit & stop loss."""
        # Returns: {"order_id": str, "status": "Pending"|"Error", "error": str|None}
    
    def place_market_sell(self, symbol: str, qty: float) -> dict:
        """Submit SELL order to close position."""
        # Returns: {"order_id": str, "status": "Pending"|"Error", "error": str|None}
    
    def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """Query testnet for active orders."""
        # Returns: [{"order_id", "symbol", "qty", "side", "status"}, ...]
    
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel order by ID."""
    
    def get_order_status(self, order_id: str, symbol: str) -> dict:
        """Get order execution details (fill price, status)."""
```

### Testnet Endpoint

All API calls use:
```
https://api-testnet.bybit.com/v5/order/create
https://api-testnet.bybit.com/v5/order/realtime
https://api-testnet.bybit.com/v5/order/cancel
```

**Same demo credentials as live** — no separate testnet account needed.

## Safety Features

### 1. TESTNET_ENABLED Flag

Orders only submit if `TESTNET_ENABLED=True`:

```python
if TRADING_MODE == "testnet" and TESTNET_ENABLED:
    # Orders submit
else:
    # Orders simulate (paper mode)
```

Without this flag, orders always simulate even if `TRADING_MODE=testnet`.

### 2. Order Confirmation (Optional)

If `AUTO_CONFIRM_TESTNET=False`, each order requires user confirmation:

```
⚠️  TESTNET MODE — Order about to submit:
    Symbol: XRPUSDT
    Side: BUY
    Qty: 160.0
    Entry Price: $2.5
    TP: $2.65
    SL: $2.425
Proceed? (y/n): _
```

### 3. Logging

All orders logged with metadata:

```
[2026-03-24 11:21 UTC] ⚠️  TESTNET ORDER PENDING CONFIRMATION
[2026-03-24 11:21 UTC]     Symbol: XRPUSDT | Qty: 160.0 | Price: $2.5
[2026-03-24 11:21 UTC]     TP: $2.65 | SL: $2.425
[2026-03-24 11:21 UTC]   XRPUSDT ✅ TESTNET BUY ORDER SUBMITTED
[2026-03-24 11:21 UTC]      Order ID: 0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d
[2026-03-24 11:21 UTC]      Qty: 160.0 | Entry: $2.5 | TP: $2.65 | SL: $2.425
```

## Portfolio Tracking

Positions track mode for reference:

```json
{
  "positions": {
    "XRPUSDT": {
      "qty": 160.0,
      "entry_price": 2.5,
      "tp": 2.65,
      "sl": 2.425,
      "entry_time": "2026-03-24 11:21 UTC",
      "order_id": "0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d",
      "mode": "testnet"
    }
  }
}
```

Closed trades also track mode:

```json
{
  "closed_trades": [
    {
      "symbol": "XRPUSDT",
      "entry_price": 2.5,
      "exit_price": 2.65,
      "pnl_usd": 24.0,
      "reason": "TP 🎯",
      "mode": "testnet"
    }
  ]
}
```

## Switching Modes

### Paper → Testnet

```bash
TRADING_MODE=testnet TESTNET_ENABLED=true AUTO_CONFIRM_TESTNET=true python3 agents/paper_trader.py
```

**Portfolio persists** — existing positions continue in their mode.

### Testnet → Paper

```bash
python3 agents/paper_trader.py
```

Testnet positions keep their order IDs but new orders simulate.

### Disable Testnet (Safety)

```bash
TRADING_MODE=testnet TESTNET_ENABLED=false python3 agents/paper_trader.py
```

Even if `TRADING_MODE=testnet`, orders simulate because `TESTNET_ENABLED=false`.

## Testing

### Test Testnet Connectivity

```bash
cd /root/.openclaw/workspace/kingk-trader && source venv/bin/activate
python3 << 'EOF'
from agents.bybit_trader import BybitTestnetTrader
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(".env"))
api_key = os.getenv("BYBIT_API_KEY")
api_secret = os.getenv("BYBIT_API_SECRET")

trader = BybitTestnetTrader(api_key, api_secret)
orders = trader.get_open_orders("XRPUSDT")
print(f"✅ Connected to testnet. Open orders: {len(orders)}")
EOF
```

### Simulate Order Flow (Paper Mode)

```bash
python3 agents/paper_trader.py
```

Output shows `[PAPER MODE]` tags.

### Test Testnet with Auto-Confirm

```bash
TRADING_MODE=testnet TESTNET_ENABLED=true AUTO_CONFIRM_TESTNET=true timeout 60 python3 agents/paper_trader.py
```

Will submit orders if signals trigger.

## Troubleshooting

### "BYBIT_API_KEY or BYBIT_API_SECRET not set"

Make sure `.env` has demo credentials:

```bash
cat kingk-trader/.env | grep BYBIT_API
```

Should show:
```
BYBIT_API_KEY=IjuDhMoZgK4umpSCuJ
BYBIT_API_SECRET=uLxHRAbemJoNMY8YazAFcIRirFKFo4ZeJdMx
```

### "TESTNET MODE DISABLED"

Set `TESTNET_ENABLED=true`:

```bash
TRADING_MODE=testnet TESTNET_ENABLED=true python3 agents/paper_trader.py
```

### Orders not submitting

Check:
1. Is `TRADING_MODE=testnet`?
2. Is `TESTNET_ENABLED=true`?
3. Are API credentials in `.env`?
4. Is a buy signal generated? (Check logs for strategy output)

### Order submission failed

Testnet errors logged:

```
[2026-03-24 11:21 UTC]   XRPUSDT ❌ TESTNET ORDER FAILED: Invalid symbol
```

Check:
- Symbol spelling (case-sensitive: `XRPUSDT`, not `xrpusdt`)
- Account has sufficient balance (demo account reset on login)
- API rate limits (max 10 requests/sec for testnet)

## Zero Risk

**This is a demo account.** Features:

✅ **Fake balance** — No real money  
✅ **Instant fills** — Orders execute at market price  
✅ **Full API** — Place, cancel, query orders exactly like live  
✅ **Reset anytime** — Clear all orders/positions via web dashboard  
✅ **No fees** — Demo trading is free  

**Perfect for testing strategies before live capital.**

## Next Steps

1. Run paper trader once to see signal flow:
   ```bash
   python3 agents/paper_trader.py
   ```

2. When confident, enable testnet with confirmation:
   ```bash
   TRADING_MODE=testnet TESTNET_ENABLED=true python3 agents/paper_trader.py
   ```

3. Review orders in logs:
   ```bash
   tail -50 logs/paper_trades.log
   ```

4. When satisfied, switch to auto-confirm:
   ```bash
   TRADING_MODE=testnet TESTNET_ENABLED=true AUTO_CONFIRM_TESTNET=true python3 agents/paper_trader.py
   ```

---

**Status:** Testnet integration complete. Ready to trade on demo account.
