# study/_probes/ — data-semantics probes

Small, strategy-free backtests that answer a **platform data question** with a measurement
instead of an argument. Written 2026-09-18 to test lookahead claims that the post screener
surfaced from the community (see `screen/verdicts.json`).

## Why they encode the answer in the result

The backtest **log is not retrievable** through the API this repo uses — `/algorithm/backtest/log`
returns empty and the sibling endpoints refuse. So a probe cannot simply print. Instead each
probe places **exactly one marker trade if and only if its condition is ever true**, and the
answer is read off the `SUMMARY` line: `completed` = condition observed, `no-trades` = never.

**Every probe needs a control.** `no-trades` is ambiguous on its own: it also happens when the
code path never runs, an API returns empty, or the order fails. Each condition probe below is
paired with a control that fires unconditionally at the same point.

## Results (TRAIN windows only; OOS never touched)

| Claim (from a screened community post) | Probe | Control | Verdict |
|---|---|---|---|
| `get_extras('is_st')` returns TODAY's ST status, not the status as of the backtest date | `is_st_extras_extra.py`, `is_st_current_extra.py` — fire if the two sources disagree in either direction | `is_st_control_*.py` — fired, and both sources returned non-empty ST sets | **NOT REPRODUCED.** The two agree exactly, every day, on 2022-01-04→01-11 and 2023-12-01→12-15. The 15 held strategies using the `get_extras` form are not contaminated. |
| An undated `get_fundamentals(q)` leaks later fundamentals | `fundamentals_undated.py` — fires if undated differs from `date=context.previous_date` | `fundamentals_control.py` — fired | **NOT REPRODUCED.** Identical code list and market caps to 6 decimal places. The 130 undated calls across `strategies/` resolve to the previous trading day. |

## Two claims that need no probe

- **七星高照 NAV-premium filter lookahead.** Moot for anything we have measured: study q-4
  already found the filter **exactly inert** on TRAIN — bit-identical stats, 484 trading days,
  not one trade different. A leak in a branch that never changes an outcome changes no result
  of ours.
- **Fund NAV (`unit_net_value`) timing.** By inspection the held discount strategies read
  `end_date=context.previous_date` at 09:20/09:30, i.e. the PRIOR day's NAV, which is published
  that evening. Not a leak as written. ⚠ **Still open**: LOF and especially QDII NAVs publish
  on a longer lag, and `15c36e0c` includes `lof` in its universe. A probe would need a fund
  whose publication lag is known independently.

## Running one

```bash
node utils/strategy-post-backtest.js study/_probes/<probe>.py "probe-<name>" \
  --start 2022-01-04 --end 2022-01-11 --max-poll-min 8
```

Read the last field of the `SUMMARY` line. Always run the control alongside the probe.
