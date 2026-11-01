// Round-1 close-out for 突破ATR趋势跟踪 (2026-11-01): page summary + §5 row + consumption event.
// Idempotent: skips each step already applied.
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..', '..');
const f = path.join(ROOT, 'wiki/families/突破ATR趋势跟踪.md');
let s = fs.readFileSync(f, 'utf8');

if (!s.includes('**第 1 轮（2026-11-01')) {
  const old = s.match(/^⚠⚠ \*\*注册时本族的全部证据.*$/m)[0];
  s = s.replace(old, old.replace('⚠⚠ **注册时', '⚠⚠ （注册时的状态，已被 round 1 取代）**注册时') +
    '\n\n**第 1 轮（2026-11-01，7 次 TRAIN 回测 + 1 次免费归因）结论**：书的 2024 水平是**一次事件上的集中贝塔**——三笔 2024-09-25 宽基入场 = 净 P&L 84.6%。`布林上轨突破` **refuted**（去掉突破、只禁出场后当日再入 → sharpe 1.62 ≥ base 1.54；9 月三本书逐位相同），突破条件唯一测得的作用是**防止出场后当日再入的反复**；`大盘择时作为回撤保护` **refuted**（去掉后 maxDD 反降 3.34pp），其测得作用是**把现金留给 9/25 满额入场**（`proposed`）。仓位摊匀（cap 1/3）被拒：更集中于 9 月、sharpe 降。可成交性 **R=3**（6 只大 ETF，地板惰性）。VAL **主动放弃**（`valDeclined: 9`，理由见 frontmatter），exit gate 显示 `none` 是终态。');
}
const row10 = '| 2026-10-31 | 注册。来源 `screen/qita/verdicts.json`，screener confidence high。零实验。 |';
if (!s.includes('| 2026-11-01 | round 1')) {
  s = s.replace(row10, row10 + '\n| 2026-11-01 | round 1：§1 填写，edge 起草 → 2 条 refuted / 1 条 proposed，R=3，VAL declined（epoch 9）。 |');
}
fs.writeFileSync(f, s);

const c = require(path.join(ROOT, 'utils/consumption'));
const runId = 'run-family-2026-11-01-r1';
const done = c.events().some(e => e.key === '突破ATR趋势跟踪' && e.stage === 'research' && e.runId === runId);
if (!done) {
  const m = c.memberState('突破ATR趋势跟踪');
  c.record({
    key: '突破ATR趋势跟踪', kind: 'family', stage: 'research', runId, outcome: 'val-declined',
    note: 'round 1: 7 TRAIN runs (bb-ablate 1.21 unresolved; regime-ablate 1.25 maxDD 5.04 refutes DD claim; liq-1/liq-2 inert R=3; cap-third 1.28 rejected; reentry-cooldown 1.62 refutes breakout edge) + free attribution (9/25 entries = 84.6% of net). realizability 3. VAL declined (valDeclined 9): level is one 9·24 event, author posted 2026-09-12. Queue drained.',
    members: m.members, memberHash: m.hash || m.memberHash,
  });
}
console.log('close-round1 done');
