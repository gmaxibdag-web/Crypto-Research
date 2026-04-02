#!/usr/bin/env python3
"""
Model quota monitor for DeepSeek, Groq, Gemini.
Tracks usage and logs to data/model_quota_state.json.
"""
import os
import json
import requests
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
QUOTA_FILE = DATA_DIR / "model_quota_state.json"

def now_utc():
    return datetime.now(timezone.utc)

def load_quota_state():
    if not QUOTA_FILE.exists():
        return {
            "last_updated": now_utc().isoformat(),
            "models": {
                "deepseek": {
                    "remaining_requests": "unknown",
                    "last_checked": None,
                    "credit_balance": "unknown"
                },
                "groq": {
                    "remaining_requests": "unknown",
                    "last_checked": None,
                    "limit": 5000
                },
                "gemini": {
                    "queries_today": 0,
                    "last_checked": None,
                    "limit": 1500
                }
            }
        }
    with open(QUOTA_FILE, "r") as f:
        return json.load(f)

def save_quota_state(state):
    state["last_updated"] = now_utc().isoformat()
    DATA_DIR.mkdir(exist_ok=True)
    with open(QUOTA_FILE, "w") as f:
        json.dump(state, f, indent=2)

def check_deepseek_quota(api_key):
    """DeepSeek doesn't have quota API — track via usage."""
    # For now, just update timestamp
    return {
        "remaining_requests": "unknown",
        "credit_balance": "unknown"
    }

def check_groq_quota(api_key):
    """Groq free tier: 5000 requests/month."""
    # Groq doesn't expose quota API — track via usage
    return {
        "remaining_requests": "unknown"
    }

def update_quota():
    """Update quota state (called after each API use)."""
    state = load_quota_state()
    
    # Increment Gemini usage (heartbeats use it)
    gemini = state["models"]["gemini"]
    gemini["queries_today"] = gemini.get("queries_today", 0) + 1
    gemini["last_checked"] = now_utc().isoformat()
    
    save_quota_state(state)
    return state

def print_quota_summary():
    state = load_quota_state()
    print(f"\n📊 Model Quota Status ({state['last_updated']})")
    print("-" * 40)
    
    for model, data in state["models"].items():
        if model == "deepseek":
            print(f"DeepSeek: {data.get('remaining_requests', '?')} req/min | Credit: {data.get('credit_balance', '?')}")
        elif model == "groq":
            print(f"Groq:     {data.get('remaining_requests', '?')}/5000 requests this month")
        elif model == "gemini":
            print(f"Gemini:   {data.get('queries_today', 0)}/1500 queries today")
    
    print("-" * 40)

if __name__ == "__main__":
    update_quota()
    print_quota_summary()
