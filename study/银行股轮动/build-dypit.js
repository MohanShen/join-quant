// u-e9-dypit: honest-dividend baseline. Base 2a323522 + py2to3 + OVERRIDE (== baseline.py) plus:
//   (1) ONE asserted logic edit in calc_dividend_yield: the filter gains
//       `finance.STK_XR_XD.a_bonus_date <= context.current_dt.date()` beside the verbatim lower bound.
//   (2) observation only (try/except -> log.error on any exception):
//       RANK   date code pb dy_h dy_l s_h s_l   for each honestly-scored name
//       DYZERO date code pb dy_l s_l            when honest dy <= 0 (name dropped at L110)
//       HOLD   date n_elig elig target           before the 调仓 block; target=KEEP on the L154 path,
//                                                target=NOSCORES on the L127 path
//   dy_l comes from a SECOND query without the upper bound (_dypit_leaky_dy), never fed to the book.
// CONTROL TWIN variants/u-e9-dypit-ctl.py: the base with ONLY the identical HOLD lines.
// Must reproduce 0.3371 / 2.37 / 45.54 / 11.83 bit-identically.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const SRC = 'strategies/2026-10-26_自己搭建的一个10年230_收益率的银行股策略-2a323522.py';
const raw = py2to3(fs.readFileSync(path.join(ROOT, SRC), 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

// ---- HOLD lines (shared by both files, observation only) ----
function addHold(s) {
  const K = "        else:\n            # 有持仓但无新标的，保留持仓不调仓\n            return\n";
  s = edit(s, K,
    "        else:\n            # 有持仓但无新标的，保留持仓不调仓\n" +
    "            try:  # u-e9-dypit HOLD (observation only)\n" +
    "                log.error('HOLD date=%s n_elig=0 elig=- target=KEEP' % (str(context.current_dt.date()),))\n" +
    "            except Exception as _e:\n" +
    "                log.error('HOLD-ERR %r' % (_e,))\n" +
    "            return\n");
  const N = "    if not scores:\n        return\n";
  s = edit(s, N,
    "    if not scores:\n" +
    "        try:  # u-e9-dypit HOLD (observation only)\n" +
    "            log.error('HOLD date=%s n_elig=0 elig=- target=NOSCORES' % (str(context.current_dt.date()),))\n" +
    "        except Exception as _e:\n" +
    "            log.error('HOLD-ERR %r' % (_e,))\n" +
    "        return\n");
  const T = "    # ----- 调仓 -----\n";
  s = edit(s, T,
    "    try:  # u-e9-dypit HOLD (observation only)\n" +
    "        log.error('HOLD date=%s n_elig=%d elig=%s target=%s' % (str(context.current_dt.date()), len(eligible_stocks), ','.join(eligible_stocks) or '-', ','.join(target_holdings) or '-'))\n" +
    "    except Exception as _e:\n" +
    "        log.error('HOLD-ERR %r' % (_e,))\n" + T);
  return s;
}

const ctl = addHold(raw);

// ---- dypit ----
// (1) the one logic edit
const F = "        finance.STK_XR_XD.a_bonus_date >= start_date\n    )\n";
let body = edit(raw, F,
  "        finance.STK_XR_XD.a_bonus_date >= start_date,\n" +
  "        finance.STK_XR_XD.a_bonus_date <= context.current_dt.date()  # u-e9-dypit: honest TTM\n    )\n");

// (2a) leaky helper = the base function verbatim, renamed; observation only
const LEAKY = [
  "def _dypit_leaky_dy(stock, context):",
  "    # u-e9-dypit: observation only. The BASE (leaky) dividend yield, no upper bound. Never fed to the book.",
  "    start_date = context.current_dt - datetime.timedelta(days=365)",
  "    q = query(",
  "        finance.STK_XR_XD.code,",
  "        finance.STK_XR_XD.bonus_ratio_rmb",
  "    ).filter(",
  "        finance.STK_XR_XD.code == stock,",
  "        finance.STK_XR_XD.a_bonus_date >= start_date",
  "    )",
  "    df = finance.run_query(q)",
  "    if df.empty:",
  "        return 0.0",
  "    total_div = df['bonus_ratio_rmb'].sum() / 10.0",
  "    if total_div <= 0:",
  "        return 0.0",
  "    df_price = get_price(stock, end_date=context.current_dt, frequency='daily',",
  "                         fields=['close'], count=1, skip_paused=True, fq=None)",
  "    if len(df_price) == 0:",
  "        return 0.0",
  "    price = df_price['close'].iloc[-1]",
  "    if price <= 0:",
  "        return 0.0",
  "    return total_div / price",
  "",
  "",
  "",
].join('\n');
const G = "def get_ma250(stock, context):\n";
body = edit(body, G, LEAKY + G);

// (2b) DYZERO before the L110 continue
const D = "        dy = calc_dividend_yield(code, context)\n        if dy <= 0:\n            continue\n";
body = edit(body, D,
  "        dy = calc_dividend_yield(code, context)\n" +
  "        try:  # u-e9-dypit (observation only)\n" +
  "            _dy_l = _dypit_leaky_dy(code, context)\n" +
  "        except Exception as _e:\n" +
  "            _dy_l = None\n" +
  "            log.error('RANK-ERR date=%s code=%s err=%r' % (str(context.current_dt.date()), code, _e))\n" +
  "        if dy <= 0:\n" +
  "            try:  # u-e9-dypit DYZERO (observation only)\n" +
  "                _m = 0\n" +
  "                if code in price_data and len(price_data[code]) >= 20:\n" +
  "                    _m = max(0, ((price_data[code].iloc[-1] - price_data[code].iloc[-20]) / price_data[code].iloc[-20] + 0.05) * 10)\n" +
  "                _sl = (0.30 * (1 / pb) + 0.30 * _dy_l * 100 + 0.40 * _m) if (_dy_l is not None and _dy_l > 0) else -1\n" +
  "                log.error('DYZERO date=%s code=%s pb=%.6f dy_h=%.8f dy_l=%s s_l=%.8f' % (str(context.current_dt.date()), code, pb, dy, ('%.8f' % _dy_l) if _dy_l is not None else 'None', _sl))\n" +
  "            except Exception as _e:\n" +
  "                log.error('DYZERO-ERR date=%s code=%s err=%r' % (str(context.current_dt.date()), code, _e))\n" +
  "            continue\n");

// (2c) RANK after the score line
const S = "        scores[code] = 0.30 * pb_score + 0.30 * dy_score + 0.40 * mom_score\n";
body = edit(body, S, S +
  "        try:  # u-e9-dypit RANK (observation only)\n" +
  "            _sl = (0.30 * pb_score + 0.30 * _dy_l * 100 + 0.40 * mom_score) if (_dy_l is not None and _dy_l > 0) else -1\n" +
  "            log.error('RANK date=%s code=%s pb=%.6f dy_h=%.8f dy_l=%s s_h=%.8f s_l=%.8f' % (str(context.current_dt.date()), code, pb, dy, ('%.8f' % _dy_l) if _dy_l is not None else 'None', scores[code], _sl))\n" +
  "        except Exception as _e:\n" +
  "            log.error('RANK-ERR date=%s code=%s err=%r' % (str(context.current_dt.date()), code, _e))\n");

body = addHold(body);

for (const s of [ctl, body]) {
  for (const k of ['order_target', 'order_value', 'order(']) {
    if (s.split(k).length !== raw.split(k).length) throw new Error('order calls changed: ' + k);
  }
  if (!s.includes("run_weekly(rebalance, weekday=5, time='close')")) throw new Error('schedule changed');
}
if (!body.includes('a_bonus_date <= context.current_dt.date()')) throw new Error('logic edit missing');
if (ctl.includes('a_bonus_date <=')) throw new Error('control carries the logic edit');
// control is purely additive: removing the HOLD try blocks must give raw back
const stripped = ctl.replace(/ *try:  # u-e9-dypit HOLD \(observation only\)\n.*\n.*\n.*\n/g, '');
if (stripped !== raw) throw new Error('control is not purely additive');

const outDir = path.join(__dirname, 'variants');
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, 'u-e9-dypit-ctl.py'), ctl + OVERRIDE);
fs.writeFileSync(path.join(outDir, 'u-e9-dypit.py'), body + OVERRIDE);
console.log('built study/银行股轮动/variants/u-e9-dypit-ctl.py, study/银行股轮动/variants/u-e9-dypit.py');
