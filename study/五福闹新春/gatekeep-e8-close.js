/**
 * gatekeep-e8-close.js — final gatekeeper pass of the e8 round for 五福闹新春.
 *
 * Three bookkeeping writes, no experiments dispatched (the round is being stopped):
 *   1. q-e8-5 (13:10 -> 14:50) -> dropped. Its falsifier is conjunctive and the second conjunct
 *      is now false (q-e8-2 measured 0.0308, not <=0.015), so as written it cannot reach its
 *      stated conclusion; re-specification would need >1 run. Time-of-day axis declared finished.
 *   2. q-e8-8 (pit3) minted as dropped — q-e8-3's implication named it, so `spawned=none` was a
 *      real dangling link. Rejected on the family's OWN standing design constraint (breadth must
 *      be held constant), not on redundancy.
 *   3. q-e8-3's findings.tsv `spawned` column: none -> q-e8-8, so the two links point at each
 *      other (the property `research-queue.js`'s header calls the thing that makes the loop a loop).
 *
 * Run: node -e "require('./study/五福闹新春/gatekeep-e8-close.js').main()"
 */

const fs = require('fs');
const path = require('path');
const rq = require('/Users/mshen/join-quant/utils/research-queue');

const FAMILY = '五福闹新春';
const FINDINGS = path.join('/Users/mshen/join-quant/study', FAMILY, 'findings.tsv');

// ── 1. q-e8-5 -> dropped ────────────────────────────────────────────────────

const DROP_E8_5 = `

gatekeeper pass 4 (本轮收尾，orchestrator 已宣布不再资助回测) — **转 dropped，时点轴对本族宣布结束**。
原 note 写的条件派发在 0.0308 处沉默（门是 ≤0.015 跑 / >0.048 drop），所以它既没有被触发也没有被取消，
必须由 gatekeeper 定案。三条独立理由，任一条单独成立即不该派发：

(a) **证伪项作为合取式已死**（recorder 的观察，核过为真）：原文是「|Δobj| ≥ 0.10 **且** q-e8-2 已显示
局部稳定（≤0.015）⇒ objective 是成交分钟的平滑函数、13:10 承载约四分之一的分数」。q-e8-2 实测 0.0308
= 该上限的 2.1 倍，第二个合取项为假，故本测无论读出什么都到不了它写下的结论。

(b) **两个点不是同一个扰动的不同幅度，所以设计承诺的「三点曲线」不存在**。本条自己的 why 已列出五个
同动通道，其中放量外推乘子 projected_today_vol = today_vol * (240/elapsed)：13:10 → 13:12 把它从
1.846 移到 1.875（**+1.6%**），13:10 → 14:50 把它移到 1.043（**−43%**，相对变化 1.77 倍）。即 13:12 几乎
只动成交价与快照末点，而 14:50 把一个机制通道整体换掉。把 (13:10, 13:12, 14:50) 并排读成「成交分钟
的形状」是把两种不同的扰动画在一根横轴上——这不是幅度更大的同一次实验。

(c) **重新规格化会使它不再是一次实验**。要让一个 14:50 读数能区分「13:10 是被挑出来的峰」与「每一对
分钟都差 ~0.03、位移越大累积越多」，需要一个「噪声随位移如何增长」的模型，而这恰恰是未知量——手上只有
一个位移点（2 分钟）。取得它至少要再加 3–4 个位移点，即 ≥4 次回测去测一个**测量精度**问题，而且测的是
base 这本书，**不是本族的候选**（候选是成员 73b13d92，0.4848）。违反队列契约第 2 条（一条目一实验）与
第 6 条（预算意识）。

**它原本要服务的决定都已由更便宜的路径取定**：§1 已改写为「引用头条须写 ≈0.375 ± 0.03」并禁止四位有效
数字读法（q-e8-2），所以「base 的绝对水平挂在一个分钟上」这个风险已经被定价进页面；而它的第二个动机
「两个 fork 的低分由时点解释」已由 q-e8-2 **关闭**（5ac906ea 本就在 13:12 成交、差 ~0.12，纯时点只值
0.031，故 ~0.09 属代码差异）。

⚠ 诚实的残余：「局部平坦 vs 全局有坡」这个形状问题**仍然开着**，本条目不声称它已被回答——声称的是
**它不能由一次回测回答**，且在本族当前的约束下不值得为它开一个多点扫描。若将来有人要重开，重开的形式
是「预先导出噪声-位移关系的多点分钟扫描」，而不是本条目；本次**不**代为铸造那一条（生成不是 gatekeeper
的职责）。至此**时点轴对本族结束**。`;

// ── 2. the unminted follow-up, minted as dropped ────────────────────────────

const PIT3 = {
  id: 'q-e8-8',
  kind: 'understand',
  title: 'pit3 瘦身检验：pit9 的 9 只 → 只留从不被 ¥2e7 地板咬到的三只大名字（518880 黄金 / 513100 纳指 / 513500 标普）',
  hypothesis: '（q-e8-3 implication 原拟的提法，照录以便将来可审）若 pit9 的 2022 超额就坐在那四只填不满的薄名字上，pit3 的 2022 total 应显著低于 q-e8-3 的 52.81；若 pit3 的 2022 ≈ 52.81，则广度结论与薄名字无关。q-e8-3 称这是「q-e8-7 那条广度结论唯一还能被推翻的方式」',
  why: 'q-e8-3 的 implication 明确点名了它（且 findings.tsv 的 spawned 为 none，--lint 因此报悬空），故必须落一个条目而不是让它消失。但 gatekeeper 判定**不派发**，理由见 note——核心是它违反本族自己的广度配平约束，而不是 orchestrator 初读的「与 q-e8-3 冗余」',
  design: '（未执行）variants/q-e8-7_weak-pit9.py 的走弱池由 9 只截到 3 只（518880/513100/513500），同一编辑点、零自由度，与 q-e8-7 (0.3962) 及 q-e8-3 (0.3463) 并读；报 2022/2023 拆分 + WEAKHOLD 普查',
  from: ['q-e8-3', 'q-e8-7', 'q-e8-1'],
  edgeRef: '趋势择时',
  rank: 99,
  status: 'dropped',
  note: `gatekeeper pass 4（本轮收尾）：**铸为 dropped**，以关闭 q-e8-3 的 spawned 悬空链接。

**先更正 orchestrator 自己提出待裁的那个读法**（他的结论对，前提不对）：pit3 **不是**在重测 q-e8-3 已
拿到的 −0.0499。地板从未咬到的是**四只**（518880 / 513100 / 513500 / **159980 有色**，逐名剔除 0/294），
且 159985 豆粕只被剔 19/294——而 159985 恰是 pit9 里**最常被选中的腿**（普查 57 日，q-e8-3 重数 53 日，
两种计数下都是第一名），在地板下还**升到 60/294**。所以 pit3 相对 q-e8-3 是**再砍掉两只地板留下的名字，
其中一只是第一主力腿**，effective breadth 从 6.27 降到 3。它会测出一个与 −0.0499 **实质不同**的数，
冗余论站不住。

**真正的否决理由：它违反本族自己的标准设计约束。** §4 由 q-e8-1 开出、经 q-e8-7 证实有效的那一条是
「任何改走弱池的实验必须保持池内名额数不变，否则『哪些名字』与『每天是否有东西通过趋势滤波』永远分不
开」。pit3 把名额数从 9（或地板下的 6.27）压到 3。本族已经测出兜底率随广度单调变化：
**N=1 → 178/294 (60.5%) · 有效 6.27 → 59/294 (20.1%) · N=9 → 43/294 (14.6%)**，
所以 N=3 的兜底率会落在明显更高的一档。于是一个偏低的 pit3 读数先验地同时兼容两个答案——「薄名字携带
2022 超额」与「广度 3 太窄、走弱期趋势滤波常把池滤空」——**这正是 q-e8-1 已经用一次回测买到过的结构性
局限，在 N=3 上原样重演**。本族不该为同一个混淆付第二次钱。

**而配平版造不出来。** 要在保持广度 9 的同时只用不被地板咬的名字，就得从 base 自己那 17 只之外补 6 只；
点时合法的 9 只里只有 **3 只**日均成交中位 ≥¥1亿（518880 6.83 / 513100 2.97 / 513500 1.84），≥¥0.2亿 的
也只有 6 只。补外部名字会把**唯一还完全未结的那一项**（资产类别事后性，§4）作为新混淆重新引入——用一个
新的事后性去测一个旧的归属问题，净信息为负。

**顺带：它要答的问题已有一半是免费的。** q-e8-3 的年度迁移（2022 **−12.85pp** / 2023 **+4.95pp**）加逐名
迁移表（501018 46→8 日、513030 44→14 日 ⇒ 159985 53→60、513100 40→45、518880 13→32、513500 5→17）
**就是**「2022 超额偏向薄名字」这一向的测量；pit3 的边际贡献只剩「三只大名字独处时的角点」，而那个 Δ
按 q-e8-2 的地板（0.031）只读得出符号、读不出幅度，还带着上面的广度混淆。

⚠ **诚实承认的一点边际价值，以及正确的工具**：pit3 的广度 3 ≈ ¥1亿 地板的平均存活数 **3.15**（免费容量
曲线），即 5× 本次已测地板——而 §4 记着「R=3 需要 5–10× 本金对应的地板点，本轮未资助」。所以这条轴上
确有一个未取的绩效读数。但正确的仪器是**在 pit9 上把地板改成 ¥1e8**（同一编辑点、零自由度、保留逐日
变动的成员资格），**不是**一张硬写死的三名池——后者把「当日流动性」换成了「永久排除」，两者不是同一个
问题。本次**不**代为铸造那个地板点（生成不是 gatekeeper 的职责，且本轮不再资助回测）。

**重开条件**：(i) 有人为 realizability R=3 资助一个 5–10× 地板的**绩效**点——届时铸 ¥1e8 地板点，不是
pit3；或 (ii) 拿到逐日点时上市/流动性数据集，届时广度配平的全流动池才造得出来，而那时本条目会并入 §4
「逐日点时海外池」那一项，不再独立存在。`,
  result: null,
};

// ── 3. make the two links point at each other ───────────────────────────────

function fixSpawned() {
  const text = fs.readFileSync(FINDINGS, 'utf8');
  const lines = text.split('\n');
  const SPAWNED = rq.FINDING_COLUMNS.indexOf('spawned');
  if (SPAWNED !== 10) throw new Error(`spawned moved to index ${SPAWNED} — re-check before writing`);
  let hits = 0;
  const out = lines.map(l => {
    if (!l.trim()) return l;
    const c = l.split('\t');
    if (c[0] !== 'q-e8-3') return l;
    if (c[SPAWNED] !== 'none') throw new Error(`q-e8-3 spawned is already ${JSON.stringify(c[SPAWNED])} — refusing to overwrite`);
    c[SPAWNED] = PIT3.id;
    hits++;
    return c.join('\t');
  });
  if (hits !== 1) throw new Error(`expected exactly 1 q-e8-3 finding row, found ${hits}`);
  fs.writeFileSync(FINDINGS, out.join('\n'));
  return hits;
}

function main() {
  const q = rq.load(FAMILY);

  // 1. q-e8-5
  const e5 = q.find(e => e.id === 'q-e8-5');
  if (!e5) throw new Error('q-e8-5 not found');
  if (e5.status !== 'queued') throw new Error(`q-e8-5 is ${e5.status}, expected queued`);
  e5.status = 'dropped';
  e5.rank = 99;                       // same convention as q-e8-4 / q-e8-6 / imp-7 / imp-8
  e5.note = (e5.note || '') + DROP_E8_5;
  const bad5 = rq.validate(e5);
  if (bad5.length) throw new Error('q-e8-5 invalid: ' + bad5.join('; '));

  // 2. q-e8-8 — minted directly (rq.add defaults status to 'queued'; we need 'dropped')
  if (q.some(e => e.id === PIT3.id)) throw new Error(`${PIT3.id} already exists`);
  const bad8 = rq.validate(PIT3);
  if (bad8.length) throw new Error('q-e8-8 invalid: ' + bad8.join('; '));
  q.push(PIT3);

  rq.save(FAMILY, q);

  // 3. the back-link
  fixSpawned();

  const open = q.filter(e => e.status === 'queued' || e.status === 'active');
  console.log(`[close] queue=${q.length}  open=${open.length}  (q-e8-5 -> dropped, ${PIT3.id} minted dropped, q-e8-3.spawned -> ${PIT3.id})`);
  return { queue: q.length, open: open.length };
}

module.exports = { main, PIT3 };
