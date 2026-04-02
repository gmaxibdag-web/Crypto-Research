#!/usr/bin/env python3
"""
Quick test of short strategies using existing backtester.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from backtests.backtest import run_backtest

def test_strategy(symbol: str, strategy_name: str, tp: float = 0.06, sl: float = 0.03):
    """Test a strategy and return results."""
    print(f"\n🔍 Testing {strategy_name} on {symbol}...")
    try:
        # Capture output to parse results
        import io
        import sys
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            results = run_backtest(
                symbol=symbol,
                capital=400,
                interval="240",
                strategy_name=strategy_name,
                tp=tp,
                sl=sl,
                json_output=False
            )
        
        output = f.getvalue()
        
        # Parse the output to extract key metrics
        metrics = {}
        lines = output.split('\n')
        
        for line in lines:
            if "Trades:" in line:
                try:
                    metrics['total_trades'] = int(line.split("Trades:")[1].strip().split()[0])
                except:
                    pass
            elif "Total P&L:" in line:
                try:
                    pnl_str = line.split("Total P&L:")[1].strip().split()[0].replace('$', '').replace(',', '')
                    metrics['total_pnl'] = float(pnl_str)
                except:
                    pass
            elif "Win Rate:" in line:
                try:
                    win_rate_str = line.split("Win Rate:")[1].strip().split('%')[0]
                    metrics['win_rate'] = float(win_rate_str)
                except:
                    pass
            elif "Sharpe Ratio:" in line:
                try:
                    sharpe_str = line.split("Sharpe Ratio:")[1].strip().split()[0]
                    metrics['sharpe_ratio'] = float(sharpe_str)
                except:
                    pass
            elif "Max Drawdown:" in line:
                try:
                    dd_str = line.split("Max Drawdown:")[1].strip().split('%')[0]
                    metrics['max_drawdown'] = float(dd_str) / 100
                except:
                    pass
        
        # Print summary
        if metrics:
            print(f"  Trades: {metrics.get('total_trades', 'N/A')}")
            print(f"  P&L: ${metrics.get('total_pnl', 0):+.2f}")
            print(f"  Win Rate: {metrics.get('win_rate', 0):.1f}%")
            print(f"  Sharpe: {metrics.get('sharpe_ratio', 0):.3f}")
            print(f"  Max DD: {metrics.get('max_drawdown', 0):.1%}")
            return metrics
        else:
            print(f"  ❌ Could not parse results")
            return None
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

def main():
    print("🚀 TESTING SHORT STRATEGIES")
    print("=" * 60)
    
    symbols = ["XRPUSDT", "SUIUSDT"]
    strategies = [
        "funding_rate_divergence",  # Original long
        "funding_rate_divergence_short",  # New short
        "liquidation_cascade",  # Original long  
        "liquidation_cascade_short",  # New short
    ]
    
    all_results = {}
    
    for symbol in symbols:
        print(f"\n{'='*60}")
        print(f"📊 {symbol}")
        print(f"{'='*60}")
        
        symbol_results = {}
        for strategy in strategies:
            # Adjust TP/SL for short strategies (same percentages, different direction)
            results = test_strategy(symbol, strategy)
            symbol_results[strategy] = results
        
        all_results[symbol] = symbol_results
    
    # Print comparison
    print(f"\n{'='*80}")
    print("🏆 FINAL COMPARISON")
    print(f"{'='*80}")
    print(f"{'Symbol/Strategy':<35} {'Trades':<8} {'P&L':<10} {'Win%':<8} {'Sharpe':<8}")
    print(f"{'-'*80}")
    
    for symbol in symbols:
        print(f"\n{symbol}:")
        for strategy in strategies:
            results = all_results[symbol].get(strategy)
            if results:
                print(f"  {strategy:<31} {results['total_trades']:<8} ${results['total_pnl']:<+9.2f} "
                      f"{results['win_rate']:<7.1f}% {results['sharpe_ratio']:<7.3f}")
            else:
                print(f"  {strategy:<31} {'-':<8} {'-':<10} {'-':<8} {'-':<8}")
    
    # Determine if short strategies are better
    print(f"\n{'='*80}")
    print("🎯 SHORT VS LONG ANALYSIS")
    print(f"{'='*80}")
    
    for symbol in symbols:
        print(f"\n{symbol}:")
        
        # Get best long and short strategies
        long_results = {}
        short_results = {}
        
        for strategy, results in all_results[symbol].items():
            if results:
                if "short" in strategy:
                    short_results[strategy] = results['sharpe_ratio']
                else:
                    long_results[strategy] = results['sharpe_ratio']
        
        if long_results and short_results:
            best_long = max(long_results.items(), key=lambda x: x[1])
            best_short = max(short_results.items(), key=lambda x: x[1])
            
            print(f"  Best LONG: {best_long[0]} (Sharpe: {best_long[1]:.3f})")
            print(f"  Best SHORT: {best_short[0]} (Sharpe: {best_short[1]:.3f})")
            
            if best_short[1] > best_long[1]:
                print(f"  🎯 SHORT STRATEGIES WIN! (+{best_short[1] - best_long[1]:.3f} Sharpe)")
            else:
                print(f"  📈 LONG STRATEGIES WIN (+{best_long[1] - best_short[1]:.3f} Sharpe)")
        else:
            print(f"  ❌ Not enough data for comparison")

if __name__ == "__main__":
    main()