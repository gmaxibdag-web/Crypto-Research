# KingK Trader - Config v3 (tuned 2026-03-24 — param sweep + trend filters)

BYBIT_API_KEY    = ""
BYBIT_API_SECRET = ""
BYBIT_TESTNET    = True   # flip to False for live

PAIRS = ["XRPUSDT", "SUIUSDT"]

TOTAL_CAPITAL = 1000
ALLOCATION = {
    "XRPUSDT": 400,
    "SUIUSDT": 400,
    "RESERVE": 200,
}

# --- TUNED STRATEGY PARAMS (param sweep 2026-03-24, 4h 2yr backtest) ---
# Winner: RSI Divergence on XRPUSDT (Sharpe=0.47, P&L=+$65.84, 26 trades)
# EMA Swing remains primary on SUIUSDT (Sharpe=0.21, P&L=+$60.00)
STRATEGY = {
    # ── XRPUSDT: RSI Divergence Breakout (PROMOTED — beats all others on XRP) ──
    # Tuned params: rsi_oversold=35, vol_mult=1.8
    # Sharpe=0.4735 | P&L=+$65.84 | 26 trades | WinRate=42.3% | MaxDD=-10.2%
    "XRPUSDT": {
        "strategy":    "rsi_divergence_breakout",  # TUNED 2026-03-24
        "rsi_oversold": 35,     # loosened from original 35 (kept best)
        "rsi_overbought": 65,
        "ema_period":  50,
        "ema_proximity": 0.10,  # allow entries within 10% of EMA50
        "vol_mult":    1.8,     # tuned (was 1.5)
        "tp":          0.06,
        "sl":          0.03,
    },
    # ── SUIUSDT: EMA Swing (baseline — still best on SUI) ──
    # Sharpe=0.2133 | P&L=+$60.00 | 40 trades | WinRate=37.5%
    "SUIUSDT": {
        "strategy":   "ema_swing",
        "ema_fast":   12,
        "ema_slow":   26,
        "ema_trend":  100,
        "rsi_min":    50,
        "rsi_max":    65,
        "vol_mult":   1.2,
        "tp":         0.05,
        "sl":         0.03,
    },
}

# --- MACD+RSI best tuned config (runner-up on SUI: P&L=+$172, Sharpe=0.166) ---
# Use if SUI strategy needs upgrade:
# macd_fast=8, macd_slow=17, macd_signal=9, rsi_max=70, ema_trend=100
# Note: higher P&L but lower Sharpe than EMA Swing

INTERVAL = "240"   # 4h candles

# --- Per-pair strategy module routing ---
STRATEGY_MODULE = {
    "XRPUSDT": "rsi_divergence_breakout",
    "SUIUSDT": "ema_swing",
}
