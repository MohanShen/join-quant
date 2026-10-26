// q-e9-pit: POINT-IN-TIME POOL test for the two high-scoring ETF books under epoch 9.
//
// ## Why
//
// Epoch 9 (TRAIN 2024) produced the library's two strongest rows, both ETF-momentum books from
// the family whose pool CLAUDE.md records as 「写于 2026」:
//
//     73b13d92  五福_ETF_轮动五年迭代        sharpe 5.22  objective 1.4926
//     1cc495be  给五福多ETF动量增加卖出冷却   sharpe 4.59  objective 0.9954
//
// The family's measured edge was established to be the POOL, not the ranking (ETF动量's own
// 11-ETF pool scored −0.27 when swapped for a broad A-share pool; 七星高照's is
// 「事后选择且不可替换」). Epoch 9 does not fix that and plausibly sharpens it: a pool assembled
// in 2026 was chosen knowing what worked through 2024, and the window now sits ~2 years from the
// authoring date instead of 4.
//
// ## The rule — fixed before the run, zero free parameters
//
//   pool = the book's OWN active names (g.global_etf_pool + g.china_etf_pool)
//          ∩ { 上市日期 < 2024-01-01 }
//
// Both inputs are pre-run facts taken from the book itself: the names are its source, and the
// listing dates are the AUTHOR'S OWN inline comments on the same lines. A listing date is a
// security attribute, not performance data, so the rule cites no 2024 price, return, volume or
// ranking. Same rule as q-e8-7, with the cutoff moved to the active TRAIN start.
//
// ## What the audit found (and why this is not only a TRAIN question)
//
// These books carry ~114 active names, not 17, and **17 of them list after 2024-01-01**:
//
//   10 list DURING train 2024  — tradeable only from their listing day, chosen knowing 2024
//    7 list in 2025            — NOT tradeable in TRAIN at all ... but tradeable in VAL 2025
//
// ⚠⚠ The second group is the serious one. Epoch 9's VAL is 2025, so a pool authored in 2026
// containing seven names that listed during 2025 has selection-on-VAL built into the source. VAL
// is ONE shot per (family, bench) and epoch 9 just granted this family a fresh one — so a VAL on
// the unrestricted book would spend the family's only validation on a pool picked knowing 2025.
// A VAL on these books needs AT LEAST a pre-2025 cutoff; this file only settles TRAIN.
//
// ## Method
//
// The excluded lines are COMMENTED OUT in place — the smallest possible edit, auditable line by
// line, and it leaves the author's own listing-date comment visible next to each exclusion.
// Nothing else is touched: no ranking change, no threshold change, no liquidity change.
//
//   node study/五福闹新春/build-e9-pit.js --dry
//   node study/五福闹新春/build-e9-pit.js

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const ROOT = path.join(__dirname, '../..');
const OUT = __dirname;
const DRY = process.argv.includes('--dry');

// The cutoff is the ACTIVE train start, read from the harness — never written down, so this
// builder stays correct if the window moves again.
const CUT = harness.window('train').start;

/**
 * Corpus-wide code -> listing-date map, built from every book that documents dates inline.
 *
 * ⚠ Used ONLY as a fallback, and the provenance is weaker than the primary rule, so it is stated
 * in the variant header rather than hidden. b50e4387 (小市值+ETF引擎, the #2 book) carries the
 * SAME 114-name pool as the documented books but with **no inline comments at all**, so the
 * primary rule found nothing to exclude and the builder correctly refused — the test would have
 * been inert. Every one of its 114 names is documented by another author in this corpus, and the
 * resulting exclusion set is the same 17 names / 7 from 2025 as its siblings, which is itself
 * corroboration that these are the same pool.
 *
 * It is still a pre-run fact with zero free parameters: a listing date is a security attribute,
 * not performance data, and reading it from another book's comment is verification, not a choice.
 */
function corpusListingDates() {
  const map = new Map();
  const dir = path.join(ROOT, 'strategies');
  for (const f of fs.readdirSync(dir).filter(x => x.endsWith('.py'))) {
    const t = fs.readFileSync(path.join(dir, f), 'utf8');
    for (const m of t.matchAll(/["']([0-9]{6}\.(?:XSHG|XSHE))["'],\s*#[^\n]*上市日期：(\d{4}-\d{2}-\d{2})/g)) {
      if (!map.has(m[1])) map.set(m[1], m[2]);
    }
  }
  return map;
}
const CORPUS_DATES = corpusListingDates();

const BOOKS = [
  { tag: 'q-e9-pit_73b13d92', match: /73b13d92/, label: '五福_ETF_轮动五年迭代' },
  { tag: 'q-e9-pit_1cc495be', match: /1cc495be/, label: '给五福多ETF动量增加卖出冷却' },
  // Added after the first two came back: the epoch-9 re-measurement produced a NEW library leader
  // at objective 1.7881 / sharpe 6.99, and it carries the same pool structure (115 names with
  // inline listing dates, 18 of them after 2024-01-01). Same rule, same builder — the point of
  // keeping one builder is that the membership rule cannot drift between books.
  { tag: 'q-e9-pit_bba95a11', match: /bba95a11/, label: '小市值_五福6年87倍13回撤' },
  // #2 book (objective 1.6997 / sharpe 6.65). Its pool is UNDATED, so it needs the corpus
  // fallback above — see that comment for why that is still a zero-free-parameter rule.
  { tag: 'q-e9-pit_b50e4387', match: /b50e4387/, label: '从30倍到47倍_给小市值装上ETF引擎后' },

  // ── Round 2, added 2026-10-22 after the epoch-9 re-measurement put five more pool-carrying
  //    books in the credible band. Same rule, same builder: the point of ONE builder is that the
  //    membership rule cannot drift between books, and four of these are the 五福 family pool the
  //    first round already measured at −33% / −19% / +0.2% / +1.1%, so they are directly
  //    comparable to it.
  { tag: 'q-e9-pit_bf30eb36', match: /bf30eb36/, label: '三马105-五福35-修复版' },        // 1.9437, pool 121, UNDATED -> corpus fallback
  { tag: 'q-e9-pit_fd5d388d', match: /fd5d388d/, label: '五福闹新春_v5_1-拟合ETF池' },     // 1.7890, pool 115, 114 dated
  { tag: 'q-e9-pit_4d4705e1', match: /4d4705e1/, label: '五福闹新春_v5_0-动态池' },        // 1.7405, pool 115, 114 dated
  { tag: 'q-e9-pit_a722ab8a', match: /a722ab8a/, label: '五福51-三状态V2版' },            // 1.5278, pool 120, 116 dated
  // ⚠ A DIFFERENT pool: 44 double-quoted codes in `g.etf_pool_2`/`g.etf_pool_3`, not the family's
  // ~115-name list, and it also runs a stock sleeve off `get_index_stocks("399101.XSHE")`. Kept in
  // because the question is the same (is the hardcoded ETF list hindsight?) — but its result is NOT
  // comparable to the four above, and it is one of THREE byte-identical books at obj 1.6156 /
  // sharpe 6.12, so one run answers all three.
  { tag: 'q-e9-pit_3c462ece', match: /3c462ece/, label: '三马七星172-大池子' },

  // ── The PRODUCT SHELF, added 2026-10-26. ETF动量's validated product re-measured on epoch 9 at
  //    objective 2.4187 / sharpe 7.23 — rank 8 of 235, and the highest score on the bench from a
  //    family NOT measured at realizability 1 (6 of the 7 above it are 打板短线 or PT多策略, both
  //    R=1). It carries 45 hardcoded ETF codes and ZERO inline listing dates, so it needs the
  //    corpus fallback, and ETF动量 is the family whose pool CLAUDE.md records as 「写于 2026」 with
  //    a broad A-share pool scoring −0.27. So that 2.4187 is not quotable until this runs.
  { tag: 'q-e9-pit_etfmom-005', match: /^etfmom-005\.py$/, label: 'ETF动量 产品 etfmom-005',
    dir: 'validated_strategies' },
];

const header = (label, cut, dropped) => [
  '# ============================================================================',
  `# q-e9-pit 变体：${label} —— 「点时」池（POINT-IN-TIME POOL）`,
  '#',
  '# 【成员资格规则 —— 跑前固定，零自由度】',
  '#   池 = 本书自己的 g.global_etf_pool + g.china_etf_pool 中所有未被作者注释掉的名字',
  `#        ∩ { 上市日期 < ${cut} }`,
  '#   两个输入都是跑前可查的事实：名单来自本书源码；上市日来自同几行作者自己的行内注释',
  '#   （上市日是证券属性，不是业绩数据）。本规则不引用任何 2024 年的价格、收益、成交额或排名。',
  '#',
  `# 【被排除的 ${dropped.length} 只 —— 一只都不得放回】`,
  ...dropped.map(d => `#   ${d.code}  上市 ${d.date}  [日期来源: ${d.via === 'own' ? '本书行内注释' : '语料库内其他作者的行内注释'}]` +
    (d.date >= '2025-01-01' ? '   ← 2025 才上市：TRAIN 完全不可交易，但 VAL(2025) 可交易' : '   ← TRAIN 窗口内上市')),
  '#',
  '# 【刻意不碰】排名、动量窗口、择时、阈值、流动性过滤、成本块，全部逐字不动。',
  '#   唯一的改动是把上述名字在池中注释掉。',
  '# ============================================================================',
  '',
].join('\n');

const built = [];
for (const b of BOOKS) {
  // ⚠ `dir` defaults to strategies/ but may name the product shelf. A shelf artifact is a BUILT
  // book, so it is not a ledger row and the primary dated-comment rule rarely applies to it — but
  // the pool question is identical, and routing it through THIS builder is the point: one builder
  // means the membership rule cannot drift between an ingested book and a product.
  const srcDir = b.dir || 'strategies';
  const src = fs.readdirSync(path.join(ROOT, srcDir)).find(f => b.match.test(f));
  if (!src) throw new Error(`no source for ${b.tag} in ${srcDir}`);
  const raw = py2to3(fs.readFileSync(path.join(ROOT, srcDir, src), 'utf8'));

  const dropped = [];
  // ⚠ A book may list one name per line WITH a dated comment (73b13d92 etc.) or several bare
  // names per line with none (b50e4387). Commenting out a whole line is only safe in the first
  // shape; in the second the excluded CODES are removed from the line individually, which is why
  // the assertion below counts changed LINES rather than codes.
  const out = raw.split('\n').map((l) => {
    if (/^\s*#/.test(l)) return l;                      // already inactive in the author's source
    const one = l.match(/^(\s*)["']([0-9]{6}\.(?:XSHG|XSHE))["'],\s*#(.*)$/);
    if (one) {
      const date = (one[3].match(/上市日期：(\d{4}-\d{2}-\d{2})/) || [])[1] || CORPUS_DATES.get(one[2]);
      if (!date || date < CUT) return l;
      dropped.push({ code: one[2], date, via: (one[3].match(/上市日期：/) ? 'own' : 'corpus') });
      return `${one[1]}#${l.trim()}   # q-e9-pit: 上市 ${date} >= ${CUT}`;
    }
    // Bare codes, possibly several on one line.
    const codes = [...l.matchAll(/["']([0-9]{6}\.(?:XSHG|XSHE))["']/g)].map(m => m[1]);
    if (!codes.length) return l;
    const kill = codes.filter(c => { const d = CORPUS_DATES.get(c); return d && d >= CUT; });
    if (!kill.length) return l;
    let out2 = l;
    for (const c of kill) {
      dropped.push({ code: c, date: CORPUS_DATES.get(c), via: 'corpus' });
      out2 = out2.replace(new RegExp(`["']${c.replace('.', '\\.')}["'],\\s*`), '');
    }
    return `${out2}   # q-e9-pit: 移除 ${kill.join(' ')}（上市 >= ${CUT}）`;
  }).join('\n');

  // ⚠ Assert the edit did exactly what the rule says, and nothing else: the only differences
  // between raw and out must be the commented lines.
  // ⚠ Lines changed <= codes excluded, because a bare-code line can lose several codes at once.
  // The invariant is: every changed line carries the q-e9-pit marker, and nothing else moved.
  const rl = raw.split('\n'), ol = out.split('\n');
  const changed = rl.map((l, i) => [i, l, ol[i]]).filter(([, a, b2]) => a !== b2);
  if (!changed.length) throw new Error(`${b.tag}: nothing changed — the test would be inert`);
  for (const [i, , b2] of changed) {
    if (!/q-e9-pit:/.test(b2)) throw new Error(`${b.tag}: line ${i + 1} changed without the marker — refusing`);
  }
  if (changed.length > dropped.length) {
    throw new Error(`${b.tag}: ${changed.length} line(s) changed but only ${dropped.length} excluded — refusing`);
  }
  if (!dropped.length) throw new Error(`${b.tag}: nothing to exclude — the test would be inert`);

  const file = path.join(OUT, `${b.tag}.py`);
  // ⚠⚠ NEVER append OVERRIDE to a book that already carries it. A PRODUCT from
  // `validated_strategies/` was built from `enhance/strategy_template.py`, which embeds the pins,
  // so a second copy rebinds `__jq_orig_initialize` to the ALREADY-WRAPPED `initialize` and the
  // wrapper calls itself: `RecursionError: maximum recursion depth exceeded`, 985 frames deep,
  // reported as a bare `compile-error`. Measured on etfmom-005, 2026-10-26 — and the signal was in
  // plain sight beforehand (a pin-marker count of 14 on the product), which I read as "good, it is
  // pinned" rather than "the OVERRIDE is already here".
  // The pins must still be PRESENT, so this asserts rather than silently skipping.
  const hasOverride = /__jq_orig_initialize/.test(out);
  if (hasOverride) {
    for (const marker of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
      if (!out.includes(marker)) {
        throw new Error(`${b.tag}: claims its own OVERRIDE but is missing ${marker} — refusing`);
      }
    }
  }
  const text = header(b.label, CUT, dropped) + out + (hasOverride ? '' : OVERRIDE);
  if (!DRY) fs.writeFileSync(file, text);
  built.push({ tag: b.tag, src, dropped: dropped.length,
               in2025: dropped.filter(d => d.date >= '2025-01-01').length });
  console.log(`[pit] ${b.tag}: excluded ${dropped.length} name(s) listed >= ${CUT} ` +
              `(${dropped.filter(d => d.date >= '2025-01-01').length} of them only from 2025)`);
}

console.log(`[pit] cutoff ${CUT} (active TRAIN start, read from the harness)`);
if (DRY) console.log('[pit] --dry: nothing written');
else {
  console.log('[pit] run each against its own epoch-9 row:');
  console.log('      73b13d92 objective 1.4926 / sharpe 5.22');
  console.log('      1cc495be objective 0.9954 / sharpe 4.59');
}
