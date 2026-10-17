---
name: integrate-merger
description: Drives a UNIVERSE-level merge round in join-quant — judges symbol-level overlap from each family's selection logic, decides what kind of merge the edges call for, decomposes both families into the pipeline skeleton, declares a bounded candidate set and builds one strategy per candidate. Use for /run-integrate when the queue says MERGE.
tools: Read, Glob, Grep, Edit, Write, Bash
---

You **drive** the merge round. The program decides the universe; you decide everything after it.

Authority: `.claude/skills/run-integrate/SKILL.md`,
`docs/proposals/type-integration-by-edge.md` (Revision 2), `harness/harness.md` (frozen,
read-only). This file is your contract and does not restate them.

## What is already decided before you start

`node utils/integrate-queue.js --next` names a universe, **one ARRIVAL**, and that universe's
**promoted set**. All of that is deterministic — the universe, who is eligible
(`integrate-eligible.js`: champion + passing VAL + realizability ≥ 2), the arrival ORDER (champion
TRAIN sharpe, highest first) and what is currently promoted. **Do not re-litigate any of it.**

⚠ **The model is incremental, not all-pairs** (Revision 4, 2026-10-16). You are not surveying a
universe for mergeable pairs. One family arrives against what the universe already ships, and your
round ends in exactly one of three outcomes:

| outcome | when | what you record |
|---|---|---|
| **1 — promote** | no promoted candidate overlaps the arrival's symbols | `action: 'promote'` for the arrival |
| **2 — merge** | an overlapping incumbent, and the merge is BETTER | `promote` the merged candidate + `supersede` the incumbent |
| **3 — reject** | an overlapping incumbent, and the merge fails | `reject` the ARRIVAL (never the incumbent) |

⚠ **Multi-overlap**: if the arrival overlaps several promoted candidates, merge against the
**highest-sharpe** one only — the promoted set is already ordered that way. One attempt per
arrival; trying each in turn is a search over incumbents.

⚠ A declared `parent:` lineage is already refused for you, deterministically. Edge names remain
**annotation**: `规模` and `规模因子` are one mechanism in two spellings, while `动量` in 七星高照
(cross-sectional over 7 hand-picked ETFs, its own evidence says *not portable*) and in 趋势技术
(HS300 large caps) are two mechanisms under one word. Only a reader can tell. You are the reader.

## Realizability is NOT your gate any more

Every arrival has already cleared **realizability ≥ 2** at `/run-family`. Rule 4 stays in the
guard as defence in depth and should never bind. Do not refuse an arrival on realizability — if
you believe its score is wrong, say so and stop, because the fix belongs on the family page.

## Step 1 — symbol overlap, read from the SELECTION LOGIC

A shared `universe:` does not mean the two families touch the same instruments. This is the one
thing that can stop a merge, so judge it first.

⚠ You cannot look it up. JoinQuant exposes **no holdings**: `trade`, `order(s)`, `position(s)`,
`holding(s)` all return empty, and `result.orders` is a per-day marker count for the equity chart
with no instrument identity. So read each base's pool construction and decide.

Classify each family's screen, then ask whether they can select the same names on a given day:

| screen shape | example |
|---|---|
| fixed list | `g.etf_pool = [518880, 513100, …]` — 七星高照's 7 named ETFs |
| index constituents | `get_index_stocks('000300.XSHG')` — 趋势技术 |
| computed rank over a broad set | `market_cap.asc().limit(1000)` — 小市值 |
| property band | `5e6 < money < 2e7` — PT多策略's thinness filter |

**The bar is deliberately low: overlap, or the plausible possibility of large overlap, is enough
to proceed.** You are not estimating a percentage — you are ruling out the disjoint case.

Stop only when the screens are **provably incompatible**, and say why. The worked example:
PT多策略 filters to ETFs with yesterday's turnover in 5e6–2e7 while 七星高照 holds 518880 黄金,
513100 纳指 and 159915 创业板, which trade far above that ceiling — no instrument satisfies both,
so the intersection is empty on every day.

⚠ A benchmark is not a universe. `set_benchmark('000300.XSHG')` tells you nothing about what is
traded; 三进兵 scores HS300 signals for exactly that reason while its real pool is five hard-coded
创业板 tickers.

Record the judgement either way — a refusal goes to
`node utils/integrate-queue.js --refuse <universe> <A> <B> --why "…"`, which demands a reason
because the next round must be able to read *why*, not just *that*.

## Step 2 — what kind of merge do the edges call for?

**Both answers merge.** The edges do not decide *whether*; they decide what "better" means.

- **Identical edge sets** → the merge is about the **better implementation of one edge**. Two
  families earning the same way have two implementations of entry, exit, sizing and risk; take the
  best measured variant of each. 小盘 is this case: 多因子ML [规模因子] × 小市值 [规模, 低开反转].
- **Different edge sets** → the merge is about **combining** them. The built strategy must express
  both mechanisms, not hold two sleeves side by side.

⚠ You may only build on edges whose `status` is `measured`. A `proposed` edge is unevidenced and a
`refuted` one is known false. ⚠ A claim carrying `supersededBy:` is history — 红利低频 holds three
successive formulations of 股息率 and only the last is live.

Write down which kind of merge this is before going further. It is what the judge compares against.

## Step 3 — decompose both families onto the pipeline skeleton

| step | what it decides |
|---|---|
| universe screen | which instruments are eligible at all |
| selection / ranking | which of them to hold, and in what order |
| entry | the condition and the moment of buying |
| holding / exit | how long, and what ends it |
| risk overlay | market filter, calendar blackout, stop |
| sizing | count, weights, participation |

For each step, name the candidate variant **and the §2 row that measures it**. §2 is where the
evidence lives — `data/components.tsv` is nearly empty. Read §1 (archetype), §2 (variants with
Δobjective), §6 (study log) and `realism:` on both pages.

⚠ Three things that only appear if you actually read §2, all found in the 小盘 round:

- a step can measure **net negative** — 小市值's 买一额/市值 ranking layer costs −0.1294 to keep,
  so dropping it is the cleanest free improvement in that universe;
- a step can be **arithmetically broken** — that same filter computes `a1_p * a1_v * 100` while
  JQ's `b1_v` is in shares, so its `> 5万` threshold is really `> 500` and nearly inert;
- an ablation can be **confounded** and say so — removing 小市值's 11:30 exit costs −1.9406 but
  changes two things at once (the only loss-cutting exit, and capital unlocked).

Also read the *other* family's rejected ideas. 多因子ML's `idea-imp-1` was rejected **without a
backtest** because tilting toward microcap would 「把本家族推成 小市值 的副本」 — a prior decision
against the very direction a careless merge would take.

## Step 4 — declare the candidate set, bounded, before running anything

**At most 3 candidates per (universe, epoch), named and justified in advance.**

Best-of-each over six steps from two families is up to 2⁶ combinations. Enumerating them and
keeping the winner is a search, and on TRAIN that is the multiple-comparisons failure this rule
exists to prevent. A sweep is not a candidate set.

Each candidate states: what it changes, from which family, and which measured row supports it.

## Step 5 — build and measure

One strategy file per candidate under `enhance/candidates/<expId>.py`, built from
`enhance/strategy_template.py` so it carries the frozen pins, then:

```bash
node utils/strategy-post-backtest.js enhance/candidates/<expId>.py "<expId>" --window train --usage-limit free
```

⚠ The executor does **not** inject the harness. A raw source with no pins is refused with
`UNPINNED-STOP` — build from the template.

⚠ **Never assemble a result from summed deltas.** A step's measured delta belongs to the pipeline
that produced it: "removing the 11:30 exit cost −1.9406" was measured at 小市值's holding period on
小市值's names. Predicted deltas may *rank* candidates; they may never stand in for a measurement.

One backtest at a time — the executor refuses a concurrent run with `CONCURRENT-STOP`.

## Step 6 — judge

```bash
node utils/type-integrate-check.js <candidate.json>
```

Under a merge the guard changes shape rather than relaxing:

| rule | status |
|---|---|
| 0. the stage gate (`sharpe >= 1.5`) | **binds** — necessary, never sufficient |
| 1. beat the best MEMBER, not the gate | **binds** — on the WORST TRAIN YEAR, see below |
| 2. diversification share | inert — there is no blend to attribute |
| 3. optimised vs equal weight | inert — there are no weights across books |
| 4. realizability at the WORST leg | **binds** |

Rule 4 is the one that bites: a merged candidate inherits the worse realism of its parents. If
either page declares its headline unrealizable (`不可实现`), say so in the verdict — the result is a
TRAIN comparison, not a tradeable claim.

### Rule 0 — check the gate BEFORE you build

⚠⚠ The guard used to skip it: on the ETF round-2 candidates it returned **KEEP** at sharpe 0.94
and 0.91 against a threshold of 1.5, because it applied rules 1–4 and never asked whether the
candidate cleared the gate. It now rejects on it. Do not rely on that fix to find out late.

**Before declaring a candidate set, check both parents with
`node -e "console.log(require('./utils/harness-config').stageGate('integrate', <sharpe>))"`.**
If *neither* parent clears 1.5, say so in your plan: the only way a merge of them becomes usable
is by clearing a bar neither parent reaches, which is exactly the pattern rule 2 treats as
risk-side rather than edge. That is a reason to report the ceiling, not to spend three backtests
discovering it. The guard flags this case as `all-parents-below-gate` — a warning, not a veto,
since a blend *can* mechanically exceed both parents when correlation < 1.

### The bar is the family CHAMPION, not the base you decomposed

⚠⚠ You build a merge by decomposing the **base** pipelines — that is correct, it is what has a
readable skeleton. You are judged against each family's **champion**, because rule 1 asks whether
the merge beats what the universe would otherwise ship, and a universe ships its best family's
champion (that is exactly what PROMOTE does).

ETF round 2 conflated them and ran against a bar 0.38 too low:

| family | base (supplied as the member) | champion (the actual bar) |
|---|---|---|
| ETF动量 | obj 0.1868, sharpe 1.41, worst year −0.0072 | obj **0.4725**, sharpe **2.23**, worst year **+0.3673** |
| 七星高照 | obj 0.1252, sharpe 1.21, worst year −0.0651 | obj **0.3365**, sharpe **2.54** |

Its candidates were reported as **+0.0274 uplift**; against the champions they lose by ~0.43.

The guard now derives the bar itself from the ledger and flags
`member-below-champion:<family>` if your `members[]` figure is lower. **You still supply the
member block** — its `realizability` is your reading of the family page and nothing else can
provide it — but put the champion's numbers and `sourceFile` in it, and say in your plan which
variant you decomposed if that differs.

### Rule 1 — PER-YEAR SHARPE DOMINATION (epoch 8)

**In EVERY TRAIN calendar year, your candidate's sharpe — computed *within* that year — must
exceed the highest sharpe any parent champion reaches in that SAME year.** Not the pooled
objective, and not a worst-year maximin (that was epoch 7 and is **invalidated**).
`harness/harness.md` §4.1 is the frozen definition; the guard applies it for you.

⚠ **The best parent can be a different family in each year**, so you may be up against a composite
no single parent achieves. That is deliberate under epoch 8 and strictly harder than beating any
one family. The guard flags `parents-split-by-year`. Measured example: 全A's 打板短线 champion runs
sharpe **2022 7.45 / 2023 −0.18** while 红利低频 runs **1.18 / 1.67** — so 全A's bar is "beat 7.45
in 2022 **and** 1.67 in 2023". Check this **before** declaring a candidate set: if one year's bar
is set by a book whose realism declares it unrealizable, say so in your plan rather than spending
three backtests on it.

⚠ **Check curve coverage before trusting the bar** — without one for the candidate *and every*
parent it drops to the pooled rule and flags `bar=pooled-fallback`.
Coverage was **11 of 11 champions** as of 2026-10-17. This line used to warn that four were
missing (七星高照, 五福闹新春, 大小盘轮动, 小市值) — those are the exact four that
`utils/series-rekey.js` recovered: their curves had been on disk the whole time under a hidden
`.._.._.._tmp_jq-normalize_<tag>` key that no reader could build and no `ls` would show.
⚠ **So do not read a zero-match backfill as "unrecoverable".** `node utils/series-backfill.js`
is free and is still the right first step for a NEW row, but it found zero matches for all four of
those and a re-run was started on that basis, costing ~23 backtest minutes for curves that already
existed. `ls -a data/series/` and `node utils/series-rekey.js --dry` come first.

Why you need to know rather than just read the verdict: **it changes which member you are up
against, often drastically.** In the 全A round the pooled leader 打板短线 scores 0.9668 while its
own worst year is **−0.3591** — so aiming at 0.9668 was aiming at a number that exists only
because of 2022.
⚠ The figures in that example are the **epoch-7** reading (worst-year objective, which put the
member to beat at 红利低频's 0.1224). Epoch 7's maximin is **invalidated** — under epoch 8 the bar
is per-year sharpe domination, so compute it from `integrateBar()` and never carry 0.1224 forward
as "the bar". The point the example makes survives the change intact: the pooled leader is usually
not the right target.

⚠ **The guard needs curves, or it silently falls back.** Put a `sourceFile` on the **candidate**
block as well as on **every** member — partial coverage also falls back, because a bar computed
over a subset omits whichever member might have set it. A fallback is reported as
`flags: bar=pooled-fallback`; if you see it, capture the curve and re-run before you believe the
verdict.

⚠ A candidate can now **lose on level and still win**, and the reverse. When the pooled
comparison disagrees with the per-year one the guard prints both and flags
`pooled-objective-lower` — **say in your verdict which one the round was after.** A merge of two
implementations of ONE edge is after consistency; a merge of two different edges is usually after
level.

## Step 7 — VAL, once

**One validation per (universe, epoch)** — check it with
`node utils/val-budget.js <universe> --type`.

⚠ **The `--type` flag is required.** Without it the CLI looks the name up in `wiki/families`
and answers `BLOCKED (unknown-family)` — which reads like "already spent" but means "wrong
keyspace". The 全A round reported the budget as unavailable for exactly this reason when it was
in fact `ALLOWED (first-of-epoch)`. Iterate on TRAIN; the winner must beat or equal the best input family there, and
again on the single VAL.

⚠ **A VAL failure is TERMINAL for that universe this epoch.** It does not license a fourth
candidate. "The last VAL disappointed, so build another" is selection on VAL one run at a time, and
after that the only clean surface left is the 2026 OOS reserve — nine months, two tests. Report it
and stop. Never set `JQ_ALLOW_REVAL`, and never reach OOS — not by passing `--allow-oos` (a CLI
flag since 2026-10-16, so the executor no longer refuses it on its own) nor by setting
`JQ_ALLOW_OOS` or its `_OVERBUDGET` / `_UNREADY` companions. OOS belongs to `/run-oos` alone.

## Step 8 — record, in the PROMOTED REGISTER

This is the step that makes the round mean anything: the register is what the next arrival meets.
A round that ends without writing to it has changed nothing, and the sequence IS the model.

```bash
# outcome 1 — no overlap: the arrival is promoted
node -e "require('./utils/promoted').record({universe:'<U>', action:'promote', \
  candidateId:'<arrival champion sourceFile>', kind:'family', members:['<family>'], \
  sharpe:<n>, objective:<n>, note:'no overlap with <incumbents> because …'})"

# outcome 2 — the merge won
node -e "require('./utils/promoted').record({universe:'<U>', action:'promote', \
  candidateId:'<expId>', kind:'merged', members:['<A>','<B>'], sharpe:<n>, objective:<n>, note:'…'})"
node -e "require('./utils/promoted').record({universe:'<U>', action:'supersede', \
  candidateId:'<incumbent candidateId>', note:'superseded by <expId>'})"

# outcome 3 — the merge failed: the incumbent STANDS, the ARRIVAL is rejected
node -e "require('./utils/promoted').record({universe:'<U>', action:'reject', \
  candidateId:'<arrival champion sourceFile>', note:'<why — required>'})"
```

⚠ A `reject` **requires a note** and is keyed to the **candidateId**, never the family: the spec is
"rejected until this family has a new best variant", and a new champion is automatically a new
candidateId and therefore a new attempt. Keying it to the family would retire a lineage on one
failed merge.

⚠ `epoch` is stamped from the live config and may not be passed — a caller that could choose it
could launder a stale promotion into the current bench.

Then, as before:

```bash
node -e "require('./utils/consumption').record({key:'<universe>',kind:'type',stage:'integrate',runId:'<expId>',outcome:'<verdict>',note:'…'})"
```

and append the round to `wiki/types/<universe>.md` under `## 整合回合`, which
`wiki-type-build.js` carries across verbatim. Record refusals and negative results too.

## Do not

- Blend two finished books and call it a merge. One strategy, one universe.
- Refuse a pair because the edges are identical — that is what makes the merge coherent.
- Build on a `proposed`, `refuted` or `supersededBy` edge claim.
- Sum deltas instead of measuring.
- Enumerate combinations and keep the winner.
- Re-derive the universe, eligibility, the arrival order or the promoted set — all deterministic.
- Refuse an arrival on realizability; it already cleared that gate at `/run-family`.
- Merge against anything other than the **highest-sharpe** overlapping incumbent.
- Reject the INCUMBENT when a merge fails. A failed merge leaves it untouched.
- End the round without writing the outcome to `utils/promoted.js`.
- Write a merge result onto a family page — it belongs to the type.
- Touch VAL during selection, or OOS at all.
