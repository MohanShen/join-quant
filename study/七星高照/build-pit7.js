// Builds the pit7 variant: the SAME point-in-time pool as variants/pit-pool.py, truncated to the
// N most liquid names, so that "which 7 names" is separated from "how many names".
// pit-pool ranked 1-of-154..302 and scored -0.6643; the hand-picked list ranks 1-of-7 and scores
// 0.1252. Those differ in TWO ways at once. This file holds the pool construction fixed and
// changes only its SIZE.
const fs = require('fs');
const path = require('path');

const dir = __dirname;
const SRC = path.join(dir, 'variants/pit-pool.py');
const src = fs.readFileSync(SRC, 'utf8');

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${from}`);
  return s.replace(from, to);
}

// one concept, two lines: declare N, then apply it where the pool is assembled
let out = edit(src,
  "POOL_TYPES       = ['etf', 'lof']\n",
  "POOL_TYPES       = ['etf', 'lof']\n" +
  "POOL_TOP_N       = 7         # pit7: keep only the N most liquid eligible names, so the pool\n" +
  "                             # has the SAME SIZE as the hand-picked list it is replacing\n");

out = edit(out,
  "    held = [s for s in context.portfolio.positions\n",
  "    pool = sorted(pool, key=lambda c: -med.get(c, 0.0))[:POOL_TOP_N]   # pit7: size-matched\n" +
  "    held = [s for s in context.portfolio.positions\n");

// the POOLSIZE log line already prints len(g.etf_pool); keep it, it is how we verify N
fs.writeFileSync(path.join(dir, 'variants/pit7-pool.py'), out);
console.log('built variants/pit7-pool.py from pit-pool.py (POOL_TOP_N=7)');
