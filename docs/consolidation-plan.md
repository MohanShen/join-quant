# docs/consolidation-plan.md — closing the pipeline, and the type layer

Status: **proposal, nothing built**. Written 2026-09-19 against measured repo state.
Authority once accepted: this file for sequencing only. `harness/harness.md` (evaluation),
`screen/screen.md` (screening) and `docs/wiki-schema.md` (knowledge base) stay authoritative
for their own constants.

---

## 0. Where the pipeline actually stands

| Stage | State | Measured |
|---|---|---|
| discover → screen | connected | 857 of 2,647 posts screened |
| screen → fetch | connected | queue led by 40 fetch-now, 219 fetch |
| fetch → normalize | connected 2026-09-18 | 54 queued in priority order |
| normalize → wiki | **leaks** | 3 of 122 measured strategies have no page |
| wiki → study / enhance | **not connected** | no record of what has been consumed |
| validation → OOS | **absent** | 2 VAL runs ever, 0 OOS, no runner |

Two numbers frame everything below. **122** strategies are measured on the frozen harness.
**60** backtest-minutes exist per day, shared by every stage. Any plan that does not economise
that budget is not a plan.

---

## 1. The type layer — what it is and what it is not

### 1.1 The three levels, kept distinct

- **Strategy** — one `.py` in `strategies/`. Immutable raw layer.
- **Family** (`wiki/families/`, 14 pages) — a **lineage**: every variant descended from the same
  base code body. Has a `base:` pointer. 五福闹新春 is a family because twenty people forked one
  script.
- **Concept** (`wiki/concepts/`, 16 pages) — a **mechanism or theme** cutting across lineages:
  止损模块, 动量与趋势. Orthogonal to family by construction.
- **Type** (NEW, this plan) — a **coordinate**, not a page hierarchy: which market a family
  trades and how fast it turns over. Families sharing a type are candidates to be compared,
  merged or cross-pollinated.

> The 93 `NEW:<name>` strings screeners emitted are **not** 93 families. 15 agents invented names
> with no shared vocabulary; 85 appear exactly once and ≥21 are near-duplicates (four futures
> variants, three 风险平价, three 全天候). Most are **mechanisms**, so their destination is
> `wiki/concepts/` under the controlled vocabulary — not new family pages. One proposal was
> literally 仓位管理, an existing concept page.

### 1.2 The two axes

**Axis U — universe.** Works as proposed. Read from the base strategy's selection code, not
from prose. Proposed values:

`ETF` · `微盘` (bottom-decile market cap) · `小盘` · `宽基大盘` (HS300/SZ50/CSI500 constituents) ·
`可转债` · `期货` · `债券` · `混合` (two or more sleeves with no dominant one)

**Axis H — holding period / turnover. NOT "execution time".**

This is a correction to the original idea and it is evidence-driven. The 打板短线 study measured
the explicit `MarketOrderStyle(day_open)` argument as **bit-for-bit inert**: removing it changed
every metric by exactly 0.0000 across 484 trading days, including trade counts and the drawdown
window. On a daily-bar harness the labels 09:26 / 11:25 / 14:50 are **decoration**. Grouping on
execution time would group on something the bench cannot see.

Turnover is measured for every normalized strategy and ranges 0.0065 → 0.3061 across the 14
families, which separates the same groups intuition wants. Proposed bands:

| H | turnover (as reported by JQ) | rough meaning |
|---|---|---|
| `H-low` | < 0.03 | monthly / quarterly rebalance |
| `H-mid` | 0.03 – 0.12 | weekly-ish rotation |
| `H-high` | > 0.12 | daily rotation or faster |

**Intraday dependence does not disappear — it becomes a flag, not an axis.** A family whose
claimed edge needs auction or intraday fills carries `intraday-dependent: true`, which is a
*realizability* property (screen rubric axis R), and it already vetoes things there.

### 1.3 Deliverable

`wiki/types/<U>-<H>.md`, one page per occupied cell, generated not hand-written:

```yaml
---
type: ETF-Hmid
universe: ETF
horizon: H-mid
families: [[[ETF动量]], [[五福闹新春]], [[七星高照]]]
memberStrategies: 58
bestFamilyObjective: 0.4814
intradayDependent: false
updatedAt: 2026-09-19
---
```

Plus `utils/wiki-type-build.js` that derives membership from family frontmatter and the
normalize ledger, in the same spirit as `wiki-family-build.js` — and with the same data-loss
guard, which exists because a plain regenerate once blanked 13 family pages.

**Acceptance**: every one of the 14 families lands in exactly one cell; no cell holds all of
them; assignment is reproducible from code and ledger, with zero hand-written membership.

---

## 2. Consumption records — the gap you identified

Today **zero** strategy pages record whether they have been studied or enhanced. Family pages
carry `sources: { normalized, study, enhance }` and every page reads `study: 0, enhance: 0` —
including families studied to completion and the small-cap family that produced a validated
enhancement. The bookkeeping exists in form and is dead in practice.

### 2.1 One ledger, not a field

Add `data/consumption.tsv`, append-only, one row per (artifact, stage) event:

```
key	kind	stage	runId	at	outcome	note
<uniqueKey>	strategy	normalize	norm-2026-09-18	2026-09-18T…	normalized|compile-error|…	objective or reason
<family>	family	study	study-红利低频-q3	2026-08-30T…	finding|exhausted	findings.tsv row id
<family>	family	enhance	jul12-005	2026-07-12T…	val-pass|val-dq|abandoned	objective(VAL)
<type>	type	integrate	int-ETF-Hmid-001	…	…	…
```

Why a ledger and not a frontmatter field: it is append-only so concurrent agents cannot clobber
each other, it survives page regeneration, and it answers "what has never been touched" with one
scan. The same reasoning that made `harness/normalize-*.tsv` a ledger.

⚠ **Track it in git.** The normalize ledger was gitignored, silently regressed from ~119 rows to
18, and blocked every family page from regenerating until it was rebuilt from the wiki.

### 2.2 Derived queues

`utils/consumption-report.js` answers, with no judgement:

- normalized strategies never assigned to a family
- families with no study event, or with study events but no `exhausted`
- families with a best variant but no enhance event
- types with ≥2 families and no integrate event

These become the **inputs** to the loops, replacing "a human picks a family".

**Acceptance**: `node utils/consumption-report.js` prints the next candidate for each loop, and
the number it reports for study matches `study/manifest.json` (14 done) on day one.

---

## 3. Concept backfill — make the trigger real

Concepts are written today by `/ingest-strategy` and `wiki-factor-signature.js`. The study
analyst and enhance recorder are *instructed* to backfill concepts; in practice they write family
pages. The evidence: concept `strategyCount` has drifted by up to 7× (止损模块 claims 12, actual
83) and the last concept edit predates the last family edit.

Change: a study finding or enhance result that is **mechanism-level rather than lineage-level**
must append to the concept page, and the append is recorded in `data/consumption.tsv` as a
`concept-backfill` event. The analyst's hand-back must state which concept it touched, or state
that the finding is lineage-specific and why.

Add `utils/wiki-concept-lint.js`: recompute `strategyCount` from the pages that actually
reference each concept, report drift, and fail loudly rather than silently fixing — the counts
are also used in prose.

**Acceptance**: drift for every concept page under 5%, and every study/enhance run since the
change has either a concept event or an explicit lineage-only note.

---

## 4. The type-level integration round — and its guard

This is the new stage: take the families in one type and try to make them one better strategy.

### 4.1 The failure mode, from this repo's own measurements

Blending raises Sharpe mechanically whenever correlation is below one, and the gate **is** a
Sharpe threshold. Two families already record it:

- **七星高照** — the blend scored Sharpe 3.17 against 2.85 and 1.60 for its two legs, with
  volatility *below both*. It passes the gate at 0.4814; one leg alone is disqualified. The study
  flagged that the headline is carried by a small-cap leg, contradicting the family's own label.
- **红利低频** — a two-factor conjunction returned 23.41% against 11.75% for the sum of its legs,
  at lower risk.

A naive integration round would therefore produce gate passes at will, look like a triumph, and
add no edge.

### 4.2 The guard

1. **Beat the best member, not the gate.** A merged candidate is kept only if
   `objective(TRAIN) > max(objective(TRAIN))` over its type's members. Clearing 2.5 Sharpe is
   necessary and means nothing on its own.
2. **Declare the diversification share.** Report the merged Sharpe against the volatility-weighted
   blend of its members. If the entire improvement is explained by correlation, say so and do not
   count it as an edge. `七星高照` §2 is the worked example.
3. **Weights are a parameter, and parameters overfit.** Equal-weight first. Any optimised weight
   must beat equal-weight by more than the noise the repo already measured — re-running the same
   strategy shifts annual return by ~0.15pp, so treat sub-1pp differences as zero.
4. **Capacity is additive, edge is not.** Two microcap families merged still trade microcaps.
   Carry the worst realizability of any member, never the average.

### 4.3 Where it selects

**Training window only.** See §5.

---

## 5. Validation and out-of-sample — fixing the leak

### 5.1 The leak in the ladder as proposed

family → study → enhance (finalises on **VAL**) → type integration → **OOS**

If integration selects among VAL-validated variants, it is selecting on VAL, which makes VAL a
second training set. Everything downstream then rests on OOS, which is single-shot by design.

### 5.2 The rule

- **TRAIN (2022–2023)** — all selection, at every level: family, enhance, and type integration.
- **VAL (2024)** — one confirmation per finalised candidate. Never a selection input. Already the
  harness rule; the type round must not become an exception.
- **OOS (2025→today)** — confirmation of last resort, code-blocked, budgeted.

### 5.3 OOS protocol — the piece that does not exist

Nothing exists today: no runner, no ledger, no rule. Proposed:

- **A budget, written down.** At most **one OOS test per candidate, and at most 4 per epoch.**
  Record the count in `harness/oos-ledger.tsv` before the run, so the reserve cannot be spent by
  accident or by a loop.
- **Entry conditions, all required.** A candidate reaches OOS only with: a VAL confirmation that
  passes the gate; a realizability score that is not vetoed; and an explicit statement of what
  result would make it fail. Pre-registering the failure condition is what stops a bad number
  being reinterpreted afterwards.
- **Human-triggered only.** `JQ_ALLOW_OOS=1` stays user-only. No agent sets it, no loop reaches
  this stage, and the code guard stays exactly as it is.
- **Result is terminal.** An OOS result is recorded and the candidate is not re-tested with a
  tweak. That is the whole point of a reserve.

⚠ **There is nothing to test yet.** Two strategies have ever reached validation and one of them
failed. Build this stage last; built early it is mostly a way to burn the reserve.

---

## 6. Sequencing, and what blocks what

| # | Piece | Depends on | Cost | Why this order |
|---|---|---|---|---|
| 1 | Fix normalize → wiki leak | — | ~1h | 3 results already lost; silent and ongoing |
| 2 | Consumption ledger + report | 1 | ~half day | every later stage needs "what is untouched" |
| 3 | Type vocabulary + build script | 2 | ~half day | needs family membership to be trustworthy |
| 4 | Concept backfill + lint | 2 | ~half day | independent of 3; cheap; stops further drift |
| 5 | Type integration round | 3, 4 | multi-day | needs the guard in §4.2 built first |
| 6 | OOS protocol + ledger | 5 | ~half day | nothing to test until 5 produces candidates |

**Two throughput facts that gate all of it.** Normalization currently moves ~3 strategies a day:
the 2026-09-18 run spent 50 of 59 minutes on five timeouts that produced nothing and marked those
strategies permanently excluded. And every stage here draws on the same 60 minutes. Before
building §5, fix the slow-skip waste — lower the per-strategy cap, recover cancelled results via
the stats endpoint (the log records this as free and it is not implemented), and make slow-skip
retriable rather than terminal, because a timeout is not evidence about a strategy.

---

## 7. What this plan deliberately does not do

- **No new family pages for the 93 screener strings.** They are mechanisms; they belong in
  `wiki/concepts/` under the controlled vocabulary, registered before use (`wiki-schema.md` §9).
- **No change to `harness/harness.md`.** The type round runs on the existing frozen台. Changing
  the gate or the cost model is a new epoch and a separate decision.
- **No automation of OOS.** It stays human-triggered.
- **No merging of the family and concept vocabularies.** They stay orthogonal; type is a third,
  derived coordinate over families, not a replacement for either.
