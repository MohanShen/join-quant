---
name: run-oos
description: Spend one test on the 2026+ out-of-sample reserve — pre-flight the candidate's readiness and budget, declare the expectation before the number exists, run it, then record the result. Use when asked to run an OOS or holdout backtest, or to take a finalised candidate to the final surface.
---

# Spend one OOS test

The last surface. TRAIN is where selection happens and may be re-run freely; VAL is one
confirmation per (family, bench); **OOS is one look, after which nothing is left but waiting for
more calendar.** No re-run, re-scoring or epoch bump un-sees it.

**Authority**: `harness/harness.md` §1 (windows) and §4.1, `utils/oos-budget.js` (the accounting),
`utils/integrate-eligible.js` (what makes a candidate ready). This skill is the entry point.

## You CAN start the run — and that is why the checks below are in code

⚠ **Changed 2026-10-16 (user decision).** OOS used to need `JQ_ALLOW_OOS=1`, an env prefix, which
does not match `.claude/settings.json` (rules are matched by `startsWith`) and therefore forced an
approval prompt on every run. `--allow-oos` is now the CLI form, and
`Bash(node utils/strategy-post-backtest.js:*)` is already allowlisted, so **an OOS run is
unattended.**

Two switches deliberately stayed environment variables, so overriding a *protection* still costs a
prompt:

| switch | form | what it overrides |
|---|---|---|
| `--allow-oos` | **flag** | the window block only |
| `JQ_ALLOW_OOS_OVERBUDGET=1` | env | the budget ceiling (1/candidate, 2/bench) |
| `JQ_ALLOW_OOS_UNREADY=1` | env | the readiness gate below |

**Never set either env var.** If a run is refused, the refusal is the answer — and report it rather than working around it.

Because the human no longer sees every run, the readiness question moved from this prose into
`strategy-post-backtest.js`: an OOS run **requires `--family`** and refuses unless that family is
`eligible`. You should still run step 1 — a refusal after the command is a worse place to learn it
than before.

## Step 1 — is the candidate ready? (this is the whole value of the skill)

```bash
node utils/integrate-eligible.js <family>     # champion/product + passing VAL + realizability
node utils/oos-budget.js <candidateId>        # per-candidate (absolute) + per-bench limits
```

**Do not proceed unless `integrate-eligible` reports the family `eligible`.** Each of the
following cost nothing to catch here and would have spent an irreversible test on the wrong book
(all three found on 2026-10-16):

| near-miss | what it looked like |
|---|---|
| the VAL validated a **different book** | 大小盘轮动's champion was the base; its VAL ran on `enhance/candidates/dxp-imp-1.py` |
| the **candidate** was the wrong artifact | `championOf` reads the ledger, which holds only INGESTED strategies — the family's product lives on the shelf (`validated_strategies/`) |
| realizability measured on **another book** | R=2 came from `liq-1` on the base, while the candidate was always-small, which the family's own realism calls worse on capacity |

⚠ **The budget counts; it does not judge.** It will happily let you spend a test on a book nothing
validated. Readiness is the protection.

Also confirm: the frozen pins are present (else `UNPINNED-STOP`), the account is clear
(`node utils/jq-running.js`), and CDP answers.

## Step 2 — declare the expectation BEFORE the run

Write down, in the report, what each outcome would mean — **before** the number exists. This is
not ceremony: once an OOS number is visible, every interpretation of it is contaminated by having
seen it.

State specifically whether a weak result would be **new information** or merely **confirmation of
a caveat the family already declared**. Example from 大小盘轮动: its product's own header says
「there is no evidence this candidate beats the base out of sample」 and its VAL drew 36.37% where
the base drew 18.23% — so a weak OOS result confirms a known caveat and is not a surprise.

## Step 3 — run it

Report the command you are about to run, filled in, so the choice of candidate and window is
visible in the transcript before the number exists:

```bash
node utils/strategy-post-backtest.js <candidate file> "<expId>" \
    --window holdout --family <family> --allow-oos --usage-limit free --max-poll-min <N>
```

⚠ **The file you pass must be the family's own candidate** — `integrate-eligible` validates the
FAMILY, not the argument, so running some other book passes the gate and spends the reserve on
something the pipeline will not ship. The executor warns when they differ; do not ignore it.

- `--window holdout` — read the dates from `node utils/harness-config.js`, never hardcode them;
  the reserve is **rolling** (`holdout.end: "today"`), so it lengthens with the calendar.
- `--max-poll-min` — size it from the candidate's known TRAIN runtime scaled by window length.
  The holdout window is far shorter than TRAIN, so a book that took 11 min over 729 days needs
  roughly 5 over 289.
- Never add `JQ_ALLOW_OOS_OVERBUDGET=1`. That is a second, separate switch for exceeding the
  budget, and it is not yours to suggest unless the human raises it.

## Step 4 — what happens on its own, and what you must check

Automatic on a **completed** run:

- `oos-budget.record()` appends an `oos-` row to `consumption.tsv`; that candidate is then
  permanently blocked from a second test and the bench's count drops;
- the curve is captured under `<slug>__holdout__e<N>`, so the per-year split is computable.

A compile-error or slow-skip **charges nothing** — it produced no number and saw nothing of the
held-out data. Report it as what it was; never substitute a projection.

Then verify rather than assume:

```bash
node utils/oos-budget.js                      # the count really moved
node utils/backtest-series.js --list | grep holdout
```

## Step 5 — record

Report the number as measured, then write it to the family page (§2 row, `类型: raw`).

⚠⚠ **Do NOT append a second `stage: 'oos'` row.** `oos-budget.record()` already wrote one, keyed on
the CANDIDATE, and `priorTests()` counts every row whose stage is `oos` *or* whose outcome starts
`oos-`. A family-keyed duplicate would make the bench read 2 of 2 and falsely exhaust the reserve.
Record the research side under `stage: 'research'` instead:

```bash
node -e "require('./utils/consumption').record({key:'<family>',kind:'family',stage:'research',runId:'<expId>',outcome:'oos-recorded',note:'…'})"
```

⚠ And keep `outcome` clear of a leading `oos-` on that row, for the same reason.

If the candidate is a universe's promoted candidate, note the result in `data/promoted.tsv` as
well — what a universe ships should carry its out-of-sample number.

## Do not

- **Set `JQ_ALLOW_OOS_OVERBUDGET` or `JQ_ALLOW_OOS_UNREADY`.** They are the human's, for the same
  reason `--allow-oos` used to be: they override a protection rather than unlock a surface.
- **Run an OOS test the human did not ask for.** The flag removes the prompt, not the decision.
- **Re-pick a candidate because its OOS disappointed.** That is selection on the last clean
  surface, one look at a time, and it is the one thing nothing can undo. Report it and stop.
- Spend a test on a family that `integrate-eligible` does not call `eligible`.
- Test a second candidate from the same family in the hope of a better number.
- Treat the budget's `ALLOWED` as a statement that the candidate is ready. It counts; it does not
  judge.
- Hardcode the holdout dates, or quote a prior epoch's reserve length.
