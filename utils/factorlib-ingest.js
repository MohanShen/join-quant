/**
 * factorlib-ingest.js — pull JoinQuant's 因子看板 (factor dashboard) into the repo.
 *
 * What this is
 * ------------
 * JoinQuant evaluates a few hundred stock factors on a fixed grid and exposes
 * the result as JSON behind /view/factorlib/list:
 *
 *   GET /factorlib/index/getFctCategoryList          -> the 10 factor categories
 *   GET /factorlib/index/getSetting                  -> the legal knob values
 *   GET /factorlib/index/getList?categoryId=&universeType=&timeRange=
 *                               &commisionFee=&skipPaused=
 *
 * Each row carries the factor's plain-language formula (`algorithmIntro`) plus
 * quintile returns, IC mean, IR, Sharpe, drawdown and turnover.
 *
 * Why commisionFee matters
 * ------------------------
 * The dashboard DEFAULTS to `commisionFee=0`, i.e. no costs at all — the same
 * blind spot as `harness/harness.md` §2 zero slippage. The knob has three
 * settings and turning it on is brutal for high-turnover factors. Measured on
 * VROC12 (12-day volume rate of change, turnover 49.7%), top-quintile excess
 * annual return:
 *
 *     commisionFee=0    none                              -11.88%
 *     commisionFee=8    3‱ commission + 1‰ stamp duty     -27.76%
 *     commisionFee=18   the above + 1‰ slippage           -43.66%
 *
 * So this tool ingests BOTH the frictionless and the fully-costed run and
 * reports the erosion per factor. Rank on the costed column. A factor that only
 * works at commisionFee=0 is the factor-level twin of the ETF-discount families
 * in `wiki/families/` whose edge dies under mild frictions.
 *
 * Output
 *   research/factorlib/factors.tsv   - tracked, one row per factor, cost-aware
 *   research/factorlib/README.md     - tracked, generated summary + how to use
 *   data/factorlib/raw-*.json        - the untouched API payloads
 *
 * Usage:
 *   node utils/factorlib-ingest.js
 *   node utils/factorlib-ingest.js --universe zz1000 --range 3y
 *   node utils/factorlib-ingest.js --list-settings
 */

const fs = require('fs');
const path = require('path');
const jq = require('./jq-http');

const REPO = path.join(__dirname, '..');
const OUT_DIR = path.join(REPO, 'research', 'factorlib');
const RAW_DIR = path.join(REPO, 'data', 'factorlib');
const BASE = 'https://www.joinquant.com/factorlib/index';

/** Cost levels the dashboard offers. 0 is its default; 18 is the honest one. */
const FEE_NONE = '0';
const FEE_FULL = '18';
const FEE_LABEL = {
  '0': 'no costs',
  '8': '3‱ commission + 1‰ stamp duty',
  '18': '3‱ commission + 1‰ stamp duty + 1‰ slippage',
};

const num = v => { const n = parseFloat(v); return Number.isFinite(n) ? n : null; };
const pct = v => (v == null ? '' : (v * 100).toFixed(2));

/** The dashboard's own JSON envelope: {data, status, code, msg}. */
function unwrap(json) {
  const d = json && (json.data !== undefined ? json.data : json);
  if (!d) return [];
  if (Array.isArray(d)) return d;
  return Object.values(d).filter(x => x && typeof x === 'object' && x.factor_id);
}

function q(params) {
  return Object.entries(params).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');
}

async function getCategories() {
  const json = await jq.jqJson(`${BASE}/getFctCategoryList`);
  return (json && json.data) || [];
}

async function getSettings() {
  const json = await jq.jqJson(`${BASE}/getSetting`);
  return (json && json.data) || {};
}

/**
 * One factor-list pull. `categoryId=0` returns every factor.
 * The endpoint is order-sensitive under rapid fire, so callers space the calls.
 */
async function getList({ categoryId = 0, universe, range, fee, skipPaused = '1' }) {
  const url = `${BASE}/getList?${q({
    categoryId,
    universeType: universe,
    timeRange: range,
    commisionFee: fee,
    skipPaused,
  })}`;
  return unwrap(await jq.jqJson(url));
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

/**
 * Ingest the whole dashboard for one (universe, range) pair.
 * @returns {Promise<{rows:object[], categories:object[], meta:object}>}
 */
async function ingest({ universe = 'zz500', range = '3y', skipPaused = '1' } = {}) {
  console.log(`[factorlib] universe=${universe} range=${range} skipPaused=${skipPaused}`);

  const categories = await getCategories();
  console.log(`[factorlib] ${categories.length} categories`);
  await sleep(400);

  // name -> category, by walking each category list.
  // NOTE: join on `name`, never on `factor_id`. `factor_id` is regenerated per
  // request — the same factor comes back under a different id on every call —
  // so an id-keyed join silently produces empty columns. `name` is the stable
  // factor code (VROC12, DAVOL5, boll_down, ...).
  const catOf = {};
  for (const c of categories) {
    const rows = await getList({ categoryId: c.id, universe, range, fee: FEE_NONE, skipPaused });
    rows.forEach(r => { catOf[r.name] = c.intro || c.name; });
    console.log(`[factorlib]   ${(c.intro || c.name).padEnd(22)} ${rows.length}`);
    await sleep(400);
  }

  const free = await getList({ categoryId: 0, universe, range, fee: FEE_NONE, skipPaused });
  await sleep(600);
  const costed = await getList({ categoryId: 0, universe, range, fee: FEE_FULL, skipPaused });

  console.log(`[factorlib] rows: frictionless=${free.length} costed=${costed.length}`);
  if (!free.length || !costed.length) throw new Error('factor list came back empty — is the session still logged in?');

  const byName = Object.fromEntries(costed.map(r => [r.name, r]));
  let differing = 0;

  const rows = free.map(f => {
    const c = byName[f.name] || {};
    const topFree = num(f.annual_ex_return_5q);
    const topCost = num(c.annual_ex_return_5q);
    const botFree = num(f.annual_ex_return_1q);
    const botCost = num(c.annual_ex_return_1q);
    if (topFree != null && topCost != null && Math.abs(topFree - topCost) > 1e-9) differing++;
    return {
      factor_id: f.factor_id,
      name: f.name,
      category: catOf[f.name] || '',
      intro: (f.intro || '').replace(/\s+/g, ' ').trim(),
      formula: (f.algorithmIntro || '').replace(/\s+/g, ' ').trim(),
      ic_mean: num(f.ic_mean),
      ir: num(f.ir),
      turnover_top: num(f.turnover_mean_5q),
      turnover_bottom: num(f.turnover_mean_1q),
      sharpe_top_free: num(f.sharpe_5q),
      sharpe_top_cost: num(c.sharpe_5q),
      maxdd_top_cost: num(c.max_drawdown_5q),
      top_ex_annual_free: topFree,
      top_ex_annual_cost: topCost,
      bottom_ex_annual_free: botFree,
      bottom_ex_annual_cost: botCost,
      ls_annual_free: num(f.annual_return_ls),
      ls_annual_cost: num(c.annual_return_ls),
      erosion: topFree != null && topCost != null ? topCost - topFree : null,
    };
  });

  const matched = rows.filter(r => r.top_ex_annual_cost != null).length;
  if (matched < rows.length) {
    throw new Error(`cost join matched only ${matched}/${rows.length} factors — the two pulls disagree on \`name\``);
  }
  if (differing === 0) {
    console.warn('[factorlib] ⚠ the costed pull matched the frictionless one on every row — ' +
                 'commisionFee may have been ignored; treat the cost columns as unverified.');
  }

  return {
    rows,
    categories,
    meta: {
      universe, range, skipPaused,
      feeFree: FEE_NONE, feeFull: FEE_FULL,
      feeFullLabel: FEE_LABEL[FEE_FULL],
      factorCount: rows.length,
      differingRows: differing,
      pulledAt: new Date().toISOString(),
    },
  };
}

// ── Writers ──────────────────────────────────────────────────────────────────

const TSV_COLS = [
  'name', 'category', 'intro', 'formula',
  'top_ex_annual_cost', 'top_ex_annual_free', 'erosion',
  'bottom_ex_annual_cost', 'ls_annual_cost',
  'ic_mean', 'ir', 'sharpe_top_cost', 'maxdd_top_cost', 'turnover_top',
];   // no factor_id: it is regenerated per request and would churn every run

const PCT_COLS = new Set([
  'top_ex_annual_cost', 'top_ex_annual_free', 'erosion',
  'bottom_ex_annual_cost', 'ls_annual_cost', 'maxdd_top_cost', 'turnover_top',
]);

function writeTsv(file, rows) {
  const cell = (r, k) => {
    const v = r[k];
    if (v == null) return '';
    if (PCT_COLS.has(k)) return pct(v);
    if (typeof v === 'number') return String(v);
    return String(v).replace(/[\t\n\r]/g, ' ');
  };
  const lines = [TSV_COLS.join('\t')];
  for (const r of rows) lines.push(TSV_COLS.map(k => cell(r, k)).join('\t'));
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, lines.join('\n') + '\n');
}

function writeReadme(file, rows, meta, categories) {
  const ranked = [...rows].sort((a, b) => (b.top_ex_annual_cost ?? -9) - (a.top_ex_annual_cost ?? -9));
  const eroded = [...rows].filter(r => r.erosion != null).sort((a, b) => a.erosion - b.erosion);
  const survivors = ranked.filter(r => (r.top_ex_annual_cost ?? -9) > 0);
  const freePositive = rows.filter(r => (r.top_ex_annual_free ?? -9) > 0).length;

  const row = r =>
    `| ${r.name} | ${r.category} | ${(r.intro || '').slice(0, 26)} | ${pct(r.top_ex_annual_cost)}% | ` +
    `${pct(r.top_ex_annual_free)}% | ${pct(r.erosion)}pp | ${r.ir ?? ''} | ${pct(r.turnover_top)}% |`;
  const head =
    '| 因子 | 类别 | 说明 | 计成本超额年化 | 零成本超额年化 | 侵蚀 | IR | 换手 |\n' +
    '|---|---|---|---|---|---|---|---|';

  const md = `# 聚宽因子看板 — 计成本快照

由 \`node utils/factorlib-ingest.js\` 生成，**请勿手改**。数据源：JoinQuant 因子看板
(\`/view/factorlib/list\` 背后的 \`factorlib/index/getList\`)。

## 口径

| 项 | 值 |
|---|---|
| 股票池 | ${meta.universe} |
| 回测周期 | ${meta.range} |
| 过滤涨停/停牌 | ${meta.skipPaused === '1' ? '是' : '否'} |
| 成本档（主）| \`commisionFee=${meta.feeFull}\` = ${meta.feeFullLabel} |
| 成本档（对照）| \`commisionFee=${meta.feeFree}\` = ${FEE_LABEL[meta.feeFree]} |
| 因子数 | ${meta.factorCount} |
| 抓取时间 | ${meta.pulledAt} |

> ⚠ **默认档是零成本**。看板 UI 打开时用的就是 \`commisionFee=0\`，与
> \`harness/harness.md\` §2 的零滑点是同一个盲区。本页**一律按计成本档排序**，
> 零成本列只作对照，用来暴露「只在无摩擦下成立」的因子。

## 成本前后的存活情况

| | 超额年化为正的因子数 |
|---|---|
| 零成本 | ${freePositive} / ${meta.factorCount} |
| 计成本 | ${survivors.length} / ${meta.factorCount} |

## 计成本后最强的 20 个因子

${head}
${ranked.slice(0, 20).map(row).join('\n')}

## 被成本吃掉最多的 20 个因子

高换手因子在这里集中出现——这正是 harness 零滑点会系统性高估的那一类。

${head}
${eroded.slice(0, 20).map(row).join('\n')}

## 类别

${categories.map(c => `- \`${c.name}\` — ${c.intro}`).join('\n')}

## 怎么用

- 全量数据在 \`factors.tsv\`（${meta.factorCount} 行），列名见首行；百分比列已乘 100。
- \`formula\` 列是聚宽给的算法说明，可直接照着在策略里实现。
- 选因子时**只看 \`top_ex_annual_cost\`**；\`erosion\` 越负说明该因子越依赖无摩擦假设。
- 与 \`wiki/families/\` 横比时注意：本页是**单因子分层组合**的绩效，不是完整策略，
  两者的 objective 不可直接比较。
`;
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, md);
}

// ── CLI ──────────────────────────────────────────────────────────────────────

function parseArgs(argv) {
  const o = { universe: 'zz500', range: '3y', skipPaused: '1', listSettings: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--universe') o.universe = argv[++i];
    else if (a === '--range') o.range = argv[++i];
    else if (a === '--no-skip-paused') o.skipPaused = '0';
    else if (a === '--list-settings') o.listSettings = true;
  }
  return o;
}

if (require.main === module) {
  const o = parseArgs(process.argv.slice(2));
  (async () => {
    if (o.listSettings) {
      const s = await getSettings();
      console.log(JSON.stringify(s, null, 2));
      return;
    }
    const { rows, categories, meta } = await ingest(o);

    const tsv = path.join(OUT_DIR, 'factors.tsv');
    const readme = path.join(OUT_DIR, 'README.md');
    const raw = path.join(RAW_DIR, `raw-${meta.universe}-${meta.range}.json`);

    writeTsv(tsv, [...rows].sort((a, b) => (b.top_ex_annual_cost ?? -9) - (a.top_ex_annual_cost ?? -9)));
    writeReadme(readme, rows, meta, categories);
    fs.mkdirSync(RAW_DIR, { recursive: true });
    fs.writeFileSync(raw, JSON.stringify({ meta, categories, rows }, null, 2));

    const survivors = rows.filter(r => (r.top_ex_annual_cost ?? -9) > 0).length;
    console.log(`[factorlib] wrote ${path.relative(REPO, tsv)} (${rows.length} factors)`);
    console.log(`[factorlib] wrote ${path.relative(REPO, readme)}`);
    console.log(`[factorlib] wrote ${path.relative(REPO, raw)}`);
    console.log(`[factorlib] positive excess annual after costs: ${survivors}/${rows.length}`);
  })()
    .catch(e => { console.error(e.message || e); process.exitCode = 1; })
    .finally(() => jq.close());
}

module.exports = { ingest, getCategories, getSettings, getList, writeTsv, writeReadme };
