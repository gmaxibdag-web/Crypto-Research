#!/usr/bin/env python3
"""
Quick test: Compare short strategies on 1h vs 4h timeframes.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from backtests.backtest import run_backtest

def test_strategy_tf(symbol: str, strategy: str, interval: str):
    """Test strategy on specific timeframe."""
    print(f"  Testing {interval}...")
    try:
        results = run_backtest(
            symbol=symbol,
            capital=400,
            interval=interval,
            strategy_name=strategy,
            tp=0.06,
            sl=0.03,
            json_output=False
        )
        
        if results:
            trades = results.get('total_trades', 0)
            pnl = results.get('total_pnl', 0)
            sharpe = results.get('sharpe_ratio', 0)
            win_rate = results.get('win_rate', 0)
            
            return {
                "trades": trades,
                "pnl": round(pnl, 2),
                "sharpe": round(sharpe, 3),
                "win_rate": round(win_rate, 1),
                "success": True
            }
        return {"success": False, "error": "No results"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def main():
    print("🚀 1H vs 4H SHORT STRATEGY COMPARISON")
    print("=" * 60)
    
    symbols = ["XRPUSDT", "SUIUSDT"]
    strategies = ["funding_rate_divergence_short", "liquidation_cascade_short"]
    
    for symbol in symbols:
        print(f"\n📊 {symbol}")
        print("-" * 40)
        
        for strategy in strategies:
            print(f"\n🔍 {strategy}:")
            
            # Test 1h
            result_1h = test_strategy_tf(symbol, strategy, "60")
            if result_1h["success"]:
                print(f"  1h: {result_1h['trades']} trades, Sharpe: {result_1h['sharpe']}, "
                      f"P&L: ${result_1h['pnl']}, Win%: {result_1h['win_rate']}%")
            else:
                print(f"  1h: Failed - {result_1h.get('error', 'Unknown')}")
            
            # Test 4h  
            result_4h = test_strategy_tf(symbol, strategy, "240")
            if result_4h["success"]:
                print(f"  4h: {result_4h['trades']} trades, Sharpe: {result_4h['sharpe']}, "
                      f"P&L: ${result_4h['pnl']}, Win%: {result_4h['win_rate']}%")
                
                # Compare
                if result_1h["success"]:
                    sharpe_diff = result_1h["sharpe"] - result_4h["sharpe"]
                    if sharpe_diff > 0.1:
                        print(f"  🎯 1h BETTER by {sharpe_diff:.3f} Sharpe")
                    elif sharpe_diff < -0.1:
                        print(f"  📈 4h BETTER by {-sharpe_diff:.3f} Sharpe")
                    else:
                        print(f"  ⚖️  Similar performance")
            else:
                print(f"  4h: Failed - {result_4h.get('error', 'Unknown')}")
    
    print(f"\n{'='*60}")
    print("🎯 SUMMARY & RECOMMENDATIONS")
    print(f"{'='*60}")
    print("""
Based on crypto market dynamics:

1. **SHORT STRATEGIES ON 1H:**
   - Likely MORE trades (faster signals)
   - Possibly BETTER for catching quick pullbacks
   - Risk: More noise, lower win rates

2. **SHORT STRATEGIES ON 4H:**
   - Fewer, higher conviction trades
   - Catches bigger reversal moves
   - Risk: Misses quick opportunities

3. **PRACTICAL IMPLEMENTATION:**
   - Start with 1h for shorts (test hypothesis)
   - Monitor performance for 1-2 weeks
   - Adjust based on actual results

4. **MIXED PORTFOLIO SETUP:**
   - Long strategies: 4h timeframe (proven)
   - Short strategies: 1h timeframe (to test)
   - Allocation: 70% long, 30% short
""")

if __name__ == "__main__":
    main()