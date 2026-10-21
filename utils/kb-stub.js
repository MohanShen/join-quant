/**
 * kb-stub.js — auto-generate wiki stub pages for newly-normalized strategies, and
 * regenerate the per-concept 归一化绩效横评 tables. Heuristic (no LLM 忠实翻译); each
 * stub is marked `autoStub: true` so a later /ingest-strategy can enrich it.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const SDIR = path.join(ROOT, 'wiki/strategies');
const CDIR = path.join(ROOT, 'wiki/concepts');

function headerField(src, key) {
  const m = src.match(new RegExp('^#\\s*' + key + ':\\s*(.+)$', 'm'));
  return m ? m[1].trim() : '';
}

// Heuristic concept/factor classifier from source text (controlled vocab, wiki-schema §2).
function classify(src) {
  const has = re => re.test(src);
  const cnt = re => (src.match(re) || []).length;
  const concepts = new Set();
  const factors = { 选股: [], 择时: [], 风控: [], 仓位: [] };

  // Small-cap: market_cap sorting within a small-cap universe.
  const smallcap = has(/market_cap/) && has(/399101|399303|000905|深证综指|国证2000|微盘|小市值|中证1000/);
  if (smallcap) { concepts.add('小市值因子'); factors.选股.push('规模价值·小市值'); }
  if (has(/国九条|三正因子/)) factors.选股.push('质量基本面·国九条');

  // ETF rotation: ETF must be the core theme (many refs) or the benchmark.
  if (cnt(/ETF/g) >= 8 || has(/set_benchmark\(["'](?:51\d{4}|159\d{3}|518880|511\d{3})/)) { concepts.add('ETF轮动'); factors.选股.push('ETF动量'); }
  if (has(/网格/)) { concepts.add('网格交易'); factors.仓位.push('网格分档'); }
  if (has(/RSRS/)) { concepts.add('择时-RSRS'); factors.择时.push('RSRS'); }
  if (has(/龙虎榜/)) concepts.add('龙虎榜');
  // 打板/涨停: require板-specific terms (not standalone 涨停/龙头, which appear as filters elsewhere).
  if (has(/打板|首板|连板|炸板|一进二|涨停.*接力|竞价.*(打板|首板)/)) concepts.add('打板与涨停');
  if (has(/动量|RPS|KAMA|唐奇安|趋势跟踪|momentum/i)) { concepts.add('动量与趋势'); factors.选股.push('动量'); }
  // MA-based market timing (specific signals, not any 择时/均线).
  if (has(/均线择时|大盘.{0,4}MA|MA\d+.{0,6}(择时|偏离)|深证综指.{0,6}(MA|偏离)|二八(轮动|择时)|大盘趋势|市场温度/)) { concepts.add('择时-均线'); factors.择时.push('趋势均线'); }
  if (has(/多因子|机器学习|sklearn|KNN|逻辑回归|LogisticRegression|SVR|ml_factor|多任务学习|因子截面/i)) concepts.add('多因子模型');
  if (has(/均值回归|反转因子|超跌反弹/)) concepts.add('均值回归');
  if (has(/RealFuture|股指期货|商品期货|跨期套利/)) concepts.add('期货与套利');
  if (has(/行业轮动|板块轮动|申万.{0,4}轮动/)) concepts.add('行业轮动');
  if (has(/做T|日内回转|高抛低吸|回转交易/)) concepts.add('日内做T');
  if (has(/SubPortfolio|多子策略|资金隔离|多策略.{0,4}(并行|组合)/)) concepts.add('多策略组合');

  if (has(/止损/)) factors.风控.push('止损线');
  if (has(/止盈/)) factors.风控.push('止盈');
  if (has(/等权/)) factors.仓位.push('等权');

  if (concepts.size === 0) concepts.add('未分类');
  return { concepts: [...concepts], factors };
}

function factorsYaml(f) {
  const parts = [];
  for (const role of ['选股', '择时', '风控', '仓位']) {
    if (f[role].length) parts.push(`  ${role}: [${[...new Set(f[role])].join(', ')}]`);
  }
  return parts.length ? parts.join('\n') : '  选股: [未分类]';
}

const pct = x => (x * 100).toFixed(1).replace(/\.0$/, '') + '%';
const safe = t => t.replace(/[\\/:*?"<>|#\[\]]/g, '').replace(/\s+/g, '').slice(0, 24);

/**
 * The `normalized:` frontmatter line — ONE builder, used by both the create and the stamp path.
 *
 * CLAUDE.md designates this line the DURABLE BACKUP of harness/normalize-*.tsv, which is
 * gitignored and has already regressed from ~119 rows to 18 once. Two copies of its format would
 * be free to drift, and `normalize-ledger-rebuild.js` parses it.
 */
/**
 * Free static flags for KNOWN unrealizability patterns, stamped BESIDE the measurement.
 *
 * ⚠⚠ This is the answer to "should realizability be checked before normalize?" — and the answer is
 * a FLAG, never a gate. Realizability needs measurement (大小盘轮动's R=2 took `liq-1` across three
 * floors, 31 JQ minutes, and the counter-intuitive answer was that the floor removed ZERO names),
 * and a pre-measurement reject must be a known fact, never a guess — one guess-based screening
 * rule discarded 287 of 549 strategies. Worse, the measurement is what EXPOSES the problem:
 * 7a1c225f's 100× unit bug was found by studying a book that had already been measured, and a
 * pre-filter would have hidden it along with the two siblings it turned out to share it with.
 *
 * So what moves earlier is the WARNING, not the decision. It lands here because this line is what
 * feeds §3, `wiki/types/` and champion resolution — the reader who needs the caveat is the one
 * looking at the table, not someone who later finds §4.
 */
/**
 * ⚠⚠⚠ THIS WAS DEAD CODE FOR ITS ENTIRE LIFE — defined, never called, never exported.
 *
 * CLAUDE.md states that `kb-stub` "stamps `realizabilityFlags:` beside the `normalized:` block,
 * because that line is what feeds §3, `wiki/types/` and champion resolution — the reader who
 * needs the caveat is the one looking at the table". The lint was written, the 18-of-259
 * measurement was taken from its CLI, the rationale was recorded — and the writer was never
 * wired into the page. Measured 2026-10-22: **0 of 256 wiki pages carried a flag line.**
 *
 * It mattered the same night: the four highest-scoring books on the epoch-9 bench are all
 * limit-up/auction entries (objective 7.85 / 7.55 / 5.29 / 2.12, sharpe 11.95 / 11.46 / 11.48 /
 * 5.14), 打板短线's realizability is measured 1, and a §3 reader had nothing on the page to weigh
 * against those numbers.
 */
function realizabilityLine(sourceFile) {
  if (!sourceFile) return null;
  let flags = [];
  try { flags = require('./realizability-lint').lintFile(sourceFile); } catch { return null; }
  if (!flags.length) return null;
  const fmt = f => `${f.id}${f.severity === 'measured' ? '!' : ''}`;
  return `realizabilityFlags: [${flags.map(fmt).join(', ')}]   # static, FREE, never a veto — ` +
         `node utils/realizability-lint.js ${sourceFile}`;
}

/**
 * The window LABEL stamped into the block, derived from the harness.
 *
 * ⚠ This was the literal string "TRAIN 2022-2023". It survived five epoch bumps because none of
 * them moved the windows — and epoch 9 moves TRAIN to 2024, at which point the hard-coded label
 * would have stamped "TRAIN 2022-2023" onto a 2024 measurement in the one block CLAUDE.md
 * designates as the ledger's DURABLE BACKUP. `normalize-ledger-rebuild.js` reads this label back
 * to recover a row's window, so a wrong label would have been reconstructed as fact.
 * Exactly the class of bug the epoch config exists to prevent: a constant duplicated outside it.
 */
function windowLabel(windowName = 'train') {
  const harness = require('./harness-config');
  const ys = harness.windowYears(windowName).map(y => y.year);
  const tag = windowName.toUpperCase();
  if (!ys.length) return tag;
  return ys.length === 1 ? `${tag} ${ys[0]}` : `${tag} ${ys[0]}-${ys[ys.length - 1]}`;
}

function normalizedLine(metrics) {
  const harness = require('./harness-config');
  const a = metrics.annual / 100, m = metrics.maxdd / 100;
  const epoch = metrics.epoch != null ? metrics.epoch : harness.config().epoch;
  return `normalized: { epoch: ${epoch}, window: "${windowLabel('train')}", annualReturn: ${a.toFixed(4)}` +
         `, sharpe: ${metrics.sharpe}, maxDrawdown: ${m.toFixed(4)}, objective: ${metrics.obj}` +
         `, gate: ${metrics.gate} }`;
}

/**
 * Write the measurement onto a page that ALREADY EXISTS.
 *
 * ⚠ createStub used to `return { existed: true }` and write nothing at all. So any strategy that
 * already had a page — one from /ingest-strategy, or an earlier pass — never received a
 * `normalized:` block when it was measured, and its measurement lived ONLY in the then-gitignored
 * ledger. Measured 2026-10-05: 16 of 136 normalized rows were in that state, unrecoverable by
 * `normalize-ledger-rebuild.js` if the ledger regressed again.
 *
 * Touches nothing but that one frontmatter line, and is idempotent: an unchanged line is not
 * rewritten, so a page's mtime and any human edits elsewhere are left alone.
 */
/**
 * Add or refresh a page's `realizabilityFlags:` line.
 *
 * ⚠ Unlike `stampNormalized`, this one REPLACES rather than being add-only, and the difference is
 * principled, not a shortcut. The `normalized:` block is co-authored — 74 pages carry a `ranAt:`
 * this builder does not emit — so rewriting it from the ledger destroyed provenance and was
 * reverted within the hour. This line has no human-authored part: every character of it is
 * derived from the source file by `realizability-lint`, so the generated text IS the truth and a
 * stale one is simply wrong. Verified before writing: 0 of 256 pages carried the line at all, so
 * there were no hand edits to preserve.
 *
 * ⚠ It also REMOVES the line when the source no longer flags anything. A flag that lingers after
 * the pattern stops matching is worse than no flag, the same reason `limit-up-entry` was deleted:
 * a reader who finds one wrong entry stops trusting the column.
 *
 * @returns 'added' | 'updated' | 'unchanged' | 'removed' | 'none' | 'no-frontmatter' | 'no-source'
 */
function stampRealizability(file, sourceFile) {
  // ⚠⚠ `sourceFile` MUST be repo-relative, and passing an absolute path THROWS rather than
  // quietly doing nothing. `realizability-lint.lintFile(rel)` does `path.join(ROOT, rel)`, which
  // turns an absolute path into garbage, so `readFileSync` throws into a `catch` that returns
  // `[]` — indistinguishable from "this book has no flags". I hit exactly that writing this
  // function: the dry run reported 34 pages to stamp and the real run stamped 0, because one
  // path passed `src` and the other passed `path.join(ROOT, src)`. Same precedent as
  // `logicalSourceFile()`, which throws on a path escaping the repo rather than writing a hidden
  // file: a silent wrong answer costs more than a loud refusal.
  if (sourceFile && path.isAbsolute(sourceFile)) {
    throw new Error(`stampRealizability: sourceFile must be repo-relative, got ${sourceFile}`);
  }
  let t;
  try { t = fs.readFileSync(file, 'utf8'); } catch { return 'unreadable'; }
  if (!t.startsWith('---')) return 'no-frontmatter';
  const end = t.indexOf('\n---', 3);
  if (end < 0) return 'no-frontmatter';
  if (!sourceFile || !fs.existsSync(path.join(ROOT, sourceFile))) return 'no-source';

  const want = realizabilityLine(sourceFile);
  const fm = t.slice(0, end);
  const have = (fm.match(/^realizabilityFlags:.*$/m) || [])[0] || null;

  if (!want && !have) return 'none';
  if (want === have) return 'unchanged';
  if (!want && have) {
    fs.writeFileSync(file, fm.replace(/^realizabilityFlags:.*$\n?/m, '') + t.slice(end));
    return 'removed';
  }
  if (have) {
    fs.writeFileSync(file, fm.replace(/^realizabilityFlags:.*$/m, want) + t.slice(end));
    return 'updated';
  }
  // New line goes directly after `normalized:` when there is one — CLAUDE.md's reason for this
  // field is that the reader looking at the measurement is the one who needs the caveat, so it
  // belongs beside it, not at the end of the frontmatter.
  const next = /^normalized:.*$/m.test(fm)
    ? fm.replace(/^(normalized:.*)$/m, `$1\n${want}`)
    : `${fm}\n${want}`;
  fs.writeFileSync(file, next + t.slice(end));
  return 'added';
}

function stampNormalized(file, metrics) {
  if (!metrics || metrics.annual == null || metrics.sharpe == null) return 'no-metrics';
  let t;
  try { t = fs.readFileSync(file, 'utf8'); } catch { return 'unreadable'; }
  if (!t.startsWith('---')) return 'no-frontmatter';      // never guess where to put it
  const end = t.indexOf('\n---', 3);
  if (end < 0) return 'no-frontmatter';
  const line = normalizedLine(metrics);
  const fm = t.slice(0, end);

  // ⚠ ADD-ONLY. Replacing an existing block was tried and REVERTED the same hour: 74 of these
  // pages carry fields this builder does not emit (`ranAt`, the measurement date), so rewriting
  // the line from the ledger silently stripped provenance from 70 pages — the same class of
  // quiet data loss this whole review is about. The gap being closed here is a MISSING block;
  // correcting a stale one is a different job and `utils/wiki-epoch-repair.js` already owns it.
  if (/^normalized:/m.test(fm)) return 'present';

  fs.writeFileSync(file, fm + '\n' + line + t.slice(end));
  return 'added';
}

// Create/overwrite a stub page. metrics: {annual%, sharpe, maxdd%, obj, gate}. Returns {path, concepts, existed}.
function createStub(srcFile, fullSrc, metrics) {
  const postId = headerField(fullSrc, 'postId');
  const title = headerField(fullSrc, 'title') || path.basename(srcFile, '.py');
  const post = headerField(fullSrc, 'joinquantPost') || (fullSrc.match(/joinquant\.com\/post\/(\d+)/) || [])[0] || '';
  const pid8 = postId.slice(0, 8);
  const existing = fs.readdirSync(SDIR).find(f => f.startsWith(pid8 + '_'));
  if (existing) {
    // Existing page: still record the measurement. Returning early here is what left 16
    // measurements with no durable copy outside the ledger.
    const full = path.join(SDIR, existing);
    const stamped = stampNormalized(full, metrics);
    return { path: full, existed: true, concepts: null, stamped };
  }

  const { concepts, factors } = classify(fullSrc);
  const a = metrics.annual / 100, m = metrics.maxdd / 100;
  // ⚠ Both of these used to be hard-coded (`epoch: 1`, `夏普<2.5`) and had gone stale.
  // The stamped epoch matters far more than it looks: CLAUDE.md designates this `normalized:`
  // block the DURABLE BACKUP of harness/normalize-*.tsv (which has already
  // regressed from ~119 rows to 18 once). Every one of the 120 existing pages claimed epoch 1
  // while the ledger said 2 or 4, so a rebuild would have reconstructed a mislabelled ledger.
  const harness = require('./harness-config');
  const epoch = metrics.epoch != null ? metrics.epoch : harness.config().epoch;
  const bar = harness.stageThreshold('normalize');
  const gateTxt = metrics.gate === 'pass' ? '过门槛' : `未过门槛 夏普<${bar}`;

  // Family PROPOSAL — deliberately not `family:`.
  //
  // A stub used to carry no family at all, and wiki-family-build skips pages without one
  // (`if (!fm.family) continue`), so every newly fetched member of an existing family was
  // invisible to that family's page. But auto-assigning is not safe either: measured against
  // the 175 hand-labelled pages, code matching decides only 31 of them, and that 31 is the very
  // set its abstain rules were tuned against — so its precision is not an independent estimate.
  // A wrong assignment corrupts §3, memberCount and the type layer above it, silently and in
  // the direction of the biggest families.
  //
  // So the stub records a PROPOSAL that wiki-family-build ignores. The member stops being
  // invisible (it shows up in `family-match --pending`) without anything being asserted.
  // Promotion to `family:` is a human / `/ingest-strategy` decision.
  let proposal = '';
  try {
    const fm = require('./family-match');
    const r = fm.match(fullSrc, fm.familyBases().bases);
    if (r.family) proposal = `familyProposal: ${r.family}\nfamilyProposalScore: ${r.score}\n`;
    else if (r.ranked[0]) proposal = `familyProposal: ~\nfamilyProposalNote: ${r.reason}\n`;
  } catch { /* matching is advisory; never block stub creation on it */ }
  const md = `---
postId: ${postId}
title: ${title}
sourceFile: ${srcFile}
${post ? 'joinquantPost: ' + (post.startsWith('http') ? post : 'https://www.joinquant.com/post/' + post) + '\n' : ''}concepts: [${concepts.join(', ')}]
factors:
${factorsYaml(factors)}
${proposal}ingestedAt: ${new Date().toISOString().slice(0, 10)}
codeLines: ${fullSrc.split('\n').length}
stats: { 绩效未公开: true }
${normalizedLine(metrics)}
${realizabilityLine(srcFile) ? realizabilityLine(srcFile) + '\n' : ''}autoStub: true
---

# ${title}

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 \`/ingest-strategy\` 补全。

## 绩效
📊 归一化（${windowLabel('train')}，零滑点）：年化 ${pct(a)} | 夏普 ${metrics.sharpe} | 最大回撤 ${pct(m)} | objective ${metrics.obj}（${gateTxt}）。自报绩效未公开。

## 涉及概念
${concepts.map(c => `- [[${c}]]`).join('\n')}

## 备注
- ⚙ **自动桩页**（\`autoStub: true\`）：概念/因子为源码启发式推断，未做忠实翻译。运行 \`/ingest-strategy strategies/${path.basename(srcFile)}\` 可补全并去除该标记。
`;
  const outPath = path.join(SDIR, `${pid8}_${safe(title)}.md`);
  fs.writeFileSync(outPath, md);
  return { path: outPath, existed: false, concepts };
}

// Regenerate all concept 归一化绩效横评 tables from current normalized blocks (idempotent).
function regenConceptTables() {
  const harness = require('./harness-config');   // live gate, not a frozen literal
  const byC = {};
  for (const f of fs.readdirSync(SDIR).filter(f => f.endsWith('.md'))) {
    const src = fs.readFileSync(path.join(SDIR, f), 'utf8');
    const nm = src.match(/^normalized: \{([^}]*)\}/m); if (!nm) continue;
    const cm = src.match(/^concepts:\s*\[([^\]]*)\]/m); if (!cm) continue;
    const g = k => (nm[1].match(new RegExp(k + ':\\s*([^,]+)')) || [])[1]?.trim();
    const rec = { page: f.replace(/\.md$/, ''), annual: parseFloat(g('annualReturn')) * 100, maxdd: parseFloat(g('maxDrawdown')) * 100, sharpe: parseFloat(g('sharpe')), obj: g('objective'), gate: g('gate') };
    for (const c of cm[1].split(',').map(s => s.trim()).filter(Boolean)) (byC[c] ||= []).push(rec);
  }
  const ov = r => (r.obj === 'DQ' ? -999 + r.sharpe / 1000 : parseFloat(r.obj));
  let n = 0;
  for (const [c, mem] of Object.entries(byC)) {
    const cf = path.join(CDIR, c + '.md'); if (!fs.existsSync(cf)) continue;
    let src = fs.readFileSync(cf, 'utf8');
    const i = src.indexOf('\n## 归一化绩效横评'); if (i >= 0) src = src.slice(0, i).replace(/\s*$/, '') + '\n';
    if (mem.length < 2) { fs.writeFileSync(cf, src); continue; }
    mem.sort((a, b) => ov(b) - ov(a));
    const nP = mem.filter(m => m.gate === 'pass').length;
    let t = `\n## 归一化绩效横评（TRAIN 2022–2023）\n> 同一区间/同一成本(零滑点)/同一 objective 的 apples-to-apples 横评；按 objective 排序。本概念归一化成员 ${mem.length}，过门槛(夏普≥${harness.stageThreshold('normalize')}) ${nP}。⚠ 打板/涨停类成交假设不真实，其数值仅参考。\n\n| 策略 | 年化 | 回撤 | 夏普 | objective | gate |\n|------|------|------|------|-----------|------|\n`;
    for (const m of mem) t += `| [[${m.page}]] | ${m.annual.toFixed(0)}% | ${m.maxdd.toFixed(1)}% | ${m.sharpe.toFixed(2)} | ${m.obj} | ${m.gate === 'pass' ? '✅' : '❌'} |\n`;
    src = src.replace(/\n?$/, '\n' + t);
    src = src.replace(/^(updatedAt:).*$/m, '$1 ' + new Date().toISOString().slice(0, 10));
    fs.writeFileSync(cf, src); n++;
  }
  return n;
}

module.exports = { stampNormalized, stampRealizability, realizabilityLine, normalizedLine, classify, createStub, regenConceptTables, headerField, windowLabel };
