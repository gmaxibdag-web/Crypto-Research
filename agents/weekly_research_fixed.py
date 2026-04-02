#!/usr/bin/env python3
"""
Weekly strategy research - Fixed version
Tests existing strategies on multiple pairs and timeframes.
"""
import sys
import os
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
RESEARCH_DIR = BASE_DIR / "research"
BACKTEST_DIR = RESEARCH_DIR / "backtests"
STRATEGIES_DIR = BASE_DIR / "strategies"

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def ensure_dirs():
    BACKTEST_DIR.mkdir(exist_ok=True)

def run_backtest(symbol, interval, strategy, tp=0.06, sl=0.03):
    """Run backtest via CLI with venv activation."""
    venv_python = BASE_DIR / "venv" / "bin" / "python3"
    if not venv_python.exists():
        venv_python = sys.executable
    
    cmd = [
        str(venv_python), "backtests/backtest.py",
        "--symbol", symbol,
        "--interval", interval,
        "--strategy", strategy,
        "--tp", str(tp),
        "--sl", str(sl),
        "--json-output"
    ]
    try:
        result = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout.strip())
        else:
            print(f"Backtest failed: {result.stderr[:200]}")
            return None
    except Exception as e:
        print(f"Backtest error: {e}")
        return None

def get_existing_strategies():
    """Get list of existing strategy files."""
    strategies = []
    for file in STRATEGIES_DIR.glob("*.py"):
        if file.name != "__init__.py":
            strategies.append(file.stem)
    return strategies

def main():
    print(f"\n🔬 Weekly Strategy Research (Fixed) — {now_utc()}")
    print("=" * 60)
    
    ensure_dirs()
    
    # Get existing strategies
    strategies = get_existing_strategies()
    print(f"Found {len(strategies)} strategies: {', '.join(strategies)}")
    
    # Test strategies on both pairs
    pairs = ["XRPUSDT", "SUIUSDT"]
    intervals = ["60", "240"]  # 1h and 4h
    
    results = []
    
    for strategy in strategies:
        print(f"\nTesting {strategy}...")
        
        for pair in pairs:
            for interval in intervals:
                print(f"  {pair} {interval}m: ", end="")
                result = run_backtest(pair, interval, strategy)
                if result:
                    sharpe = result.get("sharpe_ratio", 0)
                    pnl = result.get("total_pnl_usd", 0)
                    trades = result.get("num_trades", 0)
                    win_rate = result.get("win_rate_pct", 0)
                    print(f"Sharpe={sharpe:.3f}, P&L=${pnl:.2f}, Win%={win_rate:.1f}%, trades={trades}")
                    
                    results.append({
                        "pair": pair,
                        "interval": interval,
                        "strategy": strategy,
                        "sharpe": sharpe,
                        "pnl": pnl,
                        "trades": trades,
                        "win_rate": win_rate,
                        "timestamp": now_utc()
                    })
                else:
                    print("Failed")
    
    # Save results
    if results:
        output_file = BACKTEST_DIR / f"weekly_{datetime.now().strftime('%Y%m%d')}.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n✅ Saved {len(results)} backtest results to {output_file}")
        
        # Find best performing strategy
        best_sharpe = max(results, key=lambda x: x["sharpe"])
        best_pnl = max(results, key=lambda x: x["pnl"])
        
        print(f"\n📊 Best by Sharpe: {best_sharpe['strategy']} on {best_sharpe['pair']} {best_sharpe['interval']}m (Sharpe={best_sharpe['sharpe']:.3f})")
        print(f"📊 Best by P&L: {best_pnl['strategy']} on {best_pnl['pair']} {best_pnl['interval']}m (P&L=${best_pnl['pnl']:.2f})")
    
    print("=" * 60)

if __name__ == "__main__":
    main()