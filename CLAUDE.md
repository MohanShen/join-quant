# CLAUDE.md

## Overview

**join-quant** is an automated pipeline for the [JoinQuant](https://www.joinquant.com) Chinese quant platform. It discovers community strategies, clones their source + performance metrics, and runs backtests — both for community posts and for local custom strategy files. Node.js (>=18), Playwright for browser automation, raw HTTP for the API paths.

## Setup & Commands

```bash
npm install          # installs playwright
npm test             # node --test tests/*.test.js

# CLI (see index.js)
node index.js community <postId> <backtestId> [replyId]  # backtest a community post
node index.js custom <path-to-strategy.py>               # backtest a local file
node index.js custom --backtestId <id>                   # re-run existing backtest
node index.js list                                       # list local ./strategies/
node index.js login                                      # force fresh login, cache cookies
node index.js status                                     # show cached cookie status

# Pipeline 1 (discovery/clone) entry points — not wired into index.js
node utils/strategy-discover.js            # crawl community listV2, build queue
node utils/strategy-fetch.js [N]           # process clone queue (optional limit)
node utils/strategy-daily.js               # cron: discover -> clone loop
node utils/strategy-daily.js --discover-only

# Discovery knobs (Pipeline 1)
node utils/strategy-discover.js --pages 20            # walk 20 pages per (cate,type) combo
node utils/strategy-discover.js --pages 50 --limit 50 --cates 3,0
node utils/strategy-discover.js status                # strategy + resource queue status

# Research resources (community write-ups the strategy pipeline drops)
node utils/resource-fetch.js                          # drain the resource queue
node utils/resource-fetch.js 10 --kind notebook       # N of one kind
node utils/resource-fetch.js --dry

# Factor library (research input)
node utils/factorlib-ingest.js                        # zz500 / 3y, both cost levels
node utils/factorlib-ingest.js --universe zz1000 --range 1y
node utils/factorlib-ingest.js --list-settings        # legal universe/range/fee values

# 量化课堂 (137 lessons)
node utils/tutorial-ingest.js                         # catalog + all bodies
node utils/tutorial-ingest.js --catalog               # catalog only

# One-off: re-key the stores from postId to uniqueKey (idempotent, backs up)
node utils/migrate-unique-key.js --dry

# Screening — decide what deserves the 60 backtest-min/day (see screen/screen.md)
node utils/screen-prefilter.js --stats        # deterministic hard rejects, no tokens
node utils/screen-prefilter.js --limit 200    # + fetch bodies -> screen/candidates.json
node utils/screen-score.js <predictions.json> # grade a screener vs the sealed 104-post set
node utils/screen-prefilter.js --limit 200 --sample 42 --cates 14,3   # seeded, 精华+文章 first
node utils/screen-merge.js                    # validate batch verdicts -> screen/verdicts.json, rebuild queues
node -e "console.log(require('./utils/post-cache').size())"   # cached post bodies
node utils/normalize-backfill.js --dry        # queue held-but-unmeasured strategies by screening priority
node utils/normalize-sync.js                  # reconcile wiki pages + pending queue against the ledger
node utils/harness-config.js                  # print the active harness epoch
node utils/harness-config.js --verify         # check the frozen Python literals match it
node utils/consumption-report.js --next       # what each loop should take next
node utils/wiki-type-build.js --check         # family -> type assignment (universe x turnover)
node utils/wiki-concept-lint.js               # concept strategyCount drift
node utils/type-integrate-check.js <c.json>   # guard on a type-level integration candidate

# Return series + component harvesting (inputs to type-level integration)
node utils/series-backfill.js --scan          # index every backtest the JQ account still holds (free)
node utils/series-backfill.js --dry           # match those curves to ledger rows, write nothing
node utils/series-backfill.js                 # + save the matched curves to data/series/
node utils/backtest-series.js --list          # stored curves
node utils/backtest-series.js --corr <a> <b>  # correlation of two stored curves
node utils/component-scan.js --validate       # series-derived metrics vs the ledger they belong to
node utils/component-scan.js                  # rank ingredients per strategy type
node utils/components.js                      # the component register
node utils/components.js --add --source <f> --aspect <a> --kind exit --claim <c> --evidence <e>
node utils/strategy-normalize.js --window train --files "$(node -e "console.log(require('fs').readFileSync('data/pending-normalize.json','utf8').match(/[^\"\[\],\s]+\.py/g).join(','))")" --usage-limit 55
```

### Chrome / auth setup (required for Pipeline 2)

Pipeline 2 connects to an already-logged-in Chrome over CDP to inherit `httpOnly`
session cookies and bypass JoinQuant's CAPTCHA. **Where that Chrome runs is
configurable** — `config/exec.env` (gitignored; template at `config/exec.env.example`):

```bash
JQ_EXEC_MODE=local     # or: remote
```

**local mode** — Chrome on this machine. Start it once and keep it running:

```bash
nohup /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9225 \
  --user-data-dir=/tmp/jq-auth-browser \
  > /tmp/chrome-jq.log 2>&1 &
# First run: log into joinquant.com manually. Closing Chrome invalidates the session.
```

**remote mode** — Chrome runs on the Windows QMT server (see the `QMT-server` repo).
Its debug port is bound to the server's `127.0.0.1`, so an **SSH tunnel** bridges it:

```
localhost:9225  ->  ssh  ->  server 127.0.0.1:9225
```

The tunnel opens **automatically** — `utils/exec-config.js` probes the CDP endpoint on
every entry point and runs `scripts/cdp-tunnel.sh up` if nothing answers. Manual control:

```bash
./scripts/cdp-tunnel.sh up|down|status
```

Because the tunnel presents the browser at `localhost:9225`, every existing
`connectOverCDP('http://localhost:9225')` call works unchanged in both modes. This
also keeps Chrome's Host-header check happy (it rejects non-localhost `Host` values)
and avoids exposing the debug port — CDP on a logged-in brokerage session is a full
remote-control channel and must never be opened to the network.

In **remote mode the local-browser fallback is disabled**: the logged-in session lives
in the server's Chrome profile, so launching a browser on the Mac would only hit the
login page + CAPTCHA. `strategy-post-backtest.js` fails loudly instead.

Environment variables (optional — CDP path needs no credentials):
`JOINQUANT_USERNAME`, `JOINQUANT_PASSWORD`. `JQ_CDP_URL` still overrides the resolved
URL outright; `JQ_EXEC_MODE`, `JQ_CDP_PORT`, `JQ_REMOTE_SSH_HOST`, `JQ_REMOTE_SSH_OPTS`,
`JQ_REMOTE_CDP_PORT` override `config/exec.env` per-invocation.

## Two Pipelines

**Pipeline 1 — Daily Discovery & Clone** (`pipelines/community.js`, `utils/strategy-*.js`):
`GET /community/post/listV2` (paginated) lists community posts → split into **strategies**
(32-char `backtestId`) and **resources** (Jupyter `notebookPath`, `fileKey` attachment, or a
研报分享 / 研报复现 / 研究 tag) → dedupe against `data/discovered.json` + `data/resources.json`
→ for each strategy: `GET /algorithm/backtest/source` (Python source) +
`POST /algorithm/backtest/stats` (metrics) → save `.py` to `strategies/` → WeChat alert.
Both queues ranked by composite score (strategies: `likes + clones × 0.5`).

> ⚠ **All HTTP goes through `utils/jq-http.js`, never raw `https.get`/`curl`.** JoinQuant
> geo-blocks requests from outside mainland China with an **HTTP 200 HTML** page
> (「当前地区暂不支持访问」), so a raw call parses as a JSON error and older code read that
> as "no results" — Pipeline 1 died silently this way for two months. `jq-http` runs
> `fetch()` **inside the CDP Chrome** (right region + logged-in cookies), falls back to
> direct https only when CDP is down, and **throws** `GeoBlockedError` rather than
> returning an empty list. Never reintroduce a direct HTTP call to joinquant.com.

`listV2` pagination is deep: `page=800` at `limit=50` still returns a full page, reaching
back to 2019. Use `--pages N`; the crawler stops a combo after **5 consecutive** pages that add
nothing new. It used to stop after the *first* such page, which silently truncated sparse
categories — `cate=10` yielded 7 posts out of ~17,300 because its pages carry only 4–6
qualifying posts each, so one page of already-known items ended the sweep.

**`cate` = the forum's tabs** (read off the live site 2026-09-17; the tabs are disjoint and
`cate=0` is the superset):

| cate | tab | size | note |
|---|---|---|---|
| 0 | (none) | 60,000+ | superset; held 50/51 of `cate=3`'s page 1 |
| 3 | 文章 | ~42,300 | ordinary articles — the site default, and **the only slice the crawler used** |
| 10 | 问答 | ~17,300 | Q&A — where debunking and pitfall discussion lives |
| 13 | 公告 | small | platform announcements |
| 14 | 精华 | ~350 | editorially featured; page 1 was 50/50 `isBest`, median likes 125 vs 5 |

⚠ `strategy-discover.js` used to describe `cate=3` as 精华. **It is not** — 精华 is `cate=14`,
which had never been crawled.

**Pipeline 2 — Custom Strategy Backtest** (`pipelines/custom.js`, `backtest/runner.js`):
Browser-automated via CDP. Create `algorithmId` → inject Python into JQ's **Ace editor**
(`window.ace.edit(div).setValue(...)`, also synced to hidden `<textarea id="code">` which
the backend reads on save) → click 保存 / 编译运行 → **reload-poll** the buildList every 5s
for `完成` → scrape the result table for return/drawdown/Alpha/Beta/Sharpe.

> Why CDP, not a Playwright launch? JQ stores `PHPSESSID`/`token` as `httpOnly` cookies that
> Playwright can't set, and headless browsers hit the 拼图验证 CAPTCHA. CDP reuses the real session.
> Why reload-polling? JQ mutates backtest status in-place via XHR; a static `goto` misses updates.

## Layout

Only the directories whose contents aren't self-evident:

| Path | Purpose |
|------|---------|
| `harness/` | **Shared frozen backtest台**: `harness.md` (window/cost/OOS protocol, read-only) + `normalize-*.tsv` ledgers (gitignored). Used by study + enhance + future research. |
| `enhance/` | Auto-**enhance** team (optimize a strategy FAMILY): `program.md`, `candidates/`, `strategy_template.py`, transient `ideas-queue.json`/`loop-state.json`/`results.tsv` (gitignored) |
| `study/` | Auto-study team (understand a strategy FAMILY): `program.md`, `<family>/baseline.py` + `variants/`, transient `questions.json`/`findings.tsv` (gitignored). Writes back to `wiki/families/`. |
| `wiki/types/` | **Strategy TYPES** — generated by `utils/wiki-type-build.js`. A coordinate over families: universe (from the base source) x turnover band. Families sharing a type are integration candidates. Not a third page hierarchy; family and concept stay orthogonal. |
| `screen/` | **Frozen SCREENING rubric** — `screen.md` (four axes, priority formula, bands; read-only, epoch-versioned like `harness.md`) + `calibration/` (104 posts with sealed harness outcomes, the screener's held-out set). Decides what is worth fetching BEFORE backtest budget is spent. |
| `research/` | Reserved for a future auto-**research** pipeline — broad context: new data / factors / trading ideas. NOT the current optimize loop (that is `enhance/`). Holds `factorlib/` (below). |
| `research/factorlib/` | JQ **因子看板** ingested by `utils/factorlib-ingest.js`: 285 factors with formulas, IC/IR, quintile returns and turnover, pulled at **both** cost levels. `factors.tsv` + generated `README.md` (tracked); raw payloads in `data/factorlib/`. |
| `research/tutorials/` | **量化课堂**, 137 lessons in 5 categories, ingested by `utils/tutorial-ingest.js` via `detailV2` (free). Category 新手专区 is a full factor-research methodology chain. |
| `resources/` | **Raw layer #2** (alongside `strategies/`): community RESEARCH write-ups as `.md`, fetched by `utils/resource-fetch.js`. One file per post, frontmatter + full body. Notebook/attachment availability is recorded but the notebook itself is **not** downloadable (see Notes). |
| `validated_strategies/` | Finalized strategies that completed VAL (Agent 4 archives here; **tracked** = product shelf) |
| `data/` | **Tracked** (private backup) — discovery + resource state, `factorlib/` raw payloads. Only `data/cookies.json` is gitignored. |
| `auth/` | Session cookies; `auth/cookies.json` itself is **gitignored** (default cookie path). |

## Notes & Gotchas

- `data/` and `auth/` are **tracked** (private backup); only `data/cookies.json` and
  `auth/cookies.json` are gitignored. Never commit a cookie file.
- Default cookie path in `index.js` is `auth/cookies.json`.
- **Never call joinquant.com with raw `https`/`curl`** — use `utils/jq-http.js`. See the
  geo-block note under Pipeline 1.
- ⚠⚠ **JoinQuant re-mints IDs on every request.** `postId`, `backtestId`, the factor
  dashboard's `factor_id` and the tutorial list's `studyId` are all regenerated per call —
  the same object comes back under a new id each time, and old ids still dereference, so
  nothing fails loudly. **Stable handles**: community post = `uniqueKey`; factor = `name`;
  tutorial lesson = `title`. Never key a store, a dedup or a join on an id.
  This is why `data/discovered.json` was 10% duplicates and the `copied` map never matched
  (fixed by `utils/migrate-unique-key.js`; `postKey()` in strategy-discover.js is the rule).
- Community **notebooks cannot be downloaded** — the post page only offers 克隆研究, which
  copies into your research environment and **spends 积分 (credits)**; stored `notebookReport`
  paths 302 to 404 on old posts. `resource-fetch.js` saves the free prose and records the
  notebook as unavailable. The account currently holds **2 credits** and no VIP.
- The factor dashboard defaults to `commisionFee=0` (no costs), the same blind spot as
  `harness.md` §2. At `commisionFee=18` only **6 of 285** factors keep a positive excess
  annual return, down from 23 — and every survivor is low-turnover.
- `harness/normalize-*.tsv` is the input to `wiki-family-build.js` (family §3 tables +
  `memberCount`/`bestVariant`). It is **gitignored and has regressed before** — it once fell
  from ~119 normalized rows to 18, which blocked every family page from regenerating.
  The durable copy is the `normalized: { … }` block `kb-stub.js` stamps into each
  `wiki/strategies/*.md`; `node utils/normalize-ledger-rebuild.js` reconstructs the ledger
  from those pages with no backtest cost. Reconstructed rows leave `total_pct` empty (the
  wiki does not store it) — that is how you tell them from measured rows.
- Re-running the same strategy through normalize can shift `annual_pct` by ~0.15pp
  (e.g. −25.87 vs −26.02 for the same file). Measured rows win over reconstructed ones.
- **Screening ranks on MARGINAL information, not pass-likelihood.** Measured on this corpus:
  the 4 most-cloned posts all fail the gate; 57% of gate-passes are 小市值 variants of a family
  that already holds 35; the top-objective strategy (3.595) is an ETF-discount book that dies
  under mild friction. Popularity selects for redundancy. See `screen/screen.md` §1.
- A screener's **hard reject must be a known fact, never a guess**. An early rule dropping
  "titles with no mechanism keyword" discarded 287 of 549 strategies including a held family
  with 4 gate-passes. Vague-looking posts cost ~460 tokens to screen; wrong drops are permanent.
- **问答 (cate=10) is mostly help-desk traffic**: first 200-post screen dropped 94% of Q&A posts vs
  24–30% of 文章/精华. Help-desk posts attach backtests to ask about them, so no payload rule
  catches them. Stored rows now carry `cate`; screen with `--cates 14,3` first. Q&A is
  deferred, not rejected — it still yielded the O'Neil pocket-pivot idea.
- Full 精华+文章 screen (793 posts): fetch-now 50 / fetch 256 / hold 183 / drop 304. The
  fetch-now band spans **25 families, largest 12%** — axis M is doing its job. Screeners
  proposed **71 NEW mechanism families** in the fetch band (all-weather / risk parity, macro
  timing, northbound flow, accrual factors, overnight-gap, commodity cross-section, bonds);
  these are candidate `wiki/families/` pages, not yet registered.
- ⚠ **The fetch band mixes "read this" with "backtest this".** Many top picks score S=0: they
  are write-ups, futures-only, or need data outside 2022–23. Bands rank information, not
  runnability — check `flags` before spending backtest minutes. Candidate fix for a future
  rubric epoch.
- **Never re-request a post body.** `utils/post-cache.js` (`data/post-bodies.json`) caches the
  whole `detailV2` payload keyed by `uniqueKey`, shared by `screen-prefilter.js` and
  `resource-fetch.js`. Post text is immutable, so entries never expire by default. Before it
  existed, re-running the prefilter re-fetched every unscreened candidate and a post that was
  both screened and ingested was fetched twice — thousands of avoidable requests at ~2,600 posts.
- **Screening and normalization are connected through `data/pending-normalize.json`.**
  `utils/normalize-backfill.js` writes the held-but-never-measured strategies into it in
  screening-priority order; `normalize-daily.js` drains it and appends each day's new fetches.
  `strategy-normalize.js --files` preserves the CALLER'S order (it used to re-sort by directory
  listing, which silently discarded the priority). Screening already-fetched posts needs
  `screen-prefilter.js --keys <file>`, because R3 (already fetched) is the right rule for
  "should we download this" and the wrong one for "which file we hold deserves backtest minutes".
- The backfill EXCLUDES S=0 files (harness cannot produce a valid result) and DEFERS files a
  screener flagged as multi-hour — the normalizer's slow-skip cap cancels at 20 min, so one
  such file burns a third of the daily budget to learn nothing.
- **`data/consumption.tsv` records what each stage has consumed** (append-only, tracked). Before
  it, nothing knew which strategies or families had been studied or enhanced — every family page
  read `study: 0, enhance: 0` including families studied to exhaustion. `consumption-report.js`
  turns it into the loops' input queues. Enhance events are keyed by FAMILY, not session tag.
- **Bookkeeping belongs to the step that owns it, not to one caller.** Wiki-stub creation and
  pending-queue pruning lived only in `normalize-daily.js`, so a direct normalizer run silently
  skipped both (3 measured strategies had a ledger row and no page; the queue was stale by 11).
  `utils/normalize-sync.js` derives both from the ledger and runs at the end of every batch.
- **Type-level merging needs the guard in `utils/type-integrate-check.js`.** Blending raises
  Sharpe mechanically whenever correlation < 1 and the gate IS a Sharpe threshold — 七星高照's
  blend scores sharpe 3.17 against legs of 2.85/1.60 and still loses to its own small-cap leg
  (0.4814 vs 0.5984). Beat the best MEMBER, not the gate.
- **The ledger stores scalars, which cannot rank INGREDIENTS.** A sleeve scoring 0.1 that is
  uncorrelated with a type's leader can beat one scoring 0.8 that moves with it — correlation is
  not a function of annual/sharpe/maxdd, so filtering integration candidates by standalone score
  discards exactly the diversifying material integration exists to exploit. `utils/backtest-series.js`
  captures the DAILY CURVE of every completed run from the undocumented
  `GET /algorithm/backtest/result?backtestId=&offset=&userRecordOffset=&ajax=1` (found by sniffing
  the summary page; it pages 1000 points at a time, `data.result.overallReturn = {time,value}`).
  This is the missing input `type-integrate-check.js` documented as uncomputable — rule 2 is now a
  real decomposition when curves exist, and falls back to the old signature test when they do not.
- ⚠ `overallReturn.value` is **cumulative percent, not a daily return and not a price**. Chain it
  `(1+cₜ/100)/(1+cₜ₋₁/100)−1`; **differencing the percentages reports vol 1.3620 where JQ reports
  0.2271** — a 6× error that looks plausible in isolation. Only `dailyReturns()` does this conversion.
  Validated: a curve-derived max drawdown of 0.3302 against JQ's own 0.33022.
- ⚠ **Annualize a curve over the ROW's day count, not the curve's own span.** The ledger annualizes
  over the REQUESTED window (a uniform 729 days on every TRAIN row); a curve spans the trading days
  that actually occurred (2022-01-04..2023-12-29, 724). Self-annualizing each side put the same run
  at 34.06 against the row's 33.79 and matched **0 of 124 rows**. `total_pct` agrees exactly.
- `utils/series-backfill.js` gives the EXISTING ledger curves at **zero backtest cost** — the account
  retains 1,133 algorithms and each still serves its curve. Runs carry no name (`/algorithm/index/new`
  sets none) and every id is re-minted, so rows are matched on (window + return + drawdown) recomputed
  FROM the curve. A curve claimed by several rows is resolved by **body hash** (16% of fetches are
  byte-identical duplicates, which legitimately share one curve); anything still ambiguous is
  **skipped and reported**, never guessed — a wrong curve silently corrupts every correlation.
- Matching runs in **two passes: tight, then relaxed**. Rows reconstructed from the wiki carry no
  `total_pct` and their retained curve is often a LATER run of the same strategy — agreeing on
  drawdown to 0.00–0.01pp while annual differs by ~0.14pp (the documented ~0.15pp re-run drift).
  At 0.10pp that recovered 0 of 42; `TOL_ANNUAL_RECONSTRUCTED = 0.25` recovers 17. The bound sits
  at the **tight end of a plateau** (12 rows at 0.15, 20 at 0.25, still 20 at 1.00), so a looser
  one buys nothing and only risks a wrong pairing. **Drawdown tolerance is never relaxed.**
  Relaxation must stay a FALLBACK: one relaxed pass over everything pulled rival curves into the
  candidate set of rows that already matched tightly and pushed 4 into "ambiguous" — including the
  低换手红利 component candidate. Each row gets exactly ONE verdict; concatenating both passes'
  ambiguous lists once made the buckets sum to 135 against a ledger of 124.
- ⚠ `component-scan.js --validate` annualizes over the **ROW's** day count. Using each side's own
  span injects a gap that SCALES WITH RETURN LEVEL — 0.27pp at the median but 0.80pp on an 85.9%
  book — which made healthy rows look like bad matches. With the convention removed, median
  |Δannual| and |Δmaxdd| are both **0pp** across 88 backfilled rows and the worst is 0.24pp.
- ⚠⚠ **`component-scan.js` blends are ex-post, cost-free and daily-rebalanced** — an upper bound and a
  screening device, never a result. Nothing from it may be written to a family page or results ledger;
  a survivor still has to be built as one strategy and run through the frozen harness. It ranks on
  **score uplift over the type leader**, not Sharpe, because blending raises Sharpe mechanically.
- **`data/components.tsv` registers harvested INGREDIENTS** (append-only, tracked, like
  `consumption.tsv`): which aspect of a gate-failing strategy is worth keeping, and the measurement
  that says so. `evidence` is required — the repo has already paid for a guess-based rule, one that
  permanently discarded 287 of 549 strategies. This is **not** a second, more lenient bench:
  everything stays measured under the one active epoch, and only the DECISION about the measurement
  changes. Measuring ingredients under weaker costs would select for contributions that are artifacts
  of unfillable fills, and a blend inherits those fills rather than laundering them.
- ⚠ `sharpeNoDiversification` only reads correctly **above the risk-free rate**: a negative excess
  return divided by the larger ρ=1 volatility moves toward zero, so stripping diversification would
  *raise* the reported Sharpe. The guard checks the sign first.
- Screening verdicts live in `screen/verdicts.json` and are applied INSIDE the queue builders,
  because every discovery run rebuilds the queues from scratch.
- Blind-test result (104 posts, 22.1% base rate): judgement on post BODIES scored 0.90 AUC vs
  0.75 for a bare 小市值 keyword and 0.66 for popularity. Title-only screening scores ~0.75 —
  fetch the bodies, they are free via `community/post/detailV2`.
- **Two community lookahead claims were tested and NOT reproduced** (`study/_probes/`,
  2026-09-18): `get_extras('is_st', start_date=D, end_date=D)` agrees exactly with
  `get_current_data()[s].is_st` on two separate TRAIN windows, and an undated
  `get_fundamentals(q)` is identical to `date=context.previous_date`. So the 15 held
  strategies using the `get_extras` ST form and the 130 undated fundamentals calls are clean.
  The 七星高照 NAV-premium lookahead claim is moot: study q-4 measured that filter as exactly
  inert. Still open: LOF/QDII NAV publication lag for the discount families.
- The backtest **log is not retrievable** via the API (`/algorithm/backtest/log` returns empty).
  A probe must encode its answer as a marker trade, and **always needs a control** — `no-trades`
  otherwise cannot be told apart from "the code path never ran". See `study/_probes/README.md`.
- **Harness constants live in `harness/config/epoch-<n>.json`; `active.json` says which is in
  force; code reads them through `utils/harness-config.js`.** They used to be duplicated across
  seven files and had already drifted. Bump an epoch by writing a new JSON + updating
  `active.json`; old epoch files are kept so results stay attached to the rules that made them.
- **Epoch 3 (2026-09-19)**: VAL **2024-01-01..2025-12-31** (was 2024 only), OOS reserve starts
  **2026-01-01**, OOS budget tightened to **2 tests per epoch** (the reserve is ~9 months).
  TRAIN and costs unchanged, so epoch-2 TRAIN rows stayed comparable; the 2 VAL results are
  annotated `harness_epoch: 2` in their file headers.
- **Epoch 4 (2026-09-20)**: pins three execution settings the bench used to leave to each
  strategy — `order_volume_ratio=0.05`, fund costs via `set_order_cost(..., type='fund')`, and
  `avoid_future_data=True`. Only 9 of 215 strategies set the volume cap, `set_commission` never
  governed funds (so 170 ETF strategies ran on their authors' fees), and 71 ran with no lookahead
  guard. ⚠ These change **fills and fees**, so TRAIN results are **not comparable across epochs**.
  The ledger gained an `epoch` column; existing rows are tagged `2` and get re-measured by
  screening priority rather than invalidated in bulk.
- **Epoch 5 (2026-09-20)**: scoring only — the measurement bench is identical to epoch 4.
  Gate **2.5 -> 1.5**, and the score is **kept when the gate fails** (`keepScoreOnGateFail`).
  2.5 sat at the 88th percentile of 124 measured strategies (median sharpe 1.02) and left
  **5 of 14 families with every member at -inf**, carrying no comparative information at all.
  Because score = annual - maxdd is a pure function of stored columns, all 103 affected rows
  were rescored with **no backtests**; 16 flipped fail->pass, and the five dead families now
  rank (趋势技术 0.2936, 网格 0.1411, 红利低频 0.1348, 三进兵 -0.0900).
- **Stage thresholds**: normalize/study/enhance/validate require sharpe 1.5, **type integration
  requires 2.0** (`harness.stageGate(stage, sharpe)`). Same measurement, different standard —
  a decision rule, not a different bench.
- ⚠ **`utils/strategy-normalize.js` had no `require.main === module` guard**, so a bare
  `require()` of it started a full 214-strategy batch and spent 42 of the day's 60 backtest
  minutes before it was killed. Guard added; every entry point in `utils/` needs one.
- The normalizer's done-check is **epoch-aware**: an epoch-2 row is not a result for epoch 4,
  since the pins change fills and fees. Without that it reported `todo=0` and silently refused
  to re-measure anything after the bump.
- ⚠ `set_order_cost` is **not bound at module scope** in every JQ runtime, unlike `set_slippage`
  and `set_commission`. Rebinding it unguarded in the injected OVERRIDE raised NameError at import
  and returned `compile-error` for the whole strategy. It is wrapped in try/except NameError.
- `enhance/strategy_template.py` and the normalizer's injected OVERRIDE run on JoinQuant's
  servers and **cannot read the JSON** — they hold literal Python. `harness-config.js --verify`
  is what keeps them honest; run it after any cost change.
- Pipeline 2's backtest window is parameterized via `--window train|val` (or `--start/--end`),
  set through the `newStrategy` URL params. The **2026+ OOS window is hard-blocked** (`OOS-BLOCKED`)
  unless `JQ_ALLOW_OOS=1` — see `harness/harness.md`. No flag = JQ default range (ad-hoc).
- Do not close the CDP Chrome process — it invalidates the JQ session and forces re-login.
