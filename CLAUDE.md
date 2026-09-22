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

# Daily cron pipeline — one stage per fire, by queue priority (enhance > study > norm > discover)
node utils/daily-pipeline.js --plan            # decide and explain, run nothing
node utils/daily-pipeline.js --status          # queues, budget, deferred pool, last runs
node utils/daily-pipeline.js                   # decide and run
node utils/daily-pipeline.js --stage normalize # override the pick for one run
node utils/daily-pipeline.js --once            # one stage only, no chaining
node utils/daily-pipeline.js --sync-manifest   # reconcile study/manifest.json with the ledger
node utils/daily-pipeline.js --seed-deferred   # park stranded slow-skipped rows in the pool
node utils/daily-summary.js --dry              # preview today's summary markdown
node utils/daily-summary.js --commit           # write docs/daily/<date>.md, commit, push
DRY=1 bash scripts/daily-pipeline.sh           # the cron wrapper, plan only
FORCE=1 bash scripts/daily-pipeline.sh         # bypass the scheduled-hour gate

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
node utils/stockcost-affected.js              # who the epoch-6 stock-cost pin actually changes
node utils/stockcost-affected.js --enqueue    # queue those for re-measurement
node utils/consumption-report.js --next       # what each loop should take next
node utils/wiki-type-build.js --check         # family -> type assignment (universe x turnover)
node utils/wiki-concept-lint.js               # concept strategyCount drift
node utils/type-integrate-check.js <c.json>   # guard on a type-level integration candidate
node utils/family-match.js --pending          # pages with no family:, with a proposal each
node utils/family-match.js --validate         # re-score the matcher before changing it
node utils/family-match.js --lineage          # the family tree (parent: on the child)
node utils/wiki-epoch-repair.js --dry         # fix pages whose normalized epoch disagrees with the ledger

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
node utils/factorlib-query.js --survivors      # the 6 of 285 factors that beat costs
node utils/factorlib-query.js --name <factor>  # formula + IC/IR, to actually build it
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
| `docs/pipeline-map.html` + `docs/assets/pipeline-map.png` | **Pipeline & skill coverage map** — the 17 stages, which skill drives each, and the open gaps. ⚠ It shows LIVE FIGURES (ledger/family/queue counts) so it goes stale silently; regenerate with `node scripts/render-doc.js docs/pipeline-map.html docs/assets/pipeline-map.png` after editing the HTML, which is the thing under review. |
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
- **A newly fetched member of an EXISTING family used to vanish.** `kb-stub.createStub()` wrote no
  `family:` and `wiki-family-build.js` skips pages without one (`if (!fm.family) continue`), so the
  member was structurally invisible to its own family page. The pattern only ever worked for
  strategies the pipeline GENERATED (`autoenhance-recorder` sets `family:` then runs the builder),
  never for ones it INGESTED. Now: stubs carry a `familyProposal:` (+ score), `normalize-sync`
  spawns `wiki-family-build`, and `consumption-report` reopens the family for study/enhance.
- ⚠ **`family:` is never auto-assigned.** `utils/family-match.js` scores Jaccard overlap of
  normalized code lines against each family's `base:` (a family is a LINEAGE, so code — not
  concepts, which cut across lineages by design). Measured on the 175 hand-labelled pages it is
  willing to decide only 31 of them (abstaining on 82%), and its abstain rules were tuned on those
  same 31 — so its precision is not an independent estimate. That is not good enough to
  write: a wrong assignment corrupts §3, `memberCount` and the whole type layer, silently and in
  the direction of the biggest families. It writes a PROPOSAL that the builder ignores; promotion
  is a human/`/ingest-strategy` decision. `node utils/family-match.js --pending` is the queue,
  `--validate` re-scores before any change to the matcher.
- ⚠ **Combination books defeat code matching.** 三马/七星/五福 embed other families verbatim, so
  they score high against several bases at once — exactly where the matcher was most confident and
  most wrong (0.98 against two bases). `match()` abstains when ≥2 bases clear `MIN_SCORE`.
- **Families are NOT flat: a family page may declare `parent: [[…]]`.** `五福闹新春` is a
  sub-lineage of `ETF动量`. Recording that resolved all four of the matcher's residual errors at
  once — they were the single confusion ETF动量 → 五福闹新春, i.e. the matcher naming the child
  where a human had written the parent. `sameLineage()` counts a parent/child call as correct.
  The relation is stored **once, on the child**; `node utils/family-match.js --lineage` prints the
  tree (a reciprocal `children:` list would be a second copy free to drift, and a test forbids it).
  ⚠ This does **not** change aggregation: `memberCount` and §3 are still per-family, so a parent's
  table does not absorb its children's members.
- **`consumption.tsv` gained `members` + `memberHash`** (appended; readers indexing 0..6 ignore
  them). `consumed(stage)` answered only "has this family EVER been studied", so once all 14
  families were done the study queue read empty BY CONSTRUCTION no matter how many members
  arrived. `consumption.staleFor(stage, family)` compares the stamped membership hash with the
  current one and reports "N new member(s) since last study". A blank hash (rows predating the
  column) counts as stale ONCE rather than being assumed current.
- ⚠ **`kb-stub.js` hard-coded `epoch: 1` and `夏普<2.5`.** All 120 wiki pages claimed a bench
  superseded four times while the ledger said epoch 2 (122 rows) / epoch 4 (2). That block is the
  **durable backup** the ledger is rebuilt from, and `normalize-ledger-rebuild.js` emits only 13
  columns (no epoch) — so a rebuild after a regression would have produced a mislabelled ledger.
  Fixed to stamp the measuring epoch and the live stage threshold; `node utils/wiki-epoch-repair.js`
  repaired all 120 from the ledger (authoritative), leaving pages with no row alone.
- ⚠ **Epoch comparability is a declared boolean, not equality.** The normalizer's done-check was
  `rowEpoch === ACTIVE_EPOCH`, which discarded epoch-4 rows under epoch 5 even though epoch 5
  changed only SCORING — meaning every future scoring-only bump would re-measure the whole library
  at 60 backtest-min/day. `harness.measurementValid(rowEpoch)` walks
  `comparability.measurementPreservedFromPrevious`. **Do not** infer this from
  `unchangedFromEpoch<n>`: epoch 4 lists seven unchanged items and its own prose still says "NOT
  comparable", because the pins it added change fills and fees. Reading the list marked epoch 3
  comparable and would have mixed pre-pin measurements into current tables.
- `normalize-sync` **spawns** `wiki-family-build` rather than requiring it: that file is top-level
  script code with no `require.main` guard, so a `require()` would execute it and its
  `process.exit()` would take the parent down — the same trap that once made a bare require of
  `strategy-normalize.js` spend 42 backtest minutes. A non-zero exit means BLOCKED and is reported,
  never escalated, and `--force` is never passed.
- **`research/factorlib/` is now wired in — as a HYPOTHESIS source for the ideator, not evidence.**
  It sat unread for weeks (zero references outside its own ingester) while the integration round
  ran out of material: **4 of 6 types are exhausted** (no member improves the type leader), and
  the biggest, `小盘-H-unknown`, has 29 members whose best candidate still *lowers* the leader by
  0.0301 at correlation 0.77. Recombining redundant things cannot fix redundancy, so the library
  needs orthogonal material from outside. `utils/factorlib-query.js` is the reader; the ideator
  gained an `external-factor` mode and the critic four rules for judging one.
- ⚠⚠ **Factor-board numbers may never enter our tables.** zz500 / 3y / JQ's cost model is a
  different bench, and a result belongs to the bench that produced it (that is what the ledger's
  `epoch` column enforces). A factor earns a ledger row by being built and measured on OUR bench;
  board figures are cited only as provenance. The query tool prints that warning on every call.
- ⚠ **The two turnover columns are not the same quantity** — the board's runs 1.8–3.06, ours runs
  0.0078–0.3061 and is JQ's per-day `turnover_rate` (verified: 0.0103 over 484 days). So the
  tempting "filter factors to this type's turnover band" (the type axis IS turnover) needs a
  conversion nobody has derived. Do not compare the two numbers.
- ⚠ The snapshot is **zz500 (mid-cap)** while the exhausted types are 小盘/微盘, so its IC may not
  transfer where it is needed most — re-ingest `--universe zz1000` first for small-cap targets.
- Two measured priors worth carrying: only **6 of 285** factors keep a positive post-cost excess
  return (all low-turnover), and **every 动量类因子 is deeply negative after costs** (worst erosion
  −15.25pp). A high-turnover or momentum import needs a reason it differs from the ones that failed.
- ⚠ 量化课堂 (`research/tutorials/`) is **methodology, not material** — it teaches how to do factor
  research. It belongs to the study loop or a future research pipeline, NOT to type integration,
  which combines already-measured artefacts.
- **The daily cron fires once a day at 18:00 UTC** (`com.mohanshen.join-quant-daily`).
  ⚠ launchd evaluates `StartCalendarInterval` in the machine's **local** timezone, and this
  machine is `America/Los_Angeles` with DST — 18:00 UTC is 11:00 PDT in summer, 10:00 PST in
  winter. A single fixed local hour would drift an hour twice a year, so the plist fires at
  **both** and `daily-pipeline.sh` keeps only the fire where `date -u +%H` really is
  `DAILY_RUN_HOUR_UTC`. Change the hour in that one variable and re-bracket the two local hours.
  The gate applies only to scheduled fires (`DAILY_SCHEDULED=1`); a manual run is never blocked,
  and `FORCE=1` bypasses it.
- ⚠ **A single daily slot means a missed slot is a missed day** — if CDP is down or the budget
  is already spent at 18:00 UTC, the wrapper exits 0 and does not retry. The earlier 4-hourly
  schedule caught the first usable window instead. If that bites, add hours to the array and
  gate on "no successful run today" (`data/daily-state.json` already records it) rather than
  widening the UTC gate.
- **Two of the four queues are FILES, two are DERIVED.** `data/pending-normalize.json` and
  `data/copy-queue.json` are real files the normalize/fetch pipelines themselves read. The
  enhance and study queues are **derived** from `wiki/families/*.md` + `data/consumption.tsv`
  — no file, and **the agent loops do not read them**.
- ⚠ **That asymmetry caused a silent no-op.** The planner derives study staleness from the
  consumption ledger; the loop nudge tells the agent to work `study/manifest.json`. The manifest
  said all 14 families were `done` while the ledger said all 14 were stale, so a dispatch would
  have found nothing to do and still exited 0 — and been recorded as `ran`.
  `node utils/daily-pipeline.js --sync-manifest` reconciles them; the ledger wins (tracked,
  append-only, member-aware), and the agent marking a family done makes it non-stale again, so
  it converges rather than oscillating.
- The planner controls **which stage runs** and (via the sync) **which families are eligible** —
  NOT which family the agent picks. The study nudge orders by `bestObjective`; the planner
  reports its own queue head for the log only, and says so.
- **Sessions are headless under cron, interactive for humans**: `auto*-loop.sh` runs
  `claude -p --resume <uuid>`; `auto*-interactive.sh` runs `claude --resume` / `--session-id`
  in a TUI. The cron **resumes** rather than cold-starting, so the agents keep context.
- The daily run **chains** stages while budget remains, re-planning between each — a normalize
  pass changes the ledger, which can legitimately promote study above normalize mid-run.
  `--once` runs a single stage. **`/run-daily`** is the skill entry point; stage selection stays
  in the deterministic planner because it is arithmetic with one right answer, and the skill
  handles only what needs judgement (a blocked stage, a loop that exits 0 having done nothing).
- **The daily cron picks ONE stage by queue priority — later stages outrank earlier ones**:
  `enhance > study > normalize > discover`. A pull system: finish what is in the pipe before
  admitting more, because the 60 backtest-min/day are the binding constraint and an idle
  enhance-ready family is a worse use of them than a raw strategy nothing can act on yet.
  ⚠ **Consequence, by design**: while any family is enhance-ready, normalization never runs —
  13 families and 53 pending strategies mean normalize starves indefinitely. `--plan` prints
  every queue's depth so it is visible; `--stage <name>` overrides for one run.
- ⚠ **The cron can RESUME study/enhance but never cold-start them.** They are Claude agent
  loops; their wrappers resume a session pinned by a human
  (`data/auto{study,enhance}-session.txt`, format `<branch>\t<uuid>`). The loop script refuses
  a pin from another branch and **exits 0** — so checking only that the file exists reports
  success every day while starting nothing. `daily-pipeline.js` checks the branch too, reports
  `blocked`, **cedes the budget to the next stage**, and exits non-zero so a dead cron is
  visible. The enhance pin is currently on `research/jul12` while HEAD is `main`.
- **`slow-skipped` stays TERMINAL in the normalizer** (making it retriable re-bills it every
  batch — the `no-trades` bug). The retry path is a separate **deferred pool**,
  `data/deferred.json`, drained only by the daily pipeline and only at a **higher cap than the
  one that already failed** — re-running at the same cap spends the same minutes to learn the
  same thing. 14 previously-stranded rows were seeded into it; ceiling is 3 attempts, after
  which they stay listed under `exhausted` rather than vanishing.
- This pipeline runs a **30-min slow-skip cap** (`--max-poll-min 30`), above the 20-min default,
  and a 55-min daily usage limit to stay inside the free tier.
- `data/daily-state.json` + `data/deferred.json` are **tracked**: the run log and the work queue
  are what let tomorrow resume. `JQ_DAILY_STATE_DIR` redirects both — tests set it to a temp dir,
  because a test run that appends probe rows writes fiction into the record the next run reads.
- An in-flight claim older than 6h is treated as abandoned and **taken over** (recorded as
  `abandoned`, not silently dropped), so a cron killed mid-run cannot deadlock the next one.
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
- **Epoch 6 (2026-09-20)**: pins **stock** order costs —
  `set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001,
  min_commission=5), type='stock')`. ⚠ The bench never controlled stock fees at all: the OVERRIDE
  intercepted only `type=='fund'` and forwarded everything else to the author's fee schedule, and
  **`set_commission` does not govern stocks** because JQ lists it as **已废弃** in favour of
  `set_order_cost`. Measured by probe (`study/_probes/probe-stockcost.py`): injecting a 5%/side
  stock commission into `int-001` moved total return **+64.44% → −11.33% (−75.77pp)**, so the
  author's setting wins outright. Same class of bug as epoch 4's fund-cost gap, on the stock leg.
  The pinned values are economically identical to what `PerTrade(0.0003/0.0013/5)` was meant to
  express — the bench's INTENT is unchanged, epoch 6 only makes it apply.
- ⚠ **Epoch 6's re-measure set is 23, not 215.** `measurementValid()` is deliberately coarse and
  invalidates every pre-6 row, but the change can only move a strategy that set its OWN stock cost
  to something other than the bench's. `node utils/stockcost-affected.js` classifies all 215:
  **120** never called `set_order_cost(type='stock')` (they ran on JQ's default, which *is* the
  bench value), **57** declared bench-equivalent economics (the pin is a no-op), **37** differ —
  of which **22** are normalized rows — plus 1 unparseable treated as affected. `--enqueue` puts
  them at the head of `data/pending-normalize.json`. A missing `close_tax` counts as
  bench-default, not as a difference. 36 of the affected declared a *cheaper* commission than the
  bench, so the pre-6 ledger **flatters** them.
- **Stage thresholds**: normalize/study/enhance/validate require sharpe 1.5, **type integration
  requires 2.0** (`harness.stageGate(stage, sharpe)`). Same measurement, different standard —
  a decision rule, not a different bench.
- ⚠⚠ **VAL is budgeted: ONE validation per (family, epoch)** — `utils/val-budget.js`, enforced in
  `strategy-post-backtest.js` before the browser opens. `--window val` now **requires `--family`**
  (an unnamed VAL is an untracked VAL) and a second run for the same family at the same epoch exits
  3 with `VAL-BLOCKED`. TRAIN is unaffected — selection lives there and may be re-run freely.
  **A different candidate does NOT buy a second validation**: "the last VAL disappointed, so make a
  new candidate" is selection on VAL one run at a time, which turns the held-out window into a
  second training set silently and irreversibly — after that the only clean surface is the 2026 OOS
  reserve (~9 months, 2 tests/epoch). Budget is spent only by a **completed** run (a compile-error
  or slow-skip produces no number, so it costs nothing), and a failure to record it shouts, because
  a missing row would wrongly grant the next VAL. Human-only override `JQ_ALLOW_REVAL=1`, recorded
  in the note when used; agents never set it, exactly like `JQ_ALLOW_OOS`.
- `data/consumption.tsv` gained a 10th **`epoch`** column, stamped from the live config by
  `record()` and never passed in — a caller that could choose its own epoch could validate a family
  twice by mislabelling the second run. Rows predating it read as UNKNOWN, and for the VAL rule
  **unknown blocks** rather than permits: blocking is visible and a human clears it in one command,
  permitting silently re-spends the protected resource. `JQ_CONSUMPTION_FILE` /
  `JQ_DAILY_STATE_DIR` redirect the file — it is TRACKED, and a test appending probe rows would
  silently cost a real family its one validation.
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
- ⚠ **The result scrape used to read the page's innerText INCLUDING the Ace editor's visible source
  lines.** Authors paste their own results into header comments (`# 回测2025-01-01到2026-04-27，策略收益
  2483.22%，…最大回撤13.13%`), and the first `策略收益 N%` / `最大回撤 N%` match landed on the comment,
  not the result panel — three 打板短线 epoch-6 rows recorded the authors' 2025–26 numbers as TRAIN
  results (annual 409% beside sharpe 0.16; sharpe survived only because the panel's label is
  "Sharpe" and comments say 夏普比率). The free `POST /algorithm/backtest/stats?backtestId=&ajax=1`
  and the stored curve both said 8.96%. `strategy-post-backtest.js` now hides `.ace_editor` /
  `#code` before reading. **A sharpe that cannot coexist with its annual/maxDD (implied vol
  > ~150%) is a scrape artefact until the stats endpoint says otherwise**; 289177df's epoch-2
  row (maxDD 10.68 = its header comment) is still unchecked.
