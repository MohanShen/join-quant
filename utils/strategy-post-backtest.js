/**
 * strategy-post-backtest.js
 *
 * Flow: CDP (reuse existing Chrome) -> Create new strategy -> Paste code -> Save -> Run backtest -> Poll -> Extract metrics
 *
 * Usage:
 *   node utils/strategy-post-backtest.js <path-to-strategy.py> [title]
 *
 * Environment:
 *   JQ_CDP_URL   — Chrome debugging URL (default: http://localhost:9225)
 *   JOINQUANT_USERNAME  — JQ account (default: 15656096430)
 *   JOINQUANT_PASSWORD   — JQ password (required if CDP approach fails)
 */

const { chromium } = require('playwright');
const { StrategyLoader } = require('./loader');
const path = require('path');
const fs   = require('fs');

const JQ_BASE = 'https://www.joinquant.com';
const POLL_INTERVAL_MS = 5000;
const MAX_POLL_MS = 20 * 60 * 1000;

const JOINQUANT_USERNAME = process.env.JOINQUANT_USERNAME || '15656096430';
const JOINQUANT_PASSWORD = process.env.JOINQUANT_PASSWORD;

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function domSnapshot(page) {
  try {
    return await page.evaluate(() => {
      const lines = (document.body?.innerText || '').split('\n').filter(l => l.trim());
      return lines.slice(0, 300).join('\n');
    });
  } catch { return ''; }
}

// ── Create new strategy ─────────────────────────────────────────────────────
async function createNewStrategy(page) {
  console.log('[post] Creating new stock strategy...');
  await page.goto(`${JQ_BASE}/algorithm/index/new?restore=0&type=stock&baseCapital=100000`, {
    waitUntil: 'domcontentloaded', timeout: 30000
  });
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
async function saveStrategy(page) {
  console.log('[post] Saving...');
  try {
    await page.click('text=保存', { timeout: 3000 });
  } catch {
    await page.keyboard.press('Control+s');
  }
  await sleep(2000);
  console.log('[post] Saved');
}

// ── Run backtest ─────────────────────────────────────────────────────────────
async function runBacktest(page) {
  console.log('[post] Starting backtest (编译运行)...');
  try {
    await page.click('text=编译运行', { exact: true, timeout: 5000 });
  } catch {
    const clicked = await page.evaluate(() => {
      const all = document.querySelectorAll('*');
      for (const el of all) {
        if ((el.textContent||'').trim() === '编译运行') { el.click(); return true; }
      }
      return false;
    });
    if (!clicked) throw new Error('编译运行 button not found');
  }
  await sleep(3000);
  console.log('[post] Backtest triggered');
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

      const elapsed = Math.round((Date.now()-start)/1000);
      const prog = `${Math.floor(elapsed/60)}m ${elapsed%60}s`;
      process.stdout.write(`\r[post] Running: ${prog}...   \r`);
    }
    return { success: false, error: 'Timeout' };
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

// ── Main ─────────────────────────────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2);
  if (args.length < 1) {
    console.error('Usage: node strategy-post-backtest.js <path-to-strategy.py> [title]');
    process.exit(1);
  }

  const strategyPath = path.resolve(args[0]);
  const customTitle  = args[1] || null;

  const loader = new StrategyLoader();
  let strategy;
  try {
    strategy = await loader.load(strategyPath);
  } catch (err) {
    console.error(`[post] Load error: ${err.message}`); process.exit(1);
  }
  const title = customTitle || strategy.name || path.basename(strategyPath);
  const code  = strategy.sourceCode;
  console.log(`[post] Strategy: "${title}" (${code.length} chars)`);

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

    // ── Full workflow ────────────────────────────────────────────────
    // Use a FRESH page for the editor workflow.
    const editorPage = await ctx.newPage();
    const algorithmId = await createNewStrategy(editorPage);
    console.log(`[post] Editor ready: ${editorPage.url().substring(0, 80)}`);
    await sleep(2000);
    await pasteCode(editorPage, code);
    await saveStrategy(editorPage);
    await runBacktest(editorPage);
    const result = await pollUntilComplete(editorPage, algorithmId);

    console.log('\n========== BACKTEST RESULT ==========');
    console.log(`Strategy:    ${title}`);
    console.log(`algorithmId: ${algorithmId}`);
    if (result.success) {
      const r = result.row || {};
      console.log(`Status:      ✅ 回测完成`);
      console.log(`回测时间:    ${r.time || 'N/A'}`);
      console.log(`时间范围:    ${r.range || 'N/A'}`);
      console.log(`运行频率:    ${r.freq || 'N/A'}`);
      console.log(`策略收益:    ${r.return_ || 'N/A'}`);
      console.log(`最大回撤:    ${r.maxdd || 'N/A'}`);
      console.log(`阿尔法:      ${r.alpha || 'N/A'}`);
      console.log(`贝塔:        ${r.beta || 'N/A'}`);
      console.log(`夏普比率:    ${r.sharpe || 'N/A'}`);
    } else {
      console.log(`Status:      ❌ ${result.error}`);
    }
    console.log('====================================\n');

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

    const editorPage2 = await ctx.newPage();
    const algorithmId = await createNewStrategy(editorPage2);
    console.log(`[post] Editor ready: ${editorPage2.url().substring(0, 80)}`);
    await sleep(3000);
    await pasteCode(editorPage2, code);
    await saveStrategy(editorPage2);
    await runBacktest(editorPage2);
    const result = await pollUntilComplete(editorPage2, algorithmId);

    console.log('\n========== BACKTEST RESULT ==========');
    console.log(`Strategy:    ${title}`);
    console.log(`algorithmId: ${algorithmId}`);
    if (result.success) {
      const r = result.row || {};
      console.log(`Status:      ✅ 回测完成`);
      console.log(`回测时间:    ${r.time || 'N/A'}`);
      console.log(`时间范围:    ${r.range || 'N/A'}`);
      console.log(`运行频率:    ${r.freq || 'N/A'}`);
      console.log(`策略收益:    ${r.return_ || 'N/A'}`);
      console.log(`最大回撤:    ${r.maxdd || 'N/A'}`);
      console.log(`阿尔法:      ${r.alpha || 'N/A'}`);
      console.log(`贝塔:        ${r.beta || 'N/A'}`);
      console.log(`夏普比率:    ${r.sharpe || 'N/A'}`);
    } else {
      console.log(`Status:      ❌ ${result.error}`);
    }
    console.log('====================================\n');
  }

  if (browser) { try { await browser.close(); } catch {} }
  return cdpSuccess
    ? { status: 'completed via CDP' }
    : { status: 'completed via persistent profile' };
}

main().catch(err => { console.error('Fatal:', err.message); process.exit(1); });
