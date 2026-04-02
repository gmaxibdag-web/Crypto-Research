#!/usr/bin/env python3
"""
Treasurer Integration for Crypto Division.
Modifies paper_trader.py to check with Treasurer before trades.
"""

import sys
import os
from pathlib import Path

# Add Treasurer to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "treasurer"))

try:
    from treasurer_orchestrator import TreasurerOrchestrator
    TREASURER_AVAILABLE = True
except ImportError:
    TREASURER_AVAILABLE = False
    print("⚠️  Treasurer not available - running in legacy mode")

class TreasurerIntegration:
    """Wrapper for Treasurer integration in Crypto Division."""
    
    def __init__(self):
        self.treasurer = None
        self.integrated = False
        
        if TREASURER_AVAILABLE:
            try:
                self.treasurer = TreasurerOrchestrator()
                self.treasurer.integrate_division("crypto")
                self.integrated = True
                print("✅ Treasurer integration active for Crypto Division")
            except Exception as e:
                print(f"❌ Treasurer integration failed: {e}")
                self.integrated = False
        else:
            print("⚠️  Running without Treasurer - PAPER TRADING ONLY")
    
    def check_trade(self, symbol: str, size: float, leverage: float = 1.0, 
                   order_type: str = "market") -> dict:
        """
        Check with Treasurer before executing trade.
        Returns approval dict.
        """
        if not self.integrated or not self.treasurer:
            # Fallback: paper trading only
            return {
                "approved": False,
                "reason": "Treasurer not integrated - paper trading only",
                "simulated": True,
                "simulated_pnl": 0
            }
        
        trade_details = {
            "symbol": symbol,
            "size": size,
            "leverage": leverage,
            "order_type": order_type,
            "timestamp": os.environ.get("TRADE_TIMESTAMP", "unknown")
        }
        
        # Check with Treasurer
        result = self.treasurer.check_trade_request("crypto", trade_details)
        
        return result
    
    def update_performance(self, pnl: float, trades: int = 1, error_rate: float = 0.0):
        """Update performance metrics with Treasurer."""
        if self.integrated and self.treasurer:
            metrics = {
                "pnl": pnl,
                "trades": trades,
                "error_rate": error_rate
            }
            return self.treasurer.update_division_performance("crypto", pnl, trades, metrics)
        return None
    
    def get_division_status(self):
        """Get division status from Treasurer."""
        if self.integrated and self.treasurer:
            return self.treasurer.capital_allocator.get_division_status("crypto")
        return None
    
    def emergency_stop(self, reason: str = "Manual emergency stop"):
        """Trigger emergency stop through Treasurer."""
        if self.integrated and self.treasurer:
            return self.treasurer.emergency_action("kill_switch", reason=reason)
        return {"error": "Treasurer not integrated"}
    
    def generate_report(self):
        """Generate Treasurer report."""
        if self.integrated and self.treasurer:
            return self.treasurer.generate_weekly_report()
        return None

# Test the integration
if __name__ == "__main__":
    print("🧪 Testing Treasurer Integration for Crypto Division")
    print("=" * 60)
    
    integration = TreasurerIntegration()
    
    if integration.integrated:
        print(f"✅ Treasurer integrated: {integration.integrated}")
        
        # Test trade check
        print("\n🔍 Testing trade check:")
        result = integration.check_trade("BTCUSDT", 100, 3, "market")
        print(f"  Approved: {result['approved']}")
        print(f"  Reason: {result.get('reason', 'N/A')}")
        
        # Test performance update
        print("\n📊 Testing performance update:")
        perf = integration.update_performance(25.50, 3, 0.01)
        if perf:
            print(f"  Healthy: {perf.get('healthy', 'N/A')}")
        
        # Get division status
        print("\n📈 Getting division status:")
        status = integration.get_division_status()
        if status:
            print(f"  Capital: ${status.get('capital_allocated', 0):.2f}")
            print(f"  Status: {status.get('status', 'N/A')}")
        
        print("\n✅ Treasurer integration test complete")
    else:
        print("❌ Treasurer not available - running in fallback mode")
        print("All trades: PAPER TRADING ONLY")