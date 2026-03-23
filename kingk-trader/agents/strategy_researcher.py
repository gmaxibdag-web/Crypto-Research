#!/usr/bin/env python3
"""
KingK Strategy Auto-Researcher
Autonomously generates, backtests, and optimizes trading strategy parameters.
Uses Gemini Flash Lite for lightweight parameter mutations (saves costs),
Groq for deep synthesis when needed.

Usage:
  python3 agents/strategy_researcher.py --baseline xrp_rsi_vol --cycles 10
  python3 agents/strategy_researcher.py --list    # show all strategy generations
"""

import os
import sys
import json
import time
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
import google.generativeai as genai
from groq import Groq
from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RESEARCH_DIR = BASE_DIR / "research"
STRATEGIES_DIR = RESEARCH_DIR / "strategies"
BACKTEST_DIR = RESEARCH_DIR / "backtests"
STRATEGIES_DIR.mkdir(exist_ok=True)
BACKTEST_DIR.mkdir(exist_ok=True)

# Models
GEMINI_MODEL = "gemini-2.0-flash-lite-preview"  # Latest — fast, cheap — for parameter mutations
GROQ_MODEL = "llama-3.3-70b-versatile"  # Deep reasoning — for strategy synthesis

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{ts}] {msg}", flush=True)


def mutate_strategy_with_gemini(
    baseline_strategy: dict,
    variation_number: int,
    market_context: str = ""
) -> dict:
    """Use Gemini Flash Lite to generate a parameter mutation quickly & cheaply."""
    log(f"🧬 Gemini mutation #{variation_number}...")
    
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        
        prompt = f"""You are a quantitative trading strategist. Your job is to mutate strategy parameters.

BASELINE STRATEGY:
{json.dumps(baseline_strategy, indent=2)}

MUTATION #: {variation_number}

Generate a SINGLE parameter mutation (not a complete rewrite). 
Pick ONE parameter and tweak it slightly. Examples:
- If RSI_THRESHOLD is 30, change to 28 or 32
- If EMA_FAST is 12, change to 10 or 14
- If VOLUME_MULTIPLIER is 1.5, change to 1.3 or 1.7

Return ONLY valid JSON with the mutated strategy. No explanation.

{{
  "name": "Strategy name with variation",
  "parameters": {{ /* mutated parameters */ }},
  "rationale": "One line explaining the mutation"
}}"""

        response = model.generate_content(prompt)
        raw = response.text.strip()
        
        # Extract JSON
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        
        mutated = json.loads(raw)
        mutated["generation"] = variation_number
        mutated["source"] = "gemini_flash_lite"
        log(f"  ✓ Mutation: {mutated.get('rationale', 'N/A')}")
        return mutated
        
    except Exception as e:
        log(f"  ✗ Gemini error: {e}")
        return None


def backtest_strategy(strategy: dict, symbol: str = "XRPUSDT", timeframe: str = "4h") -> dict:
    """Run backtest via backtester. Returns sharpe_ratio, win_rate, max_drawdown, etc."""
    log(f"  📊 Backtesting {strategy.get('name', 'Unknown')}...")
    
    try:
        # Call the backtester with the strategy
        result = subprocess.run(
            [
                "python3",
                str(BASE_DIR / "backtests" / "backtest.py"),
                f"--symbol={symbol}",
                f"--timeframe={timeframe}",
                f"--strategy-json={json.dumps(strategy['parameters'])}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode == 0:
            try:
                backtest_result = json.loads(result.stdout)
                log(f"    Sharpe: {backtest_result.get('sharpe_ratio', '?'):.2f} | Win%: {backtest_result.get('win_rate', 0)*100:.1f}%")
                return backtest_result
            except:
                return {"error": "Failed to parse backtest output", "raw": result.stdout}
        else:
            log(f"    ✗ Backtest failed: {result.stderr}")
            return {"error": "Backtest subprocess failed", "stderr": result.stderr}
    
    except subprocess.TimeoutExpired:
        return {"error": "Backtest timeout"}
    except Exception as e:
        return {"error": str(e)}


def check_lookahead_bias(backtest_result: dict, threshold: float = 1.5) -> bool:
    """Simple heuristic: if Sharpe > 3.0, likely lookahead bias. Flag it."""
    sharpe = backtest_result.get("sharpe_ratio", 0)
    if sharpe > 3.0:
        log(f"    ⚠️  Possible lookahead bias (Sharpe > 3.0)")
        return True
    return False


def save_generation(
    generation_number: int,
    strategy: dict,
    backtest_result: dict,
    is_best: bool = False
):
    """Save generation record."""
    record = {
        "generation": generation_number,
        "timestamp": datetime.utcnow().isoformat(),
        "strategy": strategy,
        "backtest": backtest_result,
        "is_best": is_best,
        "lookahead_bias_flag": check_lookahead_bias(backtest_result),
    }
    
    gen_file = BACKTEST_DIR / f"gen_{generation_number:04d}.json"
    with open(gen_file, "w") as f:
        json.dump(record, f, indent=2)
    
    return record


def compare_strategies(current_best: dict, candidate: dict) -> bool:
    """Returns True if candidate is better than current_best.
    Uses Sharpe ratio as primary metric, win_rate as secondary."""
    
    current_sharpe = current_best.get("backtest", {}).get("sharpe_ratio", -999)
    candidate_sharpe = candidate.get("backtest", {}).get("sharpe_ratio", -999)
    
    # Skip if candidate has lookahead bias
    if candidate.get("lookahead_bias_flag", False):
        log(f"    ❌ Skipped (lookahead bias detected)")
        return False
    
    if candidate_sharpe > current_sharpe:
        log(f"    ✅ NEW BEST! Sharpe {candidate_sharpe:.2f} > {current_sharpe:.2f}")
        return True
    else:
        log(f"    ↗️  Not better ({candidate_sharpe:.2f} ≤ {current_sharpe:.2f})")
        return False


def load_best_strategy() -> Optional[dict]:
    """Load the current best strategy from all generations."""
    records = []
    for gen_file in sorted(BACKTEST_DIR.glob("gen_*.json")):
        try:
            with open(gen_file) as f:
                records.append(json.load(f))
        except:
            pass
    
    if not records:
        return None
    
    # Filter out lookahead bias, sort by Sharpe
    valid = [r for r in records if not r.get("lookahead_bias_flag", False)]
    if not valid:
        valid = records
    
    best = max(valid, key=lambda r: r.get("backtest", {}).get("sharpe_ratio", -999))
    return best


def run_research_loop(baseline_strategy: dict, num_cycles: int = 10, symbol: str = "XRPUSDT"):
    """Main research loop: mutate → backtest → keep winners."""
    log(f"🚀 Starting strategy research loop: {num_cycles} cycles on {symbol}")
    
    current_best = None
    generation = 0
    
    for cycle in range(num_cycles):
        generation += 1
        log(f"\n📍 GENERATION {generation}/{num_cycles}")
        
        # Generate mutation
        mutated = mutate_strategy_with_gemini(baseline_strategy, generation)
        if not mutated:
            log("  Skipping this generation (mutation failed)")
            continue
        
        # Backtest
        backtest = backtest_strategy(mutated, symbol=symbol)
        if "error" in backtest:
            log(f"  Backtest error: {backtest['error']}")
            continue
        
        # Save record
        record = save_generation(generation, mutated, backtest)
        
        # Decide: keep or discard?
        if current_best is None:
            log(f"  ✅ FIRST STRATEGY LOCKED IN")
            current_best = record
        else:
            if compare_strategies(current_best, record):
                current_best = record
        
        log(f"  Current best: Gen {current_best['generation']} (Sharpe {current_best['backtest'].get('sharpe_ratio', '?')})")
        
        # Be nice to APIs
        time.sleep(2)
    
    # Final summary
    log(f"\n{'='*60}")
    log(f"🏆 RESEARCH COMPLETE")
    if current_best:
        log(f"  Best generation: {current_best['generation']}")
        log(f"  Sharpe ratio: {current_best['backtest'].get('sharpe_ratio', '?'):.2f}")
        log(f"  Win rate: {current_best['backtest'].get('win_rate', 0)*100:.1f}%")
        log(f"  Max drawdown: {current_best['backtest'].get('max_drawdown', '?'):.2%}")
    log(f"{'='*60}")
    
    return current_best


def list_generations():
    """List all strategy generations."""
    records = []
    for gen_file in sorted(BACKTEST_DIR.glob("gen_*.json")):
        try:
            with open(gen_file) as f:
                records.append(json.load(f))
        except:
            pass
    
    if not records:
        print("No generations yet. Run: python3 agents/strategy_researcher.py --baseline <name> --cycles 10")
        return
    
    print(f"\n📚 Strategy Generations ({len(records)} total):")
    for r in records:
        gen = r['generation']
        sharpe = r['backtest'].get('sharpe_ratio', '?')
        best = "🏆" if r['is_best'] else "  "
        bias = "⚠️ " if r['lookahead_bias_flag'] else "✓ "
        print(f"  {best} Gen {gen:3d} | Sharpe {sharpe:6.2f} | {bias}")


def main():
    parser = argparse.ArgumentParser(description="KingK Strategy Auto-Researcher")
    parser.add_argument("--baseline", "-b", type=str, help="Baseline strategy name/ID")
    parser.add_argument("--cycles", "-c", type=int, default=10, help="Number of research cycles")
    parser.add_argument("--symbol", "-s", type=str, default="XRPUSDT", help="Trading symbol")
    parser.add_argument("--list", "-l", action="store_true", help="List all generations")
    args = parser.parse_args()
    
    if args.list:
        list_generations()
        return
    
    if not args.baseline:
        parser.print_help()
        return
    
    # Load baseline strategy (stub — would load from config)
    baseline_strategy = {
        "name": args.baseline,
        "parameters": {
            "rsi_threshold": 30,
            "ema_fast": 12,
            "ema_slow": 50,
            "volume_multiplier": 1.5,
        }
    }
    
    # Run research loop
    best = run_research_loop(baseline_strategy, num_cycles=args.cycles, symbol=args.symbol)


if __name__ == "__main__":
    main()
