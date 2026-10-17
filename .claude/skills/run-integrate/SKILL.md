---
name: run-integrate
description: Run one UNIVERSE-level round — one family arrives against what that universe already ships and is either promoted (no symbol overlap), merged into a better candidate, or rejected. Use when asked to integrate or combine strategy families, work at the type/universe level, or deliver a champion per universe.
---

# Run one universe round

The layer above `/run-family`. That loop works **one lineage**; this takes ONE family that has
cleared it and meets what its universe **already ships** — promoting it, merging it into something
better, or rejecting it.

**Authority**: `docs/proposals/type-integration-by-edge.md` (Revision 4, 2026-10-16),
`harness/harness.md` §4.1 (the frozen bar), `screen/screen.md` §3 R (realizability).
This skill is the entry point and does not restate them.

## One strategy, not two books — the distinction this round turns on

A **blend** allocates capital across finished books. Its return cannot exceed the weighted average
of its legs; only its risk improves. This repo measured the trap twice: 七星高照's blend scored
sharpe **3.17** from legs of 2.85/1.60 — and still lost to its own small-cap leg (0.4814 vs
0.5984). Blending raises sharpe mechanically whenever correlation < 1, and the gate **is** a sharpe
threshold, so an unguarded round manufactures passes that contain nothing.

Building ONE strategy avoids that entirely, and avoids something else too: a merged strategy
declares **one universe**, so the question "do these two trade the same names?" never has to be
answered after the fact — which is fortunate, because JoinQuant exposes no holdings to answer it
with (§Why the agent).

⚠ **Revision 4 (2026-10-16)** replaced the all-pairs model with the incremental one below.
Revision 2's rule still holds inside a merge: a shared edge is **not** a refusal — two families
earning the same way are exactly the ones whose entry, exit and risk steps are worth comparing.

## How a round starts

Either a human invokes this skill, or the **daily cron** does: `integrate` leads `PRIORITY` in
`utils/daily-pipeline.js` (later stages outrank earlier ones), and `scripts/run-integrate.sh`
dispatches one round pinned per UNIVERSE at `data/integrate-sessions/<universe>.txt`. A universe
mid-round resumes its own session; one that has never had a round gets a clean one. ⚠ A **seed**
costs no backtest, so the wrapper skips its CDP and budget preflights and the planner exempts it
from the day's budget stop — a universe must never ship nothing for want of minutes it was not
going to use.

```bash
scripts/run-integrate.sh --list         # the queue plus each universe's session state
DRY=1 scripts/run-integrate.sh          # what the next round would be, nothing run
```

## Start here

```bash
node utils/integrate-queue.js           # every universe: promoted set, arrival queue, action
node utils/integrate-queue.js --next    # the single highest-value action
node utils/integrate-eligible.js        # who may supply a candidate at all, and why not
node utils/promoted.js                  # what each universe currently ships
```

## The model is INCREMENTAL  *(Revision 4, 2026-10-16 — replaces all-pairs)*

A universe holds a set of **promoted candidates**. Families arrive **one at a time** after
clearing `/run-family`, ordered by their champion's TRAIN sharpe (highest first), and each
arrival meets the promoted set. Three outcomes, and every round ends in exactly one:

| outcome | condition | what changes |
|---|---|---|
| **1 — promote** | nothing promoted overlaps its symbols | the arrival is promoted. With an EMPTY set this needs no judgement: it is simply the first |
| **2 — merge** | an overlapping incumbent, and the merge is BETTER | the merged candidate is promoted and **supersedes** the incumbent; the arrival lives on inside it |
| **3 — reject** | an overlapping incumbent, and the merge fails | the incumbent is **unchanged**; the **arrival** is rejected until its family has a new best variant |

⚠ **Sequence is load-bearing.** The first arrival defines what everything after it must beat.
That is why this is durable state (`data/promoted.tsv`) and not a computed view.

⚠ **Multi-overlap**: an arrival overlapping several promoted candidates merges against the
**highest-sharpe** one only. One attempt per arrival; trying each in turn is a search.

The queue returns one of three actions per universe:

| action | meaning |
|---|---|
| `seed` | promoted set is empty and an eligible arrival exists — **promote it, free, no judgement** |
| `integrate` | an arrival meets a non-empty promoted set — **dispatch the agent** (below) |
| `idle` | nothing eligible is queued; the gate is upstream in `/run-family` |

## What `/run-family` must deliver before anything reaches here

`utils/integrate-eligible.js` is the exit gate, and this round never re-litigates it:

1. a **champion** measured under an epoch the active one accepts;
2. a **VAL that PASSED** `stageGate('validate')` — one validation per (family, epoch);
3. **realizability ≥ 2**, agent-scored and recorded as `realizability:` on the family page.

Requirement 3 is why the judge's rule 4 never has to bind. ⚠ **Unknown realizability BLOCKS** —
it is not inferable from the `不可实现` regex, and an unscored family is reported, not assumed.

⚠ `integrate-eligible` now names the **owner** of every block — which stage can clear it
(`research` / `normalize` / `human` / `none`). `utils/family-queue.js` reopens the
`research`-owned ones with `reason: integrate-blocked`, so an `IDLE` universe feeds back into
`/run-family` automatically instead of waiting for a human to notice. Before that, 8 of 13
families were blocked here while the research queue read **0 due**.

⚠ Measured 2026-10-16: **1 of 13 families** currently clears this gate. Four are rejected on
realizability and eight blocked (seven never validated). `IDLE … the gate is upstream` is the
expected reading, not a fault — the bottleneck is VAL coverage, not integration.

## SEED — do it inline, it is free

No judgement, no backtest, no agent. Record it and stop:

```bash
node -e "require('./utils/promoted').record({universe:'<U>', action:'promote', \
  candidateId:'<champion sourceFile>', kind:'family', members:['<family>'], \
  sharpe:<n>, objective:<n>, note:'SEED — first eligible candidate; …'})"
```

## INTEGRATE — dispatch the agent, do not do it inline

**The agent drives this step.** Dispatch `integrate-merger` (`Agent` tool,
`subagent_type: "integrate-merger"`) with the arrival and the promoted set. Its contract is
`.claude/agents/integrate-merger.md`.

The division is deliberate:

| | |
|---|---|
| **deterministic** | which universes exist, who is eligible, the arrival ORDER, the promoted set, the realizability floor, the VAL budget, the judge rules |
| **the agent** | symbol overlap, what kind of merge the edges call for, the decomposition, the candidate set, the build |

### Why the agent and not a program

**Symbol overlap has no programmatic answer.** A shared `universe:` does not mean two books touch
the same instruments — PT多策略 screens to ETFs with turnover in 5e6–2e7 while 七星高照 holds seven
named liquid ones, an empty intersection. And it cannot be looked up: JoinQuant exposes **no
holdings** (`trade`, `order(s)`, `position(s)`, `holding(s)` all empty; `result.orders` is a
chart-marker count with no instrument identity). The agent reads the **selection logic** and judges.

Edge names are annotation only: `规模` and `规模因子` are one mechanism in two spellings, while
`动量` in two families can be two mechanisms under one word.

⚠ A declared `parent:` lineage is refused **deterministically** before the agent sees it — a child
is a FORK of its parent and already carries its mechanism.

### What the agent must come back with

1. **An overlap judgement with its reasoning**, against each promoted candidate. Outcome 1 if none
   overlaps; otherwise name the highest-sharpe overlapping one as the merge target.
2. **What kind of merge this is.** Identical edge sets → the **better implementation** of one edge.
   Different sets → **combine** them. Both merge; the answer defines what "better" means.
3. **A decomposition** onto the pipeline skeleton, each step citing the §2 row that measures it.
4. **At most 3 candidates, declared before any is run.** A sweep is not a candidate set.
5. **One built strategy per candidate**, from `enhance/strategy_template.py`, on `--window train`.

### What you check when it returns, and what you record

- the overlap judgement is recorded **either way**;
- `type-integrate-check.js` was run and the bar it applied was **`perYearSharpe`**, not
  `pooled-fallback`;
- then write the outcome to the register — this is the step that makes the round mean anything:

```bash
# outcome 2 — the merge won
node -e "require('./utils/promoted').record({universe:'<U>', action:'promote', \
  candidateId:'<expId>', kind:'merged', members:['<A>','<B>'], sharpe:<n>, objective:<n>, note:'…'})"
node -e "require('./utils/promoted').record({universe:'<U>', action:'supersede', \
  candidateId:'<incumbent candidateId>', note:'superseded by <expId>'})"

# outcome 3 — the merge failed; the incumbent stands, the ARRIVAL is rejected
node -e "require('./utils/promoted').record({universe:'<U>', action:'reject', \
  candidateId:'<arrival champion sourceFile>', note:'<why — required>'})"
```

⚠ A `reject` **requires a note**: the next round must read *why*, not merely *that*. And it is
keyed to the candidate, so a new best variant for that family automatically earns another attempt.

⚠ **VAL is yours to protect, not the agent's.** One validation per (universe, epoch); a failure is
**terminal for that universe this epoch** and does not license a fourth candidate.

## The bar — what "better" means (epoch 8)

The sharpe gate is **1.5 at every stage**; integration no longer holds a different one. Its real
bar is **per-year sharpe domination** (epoch 8): in **every** TRAIN calendar year the candidate's
sharpe must exceed the best **parent champion's** sharpe in that **same** year.
`harness/harness.md` §4.1 is frozen authority.

⚠ Epoch 7's worst-year objective maximin is **invalidated**. An epoch-7 round still states an
epoch-7 conclusion, but it is not an epoch-8 one without re-judging.

⚠ Under the incremental model the two **parents are the merge inputs**: the incumbent promoted
candidate and the arrival's champion. An incumbent may itself be a MERGED artifact with no family,
so the guard does not champion-resolve it — its own figures ARE the bar, because it is what the
universe currently ships.

⚠ The bar can be a **composite**: the best parent may differ by year, so the candidate faces
something no single parent achieves. Deliberate, and strictly harder. The bar needs stored curves
for the candidate and every parent; without them it falls back to the pooled rule and says so
(`bar=pooled-fallback`). All 11 family champions have one as of 2026-10-16 — `series-rekey.js`
recovered 39 that had been saved under an unreadable key.

This is not a relaxation — applied to the two all-pairs rounds already run it **confirms both rejections**
and sharpens them: all three 全A candidates turn out to have a **negative** worst year
(−0.0464 / −0.1014 / −0.4437), which is the measured form of what that round could only say in
prose, 「combining relocates WHICH YEAR earns; it does not add」.

What it fixes: the pooled objective is almost purely annual return (r = **0.9698**), and annual
return over TRAIN is substantially a 2022 measurement (2022 supplies a median **62%** of
log-growth across the stored curves). So a merge whose payoff is **robustness** — two
implementations of one edge, the 小盘 case — had no channel to register, and a candidate trading
the 2022 tail for 2023 steadiness lost by construction.

The pooled comparison is still printed as **evidence** and never vetoes.

## Do not

- Weight two finished books and call it integration.
- Treat a gate pass as success — see the failure mode above.
- Build on edges that are `proposed`, `refuted`, or carry `supersededBy:`.
- Refuse a pair because its edges are identical — that is what makes a merge coherent.
- Average realizability across legs.
- Touch VAL during selection, or OOS at all.
- Write a merge result into a family page — it belongs to the type.
- **Re-litigate eligibility.** If a family is not in the arrival queue, the fix is in
  `/run-family` (validate it, or score its realizability), never a workaround here.
- **Finish a round without writing to `utils/promoted.js`.** An unrecorded outcome means the next
  arrival meets the wrong incumbent, and the sequence is the whole model.
- **Reject a family rather than its candidate.** The key is the `candidateId`; keying a rejection
  to the family would retire a lineage on one failed merge.
