# Proposal — merge auto-study and auto-enhance into one research loop

**Status**: proposal, nothing implemented. This is the contract to review *before* code moves.
**Authority it would change**: `docs/study-schema.md`, `docs/enhance-schema.md`, `docs/wiki-schema.md` §3.3.
**Authority it does NOT change**: `harness/harness.md` (frozen bench), `screen/screen.md`, the raw layers.

---

## 0. Why, in one paragraph

The two pipelines are the same machine with different acceptance rules: generator → gatekeeper/queue
→ enclosed executor → recorder, both writing §2 of the same family page, both calling
`utils/strategy-post-backtest.js` with the same frozen OVERRIDE, both keyed identically in
`data/consumption.tsv` (`stage / kind=family / key=<family>`). The duplication is already costing
correctness: the lock-trap bug had to be fixed in both loop scripts, and within one day of fixing
`autoenhance-loop.sh`'s resume nudge, `autostudy-loop.sh`'s copy still names a superseded epoch in
the OOS rule. Seven files carry stale epoch/gate literals.

But the reason to merge is not the plumbing. It is that **the two halves already depend on each
other one-way and cannot close the loop.** ETF溢价's entire enhance round rests on two *negative*
study findings (q-1, q-2). Nothing flows back: study never learns what enhance discovered, and
enhance has no principled prior about which changes are on-mechanism. Merging closes that.

---

## 1. The principle being rewritten — read this first

`docs/study-schema.md` §10 currently states:

> **无选择压力**：不 keep/discard、不挑「最优变体」当产物——产物是**理解**，不是新策略。
> （若解剖启发了值得优化的新策略，那是 auto-enhance 的活，另起。）

This proposal **deletes the parenthetical and keeps the sentence**, scoped to the understand-type
idea rather than to the pipeline:

> **无选择压力（按想法类型）**：`understand` 型实验**不**做 keep/discard——它的产物是理解，
> 负结果与正结果同等记录。`improve` 型实验做选择，但**其被否决的变体同样入账**（§3）。
> 选择压力属于想法的类型，不属于流水线。

Everything else in this document follows from that one change. If this sentence is wrong, stop here.

---

## 2. Change A — `edge:` , the intrinsic-factor contract

### 2.1 What exists today, and why it is not enough

`wiki-schema.md` §3.3 already has the slot, as free prose inside §1:

```
- **为什么有效**（essential driver, 溯源 [[studyId]]）：<本质驱动因子>
```

So the aspiration is not new. What is missing is that it is unstructured, unenforced, has no
falsification test, and no status — so nothing can read it and nothing notices when it is absent.
Measured state of the library:

| | count |
|---|---|
| concept pages that are `结构` (a technique: ETF轮动, 网格交易) | 9 |
| concept pages that are `机制` (a component: 止损模块, 仓位管理) | 4 |
| concept pages that are `因子族` (a source of return: 小市值因子) | **3** |
| family pages declaring **no concept at all** | **9** (incl. ETF动量, studied to exhaustion *and* enhanced) |

The wiki records what a family is made of and how it is assembled. It has never recorded why it
makes money.

### 2.2 The payoff, so this is not bookkeeping

Yesterday's epoch-6 `component-scan` shows **every candidate in every type has negative uplift** —
nothing improves any type leader. `CLAUDE.md` separately records that 57% of gate-passes are 小市值
variants and that 4 of 6 types are exhausted. These are one fact: the library is saturated in a
single factor.

Return correlation is a weak proxy for redundancy — two size books with different code decorrelate
on noise and look like diversification. **A shared intrinsic factor is the strong proxy.** Had
families carried an edge tag, that exhaustion was predictable without spending the backtest minutes
that discovered it empirically.

### 2.3 The contract

Added to family-page frontmatter. Structured, because integration has to read it:

```yaml
edge:
  - name: 规模因子                    # controlled vocabulary, see 2.4
    kind: risk-premium               # risk-premium | anomaly | arbitrage |
                                     # microstructure | information | none-found
    claim: "超额来自持有市值最小的一端，而非选股规则本身"
    test: "把 universe 按市值分五档、只在最大档内执行同一规则；若 edge 成立，超额应基本消失"
    status: proposed                 # proposed | measured | refuted
    evidence: [[study-q-7]]          # required once status != proposed
    factorlib: SIZE                  # optional: matching factor in research/factorlib/
```

Rules:

1. **`status: proposed` is the default and carries no authority.** It may not be cited as a fact,
   and integration must treat it as unknown. The repo has already paid once for a guess hardening
   into a rule — the title-keyword reject that permanently discarded 287 strategies.
2. **`test:` is mandatory at every status.** A claim with no stated refutation is not a claim. This
   is the same discipline `questions.json` already imposes with 可证伪.
3. **`kind: none-found` is a legal and valuable answer**, and a loud one: a family nobody can name
   an edge for is a fitting artifact until shown otherwise. It should be surfaced, not hidden —
   see the lint in 2.5.
4. **One or more entries.** Multiple edges are expected (小市值 + 日历效应). Each must stand alone
   as something fundamental; "uses a 5-day moving average" is a technique, not an edge.
5. **Prose stays.** The existing §1 `为什么有效` bullet remains as the human-readable form and must
   not contradict the block. Lint flags divergence; a human resolves it.

### 2.4 Vocabulary

`edge.name` joins the controlled vocabularies in `wiki-schema.md` §2.1/§2.2. It is **not** the same
axis as `concepts:` — concepts mix three things (9 结构 / 4 机制 / 3 因子族) and only the third is an
edge. Proposed seeding: promote the 3 existing `因子族` concepts, and register new names as study
answers them. Unregistered names are allowed at `status: proposed` only.

### 2.5 New check — `utils/edge-redundancy.js`

Two families sharing an `edge.name` at `status: measured` are integration-redundant **regardless of
return correlation**, and `type-integrate-check.js` gains this as a fifth rule alongside "beat the
best member". Also reports families at `none-found` and families with no `edge:` at all, so the
gap is visible rather than silent.

---

## 3. Change B — §2 变体 takes failures

`wiki-schema.md` §3.3 §2 table gains two columns:

```
| 变体 | 类型 | 相对基类的改动 | 来源 | Δobjective | Δsharpe | ΔmaxDD | 判定 | 结论 |
```

- **`类型`** = `understand` | `improve` — which generator produced it.
- **`判定`** = `adopted` | `rejected` | `informative` — `rejected` is a first-class outcome, not an
  omission. An `understand` row is normally `informative`; the word `rejected` is reserved for an
  `improve` variant that was measured and not kept.

**Row density is the real constraint, not row count.** ETF动量's §2 holds only 10 rows in a 186KB
page (the bulk is §6 at 60KB and §4 at 37KB) — so failures do not threaten the page. But those 10
rows average ~3.6KB each. A `rejected` row gets **one line**: change, Δ, and why it failed. The
long form is for variants that changed understanding.

---

## 4. Change C — one queue, two generators

`study/<family>/questions.json` and `enhance/ideas-queue.json` merge into one per-family queue.
Paths stay `study/<family>/` for now — renaming costs churn and buys nothing; see §8.

```json
{
  "id": "q-7",
  "kind": "understand",
  "title": "…",
  "hypothesis": "…",
  "why": "…",
  "design": "…",
  "from": ["q-2", "exp-004"],
  "edgeRef": "规模因子",
  "rank": 80,
  "status": "queued",
  "result": null
}
```

- **`kind`** routes to the generator and sets the acceptance rule (§1). `understand` ≈ today's
  questioner; `improve` ≈ today's ideator.
- **`improve` keeps all three of the ideator's modes** — within-family, cross-family borrow,
  new-family combination. Parameter sweeping is *one* mode, and the weakest: `CLAUDE.md` records
  that 4 of 6 types are exhausted because "recombining redundant things cannot fix redundancy",
  which is why `research/factorlib/` was wired in for orthogonal material. Narrowing `improve` to
  sweeps would re-create the problem the factorlib was added to solve.
- **`edgeRef`** ties the idea to an edge claim. This is the loop closing: once the edge is named,
  tightening the size threshold is *on-mechanism* and bolting on an unrelated momentum filter is
  *off-mechanism*. The edge claim becomes the improve-generator's prior. Nothing supplies that today.

---

## 5. Change D — record implications, and require generators to read them

This is the change that makes the two generators learn from what has already been run.

### 5.1 `findings.tsv` gains three columns

Append-only, so readers indexing 0..8 are unaffected — the same migration `consumption.tsv` already
did with `members`/`memberHash`.

```
qId  type  component_or_param  metric_delta  window  finding  confidence  flags  description
     ↑ existing 9 ─────────────────────────────────────────────────────────────────────────┘
  + implication   + spawned   + edgeRef
```

- **`finding`** (existing, col 6) = *what happened*. "sharpe 8.44 → 3.16 → 1.10 as the floor rises."
- **`implication`** (new) = *what it changes about what we do next*. Must either name a follow-up or
  explicitly close a direction. A restatement of `finding` is a schema violation.
  - closing: "no_buy_after_day is monotone-worsening upward from 2 — that knob is closed."
  - opening: "the 2e6 floor is too loose; retest every family member at 1e7 before trusting any Δ."
- **`spawned`** = ids this finding produced, or `none`. Makes the loop auditable: a high-confidence
  finding with `spawned: none` that nobody revisited is visible.
- **`edgeRef`** = which edge claim this bears on, or `-`. A result that refutes an edge claim must
  flip that claim's `status` to `refuted` in the same write.

### 5.2 The reciprocal obligation

A queue entry's **`from`** names the prior results that prompted it (§4). Together with `spawned`
these form a two-way link, and a lint can then ask the only question that matters: *is this idea
grounded in something we measured, or did someone just think of it?* An entry with empty `from` and
no §4 reference is ungrounded and ranks last.

Both generators are contractually required to read `findings.tsv` and the §2 `rejected` rows before
proposing. Today this is implicit — the agent happens to read them. Making it explicit is what stops
the round re-proposing a variant that was already measured and rejected, which is a real cost:
ETF动量's idea-1 was flagged in its own reasoning as "新颖度为零 — a carry-over re-measurement".

---

## 6. Change E — VAL becomes a terminal stage, with a budget

Per the merged loop: when both `understand` and `improve` queues are depleted for a family, the
round moves to VAL finalization. This is cleaner than today's parallel tracks and resolves the
window mismatch outright.

**But it needs a budget rule, or it quietly destroys VAL.** Today VAL is touched rarely — only
enhance finalization reaches it. Merged, *every* family ends with a VAL run, and families reopen
whenever new members arrive (`consumption.staleFor`). Repeated VAL exposure turns it into a second
training set, and `harness.md` exists to prevent exactly that. It is a one-way door: once VAL has
been selected against, the only clean surface left is the 2026 OOS reserve, which has a 2-test
budget for the whole epoch.

Proposed rule, enforced in code rather than prose:

1. **One VAL per (family, epoch).** Recorded as `stage: validate` in `data/consumption.tsv`, which
   already carries an epoch-aware key.
2. **Reopening a family does not re-authorize VAL** unless the finalized candidate itself changed.
   A new member arriving is not a new candidate.
3. **A refused VAL is reported, not silently skipped** — same discipline as `OOS-BLOCKED`.

---

## 7. What does NOT change

- **No renumbering.** There are **461** references to `§2` (excluding this document), 317 to `§3`, 164 to `§4`, 148 to `§6`
  across docs, agents and wiki. Inserting a section and shifting the rest invalidates ~1,200
  cross-references silently. `edge:` therefore goes in **frontmatter** (machine-readable, which is
  what integration needs) plus a prose subsection inside the existing §1. New columns are appended
  to existing tables, never inserted.
- **`harness/harness.md`** — untouched. Same bench, same costs, same windows, same epoch rules.
- **The raw layers** — `strategies/` and `resources/` stay immutable.
- **§3 横评** — still auto-generated by `wiki-family-build.js`; still never hand-written.
- **The enclosed executor** — still the only way to run a backtest.

---

## 8. Deferred on purpose

- **Directory/naming.** The merged loop needs a name, and `study/<family>/` no longer describes it.
  But `research/` is reserved in `CLAUDE.md` for a different pipeline, and renaming costs churn
  across hundreds of references for no functional gain. Proposed: keep paths, decide the name
  separately.
- **Collapsing the three schema files.** `study-schema.md` + `enhance-schema.md` → one document is
  the natural end state, but it should follow the contract change, not lead it.
- **The loop-script merge** (one `scripts/agent-loop.sh <stage>`, ~310 → ~130 lines). Mechanical,
  independent of this contract, and can land first or last.

---

## 9. Migration

| step | cost | note |
|---|---|---|
| Add `edge:` to the schema + lint | none | additive; absent = reported gap, not an error |
| Backfill `edge:` for 14 families | **0 backtests** for `proposed` | the claim is written from existing §1/§6 prose; `measured` requires an experiment |
| Add `类型`/`判定` columns to §2 | none | appended; existing rows default to `improve`/`adopted` for enhance rows, `understand`/`informative` for study rows |
| Add 3 columns to `findings.tsv` | none | append-only, proven pattern |
| Merge the two queues | none | both are gitignored working files |
| VAL budget check | none | reads `consumption.tsv`, which already has the data |

The only irreversible item is the §10 principle change in §1 of this document. Everything else is
additive and revertible.

---

## 10. Open questions for the human

1. **§1's principle rewrite** — is scoping 无选择压力 to the idea type, rather than to the pipeline,
   the right reading? Everything else follows from it.
2. **`edge.name` vocabulary** — promote the 3 existing `因子族` concepts and grow from there, or
   start a clean list? Growing risks inheriting the concept axis's conflation of technique and edge.
3. **VAL budget** — is one-per-(family, epoch) the right number? It is the only number in this
   document that cannot be revised after the fact, because VAL exposure is not undoable.
4. **`none-found`** — should a family sitting at `none-found` after a full study round be
   *deprecated* (excluded from enhance and integration), or merely flagged? The aggressive reading
   would retire a lot of the library.
