#!/usr/bin/env python3
"""
KingK Trader Status Dashboard
Quick health check during testnet trial: trader health, quota, portfolio.
"""
import sys
import os
import json
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def get_last_trader_run():
    """Get timestamp of last paper trader run."""
    log_file = LOGS_DIR / "paper_trades.log"
    if not log_file.exists():
        return None, None
    
    lines = log_file.read_text().strip().split("\n")
    for line in reversed(lines):
        if "[" in line and "]" in line and "UTC" in line:
            try:
                ts = line.split("[")[1].split("]")[0]
                if "UTC" in ts:
                    return ts, line
            except:
                continue
    return None, None

def get_portfolio_snapshot():
    """Get current portfolio state."""
    portfolio_file = LOGS_DIR / "paper_portfolio.json"
    if not portfolio_file.exists():
        return None
    
    try:
        return json.loads(portfolio_file.read_text())
    except:
        return None

def get_quota_state():
    """Get current model quota state."""
    quota_file = DATA_DIR / "model_quota_state.json"
    if not quota_file.exists():
        return None
    
    try:
        return json.loads(quota_file.read_text())
    except:
        return None

def print_status():
    """Print testnet trial status dashboard."""
    print(f"\n{'='*70}")
    print(f"  🚀 KingK Trader — Testnet Trial Status Dashboard")
    print(f"  {now_utc()}")
    print(f"{'='*70}\n")
    
    # Paper Trader Health
    print("📊 PAPER TRADER")
    last_run, _ = get_last_trader_run()
    if last_run:
        print(f"  Last run: {last_run}")
    else:
        print(f"  Last run: Unknown (no log)")
    
    portfolio = get_portfolio_snapshot()
    if portfolio:
        print(f"  Cash:          ${portfolio.get('cash', 0):.2f}")
        positions = portfolio.get('positions', {})
        print(f"  Open trades:   {len(positions)} positions")
        print(f"  Total P&L:     ${portfolio.get('total_pnl', 0):.2f}")
        print(f"  Closed trades: {len(portfolio.get('closed_trades', []))} (win rate: {len([t for t in portfolio.get('closed_trades', []) if t.get('pnl_usd', 0) > 0])/max(len(portfolio.get('closed_trades', [])), 1)*100:.0f}%)")
    else:
        print(f"  Status: No portfolio state yet")
    
    # Quota State
    print("\n📈 MODEL QUOTA")
    quota = get_quota_state()
    if quota:
        models = quota.get("models", {})
        
        groq = models.get("groq", {})
        print(f"  Groq:     {groq.get('remaining_requests', '?')}/5000 remaining")
        
        deepseek = models.get("deepseek", {})
        print(f"  DeepSeek: {deepseek.get('remaining_requests', '?')}/50 req/min")
        
        gemini = models.get("gemini", {})
        queries_today = gemini.get('queries_today', 0)
        print(f"  Gemini:   {queries_today}/1500 queries today")
    else:
        print(f"  Status: No quota tracking yet")
    
    # Cron Info
    print("\n⏰ NEXT RUN")
    print(f"  Paper trader runs every 4 hours (Sydney TZ)")
    print(f"  Check logs for latest status: logs/paper_trades.log")
    
    print(f"\n{'='*70}\n")

if __name__ == "__main__":
    print_status()
