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

# Daily cron pipeline — one stage per fire, by queue priority (oos > integrate > research > assign > norm > discover)
node utils/daily-pipeline.js --plan            # decide and explain, run nothing
node utils/daily-pipeline.js --status          # queues, budget, deferred pool, last runs
node utils/daily-pipeline.js                   # decide and run
node utils/daily-pipeline.js --stage normalize # override the pick for one run
node utils/daily-pipeline.js --once            # one stage only, no chaining
node utils/daily-pipeline.js --sync-manifest   # reconcile study/manifest.json with the ledger
node utils/daily-pipeline.js --seed-deferred   # park stranded slow-skipped rows in the pool
node utils/daily-summary.js --dry              # preview today's summary markdown
node utils/daily-summary.js --commit           # write docs/daily/<date>.md, commit, push
node utils/realizability-lint.js               # free static flags for KNOWN unrealizability
node utils/realizability-lint.js strategies/x.py
node utils/oos-queue.js                        # promoted candidates: ready / tested / unrunnable
scripts/run-oos.sh --list                      # the OOS queue + each session's state
node utils/integrate-queue.js --next            # the next universe round (seed / integrate / idle)
node utils/integrate-eligible.js               # the /run-family exit gate, with each block's OWNER
scripts/run-integrate.sh --list                # the integrate queue + each universe's session state
DRY=1 scripts/run-integrate.sh                 # what the next round would be, nothing run
scripts/run-family.sh --list                   # the research queue + each family's session state
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
| `harness/` | **Shared frozen backtest台**: `harness.md` (window/cost/OOS protocol, read-only) + `normalize-*.tsv` ledgers (**tracked** since 2026-09-22; they were gitignored, which is why so many comments still say so). Used by study + enhance + future research. |
| `enhance/` | Auto-**enhance** team (optimize a strategy FAMILY): `program.md`, `candidates/`, `strategy_template.py`, transient `ideas-queue.json`/`loop-state.json`/`results.tsv` (gitignored) |
| `study/` | Auto-study team (understand a strategy FAMILY): `program.md`, `<family>/baseline.py` + `variants/`, transient `questions.json`/`findings.tsv` (gitignored). Writes back to `wiki/families/`. |
| `wiki/types/` | **Strategy TYPES** — generated by `utils/wiki-type-build.js`. A coordinate over families: universe (from the base source) x turnover band. Families sharing a type are integration candidates. Not a third page hierarchy; family and concept stay orthogonal. |
| `screen/` | **Frozen SCREENING rubric** — `screen.md` (four axes, priority formula, bands; read-only, epoch-versioned like `harness.md`) + `calibration/` (104 posts with sealed harness outcomes, the screener's held-out set). Decides what is worth fetching BEFORE backtest budget is spent. |
| `research/` | Reserved for a future auto-**research** pipeline — broad context: new data / factors / trading ideas. NOT the current optimize loop (that is `enhance/`). Holds `factorlib/` (below). |
| `research/factorlib/` | JQ **因子看板** ingested by `utils/factorlib-ingest.js`: 285 factors with formulas, IC/IR, quintile returns and turnover, pulled at **both** cost levels. `factors.tsv` + generated `README.md` (tracked); raw payloads in `data/factorlib/`. |
| `research/tutorials/` | **量化课堂**, 137 lessons in 5 categories, ingested by `utils/tutorial-ingest.js` via `detailV2` (free). Category 新手专区 is a full factor-research methodology chain. |
| `resources/` | **Raw layer #2** (alongside `strategies/`): community RESEARCH write-ups as `.md`, fetched by `utils/resource-fetch.js`. One file per post, frontmatter + full body. Notebook/attachment availability is recorded but the notebook itself is **not** downloadable (see Notes). |
| `docs/pipeline-map.html` + `docs/assets/pipeline-map.png` | **Pipeline & skill coverage map** — the 16 stages, which skill drives each, and the open gaps. ⚠ It shows LIVE FIGURES (ledger/family/queue counts) so it goes stale silently; regenerate with `node scripts/render-doc.js docs/pipeline-map.html docs/assets/pipeline-map.png` after editing the HTML, which is the thing under review. |
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
  `memberCount`/`bestVariant`). It **has regressed before** — it once fell from ~119 normalized
  rows to 18, which blocked every family page from regenerating. ⚠ It was gitignored when that
  happened and is **tracked since 2026-09-22**, so `git log harness/normalize-train.tsv` is now
  the first thing to try after a regression; the rebuild below remains the free fallback.
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
- **Epoch 8 (2026-10-16)**: scoring only — the bench is byte-identical to epochs 6 and 7, so
  `measurementPreservedFromPrevious: true` and **no row is re-measured**. It **invalidates epoch 7's
  integration bar** and replaces it (user decision): `integrateBar.basis` **`worstTrainYear` →
  `perYearSharpe`**. In **every** TRAIN calendar year, the candidate's sharpe computed *within* that
  year must exceed the highest sharpe any **parent champion** achieves in that **same** year —
  domination, on sharpe, not a maximin on objective.
  **Why sharpe, not objective, and why every year rather than the worst**: both follow from the two
  measurements recorded under the epoch-7 note below (objective is almost purely annual return; and
  annual return over TRAIN is substantially a 2022 measurement). An objective bar is a return-LEVEL
  bar, and a maximin let a candidate win by being least-bad in one year while giving up the other.
  ⚠ **An epoch-7 verdict does not carry forward.** The guard dispatches on `integrateBar.basis`, so
  an old epoch still judges by its own rule — but claiming an epoch-8 conclusion requires re-judging
  (re-judging, not re-measuring).
- ⚠ **The per-year best parent may differ by year**, so the candidate faces a composite no single
  parent matches. Epoch 7 treated that as the reason to prefer a maximin; **epoch 8 accepts it as the
  price of domination**, and the guard flags `parents-split-by-year` with the per-year attribution.
  Measured: 全A's 打板短线 champion runs sharpe **2022 7.45 / 2023 −0.18** and 红利低频 **1.18 / 1.67**,
  so 全A's bar is "beat 7.45 in 2022 **and** 1.67 in 2023" — and 打板短线's own realism declares its
  headline unrealizable, so the 2022 half of that bar is set by a book we would not trade.
- ⚠ **The per-year bar needs a curve for the candidate AND every parent**, else it falls back to the
  pooled rule and says so (`flags: bar=pooled-fallback`). **7 of 11 champions** currently have a
  usable per-year split; **4 do not** (七星高照, 五福闹新春, 大小盘轮动, 小市值), so any round touching
  those lands on the fallback. `node utils/series-backfill.js` is the zero-backtest-cost fix — it
  recovered 11 curves on 2026-10-16, though not 七星高照's champion (a 三马/七星 combination book,
  in the 52 unmatched).
- ⚠⚠⚠ **63 curves were silently saved under a HIDDEN, unreadable key.**
  `strategy-post-backtest.js` keyed the stored curve by `path.relative(ROOT, strategyPath)`, which
  is right for a repo path and wrong for `strategy-normalize.js` — that writes a normalized COPY to
  `/tmp/jq-normalize/<tag>.py` and runs the child on it, so the key became
  `.._.._.._tmp_jq-normalize_<tag>__train__e6`. **Two things hid it for months**: the key starts
  with a dot, so every `ls data/series/` listed none of them; and no reader could find them,
  because every reader builds its key from the real `sourceFile`. So `loadComparable()` answered
  "no curve" for curves sitting on disk.
  This is why four family champions read as curveless, why `series-backfill.js` found **zero**
  account matches for them (JQ had reaped the runs while the local capture existed all along), and
  — once epoch 8 made the bar per-year sharpe — why the bar silently fell back to pooled.
  ⚠ **I re-ran all four before finding this** (~23 backtest minutes) on the strength of the
  backfill's zero matches. `ls -a data/series/` would have shown them. **Check for hidden files
  before concluding a curve is unrecoverable.**
  **Fixed in three places**: `--source-file` carries the LOGICAL identity (the normalizer passes
  `strategies/<name>`); `logicalSourceFile()` **throws** on a path that escapes the repo rather than
  writing a hidden file; and `node utils/series-rekey.js --dry` recovers the stranded ones.
  It re-keyed **39** and skipped 24 whose target already existed — verified byte-identical, so the
  skip rule is safe. Champion per-year coverage went **7/11 → 11/11**.
  ⚠ Mapping uses the normalizer's tag, `(postId || basename).slice(0,8)`. Eight hex characters can
  collide and a wrong curve corrupts every correlation and per-year bar built on it, so a tag
  claimed by two sourceFiles is **skipped and reported, never guessed** — the same rule the
  backfill applies to an ambiguous match.
- ⚠⚠ **The curve store is LOSSY in a way the ledger is not**, and since epoch 8 that silently
  downgrades the integration bar. JQ reaps retained algorithms, so a row can be a current
  measurement while its daily curve is gone for good. Measured 2026-10-16: the four champions with
  no curve (七星高照, 五福闹新春, 大小盘轮动, 小市值) matched **zero of 3,796** cached account curves,
  **tight and relaxed** — `series-backfill.js` cannot recover them at any tolerance, so a re-run is
  the only way back. (One of them, 大小盘轮动, is *reported* AMBIGUOUS by the backfill, but that
  ambiguity belongs to its epoch-2 reconstructed row, not to the epoch-6 champion — read which row
  the warning is about before assuming the curve is recoverable.)
- **`strategy-normalize.js --redo`** re-measures files that already carry a valid terminal row —
  the only path to a lost curve. ⚠ **Guarded to an explicit `--files` list**: a bare `--redo` exits
  2, because without that guard it re-bills the whole 215-strategy library, the same shape of
  accident as the missing `require.main` guard that once spent 42 backtest minutes. The new row
  APPENDS and newest-row-wins makes it authoritative; expect ~0.15pp of re-run drift.
- `JQ_SERIES_DIR` redirects `data/series/` for the same reason `JQ_DAILY_STATE_DIR` and
  `JQ_CONSUMPTION_FILE` exist: a test writing probe curves into the real store would put fiction
  into the thing every bar is computed from. It is resolved per call, so a test can set it after the
  module is loaded.
- ⚠⚠ **The integration bar is the family CHAMPION, and the guard derives it — it is not a caller
  input.** ETF round 2 supplied each family's study BASELINE as the member, which is the right thing
  to DECOMPOSE a pipeline from and the wrong thing to be judged against: ETF动量's base is objective
  0.1868 / sharpe 1.41 / worst year −0.0072, its champion 0.4725 / 2.23 / **+0.3673**. So the round
  reported **+0.0274 uplift** against a bar of −0.0072 when the real alternative was +0.3673 — against
  the champion the same candidates lose by ~0.43. It also made both parents look like gate failures
  (1.41 / 1.21) when every ETF champion clears 1.5. Rule 1 asks whether the merge beats what the
  universe would **otherwise ship**, and that is literally what PROMOTE ships: the champion.
  `championOf()` now resolves it from the ledger (best objective among rows `measurementValid()`
  accepts) and flags `member-below-champion:<family>` when the caller understated it.
  ⚠ It reads the **ledger**, not `component-scan.members()`, which skips rows with no stored curve —
  that would have picked a lesser row as 七星高照's champion (its real one, a 三马/七星 combination
  book, has no retrievable curve) and understated the bar all over again.
  ⚠ **Two aggregates, kept apart**: the bar side uses champions (rule 1 — the alternative we would
  ship), the leg side uses the supplied members (rule 2 — attribution among the things actually
  combined). Collapsing them is what produced the bug, and it also made `all-parents-below-gate`
  fire falsely on ETF.
- ⚠⚠ **`type-integrate-check.js` never checked the stage gate.** It applied rules 1–4 and returned
  **`keep`** for ETF round-2 candidates at sharpe **0.94 and 0.91** against a threshold of 1.5;
  only the merge agent's own reading caught it. Rule 1's slogan — "beat the MEMBER, not the gate" —
  exists to stop a gate PASS being mistaken for success, and had been read as licence to skip the
  gate entirely. Now **rule 0** rejects on `harness.stageGate('integrate', …)`, and the result
  object carries `stageGate: {min, candidate, passes}`. A companion flag `all-parents-below-gate`
  fires when no parent clears the bar — deliberately a **warning, not a veto**, because a blend can
  mechanically exceed both parents whenever correlation < 1, which is the trap rule 2 exists for.
  The agent contract now says to check both parents **before** declaring a candidate set.
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
- **INTEGRATION IS INCREMENTAL, not all-pairs** (user specification, 2026-10-16;
  `docs/proposals/type-integration-by-edge.md` Revision 4). A universe holds a set of **promoted
  candidates** (`data/promoted.tsv`, append-only + tracked, replayed by `utils/promoted.js`), and
  families arrive **one at a time** after clearing `/run-family`. Each arrival meets the set:
  **(1)** nothing promoted overlaps its symbols → promoted automatically (an EMPTY set needs no
  judgement at all — the queue calls that `seed`); **(2)** an overlapping incumbent and the merge
  is better → the merged candidate is promoted and **supersedes** the incumbent, the arrival living
  on inside it; **(3)** an overlapping incumbent and the merge fails → the incumbent is
  **unchanged** and the **arrival** is rejected.
  The old model enumerated every pair, which treated a universe as a static set with no memory of
  what it had shipped, so the same pairs came back round after round and a round's own result
  changed nothing about the next.
- ⚠ **Sequence is load-bearing.** The first arrival defines what everything after it must beat, so
  families enter `/run-family` ordered by their **champion's TRAIN sharpe**, highest first
  (`family-queue.js`: `championSharpe`, with the screen score demoted to a tiebreak — that score
  ranks what is worth FETCHING, a different question). An arrival overlapping **several** promoted
  candidates merges against the **highest-sharpe** one only: one attempt per arrival keeps the cost
  bounded, where trying each in turn would be a search over incumbents.
- ⚠ **A rejection is keyed to the `candidateId`, never the family.** Outcome 3 is "rejected until
  this family has a new best variant", so the key is the champion's `sourceFile` (or a merged
  candidate's `expId`). A new best variant is a new `candidateId` and therefore a new attempt, with
  no expiry rule to get wrong — and one failed merge can never silently retire a lineage.
- ⚠⚠⚠ **The ledger cannot hold the family's own best work, so "champion" was the wrong word.**
  `championOf` reads `harness/normalize-train.tsv`, which tracks only **ingested** community
  strategies (`strategies/*.py`). A book the research loop **built** can never appear there — so
  for a family whose best work is a constructed candidate, the "champion" was the best ingested
  **member**, a different thing. `validated_strategies/` is the real registry: CLAUDE.md already
  called it "the product shelf", and its artifacts carry structured provenance
  (`# family:`, `# expId:`, `# harness_epoch:`, `# gate_val:`).
  So the gate now takes a family's **CANDIDATE** = its validated product when the shelf has a
  usable one (comparable epoch + `gate_val: pass`), else its best ingested member.
  ⚠ Measured: 大小盘轮动's shelf holds `dxp-imp-1.py` at `train_objective 0.6623` against the base's
  0.4567, `sharpe_val 1.88`, `gate_val pass`. **The family was settled all along**; I had promoted
  the base, then saw the VAL did not match it and wrongly concluded there was no agreed candidate.
  Re-measured on this bench, imp-1 reproduces exactly (226.83 / 80.93 / 3.51 / 14.70 ⇒ 0.6623) and
  **dominates the base in both TRAIN years** (3.02/3.86 vs 2.38/2.82), so TRAIN selects it with no
  appeal to VAL. `bestVariant` names the best *member*; it is not the family's product.
  Two parsing traps found doing this: the shelf header **pads and appends a gloss**
  (`# family:  大小盘轮动   (source base: …)`) so a naive capture never matches and the shelf reads
  empty; and the VAL `runId` convention is **not one shape** — `dxp-imp-1-val` suffixes the token
  while `pt-val-base-e6` and `dbdx-VAL-base-e6` **infix** it, so a plain `includes(expId)` falsely
  rejected two correctly-recorded VALs. Both are normalised now.
- ⚠⚠ **Realizability is a property of a BOOK, and the page carries one number.** When the candidate
  is a product rather than the base, the page's score was measured on a different book. 大小盘轮动's
  R=2 came from `liq-1` on the **base**, while its product is always-small — which the family's own
  realism calls worse on capacity. `realizabilityScope:` names the book the score describes;
  absent, it is taken to describe the base, and a product candidate **blocks** until scored.
- ⚠⚠⚠ **A passing VAL does not mean the CANDIDATE was validated.** The exit gate checked "has a
  champion" and "has a passing VAL" **independently**, and a family can satisfy each with a
  DIFFERENT book. Caught 2026-10-16 while preparing an OOS run: 大小盘轮动's champion is the base
  `2f5bc859` (objective 0.4567) while its one VAL — `dxp-imp-1-val`, sharpe 1.88 — ran on
  `enhance/candidates/dxp-imp-1.py`, the always-small variant (objective 0.6623), **proven by the
  stored curve `enhance_candidates_dxp-imp-1__val__e6`**. 混合 had already been SEEDED on that, so
  an irreversible OOS test was about to be spent on a book nothing had validated. The seed is now
  **withdrawn** (`supersede` row in `data/promoted.tsv`).
  **The evidence is the stored VAL-window curve**, because `consumption.tsv` records *that* a VAL
  happened and under which `runId` — never which FILE it ran. The key is
  `seriesKey(sourceFile, 'val', epoch)`, so the curve names the book.
  ⚠ An exact key match can **never** confirm: a VAL runs on `study/<fam>/baseline*.py` or
  `enhance/candidates/*.py` (which carry pins), never on the raw `strategies/*.py` the ledger keys
  on. So the rule is: a VAL on the family's **study baseline** validates the champion **iff
  `base == bestVariant`**; a VAL on an `enhance/candidates/*` book never does, because a
  constructed candidate is never a ledger row and therefore never the champion.
  Measured across the library: **红利低频 and 打板短线 pass** (base == bestVariant, VAL on the base);
  **PT多策略** (base fa0d3bd9 vs champion c70281d3), **小市值** (VAL on `xsz-imp-5`), **ETF溢价**
  (VAL on `ep-imp-1`) and **大小盘轮动** (VAL on `dxp-imp-1`) all fail. So **1 of 13** families now
  clears the gate, down from 2.
  ⚠ This is **not** a realizability problem for 大小盘轮动 — `liq-1` confirmed R=2 by measurement.
  It is that the family never settled on one book: TRAIN prefers imp-1 (0.6623 vs 0.4567) while its
  VAL drew down **36%** against the base's 18%, and the page says 「采纳依据只在 TRAIN」.
- **`/run-family` now has an EXIT GATE** (`utils/integrate-eligible.js`): a champion measured under
  a comparable epoch, a **VAL that PASSED** `stageGate('validate')`, and **realizability ≥ 2**.
  Rule 4 at the judge therefore never has to bind — nothing with an untradeable leg can arrive. The
  check stays in the guard as defence in depth.
  ⚠ **Unknown realizability BLOCKS, it does not permit** — the same rule the VAL budget applies to
  an unknown epoch: blocking is visible and a human clears it with one edit, whereas permitting
  silently ships an unrealizable book. ⚠ And it is **not** inferable from the `不可实现` regex:
  打板短线 does not match it and was scored **1** on evidence (it buys the next-day open of
  yesterday's 涨停, and a sealed 一字板 cannot be bought at any price).
  `realizability:` + `realizabilityBasis:` now live in family-page frontmatter. Eight were
  transcribed from the `candidate.json` files that recorded them (ETF动量 2, 七星高照 2, 红利低频 3,
  打板短线 1, 小市值 1, 多因子ML 1, and ETF溢价/PT多策略 1 from their own `不可实现` declaration);
  五福闹新春, 大小盘轮动, 三进兵, 网格, 趋势技术 are deliberately **unset** and therefore blocked.
  Nothing was invented — the repo has already paid for one guess-based rule that permanently
  discarded 287 of 549 strategies.
- ⚠ **Measured consequence of the two gates: 1 of 13 families is currently eligible.** 红利低频
  (全A) seeded 全A on 2026-10-16. Four are REJECTED on realizability (PT多策略, 小市值, ETF溢价,
  打板短线) and eight BLOCKED — seven never validated, two have no champion under the active epoch.
  So the pipeline's real bottleneck is **VAL coverage and realizability**, not integration, and
  `node utils/integrate-queue.js` now reads `IDLE … the gate is upstream (/run-family)` almost
  everywhere. That is the intended signal, not a fault.
- ⚠ **A promoted INCUMBENT is not a family and must not be champion-resolved.** One side of an
  incremental merge is the universe's promoted candidate, which may itself be a **merged** artifact
  spanning two families — there is no champion of it to look up, and its own figures ARE the bar
  because it is what the universe currently ships. `type-integrate-check.js` skips resolution for
  `kind: 'merged'` / `promoted: true` and labels such a member by its `candidateId`, so a report
  never says the bar was set by `null`.
- ⚠ **Open gap I did not close**: eligibility checks the **VAL** sharpe, not the champion's TRAIN
  sharpe. 红利低频 was seeded with a champion at TRAIN sharpe **1.46**, below the 1.5 every other
  stage holds, because its VAL passed at 2.05. The spec says VAL, so this is as specified — but a
  universe can currently ship a champion that fails the TRAIN gate.
- **The liquidity-floor test is now a measured axis, and it does NOT always bite.** Run on
  大小盘轮动 (2026-10-16, 3 declared floors, 31 JQ min): at the sleeve's own position size
  (1M / 10 names / `order_volume_ratio=0.05` ⇒ **2e6**/day feasibility floor) the floor removes
  **zero** names on **31/31** rebalances, all 10 slots fill, and the curve is **bit-identical** to
  the baseline over 484 days (`max|Δcum| = 0`). So **R=1 is measured false** here — the ETF溢价
  (8.44→1.10) / 小市值 (7/8 不可成交) pattern did **not** reproduce, and 混合's promotion stands.
  R=3 is refuted too: 5× headroom (1e7) costs 0.45 sharpe and **all of 2022**, 10× (2e7) drops
  sharpe to **1.32, below the gate**. Read as a capacity curve (each floor is the feasibility
  minimum for a multiple of the base capital): **¥1M → 2.68 pass, ¥5M → 2.23 pass, ¥10M → 1.32
  fail**, so capacity is ~**¥1–2M** and the 规模 × 低价 edge is funded by names trading
  **2–20M CNY/day**. ⚠ Honest bound on that reading: the floor models a manager who *declines* a
  name he cannot fill, whereas a real ¥5M book would take **partial fills** — it is the disciplined
  version of the capacity question, not a literal capital sweep.
  ⚠⚠ **Also measured on the PRODUCT** (dxp-imp-1, always-small — the family's actual candidate):
  2e6 is inert there too (bit-identical, 40 `LIQFLOOR` lines `in==out`, `slots=10`, 0 errors), and
  1e7 keeps objective **0.5403 / sharpe 3.02** with both years above the gate (2.31/3.72) — still
  better than the **base unfloored** (0.4568). But it loses **more** sharpe at 1e7 than the base
  (−0.49 vs −0.45), because always-small holds the thin sleeve on strictly more days. So the product
  is scored **2, not 3**: capacity is what a book can ABSORB, not how much sharpe it has spare, and
  its bigger headroom to the gate is a level effect. The 2e7 point on the product is **unmeasured**
  (projection ≈2.1, so 3 is not ruled out, merely not earned).
  ⚠ **Correcting an overstatement made earlier in this file**: "capacity ~¥1–2M" conflated two
  quantities. **Unimpaired** capacity ≈ ¥1M (the 2e6 feasibility floor bites nothing there);
  **gate-passing** capacity is between ¥5M and ¥10M for the base and ≥¥5M for the product.
  ⚠⚠ **Why it was inert is incidental, not designed**: the 股息 top-25% + 营收>1e8 + 盈利/ROE/ROA
  chain happens to exclude illiquid names. So any variant loosening that chain (u-6-style dividend
  gate removal, u-7/u-8-style price-cap widening) **re-opens the axis** and must re-run liq-1 before
  its number is citable. Recorded as a conditional gap in §4.
  ⚠ The per-year curve is **non-monotone** while the pooled one is monotone: 2e7's 2022 (1.84) beats
  1e7's (1.60) while its 2023 collapses (2.82→0.62). Different name sets, not smooth degradation —
  a reason never to read one floor as "the" floor.
- ⚠ **`missingPins` checks only three markers** (`avoid_future_data`, `order_volume_ratio`,
  `set_order_cost`), so the pinned **benchmark** is not enforced. Two of the families inspected on
  2026-10-16 have baselines that deviate: 七星高照 sets `510300.XSHG` and 大小盘轮动 sets none at
  all. Severity is low — `set_benchmark` moves the benchmark curve and alpha/beta, never the
  strategy's own return/sharpe/maxDD, which is all the ledger stores — and a variant built from
  such a baseline is still a faithful Δ. But it is a declared pin that nothing polices.
- ⚠⚠ **A parent/child pair is not an integration candidate** — `integrate-queue.js` refuses it
  structurally. `五福闹新春` declares `parent: [[ETF动量]]`, so it is a FORK of that family and
  already carries its mechanism; picking the better variant within one lineage is `/run-family`'s
  job. The queue offered the pair anyway, and because the child's measured edge is named 趋势择时
  while the parent's is 动量 it read as **DIFFERENT edge sets** — i.e. the ETF universe's most
  attractive "combine" candidate was a fork of one family. **Edge names cannot catch lineage.**
  `sameLineage()` walks the chain (so a grandchild is caught) and tolerates a declaration cycle;
  it belongs in the deterministic layer because `parent:` is a declared frontmatter fact, the same
  class as `universe:`.
- **The ETF universe's ceiling is an ex-post pool, and epoch 7's bar is what makes it visible.**
  Per-year objectives of the five **study BASELINES** (free, from stored e6 curves): ETF动量 0.4889 /
  −0.0072 (**83%** of log-growth in 2022), 七星高照 0.3634 / −0.0651 (**82%**), 五福闹新春 0.5247 /
  0.2454, ETF溢价 0.6214 / 1.2905, PT多策略 2.8407 / 1.1870. The two pure momentum BASELINES are
  **negative in 2023**.
  ⚠ These are baselines, **not** the families: every ETF CHAMPION clears the gate (PT多策略 1.8448
  /sh 11.20, ETF溢价 0.7767/4.60, 五福闹新春 0.4848/2.37, ETF动量 0.4725/2.23, 七星高照 0.3365/2.54)
  and ETF动量's champion has a worst year of **+0.3673**, not −0.0072. Do not quote a baseline as a
  family's number — see the champion-bar note above.
  The baselines' realism blocks say why they are 2022-shaped: ETF动量's 11-ETF pool was 「写于 2026」 and an A-share broad
  pool scores **−0.27**; 七星高照's pool is 「事后选择且不可替换」 and the source's own 38-ETF pool
  scores **0.0016**. So the measured 动量 edge is the POOL, not the ranking — and `趋势择时` is
  **refuted** on all three momentum families.
- ⚠⚠⚠ **EPOCH 9'S VAL WINDOW IS CONTAMINATED BY CONSTRUCTION FOR THE ETF BOOKS.** Found
  2026-10-18 while auditing the two strongest epoch-9 rows (both ETF momentum: 73b13d92 objective
  **1.4926**/sharpe 5.22, 1cc495be **0.9954**/4.59). Those books carry **~114 active ETFs**, not the
  17 of the earlier round, and **17 of them list after 2024-01-01**:
  | listed | count | consequence |
  |---|---|---|
  | during TRAIN 2024 | **10** | tradeable only from their listing day, and selected in 2026 knowing 2024 |
  | during **2025** | **7** | untradeable in TRAIN at all — but **tradeable in VAL (2025)** |
  The seven 2025 listings are the serious half: `159323` 2025-01-08, `159206` 2025-03-14, `588170`
  2025-04-08, `159218` 2025-05-22, `159227` 2025-05-16, `588790` 2025-01-09, `159256` 2025-08-04.
  A pool assembled in **2026** that contains names which listed **during 2025** has
  selection-on-VAL built into the source — so a validation of these books is contaminated no
  matter how the TRAIN test comes out.
  ⚠⚠ **VAL is one shot per (family, bench) and epoch 9 granted 五福闹新春 a fresh one.** Reaching
  VAL on these books unexamined would spend the family's only validation on a pool picked with
  knowledge of the validation year. **A VAL on any of these books needs at least a pre-2025 pool
  cutoff**; the TRAIN test settles only half the question.
  ⚠ Epoch 9 does not relieve the pool problem, it reshapes it: the *availability* half improves
  (most of the 2026 pool existed by 2024, where 8 of 17 postdated the old 2022 TRAIN) while the
  *selection* half worsens (the window now sits ~2 years from the authoring date instead of 4).
- ✅ **RESULT (2026-10-19): the pools FLATTER the books but do not EXPLAIN them.** Restricting each
  pool to names listed before the window:
  | book | objective | sharpe | Δ |
  |---|---|---|---|
  | 73b13d92 unrestricted | 1.4926 | 5.22 | |
  | 73b13d92 **point-in-time** | **1.0025** | **3.66** | −0.4901 (**−33%**) |
  | 1cc495be unrestricted | 0.9954 | 4.59 | |
  | 1cc495be **point-in-time** | **0.8068** | **3.77** | −0.1886 (**−19%**) |
  Both still clear epoch 9's 1.0 gate comfortably. ⚠ **This is NOT the ETF动量 pattern**, where
  swapping to a broad A-share pool took the result to **−0.27** — hindsight is at most a third of
  the 2024 ETF-momentum strength, so these books are real candidates and the pool question does not
  have to be won before working on them.
  ⚠⚠ **Quote the two numbers as a PAIR.** The unrestricted figures run 19–33% higher, so citing one
  alone systematically over-reports. Recorded as 五福闹新春 §2 rows + finding `q-e9-pit`.
  ✅✅ **FOUR BOOKS TESTED — the pool bonus splits by MECHANISM, not per book.**
  | book | unrestricted | point-in-time | Δ |
  |---|---|---|---|
  | bba95a11 小盘**+五福** | 1.7881 | **1.7896** | +0.0015 |
  | b50e4387 小盘**+ETF** | 1.6997 | **1.7180** | **+0.0183** |
  | 1cc495be 五福+冷却 | 0.9954 | 0.8068 | −0.1886 (**19%**) |
  | 73b13d92 五福 ETF | 1.4926 | 1.0025 | −0.4901 (**33%**) |
  The two **小市值 × ETF HYBRIDS lose nothing** — both are fractionally BETTER restricted. The two
  **pure ETF-momentum** books lose 19% and 33%. Reading: the hybrids' edge comes from the 小市值
  leg, which has no pool to select, while the pure ETF books genuinely depend on the 2026 name list.
  **So the library's top two books are pool-clean and can be advanced as candidates; any new pure
  ETF-momentum book must run this test before its score is quoted, and quoted as a PAIR.**
  ⚠ **n=2 per group.** The split is clean but small — it is a guide to which book to test next (one
  more of each kind), not an established law.
  ⚠ b50e4387's pool is **UNDATED** (114 bare hardcoded codes), so the primary rule found nothing
  and the builder correctly REFUSED. It uses a **corpus-wide fallback** — listing dates recorded by
  other authors in the same corpus — with each date's provenance stamped into the variant header,
  because that is weaker evidence than a book's own comment. Corroboration: the exclusion set came
  out as the same 17 names / 7 from 2025 as its siblings.
  ⚠ The builder also learned **bare-code lines** (several ETFs per line, no comment), where
  exclusion removes CODES rather than commenting the line; the assertion therefore counts changed
  LINES and requires every changed line to carry the marker.
  ⚠⚠ **The earlier "PER BOOK" note below is superseded by the table above.** The same rule on
  **bba95a11**
  (小市值+五福组合, the epoch-9 library leader) moved it **+0.0015** — objective 1.7881 →
  **1.7896**, sharpe 6.99 → 7.10, with all **18** post-window names removed. So the three books
  span **0% / 19% / 33%** of pool hindsight: 「ETF 池都带事后性」 is NOT a family-level fact and
  must be tested book by book. bba95a11 is therefore the most trustworthy high score on this
  bench, and should be preferred over the other two for research, since they each carry a
  19–33% pool bonus. (Finding `q-e9-pit-bba95a11`; the book is `family: 小市值`, so its §2 row
  lives there while the finding stays with the chain that spawned it.)
  ⚠⚠ **The VAL contamination is UNADDRESSED by this result and is the worse half.** Seven pool
  names listed in 2025 (`159323`, `159206`, `588170`, `159218`, `159227`, `588790`, `159256`) and
  epoch 9's VAL **is** 2025 — a 2026-authored pool containing names that listed inside the
  validation year has selection-on-VAL written into the source. **Any VAL on this family must apply
  a pre-2025 pool cutoff first**; recorded as a blocking precondition in the family's §4, because
  VAL is one per (family, bench) and epoch 9 just re-granted it.
- **The point-in-time pool test is `study/五福闹新春/build-e9-pit.js`** — `pool ∩ { 上市日期 < train
  start }`, cutoff READ FROM THE HARNESS so it survives the next window move. Both inputs are
  pre-run facts from the book itself (names from its source, dates from the author's own inline
  comments; a listing date is a security attribute, not performance data), so the rule cites no
  price, return, volume or ranking from the window. Excluded names are **commented out in place**
  — the smallest auditable edit, leaving the author's own date visible beside each exclusion — and
  the builder **asserts the changed lines are exactly the exclusions**, refusing otherwise. Nothing
  else moves: ranking, momentum window, timing, thresholds, liquidity and the cost block are
  verbatim. Same rule as q-e8-7, which under the old window CLEARED ETF动量 (0.3962 vs base 0.3755,
  both TRAIN years ≥ base) — so it is not a test that only ever rejects.
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
- ⚠⚠⚠ **The `discover` STAGE was running the `normalize` stage's work, for hours.**
  `utils/strategy-daily.js` ends by calling `normalize-daily.normalizeNew()`, which runs
  **backtests**, and `runDiscover` invoked it bare. So discover measured strategies outside the
  budget accounting, the deferred pool and the retry-at-a-higher-cap rule, bounded only by
  `STAGE_TIMEOUT_MIN=255`. Measured: **4h25m on 2026-10-16**, killed by that timeout and taking the
  day's remaining budget with it; **61 min on 2026-10-17** before it was killed by hand.
  ⚠ **Neither run moved `used`** — JQ settles `duration.used` only when a run TERMINATES, so an
  in-flight backtest is invisible to every budget gate, and a hang spends wall clock rather than
  minutes. Two monitors expired in silence while it sat there; I read the first expiry as a
  wrong-file mistake, which was one expiry too late.
  **Fix (part 1 of 2)**: `runDiscover` passes `--no-normalize`.
  ⚠⚠ **That alone did NOT fix the symptom, and the "~3 min" first claimed here was wrong** — it was
  the WORK finishing, read off the log, while the process sat idle. There was a **second,
  independent cause**: `strategy-daily.js` never called `jq.close()`.
  `jq-http` holds a Playwright CDP connection; eight modules close it, but each inside its own
  `require.main === module` block, and `strategy-daily` requires `strategy-discover` /
  `strategy-fetch` as **modules**, so none of those blocks ever ran. The open socket
  (`localhost:* → localhost:9225 ESTABLISHED`) kept Node's event loop alive. Measured: all output
  written by 02:40:31, process still alive and idle at 02:45 (1.59s CPU, 1 open socket), bound for
  the 255-minute timeout. **Either cause alone takes the stage to the timeout**, which is why
  fixing one left the symptom unchanged.
  **With both fixed the stage exits 0 in 14 seconds.**
  ⚠ **Rule: an entry point that opens jq-http — including transitively, through a callee whose own
  CLI block will not run — must `.finally(() => jq.close())`.** Use `process.exitCode`, not
  `process.exit()`, or the finally is skipped. A test enforces this for any CLI that calls
  jq-http itself and names `strategy-daily` for the transitive case, which no static rule catches.
  ⚠ `strategy-copy.js` acquired the same leak on 2026-10-17 when its hand-rolled `https` helpers
  were replaced with jq-http delegates and the close was not added with them. Fixed.
  ⚠⚠ **`--no-normalize` now means "ENQUEUE but do not measure", not "skip"** — this is why it was a
  three-file change. `normalizeNew()` is the ONLY thing that appends a day's fetches to
  `data/pending-normalize.json` (the enqueue is its first two lines, the backtests follow in the
  same call), so the old skip-entirely behaviour would have stranded every strategy fetched that
  day. `normalize-daily.enqueueOnly()` is the queue-write half, and a test asserts it cannot reach
  `execFileSync` / `strategy-normalize` / `cdpAlive`.
  ⚠ Verified: 3 fetches enqueued (queue 8 → 11), measurement left to the normalize stage.
- ⚠ **The `notify` binary is absent on this machine, and its stack trace was read as the cause of
  the discover failure.** `~/.local/bin/notify` (WeChat via Server酱) does not exist; the call was
  always caught and queued to `data/notifications.json`, but it ran with `stdio: 'inherit'`, so a
  full `Cannot find module` trace landed in the daily log — and `daily-pipeline.js`'s
  cause-extractor greps the tail for `/error|Error|failed/` and reported that trace as **the reason
  the stage failed**. It cost real diagnosis time: a module-resolution error looked like the
  discover bug while the actual cause was the normalize sub-phase above. Now `existsSync` is checked
  first and the child's stderr is piped, not inherited.
  ⚠ Consequence to keep in mind: **the cause-extractor reports the loudest-looking line, not the
  cause.** Treat it as a pointer, not a diagnosis.
- ⚠ **A single daily slot means a missed slot is a missed day** — if CDP is down or the budget
  is already spent at 18:00 UTC, the wrapper exits 0 and does not retry. The earlier 4-hourly
  schedule caught the first usable window instead. If that bites, add hours to the array and
  gate on "no successful run today" (`data/daily-state.json` already records it) rather than
  widening the UTC gate.
- ⚠⚠⚠ **The research → integrate handoff was SEVERED by the loop merge.**
  `integrate-eligible` takes a family's CANDIDATE from the product shelf (`validated_strategies/`),
  and the retired `autoenhance-recorder` had archiving there as its step 4 — but `family-recorder`,
  the merged loop's recorder, never inherited it. So a family researched by `/run-family` never
  reaches the shelf, falls back to its best INGESTED ledger member (usually not the book its VAL
  validated), and reads `blocked` forever. The seven artifacts on the shelf today were each put
  there by a one-off `study/<family>/archive*.js` — eleven such scripts exist, which is the symptom.
  Restored in `family-recorder` + `/run-family`, with the header fields the gate actually parses
  (`family`, `expId`, `harness_epoch`, `train_objective` whose gloss must contain `sharpe <n>`,
  `sharpe_val`, `gate_val`). ⚠ A FAILED VAL is archived too, with `gate_val: fail` — the shelf
  records what reached validation, and the gate filters on that field.
- ⚠ **The cron used to be unable to reach the last two stages**, and `--plan` reported
  `research 0` and looked finished while candidates waited. **Integrate was fixed 2026-10-17**
  (`scripts/run-integrate.sh` + first in `PRIORITY`); **OOS stays HUMAN ONLY by design** — it
  spends an irreversible test, so `--plan` prints its remaining count and never dispatches it.
- **OOS readiness accepts a PROMOTED candidate with no `--family`.** Integration's primary success
  (outcome 2) is a MERGED candidate spanning two families, so a family-keyed check made the one
  artifact a round exists to produce untestable on the final surface. The register is consulted
  first; `--family` is demanded only when the candidate is not promoted anywhere.
  ⚠ That path was briefly dead on arrival: `oosCandidateId` was declared in the budget block
  *below* the readiness block, so it hit a temporal dead zone — and a bare `catch` **swallowed the
  ReferenceError**, making every promoted candidate read as "not promoted" while the code looked
  like it worked. Hoisted, and the catch now reports.
- **The three stage hand-offs, and the one that was missing** (verified 2026-10-17):
  | new fact | what reopens | mechanism |
  |---|---|---|
  | a member is ASSIGNED to a family | `research` | `consumption.staleFor` compares the stamped `memberHash` with `memberState(family)`, which hashes the sorted `family:` members read from `wiki/strategies/*.md` — so an assignment changes the hash. This is why `assign` outranks `normalize`. |
  | a family gets a NEW BEST VARIANT | `integrate` | `integrate-queue` dispositions on `candidateId` (`a.champion.sourceFile`), never on the family — a new best variant is a new id, so it is neither promoted nor rejected and becomes an arrival. ⚠ It only becomes a new id once the variant reaches the **product shelf**, which is `family-recorder`'s archive step. |
  | integrate PROMOTES a candidate | — | **nothing, before `utils/oos-queue.js`.** `--plan` printed only `oos N test(s) left`, a count of BUDGET, so "integrate shipped something" and "something awaits the final surface" were facts a human joined by hand out of an append-only register. |
  `node utils/oos-queue.js` derives the join: each universe's CURRENT promoted candidate with
  `state: ready | tested | blocked`, and the planner now names the ready ones.
  ⚠⚠ **It reports and never dispatches, by design.** The reserve is 2 tests per bench and 1 per
  candidate ABSOLUTE. When integrate supersedes a candidate with a slightly-changed one, testing
  the new one is a SECOND look at the same held-out window — the exact failure the VAL budget and
  `harness.md` both name: selection on the last clean surface, one look at a time. So a superseding
  candidate shows as `ready` and whether that is worth one of two tests stays a human judgement.
  `oos` is absent from `PRIORITY` and stays absent.
  ⚠ The queue also **flags a candidate below the stage gate**, because the budget says a test is
  *permitted*, never that the candidate deserves one — and `integrate-eligible` checks the VAL
  sharpe, not the champion's TRAIN sharpe. Live: 红利低频 is promoted and OOS-ready at TRAIN sharpe
  **1.46** against a 1.5 gate.
- ⚠⚠⚠ **A promoted RAW member cannot be OOS-tested as itself — `strategies/` carries no pins.**
  Found preparing 红利低频's test, and it would have made the new OOS stage dispatch a session that
  could not run. A universe may promote a raw ingested member (that is what `integrate-eligible`
  names when a family has no shelf product), but `strategies/` is the immutable raw layer:
  93379f98 is missing `order_volume_ratio`, so the executor refuses with **UNPINNED-STOP** before
  spending anything. It does not inject pins — only `strategy-normalize.js` (into a temp copy) and
  `enhance/strategy_template.py` supply them — and the normalizer never passes `--allow-oos`, so
  there is no route to the holdout window through it either. 大小盘轮动's OOS worked because its
  candidate was a BUILT product (`validated_strategies/dxp-imp-1.py`), which carries all three.
  **The runnable form is the family's pinned baseline** (`study/<family>/baseline.py`), which is
  also the artifact its VAL ran — the stored curve `study_红利低频_baseline__val__e6` is the proof.
  Run that and pass **`--source-file <candidateId>`** so the budget, the promoted register and the
  stored curve all key on the BOOK rather than the copy (verified: the charge landed on
  `strategies/…93379f98.py` and the curve on `…93379f98__holdout__e8`).
  `utils/oos-queue.js` resolves this per row (`runFile`, `runVia`) and reports `unrunnable` when
  no pinned form exists, so the stage never dispatches into a refusal.
- ⚠⚠⚠ **BOTH OOS tests on epoch 8's bench are spent, and BOTH products FAILED out of sample.**
  | family | TRAIN | VAL | OOS |
  |---|---|---|---|
  | 大小盘轮动 | 3.51 | 1.88 | **−0.21** |
  | 红利低频 | 1.46 | 2.05 | **−0.51** |
  红利低频 (`hlld-oos-1`, 2026-01-01..2026-10-16, 188 trading days): total **−2.47%**, annual
  −3.12%, sharpe **−0.51**, maxDD 16.20%, objective −0.1932.
  ⚠ **This one is NEW INFORMATION, not a confirmed caveat** — the distinction declared before the
  number existed. 大小盘轮动's product header already said「no evidence this beats the base out of
  sample」and its pool was hindsight-selected, so a weak result confirmed a stated caveat. 红利低频
  declared no such caveat: it screens 股息率 top-25% + 营收>1e8 + profitability rather than a
  hand-written list, its realizability is **3** (the best measured), the 2e6 liquidity floor is
  **inert** on it, and its per-year sharpe is positive in BOTH train years (1.18 / 1.67). So the
  negative cannot be explained away as pool selection: the dividend edge itself did not hold in
  2026.
  ⚠ Two of two is not a sample, but it is the only out-of-sample evidence the repo has, and it
  points at the selection process rather than at either family. The reserve is exhausted until a
  bench change; nothing is left to test with.
- **Are the DERIVED queues reliable?** Measured: `queues()` is **deterministic** across calls and
  costs **~292ms**. Their strength is structural — recomputed from the wiki and the ledgers every
  time, so they cannot go STALE. ⚠ They can still be WRONG in their LOGIC, and were twice on
  2026-10-17 (research reopening families that had declined their VAL; normalize counting
  non-work as depth) — but a logic bug is fixed in one place, whereas the FILE-backed queue's
  contents went wrong and needed `normalize-sync` to exist purely to reconcile them, and still
  accumulated 4 immortal entries for weeks. **So do not add a file for the derived three**: a
  second copy is what the `study/manifest.json` trap was (manifest said 14 done, ledger said 14
  stale, a dispatch would have found nothing and exited 0). What files give that derivation does
  not is a RECORD of what the queue said and whether dispatch acted on it — that is
  `data/daily-state.json`, and it is the thing to extend if this bites again.
- ⚠⚠ **`family-queue` holds a family whose CHAMPION RESTS ON A MINORITY of its members.** Added
  2026-10-18 after a measured near-miss: epoch 9 invalidated every row, the chain re-planned to
  `research` after its first normalize batch (research outranks normalize by design), and the
  family it picked was **小市值 with 37 members and exactly ONE measured** — so `championSharpe`
  5.77 was a 1-of-37 sample presented as the family's champion, and the next budget rollover would
  have gone to experiments built on it.
  ⚠ **A fixed FRACTION would be the wrong rule.** Partial coverage is normal and permanent —
  打板短线 runs at 9 measured of 25 assigned, because 15 have no ledger row and two are terminal
  failures — so a 50% bar would block it forever. What distinguishes the bad state is what is
  ACTIONABLE, so the rule is a comparison with **no magic number**:
  **more members awaiting measurement than measured ⇒ the champion is PROVISIONAL, research waits**
  (`reason: 'awaiting-measurement'`, excluded from `due`, still reported in `all` with the
  arithmetic in its `note`). Measured the day it was written: 小市值 36 vs 1, 五福闹新春 23 vs 2,
  多因子ML 21 vs 0, against 打板短线's steady state of 1 vs 9.
  ⚠ It is **self-clearing and cannot deadlock**: a compile-error or incompatible row is TERMINAL,
  so a permanently unrunnable member leaves the pending queue and never counts toward the hold.
  Only `normalize` can satisfy it, and it always can.
  ⚠⚠ **It OVERRIDES the `integrate-blocked` reopening, including `never-researched`** — dispatching
  a never-researched family whose members are all unmeasured is the worst case, not an exception.
  The precedence is deliberate and the test states why: the stranding the reopening replaced was
  **permanent and invisible**, whereas this hold is **temporary and reported**. A test asserts the
  hold is visible, because a silent hold would recreate the very failure the reopening exists for.
- **Two of the five queues are FILES, three are DERIVED.** `data/pending-normalize.json` and
  `data/copy-queue.json` are real files the normalize/fetch pipelines themselves read. The
  research, assign and integrate queues are **derived** — research from `wiki/families/*.md` +
  `data/consumption.tsv` (`utils/family-queue.js`), assign from pages with no `family:`
  (`utils/family-assign.js`), integrate from `data/promoted.tsv` + the exit gate
  (`utils/integrate-queue.js`) — no file, and **the agent loops do not read them**.
  (enhance/study were the derived pair before `/run-family` merged them. ⚠ They are **NOT**
  reachable any more: `scripts/auto{enhance,study}-loop.sh` invoke `/run-enhance` and `/run-study`,
  **skills that no longer exist**, so a `--stage enhance` dispatch would start a session that can
  do nothing and exit 0. The planner now refuses both with `blocked` and points at `/run-family`;
  the wrappers, pins and their 8 orphaned agent contracts are left in place as history, and those
  contracts still carry epoch-5-era facts.)
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
- **The agent topology has THREE patterns, not one** (mapped 2026-10-17). Five process layers run
  before any LLM does: `launchd` → `scripts/daily-pipeline.sh` (DST gate, shared lock) →
  `utils/daily-pipeline.js` (**deterministic — picks the stage, no LLM**) →
  `scripts/run-<unit>.sh` (session pin, CDP + budget preflight, orphan sweep) → `claude -p`
  (**the main agent, running one skill**) → `Agent`-tool subagents.
  | step | main agent | subagents |
  |---|---|---|
  | discover / normalize | — | pure Node, no LLM |
  | assign | session via `run-assign.sh` | none — reads `.claude/agents/family-assign.md` as a RULEBOOK |
  | research `/run-family` | session via `run-family.sh`, pinned per family | **5**: understand + improve (concurrent) → gatekeeper → executor → recorder |
  | integrate `/run-integrate` | session via `run-integrate.sh`, pinned per universe | `integrate-merger` ×1 |
  | screen `/run-screen` | interactive | `post-screener` × N batches of ~40, concurrent |
  | oos `/run-oos`, daily `/run-daily` | interactive | none — `/run-daily` orchestrates PROCESSES |
  ⚠⚠ **`/run-family` drew its five roles and then played them itself.** The skill's loop diagram
  (generator A/B → gatekeeper → executor → recorder) was written as a dispatch spec and read as a
  phase description, so a session did the reading, the experiment and the write-up in one context
  and **5 of 16 agent contracts were referenced from nowhere** — only `post-screener`,
  `integrate-merger` and `family-assign` were reachable at all. Fixed by making the skill name each
  `subagent_type`; a test now fails if a role loses its dispatch or its contract.
  ⚠ **What the orchestrator never delegates**: loop control, the backtest budget, that only ONE
  executor runs at a time (the completion signal is the account-wide running count, and concurrent
  runs have returned identical metrics for different strategies), **VAL** and the `valDeclined:`
  decision. The generators are the only safe fan-out — they are read-only (`tools:` has no Write).
  ⚠ Subagents are **ephemeral** and never message each other; the handoff is on disk
  (`study/<family>/queue.json`, `findings.tsv`, the family page), which is what makes a round
  survive a budget stop. A subagent's return is a REPORT — if it disagrees with the ledger, the
  ledger wins.
  ⚠ The 8 `autostudy-*` / `autoenhance-*` contracts are **orphaned**: superseded when the two
  loops merged, and referenced by nothing, not even their own wrapper scripts, which still exist
  and are `--stage`-reachable. Left in place, not deleted.
- **Sessions are headless under cron, interactive for humans**: `auto*-loop.sh` runs
  `claude -p --resume <uuid>`; `auto*-interactive.sh` runs `claude --resume` / `--session-id`
  in a TUI. The cron **resumes** rather than cold-starting, so the agents keep context.
- The daily run **chains** stages while budget remains, re-planning between each — a normalize
  pass changes the ledger, which can legitimately promote study above normalize mid-run.
  `--once` runs a single stage. **`/run-daily`** is the skill entry point; stage selection stays
  in the deterministic planner because it is arithmetic with one right answer, and the skill
  handles only what needs judgement (a blocked stage, a loop that exits 0 having done nothing).
- **The daily cron picks ONE stage by queue priority — later stages outrank earlier ones**:
  `oos > integrate > research > assign > normalize > discover` (`PRIORITY` in
  `utils/daily-pipeline.js`).
  ⚠ `integrate` was added 2026-10-17; before that the funnel ended one step short of its own
  product — a family that cleared `/run-family` and VAL had nowhere to go, so the exit gate
  accumulated candidates while the cron spent every minute admitting more raw strategies.
  Its wrapper is `scripts/run-integrate.sh`, pinned per UNIVERSE in
  `data/integrate-sessions/<universe>.txt`, and it CAN cold-start a universe that has never had a
  round (same arrangement as `run-family.sh`, one level up).
  ⚠⚠ **`oos` now LEADS PRIORITY (user decision, 2026-10-17), reversing the earlier design.** It
  was excluded because it spends an irreversible test on the last clean surface, and that reasoning
  has not changed. What makes automating it defensible is that the ceiling lives in CODE rather
  than in the absence of a queue: `oos-budget` refuses past 1/candidate or 2/bench before the
  browser opens, `OOS-READINESS` refuses an ineligible family, and `oos-queue.ready()` reports a
  candidate only if it is untested AND within budget AND has a **pinned runnable artifact**. So
  when the bench's tests are gone the queue is empty, depth is 0, and the stage cannot be picked
  until a bench change — that is the stop, not a human remembering. It proved itself the same day:
  both tests were spent and the queue went to `0 ready`.
  ⚠ The two PROTECTION overrides stay human-only env vars and the wrapper never sets them:
  `JQ_ALLOW_OOS_OVERBUDGET`, `JQ_ALLOW_OOS_UNREADY`. `scripts/run-oos.sh` is pinned per FAMILY in
  `data/oos-sessions/<family>.txt`.
  A pull
  system: finish what is in the pipe before admitting more, because the backtest minutes/day are
  the binding constraint and an idle research-ready family is a worse use of them than a raw
  strategy nothing can act on yet.
  ⚠ **There is no "advance to the next stage" logic** — `runChain` RE-PLANS every iteration and
  takes the highest-priority non-empty queue. So 2026-10-04's normalize → assign → research was
  emergent, not sequenced: normalize produced strategies with no `family:`, which filled the
  higher-priority assign queue; assign gave a family a new member, which filled research.
  ⚠ **Consequence, by design**: while any family is research-due, normalization does not run.
  `--plan` prints every queue's depth so it is visible; `--stage <name>` overrides for one run.
  A stage that runs without draining its queue **cedes its turn** to the next stage rather than
  ending the day (it used to `break`, which cost 2026-10-04 its remaining 124 minutes).
- ⚠⚠ **THE CHAIN STOPS WHEN THE BUDGET IS GONE** (user decision, 2026-10-17). It used to stop on
  five other things, each able to end a day with minutes unspent: `maxStages = 6` (six EXECUTIONS,
  with six stages in PRIORITY — so a stage needing several passes could not get them; normalize
  takes 40 files an invocation), and `outcome` in `empty` / `error` / `blocked`.
  Those three now **cede**, exactly as `no-progress` already did, and `maxStages` is **40** — a
  backstop, not the bound.
  ⚠ **Ceding is safe because of the no-progress guard**, which is the load-bearing part: a stage
  whose own run did not move its own queue is added to `stalled` and skipped for the rest of the
  chain. A failing stage therefore costs ONE wasted re-plan, not an infinite loop.
  ⚠⚠⚠ **That guard measured the WRONG INTERVAL and threw away a whole day.** It compared the depth
  at a stage's NEXT pick against the depth at its PREVIOUS pick — an interval spanning other
  stages, which in a funnel is precisely where a downstream queue gets REFILLED. Measured on the
  2026-10-17 18:00Z cron (`data/daily-logs/2026-10-17_110009.log`):
  `assign` drained 1→0, then normalize produced two strategies with no `family:`, so assign's next
  pick read 「queue still 2 after running」and stalled it; `normalize` drained 2→0, then discover
  admitted its 3 daily fetches, so normalize read 「queue still 3」and stalled too. Both stages had
  done exactly their job. With assign/normalize/discover all "stalled" the chain reported
  **EXHAUSTED after 7 minutes at used=2 of 180**, leaving 3 runnable strategies and 178 minutes.
  **A downstream queue growing because an upstream stage fed it is the funnel WORKING** — it is the
  one thing this pipeline exists to do, and the guard was reading it as failure.
  Now the verdict is the stage's **own** delta, sampled the moment it returns
  (`const after = depth(p.stage, queues())`), before anything else can run; a stage that moved its
  own queue stays eligible however much later work arrives.
  ⚠ Consequence: termination no longer rests on `stalled` growing to `PRIORITY.length` — a
  productive stage can be re-picked indefinitely, which is the intent. The bounds are the budget
  gate, the queue draining, and `maxStages` as a backstop.
  ⚠ `dry` is exempt: it executes nothing, so no depth can move and every stage would stall.
  ⚠ **`held` still breaks and must**: it means `state.beginRun` refused because another run owns the
  in-flight claim. That is a lock, and proceeding would let two runs spend the same budget.
  `exhausted` still breaks too — every queue empty means there is nothing for the minutes to buy.
  ⚠⚠ **`discover` runs at most ONCE per chain.** It is the stage that ADMITS work rather than
  consuming it, `strategy-daily.js`'s own limit is **20 fetches per RUN**, and it costs no
  backtest minutes — so an unbounded chain would re-run it to `maxStages` and admit up to 800 in a
  day, burying the normalize queue it is meant to feed. Consuming stages may run as long as the
  budget allows; the admitting stage may not.
  ⚠⚠ **The limit was 3/day until 2026-10-17, when the ADMISSION RATE overtook the budget as the
  binding constraint** (user decision). Measured that day: the chain ran nine stages,
  `data/pending-normalize.json` drained to **`[]`**, the deferred pool held 20 entries with **0
  retryable** (each past the 3-attempt ceiling or already tried at a cap ≥ the current one), and the
  day ended at **used=36 of 180 minutes** — while **720 strategies sat uncopied**. At the measured
  ~3.3 min/backtest, 3 fetches is 10–15 minutes of work against a 180-minute budget, so ~80% of
  capacity went idle with the funnel's mouth as the only cause. 3/day was right at 60 min/day with
  ~70 queued; neither premise still holds.
  ⚠ The raise makes the **once-per-chain brake the only thing bounding the daily total**, so it is
  now more load-bearing, not less: the per-run limit caps one invocation, the brake caps the
  invocations. Do not relax both.
  ⚠⚠ **What the budget gate CANNOT see**: an agent stage that spends no backtest minutes. A research
  round taking the Step-0 early exit costs **zero** (measured 2026-10-17: 小市值 → `logged-only`), so
  the budget will never stop it — only its queue draining will, and `maxStages` is now the only
  bound. That is token spend, not JQ spend. If it bites, the fix is a **separate cap on agent
  dispatches**; shrinking `maxStages` would re-break the thing this change fixed.
- ⚠ **Some stages cost NO backtest minutes, and the day's budget stop now says so.** `discover`
  was always exempt; `assign` and a SEED-headed `integrate` round were not, so a universe could
  ship nothing all day for want of minutes it was never going to use. A seed reads the champion's
  figures out of the ledger and writes one `promoted.tsv` row — no browser, no backtest. The
  exemption is narrow: it is the PLANNED stage that must be free, and a free stage on a spent
  budget runs **alone** (forced `--once`) rather than chaining into normalize, whose first act
  would be to ask for minutes that are gone.
- ⚠ **The cron can RESUME study/enhance but never cold-start them.** They are Claude agent
  loops; their wrappers resume a session pinned by a human
  (`data/auto{study,enhance}-session.txt`, format `<branch>\t<uuid>`). The loop script refuses
  a pin from another branch and **exits 0** — so checking only that the file exists reports
  success every day while starting nothing. `daily-pipeline.js` checks the branch too, reports
  `blocked`, **cedes the budget to the next stage**, and exits non-zero so a dead cron is
  visible. ⚠ This applies to the LEGACY `--stage enhance|study` paths; the automatic order
  runs `research`, whose wrapper pins per FAMILY in `data/research-sessions/<family>.txt` and
  CAN cold-start one that has never been researched.
- ⚠⚠ **The ledger's column order has ONE owner: `utils/ledger.js`.** Eight files hard-coded
  numeric indices into `harness/normalize-*.tsv` (`c[0]`..`c[13]` — family-queue,
  integrate-eligible, component-scan, wiki-family-build, normalize-daily, stockcost-affected,
  wiki-type-build, daily-summary, consumption-seed), which is the data every family §3 table, the
  integration bar, the exit gate and champion resolution are computed from. A column inserted
  anywhere but the end would silently have turned `sharpe` into `annual_pct` in all of them with
  nothing failing — and it has drifted once already (`normalize-ledger-rebuild.js` emits 13
  columns against the ledger's 14). `ledger.normalized()` yields named rows; `ledger.IDX.<name>`
  gives a NAMED index for the two readers that need the raw string
  (`wiki-family-build` renders sharpe/annual/maxdd straight into §3, so parsing and
  re-stringifying would reformat a stored `1.460` to `1.46` and show up as a spurious wiki diff).
  A test asserts `COLS` against the live header and fails if any util re-introduces `c[9]`.
  ⚠ It owns the SCHEMA, not the iteration policy — the readers genuinely differ (newest-epoch-per-
  file vs. has-a-curve vs. best-objective-among-valid) and collapsing them would trade eight
  legible loops for one function full of flags. Migration verified byte-identical on every
  consumer, including a full wiki rebuild (only the `updatedAt` stamp moved).
- **`utils/frontmatter.js` is the one frontmatter reader.** Ten files carried the same regex and
  four of them trimmed, so some call sites compensated with their own `.trim()` and others relied
  on no page ever having a trailing space. Not yet a live bug (zero such values in the wiki, and
  every uncompensated site feeds `parseFloat`/`parseInt`/`.match`) — but `family:` and `universe:`
  are compared by EQUALITY across those files, so one hand-edited page would make a family vanish
  from one reader and not another. `field()` always trims; `link()` also strips `[[ ]]`.
  ⚠ `wiki-family-build`'s block parser and `setFmKey` WRITER stay where they are, on purpose.
- ⚠⚠ **`utils/consumption-seed.js` had no entry-point guard, and it is NOT idempotent.** A bare
  `require()` of it (typed to check the module still loaded after a refactor) **appended 82
  duplicate rows to `data/consumption.tsv`** — tracked, append-only, and the ledger the VAL and
  OOS budgets are computed from. The budgets were unharmed (every row was `stage: normalize`,
  which neither reads) and the write was uncommitted and reverted.
  **Why its dedup cannot work**: `consumption.record()` de-duplicates on `(stage, key, runId)`,
  `runId` is a constant, but the KEY comes from `data/copy-queue.json`'s `copied` map — rebuilt
  from scratch by every discovery run, holding **re-minted postIds**. Exactly the rule CLAUDE.md
  states: *never key a store, a dedup or a join on an id.*
  ⚠ **The guard audit behind "every entry point in `utils/` needs one" searched for files reading
  `process.argv`**, and this one takes no arguments. A test now checks for top-level script code
  instead, which is the property that actually matters.
- ⚠⚠ **A second, WRONG HTTP client lived in four files** and has been removed (2026-10-17).
  `utils/fetcher.js`, `utils/strategy-copy.js`, `utils/strategy-comments.js` and
  `backtest/runner.js` each hand-rolled `https`/`curl` against joinquant.com — the one call this
  repo must never make, because the geo-block answers **HTTP 200 HTML** and `JSON.parse` then
  throws into a `catch` that reports "no source" / "no comments". `node index.js community …` is
  a documented entry point that reached it. Three of them also shipped credential problems: a
  **fresh password login per call with the password on the shell command line** (readable via
  `ps`), a hard-coded phone number as the default username, and session cookies written to a
  predictable `/tmp/jq-*-cookies.txt`. `runner.js`'s fallback additionally **could never settle** —
  its catch did `return null` inside a `new Promise` executor, so an `await` on it hung forever.
  All four now call `utils/jq-http.js`, which needs no credentials at all (it reuses the CDP
  session) and **throws** `GeoBlockedError`.
  ⚠ `jq-http` takes no `headers` option; passing one is silently ignored. The Referer that
  `strategy-comments.js` used to send was dropped rather than faked — the CDP fetch already runs
  inside a joinquant.com tab with `credentials: 'include'`.
- ⚠⚠ **A family can be `done` to the research queue and STUCK at integration's gate.** Measured
  2026-10-17: 8 of 13 families read `blocked` in `utils/integrate-eligible.js` while
  `family-queue` reported **0 due** — a family researched to exhaustion but never finalised on VAL
  has no new members and a consumption row, so it reads `done`, yet the only thing that can
  perform the missing step is `/run-family`. The funnel's last stage was waiting on its
  predecessor and its predecessor thought it was finished; four families (七星高照, 五福闹新春,
  多因子ML, 趋势技术) sat there with nothing able to notice.
  The fix is an **`owner`** on every gate verdict — which stage can clear it:
  `research` (the loop clears it unattended) / `normalize` (needs a measurement at the active
  epoch) / `human` (needs `JQ_ALLOW_REVAL` or a judgement) / `none` (a measured REJECTION).
  `family-queue` reopens **only** `research`-owned blocks, as `reason: integrate-blocked`, and
  `run-family.sh` tells the session it is a NARROW job (skill step 0b: do the one named step,
  re-check the gate, exit — do not reopen the generator loop).
  ⚠ `none` and `human` must never be reopened: an R=1 family re-entered daily would spin forever
  on a decision already taken, and a block the loop cannot clear makes every run exit having done
  nothing — this repo's recurring failure shape.
  ⚠ Whether a non-comparable VAL is `research` or `human` is **the VAL budget's answer**, not
  re-derived: `sameBench` false ⇒ a fresh VAL is allowed ⇒ research; an unrecorded epoch is
  UNKNOWN, and unknown blocks ⇒ human.
- ⚠⚠⚠ **"No VAL row" is NOT "nobody has done this step yet" — and reading it that way nearly spent
  a validation.** The `integrate-blocked` reopening (2026-10-17, the bullet above) treated
  `never validated` as a research to-do and reopened four families. Checked against what those
  families had actually recorded, it was wrong for **4 of 4** — every one had already decided not
  to spend its one validation, with the reason in §4:
  七星高照 「BLOCKED 是正确状态，不是待办」 (champion is a cross-family blend whose R=2 was scored
  for the pure rotation, and the pit-pool precondition RAN AND FAILED, so no level number including
  VAL is mechanism evidence); 五福闹新春 「不配花家族唯一一次验证」 (every built candidate is
  dominated by member 73b13d92); 多因子ML 「VAL 2024–25 对作者而言很可能是样本内」; 趋势技术
  「没有候选过 1.5 闸门」. The dispatch was live and the session already briefed with
  "finalize on VAL — one run" when this was caught; **nothing was spent** (VAL still `ALLOWED`,
  `used` unchanged, no backtest started). Beyond the VAL risk it was **non-convergent**: a Claude
  session dispatched at each family every day, forever, to re-derive the same answer.
  **Two defences, in order of trust:**
  1. **DERIVED** — a candidate that does not clear `stageGate('validate')` on TRAIN is never worth
     a validation, whatever anyone recorded. No field, nothing to keep in sync. Catches 趋势技术
     (sharpe −0.63), which is why that page needs no declaration.
  2. **DECLARED** — `valDeclined: <epoch>` + `valDeclinedBasis:` in family-page frontmatter, for
     the three whose reasons are about the **data** (a hindsight-selected pool, a VAL window inside
     the author's own sample, a candidate dominated by an existing member). None of that is
     derivable. A basis is REQUIRED and should name the clearing condition; three of the four do.
  ⚠ **The decline does NOT expire on an epoch bump** — most such reasons do not change when fills
  and fees do, and expiring it would re-dispatch a session to re-derive the same answer, which is
  the non-convergence being fixed. What reopens the family is a **new member** (`family-queue`'s
  own `new-members` reason, which does not consult this gate), because a new member can change the
  champion. Clearing it otherwise is a deliberate edit.
  ⚠ The four bases were **transcribed from each page's own §4 prose, not written fresh** — the repo
  has already paid for one guess-based rule that permanently discarded 287 of 549 strategies.
  `/run-family` step 0b now tells a session how to record a decline, which is the half that makes
  the loop converge instead of being re-dispatched.
- **`slow-skipped` stays TERMINAL in the normalizer** (making it retriable re-bills it every
  batch — the `no-trades` bug). The retry path is a separate **deferred pool**,
  `data/deferred.json`, drained only by the daily pipeline and only at a **higher cap than the
  one that already failed** — re-running at the same cap spends the same minutes to learn the
  same thing. 14 previously-stranded rows were seeded into it; ceiling is 3 attempts, after
  which they stay listed under `exhausted` rather than vanishing.
- **The caps live in the plist, not in the defaults.** `com.mohanshen.join-quant-daily` exports
  `USAGE_LIMIT=free` and `SLOW_SKIP_MIN=45` (the code defaults are 55 and 30, which is what a bare
  manual run gets).
  **`USAGE_LIMIT=free` means the ceiling IS the tier**, resolved from JQ's own reported
  `data.duration.free` by `utils/usage-limit.js` — not written down, because it has already
  changed once (60 → 180 at VIP) and a second copy would go stale. A plain number still works.
  ⚠ The limit only stops a backtest STARTING — one already running keeps billing — so the real
  ceiling is `limit + SLOW_SKIP_MIN`, now **225 worst case**. That overshoot is DELIBERATE
  (user's rule, 2026-10-06): holding the limit *below* the tier to protect it is what stranded
  the tail — that day stopped at `used=141` with 39 free minutes and 21 strategies pending,
  because nothing may start once `used >= limit`. Stop once usage is PAST the tier and let the
  in-flight run carry the overshoot; 2026-09-26 ran to 193 that way. Set a number (`135`) to go
  back to strict containment.
  ⚠ JQ settles `duration.used` when a run TERMINATES, not while it is in flight (measured: used
  stayed 0 across 19→22 min of wall clock), so no gate can observe spend mid-run — which is why
  the overshoot cannot be trimmed, only bounded by the cap.
- ⚠⚠⚠ **The daily summary's commit used to sweep the whole working tree.** `commitAndPush` ran a
  bare `git add -u`, which stages EVERY modified tracked file — so an automated run commits
  whatever a human has in progress. It did exactly that on 2026-10-17: a run whose only stage
  reported `budget-spent` (it started nothing at all) committed and **pushed 34 files, 19 of them
  mid-edit source files** across `utils/` and `backtest/` plus `CLAUDE.md`, under the message
  "daily: 2026-10-17 pipeline run". The content happened to be sound and tested; the message
  described none of it, and the work was unfinished.
  **Fixed**: both adds are scoped to `SAFE_ADD` — the paths a run PRODUCES — so `utils/`,
  `tests/`, `scripts/`, `.claude/` and `CLAUDE.md` can never be staged by a run. `SAFE_ADD` gained
  `harness`, `study`, `screen` and the four `data/*.json` queues, which had only ever been
  committed by the unscoped add; leaving them out would have stopped committing the ledger a
  normalize pass appends to and the findings a research round writes. Files modified but out of
  scope are now **named in the commit body** ("Left uncommitted (not pipeline output)") rather than
  silently taken or silently dropped. `SAFE_ADD` is exported so a test asserts on the real array —
  it used to be read by regex out of the source, which an apostrophe in its own comment broke.
  ⚠ **The DST hour gate lives in `scripts/daily-pipeline.sh`, not in the tool**, so a bare
  `node utils/daily-pipeline.js` runs, commits and pushes at any hour. That is deliberate (a human
  run is never blocked) and is why the scoping above matters: the tool's default is to commit.
  `--no-commit` writes the summary without pushing; `--dry` writes nothing.
  ⚠ The off-schedule run above left **no wrapper log line**, so it did not come through
  `daily-pipeline.sh` and its cause was not established — possibly a direct invocation from an
  interactive session. The fix does not depend on knowing: the hazard is that the default commits.
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
- ⚠ **The backtest log IS retrievable — the old note here was wrong.** `/algorithm/backtest/log`
  returns 400/empty only in its BARE form; with parameters it returns the full 日志 tab:
  `/algorithm/backtest/log?backtestId=X&offset=0&limit=2000&ajax=1` → `{data:{state,logArr[]}}`
  (23KB on a normal run). `/algorithm/backtest/error?backtestId=X&ajax=1` is the 错误 tab, where a
  Python traceback lands. `utils/backtest-log.js` wraps both; `--algorithm <id>` resolves the
  backtestId first, because ids are re-minted per request.
  The old claim shaped all of `study/_probes/`: every probe had to smuggle its answer out as a
  marker trade because nothing could read what the strategy printed. **That is no longer
  necessary** — though a control is still good practice, since `no-trades` and "the code path
  never ran" remain different things.
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
- **Epoch 9 (2026-10-18)**: ⚠⚠⚠ **MEASUREMENT CHANGE — the first since epoch 6.** User decision.
  **TRAIN 2022-01-01..2023-12-31 → 2024-01-01..2024-12-31**; **VAL 2024-2025 → 2025 only**;
  **OOS unchanged** (2026-01-01..today); **gate and every `stageThreshold` 1.5 → 1.0**.
  Costs, pins, slippage, capital, frequency and benchmark are **untouched**, so the frozen Python
  literals need no edit and `--verify` passes.
  **Rationale (user's)**: requiring a strategy to work across a five-year span is too strict and not
  necessary — what is working recently matters more, and realistically an edge has a short life
  because everyone crowds into the same trade. So the bench asks for recent consecutive
  performance (fit 2024, confirm 2025, hold 2026) instead of multi-regime survival.
  ⚠ `measurementPreservedFromPrevious: false` ⇒ `measurementValid()` rejects **every** row at
  epoch ≤ 8 and the whole library needs re-measuring. `sameBench(8,9)` is false, so **every family
  is granted a fresh VAL**.
- ⚠⚠ **Epoch 9 made the per-year integration bar DEGENERATE.** TRAIN is one calendar year, so
  「beat the best parent in EVERY train year」 is arithmetically a single **pooled sharpe
  comparison**: one year ⇒ one best parent ⇒ `parents-split-by-year` is unreachable. The basis
  stays `perYearSharpe` so the guard's code path, curve requirement and fallback reporting are
  unchanged — but **epoch 8's REASON is gone with the second year**. Read a pass as 「better in
  2024」, never as 「survives a regime change」. The two cases epoch 9 cannot express (win one year
  / lose the other; a bar split between parents) are replaced in the tests by the degeneracy plus
  a guard that the multi-year logic survives in code for a future widening.
- ⚠⚠ **The OOS reserve RESETS while the data does not.** `oos-budget` counts per BENCH, so epoch 9
  grants 2 tests again over the **same 2026 window** epochs 3–8 already looked at twice (大小盘轮动
  −0.21, 红利低频 −0.51). The **per-candidate limit of 1 is absolute across epochs** and still
  protects an individual book; what resets is how many DISTINCT candidates may touch 2026.
  Defensible only because selection now happens on 2024 so the candidates will be different books.
  The tool says it out loud: `2 test(s) charged to EARLIER benches (not restored)` — and that line
  exists **only because `data/consumption.tsv` was kept**.
- ⚠ **A one-year TRAIN overfits faster per unit of evidence.** The compensation is that VAL is a
  full adjacent year and the OOS reserve is untouched, so a 2024 fit must still survive 2025.
  The epoch-7/8 analysis that motivated per-year domination (2022 supplying a median 62% of
  log-growth; a candidate trading one year off against the other) has **no analogue** now.
- ⚠⚠ **Two hardcoded copies of the window were found by the suite going red**, both the class the
  epoch config exists to prevent. `kb-stub.js` stamped the literal `window: "TRAIN 2022-2023"` into
  the `normalized:` block — the ledger's **durable backup**, and what `normalize-ledger-rebuild.js`
  reads back to recover a row's window — so it would have labelled 2024 measurements as 2022-2023
  and had them reconstructed as fact. Now derived via `kb-stub.windowLabel()` (`TRAIN 2024`), and
  `WINDOW_SPEC` derives the ACTIVE labels while **keeping the historical literals**, because old
  pages are a rebuild's input and must still decode. Two test fixtures also generated curves pinned
  to 2022/2023, so under epoch 9 they fell entirely outside the window, `yearlySplit` found no
  overlap, the bar fell back to pooled, and **nine tests failed for reasons unrelated to what they
  assert** — a fixture pinned to one epoch's calendar silently stops exercising the thing it names.
- ⚠ **`wiki-epoch-repair` reported 193 restamps as `epoch X -> X` no-ops.** The block carries the
  window label and the gate text as well as the epoch, both derived from the ACTIVE harness, so a
  bump that moves a window or a threshold makes every page need a rewrite while NO page needs an
  epoch change. Changes now carry a `kind` (`epoch` / `metrics` / `window-label` / `restamp`) and
  only an `epoch` kind must move the epoch. Honest output: **187 label rewrites, 6 real epoch
  changes**.
- **`utils/epoch-reset.js --dry` clears what a measurement-breaking bump invalidated** — and the
  distinction that decides everything is **GENERATED vs HAND-WRITTEN**, measured before deleting:
  | kept | why |
  |---|---|
  | `wiki/strategies/*.md` | 248 pages, **228 carry a HAND-ASSIGNED `family:`**; the matcher abstains on 82% by design, so the label is human work and the family→member mapping is NOT regenerable. Only the `normalized:` line is stripped. |
  | `wiki/families/*.md` | 13 pages, 656K, 78 sections of mechanism/realism/edge/§4 analysis. The numbers are stale, the understanding is not. |
  | `data/consumption.tsv` | append-only audit trail — the only record that 2 OOS tests were spent. |
  | `validated_strategies/*.py` | source, re-measurable, already ignored on a stale epoch. |
  | `strategies/`, `screen/`, discovery | the input and the bench-independent layers. |
  Cleared: the ledgers (truncated to the header, so `ledger.COLS` survives), 419 curves, the 6
  generated type pages, `promoted.tsv`, `integrate-refusals.tsv`, the deferred pool.
  ⚠ `wiki-family-build` **REFUSED** to regenerate §3 on the empty ledger and was right to — it
  cannot distinguish a deliberate reset from the regression it exists to catch. **Do not `--force`
  it**; §3 regenerates on the first normalize batch via `normalize-sync`.
  ⚠ Six tests asserted the PRESENCE of generated artifacts. `{ skip: !existsSync(dir) }` was not
  enough for the type pages — the reset deletes the pages and leaves the directory, so an **empty
  directory** is the legitimate state. `rowsFromWiki` correctly rebuilds **0** rows once the blocks
  are stripped, and its window assertion had to stop demanding one epoch's literal dates: a rebuild
  is a HISTORICAL decoder.
- ⚠ **Epoch 6's re-measure set is 23, not 215.** `measurementValid()` is deliberately coarse and
  invalidates every pre-6 row, but the change can only move a strategy that set its OWN stock cost
  to something other than the bench's. `node utils/stockcost-affected.js` classifies all 215:
  **120** never called `set_order_cost(type='stock')` (they ran on JQ's default, which *is* the
  bench value), **57** declared bench-equivalent economics (the pin is a no-op), **37** differ —
  of which **22** are normalized rows — plus 1 unparseable treated as affected. `--enqueue` puts
  them at the head of `data/pending-normalize.json`. A missing `close_tax` counts as
  bench-default, not as a difference. 36 of the affected declared a *cheaper* commission than the
  bench, so the pre-6 ledger **flatters** them.
- **Stage thresholds**: every stage requires sharpe **1.0** since epoch 9 (`harness.stageGate(stage, sharpe)`).
  It was 1.5 from epoch 5; integration held 2.0 until epoch 7 dropped it — see below for why that
  never bound. ⚠ Never hard-code the number: it has moved three times (2.5 → 1.5 → 1.0).
- **Epoch 7 (2026-10-13)**: scoring only — the measurement bench is **byte-identical to epoch 6**,
  so `measurementPreservedFromPrevious: true` and **no row is re-measured**. Two changes, both
  about how a measurement is JUDGED:
  (a) `stageThresholds.integrate` **2.0 → 1.5**; (b) the integration bar moves from the pooled
  TRAIN objective to the **worst TRAIN calendar year** (`objective.integrateBar.basis =
  "worstTrainYear"`, read via `harness.integrateBar()`).
  ⚠ **The old integrate gate at 2.0 never bound on anything that could win.** Measured over the
  60 epoch-6 normalized rows: Spearman ρ(objective, sharpe) = **0.9836**, so the rank-bar and the
  gate never disagreed; **0 of the top-16 by objective** failed either threshold; and the only
  **3** rows between 1.5 and 2.0 score objective 0.2139–0.2970, far below any plausible incumbent.
- ⚠⚠ **`objective` is almost purely annual return** — Pearson r(annual%, objective) = **0.9698**
  across those 60 rows, with maxDrawdown supplying only **24%** of the spread the formula sees
  (sd 13.7 against 43.6). So "beat the best member's objective" was in practice "earn more than
  the biggest book in the universe", and a merge whose payoff is **robustness** (the 小盘 case:
  two implementations of ONE edge) had no channel to register at all.
- ⚠ **And pooled `annual_pct` over TRAIN is substantially a 2022 measurement.** Across the 13
  stored epoch-6 TRAIN curves, calendar 2022 supplies a **median 62%** of total log-growth and
  **63–71% for every top-8 book** (2022/2023 returns run 286/121, 182/52, 157/55, 156/55). TRAIN
  is 2022-01-01..2023-12-31 and 2022 was the small-cap rally, so a candidate that trades the 2022
  tail for 2023 steadiness **lost by construction** — which is exactly what the 全A round recorded:
  「combining relocates WHICH YEAR earns; it does not add」.
- The new bar is a **maximin**: candidate's worst TRAIN year vs the **most consistent** member's
  worst TRAIN year, same `(annual − maxDD)/100` computed **within** each year
  (`component-scan.yearlySplit()` / `worstYear()`). Not per-year domination — that lets one member
  own 2022 and another own 2023, so a candidate loses to a PAIR no single member matches.
  The pooled comparison is still **printed as evidence** (`pooledIsVeto: false`), never a veto.
  ⚠ Applied to the two completed rounds it **confirms both rejections** rather than rescuing them,
  and says why the prose could only gesture at: all three 全A candidates have a **negative** worst
  year (−0.0464 / −0.1014 / −0.4437). It also moves the 全A bar from 打板短线's 0.9668 to
  红利低频's **0.1224**, because the pooled leader's own worst year is **−0.3591** — it was never
  the right thing to beat.
- ⚠⚠ **`yearlySplit` must convert BEFORE slicing.** `dailyReturns()` runs on the WHOLE `cum`
  series and the RETURNS are then sliced by date. Clipping `cum` first measures the slice's first
  entry against a base of 1, folding every earlier year's cumulative gain into one day — on a book
  that tripled in 2022 the 2023 slice opens with a ~200% "daily" return and that year's annual,
  vol, sharpe and drawdown are all fiction that still looks like a number. Same family of error as
  differencing cumulative percentages instead of chaining them.
- ⚠ **A scoring-only bump nearly orphaned the whole curve store.** `seriesKey` embeds the
  measuring epoch, so a caller building a key from `config().epoch` asked for `__e7` and found
  nothing — all 280 stored curves are stamped `e6` and all 280 are still current.
  `series.loadComparable(sourceFile, window, epoch?)` walks `comparableEpochs()` newest-first and
  honours a `preferredEpoch` only if it is itself comparable, so a stale curve is never
  substituted for a missing current one. `component-scan.members()` and `series-backfill.js` were
  unaffected — they key on the **row's** epoch, not the active one.
- The integrate guard **falls back to the pooled rule when a curve is missing, and says so**
  (`flags: bar=pooled-fallback`). A bar that quietly relaxes because a file was absent is worse
  than one that is simply strict, so `candidate.json` now needs a `sourceFile` (or `seriesKey`) on
  the **candidate** as well as on every member; partial member coverage is also a fallback,
  because a bar computed over a subset silently omits whichever member might have set it.
- ⚠⚠ **A VAL filed under the wrong STAGE was invisible to the budget.** `priorValidations()`
  filtered `stage: 'validate'`, but `etfmom-005` sits under `stage: enhance` with
  `outcome: val-pass` and a blank epoch — and `data/series/enhance_candidates_etfmom-005__val__e6.json`
  proves the VAL-window run happened. So the budget reported **ETF动量 as never validated** while
  that family's own §4 had already written down 「`val-budget.js` 只读 `validate` 阶段，所以它误报
  ALLOWED——本族 epoch 6 的 VAL 视为已用」. The page knew; the code did not.
  Now an `outcome` matching `/^val-/` counts wherever it was filed. Deliberately **narrow** — the
  verdict shape, not any mention of "val" — because a false block is cheap to clear while a false
  permit silently spends the one window.
  ⚠ The data was **not** rewritten: `consumption.tsv` is append-only and `record()` stamps the live
  epoch on purpose, so no truthful epoch-6 row can be appended today. Fixing the READER fixes the
  class, and the blank epoch then blocks via the unknown-epoch rule, which is the right answer.
- **First OOS test spent, 2026-10-17: 大小盘轮动's product FAILED out of sample.** `dxp-oos-1`,
  holdout 2026-01-01..2026-10-16 (288 calendar / 188 trading days): total **−1.18%**, annual −1.49%,
  sharpe **−0.21**, maxDD **25.78%**, objective **−0.2727**. Curve reproduces the scrape exactly.
  **Not a crash but a stall** — roughly zero return over 9.5 months with a 26% round-trip drawdown —
  and the drawdown is **smaller** than VAL's 36.37%, so a 2024-02-style stampede did **not** recur.
  TRAIN → VAL → OOS is monotone: **3.51 → 1.88 → −0.21**. This converts the product header's own
  warning (「There is NO evidence this candidate beats the base out of sample. Adopted on TRAIN
  only.」) into a measurement: it does not beat the base, and does not beat zero.
  ⚠⚠ **Not a basis for re-picking the base.** The base was never tested on 2026; choosing between
  them on OOS is selection on the last clean surface; and the base is ineligible anyway (its VAL
  validated imp-1). Budget: candidate **absolutely** spent, bench **1 of 2**.
- ⚠⚠ **The rolling `holdout.end: "today"` was unrunnable by construction.** JQ refuses
  「结束时间不能大于前一个交易日」 — the end may not be later than the previous trading day — so the
  first OOS attempt compile-failed on a Saturday. It **charged nothing**, which is `oos-budget`'s
  "only a COMPLETED run is charged" rule proving itself on first use; had that been wrong, a
  syntax-level refusal would have burned half the epoch's reserve.
  `window()` now resolves `"today"` via `previousWeekdayISO()`. ⚠ Weekends only — there is no
  holiday calendar and there cannot be one, since `harness-config.js` is read outside any JQ
  session; a run adjacent to a long closure will be refused again, which is safe (loud, free) and
  fixed by stepping back a day.
  ⚠ Consequence of a rolling end: **two OOS tests on different days do not cover the same window**,
  so their numbers are comparable only to their own stated spans. Record the resolved dates.
  Also removed a dead second `todayISO()` in `strategy-post-backtest.js` — a second resolution of
  "today" beside the harness's is how the window logic drifted across seven files before.
- ⚠⚠ **A NOTE about an OOS test must not look like one.** `priorTests()` matched a bare `/^oos-/`,
  so a bookkeeping row (`stage: 'research'`, `outcome: 'oos-recorded'`) counted as a second test and
  pushed the bench to a false **2 of 2** — written one message after the skill warned against
  exactly that. `consumption.tsv` is append-only, so the READING was corrected, not the row: the
  outcome pattern is now the verdict shapes `record()` actually emits
  (`oos-sharpe` / `oos-completed` / `oos-pass` / `oos-fail`), while `stage: 'oos'` still counts
  whatever its outcome says. Record the research side under `stage: 'research'` with a neutral
  outcome.
- **`/run-oos` is the entry point for spending an OOS test** (`.claude/skills/run-oos/`). It
  pre-flights the candidate, declares the expectation BEFORE the number exists, hands the human the
  one gated command, then records the result.
- **`--allow-oos` replaced `JQ_ALLOW_OOS=1` as the window override** (user decision, 2026-10-16),
  so an **OOS run is now unattended** — the executor is already allowlisted as
  `Bash(node utils/strategy-post-backtest.js:*)`. The env form still works.
  ⚠ **Two protections deliberately stayed env vars**, so overriding a protection still costs a
  prompt: `JQ_ALLOW_OOS_OVERBUDGET=1` (the 1/candidate, 2/bench ceiling) and
  `JQ_ALLOW_OOS_UNREADY=1` (readiness). Agents set neither.
  ⚠⚠ **The compensating control: readiness moved from prose into code.** With no prompt, nothing
  was left to ask "is this candidate actually ready?" — so an OOS run now **requires `--family`**
  and is refused unless that family is `eligible` (`integrate-eligible.assess`), checked
  **before** the budget and before the browser, printing `OOS-READINESS`. The executor also
  **warns when the file passed is not the family's own candidate**, because eligibility validates
  the FAMILY, not the argument.
  This matters because the budget **counts tests without judging them**: all three of
  2026-10-16's near-misses (a VAL that validated a different book, a candidate that was the wrong
  artifact, a realizability score measured on another book) would have passed it and spent the test.
- ⚠ **The escape-hatch/flag split — and the one deliberate exception.** The FORM is the
  mechanism: `.claude/settings.json` matches by `startsWith`, so an `ENV=1 node …` prefix never
  matches a rule and always costs an approval prompt. That is why **operational knobs are flags**
  (`--usage-limit` and `--max-poll-min` were *converted* from env vars precisely so a run could go
  unattended — `strategy-post-backtest.js`: "avoids the `JQ_MAX_POLL_MS=…` env prefix, which
  breaks the allowlist and forces approval") while **escape hatches stayed env vars**. Measured
  2026-10-16: all 6 hatches (`JQ_ALLOW_OOS`, `_REVAL`, `_CONCURRENT`, `_UNPINNED`, `_CREDITS`,
  `_OOS_OVERBUDGET`) were env vars, and **0 of 86** allowlist rules carried an env prefix.
  **The exception**: `--allow-oos` (user decision, 2026-10-16) is the first hatch on the flag side,
  so an OOS run is unattended. The other five — including the two OOS *protections*
  (`JQ_ALLOW_OOS_OVERBUDGET`, `JQ_ALLOW_OOS_UNREADY`) — remain env vars, and a new hatch should be
  an env var unless someone decides otherwise.
  ⚠ **The budget could not substitute for the lost prompt**, which is why readiness had to move
  into code at the same time: the budget COUNTS tests without judging whether the candidate is
  ready, and all three of 2026-10-16's near-misses (a VAL that validated a different book, a
  candidate that was the wrong artifact, a realizability score measured on another book) would
  have passed it and spent the test.
- ⚠⚠ **The OOS budget was PRINTED and never ENFORCED, from epoch 3 until 2026-10-16.**
  `oosPolicy.maxTestsPerCandidate: 1` / `maxTestsPerEpoch: 2` existed only in
  `harness-config.js`'s console output and one test asserting the number went down. `assertNotOOS`
  guarded the **window**, but once `JQ_ALLOW_OOS=1` was set **nothing counted the tests** — so the
  repo's least recoverable surface was the only one with no budget, while VAL had `val-budget.js`.
  **`utils/oos-budget.js` now enforces two independent limits**, checked in
  `strategy-post-backtest.js` **before the browser opens** and recorded on completion:
  **per candidate = 1, ABSOLUTE** (any epoch — re-testing one book on the reserve after a bench
  change is still selection on OOS, one look at a time), and **per BENCH** for the repo-wide count.
  ⚠ Per bench, not per epoch NUMBER: a scoring-only bump hands back no fresh 2026 data, so it must
  not restore the reserve. That is the equality bug the VAL budget had, fixed here before it bit.
  ⚠ **Two separate switches**: `JQ_ALLOW_OOS=1` unlocks the window, `JQ_ALLOW_OOS_OVERBUDGET=1`
  only exceeds the budget. The window flag must not grant budget, or one legitimate first test
  would silently authorize an unlimited number. Both are human-only; agents set neither.
  ⚠ `touchesOOS(window)` is **shared** by the window gate and the budget gate — a second copy of
  that rule would drift, and the budget would stop watching exactly the runs it exists for.
  Only a **completed** run is charged: a compile-error or slow-skip saw no held-out data.
  An unstamped or mis-filed row still counts (`outcome` matching `/^oos-/` wherever it was filed),
  because the etfmom-005 mis-filing showed a stage filter can hide a spent test for weeks.
  ⚠ **An honest limit**: a bump that *does* change the measurement hands back no new data either —
  the same nine months re-priced. The declared policy says "per epoch", so that is what is
  implemented; what genuinely helps is that the reserve is a **rolling** window
  (`holdout.end: "today"`), so real calendar accumulates. Weigh that rather than trusting the
  counter as a statement about leakage.
  `consumption.js` gained the **`candidate`** kind for this; `stage: 'oos'` was already declared —
  the schema had anticipated the stage but not the entity it belongs to.
- ⚠⚠⚠ **The VAL budget was keyed on epoch EQUALITY, so two scoring-only bumps silently re-granted
  six validations.** `val-budget.check()` filtered prior VALs with `e.epoch === epoch`. Epochs 7
  and 8 changed only how results are JUDGED and left the measurement bench byte-identical, so an
  epoch-6 VAL is a current result — yet at epoch 8 **every** family read `ALLOWED
  (first-of-epoch)`, including all six that had already validated. The single most protected
  resource in the repo was handed back by a bump that measured nothing.
  Exactly the bug `measurementValid()` was introduced to fix in the normalizer's
  `rowEpoch === ACTIVE_EPOCH` done-check; the VAL budget never received it.
  **The rule is one VAL per (family, BENCH)**: `harness.sameBench(a, b)` asks whether measurement
  was preserved across every bump between two epochs, order-independently. The inverse still
  works — epoch 6 did change fills and fees, so an epoch-5 VAL correctly does **not** block, and a
  family is never stranded on a bench that no longer exists. ⚠ `sameBench` is deliberately
  separate from `measurementValid` because the budget must honour the epoch it is ASKED about, not
  only the active one.
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
- ⚠ **A `crash` row means the EXECUTOR produced no `SUMMARY` line — not that the strategy
  errored.** Every completion path (completed / slow-skipped / compile-error / no-trades) prints
  one, so a missing SUMMARY means the child died or refused before reporting. On 2026-09-23 that
  was the CONCURRENCY GATE: it prints `CONCURRENT-STOP` and returns before `reportResult`, the
  normalizer only knew `USAGE-STOP`, and six refusals in a row became six `crash` rows and a
  circuit break blamed on "JQ rate-limit or session drop" — the session was fine, something was
  simply still running on the account. The normalizer now recognises `CONCURRENT-STOP` and stops
  the batch without recording a failure, and a genuine crash appends the child's last lines to
  `data/normalize-crashes.log` instead of leaving an all-empty row with no cause.
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
- Pipeline 2's backtest window is parameterized via `--window train|val|holdout` (or
  `--start/--end`), set through the `newStrategy` URL params. The reserve is hard-blocked
  (`OOS-BLOCKED`) unless `--allow-oos` is passed — see the OOS notes above and `/run-oos`. No
  window flag = JQ default range (ad-hoc).
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
- ⚠⚠⚠ **A 100× UNIT ERROR inflated 小市值's headline by ~8.6×, and it is LINEAGE-WIDE.** Found by
  the research loop (`study/小市值/findings.tsv` q-e6-13 … q-e6-19), verified independently
  2026-10-17. `get_current_tick`'s `a1_v`/`b1_v` is in **SHARES**, and three books multiply by 100
  as if it were **lots**:
  `money = a1_p * a1_v * 100`. So the advertised gate 「买一档金额 > 5万」 actually means
  `money > 500` and rejects almost nothing.
  **Corroboration (not inference)**: two unrelated authors in the same corpus compute depth money
  with no `*100` — `61c9c428.py:568  seal_amount = tick['b1_v'] * tick['b1_p']` and
  `c18c86c5.py:1206  df['a1_p'] * df['a1_v'] + df['b1_p'] * df['b1_v']`. The loop's own a-priori
  argument also holds: a bid-1 volume of 100/200/300 is only sensible as shares (1 lot = 100
  shares is the minimum), and 47,200 lots would be ≈¥34.9M resting on a micro-cap bid.
  **Measured cost on the base 7a1c225f** (epoch 6): objective **1.3861 → 0.6539** when only the
  units are fixed (annual 150.24 → 78.20), and **→ 0.1606** with §1's position discipline added —
  i.e. the honest level is about **1/8.6 of the headline**, sharpe ~2.6 not 6.07.
  ⚠ **The gate was nearly INERT while broken** (q-e6-14: turning it off entirely moved objective
  +0.0107, daily-return correlation 0.9986, 2022 bit-identical). So the 0.73 is **entirely return
  contributed by untradeable names the broken gate admitted**, not screening value lost.
  ⚠ **Both edges SURVIVE the fix** — this is the important negative guarantee. On the corrected
  base, removing 低开反转 still costs half the annual (q-e6-16, 51% retained) and switching to
  market-cap ranks 1001–2000 leaves only **5%** (q-e6-17, vs 40% on the broken base), so 规模 is
  *stronger* once the gate works. The mechanism is real; only the MAGNITUDE was fiction.
  ⚠⚠ **It retroactively invalidated a spent VAL.** imp-5's advantage came almost entirely from the
  broken gate (imp-6: the same change is worth +0.009 on the fixed base vs +0.13 on the broken
  one), so the 2026-09-22 validation of `xsz-imp-5` (1.4274) confirmed a candidate whose edge is
  untradeable. The next epoch's VAL candidate is `q-13`/`q-18`, never a ranking tweak.
  **Exactly three raw files carry it** (audited repo-wide; the other 63 hits are study copies of
  the base):
  `7a1c225f:216` (base, §3 #1 — measured fixed), `8dbd994c:212` (§3 **#2**, obj 1.2810) and
  `5e874b5b:123` (§3 **#5**, obj 0.9411). The two siblings read the **ask** side while the base
  reads the **bid** (variables still named `a1_*`) — opposite directions, `×100` on both.
  ⚠ **§3's top-five ordering is not a mechanism ranking.** Both siblings were re-measured
  2026-10-17 (8 backtest minutes), each paired with its OWN control — the same book as written, at
  epoch 8 — because their only prior rows were epoch 2, which epoch 8 rejects, so the old rows are
  not comparables:
  | book | control | fixed | retained | maxDD |
  |---|---|---|---|---|
  | base `7a1c225f` | 1.3861 | 0.6539 | 47.2% | 11.63 → 12.81 |
  | `8dbd994c` (#2) | 1.2637 | **0.2867** | 22.7% | 12.61 → 14.61 |
  | `5e874b5b` (#5) | 0.8577 | **0.2858** | 33.3% | 9.75 → **19.55** |
  ⚠⚠ **THE TWO SIBLINGS CONVERGE TO WITHIN 0.0009** (0.2867 / 0.2858) from controls that differ by
  47%. Once the gate means what it says the two books are the same book — so this branch has **one**
  performance level, about **0.286**, not three. The 1.37 / 1.28 / 0.94 spread in §3 was produced
  almost entirely by how much untradeable volume each broken gate admitted, not by stock selection.
  That is q-e6-17's prose conjecture promoted to a measurement, and it means **§3 must GROUP this
  branch, never rank its members**.
  ⚠ **Drawdown worsens on all three** (+1.2 / +2.0 / **+9.8pp**, the last a doubling), so the
  broken gate was suppressing risk as well as inflating return. An honest version of these books is
  both lower-returning and riskier.
  ⚠ The fixed books keep sharpe **1.67 / 2.43** — still above the 1.5 gate, so the mechanism
  survives at a tradeable size; it is the magnitude that was fiction.
  ✅ Built by `study/小市值/build-siblings.js` — `py2to3` + ONE asserted edit + `OVERRIDE`, never an
  edit to `strategies/`. ⚠ Its stray-`*100` guard initially rejected a CORRECT build by matching
  its own explanatory comment; it now tests the code side of the line only. A check that reads
  prose as code fails precisely on the right answer.
  ✅ Not currently contaminating live tables: all three rows are **epoch 2**, which
  `measurementValid()` rejects under epoch 8, and none is queued for re-measurement. The family's
  current headline `a30641fb` (bestObjective 1.0258, epoch 8) calls `get_current_tick` **zero
  times** and is clean of this bug — its R=1 has other causes (min-500 market cap, 9:26 auction
  entry, ~100% daily turnover).
  ⚠⚠ **FORWARD RISK — still live.** `strategies/` is immutable, so the corrected numbers above live
  in `study/小市值/variants/`, NOT in the ledger: the ledger still holds only each book's epoch-2
  row. Re-measuring either sibling as-is under epoch 8 would mint an **inflated epoch-8 row** that
  WOULD feed §3, `wiki/types/` and the champion — the control runs above are exactly that number
  (1.2637 / 0.8577) and must never be committed as a ledger row without the correction beside them.
  Measure a units-fixed VARIANT, the way q-13 and q-e8-1/2 did. Realizability for this branch is
  scored **per branch**, not per member, since all three share the defect.
- **The 100× unit bug is CONFINED to those three books** (audited repo-wide 2026-10-17). Only **8**
  raw strategies read tick depth at all; only the three 小市值 books scale it by 100. The other five
  (打板短线 ×2, 其他, 多因子ML, one unassigned) compute depth money correctly.
  ⚠ Widening to the share/lot CLASS found 51 lines matching "quantity × 100" and all but the known
  one are the **correct board-lot idiom** (`int(value/price/100)*100` — JQ requires multiples of 100
  for A-share buys). So authors generally do know a lot is 100 shares, which makes this branch's
  error a misreading of what `a1_v` RETURNS rather than ignorance of lots.
- ✅ **`b3751277` liq-1: the feasibility floor is INERT — R=1 is measured FALSE.** objective
  **1.3443 → 1.3443**, sharpe 4.29 → 4.29, Δ exactly 0.0000 at the book's own ¥4e6/day floor
  (capital 1,000,000 / `g.stock_num` 5 / `order_volume_ratio` 0.05). Same outcome as 大小盘轮动's
  liq-1, the opposite of ETF溢价 (8.44→1.10) and 小市值 (7/8 不可成交). Supports **R ≥ 2, not 3** —
  liq-2 (5×) and liq-3 (10×) are built but unrun, so the capacity ceiling is unmeasured.
  ⚠⚠ **I had flagged this book as unfillable and was WRONG on every point.** I called it "a 涨停
  selection book, same mechanism as 打板短线's R=1". Reading the code: the entry is
  `run_weekly(weekly_buy, 2, '10:30')` — a weekly rebalance, NOT a buy at the next-day open of
  yesterday's limit-up, which is the specific unfillable thing; 涨停 is a HISTORICAL screen
  (`g.limit_days_window = 3 * 250`), i.e. a 涨停基因 filter; and it explicitly AVOIDS sealed boards
  (`last_price < high_limit`). The title misled me — 「涨停优选后再买入」 is "screen by limit-up,
  THEN buy later", and the 再 is load-bearing. **This is exactly the error that got the
  `limit-up-entry` lint pattern deleted** ("'buys them' and 'screens them out' both read
  `high_limit` with an equality, and the difference lives in control flow a line regex cannot
  see") — I made the regex's mistake by eye, having written that note myself. Read the entry, not
  the title.
- ⚠⚠ **A STAGE'S CHILD OUTPUT USED TO BE CAPTURED AND DISCARDED, which made a real bug
  undiagnosable.** Observed twice (2026-10-19, 2026-10-20): a first productive normalize, then a
  second invocation that runs **~15 minutes, bills ZERO, resolves ZERO files** and trips the
  no-progress guard — ending 2026-10-20 with **140 of 180 minutes unspent**. The run log held
  **28 lines and none of the normalizer's own output**: `sh()` captures stdout with `execFileSync`,
  `runNormalize` keeps a 6-line tail for the note, the rest is dropped.
  Every candidate was ruled out on code reading alone — the 6s cooldown cannot apply (done files
  leave `todo` BEFORE the loop), `waitMinFor` is cap+margin ≈ **50** min not 15, the stage timeout
  is 255 — which left a hypothesis with no way to test it.
  **Fixed**: `sh()` writes the full child output to `data/daily-logs/stage-<tag>-<ts>.log`
  (gitignored) and the stage note names the path. ⚠ Limitation: the log is written when the child
  RETURNS, so a true hang still leaves nothing.
  Leading hypothesis, now testable: the CONCURRENT-STOP retry path — with a past-cap blocker
  listed, `phantom` sets `cleared = true`, each file retries up to 3× then skips, and 164 files ×
  3 fast cycles ≈ 15 minutes writing no rows.
- **Realizability: a FREE STATIC FLAG at normalize time — `utils/realizability-lint.js` — and
  deliberately NOT a gate.** The question "should we check realizability before normalize?" has a
  three-part answer:
  1. **It cannot be scored from source.** 大小盘轮动's R=2 took `liq-1` across three declared floors
     (31 JQ min) and the answer was counter-intuitive: the floor removed **zero** names on 31/31
     rebalances, curve bit-identical. A static rule would have guessed the opposite.
  2. **A pre-measurement reject must be a known fact, never a guess** — the rule that already cost
     this repo 287 of 549 strategies.
  3. **The measurement is what EXPOSES the problem.** 7a1c225f's unit bug was found by studying a
     book that had already been measured; a pre-filter would have hidden it, and with it the fact
     that two of §3's top five shared it.
  So the WARNING moves earlier, not the decision: `kb-stub` stamps `realizabilityFlags:` beside the
  `normalized:` block, because that line is what feeds §3, `wiki/types/` and champion resolution —
  the reader who needs the caveat is the one looking at the table, not someone who later finds §4.
  Measured: **18 of 259** files flagged — `uncapped-position-size` 14, `tick-depth-x100` 3,
  `depth-gated` 3, `call-auction-entry` 2. A test fails if that ratio balloons.
  ⚠⚠ **A pattern was REMOVED for imprecision, and that bar matters more than coverage.**
  `limit-up-entry` was tried twice — 37 files, then **140** after "narrowing" — and both times the
  hits were dominated by code that AVOIDS limit-ups (`s not in g.high_limit_list`,
  `day_open == high_limit` as a 一字板 *detector*). "Buys them" and "screens them out" both read
  `high_limit` with an equality and the difference lives in control flow a line regex cannot see.
  A flag that fires on the opposite of what it claims teaches the reader to skip the column —
  including the row that mattered. It needs an AST walk or a probe, not a third regex.
  ⚠ Nothing in the pipeline consults the lint; a test asserts that `daily-pipeline`,
  `strategy-normalize` and `integrate-eligible` do not import it.
- ⚠⚠⚠ **NEVER KILL A NORMALIZER MID-BACKTEST. An ORPHANED REAL RUN BILLS ITS FULL ELAPSED TIME.**
  Measured 2026-10-18, and it cost **617 minutes — 3.4× the whole daily free tier**:
  | time | used | event |
  |---|---|---|
  | 14:20Z | 179 | two orphans listed, ages ~235 and ~259 min |
  | 14:59Z | **493** | orphan 1254 settled on its own → **+314** |
  | 15:02Z | **796** | orphan 1255 cancelled by hand → **+303** (its age was 308 min) |
  Each orphan billed almost exactly its **wall-clock age**, not its useful runtime.
  **Cause: my own kills.** Stopping a `strategy-normalize` batch (twice that day — once to change
  the usage ceiling, once to stop a premature research dispatch) leaves its in-flight backtest
  running on JQ with nothing polling it. The entry then ages indefinitely and bills the whole age
  when it finally terminates.
  ⚠⚠ **This CONTRADICTS the phantom note below, and the distinction is the whole lesson:**
  | listed entry | billing |
  |---|---|
  | **phantom** (no backtest behind it — `buildList` has no row) | bills **nothing** (`used` sat at 92 before, during and after a 121-min entry) |
  | **orphaned REAL run** (killed mid-flight, `log.state=1`, a real backtest behind it) | bills its **FULL ELAPSED AGE** |
  So "a listed run is not a billed run" is true only for phantoms. Check `log.state` /
  `buildList`: state 1 with a row means a real run is accruing.
  ⚠ **The documented overshoot bound is wrong for orphans.** `limit + SLOW_SKIP_MIN` (225) bounds a
  run the executor is still polling, because the cap cancels it. An orphan has no poller and no
  cap — it can bill hours.
  **RULE: cancel the backtest BEFORE killing the process.** `node utils/jq-cancel.js --cap-min <age>`
  then kill. And if an orphan is already loose, **cancel it immediately** — it bills elapsed-so-far,
  which only grows. Cancelling 1255 at 308 min cost 303; leaving it until the nightly reap would
  have cost more.
  ⚠ A further hazard: an orphan that settles AFTER the daily rollover bills into the NEXT day's
  tier. That is why containing it the same day matters even when the day's budget is already gone.
- ⚠⚠ **A capped run that JQ refuses to cancel may be a PHANTOM that bills nothing** — and the
  difference is only visible in `duration.used`. Measured 2026-10-17: a liquidity-floor run hit the
  45-min cap, JQ refused cancellation five times (`在此状态不能取消`) across two attempts, the entry
  stayed listed for **121 minutes**, and `used` sat at **92 before, during and after**. It released
  at `JQ_CONCURRENT_STALE_MIN` (default **120 min**), which is exactly the case `jq-running.js`
  documents: *"a phantom that JQ will never reap — one reached 701 minutes while billing nothing —
  must not make this block forever."*
  ⚠ **So do not charge wall clock to the budget.** I projected "~169 of 180 used, ~11 min left" twice
  while that run was listed; the real figure was 92 and the pipeline had **88 minutes**. `used` is
  the only authority, and it does not move until a run TERMINATES — which an unreaped phantom never
  does. A listed run is not a billed run.
  ⚠ `jq-cancel.js --cap-min N` doubles as "how old may a run be and still count as ours", so a run
  that outlives the cap reads as someone else's and is skipped; `--cap-min 180` got past that, and
  JQ still refused. The cap is not the obstacle — JQ's state is.
  ✅ **The poller now detects this in ~3 minutes instead of burning 45 + blocking 120.**
  `pollUntilComplete` watches only `statistics.running.length`, which a phantom keeps above
  baseline forever, so `emptyStreak` never accumulates. The distinguishing signal is the
  **buildList**: `/algorithm/backtest/buildList?algorithmId=X` has **no backtest at all** for a
  phantom, and that is what finally identified both. The probe requires ALL THREE —
  past `JQ_PHANTOM_GRACE_MS` (default **3 min**, far beyond the 8s registration settle), JQ still
  claiming a run above baseline, and no backtest — confirmed on **two** consecutive probes, with an
  unreadable probe never counting as a phantom. Cancelling a healthy run is the one failure worse
  than the phantom.
  ⚠⚠ **`phantom` is RETRIABLE, never `slow-skipped`.** A slow-skip means "it ran and we gave up" —
  terminal, parked in the deferred pool at a HIGHER cap. A phantom means the backtest never
  existed: nothing was learned about the strategy, nothing was billed, and a bigger cap changes
  nothing. Same class as `scrape-zero`, and kept out of `TERMINAL` for the same reason. The
  normalizer records nothing and **stops the batch**, because an account that just phantomed will
  most likely phantom the next strategy too.
  ⚠ The marker is printed BARE at line start (`PHANTOM-STOP\t…`), not behind `[post] `. A
  `*-STOP` marker the normalizer does not string-match is recorded as a **crash against the
  strategy** — six CONCURRENT-STOP refusals did exactly that on 2026-09-23 — and
  `tests/normalize.test.js` enforces that coverage for every marker the executor prints. It caught
  this one.
  ⚠⚠ **The verdict must be THREE-valued, and the first version was not.** `buildList` has three
  measured response shapes (2026-10-17, live): a **fresh** algorithm renders 22,883 bytes with
  **0** `class="backtest-tr"` rows; one with runs renders ~26,200 with **≥1**; and one the account
  **cannot read** answers a 60-byte `{"status":"2","code":"20000","msg":"系统繁忙，请稍后重试"}`.
  A boolean regex over the body (`/backtestId[=":\s]+[a-f0-9]{32}/`) gets the first two right only
  **by luck** — the shell field `<input type="hidden" id="backtestId" value="…">` is blank until a
  run exists, which is also why a page with 1 row matches **2** ids (sampled: 2/1 on all 8) — and
  reads the third as `false` = phantom. Two of those 30s apart would **cancel a healthy backtest**,
  the one failure worse than the phantom. Not transient either: four reads 4s apart all returned it.
  So `classifyBuildList()` returns `true` (≥1 row) / `false` (**rendered** and no row) /
  **`null`** (anything else — never a phantom), and it lives in **Node, not `page.evaluate`**: a
  rule inside the evaluated function cannot be unit-tested, which is why the broken version shipped.
  ⚠ Do **not** probe with `running[].id` — that is a **backtestId**, not an algorithmId, so
  `buildList` answers 系统繁忙 for it no matter what. The poller probes the algorithmId it created.
  This also means the earlier "no backtest found for algorithm 2bbd06f3…" verdict was the
  *unreadable* shape, not the empty-table one.
- ⚠⚠⚠ **THE INVERSE OF THE PHANTOM: a run that FINISHED while JQ kept listing it as running.**
  Found 2026-10-18 **by the human**, who saw 「完成」 on the server while the poller was 33 minutes
  into polling. Measured: all five newest algorithms (1245..1249) read 完成 while
  `statistics.running` still listed one entry.
  `pollUntilComplete`'s primary signal is the account-wide `running` **COUNT**, and
  `running[].id` is a **backtestId that never matches our algorithmId** — so the count cannot be
  attributed to our run. A finished run JQ leaves in the list pins the count above baseline
  forever: `emptyStreak` never accumulates, the run burns to `MAX_POLL_MS` and is written
  `slow-skipped` **while its completed result sits on the server**. Cost: ~45 min on
  `c5d20393`.
  ⚠ The loop's SECOND signal could not save it either — `resultsRendered()` is forced to `false`
  whenever `runningCount > baseline`, which is exactly this case. Two signals, both blind to it.
  **Fix**: the buildList row IS attributable (we pass our own algorithmId), so `parseBuildList()`
  answers both questions from ONE fetch — `_status="2"` ⇒ **complete** (2 confirmations ~30s
  apart), `rows === 0` ⇒ phantom, unreadable ⇒ keep polling.
  ⚠ `_status="2"` ⇔ 「完成」 verified across the 10 newest rows on the account; the visible word is
  corroboration only, because it is localized and the attribute is not. `DONE_STATUS` is a
  **whitelist of one**: no live run was available to observe the in-progress code, so anything else
  keeps polling (the old behaviour), whereas guessing a code wrong would scrape a PARTIAL result as
  final.
  ⚠ The 系统繁忙 error body literally contains `"status":"2"`. Requiring the **row attribute**
  (`class="backtest-tr" … _status=`) is what stops a server error reading as a finished run — the
  same false-positive shape the phantom probe had, waiting in a different place.
  ⚠ **Recovery is free and is by SOURCE HASH, never by id.** `study/_recover/recover-c5d20393.js`
  hashes the normalized source JQ serves against the exact temp copy the normalizer submitted
  (`/tmp/jq-normalize/<tag>.py`). It matched **three different id pairs** across three calls
  minutes apart — the same run each time. It aborts before writing unless the curve's final
  cumulative return agrees with the stats endpoint (±0.05pp), the row has exactly
  `ledger.COLS.length` cells, and the newest row really is `slow-skipped`. The recovered row
  APPENDS, so newest-row-wins makes it authoritative (c5d20393: 41.39% / annual 19.59 / sharpe
  1.29 / maxDD 6.52 ⇒ objective 0.1307, gate fail).
  ⚠⚠ **Second-order consequence: it also BLOCKS THE BATCH through the concurrency gate**, not just
  its own poll. Measured 2026-10-18: the normalizer hit `CONCURRENT STOP` and sat in
  `jq-running.js --wait` for **34 of 50 minutes at 0.21s CPU** on 这是一个简单的策略-1251, whose
  buildList row read `_status=2`. The wait cannot succeed — at 36 min the entry is UNDER the 45-min
  cap, so it reads as a LIVE blocker rather than the "past the cap, hopeless" case that IS handled,
  and JQ may hold it far longer (one reached 701 min).
  ⚠⚠ **`jq-running.js` is deliberately NOT patched.** It is what prevents two concurrent backtests,
  and concurrent runs have returned **identical metrics for different strategies** on this account:
  a false "not blocking" silently corrupts results, where a false "blocking" only wastes time. It
  also cannot use the poller's fix — it sees only `running[].id`, a backtestId it cannot attribute
  to one of our algorithms.
  ✅ **SETTLED 2026-10-18, and `jq-running.js` now uses it.** The one attributable signal for a
  LISTED entry is that entry's own log (`/algorithm/backtest/log` keyed by the id the list gave us —
  attributable to the ENTRY even though the entry is not attributable to one of our algorithms).
  Every `state` seen before came from a run already believed finished, so 2 might have meant "has
  output". The executor was instrumented to print `LIVE-RUN-STATE log.state=<n>` once per run at a
  moment when the run is KNOWN live, and the measurement is unambiguous:
  | run | `log.state` |
  |---|---|
  | **in-flight** (measured 17s in) | **1** |
  | finished / 完成 | **2** |
  So the states DO separate, and `running()` now excludes an entry whose log reads `2`.
  ⚠ **Only an exact `'2'` clears an entry** — state 1, an unreadable log and a throw all leave it
  blocking, because a false "not blocking" silently corrupts results while a false "blocking" only
  wastes time. Never infer finished from "not 1".
  ⚠ Live-checked right after: two **CANCELLED-but-unreaped** entries both reported `1` and correctly
  kept blocking. The check fires only on runs that actually FINISHED — which are exactly the ones
  with a result to capture. The age-vs-cap rule still owns the cancelled corpses.
  ⚠ The observation cost **one HTTP call on a run that was happening anyway**, and it needed two
  other fixes to be visible at all: the probe fired only every 6 polls (~30s) so it never ran on a
  normal strategy — most of this corpus finishes inside 30s, and the observation came at **17s** —
  and the normalizer **captures** the child's stdout, so a verification batch produced **zero
  `[post]` lines** and the diagnostic went to a stream nobody reads. Both fixed; the normalizer now
  echoes any `LIVE-RUN-STATE` line.
- ⚠⚠⚠ **A COMPLETED BACKTEST IS NOW ALWAYS CAPTURED — three layers.** (1) the count returns to
  baseline (normal); (2) during polling, our algorithm's `_status="2"` (2 confirmations ~30s apart);
  (3) **at the safety cap, one last `_status` read before giving up** — if it reads 完成 the run
  falls through to the scrape instead of recording `slow-skipped`. Layer 3 is the guarantee: it
  covers every route to abandoning a run, not just the one that was found.
  ⚠ The check runs **before `cancelBacktest`**: cancelling first races a run that is complete but
  not yet delisted, and the point is to prefer a real measurement over a null row. Verified live on
  2026-10-18 — two runs hit the cap genuinely unfinished, the capture declined on both, and they
  recorded `slow-skipped` correctly. A false capture would scrape a partial result, so the
  declining direction is the one that had to be tested.
  ⚠ **`utils/recover-completed.js` generalises the recovery** (`--scan` lists which slow-skipped
  rows are recoverable). **THREE rows recovered, and the bug predates today**:
  | tag | run | recovered result |
  |---|---|---|
  | c5d20393 | 2026-10-18 | 41.39% / annual 19.59 / sharpe 1.29 / maxDD 6.52 ⇒ **0.1307** |
  | c083c109 | 2026-10-18 | −2.79% / annual −1.45 / sharpe −0.50 / maxDD 12.39 ⇒ **−0.1384** |
  | 223a137e | **2026-10-16** | −18.54% / annual −10.05 / sharpe −1.00 / maxDD 24.70 ⇒ **−0.3475** |
  Each cost its run's full cap (~45 min) waiting on a result already on the server. Two are gate
  failures, which is the point: a `slow-skipped` row carries NO number, so the pipeline could not
  tell a book that fails from one it never measured.
  ⚠ Its limit is `/tmp`: the submitted copy `/tmp/jq-normalize/<tag>.py` is the only link back to
  what was submitted, so **20** older slow-skipped rows cannot be matched by content and are
  reported as such rather than guessed at. (An earlier note here said "7 of 9" — that was my own
  `tail` truncating the scan, not a measurement.)
  ⚠ Narrow with `--near "<YYYY-MM-DD[ HH:MM]>"`. The first version fetched the SOURCE of every
  candidate and **wedged for 18 minutes at 2.6s CPU with no output** — no progress logging, no
  bound. One cheap buildList call per algorithm now yields
  `name | createdAt | window | state | return`, and the date prefix cuts the expensive source check
  to the few rows created that day (223a137e needed 12 pages back).
  ⚠ **`days` is the window's EXCLUSIVE calendar span (729 for TRAIN), never blank and never the
  curve's 484 trading days.** A slow-skipped row carries no `days`, so copying it through left the
  cell empty — caught in the c083c109 dry run. The ledger annualizes over this column, and
  `component-scan --validate` reads it. Inclusive counting gives 730; the tool now refuses to write
  a row whose day count disagrees with every existing row in that ledger.
  ⚠ **Recovery is not finished at the ledger row.** `tests/daily.test.js`'s pool invariant failed on
  the tool's FIRST use: the chain had already DEFERRED c5d20393 as a slow-skip, so after recovery it
  sat in the retry pool as finished work and would have been re-measured at a higher cap. The tool
  now ends by calling `normalize-sync`, which OWNS that reconciliation — the same rule that puts it
  at the end of every normalize batch.
  ⚠ **And this undercuts the "a cancelled run bills nothing" reading** recorded above: if those
  runs COMPLETED, their minutes were charged normally. Do not treat the slow-skip overshoot as free
  on that evidence.
- ⚠ **A run JQ refuses to cancel at the slow-skip cap (「在此状态不能取消」) is not necessarily lost.**
  打板短线's jy-u-2 hit the 50-min cap, five cancel attempts failed, the executor reported
  `slow-skipped` — and the run completed server-side two minutes later. The algorithm's buildList
  read 完成 and `POST /algorithm/backtest/stats` + `GET /algorithm/backtest/result` served the full
  484-day result and curve at zero cost (`backtest-series.fetchViaHttp`, saved under the normal
  series key; the finding is flagged `recovered-after-slow-skip`). Check the buildList before
  writing a capped run off as a phantom; the minutes are already billed either way.
- ⚠⚠⚠ **"Is the account blocked?" is answered in TWO places, and fixing ONE of them LIVELOCKED the
  normalizer for a whole stage.** JQ keeps a *completed* backtest listed in `running[]` for a
  while, so a finished entry is **young by age** while being no blocker at all.
  `jq-running.probeFinished` reads each listed entry's own `/algorithm/backtest/log` and clears it
  only on a positive `state === '2'` — and on 2026-10-18 that fix went into the **waiter only**.
  `concurrencyGate()` in `strategy-post-backtest.js` kept classifying by AGE alone
  (`age > STALE_MIN ? stale : age > capMin ? dead : young`), so the two gates disagreed about the
  same entry and the batch span:
  gate refuses → `CONCURRENT-STOP` → normalizer calls `jq-running --wait` → the waiter clears the
  account **in seconds** → same file retried → refused again, 3 times per file, then on to the next
  file and the same wall.
  **Measured 2026-10-21** (`data/daily-logs/stage-strategy-normalize-2026-10-21T14-02-22.log`):
  **114 `CONCURRENT STOP` lines, 0 normalized rows, 0 backtest minutes**, `used` frozen at 49/180
  for ~38 min with 183 files pending and a `jq-running --wait` child respawning every few seconds.
  That is the "15-minute no-op" — it was never a hang; it was the pipeline refusing itself.
  ⚠ The parent normalizer is NOT where the gate lives, so it looked innocent: 0.93s CPU over 38
  minutes, **zero open sockets**, no child at the instant sampled. `pgrep -P <pid>` catching a
  two-second-old waiter child is what exposed the cycle.
  **Fixed by giving the rule ONE OWNER**: `probeFinished(page, rows)` is exported from
  `jq-running.js` and `concurrencyGate` calls it, adding a fourth category (`finished`) that is
  excluded from `young` but still counted in the poller's `baseline` — different questions.
  A test asserts both files share it, including that the executor's `running[]` map carries
  `id: r.id` (drop that and the probe has nothing to key on, returns an empty set, and the
  livelock returns with every call site still looking correct).
  ⚠ **A diagnosis rule, not just a bug**: the loudest line in the log was the refusal, and the
  refusal names the *blocker*, not the disagreement. Two gates both "working" is invisible in
  either one's output — only the pair is wrong. When a stage reports nothing and spends nothing,
  compare what each gate says about the SAME entry.
