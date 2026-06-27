/**
 * wiki-factor-signature.js
 *
 * Generate the 因子构成（选/择/控/仓）table cell for a strategy page from its
 * `factors` frontmatter, so a concept page's 变体与差异 table never drifts from
 * the strategy pages it aggregates. The cell is a deterministic compression:
 *   选:<选股信号·…> ｜ 择:<择时·…> ｜ 控:<风控+…> ｜ 仓:<仓位·…>
 * Empty roles are omitted; parenthetical clarifications are stripped for brevity
 * (full detail stays in the strategy page / frontmatter).
 *
 * Usage:
 *   node utils/wiki-factor-signature.js <wiki/strategies/xxx.md>   # one cell
 *   node utils/wiki-factor-signature.js --all                      # [[name]] | cell (all pages)
 */

const fs = require('fs');
const path = require('path');

const STRAT_DIR = path.join(__dirname, '..', 'wiki', 'strategies');

const ROLE_ORDER = ['选股', '择时', '风控', '仓位'];
const ROLE_LABEL = { 选股: '选', 择时: '择', 风控: '控', 仓位: '仓' };
const ROLE_JOIN = { 选股: '·', 择时: '·', 风控: '+', 仓位: '·' };

/** Strip half/full-width parenthetical clarifications for the compact signature. */
function strip(v) {
  return v.replace(/（[^）]*）/g, '').replace(/\([^)]*\)/g, '').trim();
}

function parseList(s) {
  const m = s.match(/\[(.*)\]/);
  if (!m) return [];
  return m[1].split(',').map(x => strip(x.trim())).filter(Boolean);
}

/** Extract {选股,择时,风控,仓位} signal arrays from a frontmatter string. */
function extractFactors(fm) {
  const lines = fm.split('\n');
  const start = lines.findIndex(l => /^factors:\s*$/.test(l));
  if (start < 0) return null;
  const out = { 选股: [], 择时: [], 风控: [], 仓位: [] };
  let role = null;
  for (let i = start + 1; i < lines.length; i++) {
    const l = lines[i];
    if (/^\S/.test(l)) break; // dedent to a top-level key -> factors block ended
    let m;
    if ((m = l.match(/^ {2}(选股|择时|风控|仓位):\s*(\[.*\])?\s*$/))) {
      role = m[1];
      if (m[2]) out[role].push(...parseList(m[2]));
    } else if (role === '选股' && (m = l.match(/^ {4}\S.*?:\s*(\[.*\])\s*$/))) {
      out['选股'].push(...parseList(m[1])); // 选股 sub-family signals flatten into 选
    }
  }
  return out;
}

function signature(factors) {
  return ROLE_ORDER
    .filter(r => (factors[r] || []).length > 0)
    .map(r => `${ROLE_LABEL[r]}:${factors[r].join(ROLE_JOIN[r])}`)
    .join(' ｜ ');
}

function cellFor(file) {
  const txt = fs.readFileSync(file, 'utf8');
  const fm = (txt.match(/^---\n([\s\S]*?)\n---/) || [])[1] || '';
  const factors = extractFactors(fm);
  return factors ? signature(factors) : null;
}

// ── CLI ─────────────────────────────────────────────────────────────────────
if (require.main === module) {
  const arg = process.argv[2];
  if (arg === '--all') {
    for (const f of fs.readdirSync(STRAT_DIR).filter(f => f.endsWith('.md')).sort()) {
      console.log(`[[${f.replace(/\.md$/, '')}]] | ${cellFor(path.join(STRAT_DIR, f))}`);
    }
  } else if (arg) {
    const cell = cellFor(arg);
    if (cell == null) { console.error('no factors block in', arg); process.exit(1); }
    console.log(cell);
  } else {
    console.error('usage: node utils/wiki-factor-signature.js <strategy.md> | --all');
    process.exit(1);
  }
}

module.exports = { cellFor, signature, extractFactors };
