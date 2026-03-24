#!/usr/bin/env python3
"""
KingK Strategy Auto-Researcher
Autonomously generates, backtests, and optimizes trading strategy parameters.
Uses Gemini Flash Lite for lightweight parameter mutations (saves costs),
Groq for deep synthesis when needed.

Usage:
  python3 agents/strategy_researcher.py --baseline ema_swing --cycles 10
  python3 agents/strategy_researcher.py --baseline macd_rsi --cycles 5 --symbol SUIUSDT
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

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent

# Try to load dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RESEARCH_DIR = BASE_DIR / "research"
BACKTEST_DIR = RESEARCH_DIR / "backtests"
STRATEGIES_DIR = BASE_DIR / "strategies"
BACKTEST_DIR.mkdir(parents=True, exist_ok=True)

# Available baseline strategies (actual files in strategies/)
AVAILABLE_STRATEGIES = {
    "ema_swing": {
        "name": "EMA Swing v1",
        "parameters": {
            "rsi_min": 45, "rsi_max": 65, "vol_mult": 1.2,
            "tp": 0.06, "sl": 0.03,
        },
        "description": "EMA 9/21 crossover + RSI + volume filter",
    },
    "macd_rsi": {
        "name": "MACD + RSI",
        "parameters": {
            "macd_fast": 12, "macd_slow": 26, "macd_signal_period": 9,
            "rsi_max": 70, "tp": 0.06, "sl": 0.03,
        },
        "description": "MACD histogram crossover + RSI overbought filter",
    },
    "bollinger_mean_reversion": {
        "name": "Bollinger Mean Reversion",
        "parameters": {
            "bb_period": 20, "bb_std": 2.0, "vol_mult": 1.2,
            "tp": 0.05, "sl": 0.025,
        },
        "description": "Price touches lower BB + volume confirmation, exit at middle band",
    },
    "rsi_divergence_breakout": {
        "name": "RSI Divergence Breakout",
        "parameters": {
            "rsi_oversold": 35, "rsi_overbought": 65, "vol_mult": 1.8,
            "ema_period": 50, "ema_proximity": 0.10, "tp": 0.06, "sl": 0.03,
        },
        "description": "RSI oversold bounce + volume surge + price near EMA50",
    },
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{ts}] {msg}", flush=True)


def mutate_strategy_with_gemini(baseline_strategy: dict, variation_number: int) -> Optional[dict]:
    """Use Gemini to generate a parameter mutation."""
    try:
        import google.generativeai as genai
        if not GEMINI_API_KEY:
            log("  ⚠ No GEMINI_API_KEY — using random mutation fallback")
            return random_mutation(baseline_strategy, variation_number)

        genai.configure(api_key=GEMINI_API_KEY)
        log(f"🧬 Gemini mutation #{variation_number}...")

        model = genai.GenerativeModel("gemini-2.0-flash-lite")
        prompt = f"""You are a quantitative trading strategist. Mutate ONE parameter slightly.

BASELINE STRATEGY:
{json.dumps(baseline_strategy, indent=2)}

MUTATION #: {variation_number}

Pick ONE numeric parameter and tweak it by 10-20%. Keep all other parameters unchanged.
Return ONLY valid JSON (no markdown):

{{
  "name": "Strategy name with variation #{variation_number}",
  "parameters": {{ ... }},
  "rationale": "One line explaining the mutation"
}}"""

        response = model.generate_content(prompt)
        raw = response.text.strip()

        # Strip markdown code fences if present
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        mutated = json.loads(raw)
        mutated["generation"] = variation_number
        mutated["source"] = "gemini"
        log(f"  ✓ Mutation: {mutated.get('rationale', 'N/A')}")
        return mutated

    except Exception as e:
        log(f"  ✗ Gemini error: {e} — falling back to random mutation")
        return random_mutation(baseline_strategy, variation_number)


def random_mutation(baseline_strategy: dict, variation_number: int) -> dict:
    """Fallback: randomly tweak one numeric parameter by ±15%."""
    import random
    params = dict(baseline_strategy.get("parameters", {}))
    if not params:
        return None

    key = random.choice(list(params.keys()))
    old_val = params[key]
    factor = random.uniform(0.85, 1.15)
    new_val = round(old_val * factor, 4)
    params[key] = new_val

    return {
        "name": f"{baseline_strategy.get('name', 'Unknown')} v{variation_number}",
        "parameters": params,
        "rationale": f"Random mutation: {key} {old_val} → {new_val}",
        "generation": variation_number,
        "source": "random",
    }


def backtest_strategy(strategy_name: str, parameters: dict,
                      symbol: str = "XRPUSDT", interval: str = "240") -> dict:
    """Run backtest via backtest.py CLI, parse JSON output."""
    log(f"  📊 Backtesting {strategy_name} on {symbol} {interval}...")

    tp = parameters.get("tp", 0.06)
    sl = parameters.get("sl", 0.03)

    try:
        cmd = [
            sys.executable,
            str(BASE_DIR / "backtests" / "backtest.py"),
            f"--symbol={symbol}",
            f"--interval={interval}",
            f"--strategy={strategy_name}",
            f"--tp={tp}",
            f"--sl={sl}",
            "--json-output",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and result.stdout.strip():
            # Find the JSON line (might have other output mixed in)
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        data = json.loads(line)
                        log(f"    Sharpe: {data.get('sharpe_ratio', '?'):.3f} | "
                            f"Win%: {data.get('win_rate', 0)*100:.1f}% | "
                            f"P&L: ${data.get('total_pnl_usd', 0):.2f}")
                        return data
                    except json.JSONDecodeError:
                        continue
            return {"error": "No valid JSON in output", "raw": result.stdout[:500]}
        else:
            log(f"    ✗ Backtest failed (rc={result.returncode}): {result.stderr[:200]}")
            return {"error": "Backtest subprocess failed", "stderr": result.stderr[:300]}

    except subprocess.TimeoutExpired:
        return {"error": "Backtest timeout"}
    except Exception as e:
        return {"error": str(e)}


def check_lookahead_bias(backtest_result: dict, threshold: float = 3.0) -> bool:
    """Heuristic: Sharpe > 3.0 is suspiciously high — flag for review."""
    sharpe = backtest_result.get("sharpe_ratio", 0)
    if sharpe and sharpe > threshold:
        log(f"    ⚠️  Possible lookahead bias (Sharpe={sharpe:.2f} > {threshold})")
        return True
    return False


def save_generation(generation_number: int, strategy_name: str,
                    strategy: dict, backtest_result: dict,
                    is_best: bool = False) -> dict:
    """Save generation record to research/backtests/."""
    record = {
        "generation": generation_number,
        "timestamp": datetime.utcnow().isoformat(),
        "strategy_module": strategy_name,
        "strategy": strategy,
        "backtest": backtest_result,
        "is_best": is_best,
        "lookahead_bias_flag": check_lookahead_bias(backtest_result),
    }

    safe_name = strategy_name.replace("/", "_")
    gen_file = BACKTEST_DIR / f"gen_{safe_name}_{generation_number:04d}.json"
    with open(gen_file, "w") as f:
        json.dump(record, f, indent=2, default=str)

    return record


def compare_strategies(current_best: dict, candidate: dict) -> bool:
    """Returns True if candidate is better than current_best (by Sharpe ratio)."""
    current_sharpe  = current_best.get("backtest", {}).get("sharpe_ratio", -999) or -999
    candidate_sharpe = candidate.get("backtest", {}).get("sharpe_ratio", -999) or -999

    if candidate.get("lookahead_bias_flag", False):
        log(f"    ❌ Skipped (lookahead bias flagged)")
        return False

    if "error" in candidate.get("backtest", {}):
        log(f"    ❌ Skipped (backtest error)")
        return False

    if candidate_sharpe > current_sharpe:
        log(f"    ✅ NEW BEST! Sharpe {candidate_sharpe:.3f} > {current_sharpe:.3f}")
        return True
    else:
        log(f"    ↗️  Not better ({candidate_sharpe:.3f} ≤ {current_sharpe:.3f})")
        return False


def run_research_loop(strategy_name: str, num_cycles: int = 10,
                      symbol: str = "XRPUSDT", interval: str = "240"):
    """Main research loop: baseline → mutate → backtest → keep winners."""
    if strategy_name not in AVAILABLE_STRATEGIES:
        log(f"❌ Unknown strategy: {strategy_name}. Available: {list(AVAILABLE_STRATEGIES.keys())}")
        return None

    baseline_info = AVAILABLE_STRATEGIES[strategy_name]
    log(f"🚀 Research loop: {strategy_name} | {num_cycles} cycles | {symbol} {interval}")
    log(f"   Baseline: {baseline_info['description']}")

    # First, backtest the baseline
    log(f"\n📍 BASELINE")
    baseline_result = backtest_strategy(strategy_name, baseline_info["parameters"], symbol, interval)
    baseline_record = save_generation(0, strategy_name, {
        "name": baseline_info["name"],
        "parameters": baseline_info["parameters"],
        "rationale": "Baseline strategy",
        "generation": 0,
        "source": "baseline",
    }, baseline_result, is_best=True)

    current_best = baseline_record

    for cycle in range(1, num_cycles + 1):
        log(f"\n📍 GENERATION {cycle}/{num_cycles}")

        # Generate mutation using current best params
        best_params = current_best.get("strategy", {}).get("parameters",
                      baseline_info["parameters"])
        mutation_base = {
            "name": baseline_info["name"],
            "parameters": dict(best_params),
        }

        mutated = mutate_strategy_with_gemini(mutation_base, cycle)
        if not mutated:
            log("  Skipping (mutation failed)")
            continue

        # Backtest the mutation
        backtest = backtest_strategy(strategy_name, mutated.get("parameters", {}),
                                     symbol, interval)
        if "error" in backtest:
            log(f"  Backtest error: {backtest['error']}")
            continue

        record = save_generation(cycle, strategy_name, mutated, backtest)

        if compare_strategies(current_best, record):
            current_best = record
            # Mark as best
            current_best["is_best"] = True

        log(f"  Current best: Gen {current_best['generation']} "
            f"(Sharpe {current_best['backtest'].get('sharpe_ratio', '?')})")

        time.sleep(1)  # Be kind to APIs

    # Final summary
    log(f"\n{'='*60}")
    log(f"🏆 RESEARCH COMPLETE — {strategy_name}")
    if current_best:
        bt = current_best["backtest"]
        log(f"  Best generation: {current_best['generation']}")
        log(f"  Sharpe ratio:    {bt.get('sharpe_ratio', '?')}")
        log(f"  Win rate:        {bt.get('win_rate', 0)*100:.1f}%")
        log(f"  Total P&L:       ${bt.get('total_pnl_usd', 0):.2f}")
        log(f"  Max drawdown:    {bt.get('max_drawdown', 0)*100:.1f}%")
        log(f"  Parameters:      {current_best['strategy'].get('parameters', {})}")
    log(f"{'='*60}")

    return current_best


def list_generations():
    """List all saved strategy generations."""
    records = []
    for gen_file in sorted(BACKTEST_DIR.glob("gen_*.json")):
        try:
            with open(gen_file) as f:
                records.append(json.load(f))
        except Exception:
            pass

    if not records:
        print("No generations yet.")
        print("Run: python3 agents/strategy_researcher.py --baseline ema_swing --cycles 10")
        return

    print(f"\n📚 Strategy Generations ({len(records)} total):")
    print(f"  {'Gen':>4} | {'Strategy':<30} | {'Sharpe':>8} | {'WinRate':>8} | {'P&L':>8} | Bias")
    print(f"  {'-'*4}-+-{'-'*30}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+------")
    for r in records:
        gen     = r.get("generation", "?")
        strat   = r.get("strategy_module", "?")[:30]
        bt      = r.get("backtest", {})
        sharpe  = bt.get("sharpe_ratio", 0) or 0
        wr      = bt.get("win_rate", 0) or 0
        pnl     = bt.get("total_pnl_usd", 0) or 0
        best    = "🏆" if r.get("is_best") else "  "
        bias    = "⚠️" if r.get("lookahead_bias_flag") else "✓"
        print(f"  {best}{gen:>4} | {strat:<30} | {sharpe:>8.3f} | {wr*100:>7.1f}% | ${pnl:>7.2f} | {bias}")


def main():
    parser = argparse.ArgumentParser(description="KingK Strategy Auto-Researcher")
    parser.add_argument("--baseline", "-b", type=str,
                        help=f"Baseline strategy. Choices: {list(AVAILABLE_STRATEGIES.keys())}")
    parser.add_argument("--strategy", type=str,
                        help="Alias for --baseline (strategy module name)")
    parser.add_argument("--cycles",   "-c", type=int, default=10, help="Number of mutation cycles")
    parser.add_argument("--symbol",   "-s", type=str, default="XRPUSDT", help="Symbol e.g. XRPUSDT")
    parser.add_argument("--interval", "-i", type=str, default="240", help="Candle interval: 60, 240")
    parser.add_argument("--list",     "-l", action="store_true", help="List all generations")
    args = parser.parse_args()

    if args.list:
        list_generations()
        return

    # Support both --baseline and --strategy (alias)
    strategy_arg = args.baseline or args.strategy
    if not strategy_arg:
        parser.print_help()
        print(f"\nAvailable strategies: {list(AVAILABLE_STRATEGIES.keys())}")
        return

    run_research_loop(
        strategy_name=strategy_arg,
        num_cycles=args.cycles,
        symbol=args.symbol,
        interval=args.interval,
    )


if __name__ == "__main__":
    main()
