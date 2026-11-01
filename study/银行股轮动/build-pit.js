// bank-imp-pit: point-in-time pool on the HONEST-DIVIDEND book. Base = variants/u-e9-dypit.py
// (baseline + a_bonus_date <= current_dt.date()), NOT baseline.py.
//   (1) ONE asserted behavioural edit, at the top of rebalance:
//       g.stocks = top 5 of get_industry_stocks('801780', date=previous_date)   [申万一级 银行]
//                  minus ST names (get_extras('is_st', ..., end_date=previous_date, count=1)),
//                  ordered by valuation.market_cap desc via get_fundamentals(date=previous_date).
//       The ICBC MA250 reference ('601398.XSHG') stays hardcoded: it is a timing input, not the pool.
//   (2) observation only:
//       PIT        date=<previous_date> n_ind=<n> n_nonst=<n> pool=<codes> caps=<亿> same=<0|1> order=<0|1>
//       PIT-SHORT  when fewer than 5 non-ST names have a market cap (the shortened pool is used, logged)
//       PIT-ERR    when any industry / ST / market-cap call raises -> rebalance SKIPPED, logged.
//                  No silent fallback to the hardcoded list.
//       PIT-ORPHAN a held position outside the new pool (the base loops iterate g.stocks only,
//                  so such a name would be neither stop-lossed nor sold)
//   RANK lines inherited from dypit cover every scored name: calc_dividend_yield (the only dy fed
//   to the book) carries the a_bonus_date upper bound for any code, incl. new pool members.
// DECISION RULE (queue.json): ADOPT as VAL-candidate pool iff sharpe >= 1.0 AND objective falls by
// < 0.05 vs dypit (0.3363). Quote dypit/pit as a PAIR.
const fs = require('fs');
const path = require('path');
const { OVERRIDE } = require('../../utils/strategy-normalize');
const DIR = path.join(__dirname, 'variants');
const base = fs.readFileSync(path.join(DIR, 'u-e9-dypit.py'), 'utf8');
if (!base.endsWith(OVERRIDE)) throw new Error('dypit does not end with the current OVERRIDE block');
const raw = base.slice(0, base.length - OVERRIDE.length);

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

const HARD = "['601398.XSHG', '601939.XSHG', '601288.XSHG', '601988.XSHG', '600036.XSHG']";
if (!raw.includes('    g.stocks = ' + HARD + '\n')) throw new Error('hardcoded pool not found');

const HELPER = [
  "_PIT_HARD = " + HARD,
  "_PIT_IND = '801780'  # 申万一级 银行",
  "",
  "",
  "def _pit_pool(context):",
  "    # bank-imp-pit: point-in-time top-5 banks by market cap on previous_date, ex-ST.",
  "    # Returns the pool, or None on any error (logged; caller skips the rebalance).",
  "    d = context.previous_date",
  "    ds = str(d)",
  "    try:",
  "        ind = list(get_industry_stocks(_PIT_IND, date=d))",
  "    except Exception as _e:",
  "        log.error('PIT-ERR date=%s step=industry err=%r' % (ds, _e))",
  "        return None",
  "    if not ind:",
  "        log.error('PIT-ERR date=%s step=industry err=empty' % (ds,))",
  "        return None",
  "    try:",
  "        st = get_extras('is_st', ind, end_date=d, count=1)",
  "        nonst = [s for s in ind if s in st.columns and not bool(st[s].iloc[-1])]",
  "    except Exception as _e:",
  "        log.error('PIT-ERR date=%s step=is_st err=%r' % (ds, _e))",
  "        return None",
  "    try:",
  "        df = get_fundamentals(query(valuation.code, valuation.market_cap).filter(valuation.code.in_(nonst)), date=d)",
  "        df = df.dropna(subset=['market_cap']).sort_values('market_cap', ascending=False)",
  "    except Exception as _e:",
  "        log.error('PIT-ERR date=%s step=market_cap err=%r' % (ds, _e))",
  "        return None",
  "    pool = list(df['code'].iloc[:5])",
  "    caps = list(df['market_cap'].iloc[:5])",
  "    if len(pool) < 5:",
  "        log.error('PIT-SHORT date=%s n=%d n_ind=%d n_nonst=%d pool=%s' % (ds, len(pool), len(ind), len(nonst), ','.join(pool) or '-'))",
  "    if len(pool) == 0:",
  "        return None",
  "    log.error('PIT date=%s n_ind=%d n_nonst=%d pool=%s caps=%s same=%d order=%d' % (ds, len(ind), len(nonst), ','.join(pool), ','.join('%.1f' % c for c in caps), int(set(pool) == set(_PIT_HARD)), int(pool == _PIT_HARD)))",
  "    return pool",
  "",
  "",
  "",
].join('\n');

const G = "def get_ma250(stock, context):\n";
let body = edit(raw, G, HELPER + G);

const TOP = "def rebalance(context):\n    # ----- 获取基本面数据（PB）-----\n";
body = edit(body, TOP,
  "def rebalance(context):\n" +
  "    # bank-imp-pit: ONLY behavioural change vs u-e9-dypit -- point-in-time pool\n" +
  "    _pool = _pit_pool(context)\n" +
  "    if _pool is None:\n" +
  "        return\n" +
  "    g.stocks = _pool\n" +
  "    try:  # bank-imp-pit PIT-ORPHAN (observation only)\n" +
  "        for _s, _p in context.portfolio.positions.items():\n" +
  "            if _p.total_amount > 0 and _s not in g.stocks:\n" +
  "                log.error('PIT-ORPHAN date=%s code=%s amount=%d' % (str(context.current_dt.date()), _s, _p.total_amount))\n" +
  "    except Exception as _e:\n" +
  "        log.error('PIT-ORPHAN-ERR %r' % (_e,))\n" +
  "    # ----- 获取基本面数据（PB）-----\n");

// guards
for (const k of ['order_target', 'order_value', 'order(']) {
  if (body.split(k).length !== raw.split(k).length) throw new Error('order calls changed: ' + k);
}
if (!body.includes("run_weekly(rebalance, weekday=5, time='close')")) throw new Error('schedule changed');
if (!body.includes('a_bonus_date <= context.current_dt.date()')) throw new Error('honest-dy edit missing');
if (body.split("get_ma250('601398.XSHG', context)").length !== 2) throw new Error('ICBC MA250 reference changed');
if (/except[^\n]*:\n\s*g\.stocks\s*=/.test(body)) throw new Error('silent fallback to a pool');

fs.writeFileSync(path.join(DIR, 'bank-imp-pit.py'), body + OVERRIDE);
console.log('built study/银行股轮动/variants/bank-imp-pit.py');
