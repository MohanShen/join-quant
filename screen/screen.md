# screen/screen.md — frozen SCREENING rubric (authoritative)

The counterpart to `harness/harness.md`. That file freezes how a strategy is **measured**;
this one freezes how a community post is **judged before we spend anything on it**.

> **Epoch**: constants here are frozen. Any change = new epoch: bump `epoch` below, log one
> line in `wiki/log.md` (`screen | epoch <n> | <what changed>`), and **re-run the calibration
> set** (§7) — a rubric change that lowers calibration AUC is a regression, not an improvement.
> Screeners **read this file and never modify it**.

- **epoch**: 1
- **setAt**: 2026-09-17
- **note**: First rubric. Weights and anchors derived from a 104-post blind test against 23
  known harness outcomes (§7). Primary axis is **marginal information**, not pass-likelihood —
  see §1 for why.

---

## 1. What we are actually selecting for

The naive target is "will this pass the harness gate". **That target is wrong**, and the
evidence is in this repo:

- The two highest-objective strategies ever normalized (`objective` 3.595 / 3.542) are ETF
  discount books whose edge **collapses to Sharpe 1.09 the moment the universe moves to funds
  you could actually trade** (`wiki/families/PT多策略.md`, study-q-1). They pass. They are
  worthless.
- 57% of all gate-passes are 小市值 variants, and the library already holds **35** of them.
  The 36th teaches nothing, however well it scores.
- 16% of everything the fetch stage pulls is a **byte-identical duplicate** of something held.

So a screener optimizing pass-likelihood is optimizing for redundancy. The thing worth
protecting is the **60 backtest-minutes/day** and the analyst attention behind it, and the
return on those is *what we learn*, not *what scores*.

**Selection target: maximise information per backtest-minute.**

---

## 2. Hard rejects — decided in code, never by judgement

Applied by `utils/screen-prefilter.js` BEFORE a screener sees anything. A post hitting any of
these is dropped and never costs a token.

| # | Rule | Why |
|---|---|---|
| R1 | No 32-char `backtestId` **and** no notebook/attachment/research tag | nothing to run, nothing to read |
| R2 | Source SHA256 already in `data/content-hashes.json` | exact duplicate of a held strategy |
| R3 | `uniqueKey` already in `copy-queue.json.copied` | already fetched |
| R4 | Tagged `文章` + `函数` | platform API documentation, not a strategy |
| R5 | Title is empty | nothing to identify it by |

Everything surviving R1–R5 goes to judgement. **Do not re-litigate hard rejects in prose.**

> **A hard reject must be something already KNOWN, never a guess.** Epoch 1 briefly had an R5
> that dropped titles containing no "mechanism token". Measured against the corpus it discarded
> **287 of 549** strategies, including 五福 / 三马 / 七星 variants — a held family with 20 members
> and 4 gate-passes — because this community names mechanisms after family lineages rather than
> techniques. A post that looks vague costs ~460 tokens to screen properly; one wrongly dropped
> here is invisible and permanent. The keyword match survives as a `mechanismHint` field the
> screener may weigh, not as a filter.

Measured on the current corpus: **587 pooled → 391 survive**, almost all drops being R3
(already fetched).

---

## 3. The four axes

Each scored **0–5 integer**. Anchors are behavioural, not vibes — quote the evidence that
put it at that level. If two anchors both fit, take the **lower**.

### M — Marginal information (PRIMARY)

*What would we know after running this that we do not know now?*

| M | Anchor |
|---|---|
| 5 | A mechanism with **no** representative among the 14 families, or a **falsifying / negative result** about a family we hold (a debunk, a lookahead-bias dissection, a documented failure with evidence) |
| 4 | A family we hold but a genuinely different mechanism inside it (new signal, new risk control), or a cross-family combination not yet tried |
| 3 | A parameter or universe variation on a held family whose direction we have **not** already measured |
| 2 | A variation whose direction the family page's §2 already records |
| 1 | Another member of a family with ≥20 held members (小市值 35, ETF动量 27, 打板短线 25, 多因子ML 20, 五福闹新春 20) with no stated difference |
| 0 | Restating a held strategy; a "my results" diary; a fork with only cosmetic edits |

> Held families and their counts are in `wiki/families/*.md` frontmatter (`memberCount`).
> **Read them before scoring M.** M is the only axis where being popular is irrelevant.

### S — Survivability on the frozen harness

*Would it plausibly clear `sharpe ≥ 2.5` on 2022-01-01→2023-12-31?*

Base rate is **22%** — most posts fail. Calibrate to that; do not hand out 4s and 5s freely.

| S | Anchor |
|---|---|
| 5 | Mechanism is a known survivor in this exact regime AND the author reports in-window numbers consistent with it |
| 4 | Plausible survivor; author reports drawdown and win rate, not just return |
| 3 | Could go either way; mechanism is sound but the evidence offered is out-of-window or thin |
| 2 | Probably fails: depends on a bull tape, or on intraday precision a daily-bar harness destroys |
| 1 | Almost certainly fails: teaching example, no risk control, or claims rest on a decade that excludes 2022–23 |
| 0 | Cannot run (Python 2, futures-only, missing data dependency) |

> Two regime facts, frozen because they decided the last blind test:
> (a) 2022–23 was the **peak** A-share micro/small-cap rotation window — small-cap strategies
> are the natural survivors here and that is a **window artifact**, not proof of edge;
> (b) the harness runs **zero slippage**, which *flatters* high turnover. A strategy that only
> survives because of (a) or (b) scores high on S and **low on R**.

### R — Realizability

*If it passes, could you actually trade it?* This is the axis that catches the discount books.

| R | Anchor |
|---|---|
| 5 | Liquid universe, low turnover (monthly/weekly), capacity well beyond ¥1M |
| 4 | Liquid universe, moderate turnover |
| 3 | Some friction risk: microcap names, or daily rebalancing of a liquid book |
| 2 | High turnover **on** thin names; real costs would bite hard |
| 1 | Edge is **constructed from** illiquidity (volume-band filters that select the thinnest instruments), or from fills a daily bar cannot honour (auction prices, intraday stops) |
| 0 | Edge requires trades that are not executable at all (sealed limit-up boards, stale NAV prints) |

> **R is a veto, not a weight.** `R ≤ 1` caps the final priority at 2 regardless of the other
> axes. That is exactly the rule that would have demoted `objective` 3.595 to the bottom.

### H — Reporting honesty

*Is the author reporting or selling?* Measured signal, not moralising: of 14 posts stating an
annual return in the title, **11 measured below their claim**, median gap **−8.9pp**.

| H | Anchor |
|---|---|
| 5 | States return **and** drawdown **and** a caveat/limitation in their own words |
| 4 | States return and drawdown; numbers are specific |
| 3 | States a specific number, nothing about risk |
| 2 | Vague claims; no numbers, or numbers with no window |
| 1 | Claims a **multiple** (`N倍`) or an annual return **>500%** — every such post measured in this repo collapsed (1602%→9.1%, 42%→−57.2%) |
| 0 | Hype vocabulary (`绝无未来函数`, `狂飙`, `最强`, `秘密`, `暴利`) — protesting-too-much is anti-predictive: the "absolutely no lookahead" post claiming 1700× measured 35.9% and failed |

---

## 4. Priority — how the axes combine

```
priority = 3*M + 2*S + 2*R + 1*H          # 0..40
if R <= 1:  priority = min(priority, 2)   # realizability veto (§3 R)
if M == 0:  priority = min(priority, 3)   # nothing to learn        -> drop
if M == 1:  priority = min(priority, 17)  # nothing NEW to learn    -> hold, never fetch
```

M carries the heaviest weight **on purpose**: S and R are guesses about a number we can just
go and measure, while M is the thing a backtest can never tell us.

**The M ladder, not the weight, is what makes M primary.** Weighting alone is not enough:
without the `M == 1` cap, a post scoring `M=1, S=5, R=5, H=5` reaches **28 = fetch-now** — the
36th variant of a 35-member family jumping the queue on the strength of the two axes we could
simply have measured. The ladder makes redundancy a ceiling, not a penalty.

**Bands** (the only thing downstream consumes):

| priority | band | action |
|---|---|---|
| ≥ 28 | `fetch-now` | queue ahead of everything |
| 18–27 | `fetch` | normal queue, ranked by priority |
| 8–17 | `hold` | keep the metadata; do not spend backtest minutes |
| ≤ 7 | `drop` | record the verdict so it is never re-screened |

---

## 5. Output contract

One JSON object per post. **Every field required**; no prose outside it.

```json
{
  "key": "<uniqueKey>",
  "M": 4, "S": 3, "R": 4, "H": 5,
  "priority": 31,
  "band": "fetch-now",
  "family": "<one of the 14, or NEW:<short name>, or UNKNOWN>",
  "mechanism": "<= 12 words, what it actually does",
  "why": "<= 25 words, the evidence that set M and the binding constraint>",
  "flags": ["zero-slippage-flattered", "thin-universe", "regime-2022-23-only"]
}
```

- `priority` must equal the §4 formula applied to the four scores. A mismatch is a bug.
- `flags` is free-form but prefer reusing values already seen in `wiki/families/*.md` frontmatter
  `realism:` strings, so screening vocabulary and KB vocabulary stay the same.

---

## 6. Screener conduct

1. **Read the post body, not just the title.** Bodies are free (`community/post/detailV2`),
   median ~460 tokens. Title-only screening scores ~0.75 AUC; body screening scored **0.90**.
2. **Mine the corpus against itself.** Authors routinely publish their own parameter studies
   and admissions ("Sharpe drops to 1.76 once the lookahead is removed"). That is the single
   highest-quality evidence available at screening time — quote it in `why`.
3. **Never assume popularity implies quality.** Measured: the four most-cloned posts in the
   corpus all fail; the two best strategies have 24 and 20 likes. Clones are a weak tiebreaker
   at best and must never move M.
4. **State the binding constraint.** If S is high only because of the window or zero slippage,
   say so in `flags`, and let R take the hit.
5. **Score independently, in the order M → S → R → H.** Do not let a high S pull M up; that is
   the failure mode that fills the queue with the 36th small-cap variant.
6. **No backtests.** Screening is judgement over text. Measuring is `harness/harness.md`'s job.

---

## 7. Calibration — required before trusting a rubric change

`screen/calibration/` holds **104 posts with sealed harness outcomes** (23 pass / 81 fail,
base rate 22.1%). It is the screener's equivalent of a held-out set.

```bash
node utils/screen-score.js <predictions.json>     # precision@K + AUC vs the sealed key
```

Epoch-1 reference numbers, from a blind run of this corpus:

| ranker | top-5 | top-10 | top-20 | AUC |
|---|---|---|---|---|
| popularity (`likes + clones×0.5`) | 20% | 30% | 35% | 0.66 |
| "title says 小市值" alone | 80% | 90% | 65% | 0.75 |
| regex ranker (tuned on this set) | 100% | 60% | 50% | 0.82 |
| **LLM judgement, blind** | **100%** | **90%** | **80%** | **0.90** |

⚠ **The calibration set grades pass-likelihood (S), not M.** It cannot validate the primary
axis, because "what would we have learned" has no recorded ground truth. Treat a good AUC as
evidence the screener understands the *market*, not that it is ranking by the right thing.
Guard M separately: if a screening batch's `fetch-now` band is >50% one family, that is a
rubric failure regardless of AUC.

Known blind spots of epoch 1, from the same run — a screener should weigh these:

- It scored the top-objective discount book **10/100** (predicted fail; it passed). On S that
  is an error; on R and on the selection target it was right. §4's veto encodes that lesson.
- It missed three 五福 family passes by committing to a structural thesis about the family.
  **A confident family-level prior is the most expensive mistake available** — apply it to M
  (redundancy is knowable) and not to S (outcomes are not).

---

## 8. Changing this file

1. Edit the constant. 2. Bump `epoch`, update `setAt`/`note`. 3. Append to `wiki/log.md`.
4. Re-run §7 calibration and record the new table. 5. Prior screening verdicts are sealed to
   their epoch and are not comparable across epochs.
