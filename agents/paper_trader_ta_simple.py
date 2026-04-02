#!/usr/bin/env python3
"""
KingK Paper Trader - TA Enhanced (Simple Version)
Real-time trading with basic technical indicators for enhanced signals.
"""
import sys, os, time, json, importlib.util
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data.fetcher import get_klines, get_ticker
from agents.failsafe import safe_call
from agents.ta_simple import SimpleTA

# Import mixed config
sys.path.insert(0, str(Path(__file__).parent.parent / "config"))
try:
    from settings_mixed import *
    print("✅ Loaded mixed portfolio config (TA Enhanced version)")
except ImportError:
    # Fallback to default config
    from config.settings import *
    print("⚠️  Using default config (no mixed portfolio)")

PORTFOLIO_FILE = Path(__file__).parent.parent / "logs" / "paper_portfolio_ta_enhanced.json"
LOG_FILE       = Path(__file__).parent.parent / "logs" / "paper_trades_ta_enhanced.log"
STRATEGIES_DIR = Path(__file__).parent.parent / "strategies"

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
        "ta_analysis": {}  # Store TA analysis results
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

def enhance_with_ta(symbol, df, base_signal):
    """
    Enhance strategy signal with TA indicators.
    
    Returns:
        enhanced_signal, ta_analysis
    """
    if df is None or len(df) < 30:
        return base_signal, {"error": "Insufficient data"}
    
    try:
        # Extract price data
        close_prices = [float(x) for x in df['close'].values[-100:]]  # Last 100 candles
        high_prices = [float(x) for x in df['high'].values[-100:]]
        low_prices = [float(x) for x in df['low'].values[-100:]]
        
        # Use SimpleTA for analysis
        ta_analysis = SimpleTA.analyze_signals(close_prices, high_prices, low_prices, base_signal)
        
        # Log TA analysis
        log(f"  📊 TA Analysis for {symbol}:")
        ta_signals = ta_analysis.get('ta_signals', {})
        if ta_signals:
            log(f"    RSI: {ta_signals.get('rsi_value', 0):.1f} ({ta_signals.get('rsi_signal', 0)})")
            log(f"    EMA Signal: {ta_signals.get('ema_signal', 0)}")
            log(f"    MACD Signal: {ta_signals.get('macd_signal', 0)}")
            log(f"    BB Signal: {ta_signals.get('bb_signal', 0)}")
            log(f"    Stochastic Signal: {ta_signals.get('stoch_signal', 0)}")
        
        log(f"    Weighted Sum: {ta_analysis.get('weighted_sum', 0):.3f}")
        log(f"    Enhanced Signal: {ta_analysis.get('enhanced_signal', 0)}")
        
        return ta_analysis['enhanced_signal'], ta_analysis
        
    except Exception as e:
        log(f"  ⚠️  TA enhancement error: {e}")
        return base_signal, {"error": str(e)}

def run_ta_enhanced_trading():
    """Run TA-enhanced trading cycle."""
    log("=" * 70)
    log("🚀 TA-ENHANCED TRADING CYCLE STARTED")
    log(f"Time: {now_utc()}")
    log("TA Library: ✅ SIMPLE TA (6 indicators)")
    log("=" * 70)
    
    portfolio = load_portfolio()
    trading_results = []
    
    for symbol_config in TRADING_PAIRS:
        symbol = symbol_config["symbol"]
        strategy_name = symbol_config["strategy"]
        
        log(f"\n📈 Processing {symbol} (Strategy: {strategy_name})")
        
        try:
            # Load strategy
            strategy_module = load_strategy_module(strategy_name)
            
            # Get data
            df = get_klines(symbol, interval="4h", limit=100)
            if df is None or len(df) < 30:
                log(f"  ⚠️  Insufficient data, skipping")
                continue
            
            # Get real-time price
            ticker = get_ticker(symbol)
            if ticker is None:
                log(f"  ❌ Could not fetch real-time price")
                continue
            
            realtime_price = float(ticker["lastPrice"])
            log(f"  Real-time price: ${realtime_price:.4f}")
            
            # Generate base signal
            base_signal = strategy_module.generate_signal(df)
            log(f"  Base strategy signal: {base_signal}")
            
            # Enhance with TA
            enhanced_signal, ta_analysis = enhance_with_ta(symbol, df, base_signal)
            
            # Determine action
            action = "HOLD"
            signal_emoji = "⚪"
            
            if enhanced_signal >= 0.5:
                action = "BUY"
                signal_emoji = "🟢" if enhanced_signal == 1 else "🟡"
            elif enhanced_signal <= -0.5:
                action = "SELL"
                signal_emoji = "🔴" if enhanced_signal == -1 else "🟠"
            
            log(f"  {signal_emoji} {action} — enhanced:{enhanced_signal} | via {strategy_name}")
            
            # Store results
            trading_results.append({
                "symbol": symbol,
                "base_signal": base_signal,
                "enhanced_signal": enhanced_signal,
                "action": action,
                "realtime_price": realtime_price,
                "ta_analysis": ta_analysis
            })
            
            # Store TA analysis in portfolio
            portfolio["ta_analysis"][symbol] = ta_analysis
            
        except Exception as e:
            log(f"  ❌ Error: {e}")
    
    # Save portfolio with TA analysis
    save_portfolio(portfolio)
    
    # Print summary
    log("\n" + "=" * 70)
    log("📊 TA-ENHANCED TRADING SUMMARY")
    log("=" * 70)
    
    buy_signals = 0
    sell_signals = 0
    hold_signals = 0
    
    for result in trading_results:
        symbol = result["symbol"]
        base = result["base_signal"]
        enhanced = result["enhanced_signal"]
        action = result["action"]
        
        if action == "BUY":
            buy_signals += 1
        elif action == "SELL":
            sell_signals += 1
        else:
            hold_signals += 1
        
        log(f"  {symbol}: Base={base} → Enhanced={enhanced} → {action}")
    
    log(f"\n📈 SIGNAL DISTRIBUTION:")
    log(f"  BUY: {buy_signals} | SELL: {sell_signals} | HOLD: {hold_signals}")
    
    log("\n💼 PORTFOLIO STATUS:")
    log(f"  Cash: ${portfolio['cash']:.2f}")
    log(f"  Positions: {len(portfolio['positions'])}")
    log(f"  Total P&L: ${portfolio['total_pnl']:+.2f}")
    
    log("=" * 70)
    log("✅ TA-enhanced trading cycle completed")
    
    return trading_results

def main():
    """Main entry point."""
    try:
        log("🎯 KingK TA-Enhanced Trader Starting...")
        log(f"Version: Simple TA 1.0 | Time: {now_utc()}")
        
        # Run enhanced trading
        results = run_ta_enhanced_trading()
        
        # Generate report
        if results:
            generate_ta_report(results)
        
        return 0
        
    except Exception as e:
        log(f"❌ Fatal error: {e}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        return 1

def generate_ta_report(results):
    """Generate TA analysis report."""
    report_file = Path(__file__).parent.parent / "logs" / "ta_enhanced_report.log"
    
    with open(report_file, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"📊 TA-ENHANCED TRADING REPORT - {now_utc()}\n")
        f.write(f"{'='*70}\n\n")
        
        for result in results:
            f.write(f"{result['symbol']}:\n")
            f.write(f"  Base Signal: {result['base_signal']}\n")
            f.write(f"  Enhanced Signal: {result['enhanced_signal']}\n")
            f.write(f"  Action: {result['action']}\n")
            f.write(f"  Price: ${result['realtime_price']:.4f}\n")
            
            ta = result.get('ta_analysis', {})
            if ta and 'ta_signals' in ta:
                signals = ta['ta_signals']
                f.write(f"  TA Indicators:\n")
                f.write(f"    RSI: {signals.get('rsi_value', 0):.1f}\n")
                f.write(f"    EMA Signal: {signals.get('ema_signal', 0)}\n")
                f.write(f"    MACD Signal: {signals.get('macd_signal', 0)}\n")
                f.write(f"    BB Signal: {signals.get('bb_signal', 0)}\n")
                f.write(f"    Stochastic Signal: {signals.get('stoch_signal', 0)}\n")
            
            f.write("\n")
        
        f.write(f"{'='*70}\n")

if __name__ == "__main__":
    sys.exit(main())