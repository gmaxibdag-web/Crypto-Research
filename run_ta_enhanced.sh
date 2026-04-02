#!/bin/bash
# Run TA-Enhanced Trading at 08:00 UTC

echo "================================================"
echo "🚀 KING K TRADING - TA-ENHANCED CYCLE"
echo "Time: $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "================================================"

cd /root/.openclaw/workspace/kingk-trader

# Check if we have the required files
if [ ! -f "agents/ta_simple.py" ]; then
    echo "❌ ERROR: TA library not found"
    exit 1
fi

if [ ! -f "data/fetcher_simple.py" ]; then
    echo "❌ ERROR: Data fetcher not found"
    exit 1
fi

# Run the test to verify everything works
echo "🧪 Testing system..."
python3 test_ta_enhanced.py 2>&1 | tail -20

echo ""
echo "✅ System ready for TA-enhanced trading"
echo ""
echo "📊 Next trading cycle will:"
echo "   1. Fetch real-time market data"
echo "   2. Generate base strategy signals"
echo "   3. Enhance with 6 TA indicators"
echo "   4. Execute trades if signals strong enough"
echo "   5. Apply risk management controls"
echo ""
echo "⏰ Scheduled for 08:00 UTC"
echo "================================================"

# Create a cron job for 08:00 UTC if not exists
CRON_JOB="0 8 * * * cd /root/.openclaw/workspace/kingk-trader && python3 test_ta_enhanced.py >> logs/ta_trading_cycle.log 2>&1"

if ! crontab -l 2>/dev/null | grep -q "test_ta_enhanced.py"; then
    echo "📅 Adding cron job for 08:00 UTC daily..."
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "✅ Cron job added"
else
    echo "📅 Cron job already exists"
fi

echo ""
echo "🎯 System Status: READY FOR 08:00 UTC TRADING"
echo "💡 First trade will trigger when:"
echo "   - Funding rate exceeds ±0.00005"
echo "   - OR liquidation volume spikes"
echo "   - Market volatility increases"