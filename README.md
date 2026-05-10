# join-quant

Automated JoinQuant strategy discovery, cloning, and backtest pipeline.

## Features

- **Strategy Discovery**: Scrapes the JoinQuant community via the listV2 API to find strategies, sorted by composite score (likes + clones×0.5)
- **Auto-Clone Pipeline**: Iterates through the copy queue, clones each strategy via Playwright browser, saves source to `strategies/`, and fetches performance stats
- **Daily Cron**: Runs discovery + copy loop daily, stopping only when hitting the access limit (VIP strategy cap)
- **WeChat Alerts**: Sends strategy summaries to your WeChat session after each successful clone
- **Modular Architecture**: Each component (auth, discovery, clone runner, backtest) is independent and reusable

## Architecture

```
join-quant/
├── utils/
│   ├── login.js           # LoginManager: Playwright login, cookie persistence
│   ├── fetcher.js        # StrategyFetcher: Get source from JoinQuant API
│   ├── loader.js         # StrategyLoader: Load local .py/.json strategies
│   └── strategy-discover.js  # Community listV2 API crawler + data store
├── backtest/
│   └── runner.js         # BacktestRunner: Clone → Poll → Parse results
├── pipelines/
│   ├── community.js      # CommunityPipeline: post → fetch → backtest
│   └── custom.js         # CustomPipeline: local file → backtest
├── strategies/           # Python strategy files (cloned strategies saved here)
├── data/                 # Discovery state (gitignored)
│   ├── discovered.json   # All discovered strategies (keyed by postId)
│   └── copy-queue.json  # Pending strategies sorted by composite score
├── tests/               # Unit tests (30 cases, all pass)
└── index.js             # CLI entry point
```

## Quick Start

```bash
cd ~/repos/join-quant
npm install

# Discover strategies (2 API calls ≈ 147 strategies)
node utils/strategy-discover.js 2

# Show discovery status
node utils/strategy-discover.js status

# Run the daily pipeline (discovery + clone loop with WeChat alerts)
node utils/strategy-daily.js
```

## Data Files

| File | Description |
|------|-------------|
| `data/discovered.json` | All strategies ever discovered, deduplicated by postId |
| `data/copy-queue.json` | Pending strategies sorted by composite score (`likes + clones×0.5`), excludes already-copied |


**Composite Score** = `likes + clones × 0.5` — weights community validation (clones) alongside author popularity (likes).

**Top Strategies in Queue:**
1. 【量化课堂】多因子策略入门 (likes=2436, clones=58610, score=31741)
2. 【网格交易策略-年化30%+】 (likes=477, clones=8069, score=4511)
3. 收益狂飙，年化收益100% (likes=749, clones=6988, score=4243)

## Installation

```bash
cd ~/repos/join-quant
npm install
```

## Configuration

```bash
# .env
JOINQUANT_USERNAME=15656096430
JOINQUANT_PASSWORD=your_password_here
```

## Cron Job (Daily)


Set up via OpenClaw cron:

```bash
# Daily at 9:00 AM Shanghai time
openclaw cron add \
  --name "join-quant daily pipeline" \
  --schedule "cron 0 9 * * *" \
  --tz "Asia/Shanghai" \
  --session-target "isolated" \
  --payload.kind "agentTurn" \
  --payload.message "Run: cd ~/repos/join-quant && node utils/strategy-daily.js"
```

The cron runs in an isolated session so it doesn't block your main chat.

Or export directly:

```bash
export JOINQUANT_PASSWORD=your_password_here
```

## CLI Usage

### Community Post Backtest

Run a backtest for a strategy from a JoinQuant community post:

```bash
node index.js community <postId> <backtestId> [replyId]

# Example:
node index.js community 5aa05159e33a10f96fd215cfeb59137c 5c94c550e05e21cb0227715f0c7451ce
```

### Custom Strategy Backtest

Run a backtest for an existing strategy already on JoinQuant (by backtestId):

```bash
node index.js custom --backtestId <backtestId>

# Example:
node index.js custom --backtestId 92a25fb27fd006b1f6b995dcc9533a83
```

Load and run a local strategy file:

```bash
node index.js custom ./strategies/my-strategy.py
```

### Login & Status

```bash
node index.js login    # Force fresh login
node index.js status  # Show cached cookie status
node index.js list    # List local strategies in ./strategies/
node index.js help    # Show full help
```

## Module Usage

### LoginManager

```javascript
const { LoginManager } = require('./auth/login');

const lm = new LoginManager('./auth/cookies.json', {
  username: '15656096430',
  password: process.env.JOINQUANT_PASSWORD
});

// Ensure logged in (uses cache if valid)
await lm.ensureLogin();
const { cookies, pageToken } = lm.getCookies();

// Get browser context with cookies pre-loaded
const { browser, context, page } = await lm.getBrowserContext();

// Force fresh login
const fresh = await lm.forceLogin();
```

### BacktestRunner

```javascript
const { BacktestRunner } = require('./backtest/runner');

const runner = new BacktestRunner({
  loginManager: lm,
  pollIntervalMs: 10000,  // Poll every 10s (default)
  maxPollAttempts: 120     // Max 20min wait (default)
});

// Run backtest for a community post strategy
const result = await runner.run({
  postId: '5aa05159e33a10f96fd215cfeb59137c',
  backtestId: '5c94c550e05e21cb0227715f0c7451ce'
});

// result = {
//   backtestId: 'new-backtest-id-here',
//   status: 'completed',
//   results: {
//     annualReturn: 1.878,      // 187.8%
//     cumulativeReturn: 213.27, // 21327%
//     maxDrawdown: 0.2357,      // 23.57%
//     sharpe: 6.30,
//     winRatio: 0.6427,         // 64.27%
//     tradingDays: 1269,
//     ...
//   }
// }

// Poll results for an existing backtest
const existing = await runner.pollResults('existing-backtest-id');
```

### StrategyLoader

```javascript
const { StrategyLoader } = require('./strategy/loader');

const loader = new StrategyLoader({
  baseDir: './strategies'  // Default: ./strategies
});

// Load Python file
const strategy = await loader.load('./strategies/ma-cross.py');
// strategy = {
//   name: 'ma-cross',
//   sourceCode: '...',
//   language: 'python',
//   path: '/full/path/to/ma-cross.py',
//   metadata: { clonedFrom: '...', packages: [...] }
// }

// Load JSON config
const config = await loader.load('./strategies/my-config.json');
// config.params = { initCash: 200000, frequency: 'daily', ... }

// List all strategies
const all = loader.list();
```

### CommunityPipeline

```javascript
const { CommunityPipeline } = require('./pipelines/community');

const pipeline = new CommunityPipeline({ loginManager: lm });

const result = await pipeline.run({
  postId: '5aa05159e33a10f96fd215cfeb59137c',
  backtestId: '5c94c550e05e21cb0227715f0c7451ce'
});

// result = {
//   pipelineId: 'pipeline_5aa05159e33a10f96fd215cfeb59137c_1715272800000',
//   postId: '5aa05159e33a10f96fd215cfeb59137c',
//   newBacktestId: 'clone-backtest-id',
//   status: 'completed',
//   results: { ... },
//   sourceCodeFetched: true,
//   sourceCodeLength: 10057,
//   durationMs: 45000
// }
```

### CustomPipeline

```javascript
const { CustomPipeline } = require('./pipelines/custom');

const pipeline = new CustomPipeline({ loginManager: lm });

// Run existing backtestId
const result = await pipeline.runFromBacktestId('existing-backtest-id');

// Run from local file
const result2 = await pipeline.runFromFile('./strategies/my-strategy.py', {
  backtestId: 'optional-override-backtest-id'
});

// List available strategies
const strategies = pipeline.listStrategies();
```

## API Results Format

All backtest results follow this normalized format:

```javascript
{
  // Performance
  annualReturn: 1.878,        // 年化收益 (1.0 = 100%)
  cumulativeReturn: 213.27,   // 累计收益 (213.27 = 21327%)
  benchmarkReturn: 45.5,      // 基准收益

  // Risk metrics
  maxDrawdown: 0.2357,        // 最大回撤 (0.24 = 24%)
  volatility: 0.32,           // 策略波动率
  benchmarkVolatility: 0.25,

  // Ratios
  sharpe: 6.30,
  sortino: 4.20,
  information: 2.10,
  alpha: 0.15,
  beta: 0.80,

  // Trading stats
  tradingDays: 1269,
  winRatio: 0.6427,           // 胜率 (0.64 = 64%)
  dayWinRatio: 0.55,
  profitLossRatio: 1.80,
  winCount: 812,
  loseCount: 457
}
```

## Testing

```bash
npm test
```

## Known Limitations

### runList API (Clone Strategy)

The `POST /algorithm/index/runList` API (clone strategy) does not work via raw HTTP with standard cookies. The browser JavaScript environment maintains additional session state that enables this call. The pipeline works around this by using Playwright to click the "克隆策略" button directly in the browser, which successfully creates a new backtest.

### JQData

JQData is a **data API only** (market data, fundamentals, etc.). It does not include a backtest execution engine. The backtest runner in this pipeline uses the JoinQuant platform's own backtest engine via browser automation.

### Strategy Upload (Custom Strategies)

JoinQuant does not expose a public API for uploading strategy code. Custom strategy support in this pipeline currently requires the strategy to already exist on JoinQuant (provide an existing backtestId). Support for code upload is planned for future versions.

## License

MIT