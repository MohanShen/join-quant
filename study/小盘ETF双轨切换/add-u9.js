// recorder 2026-11-01: append u-9 (the 动量 test's unrun arm) to the queue. Idempotent.
const rq = require('../../utils/research-queue');
const F = '小盘ETF双轨切换';
const e = rq.load(F);
if (!e.find(x => x.id === 'u-9')) {
  e.push({
    id: 'u-9', kind: 'understand',
    title: 'always-摸狗: DDDD entry condition forced False (line 188 condition -> False), 偷鸡 never entered',
    hypothesis: 'The 4-ETF momentum rotation alone, run all of 2024, clears sharpe >= 1 — the remaining arm of the 动量 edge test.',
    why: "The 动量 edge's declared test has TWO arms: (a) 摸狗-period return significantly > 0 vs cash — run as u-8 (+15.77 vs 0.00 strict, Δobjective 0.1888, PASS); (b) the always-摸狗 book (偷鸡 off) has sharpe >= 1 — NOT run. Recorder held 动量 at proposed on that basis. COMPLETES the test (→ measured) if sharpe >= 1.0; REFUTES the standalone-edge reading if sharpe < 1.0 (摸狗 then contributes inside the book but is not an edge on its own). Also the clean standalone number the integration layer needs to compare this leg with [[ETF动量]] / [[七星高照]]. Cost ~3 backtest-min.",
    design: 'Base 0d1bbe83, epoch-9 pins. Replace the DDDD entry condition `if variance < g.regime_variance_threshold and mean > 0:` with `if False:`. Everything else verbatim (摸狗 ranking, 4-ETF pool; 14:00 check_limit_up is inert with no stocks). Verify in log: 0 偷鸡 entries, an ETF held every day. Report sharpe, objective, per-ETF holding spans.',
    from: ['u-8 (摸狗→cash, obj 0.5378, Δ 0.1888)', 'u-4 (inversion, obj 0.5590)', 'edge 动量 .test arm: 常摸狗书 sharpe ≥1'],
    edgeRef: '动量', rank: 1, status: 'queued',
    note: 'recorder 2026-11-01 (after u-8): spawned to finish the declared 动量 test; promotion to measured waits on it.',
  });
  rq.save(F, e);
}
console.log(rq.load(F).map(x => x.id + ':' + x.status).join(' '));
