# join-quant

Automated JoinQuant strategy discovery, cloning, and backtest pipeline.

## Features

- **Strategy Discovery**: Scrapes the JoinQuant community via the listV2 API to find strategies, sorted by composite score (likes + clones×0.5)
- **Auto-Fetch Pipeline**: For each strategy in the queue, fetches source code + performance stats via API and saves to `strategies/`
- **Daily Cron**: Runs discovery + copy loop daily, stopping only when hitting the access limit (VIP strategy cap)
- **WeChat Alerts**: Sends strategy summaries to your WeChat session after each successful clone
- **Custom Strategy Backtest**: Upload any local Python strategy file → run on JoinQuant → poll results → extract metrics

## Architecture

```
join-quant/
├── utils/
│   ├── login.js              # LoginManager: Playwright login, cookie persistence
│   ├── fetcher.js           # StrategyFetcher: Get source from JoinQuant API
│   ├── loader.js            # StrategyLoader: Load local .py/.json strategies
│   ├── strategy-discover.js # Community listV2 API crawler + data store
│   ├── strategy-fetch.js     # Queue walker: fetch source/stats via API → save .py → WeChat
│   ├── strategy-daily.js     # Cron entry point: discover → fetch loop
│   └── strategy-post-backtest.js  # ⭐ Custom strategy → JQ backtest pipeline
├── backtest/
│   └── runner.js            # BacktestRunner: Clone → Poll → Parse results
├── pipelines/
│   ├── community.js          # CommunityPipeline: post → fetch → backtest
│   └── custom.js            # CustomPipeline: local file → backtest
├── strategies/               # Python strategy files (cloned strategies saved here)
├── data/                    # Discovery state (gitignored)
│   ├── discovered.json       # All discovered strategies (keyed by postId)
│   ├── copy-queue.json       # Pending strategies sorted by composite score
│   └── notifications.json    # Pending WeChat notifications
└── index.js                 # CLI entry point
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
# 时间范围:    2019-01-01 - 2019-06-30
# 运行频率:    每天
# 策略收益:    18%
# 最大回撤:    11.18%
# 阿尔法:      -0.1028
# 贝塔:        0.7703
# 夏普比率:    1.6733
# ====================================
```

---

## How the Pipeline Works

The `strategy-post-backtest.js` script automates the full flow:

```
CDP (connect to Chrome)
    ↓
Create new strategy on JoinQuant (GET /algorithm/index/new → redirect to editor)
    ↓
Inject Python code into Ace editor (window.ace.edit().setValue())
    ↓
Sync to hidden textarea (JQ reads from this on save)
    ↓
Click 保存 (Save)
    ↓
Click 编译运行 (Trigger backtest)
    ↓
Poll /algorithm/backtest/buildList (reload every 5s, detect "完成")
    ↓
Extract result metrics from table (cells[1..11])
```

### Key Technical Notes

- **Why CDP?** JoinQuant sets `httpOnly` cookies (`PHPSESSID`, `token`) that cannot be set via Playwright's `addCookies()`. CDP connects directly to your running Chrome's debugging interface, inheriting the full authenticated session.
- **Why Ace editor?** JoinQuant's web editor uses Ace for code editing. We manipulate the Ace editor session directly via `window.ace.edit(div).setValue(code, -1)`, then sync to the hidden textarea that JQ's backend reads on save.
- **Why reload polling?** JoinQuant updates buildList status via XHR, not page navigation. A single page load won't reflect live status — we reload the buildList URL on each poll iteration.

---

## Discovery & Clone Pipeline

```bash
# Discover top strategies from community (~5 seconds)
node utils/strategy-daily.js --discover-only

# Process the clone queue (fetch source + stats → save .py → WeChat)
node utils/strategy-fetch.js 3    # process up to N strategies

# Full daily pipeline (discover + clone loop)
node utils/strategy-daily.js
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

- **Custom backtest date range**: The pipeline uses JoinQuant's default backtest period (2019-01-01 to 2019-06-30). Custom date ranges require modifying the `newStrategy` URL parameters.
- **Headless mode**: JoinQuant shows CAPTCHA ("拼图验证") in headless browser mode. Use headed mode (`--user-data-dir` persistent profile) or CDP connection to an existing Chrome session.

## License

MIT
