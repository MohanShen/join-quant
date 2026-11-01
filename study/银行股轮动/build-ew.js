// u-e9-ew: edge.test 大行高股息板块贝塔. Base 2a323522 + py2to3 + ONE asserted edit + OVERRIDE.
// Edit: rebalance() body -> equal-weight 20% x 5 of g.stocks (no score / Bollinger / MA250 / -12% stop).
// initialize (pool, run_weekly(rebalance, weekday=5, time='close'), author's costs -> overridden) verbatim.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const SRC = 'strategies/2026-10-26_自己搭建的一个10年230_收益率的银行股策略-2a323522.py';
const raw = py2to3(fs.readFileSync(path.join(ROOT, SRC), 'utf8'));

const marker = '\ndef rebalance(context):\n';
const i = raw.indexOf(marker);
if (i < 0 || raw.indexOf(marker, i + 1) >= 0) throw new Error('rebalance() marker not found exactly once');
const tail = raw.slice(i);
if (!/order_target_value\(stock, target_value\)\s*$/.test(tail)) throw new Error('rebalance() is not the last def — refusing');
if (/\ndef /.test(tail.slice(marker.length))) throw new Error('another def follows rebalance() — refusing');

const NEW = `
def rebalance(context):
    # u-e9-ew: equal-weight 20% x 5, weekly Friday close. No score/Bollinger/MA250/stop.
    tv = context.portfolio.total_value
    for s in g.stocks:
        order_target_value(s, tv * 0.20)
`;
const body = raw.slice(0, i) + NEW;
if ((body.match(/order_target_value/g) || []).length !== 1) throw new Error('unexpected order call count');
if (!body.includes("run_weekly(rebalance, weekday=5, time='close')")) throw new Error('schedule changed');
if (raw.slice(0, i) !== body.slice(0, i)) throw new Error('prefix drift');

const outDir = path.join(__dirname, 'variants');
fs.mkdirSync(outDir, { recursive: true });
const out = path.join(outDir, 'u-e9-ew.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out));
