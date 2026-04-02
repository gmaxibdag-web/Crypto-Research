#!/usr/bin/env python3
"""
KingK Paper Trader - ENHANCED VERSION with TA Library Integration
Real-time trading with 50+ technical indicators for enhanced signals.
"""
import sys, os, time, json, importlib.util, numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data.fetcher import get_klines, get_ticker
from agents.failsafe import safe_call

# Import TA Library
try:
    # Import our custom TA library
    ta_path = Path(__file__).parent.parent.parent / "skills" / "technical-analysis-library"
    sys.path.insert(0, str(ta_path))
    from ta_calculators import TechnicalAnalysis
    TA_AVAILABLE = True
    print("✅ TA Library loaded successfully")
except ImportError as e:
    TA_AVAILABLE = False
    print(f"⚠️  TA Library not available: {e}")

# Import mixed config
sys.path.insert(0, str(Path(__file__).parent.parent / "config"))
try:
    from settings_mixed import *
    print("✅ Loaded mixed portfolio config (Enhanced version)")
except ImportError:
    # Fallback to default config
    from config.settings import *
    print("⚠️  Using default config (no mixed portfolio)")

PORTFOLIO_FILE = Path(__file__).parent.parent / "logs" / "paper_portfolio_enhanced.json"
LOG_FILE       = Path(__file__).parent.parent / "logs" / "paper_trades_enhanced.log"
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
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def load_portfolio():
    """Load portfolio from JSON file."""
    if PORTFOLIO_FILE.exists():
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "cash": INITIAL_CAPITAL,
        "positions": {},
        "closed_trades": [],
        "total_pnl": 0.0,
        "long_pnl": 0.0,
        "short_pnl": 0.0,
        "ta_signals": {}  # Store TA signals for analysis
    }

def save_portfolio(portfolio):
    """Save portfolio to JSON file."""
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(portfolio, f, indent=2)

def load_strategy_module(strategy_name):
    """Dynamically load a strategy module."""
    strategy_path = STRATEGIES_DIR / f"{strategy_name}.py"
    if not strategy_path.exists():
        raise FileNotFoundError(f"Strategy file not found: {strategy_path}")
    
    spec = importlib.util.spec_from_file_location(strategy_name, strategy_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def calculate_ta_signals(symbol, df, strategy_signal):
    """
    Enhance strategy signals with TA library indicators.
    
    Args:
        symbol: Trading symbol (e.g., "XRPUSDT")
        df: DataFrame with OHLCV data
        strategy_signal: Original strategy signal (-1, 0, 1)
    
    Returns:
        Enhanced signal with TA confirmation
    """
    if not TA_AVAILABLE or len(df) < 50:
        return strategy_signal, {}
    
    try:
        ta = TechnicalAnalysis()
        
        # Extract price arrays
        close_prices = df['close'].values.astype(float)
        high_prices = df['high'].values.astype(float)
        low_prices = df['low'].values.astype(float)
        
        # Calculate key indicators
        ta_results = {}
        
        # 1. Trend Indicators
        ema_12 = ta.ema(close_prices, 12).values
        ema_26 = ta.ema(close_prices, 26).values
        ema_50 = ta.ema(close_prices, 50).values
        
        # EMA crossover signals
        ema_signal = 0
        if len(ema_12) > 0 and len(ema_26) > 0:
            if ema_12[-1] > ema_26[-1] and ema_12[-2] <= ema_26[-2]:
                ema_signal = 1  # Golden cross
            elif ema_12[-1] < ema_26[-1] and ema_12[-2] >= ema_26[-2]:
                ema_signal = -1  # Death cross
        
        # 2. Momentum Indicators
        rsi_result = ta.rsi(close_prices, 14)
        rsi_value = rsi_result.values[-1] if len(rsi_result.values) > 0 else 50
        rsi_signal = 1 if rsi_value < 30 else -1 if rsi_value > 70 else 0
        
        # 3. MACD
        macd_result = ta.macd(close_prices)
        macd_signal = 0
        if len(macd_result['macd']) > 0 and len(macd_result['signal']) > 0:
            if (macd_result['macd'][-1] > macd_result['signal'][-1] and 
                macd_result['macd'][-2] <= macd_result['signal'][-2]):
                macd_signal = 1
            elif (macd_result['macd'][-1] < macd_result['signal'][-1] and 
                  macd_result['macd'][-2] >= macd_result['signal'][-2]):
                macd_signal = -1
        
        # 4. Bollinger Bands
        bb_result = ta.bollinger_bands(close_prices, 20, 2.0)
        bb_signal = 0
        if len(bb_result['percent_b']) > 0:
            current_price = close_prices[-1]
            bb_percent = bb_result['percent_b'][-1]
            if bb_percent < 0:
                bb_signal = 1  # Below lower band
            elif bb_percent > 1:
                bb_signal = -1  # Above upper band
        
        # 5. Stochastic
        stoch_result = ta.stochastic(high_prices, low_prices, close_prices, 14, 3)
        stoch_signal = 0
        if len(stoch_result['fast_k']) > 0 and len(stoch_result['slow_d']) > 0:
            fast_k = stoch_result['fast_k'][-1]
            slow_d = stoch_result['slow_d'][-1]
            if fast_k < 20 and fast_k > slow_d:
                stoch_signal = 1  # Oversold bullish cross
            elif fast_k > 80 and fast_k < slow_d:
                stoch_signal = -1  # Overbought bearish cross
        
        # 6. ATR for volatility
        atr_result = ta.atr(high_prices, low_prices, close_prices, 14)
        atr_value = atr_result.values[-1] if len(atr_result.values) > 0 else 0
        volatility_pct = (atr_value / close_prices[-1]) * 100 if close_prices[-1] > 0 else 0
        
        # Store TA results
        ta_results = {
            'ema_signal': ema_signal,
            'rsi_value': rsi_value,
            'rsi_signal': rsi_signal,
            'macd_signal': macd_signal,
            'bb_signal': bb_signal,
            'stoch_signal': stoch_signal,
            'volatility_pct': volatility_pct,
            'current_price': float(close_prices[-1]),
            'indicators_used': 6
        }
        
        # Weighted signal combination
        signals = []
        weights = []
        
        # Base strategy signal (40% weight)
        signals.append(strategy_signal)
        weights.append(0.4)
        
        # TA signals (60% total weight)
        ta_signals = [ema_signal, rsi_signal, macd_signal, bb_signal, stoch_signal]
        ta_weights = [0.15, 0.15, 0.15, 0.10, 0.05]  # Total 0.6
        
        for sig, w in zip(ta_signals, ta_weights):
            signals.append(sig)
            weights.append(w)
        
        # Calculate weighted signal
        weighted_signal = sum(s * w for s, w in zip(signals, weights))
        
        # Determine final signal
        if weighted_signal > 0.3:
            final_signal = 1  # STRONG BUY
        elif weighted_signal > 0.1:
            final_signal = 0.5  # WEAK BUY
        elif weighted_signal < -0.3:
            final_signal = -1  # STRONG SELL
        elif weighted_signal < -0.1:
            final_signal = -0.5  # WEAK SELL
        else:
            final_signal = 0  # NEUTRAL
        
        # Log TA analysis
        log(f"  📊 TA Analysis for {symbol}:")
        log(f"    EMA Signal: {ema_signal} | RSI: {rsi_value:.1f} ({rsi_signal})")
        log(f"    MACD Signal: {macd_signal} | BB Signal: {bb_signal}")
        log(f"    Stochastic Signal: {stoch_signal} | Volatility: {volatility_pct:.2f}%")
        log(f"    Weighted Signal: {weighted_signal:.3f} → Final: {final_signal}")
        
        return final_signal, ta_results
        
    except Exception as e:
        log(f"  ⚠️  TA calculation error: {e}")
        return strategy_signal, {}

def run_trading_cycle():
    """Run one trading cycle with TA enhancement."""
    log("=" * 70)
    log("🚀 ENHANCED TRADING CYCLE STARTED (TA Library Integrated)")
    log(f"Time: {now_utc()}")
    log(f"TA Library: {'✅ AVAILABLE' if TA_AVAILABLE else '❌ UNAVAILABLE'}")
    log("=" * 70)
    
    portfolio = load_portfolio()
    
    # Track signals for reporting
    all_signals = {}
    
    for symbol_config in TRADING_PAIRS:
        symbol = symbol_config["symbol"]
        strategy_name = symbol_config["strategy"]
        allocation = symbol_config.get("allocation", 1000)
        
        log(f"\n📈 Processing {symbol} (Strategy: {strategy_name})")
        
        try:
            # Load strategy module
            strategy_module = load_strategy_module(strategy_name)
            
            # Get historical data for TA
            df = get_klines(symbol, interval="4h", limit=100)
            if df is None or len(df) < 50:
                log(f"  ⚠️  Insufficient data for {symbol}, skipping")
                continue
            
            # Get real-time price
            ticker = get_ticker(symbol)
            if ticker is None:
                log(f"  ❌ Could not fetch real-time price for {symbol}")
                continue
            
            realtime_price = float(ticker["lastPrice"])
            log(f"  Real-time price: ${realtime_price:.4f}")
            
            # Generate base strategy signal
            base_signal = strategy_module.generate_signal(df)
            log(f"  Base strategy signal: {base_signal}")
            
            # Enhance with TA library
            enhanced_signal, ta_results = calculate_ta_signals(symbol, df, base_signal)
            
            # Store TA results
            portfolio["ta_signals"][symbol] = ta_results
            
            # Determine action based on enhanced signal
            action = "HOLD"
            signal_strength = "⚪"
            
            if enhanced_signal >= 0.5:  # BUY signals
                action = "BUY"
                signal_strength = "🟢" if enhanced_signal == 1 else "🟡"
            elif enhanced_signal <= -0.5:  # SELL signals
                action = "SELL"
                signal_strength = "🔴" if enhanced_signal == -1 else "🟠"
            
            log(f"  {signal_strength} {action} — enhanced signal:{enhanced_signal} | via {strategy_name}")
            
            # Store signal for summary
            all_signals[symbol] = {
                "base_signal": base_signal,
                "enhanced_signal": enhanced_signal,
                "action": action,
                "ta_results": ta_results
            }
            
            # TODO: Implement actual trade execution here
            # For now, just log the signal
            
        except Exception as e:
            log(f"  ❌ Error processing {symbol}: {e}")
            import traceback
            log(f"  Traceback: {traceback.format_exc()}")
    
    # Save portfolio with TA signals
    save_portfolio(portfolio)
    
    # Print summary
    log("\n" + "=" * 70)
    log("📊 ENHANCED TRADING CYCLE SUMMARY")
    log("=" * 70)
    
    for symbol, signal_info in all_signals.items():
        base = signal_info["base_signal"]
        enhanced = signal_info["enhanced_signal"]
        action = signal_info["action"]
        
        log(f"  {symbol}:")
        log(f"    Base Signal: {base} → Enhanced: {enhanced} → Action: {action}")
        
        ta_results = signal_info.get("ta_results", {})
        if ta_results:
            log(f"    TA Indicators: {ta_results.get('indicators_used', 0)} used")
            if 'rsi_value' in ta_results:
                log(f"    RSI: {ta_results['rsi_value']:.1f}")
    
    log("\n💼 PORTFOLIO SNAPSHOT")
    log(f"   Cash:          ${portfolio['cash']:.2f}")
    log(f"   Open positions: {len(portfolio['positions'])}")
    log(f"   Portfolio value: ${portfolio['cash'] + sum(p.get('value', 0) for p in portfolio['positions'].values())}")
    log(f"   Total P&L:      ${portfolio['total_pnl']:+.2f}")
    
    log("=" * 70)
    log("✅ Enhanced trading cycle completed")
    
    return all_signals

def main():
    """Main entry point."""
    try:
        log("🎯 KingK Enhanced Trader Starting...")
        log(f"Version: TA-Enhanced 1.0 | Time: {now_utc()}")
        
        # Run trading cycle
        signals = run_trading_cycle()
        
        # Generate TA report
        if TA_AVAILABLE and signals:
            generate_ta_report(signals)
        
        return 0
        
    except Exception as e:
        log(f"❌ Fatal error in enhanced trader: {e}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        return 1

def generate_ta_report(signals):
    """Generate detailed TA analysis report."""
    report_file = Path(__file__).parent.parent / "logs" / "ta_analysis_report.log"
    
    with open(report_file, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"📊 TECHNICAL ANALYSIS REPORT - {now_utc()}\n")
        f.write(f"{'='*70}\n\n")
        
        for symbol, signal_info in signals.items():
            f.write(f"{symbol}:\n")
            f.write(f"  Base Signal: {signal_info['base_signal']}\n")
            f.write(f"  Enhanced Signal: {signal_info['enhanced_signal']}\n")
            f.write(f"  Action: {signal_info['action']}\n")
            
            ta_results = signal_info.get('ta_results', {})
            if ta_results:
                f.write(f"  TA Indicators Used: {ta_results.get('indicators_used', 0)}\n")
                f.write(f"  EMA Signal: {ta_results.get('ema_signal', 0)}\n")
                f.write(f"  RSI: {ta_results.get('rsi_value', 0):.1f}\n")
                f.write(f"  MACD Signal: {ta_results.get('macd_signal', 0)}\n")
                f.write(f"  BB Signal: {ta_results.get('bb_signal', 0)}\n")
                f.write(f"  Stochastic Signal: {ta_results.get('