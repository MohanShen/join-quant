/**
 * usage-limit.js — how many used-minutes may pass before we stop STARTING backtests.
 *
 * ## Why this is a resolver and not a number
 *
 * The gate is pre-start only: `USAGE_LIMIT` stops a new run beginning, and a run already going
 * keeps billing to its slow-skip cap. So the spend ceiling is really `limit + cap`, and the limit
 * had been set BELOW the free tier to keep that sum inside it — 170 against a free 180, or 135
 * for strict safety. The cost of that caution is the tail: on 2026-10-06 the day stopped at
 * used=141 with 39 free minutes unspent and 21 strategies pending, because no run may start once
 * used >= limit.
 *
 * The user's rule (2026-10-06): do not stop short to protect the tier — stop only once usage is
 * actually PAST it, and accept the small overshoot the in-flight run carries.
 *
 * So the limit is the free tier itself. ⚠ And it is READ, not written down: JQ reports
 * `data.duration.free` on every statistics call, it has already changed once (60 -> 180 when the
 * account went VIP), and a second copy of that number in a plist is exactly the stale-literal
 * pattern this repo keeps paying for. `USAGE_LIMIT=free` means "whatever JQ says the tier is".
 *
 * A plain number still works and still means what it did, so `--usage-limit 55` is unchanged.
 *
 *   resolve('free', 180) -> 180      resolve('free', null) -> 180 (fallback)
 *   resolve('135', 180)  -> 135      resolve('', 180)      -> 55  (default)
 */

const FREE_TIER_FALLBACK = 180;   // only when JQ does not report `free`
const DEFAULT_LIMIT = 55;         // the non-VIP tier; unchanged for a bare run

const isFreeSpec = spec => /^(free|tier|auto)$/i.test(String(spec == null ? '' : spec).trim());

/**
 * @param {string|number} spec        JQ_USAGE_LIMIT / --usage-limit, or 'free'
 * @param {number|null}   freeFromApi data.duration.free, when the caller has it
 */
function resolve(spec, freeFromApi) {
  if (isFreeSpec(spec)) {
    return Number.isFinite(freeFromApi) && freeFromApi > 0 ? freeFromApi : FREE_TIER_FALLBACK;
  }
  const n = parseInt(spec, 10);
  return Number.isFinite(n) && n > 0 ? n : DEFAULT_LIMIT;
}

/** For logs: say which it was, so a surprising stop is explainable. */
function describe(spec, freeFromApi) {
  const v = resolve(spec, freeFromApi);
  return isFreeSpec(spec)
    ? `${v}min (the free tier${Number.isFinite(freeFromApi) && freeFromApi > 0 ? ' as JQ reports it' : ', fallback'})`
    : `${v}min`;
}

module.exports = { resolve, describe, isFreeSpec, FREE_TIER_FALLBACK, DEFAULT_LIMIT };
