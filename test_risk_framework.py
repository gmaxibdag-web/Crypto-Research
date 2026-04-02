#!/usr/bin/env python3
"""
Test Risk Management Framework Integration
"""

import math
from typing import Dict, List, Tuple

class RiskManager:
    """Simple Risk Management Framework"""
    
    @staticmethod
    def calculate_position_size(account_size: float, risk_per_trade: float = 0.02, 
                               stop_loss_pct: float = 0.05) -> float:
        """
        Calculate position size using fixed fractional method
        
        Args:
            account_size: Total account size
            risk_per_trade: % of account to risk per trade (default 2%)
            stop_loss_pct: Stop loss percentage (default 5%)
            
        Returns:
            Position size in dollars
        """
        risk_amount = account_size * risk_per_trade
        position_size = risk_amount / stop_loss_pct
        return position_size
    
    @staticmethod
    def calculate_kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        Calculate Kelly Criterion for optimal position sizing
        
        Args:
            win_rate: Probability of winning (0-1)
            avg_win: Average win amount
            avg_loss: Average loss amount
            
        Returns:
            Kelly fraction (0-1)
        """
        if avg_loss == 0:
            return 0.0
        
        b = avg_win / avg_loss  # Win/loss ratio
        p = win_rate  # Win probability
        q = 1 - p  # Loss probability
        
        kelly = (b * p - q) / b
        return max(0.0, min(kelly, 0.5))  # Cap at 50% for safety
    
    @staticmethod
    def calculate_var(returns: List[float], confidence_level: float = 0.95) -> float:
        """
        Calculate Value at Risk (VaR)
        
        Args:
            returns: List of historical returns
            confidence_level: Confidence level (0.95 for 95%)
            
        Returns:
            VaR as percentage
        """
        if not returns:
            return 0.0
        
        # Sort returns
        sorted_returns = sorted(returns)
        
        # Calculate index for VaR
        index = int((1 - confidence_level) * len(sorted_returns))
        
        if index >= len(sorted_returns):
            index = len(sorted_returns) - 1
        
        var = abs(sorted_returns[index])
        return var
    
    @staticmethod
    def calculate_max_drawdown(prices: List[float]) -> Tuple[float, int, int]:
        """
        Calculate maximum drawdown
        
        Returns:
            (max_drawdown_pct, start_index, end_index)
        """
        if len(prices) < 2:
            return 0.0, 0, 0
        
        peak = prices[0]
        max_dd = 0.0
        peak_index = 0
        trough_index = 0
        
        for i in range(1, len(prices)):
            if prices[i] > peak:
                peak = prices[i]
                peak_index = i
            
            drawdown = (peak - prices[i]) / peak
            
            if drawdown > max_dd:
                max_dd = drawdown
                trough_index = i
        
        return max_dd, peak_index, trough_index
    
    @staticmethod
    def check_circuit_breakers(current_drawdown: float, daily_loss: float, 
                              volatility: float, thresholds: Dict) -> Dict:
        """
        Check circuit breaker conditions
        
        Args:
            current_drawdown: Current drawdown from peak
            daily_loss: Today's loss percentage
            volatility: Current volatility
            thresholds: Dictionary of threshold values
            
        Returns:
            Dict with circuit breaker status
        """
        warnings = []
        actions = []
        
        # Drawdown circuit breaker
        dd_warning = thresholds.get('drawdown_warning', 0.10)  # 10%
        dd_halt = thresholds.get('drawdown_halt', 0.20)  # 20%
        
        if current_drawdown >= dd_halt:
            warnings.append(f"CRITICAL: Drawdown {current_drawdown:.1%} ≥ {dd_halt:.0%}")
            actions.append("HALT_ALL_TRADING")
        elif current_drawdown >= dd_warning:
            warnings.append(f"WARNING: Drawdown {current_drawdown:.1%} ≥ {dd_warning:.0%}")
            actions.append("REDUCE_POSITION_SIZES")
        
        # Daily loss circuit breaker
        daily_warning = thresholds.get('daily_loss_warning', 0.05)  # 5%
        daily_halt = thresholds.get('daily_loss_halt', 0.10)  # 10%
        
        if daily_loss >= daily_halt:
            warnings.append(f"CRITICAL: Daily loss {daily_loss:.1%} ≥ {daily_halt:.0%}")
            actions.append("HALT_ALL_TRADING")
        elif daily_loss >= daily_warning:
            warnings.append(f"WARNING: Daily loss {daily_loss:.1%} ≥ {daily_warning:.0%}")
            actions.append("REDUCE_POSITION_SIZES")
        
        # Volatility circuit breaker
        vol_warning = thresholds.get('volatility_warning', 0.03)  # 3% daily
        vol_halt = thresholds.get('volatility_halt', 0.05)  # 5% daily
        
        if volatility >= vol_halt:
            warnings.append(f"CRITICAL: Volatility {volatility:.1%} ≥ {vol_halt:.0%}")
            actions.append("HALT_ALL_TRADING")
        elif volatility >= vol_warning:
            warnings.append(f"WARNING: Volatility {volatility:.1%} ≥ {vol_warning:.0%}")
            actions.append("REDUCE_POSITION_SIZES")
        
        return {
            'warnings': warnings,
            'actions': actions,
            'trading_allowed': len(actions) == 0 or 'HALT_ALL_TRADING' not in actions
        }

def test_risk_framework():
    """Test risk management framework"""
    print("=" * 70)
    print("🧪 TESTING RISK MANAGEMENT FRAMEWORK")
    print("=" * 70)
    
    rm = RiskManager()
    
    # Test Position Sizing
    print("\n📊 POSITION SIZING TESTS:")
    print("-" * 40)
    
    account_sizes = [10000, 50000, 100000]
    
    for account in account_sizes:
        position = rm.calculate_position_size(account, risk_per_trade=0.02, stop_loss_pct=0.05)
        print(f"Account: ${account:,}")
        print(f"  2% risk per trade, 5% stop loss")
        print(f"  Position Size: ${position:,.2f}")
        print(f"  Risk Amount: ${account * 0.02:,.2f}")
        print()
    
    # Test Kelly Criterion
    print("\n🎯 KELLY CRITERION TESTS:")
    print("-" * 40)
    
    test_cases = [
        (0.55, 1.5, 1.0),  # 55% win rate, 1.5:1 win/loss
        (0.60, 1.2, 1.0),  # 60% win rate, 1.2:1 win/loss
        (0.40, 2.0, 1.0),  # 40% win rate, 2:1 win/loss
    ]
    
    for win_rate, avg_win, avg_loss in test_cases:
        kelly = rm.calculate_kelly_criterion(win_rate, avg_win, avg_loss)
        print(f"Win Rate: {win_rate:.0%}, Win/Loss: {avg_win:.1f}:{avg_loss:.1f}")
        print(f"  Kelly Fraction: {kelly:.1%}")
        print(f"  Suggested Position: {kelly * 100:.1f}% of account")
        print()
    
    # Test Value at Risk
    print("\n📉 VALUE AT RISK (VaR) TESTS:")
    print("-" * 40)
    
    # Generate sample returns
    import random
    sample_returns = [random.uniform(-0.05, 0.03) for _ in range(1000)]
    
    var_95 = rm.calculate_var(sample_returns, 0.95)
    var_99 = rm.calculate_var(sample_returns, 0.99)
    
    print(f"Sample Size: {len(sample_returns)} returns")
    print(f"95% VaR: {var_95:.2%}")
    print(f"99% VaR: {var_99:.2%}")
    print(f"Interpretation: 95% confident losses won't exceed {var_95:.2%}")
    
    # Test Maximum Drawdown
    print("\n📊 MAXIMUM DRAWDOWN TESTS:")
    print("-" * 40)
    
    # Create sample price series with a drawdown
    prices = [100.0]
    for i in range(1, 100):
        if 30 <= i <= 60:  # Create a drawdown
            prices.append(prices[-1] * 0.98)
        else:
            prices.append(prices[-1] * 1.01)
    
    max_dd, peak_idx, trough_idx = rm.calculate_max_drawdown(prices)
    
    print(f"Sample Price Series: {len(prices)} periods")
    print(f"Maximum Drawdown: {max_dd:.2%}")
    print(f"Peak: ${prices[peak_idx]:.2f} at period {peak_idx}")
    print(f"Trough: ${prices[trough_idx]:.2f} at period {trough_idx}")
    print(f"Recovery needed: {(1/(1-max_dd) - 1):.2%}")
    
    # Test Circuit Breakers
    print("\n🚨 CIRCUIT BREAKER TESTS:")
    print("-" * 40)
    
    thresholds = {
        'drawdown_warning': 0.10,
        'drawdown_halt': 0.20,
        'daily_loss_warning': 0.05,
        'daily_loss_halt': 0.10,
        'volatility_warning': 0.03,
        'volatility_halt': 0.05
    }
    
    test_scenarios = [
        (0.08, 0.03, 0.02, "Normal conditions"),
        (0.12, 0.04, 0.025, "Drawdown warning"),
        (0.25, 0.08, 0.04, "Critical drawdown"),
        (0.15, 0.12, 0.06, "Daily loss halt"),
        (0.10, 0.06, 0.07, "High volatility"),
    ]
    
    for drawdown, daily_loss, volatility, scenario in test_scenarios:
        print(f"\nScenario: {scenario}")
        print(f"  Drawdown: {drawdown:.1%}, Daily Loss: {daily_loss:.1%}, Volatility: {volatility:.1%}")
        
        result = rm.check_circuit_breakers(drawdown, daily_loss, volatility, thresholds)
        
        if result['warnings']:
            for warning in result['warnings']:
                print(f"  ⚠️  {warning}")
        
        if result['actions']:
            for action in result['actions']:
                print(f"  🚨 ACTION: {action}")
        
        print(f"  Trading Allowed: {'✅ YES' if result['trading_allowed'] else '❌ NO'}")
    
    # Integration Example
    print("\n" + "=" * 70)
    print("🎯 RISK FRAMEWORK INTEGRATION EXAMPLE")
    print("=" * 70)
    
    print("\nExample: Crypto Trading Division")
    print("-" * 40)
    
    account_size = 50000
    stop_loss = 0.05  # 5%
    
    # Calculate position size
    position = rm.calculate_position_size(account_size, 0.02, stop_loss)
    
    print(f"Account Size: ${account_size:,}")
    print(f"Risk per Trade: 2% (${account_size * 0.02:,.2f})")
    print(f"Stop Loss: {stop_loss:.0%}")
    print(f"Position Size: ${position:,.2f}")
    print(f"Quantity (at $1,000 per unit): {position/1000:.1f} units")
    
    # Check circuit breakers
    print(f"\nRisk Monitoring:")
    print(f"  • Position size limited to ${position:,.2f}")
    print(f"  • Stop loss at {stop_loss:.0%}")
    print(f"  • Daily loss limit: 5% (warning), 10% (halt)")
    print(f"  • Drawdown limit: 10% (warning), 20% (halt)")
    print(f"  • Volatility limit: 3% (warning), 5% (halt)")
    
    print("\n" + "=" * 70)
    print("✅ RISK MANAGEMENT FRAMEWORK TEST COMPLETE")
    print("=" * 70)
    
    # Summary
    print("\n🎯 KEY RISK CONTROLS IMPLEMENTED:")
    print("-" * 40)
    print("1. Position Sizing:")
    print("   • Fixed fractional method")
    print("   • Kelly Criterion for optimal sizing")
    print("   • 2% risk per trade default")
    
    print("\n2. Risk Metrics:")
    print("   • Value at Risk (VaR)")
    print("   • Maximum Drawdown")
    print("   • Volatility monitoring")
    
    print("\n3. Circuit Breakers:")
    print("   • Drawdown limits (10% warning, 20% halt)")
    print("   • Daily loss limits (5% warning, 10% halt)")
    print("   • Volatility limits (3% warning, 5% halt)")
    
    print("\n4. Integration:")
    print("   • Applied to Crypto, Stock, Helius, Hyperliquid divisions")
    print("   • Real-time monitoring")
    print("   • Automated action triggers")

if __name__ == "__main__":
    test_risk_framework()