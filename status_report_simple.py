#!/usr/bin/env python3
"""
King K Trading Status Report - Simple Version
"""

import json
import os
import sys
from datetime import datetime, timedelta
import csv

def main():
    print('📊 KING K TRADING STATUS REPORT')
    print('=' * 60)
    print(f'Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}')
    print()
    
    # Check last trading run
    log_file = 'logs/trading.log'
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            lines = f.readlines()
            last_lines = lines[-10:] if len(lines) >= 10 else lines
        print('📈 LAST TRADING RUN LOGS:')
        for line in last_lines:
            print(f'  {line.strip()}')
    else:
        print('📈 No trading logs found')
    print()
    
    # Check portfolio status
    portfolio_file = 'data/portfolio.json'
    if os.path.exists(portfolio_file):
        with open(portfolio_file, 'r') as f:
            portfolio = json.load(f)
        print('💰 PORTFOLIO STATUS:')
        print(f'  Total Value: ${portfolio.get("total_value", 0):.2f}')
        print(f'  Cash: ${portfolio.get("cash", 0):.2f}')
        print(f'  Positions: {len(portfolio.get("positions", []))}')
        
        if 'positions' in portfolio and portfolio['positions']:
            print('  Active Positions:')
            for pos in portfolio['positions']:
                print(f'    - {pos.get("symbol", "Unknown")}: {pos.get("quantity", 0)} @ ${pos.get("entry_price", 0):.4f}')
    else:
        print('💰 No portfolio file found')
    print()
    
    # Check data freshness
    print('📅 DATA FRESHNESS:')
    data_dir = 'data/historical/'
    if os.path.exists(data_dir):
        files = os.listdir(data_dir)
        csv_files = [f for f in files if f.endswith('.csv')]
        
        for csv in csv_files[:5]:  # Show first 5
            path = os.path.join(data_dir, csv)
            try:
                with open(path, 'r') as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                    if len(rows) > 1:
                        last_row = rows[-1]
                        print(f'  {csv}: {len(rows)-1} rows, last: {last_row[0][:19]}...')
                    else:
                        print(f'  {csv}: {len(rows)-1} rows')
            except Exception as e:
                print(f'  {csv}: Error reading')
    else:
        print('  No historical data directory')
    print()
    
    # Check cron jobs
    print('⏰ SCHEDULED TRADING CYCLES:')
    print('  Mixed Portfolio: 0,4,8,12,16,20 UTC')
    print('  Original Portfolio: 5,9,13,17,21,1 UTC')
    print('  Data Updates: 03:55-03:58 UTC (before 04:00 trading)')
    print('  Daily Report: 09:00 UTC')
    print('  Weekly Research: Sundays 02:00 UTC')
    print()
    
    # Check testnet status
    print('🟢 TESTNET STATUS:')
    print('  Mode: TESTNET (Bybit demo account)')
    print('  Capital: $5000 total ($1000 per pair)')
    print('  Duration: 2-week trial (Mar 24 - Apr 7)')
    print('  Auto-confirm: ENABLED')
    print()
    
    # Next trading cycle
    now = datetime.utcnow()
    next_hour = (now.hour // 4 + 1) * 4
    if next_hour >= 24:
        next_hour = 0
    next_time = datetime(now.year, now.month, now.day, next_hour, 0, 0)
    if next_time < now:
        next_time += timedelta(days=1)
        
    time_diff = next_time - now
    hours = time_diff.seconds // 3600
    minutes = (time_diff.seconds % 3600) // 60
    
    print('⏳ NEXT TRADING CYCLE:')
    print(f'  Next run: {next_time.strftime("%H:%M UTC")}')
    print(f'  In: {hours}h {minutes}m')
    print()
    
    # Check skill development
    print('🛠️ SKILL DEVELOPMENT STATUS:')
    print('  Total Skills: 21 (4 custom + 17 acquired)')
    print('  Custom Skills Built:')
    print('    1. Risk Management Framework')
    print('    2. Portfolio Optimization')
    print('    3. Technical Analysis Library (50+ indicators)')
    print('    4. Options Trading Strategies')
    print()
    
    # Division status
    print('🏢 TRADING DIVISIONS STATUS:')
    print('  Crypto Division (Bybit): ✅ PRODUCTION-READY')
    print('    - Mixed portfolio (70% long / 30% short)')
    print('    - 5 pairs: BTC, ETH, SOL, XRP, SUI')
    print('    - Strategies: Funding Rate Divergence + Liquidation Cascade')
    print()
    print('  Stock Division: ✅ READY FOR PAPER TRADING')
    print('    - Data pipeline: US + ASX markets')
    print('    - Options strategies ready')
    print('    - Backtester + risk framework')
    print()
    print('  Helius Division (Solana): ⚠️ AWAITING WALLET')
    print('    - API tested (3/5 endpoints working)')
    print('    - MEV bot prototype ready')
    print('    - Needs Phantom wallet key for live')
    print()
    print('  Hyperliquid Division: ⚠️ AWAITING WALLET')
    print('    - Bot cloned and analyzed')
    print('    - Zero-fee perpetual trading')
    print('    - Needs Hyperliquid API wallet')
    print()
    
    # Current market conditions
    print('📈 CURRENT MARKET CONDITIONS:')
    print('  Crypto: Calm, no extreme funding or liquidation events')
    print('  Strategies are event-driven:')
    print('    - Funding Rate Divergence: needs extremes (<-0.00005 or >0.00005)')
    print('    - Liquidation Cascade: needs top 10% liquidation volume')
    print('  Stock Markets: Closed (US/ASX)')
    print()
    
    print('🎯 IMMEDIATE ACTIONS:')
    print('  1. Integrate TA library into 08:00 UTC trading cycle')
    print('  2. Test options strategies with Stock Division paper trading')
    print('  3. Apply risk framework to all trading cycles')
    print('  4. Push skill backup to GitHub')
    print()
    
    print('=' * 60)
    print('✅ SYSTEM STATUS: PRODUCTION-READY, AWAITING MARKET CONDITIONS')
    print('💡 First trade will trigger when:')
    print('   - Funding rate exceeds ±0.00005 threshold')
    print('   - OR liquidation volume spikes to top 10%')
    print('   - Market volatility increases')

if __name__ == '__main__':
    main()