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

// Create/overwrite a stub page. metrics: {annual%, sharpe, maxdd%, obj, gate}. Returns {path, concepts, existed}.
function createStub(srcFile, fullSrc, metrics) {
  const postId = headerField(fullSrc, 'postId');
  const title = headerField(fullSrc, 'title') || path.basename(srcFile, '.py');
  const post = headerField(fullSrc, 'joinquantPost') || (fullSrc.match(/joinquant\.com\/post\/(\d+)/) || [])[0] || '';
  const pid8 = postId.slice(0, 8);
  const existing = fs.readdirSync(SDIR).find(f => f.startsWith(pid8 + '_'));
  if (existing) return { path: path.join(SDIR, existing), existed: true, concepts: null };

  const { concepts, factors } = classify(fullSrc);
  const a = metrics.annual / 100, m = metrics.maxdd / 100;
  const gateTxt = metrics.gate === 'pass' ? '过门槛' : '未过门槛 夏普<2.5';
  const md = `---
postId: ${postId}
title: ${title}
sourceFile: ${srcFile}
${post ? 'joinquantPost: ' + (post.startsWith('http') ? post : 'https://www.joinquant.com/post/' + post) + '\n' : ''}concepts: [${concepts.join(', ')}]
factors:
${factorsYaml(factors)}
ingestedAt: ${new Date().toISOString().slice(0, 10)}
codeLines: ${fullSrc.split('\n').length}
stats: { 绩效未公开: true }
normalized: { epoch: 1, window: "TRAIN 2022-2023", annualReturn: ${a.toFixed(4)}, sharpe: ${metrics.sharpe}, maxDrawdown: ${m.toFixed(4)}, objective: ${metrics.obj}, gate: ${metrics.gate} }
autoStub: true
---

# ${title}

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 \`/ingest-strategy\` 补全。

## 绩效
📊 归一化（TRAIN 2022–2023，零滑点）：年化 ${pct(a)} | 夏普 ${metrics.sharpe} | 最大回撤 ${pct(m)} | objective ${metrics.obj}（${gateTxt}）。自报绩效未公开。

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
    let t = `\n## 归一化绩效横评（TRAIN 2022–2023，epoch 1）\n> 同一区间/同一成本(零滑点)/同一 objective 的 apples-to-apples 横评；按 objective 排序。本概念归一化成员 ${mem.length}，过门槛(夏普≥2.5) ${nP}。⚠ 打板/涨停类成交假设不真实，其数值仅参考。\n\n| 策略 | 年化 | 回撤 | 夏普 | objective | gate |\n|------|------|------|------|-----------|------|\n`;
    for (const m of mem) t += `| [[${m.page}]] | ${m.annual.toFixed(0)}% | ${m.maxdd.toFixed(1)}% | ${m.sharpe.toFixed(2)} | ${m.obj} | ${m.gate === 'pass' ? '✅' : '❌'} |\n`;
    src = src.replace(/\n?$/, '\n' + t);
    src = src.replace(/^(updatedAt:).*$/m, '$1 ' + new Date().toISOString().slice(0, 10));
    fs.writeFileSync(cf, src); n++;
  }
  return n;
}

module.exports = { classify, createStub, regenConceptTables, headerField };
