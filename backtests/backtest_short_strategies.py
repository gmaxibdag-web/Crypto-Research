#!/usr/bin/env python3
"""
Backtest short strategies on XRPUSDT and SUIUSDT.
Compare performance vs long strategies.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import numpy as np
from pathlib import Path
from backtests.backtest import run_backtest
from strategies.funding_rate_divergence_short import generate_signals as funding_short_signals
from strategies.liquidation_cascade_short import generate_signals as liq_short_signals
from strategies.funding_rate_divergence import generate_signals as funding_long_signals
from strategies.liquidation_cascade import generate_signals as liq_long_signals

def load_data(symbol: str, interval: str = "240") -> pd.DataFrame:
    """Load OHLCV data with funding and liquidation data."""
    data_path = Path(__file__).parent.parent / "data" / "historical" / f"{symbol}_{interval}.csv"
    if not data_path.exists():
        raise FileNotFoundError(f"Data not found: {data_path}")
    
    df = pd.read_csv(data_path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    
    # Load funding data
    funding_path = Path(__file__).parent.parent / "data" / "historical" / f"{symbol}_funding_{interval}.csv"
    if funding_path.exists():
        funding_df = pd.read_csv(funding_path)
        funding_df["datetime"] = pd.to_datetime(funding_df["datetime"])
        df = pd.merge(df, funding_df[["datetime", "funding_rate"]], on="datetime", how="left")
        df["funding_rate"] = df["funding_rate"].fillna(0)
    else:
        df["funding_rate"] = 0
    
    # Load liquidation data
    liq_path = Path(__file__).parent.parent / "data" / "historical" / f"{symbol}_liquidation_{interval}.csv"
    if liq_path.exists():
        liq_df = pd.read_csv(liq_path)
        liq_df["datetime"] = pd.to_datetime(liq_df["datetime"])
        df = pd.merge(df, liq_df[["datetime", "liquidation_volume_usd"]], on="datetime", how="left")
        df["liquidation_volume_usd"] = df["liquidation_volume_usd"].fillna(0)
    else:
        df["liquidation_volume_usd"] = 0
    
    return df

def backtest_strategy(symbol: str, strategy_func, strategy_name: str, 
                     capital: float = 400, tp_pct: float = 0.06, sl_pct: float = 0.03) -> dict:
    """Run backtest for a strategy."""
    # Run backtest using the existing function
    results = run_backtest(
        symbol=symbol,
        capital=capital,
        interval="240",
        strategy_name=strategy_name.replace(" ", "_").lower().replace("(long)", "").replace("(short)", "_short"),
        tp=tp_pct,
        sl=sl_pct
    )
    
    return results

def compare_strategies(symbol: str):
    """Compare long vs short strategies for a symbol."""
    print(f"\n{'='*60}")
    print(f"📊 COMPARING STRATEGIES: {symbol}")
    print(f"{'='*60}")
    
    # Load data
    df = load_data(symbol)
    print(f"Data loaded: {len(df)} candles from {df['datetime'].min().date()} to {df['datetime'].max().date()}")
    
    # Backtest all strategies
    strategies = [
        ("Funding Rate Divergence (LONG)", funding_long_signals),
        ("Funding Rate Divergence (SHORT)", funding_short_signals),
        ("Liquidation Cascade (LONG)", liq_long_signals),
        ("Liquidation Cascade (SHORT)", liq_short_signals),
    ]
    
    results = []
    for name, func in strategies:
        print(f"\n🔍 Testing: {name}...")
        try:
            result = backtest_strategy(df, func, name, capital=400)
            results.append((name, result))
            
            print(f"  Trades: {result['total_trades']}")
            print(f"  P&L: ${result['total_pnl']:+.2f}")
            print(f"  Win Rate: {result['win_rate']:.1f}%")
            print(f"  Sharpe: {result['sharpe_ratio']:.3f}")
            print(f"  Max DD: {result['max_drawdown']:.1%}")
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append((name, {"error": str(e)}))
    
    return results

def print_comparison_table(symbol: str, results):
    """Print comparison table."""
    print(f"\n{'='*80}")
    print(f"🏆 FINAL COMPARISON: {symbol}")
    print(f"{'='*80}")
    print(f"{'Strategy':<40} {'Trades':<8} {'P&L':<10} {'Win%':<8} {'Sharpe':<8} {'MaxDD':<8}")
    print(f"{'-'*80}")
    
    for name, result in results:
        if "error" in result:
            print(f"{name:<40} {'ERROR':<8} {'-':<10} {'-':<8} {'-':<8} {'-':<8}")
        else:
            print(f"{name:<40} {result['total_trades']:<8} ${result['total_pnl']:<+9.2f} "
                  f"{result['win_rate']:<7.1f}% {result['sharpe_ratio']:<7.3f} {result['max_drawdown']:<7.1%}")
    
    # Find best strategy
    valid_results = [(name, r) for name, r in results if "error" not in r and r['total_trades'] > 0]
    if valid_results:
        best = max(valid_results, key=lambda x: x[1]['sharpe_ratio'])
        print(f"\n🏆 BEST STRATEGY: {best[0]}")
        print(f"   Sharpe: {best[1]['sharpe_ratio']:.3f}, P&L: ${best[1]['total_pnl']:.2f}, "
              f"Trades: {best[1]['total_trades']}, Win%: {best[1]['win_rate']:.1f}%")

def main():
    """Main function to compare strategies."""
    print("🚀 SHORT STRATEGY BACKTEST COMPARISON")
    print("Comparing LONG vs SHORT versions of funding rate and liquidation cascade")
    print("=" * 60)
    
    symbols = ["XRPUSDT", "SUIUSDT"]
    
    all_results = {}
    for symbol in symbols:
        results = compare_strategies(symbol)
        all_results[symbol] = results
        print_comparison_table(symbol, results)
    
    # Overall summary
    print(f"\n{'='*80}")
    print("📈 OVERALL SUMMARY")
    print(f"{'='*80}")
    
    for symbol in symbols:
        valid_results = [(name, r) for name, r in all_results[symbol] 
                        if "error" not in r and r.get('total_trades', 0) > 0]
        if valid_results:
            best = max(valid_results, key=lambda x: x[1]['sharpe_ratio'])
            worst = min(valid_results, key=lambda x: x[1]['sharpe_ratio'])
            
            print(f"\n{symbol}:")
            print(f"  Best: {best[0]} (Sharpe: {best[1]['sharpe_ratio']:.3f}, P&L: ${best[1]['total_pnl']:.2f})")
            print(f"  Worst: {worst[0]} (Sharpe: {worst[1]['sharpe_ratio']:.3f}, P&L: ${worst[1]['total_pnl']:.2f})")
            
            # Check if short strategies beat long
            long_results = [(name, r) for name, r in valid_results if "LONG" in name]
            short_results = [(name, r) for name, r in valid_results if "SHORT" in name]
            
            if long_results and short_results:
                best_long = max(long_results, key=lambda x: x[1]['sharpe_ratio'])
                best_short = max(short_results, key=lambda x: x[1]['sharpe_ratio'])
                
                if best_short[1]['sharpe_ratio'] > best_long[1]['sharpe_ratio']:
                    print(f"  🎯 SHORT STRATEGIES WIN! ({best_short[0]} beats {best_long[0]})")
                else:
                    print(f"  📈 LONG STRATEGIES WIN ({best_long[0]} beats {best_short[0]})")

if __name__ == "__main__":
    main()