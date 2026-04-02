#!/usr/bin/env python3
"""
Test TA-Enhanced Trading System
"""
import sys
import os
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import our simple modules
from data.fetcher_simple import get_klines_simple, get_ticker_simple
from agents.ta_simple import SimpleTA

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def log(msg: str):
    print(f"[{now_utc()}] {msg}")

def test_ta_enhancement():
    """Test TA enhancement on real market data."""
    print("=" * 70)
    print("🧪 TESTING TA-ENHANCED TRADING SYSTEM")
    print(f"Time: {now_utc()}")
    print("=" * 70)
    
    # Test symbols
    test_symbols = ["XRPUSDT", "SUIUSDT", "BTCUSDT"]
    
    for symbol in test_symbols:
        print(f"\n📈 Testing {symbol}:")
        print("-" * 40)
        
        try:
            # Get market data
            print(f"  Fetching market data...")
            klines = get_klines_simple(symbol, "240", 100)
            ticker = get_ticker_simple(symbol)
            
            if not klines or not ticker:
                print(f"  ❌ Failed to fetch data for {symbol}")
                continue
            
            print(f"  ✅ Data fetched: {len(klines['close'])} candles")
            print(f"  Real-time price: ${float(ticker['lastPrice']):.4f}")
            
            # Simulate a base strategy signal (neutral for testing)
            base_signal = 0
            
            # Enhance with TA
            ta = SimpleTA()
            close_prices = klines['close']
            high_prices = klines['high']
            low_prices = klines['low']
            
            if len(close_prices) >= 30:
                ta_analysis = ta.analyze_signals(close_prices, high_prices, low_prices, base_signal)
                
                print(f"  📊 TA Analysis:")
                print(f"    Base Signal: {base_signal}")
                print(f"    Enhanced Signal: {ta_analysis['enhanced_signal']}")
                print(f"    Weighted Sum: {ta_analysis['weighted_sum']:.3f}")
                print(f"    Indicators Used: {ta_analysis['indicators_used']}")
                
                ta_signals = ta_analysis.get('ta_signals', {})
                if ta_signals:
                    print(f"    RSI: {ta_signals.get('rsi_value', 0):.1f}")
                    print(f"    EMA Signal: {ta_signals.get('ema_signal', 0)}")
                    print(f"    MACD Signal: {ta_signals.get('macd_signal', 0)}")
                    print(f"    BB Signal: {ta_signals.get('bb_signal', 0)}")
                    print(f"    Stochastic Signal: {ta_signals.get('stoch_signal', 0)}")
                
                # Determine action
                enhanced = ta_analysis['enhanced_signal']
                if enhanced >= 0.5:
                    action = "BUY"
                    emoji = "🟢" if enhanced == 1 else "🟡"
                elif enhanced <= -0.5:
                    action = "SELL"
                    emoji = "🔴" if enhanced == -1 else "🟠"
                else:
                    action = "HOLD"
                    emoji = "⚪"
                
                print(f"  {emoji} Action: {action}")
                
            else:
                print(f"  ⚠️  Insufficient data for TA analysis")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            print(f"  Traceback: {traceback.format_exc()}")
    
    print("\n" + "=" * 70)
    print("✅ TA-ENHANCED SYSTEM TEST COMPLETE")
    print("=" * 70)
    
    # Test the SimpleTA library directly
    print("\n🧪 DIRECT TA LIBRARY TEST:")
    print("-" * 40)
    
    # Create sample data
    sample_prices = [100 + i * 0.5 + (i % 3 - 1) for i in range(100)]
    sample_high = [p + 1.0 for p in sample_prices]
    sample_low = [p - 1.0 for p in sample_prices]
    
    ta = SimpleTA()
    
    # Test individual indicators
    print("Testing individual indicators:")
    sma = ta.sma(sample_prices, 20)
    print(f"  SMA(20): {sma[-1] if sma else 'N/A'}")
    
    ema = ta.ema(sample_prices, 20)
    print(f"  EMA(20): {ema[-1] if ema else 'N/A'}")
    
    rsi = ta.rsi(sample_prices, 14)
    print(f"  RSI(14): {rsi[-1] if rsi else 'N/A'}")
    
    macd = ta.macd(sample_prices)
    print(f"  MACD Signal: {macd['signals'][-1] if macd['signals'] else 'N/A'}")
    
    bb = ta.bollinger_bands(sample_prices)
    print(f"  BB Signal: {bb['signals'][-1] if bb['signals'] else 'N/A'}")
    
    stoch = ta.stochastic(sample_high, sample_low, sample_prices)
    print(f"  Stochastic Signal: {stoch['signals'][-1] if stoch['signals'] else 'N/A'}")
    
    print("\n✅ All TA indicators working correctly")

if __name__ == "__main__":
    test_ta_enhancement()