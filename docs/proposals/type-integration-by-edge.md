# Integration by edge composition, on one axis

**Status**: ACCEPTED 2026-10-07 · in progress (see §9)
**Replaces**: the type layer's two-axis coordinate and the blend-first integration round
**Authority it must obey**: `harness/harness.md` (frozen), `docs/consolidation-plan.md` §4,
`.claude/skills/run-integrate/SKILL.md`

---

## 1. What changes

Three things, decided by the user on 2026-10-07:

1. **The type axis collapses to ONE dimension: universe.** The turnover/horizon axis is dropped.
2. **Universe becomes an explicit, LLM-assigned property of a family**, written on the family
   page, not re-derived by regex at build time.
3. **Integration composes EDGES, not capital.** The round stops being "blend these books" and
   becomes "build one strategy whose edge is the conjunction of theirs".

And one acceptance rule: a composed strategy must **beat or equal the best input family**, with
TRAIN and VAL agreeing (§6).

## 2. Why the H axis goes

It measured the wrong quantity and it was sourced from prose.

Measured on our own families: 大小盘轮动 has turnover **0.0373** and holds **59.42 days**
(月度调仓); 打板短线 has **0.3061** and holds **1.51 days**. If turnover were an inverse of
holding period, 0.0373 implies ~13–27 days. It is not a cadence — it is the fraction of book
traded per day, which mixes cadence with breadth and with how much of the book rotates. A 20-name
book swapping one position a month has low turnover and long holds.

It was also read by `statedTurnover()`, a regex scraping `/turnover[^0-9]{0,4}(0\.[0-9]+)/` out of
markdown that a *different* loop writes — with a dead `familyTurnover()` beside it and **no
turnover column in the ledger at all**. 6 of 13 families landed in `H-unknown`.

⚠ Cadence is still worth knowing; it is just not an axis. It survives as the existing
`intradayDependent` realizability flag, and `avg_position_days` (already on several pages) is the
better numeric companion if one is wanted.

⚠ **Cadence is not lexically derivable.** 大小盘轮动's base declares five `run_daily` handlers and
one `run_monthly` — and the monthly one is the rebalance; the daily ones are signal prep, risk
checks and opportunistic top-ups. Any count-based rule calls it daily. Reading which handler
mutates the portfolio, and what gates it, is comprehension work. If cadence is ever needed as a
field, it is an LLM job for the same reason universe is.

## 3. What one axis actually yields

Collapsing the nine two-axis cells gives six universes, four with more than one family:

| universe | families | distinct measured edges | composable pairs |
|---|---|---|---|
| 全A | 4 | 趋势择时 · 均值回归 · 涨停动量延续 | **3** |
| ETF | 3 | 均值回归 · 流动性溢价 | **1** |
| 小盘 | 2 | 规模因子 · 规模 — **the same edge** | **0** |
| 混合 | 2 | 1 measured + 1 `proposed` | 0 |
| 宽基大盘 | 1 | — | 0 |
| 其他 | 1 (ETF动量) | none declared | 0 |

That is **4 real pairs today**, against a `wiki/types/` directory currently holding two stale
single-family pages. 小盘 is the instructive one: `规模因子` and `规模` are one edge spelled two
ways, so the same-edge check in §5 must be semantic, not string equality.

## 4. `universe:` as a family property

**Assigned by an LLM from the base strategy's SOURCE, recorded once, read deterministically.**

The current `universeOf()` scores eight ordered regex rules over the base source with
`MIN_EVIDENCE = 3` and a `HYBRID_RATIO = 0.4` hybrid test. Its premise is right — *prose describes
intent, code describes behaviour* — and that premise carries over unchanged. What it cannot see is
an **implicit** universe: a strategy that screens all-A and then takes the bottom market-cap
quantile computationally, with no `小市值`/`000852` literal, scores 全A. The file already carries a
comment about nearly losing 小市值's own signal that way.

The contract, modelled on `utils/family-match.js`:

- the classifier reads the base source and **proposes** `universe:` with a short justification
  quoting the deciding lines;
- the value is written **once** onto the family page as frontmatter;
- `wiki-type-build.js` **reads the field** and never re-derives it;
- re-classification happens only on explicit request, never per build.

⚠ This discipline is the point, not ceremony. The type axis feeds integration decisions; a
classifier that re-runs on every build would reshuffle universes silently and make integrate
rounds incomparable with each other. `family:` is human-assigned for exactly this reason.

The existing regex keeps its job as a **second opinion**: when it and the LLM disagree, the page
records both and the disagreement is surfaced, rather than one silently winning.

### Prerequisite

`ETF动量`'s page still carries the unfilled template `base: [[<postId8>_<代表基类>]]`, so there is
no source to classify and it falls to `其他`. **No classifier fixes this** — it is a data gap and
must be filled first.

## 5. The composition loop

### Why composition rather than blending

A blend allocates capital across finished books. Its *return* cannot exceed the weighted average
of its legs; only its risk improves. That is why the existing guard exists: 七星高照's blend scored
sharpe **3.17** from legs of 2.85/1.60 and still lost to its own small-cap leg (0.4814 vs 0.5984).

A conjunction can be superadditive, and this repo has measured one: 红利低频's two-factor
conjunction returned **23.41% against 11.75% for the sum of its legs, at lower risk than either**.

So composition is where the alpha could be, and blending is where the illusion is.

### Shape

Four roles, mirroring `/run-family` because the machine is the same:

1. **composer** — proposes a conjunction from two (or more) families in one universe, stating
   *which mechanism is taken from each* and why they can coexist. Grounded in the families' `edge:`
   blocks and §6 findings, exactly as the family generators are.
2. **gatekeeper** — ranks candidate pairs and refuses the inadmissible (§5 rules).
3. **builder** — writes ONE strategy file implementing the conjunction and runs it on the frozen
   bench, `--window train`.
4. **judge** — `utils/type-integrate-check.js`, unchanged in spirit (§6).

### Admissibility rules for a pair

- **Same universe**, by the recorded `universe:` field.
- **Both edges `measured`.** Never `proposed` (unevidenced) and never `refuted` (known false).
  Today that excludes 五福闹新春, 红利低频 and 大小盘轮动 from any composition.
- **⚠ Distinct edges, semantically.** `规模因子` and `规模` are one edge. `utils/edge-redundancy.js`
  already clusters by edge name; it needs to cluster by *meaning*, and that comparison is the
  gatekeeper's judgement, recorded with a reason.
- **Compatible mechanics**, argued explicitly: two cross-sectional screens on the same rebalance
  compose (size floor + dividend screen); a 1.5-day limit-up book and an ETF discount mean-reversion
  do not obviously compose, and the composer must say why it believes they do.

## 6. Acceptance

The judge's four existing rules stay as the **floor**:

1. beat the best MEMBER, not the gate (integration's threshold is 2.0, not 1.5)
2. declare the diversification share — attribution from stored curves; if stripping diversification
   drops sharpe below the best member, the verdict is `keep-with-caveat`
3. optimised weights must beat equal weight by more than 1pp (the ~0.15pp re-run noise floor)
4. realizability is inherited at its WORST leg

Rule 2 matters *more* under composition, not less: a conjunction that happens to diversify will
look brilliant for the wrong reason, and we need to know which it was.

### The new rule, and the protocol problem it creates

The user's rule: **the composite must beat or equal the best input family, with TRAIN and VAL
agreeing.**

⚠ `harness.md` is explicit that VAL `仅定稿一次` and `不回头驱动选择` — it may not drive selection.
If "beat-or-equal on VAL" is a test a failed candidate can be retried against, VAL silently becomes
a search surface, and once that happens the only clean window left is the 2-test OOS reserve.

**Recommended resolution** — keeps the intent, keeps the protocol:

- **Iterate on TRAIN only.** The TRAIN criterion is beat-or-equal the best input family.
- **One VAL confirmation** on the finalised composite, where beat-or-equal must *also* hold.
- **A VAL failure is terminal for that composition** — recorded as refuted, with its reason. It is
  not an invitation to compose a different variant and try again. That single word is what keeps
  this from being selection-on-VAL.
- The type layer therefore needs its **own VAL budget**, enforced like `utils/val-budget.js`
  enforces the family one: one validation per (composition, epoch).

**Alternative, if the above is too strict**: require beat-or-equal on TRAIN, and on VAL require
only a *pre-declared floor* ("does not collapse"), stated before the run. Weaker, but leak-free for
the same reason — the bar is fixed in advance.

**DECIDED 2026-10-07 (user)**: the recommended resolution. Iterate on TRAIN against
beat-or-equal; confirm ONCE on VAL where beat-or-equal must also hold; a VAL failure is
TERMINAL for that composition. A type-level VAL budget enforces one validation per
(composition, epoch), the way `utils/val-budget.js` does for families.

## 7. Budget and ranking

N families in a universe give N(N−1)/2 pairs, each a real backtest at up to the 45-minute cap
against ~180 free minutes a day. That is **4–6 experiments per day**, so ranking is mandatory:

- prefer pairs whose edges are furthest apart (the redundancy clusterer already measures this);
- prefer universes with more usable material — 全A (3 pairs) before ETF (1);
- `component-scan.js` blends remain a **screening device only** for ordering pairs: they are
  ex-post, cost-free and daily-rebalanced, an upper bound and never a result.

## 8. What this does NOT change

- The frozen bench. Every composite is measured under the active epoch, with the same pins.
- OOS stays hard-blocked and user-only.
- `type-integrate-check.js`'s four rules, which become the floor rather than the whole test.
- Family-level work. `/run-family` continues to produce the champions this layer consumes.

## 9. Sequence

1. Fill `ETF动量`'s `base:` — one line, unblocks its classification.
2. Classify `universe:` for all 13 families; record both the LLM call and the regex second opinion.
3. Rebuild `wiki/types/` on the single axis (free, no backtests).
4. Audit edges within each universe for *semantic* distinctness — this is what decides whether the
   loop has anything to do on day one, and 小盘 already shows it will collapse a pair.
5. Only then build the composition loop.

⚠ Step 4 can legitimately conclude "there is nothing composable yet". That is a finding, not a
failure, and it is cheaper to learn before the loop exists than after.
