# join-quant

Automated JoinQuant strategy discovery, cloning, and backtest pipeline.

## Features

- **Pipeline 1 — Daily Discovery & Clone**: Scrapes the JoinQuant community via the listV2 API, fetches source code + performance metrics via HTTP API, saves to `strategies/`, sends WeChat alerts on new finds.
- **Pipeline 2 — Custom Strategy Backtest**: Upload any local Python strategy file → create JQ research entry → inject code via Ace editor → trigger backtest → poll completion → extract metrics. Fully browser-automated via CDP connection to your logged-in Chrome.
- **Daily Cron**: Pipeline 1 runs on a schedule (configured via OpenClaw cron), stopping when hitting VIP access limits.
- **Modular**: Each component (auth, discovery, fetcher, backtest) is independent and reusable.

## Implemented Pipelines

Two fully-automated pipelines are implemented. Each is documented below with its exact technical implementation.

---

### Pipeline 1: Daily Strategy Discovery & Clone

**Purpose:** Automatically discover high quality strategies from the JoinQuant community, clone their source code, and save locally.

**Entry points:**
```bash
node utils/strategy-discover.js        # Discover top N strategies
node utils/strategy-fetch.js            # Process entire clone queue
node utils/strategy-fetch.js 3         # Process up to N strategies
node utils/strategy-daily.js          # Full pipeline: discover + clone loop
node utils/strategy-daily.js --discover-only  # Discovery only (~5s)
```

**Step-by-step technical implementation:**

| Step | What happens | How |
|------|-------------|-----|
| 1. Login | Authenticate to JQ | `POST /user/login` with `username` + `pwd` (form encoded). Server sets cookies (`uid`, `PHPSESSID`, `token`) in response headers. Stored in `data/cookies.json`. |
| 2. Discovery | Fetch community strategy list | `GET /data/listV2` with page/sort params. Returns JSON with `postId`, `likes`, `clones`, `communityScore`. Strategies sorted by composite score = `likes + clones×0.5`. |
| 3. Dedupe | Filter out already-copied strategies | Compare against `data/discovered.json` (all-time) and `data/copy-queue.json` (pending). New strategies appended to queue. |
| 4. Clone fetch | For each queued strategy: fetch source + stats | `GET /algorithm/backtest/source?backtestId=X` — returns Python source code. `POST /algorithm/backtest/stats?backtestId=X&ajax=1` — returns JSON with `annualReturn`, `maxDrawdown`, `sharpe`, etc. |
| 5. Save | Write `.py` file to `strategies/` | Filename format: `{date}_{title}-{shortPostId}.py`. Strategy name, metrics, and `postId` embedded as comments at the top. |
| 6. WeChat alert | Send strategy summary to user | OpenClaw WeChat channel. Message includes strategy title, metrics, and clone/link info. |

**No browser automation required.** Steps 1–5 use raw HTTP API calls. Step 6 uses OpenClaw internal messaging.

---

### Pipeline 2: Custom Strategy Backtest

**Purpose:** Upload any local Python strategy file to JoinQuant, run a backtest, poll for completion, and extract result metrics.

**Entry point:**
```bash
node utils/strategy-post-backtest.js <path-to-strategy.py> [title] [--window train|val] [--start YYYY-MM-DD --end YYYY-MM-DD] [--capital N]
```
The backtest window is parameterized (`--window train` = 2022-01-01→2023-12-31, `--window val` = 2024). Any window reaching into **2025+ is hard-blocked** (`OOS-BLOCKED`, reserved out-of-sample) unless `JQ_ALLOW_OOS=1`. With no window flag, JQ's default range is used (ad-hoc mode).

**Step-by-step technical implementation:**

| Step | What happens | How |
|------|-------------|-----|
| 1. Browser setup | Connect to running Chrome via CDP | `chromium.connectOverCDP('http://localhost:9225')`. Reuses the user's existing Chrome session (cookies, login state). **No username/password needed.** If no Chrome at 9225: launch persistent-context Chrome with `--user-data-dir=/tmp/jq-auth-browser`. |
| 2. Create strategy | Get a new `algorithmId` | Navigate to `/algorithm/index/new?restore=0&type=stock&baseCapital=100000`. JQ does a client-side redirect to `/algorithm/index/edit?algorithmId={32-char-hex}`. Extract `algorithmId` from final URL. |
| 3. Inject code | Put Python code into JQ's editor | JQ uses the **Ace code editor**. Code injected via `window.ace.edit(div).setValue(code, -1)`. Also synced to hidden `<textarea id="code">` (JQ's backend reads from this on save, not from Ace directly). |
| 4. Save | Persist code to JQ servers | `page.evaluate()` clicks the "保存" button. JQ POSTs the textarea content to backend. |
| 5. Trigger backtest | Start the backtest run | `page.evaluate()` clicks the "编译运行" button. JQ queues the backtest job. |
| 6. Poll for completion | Wait for backtest to finish | Navigate to `/algorithm/backtest/buildList?algorithmId=X`. JQ updates this page via XHR without full page reload. **Reload on each poll iteration** (every 5s) to see fresh status. Detect `"完成"` in DOM to know when done. |
| 7. Extract metrics | Parse result table | `document.querySelectorAll('table tbody tr')`. Find the row where `cells[6].textContent === '完成'`. Extract: `cells[7]`=策略收益, `cells[8]`=最大回撤, `cells[9]`=Alpha, `cells[10]`=Beta, `cells[11]`=Sharpe. |

**Why CDP instead of Playwright launch?**
JoinQuant sets `PHPSESSID` and `token` as `httpOnly` cookies — browsers guard these and Playwright cannot read or set them via `addCookies()`. CDP connects to the user's already-logged-in Chrome, inheriting all cookies and the full session state, bypassing authentication entirely.

**Why reload polling?**
JoinQuant updates backtest status via JavaScript XHR calls that mutate the DOM in-place. A single `page.goto()` loads a static snapshot — subsequent status changes are invisible without a full page reload. We reload the buildList URL on every poll to get the latest state.

---

### Pipeline 3: Autoresearch Team

**Purpose:** A self-improving strategy-research loop that mines the wiki knowledge base for ideas, iterates strategy mutations on a frozen backtest harness, and writes learnings back — a **4-agent team** (run via the `/run-experiment` skill; authoritative spec in `research/program.md`).

- **Agent 1 (ideator)** — reads the KB + experiment logs, generates ideas with reasoning; decides keep-iterating / finalize / give-up on TRAIN results.
- **Agent 2 (critic)** — judges idea validity, maintains a ranked `research/ideas-queue.json`, dispatches the best idea.
- **Agent 3 (engineer)** — writes the candidate `.py`, runs the backtest (enclosed, harness-obeying); Type-1→TRAIN, Type-2→VAL.
- **Agent 4 (recorder)** — on a VAL result, records the experiment + archives the strategy to `validated_strategies/`, backfills the wiki.

**Strict window protocol** (`research/harness.md`, frozen): iteration/selection runs on **TRAIN** (2022–2023) only; **VAL** (2024) is run once on a *finalized* strategy; the **2025→now OOS window is never touched** (hard-blocked in `strategy-post-backtest.js`). Resumable via `research/loop-state.json` + `ideas-queue.json` + `results.tsv` + git. Unattended auto-resume across quota resets: `scripts/autoresearch-loop.sh` + the launchd agent.

---

## Architecture

```
join-quant/
├── utils/
│   ├── login.js              # LoginManager: raw HTTP login → cookies.json
│   ├── fetcher.js            # StrategyFetcher: source + stats via HTTP API
│   ├── loader.js             # StrategyLoader: load local .py/.json files
│   ├── strategy-discover.js  # Community listV2 API crawler + data store
│   ├── strategy-fetch.js     # Clone queue processor (Pipeline 1)
│   ├── strategy-daily.js    # Cron entry: discover → fetch loop
│   └── strategy-post-backtest.js  # Custom strategy backtest (Pipeline 2)
├── backtest/
│   └── runner.js             # BacktestRunner: clone → poll → parse
├── pipelines/
│   ├── community.js          # CommunityPipeline orchestrator (Pipeline 1)
│   └── custom.js             # CustomPipeline orchestrator (Pipeline 2)
├── strategies/                # Cloned + local Python strategy files
├── data/                     # Discovery state (gitignored)
│   ├── discovered.json        # All-time discovered strategies by postId
│   ├── copy-queue.json        # Pending strategies sorted by score
│   ├── notifications.json    # Pending WeChat notifications
│   └── cookies.json          # JoinQuant session cookies
└── index.js                  # CLI entry point
```

---

## Quick Start

```bash
cd ~/repos/join-quant
npm install
```

### 1. Start Chrome with Debugging Port (one-time setup)

```bash
# Run this ONCE to set up Chrome. Keep this Chrome process running.
# It remembers your JQ login permanently.

nohup /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9225 \
  --user-data-dir=/tmp/jq-auth-browser \
  > /tmp/chrome-jq.log 2>&1 &

# On first run: open Chrome, manually log into joinquant.com
# Subsequent runs: Chrome reuses the cached session — no re-login needed
```

### 2. Backtest a Custom Strategy

```bash
cd ~/repos/join-quant

# Run backtest on a local Python strategy file:
node utils/strategy-post-backtest.js strategies/我的策略.py "可选标题"

# Output:
# [auth] ✅ Connected to existing Chrome (no CAPTCHA needed)
# [post] Strategy created, algorithmId=xyz
# [post] Ace: 943 chars
# [post] Saved
# [post] Backtest triggered
# [post] ✅ 回测完成 (19s)
#
# ========== BACKTEST RESULT ==========
# Strategy:    我的策略
# algorithmId: xyz
# Status:      ✅ 回测完成
# 回测时间:    2026-06-21 00:03:34
# 时间范围:    2022-01-01 - 2023-12-31   (--window train; illustrative)
# 运行频率:    每天
# 策略收益:    18%
# 最大回撤:    11.18%
# 阿尔法:      -0.1028
# 贝塔:        0.7703
# 夏普比率:    1.6733
# ====================================
```

---

## CLI Reference

```bash
node index.js community <postId> <backtestId>   # Backtest a community post strategy
node index.js custom ./strategies/my.py          # Backtest a local file
node index.js custom --backtestId <id>           # Re-run an existing backtest
node index.js list                               # List local strategies
node index.js status                             # Show cookie/auth status
node index.js login                              # Force fresh login
```

---

## Configuration

```bash
# Environment variables (optional — CDP approach doesn't need credentials)
JOINQUANT_USERNAME=15656096430
JOINQUANT_PASSWORD=your_password_here
JQ_CDP_URL=http://localhost:9225          # Chrome debugging endpoint (default)
```

**Chrome Setup (most important):**
The JQ session is stored in Chrome's profile at `/tmp/jq-auth-browser`. Do NOT close the Chrome process — closing it invalidates the session and requires re-login. The Chrome process should be started once and kept running.

---

## Data Files

| File | Description |
|------|-------------|
| `data/discovered.json` | All strategies ever discovered, deduplicated by postId |
| `data/copy-queue.json` | Pending strategies sorted by composite score (`likes + clones×0.5`) |
| `data/notifications.json` | Pending WeChat notifications |

**Composite Score** = `likes + clones × 0.5`

---

## Testing

```bash
npm test
```

---

## Known Limitations

- **Backtest date range**: Pipeline 2's window is set via `--window train|val` or `--start/--end`. The **2025-01-01→now out-of-sample window is hard-blocked** (`OOS-BLOCKED`) unless `JQ_ALLOW_OOS=1` — see `research/harness.md`. With no flag, JQ's default range applies (ad-hoc, not valid for logging experiments).
- **Chrome session persistence**: Pipeline 2 relies on a running Chrome process. Closing it invalidates the session and requires re-login. Keep the Chrome process running (see Chrome Setup above).
- **Headless mode**: JoinQuant shows CAPTCHA ("拼图验证") in headless Playwright browsers. Pipeline 2 uses CDP connection to an existing headed Chrome session to bypass this.

## License

MIT
