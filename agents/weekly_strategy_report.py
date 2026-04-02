#!/usr/bin/env python3
"""
Weekly Strategy Report for Board Meeting
Generates performance analysis and recommendations.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
from datetime import datetime, timedelta
from pathlib import Path

def load_portfolio(portfolio_file: Path) -> dict:
    """Load portfolio data."""
    if not portfolio_file.exists():
        return {"error": "Portfolio file not found"}
    
    try:
        with open(portfolio_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        return {"error": f"Error loading portfolio: {e}"}

def analyze_trades(trades: list) -> dict:
    """Analyze trade performance."""
    if not trades:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "largest_win": 0,
            "largest_loss": 0
        }
    
    wins = [t for t in trades if t.get("pnl_usd", 0) > 0]
    losses = [t for t in trades if t.get("pnl_usd", 0) <= 0]
    
    total_pnl = sum(t.get("pnl_usd", 0) for t in trades)
    avg_win = sum(t.get("pnl_usd", 0) for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t.get("pnl_usd", 0) for t in losses) / len(losses) if losses else 0
    
    largest_win = max((t.get("pnl_usd", 0) for t in wins), default=0)
    largest_loss = min((t.get("pnl_usd", 0) for t in losses), default=0)
    
    return {
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": len(wins) / len(trades) * 100 if trades else 0,
        "total_pnl": total_pnl,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "largest_win": largest_win,
        "largest_loss": largest_loss
    }

def generate_weekly_report():
    """Generate weekly strategy report."""
    print("=" * 80)
    print("📊 WEEKLY STRATEGY REPORT - BOARD OF DIRECTORS")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 80)
    
    base_dir = Path(__file__).parent.parent
    
    # Load portfolios
    mixed_portfolio = load_portfolio(base_dir / "logs" / "paper_portfolio_mixed.json")
    original_portfolio = load_portfolio(base_dir / "logs" / "paper_portfolio.json")
    
    print("\n🎯 EXECUTIVE SUMMARY")
    print("-" * 40)
    
    mixed_pnl = mixed_portfolio.get("total_pnl", 0) if "error" not in mixed_portfolio else 0
    original_pnl = original_portfolio.get("total_pnl", 0) if "error" not in original_portfolio else 0
    
    print(f"Mixed Portfolio (70/30): ${mixed_pnl:+.2f}")
    print(f"Original Portfolio (Long-only): ${original_pnl:+.2f}")
    
    if mixed_pnl > original_pnl:
        print(f"✅ Mixed portfolio outperforming by ${mixed_pnl - original_pnl:.2f}")
    elif original_pnl > mixed_pnl:
        print(f"📈 Original portfolio outperforming by ${original_pnl - mixed_pnl:.2f}")
    else:
        print("⚖️  Portfolios performing equally")
    
    # Trade analysis
    print("\n📈 TRADE PERFORMANCE ANALYSIS")
    print("-" * 40)
    
    if "error" not in mixed_portfolio:
        mixed_trades = mixed_portfolio.get("closed_trades", [])
        mixed_analysis = analyze_trades(mixed_trades)
        
        print(f"\nMixed Portfolio:")
        print(f"  Total trades: {mixed_analysis['total_trades']}")
        print(f"  Win rate: {mixed_analysis['win_rate']:.1f}%")
        print(f"  Total P&L: ${mixed_analysis['total_pnl']:+.2f}")
        print(f"  Avg win: ${mixed_analysis['avg_win']:.2f}")
        print(f"  Avg loss: ${mixed_analysis['avg_loss']:.2f}")
        
        # Analyze by side
        long_trades = [t for t in mixed_trades if t.get("side") == "long"]
        short_trades = [t for t in mixed_trades if t.get("side") == "short"]
        
        if long_trades:
            long_pnl = sum(t.get("pnl_usd", 0) for t in long_trades)
            long_wins = len([t for t in long_trades if t.get("pnl_usd", 0) > 0])
            print(f"  Long trades: {len(long_trades)} (${long_pnl:+.2f}, {long_wins/len(long_trades)*100:.1f}% win rate)")
        
        if short_trades:
            short_pnl = sum(t.get("pnl_usd", 0) for t in short_trades)
            short_wins = len([t for t in short_trades if t.get("pnl_usd", 0) > 0])
            print(f"  Short trades: {len(short_trades)} (${short_pnl:+.2f}, {short_wins/len(short_trades)*100:.1f}% win rate)")
    
    if "error" not in original_portfolio:
        original_trades = original_portfolio.get("closed_trades", [])
        original_analysis = analyze_trades(original_trades)
        
        print(f"\nOriginal Portfolio:")
        print(f"  Total trades: {original_analysis['total_trades']}")
        print(f"  Win rate: {original_analysis['win_rate']:.1f}%")
        print(f"  Total P&L: ${original_analysis['total_pnl']:+.2f}")
    
    # Strategy effectiveness
    print("\n🎯 STRATEGY EFFECTIVENESS")
    print("-" * 40)
    
    # Check which strategies have executed trades
    if "error" not in mixed_portfolio:
        mixed_trades = mixed_portfolio.get("closed_trades", [])
        if mixed_trades:
            strategies = {}
            for trade in mixed_trades:
                strategy = trade.get("strategy", "unknown")
                if strategy not in strategies:
                    strategies[strategy] = {"trades": 0, "pnl": 0, "wins": 0}
                strategies[strategy]["trades"] += 1
                strategies[strategy]["pnl"] += trade.get("pnl_usd", 0)
                if trade.get("pnl_usd", 0) > 0:
                    strategies[strategy]["wins"] += 1
            
            print("Strategy performance (Mixed Portfolio):")
            for strategy, data in strategies.items():
                win_rate = data["wins"] / data["trades"] * 100 if data["trades"] > 0 else 0
                print(f"  {strategy}: {data['trades']} trades, ${data['pnl']:+.2f}, {win_rate:.1f}% win rate")
        else:
            print("No trades executed yet - strategies awaiting market conditions")
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS FOR BOARD MEETING")
    print("-" * 40)
    
    recommendations = []
    
    # Based on trade count
    total_trades = 0
    if "error" not in mixed_portfolio:
        total_trades += len(mixed_portfolio.get("closed_trades", []))
    if "error" not in original_portfolio:
        total_trades += len(original_portfolio.get("closed_trades", []))
    
    if total_trades == 0:
        recommendations.append("⚠️  No trades executed - review signal thresholds or expand to more pairs")
    elif total_trades < 5:
        recommendations.append("📊 Insufficient data - continue current strategy for another week")
    else:
        recommendations.append("✅ Sufficient data for strategy evaluation")
    
    # Based on performance
    if mixed_pnl > 0 and original_pnl > 0:
        recommendations.append("🎯 Both portfolios profitable - consider scaling capital")
    elif mixed_pnl > 0 and original_pnl <= 0:
        recommendations.append("🏆 Mixed portfolio winning - consider increasing 70/30 allocation")
    elif mixed_pnl <= 0 and original_pnl > 0:
        recommendations.append("📈 Original portfolio winning - consider reducing short allocation")
    else:
        recommendations.append("🔄 Both portfolios neutral - maintain current strategy")
    
    # Risk management
    if "error" not in mixed_portfolio:
        cash = mixed_portfolio.get("cash", 0)
        if cash < 1000:
            recommendations.append("💰 Mixed portfolio deploying capital - monitor position sizing")
    
    # Print recommendations
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")
    
    # Action items for board
    print("\n📋 ACTION ITEMS FOR BOARD MEETING")
    print("-" * 40)
    
    actions = [
        "Review trade execution quality",
        "Evaluate strategy parameter effectiveness", 
        "Assess risk-adjusted returns (Sharpe when available)",
        "Decide on capital allocation for next week",
        "Set research priorities for Dr. Chain"
    ]
    
    for i, action in enumerate(actions, 1):
        print(f"{i}. {action}")
    
    print("\n" + "=" * 80)
    print("📅 NEXT WEEKLY BOARD MEETING")
    print("=" * 80)
    print("Date: Next Monday 10:00 UTC")
    print("Location: This report + live dashboard")
    print("Preparation: Review this report before meeting")

if __name__ == "__main__":
    generate_weekly_report()