#!/usr/bin/env python3
"""
Weekly strategy research using DeepSeek → Groq → Gemini fallback chain.
Mutates existing strategies, backtests, saves best to research/backtests/.
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

def run_backtest(symbol, interval, strategy, tp, sl):
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

def load_findings():
    findings_file = RESEARCH_DIR / "findings.json"
    if not findings_file.exists():
        return []
    with open(findings_file, "r") as f:
        return json.load(f)

def main():
    print(f"\n🔬 Weekly Strategy Research — {now_utc()}")
    print("=" * 60)
    
    ensure_dirs()
    findings = load_findings()
    
    if not findings:
        print("No research findings found. Run strategy_researcher.py first.")
        return
    
    # Test top 3 findings on both pairs
    pairs = ["XRPUSDT", "SUIUSDT"]
    interval = "240"  # 4h
    
    results = []
    
    for i, finding in enumerate(findings[:3]):
        strategy_name = finding.get("strategy_name", f"mutant_{i}")
        print(f"\nTesting {strategy_name}...")
        
        for pair in pairs:
            print(f"  {pair}: ", end="")
            result = run_backtest(pair, interval, strategy_name, 0.06, 0.03)
            if result:
                sharpe = result.get("sharpe_ratio", 0)
                pnl = result.get("total_pnl_usd", 0)
                trades = result.get("num_trades", 0)
                print(f"Sharpe={sharpe:.3f}, P&L=${pnl:.2f}, trades={trades}")
                
                results.append({
                    "pair": pair,
                    "strategy": strategy_name,
                    "sharpe": sharpe,
                    "pnl": pnl,
                    "trades": trades,
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
    
    print("=" * 60)

if __name__ == "__main__":
    main()
