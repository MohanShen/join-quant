#!/usr/bin/env bash
#
# with-timeout.sh — run a command under a wall-clock bound, and kill its WHOLE PROCESS TREE
# when the bound is hit.
#
# Why this exists. `utils/daily-pipeline.js` dispatches each stage with `execFileSync(…, {timeout})`.
# Node's timeout sends SIGTERM to the direct child only. Every stage here is a shell wrapper that
# spawns the process doing the actual work, so the signal lands on the wrapper and the grandchild
# is ORPHANED — it keeps running, keeps spending JoinQuant backtest minutes, and keeps writing to
# the repo, while the pipeline has already recorded the stage as failed and moved on.
#
# Measured: the 2026-09-20 VIP run hit the old 60-minute ceiling; `bash autoenhance-loop.sh` died,
# and its `claude -p --resume` child was still running an hour later, outside the pipeline's
# accounting and outside its lock. Two processes then believed they owned the JQ session.
#
# The fix is a process GROUP. `set -m` gives each job its own group, so `kill -TERM -$pid` reaches
# the wrapper and everything it spawned. (`setsid` would be the usual tool; macOS has no such
# binary, and this repo runs on darwin.)
#
# Exit code 124 means "timed out", matching GNU timeout(1), so the caller can tell a bound we
# enforced apart from a command that genuinely crashed.
#
# Usage: with-timeout.sh <minutes> <command> [args…]

set -uo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: with-timeout.sh <minutes> <command> [args...]" >&2
  exit 2
fi

mins="$1"; shift
case "$mins" in
  ''|*[!0-9]*) echo "with-timeout: minutes must be a positive integer, got '$mins'" >&2; exit 2 ;;
esac

# Job control: the child below becomes the leader of its own process group, whose id is its pid.
set -m

"$@" &
child=$!

# Watchdog. TERM first so the wrapper's own EXIT trap runs and releases its locks; KILL only for
# what ignores it. The negative pid is the point of the whole file — it addresses the group.
#
# ⚠ Whether we timed out is recorded in a MARKER FILE, not inferred from the watchdog still being
# alive. After a TERM the watchdog is mid-`sleep 15`, so `wait` returns while it is very much
# alive — reading liveness would report every timeout as a clean exit, which is the exact
# misreport this file exists to prevent.
fired="$(mktemp -t jq-with-timeout)"
rm -f "$fired"

(
  sleep $(( mins * 60 ))
  : > "$fired"
  kill -TERM -"$child" 2>/dev/null || kill -TERM "$child" 2>/dev/null
  sleep 15
  kill -KILL -"$child" 2>/dev/null || kill -KILL "$child" 2>/dev/null
) &
watchdog=$!

wait "$child"
rc=$?

kill -TERM "$watchdog" 2>/dev/null
wait "$watchdog" 2>/dev/null

if [ -e "$fired" ]; then rc=124; fi
rm -f "$fired"

exit "$rc"
