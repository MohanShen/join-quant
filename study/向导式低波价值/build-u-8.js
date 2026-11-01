// Builds study/向导式低波价值/variants/u-8a.py (Leg A, low-vol 6) and u-8b.py (Leg B, whole PE pool).
// queue.json u-8 — edge 低波动 test on a REBALANCE harness (NOT the pool-EW harness: that one is a
// day-1 buy-and-hold by construction and can give only one cross-section).
//
// Both legs = baseline.py (py2to3 + live OVERRIDE) + the SAME rebalance harness, and differ in
// exactly ONE constant: _RB_TOPN = 6 (Leg A) vs None (Leg B). Asserted below.
//
//   R1  entry gate L196 (yuan ATR_judge_xiaoyu 0.15) -> _rb_select(): rel15 for every candidate,
//       computed EXACTLY as u-5 / the u-2 probe (attribute_history 60 x 1d to previous_date,
//       talib.ATR(hi[-15:], lo[-15:], cl[-15:], 14)[-1] / cl[-1]). Leg A keeps the _RB_TOPN lowest
//       (rank, not threshold, so breadth is fixed every date); Leg B keeps the whole pool.
//       A name whose rel15 cannot be computed is dropped from Leg A (cannot be ranked) and KEPT in
//       Leg B (it is in the pool); logged as RBERR.
//   R2  trade()'s separate sell()/buy() blocks -> one _rb_rebalance() on the buy cadence (same
//       10-day counter as check_stocks, both registered at 'open', check_stocks first). This turns
//       the yuan ATR>0.35 exit OFF (sell() is never called — same effect as pool-EW H1), and gives
//       the rebalance its own sell logic: sell every holding not in the target, trim overweights,
//       then buy underweights to EW target = total_value * 0.998 / n.
//       No-trade band: a held target name is left alone when |target - value| < 5% of target
//       (avoids min-commission dust trades on ~30-name Leg B; identical in both legs).
//   R3  STAR (688/689): JQ refuses a bare market order (u-3: 「科创板市价单需要指定保护限价」).
//       Per the queue spec they get a PROTECTED market order in BOTH legs:
//       MarketOrderStyle(high_limit) on a buy, MarketOrderStyle(low_limit) on a sell.
//       Main-board names keep the plain MarketOrderStyle(), as in every earlier variant.
//   LOG RBREL (per candidate per check date), RBSEL (pre/post counts + codes), RBORD (every order:
//       side, value, filled, price), REBAL (date n_pool n_tgt codes sectors turnover held cash tv).
//       Sector = get_industry(sw_l1) at the rebalance date.
const fs = require('fs');
const path = require('path');
const { OVERRIDE } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');

function edit(src, from, to) {
  const n = src.split(from).length - 1;
  if (n !== 1) throw new Error(`anchor matched ${n}x: ${JSON.stringify(from.slice(0, 80))}`);
  return src.replace(from, () => to);
}

// u-9 EXTENSION (queue.json u-9, sector-controlled low-vol test): `--u9` builds variants/u-9a.py /
// u-9b.py = the u-8 legs + ONE asserted edit X1 per leg: after the PE 6-11 / ST / paused / delisted /
// high-limit filters and BEFORE _rb_select, drop every name whose get_industry(sw_l1,
// date=previous_date) is 电气设备I or 房地产I (the industry_name strings the u-8 REBAL sector logging
// emitted; SW L1 codes 801730 / 801180 accepted too). Same exclusion in both legs. Logs RBEXCL
// date n_before n_after codes. Without --u9 the output is byte-identical to u-8.
//   run: node -e "require('./study/向导式低波价值/build-u-8.js')" -- --u9
const U9 = process.argv.includes('--u9');
const EXCL_NAMES = ['电气设备I', '房地产I'];
const EXCL_CODES = ['801730', '801180'];

function build(topn, leg) {
  let src = fs.readFileSync(path.join(__dirname, 'baseline.py'), 'utf8');
  if (!src.includes(OVERRIDE)) throw new Error('baseline.py OVERRIDE != live OVERRIDE; rebuild baseline');

  // R1 — the entry gate
  src = edit(src,
    '        buy_lists = [security for security in buy_lists if ATR_judge_xiaoyu(security, 0.15, 14)]\n',
    '        buy_lists = _rb_select(context, buy_lists)  # u-8 R1 (was: yuan ATR_judge_xiaoyu(security, 0.15, 14) filter)\n');

  // R2 — sell()/buy() -> one rebalance on the buy cadence
  src = edit(src,
    '    # 卖出操作\n' +
    '    if g.sell_trade_days%g.sell_refresh_rate != 0:\n' +
    '        # 计数器加一\n' +
    '        g.sell_trade_days += 1\n' +
    '    else:\n' +
    '        # 卖出股票\n' +
    '        sell(context, buy_lists)\n' +
    '        # 计数器归一\n' +
    '        g.sell_trade_days = 1\n' +
    '\n' +
    '\n' +
    '    # 买入操作\n' +
    '    if g.buy_trade_days%g.buy_refresh_rate != 0:\n' +
    '        # 计数器加一\n' +
    '        g.buy_trade_days += 1\n' +
    '    else:\n' +
    '        # 卖出股票\n' +
    '        buy(context, buy_lists)\n' +
    '        # 计数器归一\n' +
    '        g.buy_trade_days = 1\n',
    '    # u-8 R2: rebalance replaces sell()+buy(); yuan ATR>0.35 exit is never called\n' +
    '    if g.buy_trade_days%g.buy_refresh_rate != 0:  # u-8 R2\n' +
    '        g.buy_trade_days += 1  # u-8 R2\n' +
    '    else:  # u-8 R2\n' +
    '        _rb_rebalance(context, buy_lists)  # u-8 R2\n' +
    '        g.buy_trade_days = 1  # u-8 R2\n');

  const helpers = `
# ===== u-8 REBALANCE HARNESS (study/向导式低波价值/build-u-8.js) =====
_RB_TOPN = ${topn === null ? 'None' : topn}  # u-8 LEG ${leg}: the ONLY difference between u-8a and u-8b
_RB_BAND = 0.05
_RB_BUF = 0.998

def _rb_select(context, buy_lists):
    d = context.current_dt.strftime('%Y-%m-%d')
    scored = []
    unscored = []
    for s in buy_lists:
        try:
            h = attribute_history(s, 60, '1d', ['high', 'low', 'close'])
            hi = np.array(h['high'].values, dtype=float)
            lo = np.array(h['low'].values, dtype=float)
            cl = np.array(h['close'].values, dtype=float)
            a = talib.ATR(hi[-15:], lo[-15:], cl[-15:], 14)[-1]
            r = a / cl[-1]
            if not np.isfinite(r):
                raise ValueError('rel15 not finite')
            scored.append((r, s))
            log.info('RBREL date=%s code=%s close=%.4f atr15=%.5f rel15=%.5f' % (d, s, cl[-1], a, r))
        except Exception as e:
            unscored.append(s)
            log.info('RBERR date=%s code=%s err=%s' % (d, s, e))
    scored.sort()
    if _RB_TOPN is None:
        out = list(buy_lists)
    else:
        out = [s for r, s in scored[:_RB_TOPN]]
    log.info('RBSEL date=%s n_pre=%d n_scored=%d n_tgt=%d codes=%s' % (d, len(buy_lists), len(scored), len(out), ','.join(out)))
    return out

def _rb_style(s, cd, side):
    if s[:3] in ('688', '689'):
        return MarketOrderStyle(cd[s].high_limit if side == 'buy' else cd[s].low_limit)
    return MarketOrderStyle()

def _rb_order(d, s, value, cd, side):
    try:
        o = order_target_value(s, value, _rb_style(s, cd, side))
    except Exception as e:
        log.info('RBORD date=%s code=%s side=%s tgt=%.2f err=%s' % (d, s, side, value, e))
        return 0.0
    if o is None:
        log.info('RBORD date=%s code=%s side=%s tgt=%.2f order=None' % (d, s, side, value))
        return 0.0
    f = o.filled or 0
    p = o.price or 0.0
    log.info('RBORD date=%s code=%s side=%s tgt=%.2f amount=%s filled=%s price=%.4f' % (d, s, side, value, o.amount, f, p))
    return f * p

def _rb_rebalance(context, target):
    d = context.current_dt.strftime('%Y-%m-%d')
    cd = get_current_data()
    tv0 = context.portfolio.total_value
    traded = 0.0
    n_ord = 0
    # 1) sell every holding that left the target
    for s in list(context.portfolio.positions.keys()):
        if s not in target:
            traded += _rb_order(d, s, 0, cd, 'sell')
            n_ord += 1
    n = len(target)
    if n > 0:
        tgt = context.portfolio.total_value * _RB_BUF / n
        pos = context.portfolio.positions
        # 2) trim overweights first (frees cash), 3) then buy underweights
        for s in target:
            v = pos[s].value if s in pos else 0.0
            if v > tgt and (v - tgt) >= _RB_BAND * tgt:
                traded += _rb_order(d, s, tgt, cd, 'sell')
                n_ord += 1
        for s in target:
            v = pos[s].value if s in pos else 0.0
            if v < tgt and (tgt - v) >= _RB_BAND * tgt:
                traded += _rb_order(d, s, tgt, cd, 'buy')
                n_ord += 1
    try:
        ind = get_industry(target, date=context.previous_date)
        sec = {}
        for s in target:
            nm = ind.get(s, {}).get('sw_l1', {}).get('industry_name', '?')
            sec[nm] = sec.get(nm, 0) + 1
        sectors = ';'.join('%s:%d' % (k, v) for k, v in sorted(sec.items(), key=lambda x: -x[1]))
    except Exception as e:
        sectors = 'err:%s' % e
    held = sorted(context.portfolio.positions.keys())
    log.info('REBAL date=%s n_tgt=%d codes=%s sectors=%s turnover=%.4f n_ord=%d n_held=%d held=%s cash=%.2f tv=%.2f' % (
        d, n, ','.join(target), sectors, traded / tv0 if tv0 else 0.0, n_ord, len(held), ','.join(held),
        context.portfolio.available_cash, context.portfolio.total_value))
`;
  src = edit(src, OVERRIDE, helpers + OVERRIDE);

  if (U9) {
    // X1 — the sector exclusion, immediately before the selection (same line in both legs)
    src = edit(src,
      '        buy_lists = _rb_select(context, buy_lists)  # u-8 R1',
      '        buy_lists = _rb_excl(context, buy_lists)  # u-9 X1: drop 电气设备I + 房地产I before selection\n' +
      '        buy_lists = _rb_select(context, buy_lists)  # u-8 R1');
    const exclHelper = `
# ===== u-9 SECTOR EXCLUSION (study/向导式低波价值/build-u-8.js --u9) =====
_RB_EXCL_NAMES = (${EXCL_NAMES.map(n => `'${n}'`).join(', ')})
_RB_EXCL_CODES = (${EXCL_CODES.map(n => `'${n}'`).join(', ')})

def _rb_excl(context, buy_lists):
    d = context.current_dt.strftime('%Y-%m-%d')
    try:
        ind = get_industry(list(buy_lists), date=context.previous_date)
    except Exception as e:
        log.info('RBEXCL date=%s err=%s n_before=%d n_after=%d codes=' % (d, e, len(buy_lists), len(buy_lists)))
        return list(buy_lists)
    out = []
    dropped = []
    for s in buy_lists:
        l1 = ind.get(s, {}).get('sw_l1', {})
        if l1.get('industry_name', '') in _RB_EXCL_NAMES or str(l1.get('industry_code', '')) in _RB_EXCL_CODES:
            dropped.append('%s:%s' % (s, l1.get('industry_name', '?')))
        else:
            out.append(s)
    log.info('RBEXCL date=%s n_before=%d n_after=%d codes=%s' % (d, len(buy_lists), len(out), ','.join(dropped)))
    return out
`;
    src = edit(src, OVERRIDE, exclHelper + OVERRIDE);
    if ((src.match(/= _rb_excl\(context, buy_lists\)/g) || []).length !== 1) throw new Error('X1 call not exactly once');
  }

  // header (comment only)
  src = edit(src, src.split('\n')[0] + '\n',
    `# study variant ${U9 ? 'u-9' : 'u-8'}${leg.toLowerCase()} — family: 向导式低波价值 — REBALANCE harness, LEG ${leg}: ` +
    (topn === null ? 'whole HS300 ∩ PE 6-11 pool EW (control)' : `the ${topn} lowest rel15 ATR/close of HS300 ∩ PE 6-11, EW`) +
    (U9 ? ' (电气设备I + 房地产I excluded before selection)' : '') +
    ', rebalanced on every 10-day check date\n' +
    '# built from study/向导式低波价值/baseline.py by study/向导式低波价值/build-u-8.js' + (U9 ? ' --u9' : '') +
    '; edits marked # u-8 R1/R2' + (U9 ? ' + # u-9 X1' : '') + ', helpers above the OVERRIDE\n');

  // guards (code side only)
  const code = src.split('\n').map(l => l.split('#')[0]).join('\n');
  if (code.includes('ATR_judge_xiaoyu(security, 0.15')) throw new Error('yuan entry gate still live');
  if (/^\s+sell\(context, buy_lists\)/m.test(code)) throw new Error('yuan exit sell() still called');
  if (/^\s+buy\(context, buy_lists\)/m.test(code)) throw new Error('wizard buy() still called');
  for (const keep of ['valuation.pe_ratio, (6,11)', 'high_limit_filter(context, buy_lists)', 'paused_filter(context, buy_lists)',
    'st_filter(context, buy_lists)', 'g.security_universe_index = ["000300.XSHG"]', 'import talib', 'import numpy as np']) {
    if (!src.includes(keep)) throw new Error('lost: ' + keep);
  }
  if (!src.endsWith(OVERRIDE) && !src.trimEnd().endsWith(OVERRIDE.trimEnd())) throw new Error('OVERRIDE is not the tail');
  return src;
}

const a = build(6, 'A');
const b = build(null, 'B');
// the legs differ ONLY in the header and the _RB_TOPN line
const al = a.split('\n'), bl = b.split('\n');
if (al.length !== bl.length) throw new Error('legs differ in length');
const diff = al.map((l, i) => l !== bl[i] ? i : -1).filter(i => i >= 0);
const nonHeader = diff.filter(i => i > 1);
if (nonHeader.length !== 1 || !al[nonHeader[0]].startsWith('_RB_TOPN')) throw new Error('legs differ beyond _RB_TOPN: ' + nonHeader);

for (const [name, s] of (U9 ? [['u-9a.py', a], ['u-9b.py', b]] : [['u-8a.py', a], ['u-8b.py', b]])) {
  const out = path.join(__dirname, 'variants', name);
  fs.writeFileSync(out, s);
  console.log('built', path.relative(ROOT, out), 'lines', s.split('\n').length);
}
console.log('leg diff outside header:', nonHeader.map(i => `L${i + 1}: A=${al[i]} | B=${bl[i]}`).join(' '));
