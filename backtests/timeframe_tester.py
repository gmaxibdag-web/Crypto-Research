#!/usr/bin/env python3
"""
Multi-Timeframe Strategy Tester
Tests strategies on different timeframes (15m, 30m, 1h, 4h) to find optimal.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import numpy as np
from pathlib import Path
from backtests.backtest import run_backtest
import json
from datetime import datetime

def test_timeframe(symbol: str, strategy_name: str, interval: str, 
                  capital: float = 400, days: int = 90) -> dict:
    """
    Test a strategy on a specific timeframe.
    Limits data to last N days for faster testing.
    """
    print(f"  Testing {interval} timeframe...")
    
    try:
        # Run backtest
        results = run_backtest(
            symbol=symbol,
            capital=capital,
            interval=interval,
            strategy_name=strategy_name,
            tp=0.06,
            sl=0.03,
            json_output=False
        )
        
        if results:
            # Calculate additional metrics
            trades = results.get('total_trades', 0)
            pnl = results.get('total_pnl', 0)
            win_rate = results.get('win_rate', 0)
            sharpe = results.get('sharpe_ratio', 0)
            max_dd = results.get('max_drawdown', 0)
            
            # Calculate trades per day
            if trades > 0:
                trades_per_day = trades / (days if days > 0 else 90)
            else:
                trades_per_day = 0
            
            return {
                "interval": interval,
                "trades": trades,
                "trades_per_day": round(trades_per_day, 2),
                "pnl": round(pnl, 2),
                "win_rate": round(win_rate, 1),
                "sharpe": round(sharpe, 3),
                "max_drawdown": round(max_dd, 3),
                "pnl_per_trade": round(pnl / trades, 2) if trades > 0 else 0,
                "success": True
            }
        else:
            return {
                "interval": interval,
                "success": False,
                "error": "No results returned"
            }
            
    except Exception as e:
        return {
            "interval": interval,
            "success": False,
            "error": str(e)
        }

def test_strategy_on_all_timeframes(symbol: str, strategy_name: str, 
                                   capital: float = 400) -> dict:
    """
    Test a strategy on all timeframes.
    """
    print(f"\n🔍 Testing {strategy_name} on {symbol}")
    print("-" * 60)
    
    timeframes = ["15", "30", "60", "240"]  # 15m, 30m, 1h, 4h
    results = {}
    
    for tf in timeframes:
        # Check if data exists
        data_path = Path(__file__).parent.parent / "data" / "historical" / f"{symbol}_{tf}.csv"
        if not data_path.exists():
            print(f"  ❌ No data for {tf} timeframe")
            results[tf] = {"success": False, "error": "No data"}
            continue
        
        result = test_timeframe(symbol, strategy_name, tf, capital, days=90)
        results[tf] = result
        
        if result["success"]:
            print(f"    {tf}: {result['trades']} trades, Sharpe: {result['sharpe']}, "
                  f"P&L: ${result['pnl']}, Trades/day: {result['trades_per_day']}")
        else:
            print(f"    {tf}: Failed - {result.get('error', 'Unknown error')}")
    
    return results

def find_best_timeframe(results: dict) -> tuple:
    """Find the best timeframe based on Sharpe ratio."""
    best_tf = None
    best_sharpe = -999
    best_result = None
    
    for tf, result in results.items():
        if result.get("success") and result.get("sharpe", -999) > best_sharpe:
            best_sharpe = result["sharpe"]
            best_tf = tf
            best_result = result
    
    return best_tf, best_sharpe, best_result

def compare_strategies_timeframes(symbol: str, strategies: list):
    """
    Compare multiple strategies across timeframes.
    """
    print(f"\n{'='*80}")
    print(f"📊 MULTI-TIMEFRAME COMPARISON: {symbol}")
    print(f"{'='*80}")
    
    all_results = {}
    
    for strategy in strategies:
        print(f"\n🎯 Strategy: {strategy}")
        results = test_strategy_on_all_timeframes(symbol, strategy, capital=400)
        all_results[strategy] = results
        
        # Find best timeframe for this strategy
        best_tf, best_sharpe, best_result = find_best_timeframe(results)
        if best_tf:
            print(f"  🏆 Best timeframe: {best_tf} (Sharpe: {best_sharpe:.3f}, "
                  f"P&L: ${best_result['pnl']:.2f}, Trades: {best_result['trades']})")
    
    # Print comparison table
    print(f"\n{'='*80}")
    print("📈 COMPARISON TABLE (Sharpe Ratios)")
    print(f"{'='*80}")
    print(f"{'Strategy':<30} {'15m':<8} {'30m':<8} {'1h':<8} {'4h':<8} {'Best':<8}")
    print(f"{'-'*80}")
    
    for strategy, results in all_results.items():
        sharpe_values = []
        for tf in ["15", "30", "60", "240"]:
            if results.get(tf, {}).get("success"):
                sharpe = results[tf]["sharpe"]
                sharpe_values.append(f"{sharpe:.3f}")
            else:
                sharpe_values.append("N/A")
        
        best_tf, best_sharpe, _ = find_best_timeframe(results)
        best_str = f"{best_tf}({best_sharpe:.3f})" if best_tf else "N/A"
        
        print(f"{strategy:<30} {sharpe_values[0]:<8} {sharpe_values[1]:<8} "
              f"{sharpe_values[2]:<8} {sharpe_values[3]:<8} {best_str:<8}")
    
    # Find overall best strategy+timeframe combo
    print(f"\n{'='*80}")
    print("🏆 OVERALL BEST COMBINATIONS")
    print(f"{'='*80}")
    
    best_combinations = []
    for strategy, results in all_results.items():
        best_tf, best_sharpe, best_result = find_best_timeframe(results)
        if best_tf:
            best_combinations.append({
                "strategy": strategy,
                "timeframe": best_tf,
                "sharpe": best_sharpe,
                "pnl": best_result["pnl"],
                "trades": best_result["trades"],
                "trades_per_day": best_result["trades_per_day"]
            })
    
    # Sort by Sharpe ratio
    best_combinations.sort(key=lambda x: x["sharpe"], reverse=True)
    
    for i, combo in enumerate(best_combinations[:5]):  # Top 5
        rank = "🥇" if i == 0 else ("🥈" if i == 1 else ("🥉" if i == 2 else f"{i+1}."))
        print(f"{rank} {combo['strategy']:.<30} {combo['timeframe']:4} "
              f"Sharpe: {combo['sharpe']:.3f}, P&L: ${combo['pnl']:.2f}, "
              f"Trades/day: {combo['trades_per_day']:.1f}")
    
    return all_results

def save_results(symbol: str, results: dict):
    """Save results to JSON file."""
    output_dir = Path(__file__).parent / "timeframe_results"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"{symbol}_timeframe_test_{timestamp}.json"
    filepath = output_dir / filename
    
    with open(filepath, 'w') as f:
        json.dump({
            "symbol": symbol,
            "timestamp": timestamp,
            "results": results
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: {filepath}")
    return filepath

def main():
    """Main function."""
    print("🚀 MULTI-TIMEFRAME STRATEGY TESTER")
    print("Testing strategies on 15m, 30m, 1h, and 4h timeframes")
    print("=" * 80)
    
    # Test short strategies on different timeframes
    symbols = ["XRPUSDT", "SUIUSDT"]
    short_strategies = ["funding_rate_divergence_short", "liquidation_cascade_short"]
    
    for symbol in symbols:
        print(f"\n{'='*80}")
        print(f"📊 TESTING SHORT STRATEGIES ON: {symbol}")
        print(f"{'='*80}")
        
        # First check if we have data for lower timeframes
        data_missing = False
        for tf in ["15", "30", "60"]:
            data_path = Path(__file__).parent.parent / "data" / "historical" / f"{symbol}_{tf}.csv"
            if not data_path.exists():
                print(f"⚠️  No {tf}m data for {symbol}. Run: python3 data/fetch_history.py --symbol {symbol} --interval {tf}")
                data_missing = True
        
        if data_missing:
            print(f"\n⏭️  Skipping {symbol} due to missing data")
            continue
        
        # Test strategies
        results = compare_strategies_timeframes(symbol, short_strategies)
        
        # Save results
        save_results(symbol, results)
    
    print(f"\n{'='*80}")
    print("🎯 RECOMMENDATIONS")
    print(f"{'='*80}")
    print("""
Based on typical crypto market behavior:

1. **SHORT STRATEGIES** often work better on LOWER TIMEFRAMES:
   - Crypto pullbacks are fast (minutes to hours)
   - Uptrends last longer (days to weeks)
   - Shorts need to catch quick reversals

2. **LONG STRATEGIES** work better on HIGHER TIMEFRAMES:
   - Trend following needs time to develop
   - 4h captures full swing moves
   - Less noise, higher win rates

3. **OPTIMAL MIX** (prediction):
   - Long strategies: 4h timeframe
   - Short strategies: 15m-1h timeframe
   - Mixed portfolio smooths equity curve
""")

if __name__ == "__main__":
    main()