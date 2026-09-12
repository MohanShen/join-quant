/**
 * tutorial-ingest.js — pull JoinQuant's 量化课堂 (quant classroom) into the repo.
 *
 * Endpoints
 *   GET /help/tutorial/GetStudyList?ajax=1&page=<n>&type=<0..4>   the catalog
 *   GET /community/post/detailV2?postId=<id>                      the lesson body
 *
 * Each lesson row carries a `postId`, so the whole curriculum reads through the
 * ordinary community-post endpoint and costs nothing.
 *
 * Two traps this file works around
 * --------------------------------
 * 1. `page` is ignored. Asking for page 1..6 returns the same lessons each time.
 * 2. `studyId` AND `postId` are regenerated per request — the same lesson comes
 *    back under fresh ids on every call. Naively collecting pages yielded 720
 *    "unique" ids for **137 real lessons**. So dedupe on TITLE, which is the only
 *    stable handle the catalog exposes. (Old postIds do still dereference, so a
 *    stale id is safe to fetch with, just not safe to count with.)
 *
 * Why this is worth having: category 0 is a complete factor-research curriculum
 * (data acquisition, winsorizing, standardizing, neutralizing, then IC / return /
 * turnover analysis) — the exact methodology the study loop reasons about — and
 * several 策略与应用 lessons correspond to families already in `wiki/families/`.
 *
 * Output
 *   research/tutorials/<category>/<title>.md   one file per lesson
 *   research/tutorials/README.md               generated index
 *
 * Usage:
 *   node utils/tutorial-ingest.js              # catalog + bodies
 *   node utils/tutorial-ingest.js --catalog    # catalog only, write nothing
 *   node utils/tutorial-ingest.js --limit 20
 */

const fs = require('fs');
const path = require('path');
const jq = require('./jq-http');

const REPO = path.join(__dirname, '..');
const OUT_DIR = path.join(REPO, 'research', 'tutorials');
const J = 'https://www.joinquant.com';

/** The five catalog tabs, in the order the site shows them. */
const CATEGORIES = {
  0: '新手专区',
  1: 'Python编程',
  2: '策略与应用',
  3: '数学课堂',
  4: '经济与市场',
};

const sleep = ms => new Promise(r => setTimeout(r, ms));

const safeName = t => (t || '')
  .replace(/[^一-龥a-zA-Z0-9_\-（）()]/g, '_')
  .replace(/_+/g, '_')
  .slice(0, 70)
  .replace(/^_+|_+$/g, '');

/**
 * Walk the catalog. `page` is ignored by the API, so we ask a few times per
 * category and dedupe on title — repeated calls surface the same lessons under
 * new ids, and occasionally a row the previous call did not include.
 */
async function fetchCatalog({ passes = 6 } = {}) {
  const byTitle = new Map();
  for (const type of Object.keys(CATEGORIES)) {
    for (let page = 1; page <= passes; page++) {
      let json;
      try { json = await jq.jqJson(`${J}/help/tutorial/GetStudyList?ajax=1&page=${page}&type=${type}`); }
      catch { break; }
      const rows = (json && json.data && (json.data.list || json.data)) || [];
      if (!Array.isArray(rows) || !rows.length) break;
      for (const r of rows) {
        if (!r.title) continue;
        const prev = byTitle.get(r.title);
        // Keep the highest learner count seen; refresh postId each time (they expire-ish).
        if (!prev || (parseInt(r.studyCount) || 0) > (parseInt(prev.studyCount) || 0)) {
          byTitle.set(r.title, { ...r, type: Number(type), category: CATEGORIES[type] });
        }
      }
      await sleep(250);
    }
    console.log(`[tutorial] ${CATEGORIES[type].padEnd(12)} cumulative unique lessons: ${byTitle.size}`);
  }
  return [...byTitle.values()];
}

/** Fetch one lesson body. */
async function fetchLesson(row) {
  const json = await jq.jqJson(`${J}/community/post/detailV2?postId=${row.postId}`);
  if (!json || json.code !== '00000' || !json.data) {
    throw new Error(`detailV2 refused: ${(json && json.msg) || 'no data'}`);
  }
  return json.data;
}

function renderLesson(row, detail) {
  const lines = [
    '---',
    `title: ${JSON.stringify(detail.title || row.title)}`,
    `category: ${row.category}`,
    `learners: ${row.studyCount || 0}`,
    `postedAt: ${detail.addTime || ''}`,
    `source: 量化课堂 (/study)`,
    `fetchedAt: ${new Date().toISOString()}`,
  ];
  if (detail.notebookPath) {
    lines.push(`notebookPath: ${JSON.stringify(detail.notebookPath)}`);
    lines.push('notebookAvailable: false   # 克隆研究 only, spends 积分');
  }
  lines.push('# NOTE: postId/studyId are re-minted per request and are NOT recorded —');
  lines.push('#       title + category is this lesson\'s stable handle.');
  lines.push('---', '', `# ${detail.title || row.title}`, '');
  lines.push(String(detail.content || '').trim(), '');
  return lines.join('\n');
}

function writeIndex(saved, catalog) {
  const byCat = {};
  for (const s of saved) (byCat[s.category] = byCat[s.category] || []).push(s);
  const total = catalog.length;

  const md = `# 量化课堂 (JoinQuant quant classroom)

由 \`node utils/tutorial-ingest.js\` 生成，**请勿手改**。
来源：\`/study\` 的 \`help/tutorial/GetStudyList\` + \`community/post/detailV2\`（均免费）。

**${total} 节课**（按标题去重），已抓正文 **${saved.length}** 节。

> ⚠ 目录接口的 \`page\` 参数被忽略，且 \`studyId\`/\`postId\` **每次请求都会重新生成**——
> 同一节课反复出现在不同 id 下（720 个 id 实为 137 节课）。**标题是唯一稳定句柄**，
> 本目录据此去重，文件里也不记录 id。

## 按分类

${Object.entries(CATEGORIES).map(([k, name]) => {
  const rows = (byCat[name] || []).sort((a, b) => (b.learners || 0) - (a.learners || 0));
  const inCat = catalog.filter(c => c.category === name).length;
  return `### ${name} — ${inCat} 节（已抓 ${rows.length}）\n\n` +
    (rows.length
      ? '| 课程 | 学习人数 |\n|---|---|\n' +
        rows.slice(0, 40).map(r => `| [${r.title}](${encodeURI(name + '/' + r.file)}) | ${r.learners} |`).join('\n')
      : '_（未抓取）_');
}).join('\n\n')}

## 为什么值得留着

- **新手专区**里的「因子专题」是一条完整的因子研究方法论链：数据获取 → 去极值 →
  标准化 → 中性化 → 收益/信息/换手三段有效性分析。auto-study 的实验设计正是围绕
  这些步骤展开，可直接引用。
- **策略与应用**里多节课与 \`wiki/families/\` 已有家族对应（如「【量化课堂】机器学习多因子策略」
  对应 [[多因子ML]]、「季报预告信号策略的失效」对应该家族的同名成员）。
- 课程正文免费；附带的 notebook 与社区帖一样，需要「克隆研究」并消耗积分。
`;
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(path.join(OUT_DIR, 'README.md'), md);
}

async function run({ limit = 0, catalogOnly = false } = {}) {
  const catalog = await fetchCatalog();
  console.log(`[tutorial] catalog: ${catalog.length} unique lessons`);
  const byCat = {};
  catalog.forEach(c => { byCat[c.category] = (byCat[c.category] || 0) + 1; });
  console.log('[tutorial] by category:', JSON.stringify(byCat));
  if (catalogOnly) return { catalog, saved: [] };

  const targets = limit > 0 ? catalog.slice(0, limit) : catalog;
  const saved = [];
  let failed = 0;

  for (const row of targets) {
    try {
      const detail = await fetchLesson(row);
      const body = String(detail.content || '');
      if (!body.trim()) { failed++; continue; }
      const dir = path.join(OUT_DIR, row.category);
      fs.mkdirSync(dir, { recursive: true });
      const file = `${safeName(row.title)}.md`;
      fs.writeFileSync(path.join(dir, file), renderLesson(row, detail));
      saved.push({ title: row.title, category: row.category, learners: parseInt(row.studyCount) || 0, file, bytes: body.length });
    } catch (e) {
      failed++;
      console.error(`[tutorial] ✗ ${row.title.slice(0, 40)} :: ${e.message.split('\n')[0].slice(0, 70)}`);
    }
    await sleep(700);
  }

  writeIndex(saved, catalog);
  const bytes = saved.reduce((n, s) => n + s.bytes, 0);
  console.log(`[tutorial] saved ${saved.length}/${targets.length} lessons (${(bytes / 1024).toFixed(0)} KB), failed ${failed}`);
  console.log(`[tutorial] wrote ${path.relative(REPO, OUT_DIR)}/README.md`);
  return { catalog, saved };
}

if (require.main === module) {
  const args = process.argv.slice(2);
  const li = args.indexOf('--limit');
  run({ limit: li >= 0 ? parseInt(args[li + 1], 10) : 0, catalogOnly: args.includes('--catalog') })
    .catch(e => { console.error(e.message || e); process.exitCode = 1; })
    .finally(() => jq.close());
}

module.exports = { fetchCatalog, fetchLesson, run, CATEGORIES };
