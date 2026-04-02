#!/usr/bin/env python3
"""
KingK Research Agent
Searches arXiv + Semantic Scholar for crypto trading signal research,
synthesizes findings via Groq LLM, and outputs structured signal parameters.

Usage:
  python3 agents/research_agent.py --topic "RSI divergence volume XRP breakout"
  python3 agents/research_agent.py --topic "on-chain metrics leading indicators crypto"
  python3 agents/research_agent.py --list     # show saved findings
"""

import os
import sys
import json
import time
import argparse
import requests
import arxiv
from datetime import datetime
from pathlib import Path
from groq import Groq
from tavily import TavilyClient
from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
RESEARCH_DIR = BASE_DIR / "research"
FINDINGS_FILE = RESEARCH_DIR / "findings.json"
RESEARCH_DIR.mkdir(exist_ok=True)

# Groq models
GROQ_MODEL_PRIMARY = "llama-3.3-70b-versatile"   # Groq free tier — fast, strong
GROQ_MODEL_FALLBACK = "llama-3.1-8b-instant"      # smaller fallback if rate limited

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{ts}] {msg}", flush=True)


def search_arxiv(topic: str, max_results: int = 8) -> list[dict]:
    """Search arXiv for relevant papers."""
    log(f"🔍 arXiv search: '{topic}'")
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=topic + " cryptocurrency trading",
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        papers = []
        for r in client.results(search):
            papers.append({
                "title": r.title,
                "abstract": r.summary[:600],
                "authors": [a.name for a in r.authors[:3]],
                "published": r.published.strftime("%Y-%m-%d"),
                "url": r.entry_id,
                "source": "arxiv",
            })
        log(f"  ✓ Found {len(papers)} arXiv papers")
        return papers
    except Exception as e:
        log(f"  ✗ arXiv error: {e}")
        return []


def search_semantic_scholar(topic: str, max_results: int = 8) -> list[dict]:
    """Search Semantic Scholar for relevant papers."""
    log(f"🔍 Semantic Scholar search: '{topic}'")
    try:
        params = {
            "query": topic + " crypto trading signals",
            "limit": max_results,
            "fields": "title,abstract,year,authors,url",
        }
        resp = requests.get(SEMANTIC_SCHOLAR_API, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        papers = []
        for p in data.get("data", []):
            abstract = (p.get("abstract") or "")[:600]
            if not abstract:
                continue
            papers.append({
                "title": p.get("title", ""),
                "abstract": abstract,
                "authors": [a.get("name","") for a in (p.get("authors") or [])[:3]],
                "published": str(p.get("year", "")),
                "url": p.get("url", ""),
                "source": "semantic_scholar",
            })
        log(f"  ✓ Found {len(papers)} Semantic Scholar papers")
        return papers
    except Exception as e:
        log(f"  ✗ Semantic Scholar error: {e}")
        return []


def search_web_tavily(topic: str, max_results: int = 6) -> list[dict]:
    """Search the live web via Tavily for recent crypto research & analysis."""
    if not TAVILY_API_KEY:
        log("  ⚠ Tavily key not set, skipping web search")
        return []
    log(f"🌐 Tavily web search: '{topic}'")
    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        result = client.search(
            query=topic + " crypto trading strategy 2024 2025",
            search_depth="advanced",
            max_results=max_results,
            include_answer=True,
        )
        web_results = []
        for r in result.get("results", []):
            content = (r.get("content") or "")[:600]
            if not content:
                continue
            web_results.append({
                "title": r.get("title", ""),
                "abstract": content,
                "authors": [],
                "published": "2024-2025",
                "url": r.get("url", ""),
                "source": "web_tavily",
            })
        # Also include Tavily's synthesized answer as a source
        answer = result.get("answer", "")
        if answer:
            web_results.insert(0, {
                "title": f"Web synthesis: {topic}",
                "abstract": answer[:600],
                "authors": [],
                "published": "2025",
                "url": "",
                "source": "tavily_answer",
            })
        log(f"  ✓ Found {len(web_results)} web results")
        return web_results
    except Exception as e:
        log(f"  ✗ Tavily error: {e}")
        return []


def synthesize_with_groq(topic: str, papers: list[dict]) -> dict:
    """Use Groq LLM to synthesize research findings into signal parameters."""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set in .env")

    client = Groq(api_key=GROQ_API_KEY)

    # Build paper summaries for context
    paper_context = ""
    for i, p in enumerate(papers[:12], 1):
        paper_context += f"\n[{i}] {p['title']} ({p['published']})\n{p['abstract']}\n"

    prompt = f"""You are a quantitative crypto trading analyst. Your job is to analyze academic research and extract actionable trading signal parameters.

RESEARCH TOPIC: {topic}

RELEVANT PAPERS:
{paper_context}

Based on this research, provide a structured analysis in JSON format:

{{
  "topic": "{topic}",
  "summary": "2-3 sentence summary of what the research says about this topic",
  "edge_exists": true/false,
  "confidence": "low/medium/high",
  "key_findings": [
    "Finding 1 — what signal or pattern has predictive value",
    "Finding 2",
    "Finding 3"
  ],
  "signal_parameters": {{
    "primary_indicator": "name of main indicator/signal",
    "optimal_timeframe": "e.g. 4h, 1d",
    "entry_conditions": ["condition 1", "condition 2"],
    "confirmation_signals": ["signal 1", "signal 2"],
    "risk_notes": "key risk or limitation"
  }},
  "implementation_notes": "How to implement this in a paper trader",
  "backtesting_suggestions": "What to test and how",
  "papers_cited": {json.dumps([p['title'] for p in papers[:5]])}
}}

Return ONLY the JSON, no markdown, no explanation."""

    log(f"🧠 Synthesizing with Groq ({GROQ_MODEL_PRIMARY})...")
    
    for model in [GROQ_MODEL_PRIMARY, GROQ_MODEL_FALLBACK]:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=2000,
            )
            raw = response.choices[0].message.content.strip()
            
            # Strip any <think>...</think> blocks (Deepseek R1 style)
            if "<think>" in raw:
                raw = raw[raw.rfind("</think>")+8:].strip()
            
            # Extract JSON if wrapped in markdown
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            
            result = json.loads(raw)
            result["model_used"] = model
            log(f"  ✓ Synthesis complete using {model}")
            return result
        except json.JSONDecodeError as e:
            log(f"  ✗ JSON parse error with {model}: {e}")
            if model == GROQ_MODEL_FALLBACK:
                return {"error": "Failed to parse LLM response", "raw": raw, "topic": topic}
        except Exception as e:
            log(f"  ✗ Groq error with {model}: {e}")
            if "rate_limit" in str(e).lower():
                log("  ⏳ Rate limited, waiting 30s...")
                time.sleep(30)

    return {"error": "All models failed", "topic": topic}


def save_finding(finding: dict):
    """Append finding to findings.json."""
    findings = load_findings()
    finding["researched_at"] = datetime.utcnow().isoformat()
    
    # Replace if same topic exists
    topic = finding.get("topic", "")
    findings = [f for f in findings if f.get("topic", "") != topic]
    findings.append(finding)
    
    with open(FINDINGS_FILE, "w") as f:
        json.dump(findings, f, indent=2)
    log(f"💾 Saved to {FINDINGS_FILE}")


def load_findings() -> list[dict]:
    """Load existing findings."""
    if FINDINGS_FILE.exists():
        try:
            with open(FINDINGS_FILE) as f:
                return json.load(f)
        except:
            return []
    return []


def print_finding(finding: dict):
    """Pretty print a finding."""
    print("\n" + "="*60)
    print(f"📊 RESEARCH FINDING: {finding.get('topic', 'Unknown')}")
    print("="*60)
    
    if "error" in finding:
        print(f"❌ Error: {finding['error']}")
        return
    
    print(f"\n📝 Summary: {finding.get('summary', 'N/A')}")
    print(f"✅ Edge exists: {finding.get('edge_exists', '?')} | Confidence: {finding.get('confidence', '?')}")
    
    print("\n🔑 Key Findings:")
    for kf in finding.get("key_findings", []):
        print(f"  • {kf}")
    
    sp = finding.get("signal_parameters", {})
    if sp:
        print(f"\n📈 Signal Parameters:")
        print(f"  Indicator:  {sp.get('primary_indicator', 'N/A')}")
        print(f"  Timeframe:  {sp.get('optimal_timeframe', 'N/A')}")
        print(f"  Entry:      {', '.join(sp.get('entry_conditions', []))}")
        print(f"  Confirm:    {', '.join(sp.get('confirmation_signals', []))}")
        print(f"  Risk:       {sp.get('risk_notes', 'N/A')}")
    
    print(f"\n🔧 Implementation: {finding.get('implementation_notes', 'N/A')}")
    print(f"🧪 Backtest: {finding.get('backtesting_suggestions', 'N/A')}")
    print(f"\n⏱️  Researched: {finding.get('researched_at', 'N/A')}")
    print("="*60 + "\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def run_research(topic: str) -> dict:
    log(f"🚀 Starting research: '{topic}'")
    
    # Search all sources
    arxiv_papers = search_arxiv(topic)
    time.sleep(1)
    ss_papers = search_semantic_scholar(topic)
    time.sleep(1)
    web_results = search_web_tavily(topic)
    
    all_papers = arxiv_papers + ss_papers + web_results
    log(f"📚 Total sources found: {len(all_papers)} (arXiv: {len(arxiv_papers)}, S2: {len(ss_papers)}, web: {len(web_results)})")
    
    if not all_papers:
        log("⚠️  No papers found — synthesizing from general knowledge only")
    
    # Synthesize
    finding = synthesize_with_groq(topic, all_papers)
    finding["papers_found"] = len(all_papers)
    finding["topic"] = topic  # ensure topic is set
    
    # Save
    save_finding(finding)
    
    return finding


def main():
    parser = argparse.ArgumentParser(description="KingK Research Agent — crypto signal edge discovery")
    parser.add_argument("--topic", "-t", type=str, help="Research topic / hypothesis")
    parser.add_argument("--list", "-l", action="store_true", help="List all saved findings")
    parser.add_argument("--show", "-s", type=str, help="Show finding by topic keyword")
    args = parser.parse_args()

    if args.list:
        findings = load_findings()
        if not findings:
            print("No findings yet. Run: python3 agents/research_agent.py --topic 'your hypothesis'")
            return
        print(f"\n📚 Saved Research Findings ({len(findings)} total):")
        for i, f in enumerate(findings, 1):
            edge = "✅" if f.get("edge_exists") else "❌"
            conf = f.get("confidence", "?")
            ts = f.get("researched_at", "?")[:10]
            print(f"  {i}. {edge} [{conf}] {f.get('topic', 'Unknown')} ({ts})")
        return

    if args.show:
        findings = load_findings()
        keyword = args.show.lower()
        matches = [f for f in findings if keyword in f.get("topic", "").lower()]
        if not matches:
            print(f"No finding matching '{args.show}'")
            return
        for f in matches:
            print_finding(f)
        return

    if not args.topic:
        parser.print_help()
        return

    finding = run_research(args.topic)
    print_finding(finding)


if __name__ == "__main__":
    main()
