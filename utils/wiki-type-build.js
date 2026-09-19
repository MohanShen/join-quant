/**
 * wiki-type-build.js — group families into TYPES on two derived axes.
 *
 * A type is a coordinate over families, not a third page hierarchy
 * (docs/consolidation-plan.md §1). Families sharing a type trade the same market at the same
 * speed, which makes them candidates to be compared, merged or cross-pollinated.
 *
 *   Axis U — universe. Derived by matching the family's BASE strategy source, because prose
 *            describes intent and code describes behaviour.
 *   Axis H — holding period, bucketed from measured turnover.
 *
 * Why turnover and not execution time. The 打板短线 study measured the explicit
 * `MarketOrderStyle(day_open)` argument as bit-for-bit inert: removing it changed every metric
 * by 0.0000 across 484 trading days, trade counts and drawdown window included. On a daily-bar
 * harness the 09:26 / 11:25 / 14:50 labels are decoration, so grouping on execution time would
 * group on something the bench cannot see. Turnover is measured for every normalized strategy.
 * Intraday dependence survives as a FLAG (a realizability property), not as an axis.
 *
 * Membership is never hand-written. Like wiki-family-build.js this refuses to write a page
 * that would lose information, because a plain regenerate once blanked 13 family pages.
 *
 * Usage:
 *   node utils/wiki-type-build.js --check     # report assignments, write nothing
 *   node utils/wiki-type-build.js             # write wiki/types/<U>-<H>.md
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const FAM_DIR = path.join(ROOT, 'wiki/families');
const PAGES_DIR = path.join(ROOT, 'wiki/strategies');
const TYPE_DIR = path.join(ROOT, 'wiki/types');
const LEDGER = path.join(ROOT, 'harness/normalize-train.tsv');

const fmField = (t, k) => (t.match(new RegExp(`^${k}:\\s*(.*)$`, 'm')) || [])[1] || '';

/**
 * Universe signals. Each regex is counted (global), not first-match: a defensive 511880
 * money-market sleeve should not turn an ETF rotation book into a bond fund, which is exactly
 * what a priority-ordered first-match rule did on the first run.
 */
const UNIVERSE_RULES = [
  ['期货', /RealFuture|get_dominant_future|set_future_commission|期货合约/g],
  ['可转债', /转债|convertible/g],
  ['债券', /国债|债券|511880|511010|511010\.XSHG/g],
  ['微盘', /market_cap\.asc|circulating_market_cap\.asc|最小市值|微盘|399101/g],
  ['小盘', /小市值|small_cap|中证1000|000852/g],
  ['ETF', /unit_net_value|etf_pool|get_all_securities\(\s*\[?['"](?:etf|lof)/g],
  ['宽基大盘', /000300|沪深300|000905|中证500|000016|上证50|白马|蓝筹/g],
  ['全A', /get_all_securities\(\s*\[?['"]stock|get_index_stocks\(\s*['"]000985/g],
];

/** Below this many matches the evidence is too thin to name a universe. */
const MIN_EVIDENCE = 3;
/** Two universes both this strong, relative to the leader, means a hybrid book. */
const HYBRID_RATIO = 0.4;

/**
 * Score the base source and return the dominant universe, `混合` when two are jointly
 * dominant, or `全A` when nothing scores above the evidence floor.
 *
 * 混合 is a real answer, not a cop-out: the 七星高照 study measured that family's base as a
 * 50/50 小市值 + ETF blend, and its signal counts here (微盘 26, ETF 15) say the same thing.
 */
function universeOf(rawSrc) {
  // A benchmark is not a universe. `set_benchmark('000300.XSHG')` and
  // `reference_security=` appear in almost every strategy and were enough to make two pure
  // ETF-discount books look like large-cap hybrids. Strip those lines before scoring.
  const src = rawSrc
    .split('\n')
    // Comments are KEPT: these strategies name their universe in Chinese comments, and
    // stripping them lost the signal that 小市值's base picks the smallest-cap names.
    .filter(l => !/set_benchmark|reference_security|set_option|log\./.test(l))
    .join('\n');
  const scored = UNIVERSE_RULES
    .map(([name, re]) => [name, (src.match(re) || []).length])
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1]);
  if (!scored.length || scored[0][1] < MIN_EVIDENCE) return '全A';
  const [top, second] = scored;
  // 微盘/小盘 are the same market at different cuts — never call that a hybrid.
  const sameMarket = (a, b) => ['微盘', '小盘'].includes(a) && ['微盘', '小盘'].includes(b);
  if (second && second[1] >= MIN_EVIDENCE && second[1] / top[1] >= HYBRID_RATIO
      && !sameMarket(top[0], second[0])) {
    return '混合';
  }
  return top[0];
}

/** Turnover bands. Measured family turnover spans 0.0078 (三进兵) to 0.3061 (打板短线). */
function horizonOf(turnover) {
  if (turnover == null) return 'H-unknown';
  if (turnover < 0.03) return 'H-low';
  if (turnover <= 0.12) return 'H-mid';
  return 'H-high';
}

/** Is the claimed edge dependent on fills a daily bar cannot honour? A flag, not an axis. */
const INTRADAY = /竞价|call_auction|get_current_data\(\)\[[^\]]*\]\.day_open|MarketOrderStyle|涨停板|封板|盘中止损|11:2[0-9]|14:5[0-9]/;

/** sourceFile -> { family, page } from the strategy pages. */
function pageIndex() {
  const out = {};
  if (!fs.existsSync(PAGES_DIR)) return out;
  for (const p of fs.readdirSync(PAGES_DIR).filter(f => f.endsWith('.md'))) {
    const t = fs.readFileSync(path.join(PAGES_DIR, p), 'utf8');
    const src = fmField(t, 'sourceFile').trim();
    if (src) out[src] = { family: fmField(t, 'family').trim(), page: p.replace(/\.md$/, '') };
  }
  return out;
}

/** Measured turnover per family: median over its normalized members that report one. */
function familyTurnover(idx) {
  const byFam = {};
  let text;
  try { text = fs.readFileSync(LEDGER, 'utf8'); } catch { return byFam; }
  for (const line of text.split('\n').slice(1)) {
    const c = line.split('\t');
    if (!c[0] || c[3] !== 'normalized') continue;
    const fam = (idx[c[0]] || {}).family;
    if (!fam) continue;
    (byFam[fam] = byFam[fam] || []).push(c[0]);
  }
  return byFam;
}

/** Read a family's stated turnover from its own page (the study loop records it there). */
function statedTurnover(text) {
  const m = text.match(/turnover[^0-9]{0,4}(0\.[0-9]+)/);
  return m ? parseFloat(m[1]) : null;
}

function build() {
  const idx = pageIndex();
  const members = familyTurnover(idx);
  const rows = [];

  for (const f of fs.readdirSync(FAM_DIR).filter(f => f.endsWith('.md'))) {
    const name = f.replace(/\.md$/, '');
    const text = fs.readFileSync(path.join(FAM_DIR, f), 'utf8');
    const base = fmField(text, 'base').trim();

    // resolve the base page -> its source file -> read the code
    let src = '';
    const m = base.match(/\[\[([^\]]+)\]\]/);
    if (m) {
      const p = path.join(PAGES_DIR, `${m[1]}.md`);
      if (fs.existsSync(p)) {
        const sf = fmField(fs.readFileSync(p, 'utf8'), 'sourceFile').trim();
        const abs = path.join(ROOT, sf);
        if (sf && fs.existsSync(abs)) src = fs.readFileSync(abs, 'utf8');
      }
    }

    const turnover = statedTurnover(text);
    rows.push({
      family: name,
      universe: src ? universeOf(src) : '其他',
      turnover,
      horizon: horizonOf(turnover),
      intraday: src ? INTRADAY.test(src) : false,
      members: parseInt(fmField(text, 'memberCount'), 10) || (members[name] || []).length,
      bestObjective: parseFloat(fmField(text, 'bestObjective')) || null,
      resolved: Boolean(src),
    });
  }
  return rows;
}

function typeKey(r) { return `${r.universe}-${r.horizon}`; }

function render(key, group) {
  const best = group.reduce((a, b) => ((b.bestObjective ?? -9) > (a.bestObjective ?? -9) ? b : a));
  const lines = [
    '---',
    `type: ${key}`,
    `universe: ${group[0].universe}`,
    `horizon: ${group[0].horizon}`,
    `families: [${group.map(g => `[[${g.family}]]`).join(', ')}]`,
    `familyCount: ${group.length}`,
    `memberStrategies: ${group.reduce((n, g) => n + g.members, 0)}`,
    `bestFamily: ${best.bestObjective != null ? `[[${best.family}]]` : '—'}`,
    `bestFamilyObjective: ${best.bestObjective ?? 'null'}`,
    `intradayDependent: ${group.some(g => g.intraday)}`,
    `generatedBy: utils/wiki-type-build.js`,
    `updatedAt: ${new Date().toISOString().slice(0, 10)}`,
    '---',
    '',
    `# ${key} — strategy type`,
    '',
    '**由 `utils/wiki-type-build.js` 生成，勿手改。** 家族归属由基类源码（universe）+ 实测换手',
    '（horizon）导出，不读正文叙述。',
    '',
    '## 成员家族',
    '',
    '| 家族 | 成员数 | bestObjective | 实测换手 | 盘中依赖 |',
    '|---|---|---|---|---|',
    ...group
      .slice()
      .sort((a, b) => (b.bestObjective ?? -9) - (a.bestObjective ?? -9))
      .map(g => `| [[${g.family}]] | ${g.members} | ${g.bestObjective ?? 'DQ'} | ${g.turnover ?? '—'} | ${g.intraday ? '⚠ 是' : '否'} |`),
    '',
    '## 整合回合（见 `docs/consolidation-plan.md` §4）',
    '',
    '> ⚠ **合并必然抬高夏普**：相关性 < 1 时混合的夏普机械地高于单腿，而闸门**就是**夏普阈值。',
    '> 本仓库已两次实测到这点——[[七星高照]] 混合 sharpe 3.17 高于两腿（2.85 / 1.60）且波动低于两腿；',
    '> [[红利低频]] 的双因子合取回报 23.41% 对两腿之和 11.75%。所以整合候选的判据是',
    '> **超过本类型最好的那个成员**，不是过闸；并须报出「多少来自分散化」。',
    '',
    '_（本节由整合回合追加；当前无记录。）_',
    '',
  ];
  return lines.join('\n');
}

if (require.main === module) {
  const check = process.argv.includes('--check');
  const rows = build();
  const groups = {};
  for (const r of rows) (groups[typeKey(r)] = groups[typeKey(r)] || []).push(r);

  console.log(`[type] ${rows.length} families -> ${Object.keys(groups).length} type cell(s)`);
  const unresolved = rows.filter(r => !r.resolved);
  if (unresolved.length) {
    console.log(`[type] ⚠ ${unresolved.length} family(ies) whose base source could not be read (universe=其他):`);
    unresolved.forEach(r => console.log(`        ${r.family}`));
  }
  for (const [k, g] of Object.entries(groups).sort((a, b) => b[1].length - a[1].length)) {
    console.log(`  ${k.padEnd(14)} ${g.length} family(ies): ${g.map(x => x.family).join(', ')}`);
  }
  const biggest = Math.max(...Object.values(groups).map(g => g.length));
  if (biggest === rows.length) console.log('[type] ⚠ one cell holds every family — the axes are not separating anything');

  if (check) { console.log('[type] (--check — nothing written)'); process.exit(0); }

  fs.mkdirSync(TYPE_DIR, { recursive: true });
  for (const [k, g] of Object.entries(groups)) {
    fs.writeFileSync(path.join(TYPE_DIR, `${k}.md`), render(k, g));
  }
  console.log(`[type] wrote ${Object.keys(groups).length} page(s) to wiki/types/`);
}

module.exports = { build, universeOf, horizonOf, typeKey, UNIVERSE_RULES };
