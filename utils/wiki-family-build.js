#!/usr/bin/env node
/**
 * wiki-family-build.js — regenerate the AUTO half of wiki/families/*.md from
 * strategy pages' `family:` fields + harness/normalize-train.tsv.
 *
 * AUTO (this script owns, never hand-edit):
 *   - §3 家族内绩效横评 (ranked metrics table)
 *   - frontmatter: memberCount, bestVariant, bestObjective, updatedAt
 * HAND (never touched by this script):
 *   - §1 基类, §2 变体 (narrative + Δ), §4 待研究, §5 沿革, and all other frontmatter.
 *
 * Modes:
 *   node utils/wiki-family-build.js            # write/scaffold family pages
 *   node utils/wiki-family-build.js --check    # lint: exit 1 if any page is stale (CI)
 *   node utils/wiki-family-build.js --list     # member counts per family
 *   node utils/wiki-family-build.js --force    # bypass the data-loss guard (see below)
 *
 * DATA-LOSS GUARD — read before using --force.
 *   §3 is generated from `harness/normalize-train.tsv`, which is GITIGNORED. The
 *   committed family pages are therefore the ONLY copy of the normalization
 *   results. If the ledger is missing or partial, a plain run would rewrite every
 *   §3 with empty cells and report success.
 *   This script now refuses to write a page that would end up with fewer
 *   populated metric values than it already has, and exits 1. That is a ledger
 *   problem, not a page problem: rebuild it with utils/strategy-normalize.js.
 *   node utils/wiki-family-build.js --list     # print family -> member/pass counts
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const STRAT = path.join(ROOT, 'wiki/strategies');
const FAM = path.join(ROOT, 'wiki/families');
const LEDGER = path.join(ROOT, 'harness/normalize-train.tsv');

const args = process.argv.slice(2);
const CHECK = args.includes('--check');
const LIST = args.includes('--list');
const FORCE = args.includes('--force');
const TODAY = new Date().toISOString().slice(0, 10);

// ── ledger: sourceFile -> best (highest-objective) normalized row ──
function loadLedger() {
  const by = {};
  const rows = fs.readFileSync(LEDGER, 'utf8').split('\n').slice(1);
  for (const r of rows) {
    const c = r.split('\t');
    if (c[3] !== 'normalized') continue;
    const src = c[0];
    const obj = parseFloat(c[11]);
    const rec = { obj: isNaN(obj) ? null : obj, sharpe: c[9], annual: c[8], maxdd: c[10], gate: c[12] };
    if (!by[src] || (rec.obj != null && (by[src].obj == null || rec.obj > by[src].obj))) by[src] = rec;
  }
  return by;
}

function frontmatter(src) {
  const m = src.match(/^---\n([\s\S]*?)\n---/);
  const fm = {};
  if (m) for (const line of m[1].split('\n')) {
    const mm = line.match(/^(\w+):\s*(.*)$/);
    if (mm) fm[mm[1]] = mm[2].trim();
  }
  return fm;
}

function loadStrategies() {
  const out = [];
  for (const f of fs.readdirSync(STRAT).filter(x => x.endsWith('.md'))) {
    const fm = frontmatter(fs.readFileSync(path.join(STRAT, f), 'utf8'));
    if (!fm.family) continue;
    out.push({ id: f.replace(/\.md$/, ''), family: fm.family, role: fm.familyRole || 'variant',
               sourceFile: fm.sourceFile || '' });
  }
  return out;
}

// ── §3 ranked 横评 table ──
function horizSection(members) {
  const ranked = members.slice().sort((a, b) => (b.obj ?? -1e9) - (a.obj ?? -1e9));
  const best = ranked.find(m => m.obj != null) || null;
  const L = ['## 3. 家族内绩效横评 (auto)',
             '',
             '| 排名 | 变体 | obj | sharpe | annual% | maxDD% | gate |',
             '|---|---|---|---|---|---|---|'];
  ranked.forEach((m, i) => {
    const obj = m.obj != null ? m.obj.toFixed(4) : 'DQ/—';
    const gate = m.gate === 'pass' ? '✅' : (m.gate === 'fail' ? '❌' : '—');
    const s = (best && m.id === best.id) ? '**' : '';
    L.push(`| ${s}${i + 1}${s} | ${s}[[${m.id}]]${s} | ${obj} | ${m.sharpe || '—'} | ${m.annual || '—'} | ${m.maxdd || '—'} | ${gate} |`);
  });
  const passN = members.filter(m => m.gate === 'pass').length;
  L.push('', `*${passN} gate-pass / ${members.length} members. 快照 ${TODAY}（TRAIN 2022–2023, 冻结零滑点 ⚠）。由 \`wiki-family-build.js\` 生成，勿手改。*`, '');
  return { text: L.join('\n'), best };
}

// ── Regression guard ────────────────────────────────────────────────────────
// §3 is generated from `harness/normalize-train.tsv`, which is GITIGNORED. If
// that ledger is missing, truncated, or from a partial re-run, this script will
// happily rewrite every §3 table with `DQ/—` and report success — silently
// deleting the only surviving copy of the normalization results, since the
// ledger that produced them is not in git.
//
// That is not hypothetical: on 2026-08-30 the ledger was a 13-row stub of
// compile-error rows, `--check` reported "13 stale", and a plain run blanked the
// metrics on all 13 family pages (小市值 1.3738/5.81/148.50 → DQ/—).
//
// So a page is never allowed to LOSE data. Counting is done per CELL, not per
// row: a DQ row still carries real sharpe / annual / maxDD / gate values
// (`DQ/— | -0.49 | 0.00 | 9.00 | ❌`), and an earlier version of this guard
// counted only the objective column — so it waved through writes that blanked
// every other metric on all-DQ pages. Any drop in populated cells is a loss.
const METRIC_COLS = [3, 4, 5, 6, 7];        // obj, sharpe, annual, maxdd, gate
const EMPTY_CELL = new Set(['', '—', 'DQ/—']);

function countMetricCells(section3Text) {
  let cells = 0;
  for (const line of (section3Text || '').split('\n')) {
    if (!/^\|\s*\*{0,2}\d+\*{0,2}\s*\|/.test(line)) continue;   // a ranked data row
    const c = line.split('|').map(x => x.replace(/\*/g, '').trim());
    // c: ['', rank, variant, obj, sharpe, annual, maxdd, gate, '']
    for (const i of METRIC_COLS) if (c[i] !== undefined && !EMPTY_CELL.has(c[i])) cells++;
  }
  return cells;
}

function extractSection3(body) {
  const lines = body.split('\n');
  const start = lines.findIndex(l => /^## 3\. /.test(l));
  if (start < 0) return '';
  let end = lines.length;
  for (let i = start + 1; i < lines.length; i++) {
    if (/^## /.test(lines[i])) { end = i; break; }
  }
  return lines.slice(start, end).join('\n');
}

// replace the "## 3. …" section (up to the next "## " or EOF) with fresh content
function replaceSection3(body, section3) {
  const lines = body.split('\n');
  const start = lines.findIndex(l => /^## 3\. /.test(l));
  if (start < 0) return null; // caller decides (scaffold)
  let end = lines.length;
  for (let i = start + 1; i < lines.length; i++) {
    if (/^## /.test(lines[i])) { end = i; break; }
  }
  return [...lines.slice(0, start), ...section3.split('\n'), ...lines.slice(end)].join('\n');
}

function setFmKey(fmBlock, key, val) {
  const re = new RegExp(`^${key}:.*$`, 'm');
  return re.test(fmBlock) ? fmBlock.replace(re, `${key}: ${val}`) : fmBlock + `\n${key}: ${val}`;
}

function scaffold(family, section3, best, memberCount) {
  return `---
family: ${family}
aliases: []
concepts: []
base: [[<postId8>_<代表基类>]]
bestVariant: ${best ? `[[${best.id}]]` : '[[]]'}
bestObjective: ${best && best.obj != null ? best.obj.toFixed(4) : 'null'}
memberCount: ${memberCount}
sources: { normalized: ${memberCount}, study: 0, enhance: 0 }
realism: "<⚠ 待人工填写>"
status: active
updatedAt: ${TODAY}
---

# ${family} — strategy family

**一句话**：<待人工填写：该血统在做什么>

## 1. 基类 (base archetype)   ← 待人工填写 + [[study]] 溯源
- **Universe 选股池**：<>
- **交易频率**：<>
- **交易机制**：入场/择时 <> ；调仓 <> ；止损/风控 <>
- **基线绩效**（frozen harness, TRAIN 2022–2023）：见 §3。
- **为什么有效**：<>
- **⚠ 现实性 / 容量**：<>

## 2. 变体 (variants)   ← 待人工/study/enhance 填写
| 变体 | 相对基类的改动 | 来源 | Δobjective | Δsharpe | ΔmaxDD | 结论 |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — |

${section3}
## 4. 待研究 / 空白 (research gaps)   ← 待人工填写：本家族未试方向

## 5. 沿革 (provenance)   ← 待人工填写：首发 postId/作者、版本演进
`;
}

// ── build ──
const ledger = loadLedger();
const strats = loadStrategies();
const families = {};
for (const s of strats) (families[s.family] ||= []).push({ ...s, ...(ledger[s.sourceFile] || {}) });

if (LIST) {
  Object.entries(families).sort((a, b) => b[1].length - a[1].length)
    .forEach(([f, m]) => console.log(`${String(m.length).padStart(3)}  ${m.filter(x => x.gate === 'pass').length} pass  ${f}`));
  process.exit(0);
}

fs.mkdirSync(FAM, { recursive: true });
// Ledger preflight: a ledger with no usable rows can only ever blank pages.
const normalizedRows = Object.keys(ledger).length;
if (normalizedRows === 0 && !FORCE) {
  console.error(
    `REFUSING TO RUN: ${path.relative(ROOT, LEDGER)} has 0 \`normalized\` rows.\n` +
    `  §3 is generated from that ledger, and it is gitignored — so the family pages\n` +
    `  are currently the ONLY copy of the normalization results. Running now would\n` +
    `  erase them. Rebuild the ledger first (utils/strategy-normalize.js).\n` +
    `  Override with --force only if you intend to publish empty tables.`);
  process.exit(1);
}

let stale = 0, wrote = 0, scaffolded = 0, blocked = 0;
for (const [family, members] of Object.entries(families)) {
  if (family === '其他') continue; // singletons bucket: no family page
  const { text: section3, best } = horizSection(members);
  const file = path.join(FAM, family + '.md');
  let next;
  if (fs.existsSync(file)) {
    let cur = fs.readFileSync(file, 'utf8');
    const replaced = replaceSection3(cur, section3);
    next = replaced != null ? replaced : cur; // if no §3 heading, leave body (page malformed)
    // refresh AUTO frontmatter keys
    const fmMatch = next.match(/^---\n([\s\S]*?)\n---/);
    if (fmMatch) {
      let fm = fmMatch[1];
      fm = setFmKey(fm, 'memberCount', members.length);
      if (best) { fm = setFmKey(fm, 'bestVariant', `[[${best.id}]]`); fm = setFmKey(fm, 'bestObjective', best.obj.toFixed(4)); }
      fm = setFmKey(fm, 'updatedAt', TODAY);
      next = next.replace(/^---\n[\s\S]*?\n---/, `---\n${fm}\n---`);
    }
  } else {
    next = scaffold(family, section3, best, members.length);
  }
  const cur = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : '';
  if (next === cur) continue;

  // Refuse to trade populated metric cells for empty ones (see countMetricCells).
  const had = countMetricCells(extractSection3(cur));
  const gets = countMetricCells(section3);
  if (cur && gets < had && !FORCE) {
    console.error(
      `BLOCKED: wiki/families/${family}.md — would drop ${had - gets} metric value(s) ` +
      `(${had} → ${gets}). The ledger is incomplete, not the page.`);
    blocked++;
    continue;
  }

  if (CHECK) { console.error(`STALE: wiki/families/${family}.md`); stale++; continue; }
  fs.writeFileSync(file, next);
  if (cur) { wrote++; } else { scaffolded++; }
  console.log(`${cur ? 'updated ' : 'scaffold'} wiki/families/${family}.md (${members.length} members)`);
}
if (blocked) {
  // Reported in BOTH modes, and never as "stale" — telling someone to run the
  // tool is the wrong advice when the tool is what would destroy the data.
  console.error(
    `\n${blocked} family page(s) BLOCKED: regenerating would delete metric rows.\n` +
    `  Cause: harness/normalize-train.tsv is incomplete (${normalizedRows} normalized row(s)).\n` +
    `  Fix:   rebuild the ledger — node utils/strategy-normalize.js\n` +
    `  The pages are correct; the ledger is not. Do NOT --force unless you mean it.`);
}
if (CHECK) {
  if (stale) console.error(`\n${stale} family page(s) stale — run: node utils/wiki-family-build.js`);
  if (stale || blocked) process.exit(1);
  console.log('all family pages up to date ✓');
} else {
  console.log(`\ndone: ${wrote} updated, ${scaffolded} scaffolded${blocked ? `, ${blocked} blocked` : ''}`);
  if (blocked) process.exit(1);
}
