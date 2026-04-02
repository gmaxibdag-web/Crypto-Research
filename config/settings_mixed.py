# KingK Trader - MIXED PORTFOLIO CONFIG (Long + Short)
# Updated: 2026-03-29 - Added short strategies with 30% allocation

BYBIT_API_KEY    = ""
BYBIT_API_SECRET = ""
BYBIT_TESTNET    = True   # flip to False for live

# --- Trading Mode Configuration ---
TRADING_MODE = "testnet"  # "paper" (simulation) or "testnet" (Bybit demo account)
TESTNET_ENABLED = True  # SAFETY FLAG: must be True to submit real orders to testnet
AUTO_CONFIRM_TESTNET = False  # Auto-confirm testnet orders (False = require input)

# Pairs with both long and short strategies
PAIRS = ["XRPUSDT", "SUIUSDT"]

# Total capital: $1000 per pair, split 70% long / 30% short
TOTAL_CAPITAL = 2000
ALLOCATION = {
    "XRPUSDT_LONG": 700,   # 70% of $1000
    "XRPUSDT_SHORT": 300,  # 30% of $1000
    "SUIUSDT_LONG": 700,
    "SUIUSDT_SHORT": 300,
}

# --- STRATEGY CONFIGURATION ---
# Long strategies (70% allocation) - Proven high Sharpe
# Short strategies (30% allocation) - Diversification, lower timeframes

STRATEGY = {
    # XRPUSDT - LONG (Funding Rate Divergence)
    "XRPUSDT_LONG": {
        "strategy":          "funding_rate_divergence",
        "funding_threshold": -0.00005,
        "oi_drop_pct":       0.02,
        "use_price_filter":  False,
        "use_rsi_filter":    True,
        "tp":                0.06,
        "sl":                0.03,
        "interval":          "240",  # 4h
    },
    
    # XRPUSDT - SHORT (Funding Rate Divergence Short)
    "XRPUSDT_SHORT": {
        "strategy":          "funding_rate_divergence_short",
        "funding_threshold": 0.00005,
        "oi_increase_pct":   0.02,
        "use_price_filter":  False,
        "use_rsi_filter":    True,
        "tp":                0.06,
        "sl":                0.03,
        "interval":          "60",   # 1h - test lower timeframe
    },
    
    # SUIUSDT - LONG (Liquidation Cascade)
    "SUIUSDT_LONG": {
        "strategy":              "liquidation_cascade",
        "cluster_pct_threshold": 0.90,
        "funding_threshold":     -0.00005,
        "use_rsi_filter":        False,
        "tp":                    0.06,
        "sl":                    0.03,
        "interval":              "240",  # 4h
    },
    
    # SUIUSDT - SHORT (Liquidation Cascade Short)
    "SUIUSDT_SHORT": {
        "strategy":              "liquidation_cascade_short",
        "cluster_pct_threshold": 0.90,
        "funding_threshold":     0.00005,
        "use_rsi_filter":        False,
        "tp":                    0.06,
        "sl":                    0.03,
        "interval":              "60",   # 1h - test lower timeframe
    },
}

# Strategy module routing
STRATEGY_MODULE = {
    "XRPUSDT_LONG": "funding_rate_divergence",
    "XRPUSDT_SHORT": "funding_rate_divergence_short",
    "SUIUSDT_LONG": "liquidation_cascade",
    "SUIUSDT_SHORT": "liquidation_cascade_short",
}

# Default interval (for backward compatibility)
INTERVAL = "240"

# --- Treasurer Risk Limits ---
# Applied via Treasurer (Risk-1) integration
RISK_LIMITS = {
    "max_position_size_long": 28,    # $28 per long trade (70% of $40)
    "max_position_size_short": 12,   # $12 per short trade (30% of $40)
    "max_leverage_long": 3,
    "max_leverage_short": 2,         # Lower leverage for shorts (more risky)
    "daily_loss_limit_long": 70,     # $70 (10% of $700)
    "daily_loss_limit_short": 45,    # $45 (15% of $300 - tighter due to lower Sharpe)
}

# --- Timeframe Testing Configuration ---
TIMEFRAME_TESTING = {
    "enabled": True,
    "timeframes_to_test": ["15", "30", "60"],  # 15m, 30m, 1h
    "test_duration_days": 7,
    "optimization_metric": "sharpe_ratio",
}