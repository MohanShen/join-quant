/**
 * strategy-post-backtest.js
 *
 * Flow: CDP (reuse existing Chrome) -> Create new strategy -> Set backtest window/capital
 *       -> Paste code -> Save -> Run backtest -> Poll -> Extract metrics -> Verify window ran
 *
 * Usage:
 *   node utils/strategy-post-backtest.js <path-to-strategy.py> [title] [options]
 *
 * Options (autoresearch harness — see research/harness.md):
 *   --window <train|val>           Frozen backtest window (research/harness.md). Sets start/end dates.
 *                                  NOTE: holdout / any 2025+ window is HARD-BLOCKED (reserved
 *                                  OOS) unless JQ_ALLOW_OOS=1 (user-only private final test).
 *   --start <YYYY-MM-DD>           Explicit start date (overrides --window).
 *   --end   <YYYY-MM-DD>           Explicit end date (overrides --window).
 *   --capital <N>                  Base capital in yuan (default 1000000 = harness ¥1M).
 *   If neither --window nor --start/--end is given, JQ's default window is used and
 *   window verification is SKIPPED (ad-hoc mode; not valid for logging experiments).
 *
 * Environment:
 *   JQ_CDP_URL   — Chrome debugging URL (default: http://localhost:9225)
 *   JOINQUANT_USERNAME  — JQ account (default: 15656096430)
 *   JOINQUANT_PASSWORD   — JQ password (required if CDP approach fails)
 *   JQ_BASE_CAPITAL — default base capital if --capital omitted
 */

const { chromium } = require('playwright');
const { StrategyLoader } = require('./loader');
const path = require('path');
const fs   = require('fs');

const JQ_BASE = 'https://www.joinquant.com';
const POLL_INTERVAL_MS = 5000;
// Cost control is a PRE-START USAGE GATE, not cancellation: before creating a backtest we
// check today's used-minutes; if used >= USAGE_LIMIT we don't start (emit USAGE-STOP). A
// running backtest is left to finish (its runtime is billed — accepted). Cancellation is
// kept ONLY as a last-resort safety net at MAX_POLL_MS, so a truly stuck run can't block
// the batch forever; normal slow backtests finish well before it.
const MAX_POLL_MS = parseInt(process.env.JQ_MAX_POLL_MS || String(5 * 60 * 1000), 10);   // safety cap: hangs never finish; normal runs ~25s
const USAGE_LIMIT = parseInt(process.env.JQ_USAGE_LIMIT || '55', 10);   // daily used-minutes ceiling to start new runs

const JOINQUANT_USERNAME = process.env.JOINQUANT_USERNAME || '15656096430';
const JOINQUANT_PASSWORD = process.env.JOINQUANT_PASSWORD;
const DEFAULT_CAPITAL = parseInt(process.env.JQ_BASE_CAPITAL || '1000000', 10);

// Frozen backtest windows — MUST match research/harness.md (current epoch).
// HOLDOUT end rolls forward to "today" (true out-of-sample).
function todayISO() { return new Date().toISOString().slice(0, 10); }
const WINDOWS = {
  train:   { start: '2022-01-01', end: '2023-12-31' },
  val:     { start: '2024-01-01', end: '2024-12-31' },
  holdout: { start: '2025-01-01', end: todayISO() },
};

// Enclosed-environment guard: the 2025-01-01→now window is a reserved OUT-OF-SAMPLE set
// that the autoresearch pipeline must NEVER backtest (research/harness.md). This hard-block
// makes it a code guarantee, not an instruction — no agent can touch OOS even via custom
// --start/--end that overlaps 2025+. Only the user, for a private final test, may override
// with JQ_ALLOW_OOS=1.
const OOS_CUTOFF = '2025-01-01';
function assertNotOOS(window) {
  if (!window || process.env.JQ_ALLOW_OOS === '1') return;
  const touchesOOS = (window.start && window.start >= OOS_CUTOFF) ||
                     (window.end && window.end >= OOS_CUTOFF);   // ISO dates compare lexicographically
  if (touchesOOS) {
    throw new Error(
      `OOS-BLOCKED: window "${window.name}" (${window.start}→${window.end}) reaches into the reserved ` +
      `out-of-sample period (>= ${OOS_CUTOFF}). The frozen harness forbids backtesting 2025-01-01→now — ` +
      `the research loop may only use train (2022-2023) and val (2024). ` +
      `(User-only override for a private final test: JQ_ALLOW_OOS=1.)`
    );
  }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── CLI parsing ──────────────────────────────────────────────────────────────
// Returns { strategyPath, title, window, baseCapital } where window is
// { name, start, end } or null (ad-hoc mode).
function parseArgs(argv) {
  const positional = [];
  const opt = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) opt[a.slice(2)] = argv[++i];
    else positional.push(a);
  }
  const baseCapital = parseInt(opt.capital || DEFAULT_CAPITAL, 10);

  let window = null;
  if (opt.start || opt.end) {
    if (!opt.start || !opt.end) throw new Error('--start and --end must be given together');
    window = { name: opt.window || 'custom', start: opt.start, end: opt.end };
  } else if (opt.window) {
    const w = WINDOWS[opt.window];
    if (!w) throw new Error(`Unknown --window "${opt.window}". Use train|val|holdout or --start/--end.`);
    window = { name: opt.window, start: w.start, end: w.end };
  }
  assertNotOOS(window);   // hard-block 2025+ OOS unless JQ_ALLOW_OOS=1
  return { strategyPath: positional[0], title: positional[1] || null, window, baseCapital };
}

// Parse JQ result-row "时间范围" like "2022-01-01 - 2023-12-31" or "2022-01-01 至 2024-01-01".
function parseRange(rangeStr) {
  const m = (rangeStr || '').match(/(\d{4}-\d{2}-\d{2}).*?(\d{4}-\d{2}-\d{2})/);
  return m ? { start: m[1], end: m[2] } : null;
}

function daysBetween(a, b) {
  return Math.abs((new Date(a) - new Date(b)) / 86400000);
}

async function domSnapshot(page) {
  try {
    return await page.evaluate(() => {
      const lines = (document.body?.innerText || '').split('\n').filter(l => l.trim());
      return lines.slice(0, 300).join('\n');
    });
  } catch { return ''; }
}

// ── Create new strategy ─────────────────────────────────────────────────────
// The backtest window + base capital are set via URL params to /algorithm/index/new
// (confirmed: JQ carries startTime/endTime/baseCapital into #startTime/#endTime/
// #daily_backtest_capital_base_box). ensureBacktestWindow() re-checks & fixes them.
async function createNewStrategy(page, baseCapital = DEFAULT_CAPITAL, window = null) {
  console.log(`[post] Creating new stock strategy (baseCapital=${baseCapital}` +
              (window ? `, window=${window.start}→${window.end})...` : ')...'));
  let newUrl = `${JQ_BASE}/algorithm/index/new?restore=0&type=stock&baseCapital=${baseCapital}`;
  if (window) newUrl += `&startTime=${window.start}&endTime=${window.end}`;
  await page.goto(newUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
  // JQ client-side redirects to editor URL. Wait for the URL to contain 'algorithmId='
  await page.waitForFunction(() => window.location.href.includes('algorithmId='), { timeout: 15000 });
  await sleep(2000); // give Ace time to fully initialize

  const url = page.url();
  const m = url.match(/algorithmId=([a-f0-9]{32})/);
  if (m) { console.log(`[post] Strategy created, algorithmId=${m[1]}`); return m[1]; }

  // Fallback: extract from DOM
  const algId = await page.evaluate(() => {
    const scripts = document.querySelectorAll('script');
    for (const s of scripts) {
      const match = s.textContent?.match(/algorithmId[\W]+([a-f0-9]{32})/);
      if (match) return match[1];
    }
    const inputs = document.querySelectorAll('input, [_algorithmid]');
    for (const i of inputs) {
      const v = i.value || i.getAttribute('_algorithmid');
      if (v && /^[a-f0-9]{32}$/.test(v)) return v;
    }
    return null;
  });

  if (algId) { console.log(`[post] algorithmId=${algId} from DOM`); return algId; }
  throw new Error(`Cannot find algorithmId in: ${url}\nDOM:\n${(await domSnapshot(page)).substring(0, 500)}`);
}

// ── Ensure backtest window is set (confirm URL params, fix via DOM if needed) ─
// Primary path: startTime/endTime URL params on /algorithm/index/new (set in
// createNewStrategy). Here we read the actual #startTime/#endTime datepicker inputs
// and, if they don't match, set them directly (they're readonly for typing but JS
// .value + change works). Verified selectors: #startTime, #endTime.
async function ensureBacktestWindow(page, window) {
  if (!window) { console.log('[post] No window given — using JQ default range (ad-hoc mode)'); return; }
  await sleep(500);

  const outcome = await page.evaluate(({ start, end }) => {
    const s = document.getElementById('startTime');
    const e = document.getElementById('endTime');
    if (!s || !e) return { ok: false, reason: 'inputs-missing' };
    const setVal = (el, v) => {
      const proto = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
      proto.set.call(el, v);
      el.dispatchEvent(new Event('input',  { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      el.dispatchEvent(new Event('blur',   { bubbles: true }));
    };
    let fixed = false;
    if (s.value !== start) { setVal(s, start); fixed = true; }
    if (e.value !== end)   { setVal(e, end);   fixed = true; }
    return { ok: true, fixed, s: s.value, e: e.value };
  }, window);

  if (!outcome.ok) {
    console.log(`[post] ⚠ #startTime/#endTime not found — verification will catch any mismatch.`);
  } else {
    console.log(`[post] Window ${window.name}: ${outcome.s} → ${outcome.e}` +
                (outcome.fixed ? ' (set via DOM)' : ' (from URL params)'));
  }
  await sleep(500);
}

// ── Paste code via Ace editor ────────────────────────────────────────────────
async function pasteCode(page, code) {
  console.log('[post] Pasting code into Ace editor...');

  // Wait for Ace to be fully ready (JQ loads Ace dynamically)
  await page.waitForFunction(
    () => window.ace && document.querySelector('.ace_editor') &&
          window.ace.edit(document.querySelector('.ace_editor')).getSession,
    { timeout: 15000 }
  );
  await sleep(500);

  // Set via Ace editor API (most reliable — directly manipulates editor session)
  const result = await page.evaluate((c) => {
    const div = document.querySelector('.ace_editor');
    if (!div || !window.ace) return 'No Ace';
    const editor = window.ace.edit(div);
    editor.setValue(c, -1); // -1 = keep cursor, don't select all
    return 'Ace OK: ' + editor.getValue().length + ' chars';
  }, code);
  console.log('[post] Ace:', result);

  // Sync to hidden textarea (JQ reads from it on save — not the Ace session)
  await page.evaluate((c) => {
    const ta = document.getElementById('code');
    if (!ta) return;
    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
    setter.call(ta, c);
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    ta.dispatchEvent(new Event('change', { bubbles: true }));
  }, code);

  // Verify
  const verify = await page.evaluate(() => {
    const div = document.querySelector('.ace_editor');
    if (div && window.ace) {
      const ed = window.ace.edit(div);
      return 'Ace: ' + ed.getValue().length + ' chars | textarea: ' + (document.getElementById('code')?.value?.length || 0);
    }
    return 'no editor';
  });
  console.log('[post] Verify:', verify);
}

// ── Save ─────────────────────────────────────────────────────────────────────
// Use the stable button IDs (JQ's editor renders "保 存" with a space, so text= fails).
async function saveStrategy(page) {
  console.log('[post] Saving...');
  try {
    await page.click('#algo-save-button', { timeout: 5000 });
  } catch {
    await page.keyboard.press('Control+s');
  }
  await sleep(2000);
  console.log('[post] Saved');
}

// ── Run backtest ─────────────────────────────────────────────────────────────
// #validate-button = 编译运行 (compile + run daily backtest). Text= matches multiple
// nested spans, so use the id.
async function runBacktest(page) {
  console.log('[post] Starting backtest (编译运行)...');
  try {
    await page.click('#validate-button', { timeout: 5000 });
  } catch {
    const clicked = await page.evaluate(() => {
      const el = document.getElementById('validate-button') || document.getElementById('buildBtn');
      if (el) { el.click(); return true; }
      return false;
    });
    if (!clicked) throw new Error('编译运行 button (#validate-button) not found');
  }
  await sleep(3000);

  // JQ shows "编译失败:当前并行编译或回测数量最多2个" (and syntax errors) as a transient
  // toast/notice on the EDITOR page — check it now, before navigating to buildList,
  // otherwise a missed toast makes us poll buildList until MAX_POLL_MS.
  const notice = await page.evaluate(() => {
    const txt = document.body?.innerText || '';
    const m = txt.match(/编译失败[:：][^\n]{0,40}/);
    return m ? m[0] : '';
  });
  if (notice) {
    const rateLimited = /并行|最多|数量/.test(notice);
    console.log(`[post] ⚠ ${notice} ${rateLimited ? '(concurrency cap)' : '(compile error)'}`);
    return { error: notice, rateLimited };
  }
  console.log('[post] Backtest triggered');
  return { error: null };
}

// ── Read JQ's daily free-runtime counter via API ────────────────────────────
// GET /algorithm/index/statistics → {data:{duration:{used,free}, running:[...]}}.
// Direct query (uses the page's logged-in cookies) — more reliable than DOM scraping.
// Emits a machine-readable QUOTA line for the batch runner's budget guard, incl. the
// count of currently-running backtests (each occupies one of JQ's 2 slots + bills).
async function readQuota(page) {
  try {
    const q = await page.evaluate(async () => {
      const r = await fetch('/algorithm/index/statistics', { credentials: 'include' });
      const j = await r.json();
      const d = j && j.data && j.data.duration;
      const running = (j && j.data && j.data.running) || [];
      return d ? { used: d.used, free: d.free, running: running.length } : null;
    });
    console.log(q ? `QUOTA\tused=${q.used}\tfree=${q.free}\trunning=${q.running}` : 'QUOTA\tunknown');
  } catch { console.log('QUOTA\tunknown'); }
}

// Pre-start usage gate: if today's used-minutes already meets/exceeds USAGE_LIMIT, do NOT
// start a new backtest. Emits USAGE-STOP (the batch runner reads it and halts). Returns
// true if ok to proceed.
async function usageGate(page) {
  const u = await page.evaluate(async () => {
    try { return (await (await fetch('/algorithm/index/statistics', { credentials: 'include' })).json()).data.duration; }
    catch { return null; }
  });
  if (u && u.used != null && u.used >= USAGE_LIMIT) {
    console.log(`USAGE-STOP\tused=${u.used}\tlimit=${USAGE_LIMIT}`);
    return false;
  }
  console.log(`[post] usage ${u ? u.used : '?'}/${USAGE_LIMIT}min — ok to run`);
  return true;
}

// Parse a JQ duration string like "41分14秒" / "1时02分" / "37秒" → minutes.
function parseCnDuration(s) {
  if (!s) return 0;
  const h = (s.match(/(\d+)\s*(?:时|小时)/) || [])[1];
  const m = (s.match(/(\d+)\s*分/) || [])[1];
  const sec = (s.match(/(\d+)\s*秒/) || [])[1];
  return (h ? +h * 60 : 0) + (m ? +m : 0) + (sec ? +sec / 60 : 0);
}

// Live run state from the statistics API: daily used/free minutes + THIS backtest's
// elapsed (matched by algorithmId). Used to cancel only when budget requires it.
async function fetchRunState(page, algorithmId) {
  try {
    return await page.evaluate(async (algId) => {
      const r = await fetch('/algorithm/index/statistics', { credentials: 'include' });
      const j = await r.json();
      const d = (j && j.data && j.data.duration) || {};
      const running = (j && j.data && j.data.running) || [];
      const mine = running.find(x => x.id === algId);
      return { used: d.used, free: d.free, usedSec: mine ? mine.usedSec : null, runningCount: running.length };
    }, algorithmId);
  } catch { return null; }
}

// ── Cancel a running backtest to stop billing ───────────────────────────────
// The #cancel-daily-backtest-button only opens a "确实要取消?" confirm dialog — clicking
// it does NOT cancel. The real cancel is the API the JS calls after confirmation:
//   Cy.ajax("/algorithm/index/cancel", { data:"backtestId="+backtestId })
// (jQuery-style, so it also sends X-Requested-With: XMLHttpRequest — required, else JQ
// returns a full error page). backtestId is the hidden #backtestId input on the editor
// page. We call it directly, which reliably stops the run AND works for any backtest id.
async function cancelBacktest(editorPage) {
  try {
    // backtestId is usually not on the editor DOM during a run; get it from the statistics
    // running list (sequential batch → the single running entry is ours).
    const bid = await editorPage.evaluate(async () => {
      const onPage = document.getElementById('backtestId')?.value;
      if (onPage) return onPage;
      try {
        const run = (await (await fetch('/algorithm/index/statistics', { credentials: 'include' })).json()).data.running || [];
        return run.length === 1 ? run[0].id : null;
      } catch { return null; }
    });
    if (!bid) { console.log('\n[post] ⚠ cancel: no backtestId found (backtest may not have started)'); return false; }
    // The cancel API is flaky — returns {"status":"2",msg:"系统繁忙"} intermittently; success is
    // status:"0". Retry a few times.
    for (let attempt = 1; attempt <= 5; attempt++) {
      const r = await editorPage.evaluate(async (id) => {
        try {
          const resp = await fetch('/algorithm/index/cancel', {
            method: 'POST', credentials: 'include',
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded' },
            body: 'backtestId=' + encodeURIComponent(id),
          });
          const body = await resp.text();
          let ok = false; try { ok = JSON.parse(body).status === '0'; } catch {}
          return { ok, body: body.replace(/\s+/g, ' ').slice(0, 70) };
        } catch (e) { return { ok: false, body: String(e).slice(0, 70) }; }
      }, bid);
      if (r.ok) { console.log(`\n[post] ⏹ cancelled backtestId=${bid.slice(0, 8)} (attempt ${attempt})`); await sleep(1000); return true; }
      console.log(`\n[post] cancel attempt ${attempt}: ${r.body}`);
      await sleep(4000);
    }
    console.log(`\n[post] ⚠ cancel failed after retries (backtestId=${bid.slice(0, 8)})`);
    return false;
  } catch (e) {
    console.log(`\n[post] ⚠ cancel failed: ${e.message.slice(0, 70)}`);
    return false;
  }
}

// Detect a compile/runtime error (Python traceback, syntax error, missing module) on the
// editor page or any of its iframes (JQ renders the run log in a frame). Reliable fast-fail:
// only real error output matches, so healthy strategies never trip it.
async function detectCompileError(page) {
  const RX = /Traceback \(most recent call last\)|SyntaxError[^\n]{0,60}|NameError[^\n]{0,60}|ImportError[^\n]{0,60}|IndentationError[^\n]{0,60}|invalid syntax|编译失败[:：][^\n]{0,50}|编译错误[^\n]{0,50}/;
  try {
    for (const t of [page, ...page.frames()]) {
      const hit = await t.evaluate((src) => {
        const rx = new RegExp(src);
        const m = (document.body ? document.body.innerText : '').match(rx);
        return m ? m[0].slice(0, 90) : null;
      }, RX.source).catch(() => null);
      if (hit) return hit;
    }
  } catch {}
  return null;
}

// ── Poll until done ─────────────────────────────────────────────────────────
// JoinQuant doesn't update the editor page on backtest completion — it shows
// results in a separate buildList page.  We navigate there and poll for "完成".
async function pollUntilComplete(page, algorithmId) {
  const start = Date.now();

  // First wait for the backtest to be submitted (JQ redirects to buildList)
  // Give the server a moment to register the submission
  await sleep(8000);

  // Navigate to buildList and poll there.  IMPORTANT: reload on each poll
  // iteration because JQ updates the status via XHR/JS — a static page load
  // won't reflect live status changes.
  const listPage = await (page.context()).newPage();
  try {
    // First load
    await listPage.goto(`${JQ_BASE}/algorithm/backtest/buildList?algorithmId=${algorithmId}`, {
      waitUntil: 'networkidle', timeout: 30000
    });
    await sleep(8000); // wait for backtest to be registered

    while (Date.now() - start < MAX_POLL_MS) {
      // Reload to get fresh status
      await listPage.reload({ waitUntil: 'networkidle', timeout: 30000 });
      const dom = await domSnapshot(listPage);

      if (dom.includes('完成')) {
        // Extract the latest backtest result row (skip table header row)
        const row = await listPage.evaluate(() => {
          const rows = document.querySelectorAll('table tbody tr');
          for (const row of rows) {
            const cells = Array.from(row.querySelectorAll('td'));
            // cells layout: [empty, name, time, range, duration, freq, status, return_, alpha, beta, sharpe, extra]
            // Header row check: cells[6] = '状态'. Data row: cells[6] = '完成' (status)
            const statusCell = cells[6]?.textContent?.trim() || '';
            if (cells.length >= 11 && statusCell === '完成') {
              return {
                name: cells[1]?.textContent?.trim(),
                time: cells[2]?.textContent?.trim(),
                range: cells[3]?.textContent?.trim(),
                duration: cells[4]?.textContent?.trim(),
                freq: cells[5]?.textContent?.trim(),
                status: statusCell,
                return_: cells[7]?.textContent?.trim(),
                maxdd: cells[8]?.textContent?.trim(),
                alpha: cells[9]?.textContent?.trim(),
                beta: cells[10]?.textContent?.trim(),
                sharpe: cells[11]?.textContent?.trim(),
              };
            }
          }
          // Fallback: look for any row with 完成 in non-header cells
          const allRows = document.querySelectorAll('tr');
          for (const row of allRows) {
            const cells = Array.from(row.querySelectorAll('td'));
            if (cells.length >= 11 && (cells[6]?.textContent?.trim() || '') === '完成') {
              return {
                name: cells[1]?.textContent?.trim(),
                time: cells[2]?.textContent?.trim(),
                range: cells[3]?.textContent?.trim(),
                duration: cells[4]?.textContent?.trim(),
                freq: cells[5]?.textContent?.trim(),
                status: cells[6]?.textContent?.trim(),
                return_: cells[7]?.textContent?.trim(),
                maxdd: cells[8]?.textContent?.trim(),
                alpha: cells[9]?.textContent?.trim(),
                beta: cells[10]?.textContent?.trim(),
                sharpe: cells[11]?.textContent?.trim(),
              };
            }
          }
          return null;
        });
        console.log(`\n[post] ✅ 回测完成 (${Math.round((Date.now()-start)/1000)}s)`);
        return { success: true, dom, row };
      }

      if (dom.includes('失败') || dom.includes('错误')) {
        return { success: false, dom, error: '回测失败' };
      }

      // Compile/runtime error on the editor (traceback etc.) → fast-fail, don't wait for the cap.
      const cerr = await detectCompileError(page);
      if (cerr) return { success: false, error: cerr, compileError: true };

      // No early cancel — let the backtest run to completion (cost accepted; gated at start).
      const elapsed = Math.round((Date.now()-start)/1000);
      const prog = `${Math.floor(elapsed/60)}m ${elapsed%60}s`;
      process.stdout.write(`\r[post] Running: ${prog}...   \r`);
    }
    // Safety net only: a truly stuck run (> MAX_POLL_MS) — last-resort cancel via the API
    // so it can't block the batch forever. Normal slow backtests finish well before this.
    await cancelBacktest(page);
    return { success: false, stopped: true, error: `safety-cap (>${Math.round(MAX_POLL_MS/1000)}s)` };
  } finally {
    await listPage.close();
  }
}

// ── Extract metrics ─────────────────────────────────────────────────────────
function extractMetrics(dom) {
  const patterns = {
    strategyReturn:   [/策略收益[^%\d]*(-?\d+\.?\d*)%/],
    benchmarkReturn:  [/基准收益[^%\d]*(-?\d+\.?\d*)%/],
    annualReturn:     [/年化收益[^%\d]*(-?\d+\.?\d*)%/],
    alpha:            [/阿尔法[^-\d]*(-?\d+\.?\d*)/],
    beta:             [/贝塔[^-\d]*(-?\d+\.?\d*)/],
    sharpe:           [/夏普比率[^-\d]*(-?\d+\.?\d*)/],
    maxDrawdown:      [/最大回撤[^%\d]*(\d+\.?\d*)%/],
    winRate:          [/胜率[^%\d]*(\d+\.?\d*)%/],
  };
  const m = {};
  for (const [k, pats] of Object.entries(patterns)) {
    for (const p of pats) {
      const match = dom.match(p);
      if (match) { m[k] = match[1]; break; }
    }
  }
  return m;
}

// Annualize a total return over `days` calendar days: (1+total)^(365/days) − 1.
// JQ's buildList row exposes TOTAL strategy return, not annualized — so we compute it
// ourselves from the actual window length (see research/harness.md §4).
function annualizeReturn(totalPct, days) {
  if (totalPct == null || !days || days <= 0) return null;
  const total = totalPct / 100;
  return (Math.pow(1 + total, 365 / days) - 1) * 100;
}

function numPct(s) {
  const m = (s || '').match(/-?\d+\.?\d*/);
  return m ? parseFloat(m[0]) : null;
}

// ── Report + verify the window that actually ran ────────────────────────────
// Prints the human summary AND a machine-readable line the /run-experiment loop
// can grep (single line, tab-separated):
//   SUMMARY\t<window>\t<start>\t<end>\t<days>\t<total%>\t<annual%>\t<sharpe>\t<maxdd%>\t<status>
// annual% is computed from total% over the actual window (JQ gives only total).
// status ∈ completed | window-mismatch | failed
function reportResult(title, algorithmId, result, requestedWindow) {
  console.log('\n========== BACKTEST RESULT ==========');
  console.log(`Strategy:    ${title}`);
  console.log(`algorithmId: ${algorithmId}`);

  let status = 'failed';
  const r = (result && result.row) || {};
  const range = (r.range || '').replace(/\s+/g, ' ').trim();   // JQ cell may contain newlines
  const ran = parseRange(range);
  const days = ran ? Math.max(1, Math.round(daysBetween(ran.start, ran.end))) : null;
  const totalPct = numPct(r.return_);
  const annualPct = annualizeReturn(totalPct, days);
  const maxddPct = numPct(r.maxdd);
  const sharpe = numPct(r.sharpe);

  if (result && result.success && totalPct == null) {
    // Poll saw 完成 but no parseable metrics row (e.g. strategy made no trades).
    console.log(`Status:      ⚠ 回测完成但无可解析指标 — 视为 failed，不可记账`);
  } else if (result && result.success) {
    status = 'completed';
    console.log(`Status:      ✅ 回测完成`);
    console.log(`时间范围:    ${range || 'N/A'}${days ? ` (${days}天)` : ''}`);
    console.log(`运行频率:    ${r.freq || 'N/A'}`);
    console.log(`策略收益:    ${totalPct != null ? totalPct + '%' : 'N/A'} (总收益)`);
    console.log(`年化收益:    ${annualPct != null ? annualPct.toFixed(2) + '% (计算值)' : 'N/A'}`);
    console.log(`最大回撤:    ${maxddPct != null ? maxddPct + '%' : 'N/A'}`);
    console.log(`夏普比率:    ${sharpe != null ? sharpe : 'N/A'}`);

    // Verify the window that actually ran matches what we requested.
    if (requestedWindow) {
      if (!ran) {
        status = 'window-mismatch';
        console.log(`⚠ WINDOW: could not parse actual range "${range}" — treat as mismatch.`);
      } else {
        const startOff = daysBetween(ran.start, requestedWindow.start);
        const endOff   = daysBetween(ran.end,   requestedWindow.end);
        // Start must be exact (±3 trading-calendar days); end tolerant for holdout "today".
        if (startOff > 3 || endOff > 10) {
          status = 'window-mismatch';
          console.log(`⚠ WINDOW MISMATCH: requested ${requestedWindow.start}→${requestedWindow.end}, ` +
                      `ran ${ran.start}→${ran.end} (startΔ=${startOff}d endΔ=${endOff}d). ` +
                      `DO NOT log this result — fix date-setting and rerun.`);
        } else {
          console.log(`✓ WINDOW OK: ran ${ran.start}→${ran.end} matches ${requestedWindow.name}`);
        }
      }
    }
  } else {
    status = (result && result.rateLimited)  ? 'rate-limited'
           : (result && result.compileError) ? 'compile-error'
           : (result && result.stopped)      ? 'slow-skipped'
           : 'failed';
    console.log(`Status:      ❌ ${result ? result.error : 'unknown'} [${status}]`);
  }
  console.log('====================================');

  const f = (x, d = 2) => (x == null ? '' : x.toFixed(d));
  const cells = [
    'SUMMARY',
    requestedWindow ? requestedWindow.name : 'adhoc',
    ran ? ran.start : '',
    ran ? ran.end : '',
    days || '',
    f(totalPct),
    f(annualPct),
    f(sharpe),
    f(maxddPct),
    status,
  ];
  console.log(cells.join('\t'));
  return status;
}

// ── Main ─────────────────────────────────────────────────────────────────────
async function main() {
  let parsed;
  try {
    parsed = parseArgs(process.argv.slice(2));
  } catch (err) {
    console.error(`[post] ${err.message}`); process.exit(1);
  }
  if (!parsed.strategyPath) {
    console.error('Usage: node strategy-post-backtest.js <path-to-strategy.py> [title] ' +
                  '[--window train|val|holdout | --start YYYY-MM-DD --end YYYY-MM-DD] [--capital N]');
    process.exit(1);
  }

  const strategyPath  = path.resolve(parsed.strategyPath);
  const { window, baseCapital } = parsed;

  const loader = new StrategyLoader();
  let strategy;
  try {
    strategy = await loader.load(strategyPath);
  } catch (err) {
    console.error(`[post] Load error: ${err.message}`); process.exit(1);
  }
  const title = parsed.title || strategy.name || path.basename(strategyPath);
  const code  = strategy.sourceCode;
  console.log(`[post] Strategy: "${title}" (${code.length} chars)` +
              (window ? ` | window=${window.name} ${window.start}→${window.end}` : ' | window=adhoc'));

  // ----------------------------------------------------------------
  // Browser setup
  // Approach 1 (best): CDP to existing Chrome at localhost:9225
  //   → No login, no CAPTCHA, instant reuse of your logged-in session
  // Approach 2: Persistent profile (only if CDP fails)
  //   → First run may need manual CAPTCHA; afterwards cached
  // ----------------------------------------------------------------
  let browser;

  const CDP_URL = process.env.JQ_CDP_URL || 'http://localhost:9225';

  // ── Approach 1: CDP ───────────────────────────────────────────────
  let cdpSuccess = false;
  try {
    console.log('[auth] Trying CDP at', CDP_URL, '...');
    browser = await chromium.connectOverCDP(CDP_URL);
    const ctx = browser.contexts()[0];

    // Reuse existing pages — NEVER close pages as that destroys the CDP
    // session's cookie context.  Find a valid logged-in page to use.
    const existingPages = await ctx.pages();
    const validPages = existingPages.filter(p =>
      !p.url().startsWith('chrome://') &&
      !p.url().startsWith('about:') &&
      !p.url().includes('/user/login')
    );
    if (validPages.length === 0) {
      throw new Error('No logged-in JQ page found — please open JoinQuant in the Chrome window and log in');
    }
    const hubPage = validPages[0];
    console.log('[auth] ✅ Connected to existing Chrome (no CAPTCHA needed)');
    cdpSuccess = true;

    // Pre-start usage gate — don't create/run a backtest if we're over the daily limit.
    if (!(await usageGate(hubPage))) { if (browser) { try { await browser.close(); } catch {} } return { status: 'usage-stop' }; }

    // ── Full workflow ────────────────────────────────────────────────
    // Use a FRESH page for the editor workflow.
    const editorPage = await ctx.newPage();
    const algorithmId = await createNewStrategy(editorPage, baseCapital, window);
    console.log(`[post] Editor ready: ${editorPage.url().substring(0, 80)}`);
    await sleep(2000);
    await readQuota(editorPage);
    await ensureBacktestWindow(editorPage, window);
    await pasteCode(editorPage, code);
    await saveStrategy(editorPage);
    const bt = await runBacktest(editorPage);
    const result = bt.error
      ? { success: false, error: bt.error, rateLimited: bt.rateLimited }
      : await pollUntilComplete(editorPage, algorithmId);
    reportResult(title, algorithmId, result, window);
    // Close the editor tab we created (NOT the logged-in hub page) so batch runs
    // don't accumulate hundreds of tabs. Session cookies live in the context.
    try { await editorPage.close(); } catch {}

  } catch (connErr) {
    // ── Approach 2: Persistent profile ──────────────────────────────
    if (browser) { try { await browser.close(); } catch {} }
    console.log('[auth] CDP failed:', connErr.message.substring(0, 100));
    console.log('[auth] Falling back to persistent profile...');

    if (!JOINQUANT_PASSWORD) {
      console.error('[auth] No JOINQUANT_PASSWORD set — persistent profile will need manual login');
    }

    const PROFILE_DIR = '/tmp/jq-auth-browser';
    if (!fs.existsSync(PROFILE_DIR)) fs.mkdirSync(PROFILE_DIR, { recursive: true });

    browser = await chromium.launchPersistentContext(PROFILE_DIR, {
      headless: false,
      executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      args: ['--no-sandbox'],
    });

    const ctx = browser.contexts ? browser.contexts()[0] : browser;
    const page = ctx.pages()[0] || await ctx.newPage();
    await page.goto(`${JQ_BASE}/algorithm/index/list`, { waitUntil: 'networkidle', timeout: 15000 });
    await sleep(1500);

    if (page.url().includes('/user/login')) {
      const bodyText = await page.evaluate(() => document.body.innerText);
      if (bodyText.includes('验证码') || bodyText.includes('拼图')) {
        console.log('[auth] ⚠️  CAPTCHA required — solve it in the browser window, then press Enter');
        await new Promise(r => process.stdin.once('data', r));
        if (page.url().includes('/user/login')) throw new Error('CAPTCHA not solved');
      } else {
        throw new Error(`Login page still showing — solve in browser, then press Enter`);
      }
    }
    console.log('[auth] ✅ Persistent profile ready');

    if (!(await usageGate(page))) { if (browser) { try { await browser.close(); } catch {} } return { status: 'usage-stop' }; }

    const editorPage2 = await ctx.newPage();
    const algorithmId = await createNewStrategy(editorPage2, baseCapital, window);
    console.log(`[post] Editor ready: ${editorPage2.url().substring(0, 80)}`);
    await sleep(3000);
    await readQuota(editorPage2);
    await ensureBacktestWindow(editorPage2, window);
    await pasteCode(editorPage2, code);
    await saveStrategy(editorPage2);
    const bt = await runBacktest(editorPage2);
    const result = bt.error
      ? { success: false, error: bt.error, rateLimited: bt.rateLimited }
      : await pollUntilComplete(editorPage2, algorithmId);
    reportResult(title, algorithmId, result, window);
    try { await editorPage2.close(); } catch {}
  }

  if (browser) { try { await browser.close(); } catch {} }
  return cdpSuccess
    ? { status: 'completed via CDP' }
    : { status: 'completed via persistent profile' };
}

main().catch(err => { console.error('Fatal:', err.message); process.exit(1); });
