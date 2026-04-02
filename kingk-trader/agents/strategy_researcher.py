#!/usr/bin/env python3
"""
KingK Strategy Auto-Researcher
Autonomously generates, backtests, and optimizes trading strategy parameters.
Uses a smart fallback chain: Groq → DeepSeek → Gemini → Haiku → Random
with comprehensive quota tracking for each model.

Usage:
  python3 agents/strategy_researcher.py --baseline ema_swing --cycles 10
  python3 agents/strategy_researcher.py --strategy funding_rate_divergence --symbol XRPUSDT --cycles 5
  python3 agents/strategy_researcher.py --list    # show all strategy generations
"""

import os
import sys
import json
import time
import random
import argparse
import subprocess
import requests
from datetime import datetime, timezone, timedelta
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

GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

RESEARCH_DIR  = BASE_DIR / "research"
BACKTEST_DIR  = RESEARCH_DIR / "backtests"
STRATEGIES_DIR = BASE_DIR / "strategies"
DATA_DIR      = BASE_DIR / "data"
QUOTA_STATE_FILE = DATA_DIR / "model_quota_state.json"

BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Default quota state ───────────────────────────────────────────────────────
DEFAULT_QUOTA_STATE = {
    "last_checked_at": datetime.now(timezone.utc).isoformat(),
    "models": {
        "groq": {
            "remaining_requests": 5000,
            "limit_tokens_per_min": 0,
            "available": True,
            "last_check": datetime.now(timezone.utc).isoformat(),
            "quota_exhausted_at": None,
        },
        "deepseek": {
            "remaining_requests": 50,
            "limit_tokens_per_min": 60000,
            "available": True,
            "last_check": datetime.now(timezone.utc).isoformat(),
        },
        "gemini": {
            "free_tier_limit_queries_per_min": 15,
            "free_tier_limit_queries_per_day": 1500,
            "queries_today": 0,
            "queries_this_minute": 0,
            "last_check": datetime.now(timezone.utc).isoformat(),
            "last_minute_reset": datetime.now(timezone.utc).isoformat(),
            "last_day_reset": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "available": True,
        },
        "haiku": {
            "available": True,
            "note": "Anthropic provides generous limits, track conservatively",
        },
    }
}

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
    "funding_rate_divergence": {
        "name": "Funding Rate Divergence",
        "parameters": {
            "funding_threshold": 0.0003, "rsi_min": 40, "rsi_max": 60,
            "vol_mult": 1.5, "tp": 0.04, "sl": 0.02,
        },
        "description": "Trade when funding rate diverges from price action",
    },
    "liquidation_cascade": {
        "name": "Liquidation Cascade",
        "parameters": {
            "cluster_pct_threshold": 0.90,
            "funding_threshold": -0.00005,
            "tp": 0.06,
            "sl": 0.03,
        },
        "description": "Liquidation cascade + negative funding = reversal signal (4h XRP baseline Sharpe 0.496)",
    },
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg):
    ts = datetime.utcnow().strftime("%H:%M")
    print(f"[{ts}] {msg}", flush=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── Quota State Management ────────────────────────────────────────────────────

def load_quota_state() -> dict:
    """Load quota state from JSON file. Returns default state if file missing."""
    try:
        if QUOTA_STATE_FILE.exists():
            with open(QUOTA_STATE_FILE) as f:
                state = json.load(f)
            # Ensure all model keys exist (merge with defaults)
            for model, defaults in DEFAULT_QUOTA_STATE["models"].items():
                if model not in state["models"]:
                    state["models"][model] = dict(defaults)
            return state
    except Exception as e:
        log(f"  ⚠ Could not load quota state: {e} — using defaults")
    return dict(DEFAULT_QUOTA_STATE)


def save_quota_state(state: dict) -> None:
    """Write quota state back to JSON file with updated timestamp."""
    try:
        state["last_checked_at"] = now_iso()
        with open(QUOTA_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2, default=str)
    except Exception as e:
        log(f"  ⚠ Could not save quota state: {e}")


def should_use_model(model_name: str, quota_state: dict) -> bool:
    """
    Check if model quota is available.
    Returns False if exhausted or in cooldown.
    Handles Gemini minute/day reset logic.
    """
    # 'random' is always available
    if model_name == "random":
        return True

    models = quota_state.get("models", {})
    if model_name not in models:
        return True  # Unknown model — assume available

    m = models[model_name]

    # Basic availability flag
    if not m.get("available", True):
        # Check if cooldown period has passed (1 hour after exhaustion)
        exhausted_at = m.get("quota_exhausted_at")
        if exhausted_at:
            try:
                exhausted_dt = datetime.fromisoformat(exhausted_at.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - exhausted_dt > timedelta(hours=1):
                    # Reset availability
                    m["available"] = True
                    m["quota_exhausted_at"] = None
                    save_quota_state(quota_state)
                    log(f"  ↺ {model_name} cooldown expired — re-enabling")
                    return True
            except Exception:
                pass
        return False

    # Gemini-specific: check minute/day limits
    if model_name == "gemini":
        today = now_date()
        last_day_reset = m.get("last_day_reset", "")
        if last_day_reset != today:
            m["queries_today"] = 0
            m["last_day_reset"] = today

        # Check minute reset (sliding window)
        last_min_reset = m.get("last_minute_reset", now_iso())
        try:
            reset_dt = datetime.fromisoformat(last_min_reset.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - reset_dt > timedelta(minutes=1):
                m["queries_this_minute"] = 0
                m["last_minute_reset"] = now_iso()
        except Exception:
            m["queries_this_minute"] = 0
            m["last_minute_reset"] = now_iso()

        daily_limit = m.get("free_tier_limit_queries_per_day", 1500)
        min_limit   = m.get("free_tier_limit_queries_per_min", 15)

        if m.get("queries_today", 0) >= daily_limit:
            log(f"  ⊘ gemini daily quota exhausted ({m['queries_today']}/{daily_limit})")
            return False
        if m.get("queries_this_minute", 0) >= min_limit:
            log(f"  ⊘ gemini rate limited this minute ({m['queries_this_minute']}/{min_limit})")
            return False

    # Groq/DeepSeek: check remaining requests
    if model_name in ("groq", "deepseek"):
        remaining = m.get("remaining_requests", 1)
        if remaining is not None and remaining <= 0:
            return False

    return True


def mark_model_quota_exhausted(model_name: str, quota_state: dict) -> None:
    """Mark a model as quota-exhausted and persist state."""
    models = quota_state.get("models", {})
    if model_name in models:
        models[model_name]["available"] = False
        models[model_name]["quota_exhausted_at"] = now_iso()
        models[model_name]["last_check"] = now_iso()
        save_quota_state(quota_state)


def update_quota_after_success(model_name: str, quota_state: dict,
                                response_headers: dict = None) -> None:
    """Update quota state after a successful model call."""
    models = quota_state.get("models", {})
    if model_name not in models:
        return

    m = models[model_name]
    m["last_check"] = now_iso()

    if model_name == "groq" and response_headers:
        remaining = response_headers.get("x-ratelimit-remaining-requests")
        if remaining is not None:
            try:
                m["remaining_requests"] = int(remaining)
            except (ValueError, TypeError):
                pass
        # Decrement if no header
        elif m.get("remaining_requests") is not None and m["remaining_requests"] > 0:
            m["remaining_requests"] -= 1

    elif model_name == "deepseek" and response_headers:
        remaining = response_headers.get("x-ratelimit-remaining-requests")
        tokens_limit = response_headers.get("x-ratelimit-limit-tokens")
        if remaining is not None:
            try:
                m["remaining_requests"] = int(remaining)
            except (ValueError, TypeError):
                pass
        elif m.get("remaining_requests") is not None and m["remaining_requests"] > 0:
            m["remaining_requests"] -= 1
        if tokens_limit is not None:
            try:
                m["limit_tokens_per_min"] = int(tokens_limit)
            except (ValueError, TypeError):
                pass

    elif model_name == "gemini":
        m["queries_today"] = m.get("queries_today", 0) + 1
        m["queries_this_minute"] = m.get("queries_this_minute", 0) + 1

    elif model_name == "haiku":
        # Conservative tracking only
        pass

    save_quota_state(quota_state)


# ── Quota Check Functions ─────────────────────────────────────────────────────

def check_groq_quota() -> dict:
    """
    Query Groq API for remaining quota.
    Returns {"remaining": int, "available": bool, "error": str or None}
    Falls back gracefully if unavailable.
    """
    if not GROQ_API_KEY:
        return {"remaining": None, "available": False, "error": "No GROQ_API_KEY"}
    try:
        resp = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            timeout=5,
        )
        if resp.status_code == 200:
            remaining = resp.headers.get("x-ratelimit-remaining-requests")
            return {
                "remaining": int(remaining) if remaining else None,
                "available": True,
                "error": None,
            }
        elif resp.status_code == 429:
            return {"remaining": 0, "available": False, "error": "Rate limited"}
        else:
            return {"remaining": None, "available": True, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        # Graceful degrade: assume available
        return {"remaining": None, "available": True, "error": str(e)}


def check_deepseek_quota() -> dict:
    """
    Send a minimal test call to DeepSeek and parse rate limit headers.
    Returns quota dict. Falls back gracefully if unavailable.
    """
    if not DEEPSEEK_API_KEY:
        return {"remaining": None, "available": False, "error": "No DEEPSEEK_API_KEY"}
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
            },
            timeout=10,
        )
        remaining = resp.headers.get("x-ratelimit-remaining-requests")
        tokens_limit = resp.headers.get("x-ratelimit-limit-tokens")

        if resp.status_code == 429:
            return {
                "remaining": 0,
                "limit_tokens_per_min": int(tokens_limit) if tokens_limit else None,
                "available": False,
                "error": "Rate limited",
            }
        return {
            "remaining": int(remaining) if remaining else None,
            "limit_tokens_per_min": int(tokens_limit) if tokens_limit else None,
            "available": resp.status_code < 500,
            "error": None if resp.status_code < 400 else f"HTTP {resp.status_code}",
        }
    except Exception as e:
        return {"remaining": None, "available": True, "error": str(e)}


def check_gemini_quota(quota_state: dict) -> dict:
    """
    Track Gemini queries per day (1500 limit) and per minute (15 limit).
    Returns {"queries_today": int, "available": bool, "rate_limit_this_min": bool}
    """
    m = quota_state.get("models", {}).get("gemini", {})
    daily_limit = m.get("free_tier_limit_queries_per_day", 1500)
    min_limit   = m.get("free_tier_limit_queries_per_min", 15)
    queries_today   = m.get("queries_today", 0)
    queries_this_min = m.get("queries_this_minute", 0)

    return {
        "queries_today": queries_today,
        "queries_this_minute": queries_this_min,
        "daily_limit": daily_limit,
        "min_limit": min_limit,
        "available": queries_today < daily_limit,
        "rate_limit_this_min": queries_this_min >= min_limit,
    }


# ── Mutation Prompt ───────────────────────────────────────────────────────────

MUTATION_PROMPT_TEMPLATE = """You are a quantitative trading strategist. Mutate ONE parameter slightly.

BASELINE:
{baseline_json}

MUTATION #: {variation_number}

Pick ONE numeric parameter and tweak it by 10-20%. Keep all other parameters unchanged.
Return ONLY valid JSON (no markdown, no explanation):

{{"name": "Strategy name with variation #{variation_number}", "parameters": {{...}}, "rationale": "One line explaining the mutation"}}"""


def _parse_json_response(raw: str) -> dict:
    """Strip markdown fences and parse JSON."""
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    return json.loads(raw.strip())


# ── Mutation Functions ────────────────────────────────────────────────────────

def mutate_with_groq(baseline_strategy: dict, variation_number: int,
                     quota_state: dict = None) -> Optional[dict]:
    """Use Groq Llama (cheap, fast) to generate a parameter mutation."""
    if not GROQ_API_KEY:
        return None

    prompt = MUTATION_PROMPT_TEMPLATE.format(
        baseline_json=json.dumps(baseline_strategy, indent=2),
        variation_number=variation_number,
    )

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 300,
            },
            timeout=30,
        )

        if resp.status_code == 429:
            raise RateLimitError("groq", "Rate limited (429)")

        resp.raise_for_status()

        if quota_state:
            update_quota_after_success("groq", quota_state, dict(resp.headers))

        raw = resp.json()["choices"][0]["message"]["content"]
        mutated = _parse_json_response(raw)
        mutated["generation"] = variation_number
        mutated["source"] = "groq_llama_8b"
        return mutated

    except RateLimitError:
        raise
    except Exception as e:
        raise Exception(f"Groq error: {e}") from e


def mutate_with_deepseek(baseline_strategy: dict, variation_number: int,
                          quota_state: dict = None) -> Optional[dict]:
    """Use DeepSeek API to generate a parameter mutation."""
    if not DEEPSEEK_API_KEY:
        return None

    prompt = MUTATION_PROMPT_TEMPLATE.format(
        baseline_json=json.dumps(baseline_strategy, indent=2),
        variation_number=variation_number,
    )

    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 300,
            },
            timeout=30,
        )

        if resp.status_code == 429:
            raise RateLimitError("deepseek", "Rate limited (429)")

        resp.raise_for_status()

        if quota_state:
            update_quota_after_success("deepseek", quota_state, dict(resp.headers))

        raw = resp.json()["choices"][0]["message"]["content"]
        mutated = _parse_json_response(raw)
        mutated["generation"] = variation_number
        mutated["source"] = "deepseek"
        return mutated

    except RateLimitError:
        raise
    except Exception as e:
        raise Exception(f"DeepSeek error: {e}") from e


def mutate_with_gemini(baseline_strategy: dict, variation_number: int,
                        quota_state: dict = None) -> Optional[dict]:
    """Use Gemini Flash Lite to generate a parameter mutation with daily/minute tracking."""
    if not GEMINI_API_KEY:
        return None

    try:
        import google.generativeai as genai
    except ImportError:
        return None

    prompt = MUTATION_PROMPT_TEMPLATE.format(
        baseline_json=json.dumps(baseline_strategy, indent=2),
        variation_number=variation_number,
    )

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash-lite")
        response = model.generate_content(prompt)
        raw = response.text.strip()

        if quota_state:
            update_quota_after_success("gemini", quota_state)

        mutated = _parse_json_response(raw)
        mutated["generation"] = variation_number
        mutated["source"] = "gemini"
        return mutated

    except Exception as e:
        err_str = str(e).lower()
        if "429" in err_str or "quota" in err_str or "rate" in err_str:
            raise RateLimitError("gemini", str(e))
        raise Exception(f"Gemini error: {e}") from e


def mutate_with_haiku(baseline_strategy: dict, variation_number: int,
                       quota_state: dict = None) -> Optional[dict]:
    """Use Claude Haiku (last resort, reliable) to generate a parameter mutation."""
    if not ANTHROPIC_API_KEY:
        return None

    prompt = MUTATION_PROMPT_TEMPLATE.format(
        baseline_json=json.dumps(baseline_strategy, indent=2),
        variation_number=variation_number,
    )

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        if quota_state:
            update_quota_after_success("haiku", quota_state)

        raw = response.content[0].text.strip()
        mutated = _parse_json_response(raw)
        mutated["generation"] = variation_number
        mutated["source"] = "haiku"
        return mutated

    except Exception as e:
        err_str = str(e).lower()
        if "429" in err_str or "overloaded" in err_str or "rate" in err_str:
            raise RateLimitError("haiku", str(e))
        raise Exception(f"Haiku error: {e}") from e


def random_mutation(baseline_strategy: dict, variation_number: int,
                    quota_state: dict = None) -> dict:
    """Fallback: randomly tweak one numeric parameter by ±15%."""
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


# ── Custom Exception ──────────────────────────────────────────────────────────

class RateLimitError(Exception):
    def __init__(self, model_name: str, message: str = ""):
        self.model_name = model_name
        super().__init__(message or f"{model_name} rate limited")


# ── Backtest Helpers ──────────────────────────────────────────────────────────

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
    current_sharpe   = current_best.get("backtest", {}).get("sharpe_ratio", -999) or -999
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


# ── Main Research Loop ────────────────────────────────────────────────────────

def run_research_loop(strategy_name: str, num_cycles: int = 10,
                      symbol: str = "XRPUSDT", interval: str = "240",
                      free_tier_only: bool = False):
    """Main research loop with smart model fallback chain and quota tracking."""
    if strategy_name not in AVAILABLE_STRATEGIES:
        log(f"❌ Unknown strategy: {strategy_name}. Available: {list(AVAILABLE_STRATEGIES.keys())}")
        return None

    baseline_info = AVAILABLE_STRATEGIES[strategy_name]
    log(f"🚀 Research loop: {strategy_name} | {num_cycles} cycles | {symbol} {interval}")
    log(f"   Baseline: {baseline_info['description']}")

    # FREE_TIER_ONLY_MODE: env var or CLI flag
    _free_only = FREE_TIER_ONLY_MODE or free_tier_only
    if _free_only:
        log(f"🔒 FREE_TIER_ONLY_MODE enabled — skipping paid tiers")

    # Load quota state
    quota_state = load_quota_state()

    # Define fallback chain: (model_name, mutator_func)
    # FREE_TIER_ONLY_MODE skips DeepSeek and Haiku
    if _free_only:
        mutation_attempt_order = [
            ("groq",   mutate_with_groq),
            ("gemini", mutate_with_gemini),
            ("random", random_mutation),
        ]
    else:
        mutation_attempt_order = [
            ("groq",     mutate_with_groq),
            ("deepseek", mutate_with_deepseek),
            ("gemini",   mutate_with_gemini),
            ("haiku",    mutate_with_haiku),
            ("random",   random_mutation),
        ]

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

        # Loop prevention: check if any method is available
        if not should_continue_loop(cycle, num_cycles, quota_state):
            log(f"⚠️  Stopping at cycle {cycle}/{num_cycles} — quota exhausted")
            break

        best_params = current_best.get("strategy", {}).get("parameters",
                      baseline_info["parameters"])
        mutation_base = {
            "name": baseline_info["name"],
            "parameters": dict(best_params),
        }

        mutated = None
        tried_models = []

        for model_name, mutator_func in mutation_attempt_order:
            if not should_use_model(model_name, quota_state):
                log(f"  ⊘ {model_name} quota exhausted, skipping")
                continue

            # Show quota info per mutation
            m = quota_state["models"].get(model_name, {})
            if model_name == "groq":
                remaining = m.get("remaining_requests", "?")
                quota_str = f"{remaining}/5000"
            elif model_name == "deepseek":
                remaining = m.get("remaining_requests", "?")
                quota_str = f"{remaining}/50 req/min"
            elif model_name == "gemini":
                qd  = m.get("queries_today", 0)
                qdl = m.get("free_tier_limit_queries_per_day", 1500)
                quota_str = f"{qd}/{qdl} today"
            elif model_name == "haiku":
                quota_str = "Anthropic (generous)"
            else:
                quota_str = "unlimited"

            fallback_str = " → ".join(tried_models) + (" → " if tried_models else "")
            log(f"  🧬 Mutation #{cycle} {fallback_str}{model_name} ({quota_str})")

            try:
                mutated = mutator_func(mutation_base, cycle, quota_state)
                if mutated:
                    log(f"    ✅ {model_name} success — {mutated.get('rationale', 'mutation applied')}")
                    break
            except RateLimitError as e:
                log(f"    ⚠️  {model_name} quota limit hit → falling back")
                mark_model_quota_exhausted(model_name, quota_state)
                tried_models.append(model_name)
                continue
            except Exception as e:
                log(f"    ✗ {model_name} error: {e}")
                tried_models.append(model_name)
                continue

        if not mutated:
            log("  ✗ All mutation methods failed — skipping cycle")
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
            current_best["is_best"] = True

        log(f"  Current best: Gen {current_best['generation']} "
            f"(Sharpe {current_best['backtest'].get('sharpe_ratio', '?')})")

        # Persist updated quota state
        save_quota_state(quota_state)
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
        log(f"  Mutation source: {current_best['strategy'].get('source', '?')}")

    # Print final quota summary
    log(f"\n📊 QUOTA SUMMARY")
    for model_name, m in quota_state["models"].items():
        avail = "✅" if m.get("available", True) else "❌"
        if model_name == "groq":
            log(f"  {avail} groq:     {m.get('remaining_requests', '?')} requests remaining")
        elif model_name == "deepseek":
            log(f"  {avail} deepseek: {m.get('remaining_requests', '?')} requests/min remaining")
        elif model_name == "gemini":
            log(f"  {avail} gemini:   {m.get('queries_today', 0)}/1500 today, "
                f"{m.get('queries_this_minute', 0)}/15 this min")
        elif model_name == "haiku":
            log(f"  {avail} haiku:    (generous Anthropic limits)")
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
    print(f"  {'Gen':>4} | {'Strategy':<30} | {'Sharpe':>8} | {'WinRate':>8} | {'P&L':>8} | {'Source':<12} | Bias")
    print(f"  {'-'*4}-+-{'-'*30}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*12}-+------")
    for r in records:
        gen    = r.get("generation", "?")
        strat  = r.get("strategy_module", "?")[:30]
        bt     = r.get("backtest", {})
        sharpe = bt.get("sharpe_ratio", 0) or 0
        wr     = bt.get("win_rate", 0) or 0
        pnl    = bt.get("total_pnl_usd", 0) or 0
        source = r.get("strategy", {}).get("source", "?")[:12]
        best   = "🏆" if r.get("is_best") else "  "
        bias   = "⚠️" if r.get("lookahead_bias_flag") else "✓"
        print(f"  {best}{gen:>4} | {strat:<30} | {sharpe:>8.3f} | {wr*100:>7.1f}% | "
              f"${pnl:>7.2f} | {source:<12} | {bias}")


# ── Free-Tier Only Mode ───────────────────────────────────────────────────────

FREE_TIER_ONLY_MODE = os.getenv("FREE_TIER_ONLY", "").lower() in ("true", "1", "yes")


def should_continue_loop(cycle: int, max_cycles: int, quota_state: dict) -> bool:
    """
    Prevent infinite loops when all tiers exhausted.
    Random mutation is always available as final fallback, so this only
    logs state and warns — it never blocks if random is the last resort.
    """
    free_only = FREE_TIER_ONLY_MODE
    groq_ok     = should_use_model("groq", quota_state)
    gemini_ok   = should_use_model("gemini", quota_state)
    deepseek_ok = not free_only and should_use_model("deepseek", quota_state)
    haiku_ok    = not free_only and should_use_model("haiku", quota_state)

    any_ai = groq_ok or gemini_ok or deepseek_ok or haiku_ok

    if not any_ai:
        # Get gemini quota info for the log message
        gm = quota_state.get("models", {}).get("gemini", {})
        gemini_remaining = gm.get("free_tier_limit_queries_per_day", 1500) - gm.get("queries_today", 0)

        groq_rem = quota_state.get("models", {}).get("groq", {}).get("remaining_requests", 0)
        ds_rem   = quota_state.get("models", {}).get("deepseek", {}).get("remaining_requests", 0)

        log(f"⚠️  All AI model quotas exhausted at cycle {cycle}/{max_cycles}")
        log(f"   Groq: {groq_rem} remaining | DeepSeek: {ds_rem} remaining | "
            f"Gemini: {gemini_remaining} remaining")
        log(f"   Action: Enable FREE_TIER_ONLY_MODE or top up credits")
        log(f"   Falling back to random mutation (always available)")
        # We still return True — random mutation is always available as fallback
        # Return False only if you want to halt on quota exhaustion
    return True


def main():
    parser = argparse.ArgumentParser(description="KingK Strategy Auto-Researcher")
    parser.add_argument("--baseline", "-b", type=str,
                        help=f"Baseline strategy. Choices: {list(AVAILABLE_STRATEGIES.keys())}")
    parser.add_argument("--strategy", type=str,
                        help="Alias for --baseline (strategy module name)")
    parser.add_argument("--cycles",   "-c", type=int, default=10, help="Number of mutation cycles")
    parser.add_argument("--symbol",   "-s", type=str, default="XRPUSDT", help="Symbol e.g. XRPUSDT")
    parser.add_argument("--interval", "-i", type=str, default="240", help="Candle interval: 60, 240")
    parser.add_argument("--list",           "-l", action="store_true", help="List all generations")
    parser.add_argument("--quota",          "-q", action="store_true", help="Show current quota state")
    parser.add_argument("--free-tier-only", "-f", action="store_true",
                        help="FREE_TIER_ONLY_MODE: skip paid tiers (DeepSeek, Haiku), use Groq → Gemini → Random")
    args = parser.parse_args()

    if args.list:
        list_generations()
        return

    if args.quota:
        state = load_quota_state()
        print(json.dumps(state, indent=2, default=str))
        return

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
        free_tier_only=args.free_tier_only,
    )


if __name__ == "__main__":
    main()
