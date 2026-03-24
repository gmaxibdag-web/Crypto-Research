# MEMORY.md — Willy's Long-Term Memory

_Curated knowledge. Updated as we go._

---

## 👤 King K

- Crypto trader, builder mindset, direct communicator
- Building autonomous trading agents (paper → live)
- Wants systematic, data-driven edge — no hype
- Timezone: unknown

---

## 📁 Project: KingK Trader

**Location:** `/root/.openclaw/workspace/kingk-trader`

### Architecture
- `agents/paper_trader.py` — live paper trading loop (runs every 4h via cron)
- `agents/strategy_researcher.py` — auto-researcher using Gemini Flash Lite for mutations + Groq for synthesis
- `agents/research_agent.py` — research agent (fetches academic/web findings)
- `backtests/backtest.py` — backtester, loads from CSV
- `backtests/tune.py` — parameter tuner
- `strategies/ema_swing.py` — current live strategy
- `data/fetch_history.py` — paginated historical data fetcher
- `data/historical/` — CSV OHLCV data
- `config/settings.py` — pairs, allocation, strategy params
- `research/findings.json` — 8 research findings from auto-researcher

### Data Available
- `XRPUSDT_240.csv` — 5000 bars (4h, ~2yr, from Dec 2023)
- `SUIUSDT_240.csv` — 5000 bars (4h, ~2yr)
- `XRPUSDT_60.csv` — 18000 bars (1h, ~2yr) — fetched 2026-03-24
- `SUIUSDT_60.csv` — 18000 bars (1h, ~2yr) — fetched 2026-03-24

### Capital Allocation
- Total: $1000
- XRPUSDT: $400 | SUIUSDT: $400 | Reserve: $200

### Current Strategy: EMA Swing v1 (4h)
- Entry: EMA12 crosses EMA26 up, above EMA100 (trend), RSI 45-65, volume > 1.2x MA20
- XRP: TP 8%, SL 2.5% | SUI: TP 5%, SL 3%
- **Backtest results (2yr 4h):** XRP +14.2% ($57), SUI +24% ($96) ✅
- **1h backtest:** Both negative — too much noise on 1h. Stay on 4h.

### Model Tier Config (set 2026-03-24)
- T1 Routine: `google/gemini-3.1-flash-lite-preview`
- T2 Logic: `claude-haiku-4-5-20251001`
- T3 Strategy: `claude-sonnet-4-6`
- T4 Exec: `claude-opus-4-6`

### Cron Jobs
- Paper trader: every 4h (Sydney tz), main session system event

---

## 🔬 Research Findings (2026-03-22/23)

8 strategies researched, all showing `edge_exists: true, confidence: medium`:
1. RSI divergence + volume breakout (optimal: 4h)
2. SUI on-chain momentum (optimal: 4h)
3. EMA crossover trend following (optimal: 1d)
4. Funding rate divergence reversal (optimal: 4h-1d)
5. Liquidation cascade momentum (optimal: 4h)
6. MACD histogram divergence (optimal: 4h, 1d)
7. Bollinger Bands mean reversion (optimal: 4h)
8. Order book imbalance — **HIGH confidence** (optimal: 1m-1h)

---

## 🛠️ Known Issues / Fixed

- `backtest.py` was using `limit=500` (only 83 days). Fixed to load full CSV.
- `backtest.py` imported `TAKE_PROFIT_PCT` / `STOP_LOSS_PCT` — removed in config v2. Fixed.
- `strategy_researcher.py` called `backtest.py` with `--strategy-json` CLI arg that didn't exist. Fix in progress (subagent 2026-03-24).
- `research/backtests/` was empty — mutations generated but never backtested.

---

## ✅ Completed (2026-03-24)

### Multi-Strategy Pipeline
- `strategies/macd_rsi.py` — built
- `strategies/bollinger_mean_reversion.py` — built
- `strategies/rsi_divergence_breakout.py` — built
- `backtests/backtest.py` — full CLI (--symbol, --interval, --strategy, --tp, --sl, --json-output), Sharpe + MaxDD
- `backtests/compare_strategies.py` — comparison matrix runner
- `agents/strategy_researcher.py` — fixed, now calls backtest properly, saves to research/backtests/

### Strategy Comparison Results (4h, 2yr, $400/pair)
| Symbol | Strategy | Trades | Win% | P&L | Sharpe |
|--------|----------|--------|------|-----|--------|
| SUIUSDT | EMA Swing 🏆 | 40 | 37.5% | +$60 | +0.21 |
| XRPUSDT | EMA Swing | 32 | 34.4% | -$7 | -0.04 |
| XRPUSDT | MACD+RSI | 193 | 28.0% | -$242 | -0.11 |
| SUIUSDT | MACD+RSI | 187 | 28.9% | -$210 | -0.08 |
| XRPUSDT | Bollinger MR | 127 | 37.0% | -$114 | -0.10 |
| SUIUSDT | Bollinger MR | 132 | 24.2% | -$375 | -0.31 |
| Both | RSI Divergence | ~0 | — | — | — |

### Initial Findings (pre-tuning)
- EMA Swing SUI only positive Sharpe — keep live
- MACD+RSI overtrades (190 trades) — needs trend filter
- Bollinger MR bleeds in downtrends — needs trend filter
- RSI Divergence too restrictive — near-zero signals

### Tuning Results (2026-03-24) — FINAL
| Strategy | Pair | Trades | P&L | Sharpe | Win% | MaxDD |
|----------|------|--------|-----|--------|------|-------|
| RSI Divergence (tuned) 🏆 | XRP | 26 | +$65.84 | 0.47 | 42.3% | -10.2% |
| EMA Swing | SUI | 40 | +$60 | 0.21 | 37.5% | -16.5% |
| MACD+RSI (tuned) | SUI | 100 | +$173 | 0.17 | 38.0% | -14.9% |
| EMA Swing | XRP | 32 | -$7 | -0.04 | 34.4% | -19.3% |
| Bollinger MR | both | — | negative | negative | — | deep |

### Current Live Config (as of 2026-03-24)
- **XRPUSDT → rsi_divergence_breakout** (tuned: rsi_oversold=35, vol_mult=1.8, EMA50 ±10% window)
- **SUIUSDT → ema_swing** (ema_fast=12, ema_slow=26, ema_trend=100, RSI 50-65, vol 1.2x, TP 5%, SL 3%)

### Key Decisions
- Bollinger MR benched — fundamentally broken in crypto downtrends
- MACD+RSI SUI (+$173) tempting but Sharpe 0.17 < EMA Swing 0.21 — stay EMA Swing on SUI
- RSI Divergence XRP wins on quality: fewest trades (26), best Sharpe (0.47), lowest drawdown (-10.2%)

---

## 📌 Decisions & Lessons

- **4h > 1h for this strategy.** 1h generates too many false EMA crosses. Both pairs negative on 1h.
- **Don't trust small sample backtests** — 500 bars = 83 days, not enough. Always load full CSV.
- **Auto-researcher needs backtest integration to work** — mutation loop is useless without it.
- **Document everything in MEMORY.md** to avoid re-discovering the same issues next session.
