# Changelog

## 2026-06-21 — Custom Strategy Backtest Pipeline ✅

**Milestone:** Full end-to-end custom strategy backtest pipeline completed.

### What works now

Upload any local Python strategy file → JoinQuant → run backtest → poll completion → extract metrics. Full automation, zero manual intervention (after one-time Chrome login).

### How to use

```bash
# 1. Start Chrome with debug port (one-time, keeps session)
nohup /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9225 \
  --user-data-dir=/tmp/jq-auth-browser \
  > /tmp/chrome-jq.log 2>&1 &
# (If first time: open Chrome, log into joinquant.com manually)

# 2. Run backtest on any local strategy file
cd ~/repos/join-quant
node utils/strategy-post-backtest.js strategies/我的策略.py "可选标题"
```

### Technical breakthroughs

- **CDP connection** — Connect to your running Chrome's debug port instead of launching a fresh browser. Bypasses JoinQuant's `httpOnly` cookie restriction (Playwright can't set those cookies).
- **Ace editor injection** — Use `window.ace.edit(div).setValue(code, -1)` to set code directly in JoinQuant's Ace editor, then sync the hidden textarea that JQ's backend reads on save.
- **Reload-based polling** — JoinQuant updates buildList status via XHR without page navigation. Poll by reloading the buildList URL each iteration, not by watching DOM changes.

### Script: `utils/strategy-post-backtest.js`

```
Flow: CDP connect → createNewStrategy → pasteCode (Ace) → save → runBacktest → pollUntilComplete → extractMetrics
```

| Step | Method |
|------|--------|
| Create strategy | Navigate to `/algorithm/index/new?restore=0&type=stock&baseCapital=100000`, wait for `algorithmId=` in URL |
| Paste code | `window.ace.edit(div).setValue(code, -1)` + textarea sync |
| Save | `page.evaluate()` click "保存" button |
| Trigger backtest | `page.evaluate()` click "编译运行" button |
| Poll completion | Reload `/algorithm/backtest/buildList?algorithmId=X` every 5s, detect "完成" |
| Extract results | Parse `table tbody tr` cells by index (status at cells[6], return at cells[7], alpha at cells[9], beta at cells[10], sharpe at cells[11]) |

---

## 2026-05-10 — VIP Access & Community Clone Pipeline

**Milestone:** Clone community strategies via browser automation (Playwright).

Key discovery: `POST /algorithm/index/runList` requires browser-level session context that raw HTTP can't provide. Solution: use Playwright to click "克隆策略" button directly.

---

## 2026-05-07 — JQData API

**Milestone:** JQData market data API access verified.
