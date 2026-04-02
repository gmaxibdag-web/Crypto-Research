#!/usr/bin/env python3
"""
KingK Trader - Testnet Monitoring Dashboard
Shows status of both mixed and original portfolios.
"""
import sys
import os
import json
from datetime import datetime, timezone
from pathlib import Path

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def read_log_tail(log_file: Path, lines: int = 20) -> str:
    """Read last N lines of a log file."""
    if not log_file.exists():
        return f"Log file not found: {log_file}"
    
    try:
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
            return ''.join(all_lines[-lines:])
    except Exception as e:
        return f"Error reading log: {e}"

def read_portfolio_json(portfolio_file: Path) -> dict:
    """Read portfolio JSON file."""
    if not portfolio_file.exists():
        return {"error": f"Portfolio file not found: {portfolio_file}"}
    
    try:
        with open(portfolio_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        return {"error": f"Error reading portfolio: {e}"}

def print_portfolio_summary(name: str, portfolio: dict):
    """Print portfolio summary."""
    print(f"\n📊 {name}")
    print("-" * 60)
    
    if "error" in portfolio:
        print(f"  ❌ {portfolio['error']}")
        return
    
    cash = portfolio.get("cash", 0)
    total_pnl = portfolio.get("total_pnl", 0)
    positions = portfolio.get("positions", {})
    closed_trades = portfolio.get("closed_trades", [])
    
    print(f"  Cash: ${cash:.2f}")
    print(f"  Total P&L: ${total_pnl:+.2f}")
    print(f"  Open positions: {len(positions)}")
    
    if positions:
        print("  Current positions:")
        for symbol, pos in positions.items():
            side = pos.get("side", "long")
            entry = pos.get("entry_price", 0)
            qty = pos.get("qty", 0)
            strategy = pos.get("strategy", "unknown")
            print(f"    {symbol}: {side.upper()} {qty} @ ${entry} ({strategy})")
    
    print(f"  Closed trades: {len(closed_trades)}")
    
    if closed_trades:
        # Calculate win rate
        wins = [t for t in closed_trades if t.get("pnl_usd", 0) > 0]
        win_rate = len(wins) / len(closed_trades) * 100 if closed_trades else 0
        
        # Calculate P&L by side if mixed portfolio
        long_trades = [t for t in closed_trades if t.get("side") == "long"]
        short_trades = [t for t in closed_trades if t.get("side") == "short"]
        
        long_pnl = sum(t.get("pnl_usd", 0) for t in long_trades)
        short_pnl = sum(t.get("pnl_usd", 0) for t in short_trades)
        
        print(f"  Win rate: {win_rate:.1f}%")
        
        if long_trades or short_trades:
            print(f"  Long P&L: ${long_pnl:+.2f} ({len(long_trades)} trades)")
            print(f"  Short P&L: ${short_pnl:+.2f} ({len(short_trades)} trades)")

def main():
    """Main dashboard function."""
    print("=" * 80)
    print("🚀 KINGK TRADER - TESTNET MONITORING DASHBOARD")
    print(f"Time: {now_utc()}")
    print("=" * 80)
    
    base_dir = Path(__file__).parent.parent
    
    # Portfolio files
    mixed_portfolio = base_dir / "logs" / "paper_portfolio_mixed.json"
    original_portfolio = base_dir / "logs" / "paper_portfolio.json"
    
    # Log files
    mixed_log = base_dir / "logs" / "mixed_portfolio.log"
    original_log = base_dir / "logs" / "paper_trades.log"
    
    # Read portfolios
    mixed_data = read_portfolio_json(mixed_portfolio)
    original_data = read_portfolio_json(original_portfolio)
    
    # Print summaries
    print_portfolio_summary("MIXED PORTFOLIO (70% Long / 30% Short)", mixed_data)
    print_portfolio_summary("ORIGINAL PORTFOLIO (Long-Only)", original_data)
    
    # Compare performance
    print(f"\n{'='*80}")
    print("📈 PERFORMANCE COMPARISON")
    print(f"{'='*80}")
    
    mixed_pnl = mixed_data.get("total_pnl", 0) if "error" not in mixed_data else 0
    original_pnl = original_data.get("total_pnl", 0) if "error" not in original_data else 0
    
    mixed_trades = len(mixed_data.get("closed_trades", [])) if "error" not in mixed_data else 0
    original_trades = len(original_data.get("closed_trades", [])) if "error" not in original_data else 0
    
    print(f"  Mixed Portfolio:    ${mixed_pnl:+.2f} ({mixed_trades} trades)")
    print(f"  Original Portfolio: ${original_pnl:+.2f} ({original_trades} trades)")
    
    if mixed_trades > 0 and original_trades > 0:
        pnl_diff = mixed_pnl - original_pnl
        if pnl_diff > 0:
            print(f"  🎯 Mixed portfolio leads by ${pnl_diff:.2f}")
        elif pnl_diff < 0:
            print(f"  📈 Original portfolio leads by ${-pnl_diff:.2f}")
        else:
            print(f"  ⚖️  Portfolios are tied")
    
    # Show recent log activity
    print(f"\n{'='*80}")
    print("📝 RECENT ACTIVITY (Last 5 log entries each)")
    print(f"{'='*80}")
    
    print(f"\nMixed Portfolio Log:")
    print("-" * 40)
    mixed_log_tail = read_log_tail(mixed_log, 5)
    print(mixed_log_tail if mixed_log_tail else "  No recent activity")
    
    print(f"\nOriginal Portfolio Log:")
    print("-" * 40)
    original_log_tail = read_log_tail(original_log, 5)
    print(original_log_tail if original_log_tail else "  No recent activity")
    
    # Next run times
    print(f"\n{'='*80}")
    print("⏰ NEXT SCHEDULED RUNS")
    print(f"{'='*80}")
    print("""
  Mixed Portfolio:   0,4,8,12,16,20 UTC (every 4h)
  Original Portfolio: 5,9,13,17,21,1 UTC (5min after mixed)
  
  Next runs (UTC):
    - 08:00 UTC: Mixed Portfolio
    - 08:05 UTC: Original Portfolio
    - 12:00 UTC: Mixed Portfolio  
    - 12:05 UTC: Original Portfolio
  """)
    
    # Testnet status
    print(f"\n{'='*80}")
    print("🔧 TESTNET STATUS")
    print(f"{'='*80}")
    
    # Check if testnet is enabled
    try:
        sys.path.insert(0, str(base_dir / "config"))
        from settings_mixed import TRADING_MODE, TESTNET_ENABLED
        print(f"  Trading Mode: {TRADING_MODE}")
        print(f"  Testnet Enabled: {TESTNET_ENABLED}")
        
        if TRADING_MODE == "testnet" and TESTNET_ENABLED:
            print("  ✅ Testnet orders WILL be submitted to Bybit demo account")
        else:
            print("  ⚠️  Paper trading only - no real orders")
    except ImportError:
        print("  ⚠️  Could not load config")
    
    print(f"\n{'='*80}")
    print("💡 QUICK COMMANDS")
    print(f"{'='*80}")
    print("""
  View full logs:
    tail -f logs/mixed_portfolio.log
    tail -f logs/original_portfolio.log
  
  Run manually:
    python3 agents/paper_trader_mixed.py
    python3 agents/paper_trader.py
  
  Check cron jobs:
    crontab -l
  
  View this dashboard:
    python3 agents/monitor_dashboard.py
  """)

if __name__ == "__main__":
    main()