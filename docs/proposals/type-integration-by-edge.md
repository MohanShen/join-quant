# Integration by edge composition, on one axis

**Status**: ACCEPTED 2026-10-07 · **Revision 2, 2026-10-11** (merge replaces composition: §5, §6, §7, §9)
· **Revision 3, 2026-10-13** (rule 1 becomes a per-year comparison; harness epoch 7: §6)
· **Revision 4, 2026-10-16** (INCREMENTAL rounds replace all-pairs; a `/run-family` exit gate: §10)
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
   → ⚠ **Superseded by Revision 2 (§5)**: a round now MERGES two families in one universe into a
   single strategy by taking the best variant of each pipeline step, and a shared edge is no
   longer a refusal. The reasoning that led here is kept because it explains the guard set.

And one acceptance rule: a merged strategy must **beat or equal the best input family**, with
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

Collapsing the nine two-axis cells gives six universes, four with more than one family. These are
the figures AFTER the §4 classification, not the earlier regex estimate:

| universe | families | measured edges | mergeable (§5) |
|---|---|---|---|
| ETF | 5 — ETF动量, ETF溢价, PT多策略, 七星高照, 五福闹新春 | 均值回归 · 流动性溢价 · 动量 | ⚠ yes, but the top two declare themselves unrealizable |
| 小盘 | 2 — 多因子ML, 小市值 | 规模因子 · 规模 — **one edge, two spellings** | **yes — the best first candidate** |
| 全A | 2 — 打板短线, 红利低频 | 涨停动量延续 (红利低频's is `refuted`) | yes |
| 宽基大盘 | 2 — 网格, 趋势技术 | 均值回归 · 动量 | yes, but 网格 has no epoch-6 row |
| 固定篮子 | 1 — 三进兵 | 趋势择时 | no — promote (and it is BLOCKED: objective −0.09) |
| 混合 | 1 — 大小盘轮动 | 风格轮动择时 (`proposed`) | no — promote |

Against a `wiki/types/` directory that held **two stale single-family pages**, that is four
mergeable universes.

⚠ Under Revision 1 小盘 scored **0 composable pairs** — `规模因子` and `规模` are one edge spelled
two ways. Under Revision 2 that is exactly what makes it the best *merge* candidate: same market,
same source of return, two different implementations to pick steps from.

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

## 5. The merge loop  *(REVISED 2026-10-11 — replaces the composition loop)*

> **Revision 2.** §1–§4 stand unchanged: one axis, `universe:` assigned by reading the base
> source, recorded on the family page. What changes is what a round *does* with two families in
> one universe.
>
> | | Revision 1 (composition) | Revision 2 (merge) |
> |---|---|---|
> | the round builds | a conjunction of two EDGES | one strategy assembled from the best STEP of each |
> | same edge | refused | **allowed** |
> | nothing admissible | promote | promote (unchanged) |
> | binding risk | diversification masquerading as alpha | **overfitting a step search** |

### Why this replaces composition

**The instrument-overlap problem dissolves.** Two families can share a `universe:` label and trade
disjoint instruments — PT多策略 screens to ETFs with 5e6 < turnover < 2e7 while 七星高照 holds 7
hand-picked liquid ones, so their intersection is empty. Under composition that had to be detected,
and detecting it turned out to be expensive:

- JoinQuant exposes **no holdings**. Probed 2026-10-11: `trade`, `trades`, `transaction(s)`,
  `order(s)`, `position(s)`, `holding(s)`, `record` all return 60-byte empties; only `detail`
  answers, with metadata. `result.orders` looked promising — it is in the endpoint we already call
  for the curve — but it is `{buy:{time,value}, sell:{time,value}}`, a per-day marker count for
  plotting. **No instrument identity anywhere.**
- Static parsing covers 6 of 13 families; the other 7 define their pool dynamically and their only
  literal ticker is usually `set_benchmark`.
- So an overlap test would have required instrumenting the OVERRIDE and re-running all 13 bases.

**A merge builds ONE strategy and therefore declares ONE universe.** The question "do these two
trade the same names?" stops existing, because the merged strategy trades whatever universe we
choose for it. That cost is avoided entirely, not deferred.

### Why same-edge is no longer a refusal

Refusing a shared edge was right for *conjunction* — a mechanism cannot be conjoined with itself.
It is wrong for *assembly*. 多因子ML and 小市值 both earn from 规模, and that is exactly why their
steps are interchangeable: same market, same source of return, two different implementations of
entry, exit and risk. The shared edge makes the merge coherent rather than redundant.

⚠ The same-edge check stays in `integrate-queue.js` but **stops gating**: it becomes information
("these two earn the same way"), not a veto.

### The pipeline skeleton

A merge decomposes each family into the same steps and picks one variant per step:

| step | what it decides |
|---|---|
| universe screen | which instruments are eligible at all |
| selection / ranking | which of them to hold, and in what order |
| entry | the condition and the moment of buying |
| holding / exit | how long, and what ends it |
| risk overlay | market filter, calendar blackout, stop |
| sizing | count, weights, participation |

The evidence already exists, in §2 rather than in the register. `data/components.tsv` has **1 row**,
but 小市值's §2 alone carries `q-1 换到第 1001–2000 名` (universe), `q-2 去低开条件` (entry),
`q-3 去 11:30 退出` (exit), `q-4 去 1/4 月空仓` (calendar), and 多因子ML's carries `q-e6-1
small_cap=0` and `q-e6-2 etf=0` (factor weights). A distillation pass over §2 costs no backtests.

### Shape

1. **decomposer** — map both families onto the skeleton from their §2 findings and base source,
   and state, per step, which family's variant is the candidate and the measured row that says so.
2. **gatekeeper** — bound the search (below), and refuse steps whose evidence does not apply.
3. **builder** — write ONE strategy implementing the chosen steps; run it on the frozen bench.
4. **judge** — `utils/type-integrate-check.js`, with the revised rule set in §6.

## 6. Acceptance  *(REVISED)*

### The guard set changes shape

| rule | status under merge |
|---|---|
| 1. beat the best MEMBER, not the gate | **binds** — per-year since Revision 3, below |
| 2. declare the diversification share | **inert** — there is no blend to attribute |
| 3. optimised weights must beat equal weight | **inert** — there are no weights across books |
| 4. realizability inherited at its WORST leg | **binds** |

Rules 2 and 3 were the guard against diversification masquerading as alpha. A merge produces one
book, so they have nothing to measure. ⚠ That is not a relaxation — the risk they covered is gone,
and a *different* risk takes its place, which rules 5 and 6 exist for.

### Rule 1 is a per-year comparison  *(REVISION 3, 2026-10-13 — harness epoch 7)*

Revision 2 left rule 1 reading "beat the best member's **pooled TRAIN objective**". Two rounds ran
under it (小盘, 全A), both REJECT, and both reported that the bar itself looked unsound. Measuring
the objective settled it:

| measured over the 60 epoch-6 normalized rows | |
|---|---|
| Pearson r(annual%, objective) | **0.9698** |
| maxDrawdown's share of the spread the formula sees | **24%** (sd 13.7 vs 43.6) |
| Spearman ρ(objective, sharpe) | **0.9836** |

Two conclusions, one of which contradicts what the rounds assumed:

1. **objective and sharpe do not disagree** (ρ = 0.984), so the old "rank on one, gate on the
   other" worry was unfounded — and the separate 2.0 integrate gate never bound on anything that
   could win (0 of the top-16 by objective failed it; the only 3 rows in 1.5–2.0 score ≤ 0.2970).
   Epoch 7 drops it to 1.5, matching every other stage.
2. **objective is essentially annual return**, and annual return over TRAIN is substantially a
   **2022** measurement: across the 13 stored TRAIN curves 2022 supplies a median **62%** of
   log-growth and 63–71% for every top-8 book. TRAIN is 2022-01-01..2023-12-31; 2022 was the
   small-cap rally.

So the pooled bar asked "did you earn more in the 2022 rally", which is the wrong question for
this round twice over: a **same-edge merge** (小盘: two implementations of 规模) is after
robustness and has no channel to express it, and a candidate that trades the 2022 tail for 2023
steadiness **loses by construction** — exactly the 全A verdict, 「combining relocates WHICH YEAR
earns; it does not add」.

**Revision 3**: rule 1 compares the candidate's **worst TRAIN calendar year** against the **most
consistent member's** worst TRAIN year, on the same `(annual − maxDD)/100` computed within each
year. A maximin, not per-year domination — domination lets one member own 2022 and another own
2023, so a candidate is rejected for losing to a pair no single member matches. The pooled
comparison is retained as **evidence** and no longer vetoes (`integrateBar.pooledIsVeto = false`).

⚠ **This is not a loosening.** Re-applied to the two completed rounds it confirms both rejections
and explains them: all three 全A candidates have a **negative** worst year (−0.0464 / −0.1014 /
−0.4437). It also corrects *who* the candidate was up against — 全A's pooled leader 打板短线
(0.9668) has a worst year of **−0.3591**, so the real bar is 红利低频's **0.1224**.

Frozen definition and the two arithmetic traps (convert-before-slice; annualize over the window
year) live in `harness/harness.md` §4.1. Nothing is re-measured: epoch 7 declares
`measurementPreservedFromPrevious: true`.

### 5. The candidate set is declared and bounded

Best-of-each across six steps from two families is up to 2⁶ combinations. Evaluated on TRAIN that
is a multiple-comparisons search, and it is a larger search than the family loop ever runs.

- at most **3 candidates per (universe, epoch)**, named and justified **before** the first is run;
- each step choice cites the measured §2 row or component that supports it;
- a sweep is not a candidate set. Enumerating combinations and keeping the winner is the failure
  mode this rule exists to prevent.

### 6. No assembly from summed deltas

⚠ A step's measured delta belongs to the pipeline that produced it. "Removing the 11:30 exit cost
X" was measured inside 小市值's holding period, on 小市值's names. Transplanted into a weekly
rebalance it inherits nothing — the same principle CLAUDE.md states for factor-board figures: *a
result belongs to the bench that produced it.*

**Every merged candidate is built and measured as one strategy.** Predicted deltas may rank the
candidates; they may never stand in for a measurement.

### The VAL rule is unchanged, and matters more

**ONE validation per (universe, epoch)**, `utils/val-budget.js` with `kind: 'type'`. Iterate on
TRAIN; the composite must beat or equal the best input family there, and again on the single VAL.
**A VAL failure is TERMINAL for that universe this epoch** — it does not license a fourth
candidate. With a step search upstream, this is the only thing standing between the loop and a
held-out window quietly turned into a second training set.

## 7. Budget and ranking  *(REVISED)*

A merge candidate is one strategy and one backtest, at up to the 45-minute cap against ~180 free
minutes a day — so **4–6 experiments per day**, and §6 rule 5 caps a universe at 3 candidates per
epoch anyway. The scarce resource is no longer backtest slots; it is the VAL, of which each
universe has exactly one.

Ranking therefore applies to UNIVERSES, not pairs:

- prefer universes whose families have the richest §2 — the decomposition is only as good as the
  step evidence behind it, and a family with no ablations contributes nothing to pick from;
- **skip universes whose candidates declare themselves unrealizable.** Merging steps from such a
  book inherits the problem under rule 4; ETF's top two are in this state;
- a universe with one family is a PROMOTE, not a cheap merge.

⚠ `component-scan.js` blends are now irrelevant to this layer. They ranked BLEND candidates by
ex-post, cost-free, daily-rebalanced uplift; a merge is not a blend, and the figure has nothing to
say about which step to take from which family.

## 8. What this does NOT change

- The frozen bench. Every merged candidate is measured under the active epoch, with the same pins.
- OOS stays hard-blocked and user-only.
- `type-integrate-check.js` keeps rules 1 and 4; rules 2 and 3 go inert under a merge (§6).
- The PROMOTE path, including its positivity floor and its realizability floor.
- The VAL budget: one validation per (universe, epoch), a failure terminal for that epoch.
- Family-level work. `/run-family` continues to produce the champions this layer consumes.

## 9. Sequence

Steps 1–5 are DONE (commits 6b077ec, a4f5215, 9dbb381):

1. ~~Fill `ETF动量`'s `base:`~~ — done; it was the unfilled template.
2. ~~Classify `universe:` for all 13 families~~ — done, with `universeBasis` and the regex second
   opinion recorded. ⚠ The regex disagreed on **6 of 13**, including every ETF family.
3. ~~Rebuild `wiki/types/`~~ — done: 9 two-axis cells → 6 universes, 4 multi-family.
4. ~~Audit edges per universe~~ — done. ⚠ Under Revision 2 this audit's *conclusion* changes: the
   pairs it refused for sharing an edge (小盘) are now the best merge candidates.
5. ~~Build the loop~~ — the queue, the promote path and the VAL budget are built and in use. The
   ETF round ran and refused all three pairs with recorded reasons.

Remaining, under Revision 2:

6. **Distil §2 into the pipeline skeleton** for the families of one universe — free, no backtests.
   `data/components.tsv` exists for this and has 1 row; §2 has the material.
7. **Re-point `integrate-queue.js`**: same-edge becomes information, not a veto; a universe with
   ≥2 families is MERGE; the gatekeeper refusals already recorded stay valid as *composition*
   verdicts and must not be read as merge verdicts.
8. **Run the first merge on 小盘** (多因子ML × 小市值) — same universe, same edge, two different
   implementations, both with rich §2. It is precisely the pair Revision 1 refused, so it exercises
   the change end to end.

⚠ Not ETF. Its top two declare their own headlines unrealizable, and a merge inherits that at
rule 4.

---

## 10. Incremental rounds  *(REVISION 4, 2026-10-16 — user specification)*

§5's loop surveyed a universe for mergeable PAIRS. That was wrong in a way no amount of tuning
fixes: it treated a universe as a static set with no memory of what it had already delivered, so
the same pairs came back round after round and a round's own result changed nothing about the
next one. Two rounds ran that way (小盘, 全A), both REJECT, and neither left the universe in a
different state than it started.

### The model

A universe holds a set of **promoted candidates** — durable state in `data/promoted.tsv`
(append-only, tracked, replayed by `utils/promoted.js`). Families arrive **one at a time** after
clearing `/run-family`, and each arrival meets that set:

| outcome | condition | effect |
|---|---|---|
| **1 — promote** | no promoted candidate overlaps its symbols | the arrival is promoted. An EMPTY set needs no judgement: it is simply the first |
| **2 — merge** | an overlapping incumbent, merge is better | the merged candidate is promoted and **supersedes** the incumbent; the arrival lives on inside it |
| **3 — reject** | an overlapping incumbent, merge fails | the incumbent is **unchanged**; the **arrival** is rejected |

**Sequence is load-bearing**, which is the whole reason this is state and not a computed view: the
first arrival defines what everything after it has to beat. Families therefore enter
`/run-family` ordered by **champion TRAIN sharpe**, highest first (`utils/family-queue.js`).

**Multi-overlap** resolves to the **highest-sharpe** incumbent. One merge attempt per arrival
keeps the cost bounded; trying each in turn would be a search over incumbents, with the
multiple-comparisons problem §6's rule 5 exists to prevent.

**A rejection is keyed to the `candidateId`**, never the family. Outcome 3 is "rejected until this
family has a new best variant", so the champion's `sourceFile` is the key and a new best variant
is automatically a new attempt — no expiry rule to get wrong, and one failed merge can never
silently retire a lineage.

### The `/run-family` exit gate

Integration takes only the best variant that ALSO passed validation, and will not take an
untradeable one (`utils/integrate-eligible.js`):

1. a **champion** measured under an epoch the active one accepts;
2. a **VAL that PASSED** `stageGate('validate')`;
3. **realizability ≥ 2**, agent-scored and recorded as `realizability:` on the family page.

Requirement 3 is why §6's rule 4 never has to bind: nothing with an untradeable leg can arrive.
The check remains in the guard as defence in depth.

⚠ **Unknown realizability BLOCKS**, the same rule the VAL budget applies to an unknown epoch —
blocking is visible and a human clears it with one edit, whereas permitting silently ships an
unrealizable book. And it is **not** inferable from the `不可实现` regex: 打板短线 does not match
it and was scored 1 on evidence.

### Measured consequence

As of 2026-10-16, **1 of 13 families** clears the gate: 红利低频, which seeded 全A. Four are
rejected on realizability (PT多策略, 小市值, ETF溢价, 打板短线) and eight blocked — seven never
validated, two with no champion under the active epoch. So the binding constraint is **VAL
coverage and realizability**, not integration, and the queue correctly reads
`IDLE … the gate is upstream (/run-family)` almost everywhere.

⚠ **Known gap, not closed**: eligibility checks the VAL sharpe, not the champion's TRAIN sharpe.
红利低频 seeded 全A with a champion at TRAIN sharpe **1.46**, below the 1.5 every other stage
holds, because its VAL passed at 2.05. That is as specified, but a universe can currently ship a
champion that fails the TRAIN gate.
