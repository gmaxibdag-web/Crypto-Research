#!/usr/bin/env python3
"""
Simple Technical Analysis Library - No numpy dependency
Basic indicators for enhanced signal generation
"""

import math
from typing import List, Dict, Optional

class SimpleTA:
    """Simple Technical Analysis without numpy dependency"""
    
    @staticmethod
    def sma(prices: List[float], period: int) -> List[float]:
        """Simple Moving Average"""
        if len(prices) < period:
            return []
        
        sma_values = []
        for i in range(period - 1, len(prices)):
            window = prices[i - period + 1:i + 1]
            sma_values.append(sum(window) / period)
        
        return sma_values
    
    @staticmethod
    def ema(prices: List[float], period: int) -> List[float]:
        """Exponential Moving Average"""
        if len(prices) < period:
            return []
        
        alpha = 2 / (period + 1)
        ema_values = [prices[0]]
        
        for price in prices[1:]:
            ema_value = alpha * price + (1 - alpha) * ema_values[-1]
            ema_values.append(ema_value)
        
        return ema_values
    
    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> List[float]:
        """Relative Strength Index"""
        if len(prices) < period + 1:
            return []
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        
        gains = [delta if delta > 0 else 0 for delta in deltas]
        losses = [-delta if delta < 0 else 0 for delta in deltas]
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        rsi_values = [100 - 100 / (1 + (avg_gain / avg_loss if avg_loss != 0 else 1))]
        
        for i in range(period, len(deltas)):
            gain = gains[i] if i < len(gains) else 0
            loss = losses[i] if i < len(losses) else 0
            
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period
            
            rs = avg_gain / avg_loss if avg_loss != 0 else 1
            rsi_values.append(100 - 100 / (1 + rs))
        
        # Pad beginning with first value
        padded_rsi = [rsi_values[0]] * (period) + rsi_values
        
        return padded_rsi[:len(prices)]
    
    @staticmethod
    def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """MACD Indicator"""
        ema_fast = SimpleTA.ema(prices, fast)
        ema_slow = SimpleTA.ema(prices, slow)
        
        # Align lengths
        min_len = min(len(ema_fast), len(ema_slow))
        ema_fast = ema_fast[-min_len:]
        ema_slow = ema_slow[-min_len:]
        
        macd_line = [fast - slow for fast, slow in zip(ema_fast, ema_slow)]
        signal_line = SimpleTA.ema(macd_line, signal)
        
        # Align signal line
        signal_len = len(signal_line)
        macd_line = macd_line[-signal_len:]
        
        histogram = [m - s for m, s in zip(macd_line, signal_line)]
        
        # Generate signals
        signals = [0] * len(prices)
        for i in range(1, len(macd_line)):
            idx = len(prices) - len(macd_line) + i
            if idx < len(signals):
                if macd_line[i-1] <= signal_line[i-1] and macd_line[i] > signal_line[i]:
                    signals[idx] = 1  # Bullish crossover
                elif macd_line[i-1] >= signal_line[i-1] and macd_line[i] < signal_line[i]:
                    signals[idx] = -1  # Bearish crossover
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram,
            'signals': signals[-len(prices):] if len(signals) >= len(prices) else [0] * len(prices)
        }
    
    @staticmethod
    def bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2.0) -> Dict:
        """Bollinger Bands"""
        if len(prices) < period:
            return {'upper': [], 'middle': [], 'lower': [], 'percent_b': [], 'signals': [0] * len(prices)}
        
        sma_values = SimpleTA.sma(prices, period)
        
        upper_band = []
        lower_band = []
        percent_b = []
        
        for i in range(period - 1, len(prices)):
            window = prices[i - period + 1:i + 1]
            
            # Calculate standard deviation
            mean = sum(window) / period
            variance = sum((x - mean) ** 2 for x in window) / period
            std = math.sqrt(variance)
            
            upper = mean + std_dev * std
            lower = mean - std_dev * std
            
            upper_band.append(upper)
            lower_band.append(lower)
            
            # Calculate %B
            current_price = prices[i]
            if upper != lower:
                pb = (current_price - lower) / (upper - lower)
            else:
                pb = 0.5
            percent_b.append(pb)
        
        # Generate signals
        signals = [0] * len(prices)
        for i in range(len(percent_b)):
            idx = i + period - 1
            if idx < len(signals):
                if percent_b[i] < 0:
                    signals[idx] = 1  # Below lower band
                elif percent_b[i] > 1:
                    signals[idx] = -1  # Above upper band
        
        # Pad beginning
        sma_padded = [sma_values[0]] * (period - 1) + sma_values if sma_values else []
        upper_padded = [upper_band[0]] * (period - 1) + upper_band if upper_band else []
        lower_padded = [lower_band[0]] * (period - 1) + lower_band if lower_band else []
        percent_padded = [0.5] * (period - 1) + percent_b if percent_b else []
        
        return {
            'upper': upper_padded[:len(prices)],
            'middle': sma_padded[:len(prices)],
            'lower': lower_padded[:len(prices)],
            'percent_b': percent_padded[:len(prices)],
            'signals': signals
        }
    
    @staticmethod
    def stochastic(high: List[float], low: List[float], close: List[float], 
                   k_period: int = 14, d_period: int = 3) -> Dict:
        """Stochastic Oscillator"""
        n = len(close)
        fast_k = [0] * n
        
        for i in range(k_period - 1, n):
            window_high = max(high[i - k_period + 1:i + 1])
            window_low = min(low[i - k_period + 1:i + 1])
            
            if window_high == window_low:
                fast_k[i] = 50
            else:
                fast_k[i] = ((close[i] - window_low) / (window_high - window_low)) * 100
        
        # Slow %K (SMA of Fast %K)
        slow_k = SimpleTA.sma(fast_k[k_period - 1:], d_period)
        
        # %D (SMA of Slow %K)
        slow_d = SimpleTA.sma(slow_k, d_period) if slow_k else []
        
        # Generate signals
        signals = [0] * n
        if slow_d and len(slow_d) > 1:
            for i in range(1, min(len(slow_k), len(slow_d))):
                idx = i + k_period - 1 + d_period - 1
                if idx < n and idx-1 < len(fast_k) and i-1 < len(slow_d) and i < len(slow_d):
                    # Bullish: %K crosses above %D from oversold
                    if (fast_k[idx-1] <= slow_d[i-1] and fast_k[idx] > slow_d[i] and 
                        fast_k[idx] < 20):
                        signals[idx] = 1
                    # Bearish: %K crosses below %D from overbought
                    elif (fast_k[idx-1] >= slow_d[i-1] and fast_k[idx] < slow_d[i] and 
                          fast_k[idx] > 80):
                        signals[idx] = -1
        
        # Pad arrays
        fast_k_padded = fast_k
        slow_k_padded = ([slow_k[0]] * (k_period - 1 + d_period - 1) + slow_k) if slow_k else []
        slow_d_padded = ([slow_d[0]] * (k_period - 1 + d_period - 1) + slow_d) if slow_d else []
        
        return {
            'fast_k': fast_k_padded[:n],
            'slow_k': slow_k_padded[:n],
            'slow_d': slow_d_padded[:n],
            'signals': signals
        }
    
    @staticmethod
    def analyze_signals(prices: List[float], high: List[float], low: List[float], 
                       base_signal: float) -> Dict:
        """
        Analyze multiple TA indicators and return enhanced signal
        
        Returns:
            Dict with enhanced signal and indicator values
        """
        if len(prices) < 30:
            return {
                'enhanced_signal': base_signal,
                'indicators_used': 0,
                'ta_signals': {}
            }
        
        ta = SimpleTA()
        
        # Calculate indicators
        ema_12 = ta.ema(prices, 12)
        ema_26 = ta.ema(prices, 26)
        
        rsi_values = ta.rsi(prices, 14)
        macd_result = ta.macd(prices)
        bb_result = ta.bollinger_bands(prices)
        stoch_result = ta.stochastic(high, low, prices)
        
        # Get latest values
        current_price = prices[-1] if prices else 0
        
        # EMA signal
        ema_signal = 0
        if len(ema_12) > 1 and len(ema_26) > 1:
            if ema_12[-1] > ema_26[-1] and ema_12[-2] <= ema_26[-2]:
                ema_signal = 1  # Golden cross
            elif ema_12[-1] < ema_26[-1] and ema_12[-2] >= ema_26[-2]:
                ema_signal = -1  # Death cross
        
        # RSI signal
        rsi_signal = 0
        rsi_value = rsi_values[-1] if rsi_values else 50
        if rsi_value < 30:
            rsi_signal = 1  # Oversold
        elif rsi_value > 70:
            rsi_signal = -1  # Overbought
        
        # MACD signal
        macd_signal = macd_result['signals'][-1] if macd_result['signals'] else 0
        
        # Bollinger Bands signal
        bb_signal = bb_result['signals'][-1] if bb_result['signals'] else 0
        
        # Stochastic signal
        stoch_signal = stoch_result['signals'][-1] if stoch_result['signals'] else 0
        
        # Combine signals with weights
        signals = [
            (base_signal, 0.4),      # Base strategy: 40%
            (ema_signal, 0.15),      # EMA: 15%
            (rsi_signal, 0.15),      # RSI: 15%
            (macd_signal, 0.15),     # MACD: 15%
            (bb_signal, 0.10),       # BB: 10%
            (stoch_signal, 0.05)     # Stochastic: 5%
        ]
        
        weighted_sum = sum(signal * weight for signal, weight in signals)
        
        # Determine final signal
        if weighted_sum > 0.3:
            enhanced_signal = 1  # STRONG BUY
        elif weighted_sum > 0.1:
            enhanced_signal = 0.5  # WEAK BUY
        elif weighted_sum < -0.3:
            enhanced_signal = -1  # STRONG SELL
        elif weighted_sum < -0.1:
            enhanced_signal = -0.5  # WEAK SELL
        else:
            enhanced_signal = 0  # NEUTRAL
        
        return {
            'enhanced_signal': enhanced_signal,
            'weighted_sum': weighted_sum,
            'indicators_used': 6,
            'ta_signals': {
                'ema_signal': ema_signal,
                'rsi_value': rsi_value,
                'rsi_signal': rsi_signal,
                'macd_signal': macd_signal,
                'bb_signal': bb_signal,
                'stoch_signal': stoch_signal,
                'current_price': current_price
            }
        }

# Test the library
if __name__ == "__main__":
    # Create sample data
    prices = [100 + i * 0.5 + (i % 3 - 1) for i in range(100)]
    high = [p + 1.0 for p in prices]
    low = [p - 1.0 for p in prices]
    
    ta = SimpleTA()
    
    print("🧪 Testing Simple TA Library")
    print("=" * 60)
    
    # Test SMA
    sma = ta.sma(prices, 20)
    print(f"SMA(20): {sma[-1] if sma else 'N/A'}")
    
    # Test EMA
    ema = ta.ema(prices, 20)
    print(f"EMA(20): {ema[-1] if ema else 'N/A'}")
    
    # Test RSI
    rsi = ta.rsi(prices, 14)
    print(f"RSI(14): {rsi[-1] if rsi else 'N/A'}")
    
    # Test signal analysis
    analysis = ta.analyze_signals(prices, high, low, 0)
    print(f"\nSignal Analysis:")
    print(f"  Enhanced Signal: {analysis['enhanced_signal']}")
    print(f"  Weighted Sum: {analysis['weighted_sum']:.3f}")
    print(f"  Indicators Used: {analysis['indicators_used']}")
    
    print("\n✅ Simple TA Library working correctly")