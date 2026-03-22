# KingK Trader - Config v2 (tuned 2026-03-21)

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

# --- TUNED STRATEGY PARAMS (backtested on 2.5yr data) ---
STRATEGY = {
    "XRPUSDT": {
        "ema_fast":  12,
        "ema_slow":  26,
        "ema_trend": 100,   # trend filter — only long above this
        "rsi_min":   45,
        "rsi_max":   65,
        "vol_mult":  1.2,
        "tp":        0.08,  # 8% take profit
        "sl":        0.025, # 2.5% stop loss
    },
    "SUIUSDT": {
        "ema_fast":  12,
        "ema_slow":  26,
        "ema_trend": 100,
        "rsi_min":   50,
        "rsi_max":   65,
        "vol_mult":  1.2,
        "tp":        0.05,  # 5% take profit
        "sl":        0.03,  # 3% stop loss
    },
}

INTERVAL = "240"   # 4h candles
