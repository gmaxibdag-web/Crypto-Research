# HEARTBEAT.md — KingK Trader Testnet Monitoring

## Active Checks (2026-03-24 to 2026-04-07)

During 2-week testnet trial, check:

1. **Paper trader health** — Did last 4h run execute? Any errors in logs?
2. **Quota state** — Groq/DeepSeek/Gemini remaining? Any approaching limits?
3. **Portfolio status** — Total positions, P&L, number of trades so far
4. **Next run time** — When's the next 4h paper trader cycle?

Skip: calendar, weather, email, general chatter. Only testnet metrics matter right now.

## After Testnet (April 8+)

Once 2-week test is done, expand checks to:
- Portfolio analysis (drawdown, Sharpe comparison vs backtest)
- Research loop readiness (if we run mutations)
- General system health
