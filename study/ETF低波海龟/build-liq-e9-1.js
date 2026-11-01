// liq-e9-1 builder: buy-side feasibility floor on the BASE 4a8bcfd5 (ETF低波海龟).
// Usage: node -e "require('./study/ETF低波海龟/build-liq-e9-1.js')"
//
// Floor = capital / holdings (1) / order_volume_ratio, READ FROM THE HARNESS (expect 2e7 CNY/day).
// A name whose 20-day average traded money (end_date = previous_date) is below the floor is removed
// from the BUY candidate set before ranking. Held names are exempt (no force-sell; liq-1 convention).
// The risk-vol MEDIAN (the safe-leg regime signal) is computed on the untouched full pool — it is a
// signal, not a buy. Two call sites: the ranking candidate set, and the 换回 (safe -> risk) re-entry.
// Missing data => nothing removed, logged status=bypass-nodata. strategies/ never modified.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');
const ROOT = path.join(__dirname, '../..');
const PARENT = path.join(ROOT, 'strategies/2026-10-17_量化分享_ETF低波海龟法则与复利增强的验证-4a8bcfd5.py');
const CURVE = path.join(ROOT, 'data/series/2026-10-17_量化分享_ETF低波海龟法则与复利增强的验证-4a8bcfd5__train__e9.json');
const EXPECT_SHA = 'ae068f0d9dac9ce578220389f17b09ec0975a8d23bad84c21aa5b919fce85b56';
const EXPECT_CUM = 22.51;

const raw = fs.readFileSync(PARENT);
const sha = crypto.createHash('sha256').update(raw).digest('hex');
if (sha !== EXPECT_SHA) throw new Error('parent sha256 mismatch ' + sha);
const pc = JSON.parse(fs.readFileSync(CURVE, 'utf8'));
if (pc.epoch !== 9 || pc.window !== 'train') throw new Error('stored base curve is not e9 TRAIN');
if (Math.abs(pc.cum[pc.cum.length - 1] - EXPECT_CUM) > 0.005) throw new Error('base curve end != 22.51');
console.log('parent sha256 OK; base curve', pc.points, 'pts, end', pc.cum.at(-1));

const hc = harness.config();
const CAPITAL = hc.costs.capital, OVR = hc.costs.orderVolumeRatio, SLOTS = 1;
const FLOOR = CAPITAL / SLOTS / OVR;
console.log(`harness epoch ${hc.epoch}: capital ${CAPITAL} ovr ${OVR} => floor ${FLOOR}`);
if (FLOOR !== 2e7) throw new Error('floor expected 2e7, got ' + FLOOR);

const src = py2to3(raw.toString('utf8'));
function edit(s, from, to, tag) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`[${tag}] expected exactly 1 match, got ${n}`);
  return s.replace(from, to);
}

const INS_KNOBS = [
  `    g.liq_ovr = ${OVR}  # liq-e9-1: harness orderVolumeRatio`,
  `    g.liq_capital = ${CAPITAL}.0  # liq-e9-1: harness capital`,
  `    g.liq_slots = ${SLOTS}  # liq-e9-1: single holding`,
  '    g.liq_days = 20  # liq-e9-1: 20-day average money',
  '',
].join('\n');
const FROM_KNOBS = "    run_daily(rebalance_trade, '09:35')\n";

const HELPER = `

# ==================== liq-e9-1: buy-side feasibility floor (read + log only) ====================
def liq_screen(context, cands, site):
    """Return a dict of cands minus non-held names whose 20d avg money < capital/slots/ovr."""
    codes = list(cands.keys())
    floor = float(g.liq_capital) / float(g.liq_slots) / float(g.liq_ovr)
    floor_live = float(context.portfolio.total_value) / float(g.liq_slots) / float(g.liq_ovr)
    held = set([c for c in context.portfolio.positions
                if context.portfolio.positions[c].total_amount > 0])
    try:
        df = get_price(codes, end_date=context.previous_date, count=g.liq_days,
                       frequency='daily', fields=['money'], panel=False)
        money = df.groupby('code')['money'].mean().to_dict()
    except Exception:
        money = None
    if not money:
        log.info("LIQFLOOR site=%s date=%s floor=%.0f in=%d out=%d removed=- status=bypass-nodata"
                 % (site, context.previous_date, floor, len(codes), len(codes)))
        return cands
    kept = {}
    removed = []
    live_removed = []
    exempt = []
    for c in codes:
        m = float(money.get(c, 0.0) or 0.0)
        if m < floor_live and c not in held:
            live_removed.append(c)
        if c in held:
            exempt.append(c)
            kept[c] = cands[c]
        elif m >= floor:
            kept[c] = cands[c]
        else:
            removed.append(c)
    log.info("LIQFLOOR site=%s date=%s floor=%.0f floor_live=%.0f in=%d out=%d removed=%s live_removed=%s exempt=%s money=%s status=ok"
             % (site, context.previous_date, floor, floor_live, len(codes), len(kept),
                ';'.join(removed) or '-', ';'.join(live_removed) or '-', ';'.join(exempt) or '-',
                ';'.join(['%s:%.0f' % (c, float(money.get(c, 0.0) or 0.0)) for c in codes])))
    return kept
`;

let out = src;
out = edit(out, FROM_KNOBS, INS_KNOBS + FROM_KNOBS, 'knobs');
const FROM_RANK = '    vol = get_vol_rank(context, candidates)\n';
const INS_RANK = "    candidates = liq_screen(context, candidates, 'rank')  # liq-e9-1\n";
out = edit(out, FROM_RANK, INS_RANK + FROM_RANK, 'rank-site');
const FROM_BACK = '            risk_vol_only = get_vol_rank(context, g.all_risk_etfs)\n';
const TO_BACK = "            risk_vol_only = get_vol_rank(context, liq_screen(context, g.all_risk_etfs, 'back'))  # liq-e9-1\n";
out = edit(out, FROM_BACK, TO_BACK, 'back-site');
out = out + HELPER;

// assertions: removing the insertions + reverting the one modified line restores the parent
let restored = out.replace(HELPER, '').replace(INS_KNOBS, '').replace(INS_RANK, '').replace(TO_BACK, FROM_BACK);
if (restored !== src) throw new Error('reverting the edits does not restore the parent byte-for-byte');
if ((out.match(/liq_screen\(context, [\w.]+, '/g) || []).length !== 2) throw new Error('expected exactly 2 call sites');
if (/order\w*\(/.test(HELPER)) throw new Error('helper places orders');
if (/\bg\.\w+\s*=[^=]/.test(HELPER)) throw new Error('helper assigns g.*');
if (/\b(2e7|20000000)\b/.test(INS_KNOBS + HELPER)) throw new Error('hard-coded floor value in inserted code');
// median line untouched: first get_vol_rank call still on the full pool
if (!out.includes('    risk_vol = get_vol_rank(context, g.all_risk_etfs)\n')) throw new Error('median line moved');

const HDR = `# liq-e9-1: ETF低波海龟 base 4a8bcfd5 (sha256 ${sha}) + buy-side feasibility floor ` +
  `capital ${CAPITAL} / ${SLOTS} / ovr ${OVR} = ${FLOOR.toExponential(0)} CNY/day on 20d avg money; held exempt. ` +
  'Built by study/ETF低波海龟/build-liq-e9-1.js\n';
const variant = HDR + out + OVERRIDE;
const OUT = path.join(__dirname, 'variants', 'liq-e9-1.py');
fs.writeFileSync(OUT, variant);
console.log('wrote', OUT, 'sha256', crypto.createHash('sha256').update(variant).digest('hex'));
