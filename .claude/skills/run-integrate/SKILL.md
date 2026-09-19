---
name: run-integrate
description: Run a TYPE-level integration round — take the strategy families that share a type (same universe, same turnover band) and try to build one strategy that beats the best of them. Enforces the anti-diversification guard, selects on TRAIN only, and records the result. Use when asked to integrate/merge/combine strategy families, work at the type level, or improve across families rather than within one.
---

# Run a type-level integration round

The layer above `/run-enhance`. Enhance improves **one lineage**; this asks whether the families
in one **type** (`wiki/types/<universe>-<horizon>.md`) can be combined into something better than
any of them alone.

**Authority**: `docs/consolidation-plan.md` §4 (this round), `harness/harness.md` (frozen bench,
read-only), `screen/screen.md` §3 R (realizability). This skill is the entry point.

## Read first
1. The target type page — its member families, their `bestObjective`, measured turnover and the
   `intradayDependent` flag.
2. Each member family page §1 (why it works) and §2 (variants already tried).
3. `docs/consolidation-plan.md` §4.1 — **the failure mode**, below.

## The failure mode, and why the guard exists

**Blending raises Sharpe mechanically** whenever member correlation is below one, and the gate
**is** a Sharpe threshold. This repo measured it twice:

- **七星高照** — the blend scored sharpe **3.17** against **2.85 / 1.60** for its two legs, with
  volatility *below both*. It clears the gate at 0.4814 while its small-cap leg alone scores
  **0.5984**. The blend is *worse* than one of its parts and still passes.
- **红利低频** — a two-factor conjunction returned **23.41%** against **11.75%** for the sum of
  its legs, at lower risk than either.

So an unguarded round manufactures gate passes and adds nothing. Expect that, and do not
celebrate it.

## The guard — run it, do not argue with it

```bash
node utils/type-integrate-check.js <candidate.json>
```

1. **Beat the best MEMBER, not the gate.** Clearing sharpe 2.5 is necessary and meaningless.
2. **Declare the diversification share.** Sharpe up while return is not up is the diversification
   signature; the checker flags it and the verdict becomes `keep-with-caveat`. ⚠ The ledger has
   no return series, so the checker detects the *signature*, not the attribution — a flagged
   candidate needs your own decomposition before anyone calls it an edge.
3. **Equal weight first.** Optimised weights must beat equal weight by more than 1pp — re-running
   the same strategy moves annual return by ~0.15pp, so smaller gaps are noise.
4. **Worst realizability wins.** Capacity is additive, edge is not. One untradeable leg makes the
   blend untradeable.

## Window discipline — the part that is easy to get wrong

**Selection happens on TRAIN only.** Enhance already finalises on VAL; if this round then picked
among VAL-confirmed variants it would turn VAL into a second training set and leave only the
single-shot OOS reserve. So:

- iterate and choose on `--window train`;
- VAL is **one confirmation** for a finalised candidate, never an input to the choice;
- OOS is not part of this round at all (`docs/consolidation-plan.md` §5.3).

## Steps

1. Pick the type. `node utils/consumption-report.js --next` names one with ≥2 families and no
   integrate event. A single-family type has nothing to integrate.
2. Collect each member's baseline from the type page and `harness/normalize-train.tsv`. Do not
   re-measure what is already in the ledger — the 60 backtest-min/day are shared with the
   normalize queue and `/run-enhance`.
3. Write the candidate as one strategy file under `enhance/candidates/<expId>.py`, using the
   frozen cost block. Start **equal-weight**.
4. Run it: `node utils/strategy-post-backtest.js enhance/candidates/<expId>.py "<expId>" --window train --usage-limit 55`
   (foreground, plain form, per `/run-enhance`).
5. Build `candidate.json` and run the guard. `reject` ends it; record why.
6. On `keep` or `keep-with-caveat`: one VAL run, then append a row to the type page's
   整合回合 section and record the event:
   `node -e "require('./utils/consumption').record({key:'<type>',kind:'type',stage:'integrate',runId:'<expId>',outcome:'<verdict>',note:'…'})"`

## Do not
- Treat a gate pass as success — see the failure mode.
- Optimise weights before equal weight has been measured.
- Average realizability across members.
- Touch VAL during selection, or OOS at all.
