"""
Failsafe / Circuit Breaker for KingK agents.
Prevents runaway API calls and token burn.

Rules:
- Max 3 retries per call, exponential backoff
- Circuit breaker: if 3 consecutive failures → open circuit, skip for 30 min
- Hard daily call limit per model
- All failures logged, never silently swallowed
"""
import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path(__file__).parent.parent / "logs" / "circuit_state.json"
LOG_FILE   = Path(__file__).parent.parent / "logs" / "failsafe.log"

# Config
MAX_RETRIES        = 3
BACKOFF_BASE       = 2       # seconds (doubles each retry: 2, 4, 8)
CIRCUIT_OPEN_SECS  = 1800    # 30 min cooldown after circuit opens
DAILY_CALL_LIMITS  = {
    "gemini":    100,
    "haiku":     50,
    "default":   30,
}

def _now() -> float:
    return time.time()

def _log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    line = f"[{ts}] [FAILSAFE] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}

def _save_state(state: dict):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

class CircuitBreaker:
    def __init__(self, service: str):
        self.service = service
        self.state   = _load_state()

    def _svc(self) -> dict:
        return self.state.setdefault(self.service, {
            "failures": 0,
            "open_until": 0,
            "daily_calls": {},
        })

    def is_open(self) -> bool:
        svc = self._svc()
        if svc["open_until"] > _now():
            remaining = int(svc["open_until"] - _now())
            _log(f"{self.service} circuit OPEN — skipping ({remaining}s cooldown remaining)")
            return True
        return False

    def check_daily_limit(self) -> bool:
        svc   = self._svc()
        today = _today()
        calls = svc["daily_calls"].get(today, 0)
        limit = DAILY_CALL_LIMITS.get(self.service, DAILY_CALL_LIMITS["default"])
        if calls >= limit:
            _log(f"{self.service} daily limit hit ({calls}/{limit}) — blocking call")
            return False
        return True

    def record_call(self):
        svc   = self._svc()
        today = _today()
        svc["daily_calls"][today] = svc["daily_calls"].get(today, 0) + 1
        _save_state(self.state)

    def record_success(self):
        svc = self._svc()
        svc["failures"] = 0
        svc["open_until"] = 0
        _save_state(self.state)

    def record_failure(self, err: str):
        svc = self._svc()
        svc["failures"] += 1
        _log(f"{self.service} failure #{svc['failures']}: {err}")
        if svc["failures"] >= MAX_RETRIES:
            svc["open_until"] = _now() + CIRCUIT_OPEN_SECS
            _log(f"{self.service} circuit OPENED — cooling down for {CIRCUIT_OPEN_SECS//60} min")
        _save_state(self.state)


def safe_call(service: str, fn, *args, **kwargs):
    """
    Wrap any API call with retry + circuit breaker.
    Usage:
        result = safe_call("gemini", my_api_function, arg1, arg2)
        if result is None: # circuit open or limit hit — skip quietly
            return
    """
    cb = CircuitBreaker(service)

    if cb.is_open():
        return None

    if not cb.check_daily_limit():
        return None

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            cb.record_call()
            result = fn(*args, **kwargs)
            cb.record_success()
            return result
        except Exception as e:
            last_err = str(e)
            cb.record_failure(last_err)
            if attempt < MAX_RETRIES:
                wait = BACKOFF_BASE ** attempt
                _log(f"{service} retry {attempt}/{MAX_RETRIES} in {wait}s...")
                time.sleep(wait)
            else:
                _log(f"{service} gave up after {MAX_RETRIES} attempts. Last error: {last_err}")

    return None  # All retries exhausted — caller handles None gracefully


def get_circuit_status() -> str:
    """Quick status summary for all services."""
    state = _load_state()
    if not state:
        return "No circuit state yet — all services healthy."
    lines = []
    for svc, data in state.items():
        today  = _today()
        calls  = data.get("daily_calls", {}).get(today, 0)
        limit  = DAILY_CALL_LIMITS.get(svc, DAILY_CALL_LIMITS["default"])
        open_u = data.get("open_until", 0)
        status = "🔴 OPEN" if open_u > _now() else "🟢 OK"
        lines.append(f"  {svc}: {status} | today {calls}/{limit} calls | failures {data.get('failures',0)}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(get_circuit_status())
