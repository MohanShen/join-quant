# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

**join-quant** is an automated pipeline for the [JoinQuant](https://www.joinquant.com) Chinese quant platform. It discovers community strategies, clones their source + performance metrics, and runs backtests — both for community posts and for local custom strategy files. Node.js (>=18), Playwright for browser automation, raw HTTP for the API paths.

## Setup & Commands

```bash
npm install          # installs playwright
npm test             # node --test tests/*.test.js

# CLI (see index.js)
node index.js community <postId> <backtestId> [replyId]  # backtest a community post
node index.js custom <path-to-strategy.py>               # backtest a local file
node index.js custom --backtestId <id>                   # re-run existing backtest
node index.js list                                       # list local ./strategies/
node index.js login                                      # force fresh login, cache cookies
node index.js status                                     # show cached cookie status

# Pipeline 1 (discovery/clone) entry points — not wired into index.js
node utils/strategy-discover.js            # crawl community listV2, build queue
node utils/strategy-fetch.js [N]           # process clone queue (optional limit)
node utils/strategy-daily.js               # cron: discover -> clone loop
node utils/strategy-daily.js --discover-only
```

### Chrome / auth setup (required for Pipeline 2)

Pipeline 2 connects to an already-logged-in Chrome over CDP to inherit `httpOnly`
session cookies and bypass JoinQuant's CAPTCHA. Start Chrome once and keep it running:

```bash
nohup /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9225 \
  --user-data-dir=/tmp/jq-auth-browser \
  > /tmp/chrome-jq.log 2>&1 &
# First run: log into joinquant.com manually. Closing Chrome invalidates the session.
```

Environment variables (optional — CDP path needs no credentials):
`JOINQUANT_USERNAME`, `JOINQUANT_PASSWORD`, `JQ_CDP_URL` (default `http://localhost:9225`).

## Two Pipelines

**Pipeline 1 — Daily Discovery & Clone** (`pipelines/community.js`, `utils/strategy-*.js`):
Pure HTTP. `GET /data/listV2` lists community strategies → dedupe against
`data/discovered.json` / `data/copy-queue.json` → for each: `GET /algorithm/backtest/source`
(Python source) + `POST /algorithm/backtest/stats` (metrics) → save `.py` to `strategies/`
→ WeChat alert. Ranked by composite score = `likes + clones × 0.5`.

**Pipeline 2 — Custom Strategy Backtest** (`pipelines/custom.js`, `backtest/runner.js`):
Browser-automated via CDP. Create `algorithmId` → inject Python into JQ's **Ace editor**
(`window.ace.edit(div).setValue(...)`, also synced to hidden `<textarea id="code">` which
the backend reads on save) → click 保存 / 编译运行 → **reload-poll** the buildList every 5s
for `完成` → scrape the result table for return/drawdown/Alpha/Beta/Sharpe.

> Why CDP, not a Playwright launch? JQ stores `PHPSESSID`/`token` as `httpOnly` cookies that
> Playwright can't set, and headless browsers hit the 拼图验证 CAPTCHA. CDP reuses the real session.
> Why reload-polling? JQ mutates backtest status in-place via XHR; a static `goto` misses updates.

## Layout

| Path | Purpose |
|------|---------|
| `index.js` | CLI entry (`community` / `custom` / `list` / `login` / `status`) |
| `utils/login.js` | `LoginManager` — raw HTTP login → cookies |
| `utils/fetcher.js` | `StrategyFetcher` — source + stats via HTTP API |
| `utils/loader.js` | `StrategyLoader` — load local `.py`/`.json` |
| `utils/strategy-discover.js` / `strategy-fetch.js` / `strategy-daily.js` | Pipeline 1 discovery/clone/cron |
| `utils/strategy-post-backtest.js` | Pipeline 2 custom backtest driver |
| `utils/refresh-cookies*.js` | Session cookie refresh (HTTP + CDP variants) |
| `pipelines/` | Orchestrators: `community.js`, `custom.js` |
| `backtest/runner.js` | `BacktestRunner` — clone → poll → parse |
| `strategies/` | ~155 cloned + local Python strategy files |
| `wiki/` | Strategy wiki (`index.md`, `strategies/`, `authors/`, `concepts/`) |
| `docs/` | `wiki-schema.md`, `push-format.md`, `translator-agent-prompt.md` |
| `tests/` | `node --test` suites: `auth`, `loader`, `runner` |
| `data/` | **gitignored** — discovery state + `cookies.json` |
| `auth/` | **gitignored** — session cookies (default cookie path is `auth/cookies.json`) |
| `.claude/skills/` | `ingest-strategy`, `query-wiki` skills |

## Notes & Gotchas

- `data/` and `auth/` are gitignored (state + credentials). Never commit them.
- Default cookie path in `index.js` is `auth/cookies.json`.
- Pipeline 2 uses JoinQuant's default backtest window (2019-01-01 → 2019-06-30); change the
  `newStrategy` URL params in `strategy-post-backtest.js` for a custom range.
- Do not close the CDP Chrome process — it invalidates the JQ session and forces re-login.
