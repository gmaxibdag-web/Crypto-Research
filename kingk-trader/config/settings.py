# KingK Trader - Config v3 (tuned 2026-03-24 — param sweep + trend filters)

BYBIT_API_KEY    = ""
BYBIT_API_SECRET = ""
BYBIT_TESTNET    = True   # flip to False for live

# --- Trading Mode Configuration ---
TRADING_MODE = "paper"  # "paper" (simulation) or "testnet" (Bybit demo account)
TESTNET_ENABLED = False  # SAFETY FLAG: must be True to submit real orders to testnet
AUTO_CONFIRM_TESTNET = False  # Auto-confirm testnet orders (False = require input)

PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "SUIUSDT"]

TOTAL_CAPITAL = 5000
ALLOCATION = {
    "BTCUSDT": 1000,
    "ETHUSDT": 1000,
    "SOLUSDT": 1000,
    "XRPUSDT": 1000,
    "SUIUSDT": 1000,
    "RESERVE": 0,
}

# --- TUNED STRATEGY PARAMS (2026-03-24 — expanded to 5 pairs) ---
# Backtest results (2yr 4h, $1000 per pair):
#   BTCUSDT: Funding Rate Divergence (Sharpe=0.5818, +$43.39)
#   ETHUSDT: Funding Rate Divergence (Sharpe=0.2367, +$86.13)
#   SOLUSDT: Liquidation Cascade (Sharpe=0.5680, +$188.11)
#   XRPUSDT: Funding Rate Divergence (Sharpe=0.5199, +$360.50)
#   SUIUSDT: Liquidation Cascade (Sharpe=0.8426, +$211.47)
STRATEGY = {
    # ── BTCUSDT: Funding Rate Divergence ──
    "BTCUSDT": {
        "strategy":          "funding_rate_divergence",
        "funding_threshold": -0.00005,
        "oi_drop_pct":       0.02,
        "use_price_filter":  False,
        "use_rsi_filter":    True,
        "tp":                0.06,
        "sl":                0.03,
    },
    # ── ETHUSDT: Funding Rate Divergence ──
    "ETHUSDT": {
        "strategy":          "funding_rate_divergence",
        "funding_threshold": -0.00005,
        "oi_drop_pct":       0.02,
        "use_price_filter":  False,
        "use_rsi_filter":    True,
        "tp":                0.06,
        "sl":                0.03,
    },
    # ── SOLUSDT: Liquidation Cascade ──
    "SOLUSDT": {
        "strategy":          "liquidation_cascade",
        "cluster_pct_threshold": 0.90,
        "funding_threshold": -0.00005,
        "use_rsi_filter":    False,
        "tp":                0.06,
        "sl":                0.03,
    },
    # ── XRPUSDT: Funding Rate Divergence ──
    "XRPUSDT": {
        "strategy":          "funding_rate_divergence",
        "funding_threshold": -0.00005,
        "oi_drop_pct":       0.02,
        "use_price_filter":  False,
        "use_rsi_filter":    True,
        "tp":                0.06,
        "sl":                0.03,
    },
    # ── SUIUSDT: Liquidation Cascade ──
    "SUIUSDT": {
        "strategy":          "liquidation_cascade",
        "cluster_pct_threshold": 0.90,
        "funding_threshold": -0.00005,
        "use_rsi_filter":    False,
        "tp":                0.06,
        "sl":                0.03,
    },
}

# ── LIQUIDATION CASCADE (2026-03-24) ─────────────────────────────────────────
# Signal: OI-derived liquidation spike (top 10%) + red candle + negative funding
# = long capitulation event → relief bounce
#
# XRPUSDT: Sharpe=0.496 | P&L=+$58  | 27 trades | WR=48% | MaxDD=-11.3%
# SUIUSDT: Sharpe=0.831 | P&L=+$97  | 24 trades | WR=50% | MaxDD=-6.4%
#
# VERDICT: Competitive. BEATS funding_rate_divergence on SUI (0.831 vs 0.696 Sharpe).
# Lower trade count = more selective signal.
# NOTE: Requires liquidation + funding CSVs:
#   python3 data/fetch_liquidation_history.py
#   python3 data/fetch_funding_history.py
LIQUIDATION_CASCADE_CONFIG = {
    "XRPUSDT": {
        "strategy":              "liquidation_cascade",
        "cluster_pct_threshold": 0.90,      # top 10% liq vol events
        "funding_threshold":     -0.00005,  # neg funding = bearish over-leverage
        "use_rsi_filter":        False,
        "tp":                    0.06,
        "sl":                    0.03,
    },
    "SUIUSDT": {
        "strategy":              "liquidation_cascade",
        "cluster_pct_threshold": 0.90,
        "funding_threshold":     -0.00005,
        "use_rsi_filter":        False,
        "tp":                    0.06,
        "sl":                    0.03,
    },
}

# --- MACD+RSI best tuned config (runner-up on SUI: P&L=+$172, Sharpe=0.166) ---
# Use if SUI strategy needs upgrade:
# macd_fast=8, macd_slow=17, macd_signal=9, rsi_max=70, ema_trend=100
# Note: higher P&L but lower Sharpe than EMA Swing

INTERVAL = "240"   # 4h candles

# --- Per-pair strategy module routing ---
# Updated 2026-03-24: expanded to 5 pairs (BTC, ETH, SOL, XRP, SUI)
# Backtest winner assignment (2yr 4h):
# BTCUSDT: Funding Rate Divergence (Sharpe=0.5818, +$43.39, 12 trades)
# ETHUSDT: Funding Rate Divergence (Sharpe=0.2367, +$86.13, 33 trades)
# SOLUSDT: Liquidation Cascade (Sharpe=0.5680, +$188.11, 28 trades)
# XRPUSDT: Funding Rate Divergence (Sharpe=0.5199, +$360.50, 50 trades)
# SUIUSDT: Liquidation Cascade (Sharpe=0.8426, +$211.47, 22 trades)
STRATEGY_MODULE = {
    "BTCUSDT": "funding_rate_divergence",
    "ETHUSDT": "funding_rate_divergence",
    "SOLUSDT": "liquidation_cascade",
    "XRPUSDT": "funding_rate_divergence",
    "SUIUSDT": "liquidation_cascade",
}
