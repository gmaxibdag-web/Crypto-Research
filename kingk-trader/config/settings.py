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
    # ── XRPUSDT: Funding Rate Divergence (NEW — beats RSI Divergence on XRP) ──
    # Signal: negative funding + OI drop = bull capitulation reversal
    # Sharpe=0.520 | P&L=+$144.23 | 50 trades | WinRate=58.0% | MaxDD=-14.2%
    # Added 2026-03-24. Prev best: rsi_divergence_breakout (Sharpe=0.473, P&L=+$65.85)
    "XRPUSDT": {
        "strategy":          "funding_rate_divergence",  # NEW 2026-03-24
        "funding_threshold": -0.00005,   # negative funding, calibrated to Bybit perp scale
        "oi_drop_pct":       0.02,       # >2% OI drop in 4h = deleveraging signal
        "use_price_filter":  False,      # price filter hurts performance on XRP
        "use_rsi_filter":    True,       # RSI < 50 guards against overbought entries
        "tp":                0.06,
        "sl":                0.03,
    },
    # ── SUIUSDT: Funding Rate Divergence (NEW — dominates EMA Swing on SUI) ──
    # Signal: negative funding + OI drop = bull capitulation reversal
    # Sharpe=0.696 | P&L=+$132.01 | 34 trades | WinRate=50.0% | MaxDD=-11.8%
    # Added 2026-03-24. Prev best: ema_swing (Sharpe=0.213, P&L=+$60.00)
    "SUIUSDT": {
        "strategy":          "funding_rate_divergence",  # NEW 2026-03-24
        "funding_threshold": -0.00005,
        "oi_drop_pct":       0.02,
        "use_price_filter":  False,
        "use_rsi_filter":    True,
        "tp":                0.06,
        "sl":                0.03,
    },
    # ── FALLBACK STRATEGIES (kept for reference / rotation) ──
    # XRPUSDT fallback: rsi_divergence_breakout (Sharpe=0.473, P&L=+$65.85)
    # SUIUSDT fallback: ema_swing (Sharpe=0.213, P&L=+$60.00)
}

# --- MACD+RSI best tuned config (runner-up on SUI: P&L=+$172, Sharpe=0.166) ---
# Use if SUI strategy needs upgrade:
# macd_fast=8, macd_slow=17, macd_signal=9, rsi_max=70, ema_trend=100
# Note: higher P&L but lower Sharpe than EMA Swing

INTERVAL = "240"   # 4h candles

# --- Per-pair strategy module routing ---
# Updated 2026-03-24: funding_rate_divergence promoted on both pairs
STRATEGY_MODULE = {
    "XRPUSDT": "funding_rate_divergence",  # NEW 2026-03-24 (was: rsi_divergence_breakout)
    "SUIUSDT": "funding_rate_divergence",  # NEW 2026-03-24 (was: ema_swing)
}
