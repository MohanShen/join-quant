#!/usr/bin/env bash
#
# run-integrate.sh [universe] — run ONE universe-level integration round.
#
# ## Why a wrapper, and why pinned per UNIVERSE
#
# `/run-integrate` was the last stage with no wrapper: it could only be invoked by a human in a
# TUI, so the daily pipeline could not reach it and families that cleared `/run-family` piled up
# at the exit gate with nothing to admit them. This is the same machine as `scripts/run-family.sh`
# with one substitution — its unit of work is a **universe**, not a family.
#
# The pin follows the unit for the same reason it does there: the single pinned per-STAGE session
# that `agent-loop.sh` used carried one family's context into the next family's round and kept
# working the old one. A universe round is about what that universe currently ships
# (`data/promoted.tsv`), which incumbent an arrival meets, and why an earlier pair was refused.
# None of that transfers to another universe, and all of it is on disk.
#
#   pins: data/integrate-sessions/<universe>.txt   ("<branch>\t<uuid>")
#
# ## A SEED costs nothing, and this script knows it
#
# `integrate-queue.js` returns one of three actions. `seed` — an empty promoted set meeting its
# first eligible arrival — is a record, not a judgement: no backtest, no browser. So the CDP and
# budget preflights are skipped for it. Gating a free action behind a spent budget is how a
# universe would sit empty all day for want of minutes it was never going to use.
#
# Usage:
#   scripts/run-integrate.sh              # take the queue's --next action
#   scripts/run-integrate.sh 全A           # a named universe
#   scripts/run-integrate.sh --list       # the queue and each universe's session state
#   FRESH=1 scripts/run-integrate.sh <u>  # force a new session even if one is pinned
#   DRY=1   scripts/run-integrate.sh <u>  # print what would run
#
# Env: REPO, USAGE_LIMIT (default 55), JQ_CDP_URL, USE_BYPASS
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
USAGE_LIMIT="${USAGE_LIMIT:-55}"
SLOW_SKIP_MIN="${SLOW_SKIP_MIN:-45}"
JQ_CDP_URL="${JQ_CDP_URL:-http://localhost:9225}"
PIN_DIR="$REPO/data/integrate-sessions"
LOG_DIR="$REPO/data/autointegrate-logs"
LOCK="$REPO/data/autointegrate.lock"
PLOCK="$REPO/data/jq-pipeline.lock"
mkdir -p "$PIN_DIR" "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG_DIR/wrapper.log"; }
cd "$REPO" || { echo "FATAL: cannot cd to $REPO" >&2; exit 1; }

# ── --list ──────────────────────────────────────────────────────────────────
if [ "${1:-}" = "--list" ]; then
  node utils/integrate-queue.js
  echo
  echo "  session state:"
  shopt -s nullglob
  for f in "$PIN_DIR"/*.txt; do
    u="$(basename "$f" .txt)"
    sid="$(cut -f2 "$f" 2>/dev/null)"
    alive="$(ls "$HOME"/.claude/projects/*/"$sid".jsonl 2>/dev/null | head -1)"
    printf '   %-14s %s  %s\n' "$u" "${sid:0:8}" "${alive:+transcript present}"
  done
  shopt -u nullglob
  exit 0
fi

# ── which universe, and which of the three actions ──────────────────────────
# The queue is authoritative about the ACTION even when a human names the universe: an `idle`
# universe has nothing to admit, and a round that runs anyway would re-litigate eligibility —
# which the skill forbids, because the fix for an ineligible family is upstream in /run-family.
WANT="${1:-}"
ROW="$(node -e '
  const q = require("./utils/integrate-queue");
  const want = process.argv[1] || "";
  const row = want ? q.build().find(r => r.universe === want) : q.next();
  if (!row) { process.stdout.write(want ? "no-such-universe\t" + want : "none\t"); process.exit(0); }
  const a = row.arrivals && row.arrivals.length ? row.arrivals[0] : row.arrival;
  process.stdout.write([row.action, row.universe, (a && a.family) || "",
                        (row.promoted || []).length, (row.why || "").replace(/\s+/g, " ")].join("\t"));
' "$WANT" 2>/dev/null)"

ACTION="$(printf '%s' "$ROW" | cut -f1)"
UNIVERSE="$(printf '%s' "$ROW" | cut -f2)"
ARRIVAL="$(printf '%s' "$ROW" | cut -f3)"
NPROMOTED="$(printf '%s' "$ROW" | cut -f4)"
WHY="$(printf '%s' "$ROW" | cut -f5)"

case "$ACTION" in
  none)
    log "nothing to do — every universe is idle (the gate is upstream in /run-family)"; exit 0 ;;
  no-such-universe)
    log "FATAL: no such universe in the queue: $UNIVERSE (node utils/integrate-queue.js lists them)"; exit 1 ;;
  idle)
    log "skip: $UNIVERSE is idle — $WHY"; exit 0 ;;
  seed|integrate) ;;
  *)
    log "FATAL: could not read the integrate queue (action='${ACTION}')"; exit 1 ;;
esac
[ -n "$WANT" ] || log "no universe given; took the queue head: $UNIVERSE ($ACTION)"

# ── one fire at a time ──────────────────────────────────────────────────────
if [ -e "$LOCK" ]; then
  lp="$(cat "$LOCK" 2>/dev/null)"
  if [ -n "$lp" ] && kill -0 "$lp" 2>/dev/null; then log "skip: an integrate fire (pid $lp) is already running"; exit 0; fi
  log "stale lock (pid ${lp:-?}) — clearing"
fi
echo $$ > "$LOCK"
PLOCK_MINE=0
cleanup() { rm -f "$LOCK"; [ "$PLOCK_MINE" = "1" ] && rm -f "$PLOCK"; }
trap cleanup EXIT

# ── preflight — only a MERGE needs the browser, the minutes and the shared lock ──
USED=""
if [ "$ACTION" = "integrate" ]; then
  if ! curl -s -m 5 "$JQ_CDP_URL/json/version" >/dev/null 2>&1; then
    bash "$SCRIPT_DIR/cdp-tunnel.sh" up >/dev/null 2>&1 || true
  fi
  if ! curl -s -m 5 "$JQ_CDP_URL/json/version" >/dev/null 2>&1; then
    log "skip: CDP Chrome not reachable at $JQ_CDP_URL"; exit 0
  fi
  BUDGET="$(node utils/jq-budget.js 2>/dev/null)"
  USED="$(printf '%s' "$BUDGET" | sed -n 's/.*used=\([0-9]*\).*/\1/p')"
  if [ -n "$USED" ] && [ "$USED" -ge "$USAGE_LIMIT" ] 2>/dev/null; then
    log "skip: JQ budget used=${USED}min >= limit=${USAGE_LIMIT}min — wait for the daily reset"; exit 0
  fi

  if [ "${JQ_PIPELINE_LOCK_HELD:-0}" = "1" ]; then
    log "shared lock held by caller — proceeding without re-taking it"
  elif [ -e "$PLOCK" ]; then
    pp="$(cat "$PLOCK" 2>/dev/null)"
    if [ -n "$pp" ] && kill -0 "$pp" 2>/dev/null; then log "skip: another JQ pipeline (pid $pp) is running"; exit 0; fi
    echo $$ > "$PLOCK"; PLOCK_MINE=1
  else
    echo $$ > "$PLOCK"; PLOCK_MINE=1
  fi
else
  log "action=seed — no backtest, no browser: skipping the CDP and budget preflights"
fi

# ── resume this UNIVERSE's own session, or start a clean one ─────────────────
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
PIN="$PIN_DIR/$UNIVERSE.txt"
SID=""
MODE="new"

if [ "${FRESH:-0}" != "1" ] && [ -f "$PIN" ]; then
  pin_branch="$(cut -f1 "$PIN" 2>/dev/null)"
  pin_sid="$(cut -f2 "$PIN" 2>/dev/null)"
  if [ "$pin_branch" = "$BRANCH" ] && [ -n "$pin_sid" ] \
     && ls "$HOME"/.claude/projects/*/"$pin_sid".jsonl >/dev/null 2>&1; then
    holder="$(pgrep -f "$pin_sid" 2>/dev/null | tr '\n' ' ')"
    if [ -n "$holder" ]; then
      log "skip: $UNIVERSE's session $pin_sid is held by pid(s) $holder — close it to hand off"; exit 0
    fi
    SID="$pin_sid"; MODE="resume"
  fi
fi

if [ -z "$SID" ]; then
  SID="$(uuidgen | tr 'A-Z' 'a-z')"
  # ⚠ Never pin on a dry run — see run-family.sh: a DRY=1 preview that pins makes the next real
  # run "resume" a session that never existed.
  [ "${DRY:-0}" = "1" ] || printf '%s\t%s\n' "$BRANCH" "$SID" > "$PIN"
fi

RUN_LOG="$LOG_DIR/$UNIVERSE-$(date '+%Y%m%d-%H%M%S').log"
PERM_FLAG="--permission-mode acceptEdits"
[ "${USE_BYPASS:-0}" = "1" ] && PERM_FLAG="--dangerously-skip-permissions"

if [ "$ACTION" = "seed" ]; then
  TASK="The queue says SEED: $UNIVERSE ships nothing yet and ${ARRIVAL:-an eligible family} is its
first eligible arrival. That is a RECORD, not a judgement — no overlap question, no merge, no
backtest, no agent. Follow the skill's SEED section: write the promote row with
utils/promoted.js (sharpe/objective read from the ledger, and a note saying it was the first),
then stop. Do not open a merge round, and do not spend backtest minutes."
else
  TASK="The queue says INTEGRATE: ${ARRIVAL:-an arrival} meets ${UNIVERSE}'s ${NPROMOTED} promoted
candidate(s). Dispatch the integrate-merger agent per the skill — the overlap judgement, the merge
kind, the decomposition and at most 3 declared candidates are its job; the eligibility, the arrival
order, the bar and the VAL budget are not negotiable and not yours to re-litigate. Backtest cap:
pass --usage-limit $USAGE_LIMIT, foreground/blocking, ONE backtest at a time. The round MUST end in
a write to utils/promoted.js — promote, supersede or reject with a note — because the next arrival
meets whatever that register says."
fi

if [ "$MODE" = "new" ]; then
  PROMPT="/run-integrate $UNIVERSE

This is a FRESH session for this universe: you have no prior context, and the on-disk state is the
whole handoff — data/promoted.tsv, data/integrate-refusals.tsv, wiki/types/, and the family pages
of the arrival and of every promoted candidate's members. Start by running
'node utils/integrate-queue.js' and 'node utils/promoted.js', exactly as the skill requires.

$TASK

Work ONLY this universe and stop when the round is recorded. Stop at a clean git state with a
one-line status naming the outcome and what the universe now ships."
else
  PROMPT="/run-integrate $UNIVERSE

Continuing this universe's own session. Re-read 'node utils/integrate-queue.js' and
'node utils/promoted.js' FIRST and trust the register over your memory: the promoted set, the
arrival order and the earlier refusals may have moved since.

$TASK

Stop at a clean git state with a one-line status."
fi

log "$MODE session ${SID:0:8} for universe $UNIVERSE ($ACTION, arrival ${ARRIVAL:-none}, ${NPROMOTED} promoted, budget ${USED:-n/a}/${USAGE_LIMIT}min) -> $RUN_LOG"

if [ "${DRY:-0}" = "1" ]; then
  log "DRY=1 — would run: claude -p $( [ "$MODE" = resume ] && echo "--resume $SID" || echo "--session-id $SID" ) $PERM_FLAG"
  echo "--- prompt ---"; echo "$PROMPT"
  exit 0
fi

if [ "$MODE" = "resume" ]; then
  JQ_USAGE_LIMIT="$USAGE_LIMIT" claude -p --resume "$SID" "$PROMPT" $PERM_FLAG >"$RUN_LOG" 2>&1
else
  JQ_USAGE_LIMIT="$USAGE_LIMIT" claude -p --session-id "$SID" "$PROMPT" $PERM_FLAG >"$RUN_LOG" 2>&1
fi
rc=$?
tail -n 3 "$RUN_LOG" 2>/dev/null | sed 's/^/    /' | tee -a "$LOG_DIR/wrapper.log" >/dev/null
if [ $rc -ne 0 ]; then
  log "claude exited rc=$rc (likely rate-limited — the pin is kept, next fire resumes this universe)"
else
  log "$UNIVERSE: round complete rc=0 — check data/promoted.tsv, exit 0 is not proof work happened"
fi

# ── did the round actually record an outcome? ───────────────────────────────
# An unrecorded outcome is worse than no round: the next arrival meets the wrong incumbent, and the
# sequence IS the model. rc=0 does not say the register moved, so look.
AFTER="$(node -e '
  const p = require("./utils/promoted");
  const u = process.argv[1];
  const rows = (p.events ? p.events() : []).filter(e => e.universe === u);
  process.stdout.write(String(rows.length));
' "$UNIVERSE" 2>/dev/null)"
log "$UNIVERSE: ${AFTER:-?} row(s) in the promoted register after this round"

# ── Orphan sweep (merge rounds only — a seed starts nothing) ────────────────
# Same rationale as run-family.sh: once the agent has exited nothing can read a running backtest's
# panel, so waiting only converts lost minutes into more lost minutes. Safe because this script
# holds the shared jq-pipeline lock, so a live run right now is ours. Never fails the stage.
if [ "$ACTION" = "integrate" ]; then
  if ! node "$REPO/utils/jq-running.js" >/dev/null 2>&1; then
    log "⚠ a backtest is STILL RUNNING after the agent exited — orphaned; cancelling"
    node "$REPO/utils/jq-cancel.js" --cap-min "$SLOW_SKIP_MIN" 2>&1 | while IFS= read -r l; do log "  $l"; done
  else
    log "account clear — no orphaned backtest"
  fi
fi

exit 0
