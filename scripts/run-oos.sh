#!/usr/bin/env bash
#
# run-oos.sh [family] — spend ONE out-of-sample test on the candidate a universe ships.
#
# ## ⚠⚠ Read this before changing anything here
#
# This is the only wrapper that spends an IRREVERSIBLE resource. The 2026+ reserve is **2 tests
# per bench and 1 per candidate, absolute** — once a candidate has been looked at there, nothing is
# left but waiting for more calendar, and no re-run, re-scoring or epoch bump un-sees it.
#
# OOS was deliberately kept OUT of the daily pipeline for exactly that reason, and the author of
# this file argued for keeping it out. **User decision, 2026-10-17: connect it to integrate's
# output anyway.** The argument that it is safe to automate is not "it does not matter" — it is
# that the ceiling is enforced in CODE and not by the absence of a queue:
#
#   1. `utils/oos-budget.js` refuses past 1/candidate or 2/bench, checked in
#      `strategy-post-backtest.js` BEFORE the browser opens;
#   2. `OOS-READINESS` refuses a family `integrate-eligible` does not call eligible;
#   3. `utils/oos-queue.js` only reports `ready` for a candidate that is untested, within budget,
#      and has a PINNED runnable artifact.
#
# So when the bench's two tests are gone the queue is empty, depth is 0, and this stage simply
# never runs again until a bench change. That is the stop — not a human remembering.
#
# ⚠ It still does NOT set `JQ_ALLOW_OOS_OVERBUDGET` or `JQ_ALLOW_OOS_UNREADY`. Those override the
# protections above and remain the human's, as env vars, on purpose.
#
#   pins: data/oos-sessions/<family>.txt   ("<branch>\t<uuid>")
#
# Usage:
#   scripts/run-oos.sh              # take the queue's ready head
#   scripts/run-oos.sh 红利低频       # a named family
#   scripts/run-oos.sh --list       # the OOS queue and each session's state
#   DRY=1 scripts/run-oos.sh        # print what would run, spend nothing
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
USAGE_LIMIT="${USAGE_LIMIT:-55}"
JQ_CDP_URL="${JQ_CDP_URL:-http://localhost:9225}"
PIN_DIR="$REPO/data/oos-sessions"
LOG_DIR="$REPO/data/autooos-logs"
LOCK="$REPO/data/autooos.lock"
PLOCK="$REPO/data/jq-pipeline.lock"
mkdir -p "$PIN_DIR" "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG_DIR/wrapper.log"; }
cd "$REPO" || { echo "FATAL: cannot cd to $REPO" >&2; exit 1; }

if [ "${1:-}" = "--list" ]; then
  node utils/oos-queue.js
  echo
  echo "  session state:"
  shopt -s nullglob
  for f in "$PIN_DIR"/*.txt; do
    u="$(basename "$f" .txt)"; sid="$(cut -f2 "$f" 2>/dev/null)"
    printf '   %-14s %s\n' "$u" "${sid:0:8}"
  done
  shopt -u nullglob
  exit 0
fi

# ── which candidate, resolved from the queue (never from an argument alone) ──
# A named family still has to be `ready` in the queue: the queue is what knows the budget, the
# readiness gate and whether a pinned artifact exists.
WANT="${1:-}"
ROW="$(node -e '
  const q = require("./utils/oos-queue").build();
  const want = process.argv[1] || "";
  const pick = want
    ? q.find(r => (r.members || []).includes(want) || r.universe === want)
    : q.find(r => r.state === "ready");
  if (!pick) { process.stdout.write(want ? "no-such-candidate\t" + want : "none\t"); process.exit(0); }
  process.stdout.write([pick.state, (pick.members || [])[0] || pick.universe, pick.candidateId,
                        pick.runFile || "", (pick.flags || []).join("; "),
                        (pick.why || "").replace(/\s+/g, " ")].join("\t"));
' "$WANT" 2>/dev/null)"

STATE="$(printf '%s' "$ROW" | cut -f1)"
FAMILY="$(printf '%s' "$ROW" | cut -f2)"
CANDIDATE="$(printf '%s' "$ROW" | cut -f3)"
RUNFILE="$(printf '%s' "$ROW" | cut -f4)"
FLAGS="$(printf '%s' "$ROW" | cut -f5)"
WHY="$(printf '%s' "$ROW" | cut -f6)"

case "$STATE" in
  none)              log "nothing ready — integrate has shipped no untested candidate"; exit 0 ;;
  no-such-candidate) log "FATAL: $FAMILY is not in the OOS queue (node utils/oos-queue.js)"; exit 1 ;;
  tested)            log "skip: $FAMILY already spent its look — $WHY"; exit 0 ;;
  unrunnable)        log "skip: $FAMILY has no PINNED artifact — $WHY"; exit 0 ;;
  blocked)           log "skip: $FAMILY blocked — $WHY"; exit 0 ;;
  ready) ;;
  *)                 log "FATAL: could not read the OOS queue (state='${STATE}')"; exit 1 ;;
esac
[ -n "$RUNFILE" ] || { log "FATAL: ready with no runnable artifact — refusing"; exit 1; }

# ── one fire at a time ──────────────────────────────────────────────────────
if [ -e "$LOCK" ]; then
  lp="$(cat "$LOCK" 2>/dev/null)"
  if [ -n "$lp" ] && kill -0 "$lp" 2>/dev/null; then log "skip: an OOS fire (pid $lp) is running"; exit 0; fi
  log "stale lock (pid ${lp:-?}) — clearing"
fi
echo $$ > "$LOCK"
PLOCK_MINE=0
cleanup() { rm -f "$LOCK"; [ "$PLOCK_MINE" = "1" ] && rm -f "$PLOCK"; }
trap cleanup EXIT

if ! curl -s -m 5 "$JQ_CDP_URL/json/version" >/dev/null 2>&1; then
  bash "$SCRIPT_DIR/cdp-tunnel.sh" up >/dev/null 2>&1 || true
fi
if ! curl -s -m 5 "$JQ_CDP_URL/json/version" >/dev/null 2>&1; then
  log "skip: CDP Chrome not reachable at $JQ_CDP_URL"; exit 0
fi
BUDGET="$(node utils/jq-budget.js 2>/dev/null)"
USED="$(printf '%s' "$BUDGET" | sed -n 's/.*used=\([0-9]*\).*/\1/p')"
if [ -n "$USED" ] && [ "$USED" -ge "$USAGE_LIMIT" ] 2>/dev/null; then
  log "skip: JQ budget used=${USED}min >= limit=${USAGE_LIMIT}min"; exit 0
fi
if [ "${JQ_PIPELINE_LOCK_HELD:-0}" = "1" ]; then
  log "shared lock held by caller"
elif [ -e "$PLOCK" ]; then
  pp="$(cat "$PLOCK" 2>/dev/null)"
  if [ -n "$pp" ] && kill -0 "$pp" 2>/dev/null; then log "skip: another JQ pipeline (pid $pp) is running"; exit 0; fi
  echo $$ > "$PLOCK"; PLOCK_MINE=1
else
  echo $$ > "$PLOCK"; PLOCK_MINE=1
fi

# ── session, pinned per FAMILY ──────────────────────────────────────────────
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
PIN="$PIN_DIR/$FAMILY.txt"
SID=""; MODE="new"
if [ "${FRESH:-0}" != "1" ] && [ -f "$PIN" ]; then
  pin_branch="$(cut -f1 "$PIN" 2>/dev/null)"; pin_sid="$(cut -f2 "$PIN" 2>/dev/null)"
  if [ "$pin_branch" = "$BRANCH" ] && [ -n "$pin_sid" ] \
     && ls "$HOME"/.claude/projects/*/"$pin_sid".jsonl >/dev/null 2>&1; then
    holder="$(pgrep -f "$pin_sid" 2>/dev/null | tr '\n' ' ')"
    if [ -n "$holder" ]; then log "skip: $FAMILY's session is held by pid(s) $holder"; exit 0; fi
    SID="$pin_sid"; MODE="resume"
  fi
fi
if [ -z "$SID" ]; then
  SID="$(uuidgen | tr 'A-Z' 'a-z')"
  [ "${DRY:-0}" = "1" ] || printf '%s\t%s\n' "$BRANCH" "$SID" > "$PIN"
fi

RUN_LOG="$LOG_DIR/$FAMILY-$(date '+%Y%m%d-%H%M%S').log"
PERM_FLAG="--permission-mode acceptEdits"
[ "${USE_BYPASS:-0}" = "1" ] && PERM_FLAG="--dangerously-skip-permissions"

PROMPT="/run-oos $FAMILY

The OOS queue says this candidate is READY. Follow the skill in order and do not skip step 2.

  family     : $FAMILY
  candidate  : $CANDIDATE      (the promoted book — what the budget charges)
  run this   : $RUNFILE
  budget     : $WHY${FLAGS:+
  ⚠ FLAGS    : $FLAGS}

⚠ Pass --source-file $CANDIDATE so the budget, the promoted register and the stored curve all key
on the BOOK and not on the pinned copy you execute. The candidate and the file differ on purpose:
a raw strategies/*.py carries none of the frozen pins and the executor refuses it with
UNPINNED-STOP, so the runnable form is the family's pinned baseline — which is also the artifact
its VAL ran.

⚠⚠ DECLARE THE EXPECTATION BEFORE THE NUMBER EXISTS (skill step 2). Say what each outcome would
mean, and specifically whether a weak result would be NEW INFORMATION or merely confirmation of a
caveat the family already declared. Once the number is visible every reading of it is contaminated.

Never set JQ_ALLOW_OOS_OVERBUDGET or JQ_ALLOW_OOS_UNREADY. If the run is refused, the refusal IS
the answer — report it. Record the result per step 5, and stop at a clean git state."

log "$MODE session ${SID:0:8} | family $FAMILY | candidate $CANDIDATE | run $RUNFILE | budget ${USED:-?}/${USAGE_LIMIT}min -> $RUN_LOG"
[ -n "$FLAGS" ] && log "  ⚠ $FLAGS"

if [ "${DRY:-0}" = "1" ]; then
  log "DRY=1 — would run: claude -p $( [ "$MODE" = resume ] && echo "--resume $SID" || echo "--session-id $SID" )"
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
log "$FAMILY: rc=$rc — verify with 'node utils/oos-budget.js'; exit 0 is not proof a test was spent"

# ── did the reserve actually move? ──────────────────────────────────────────
node utils/oos-budget.js 2>&1 | grep -E "spent on this bench" | sed 's/^/    /' | tee -a "$LOG_DIR/wrapper.log" >/dev/null

if ! node "$REPO/utils/jq-running.js" >/dev/null 2>&1; then
  log "⚠ a backtest is STILL RUNNING after the agent exited — orphaned; cancelling"
  node "$REPO/utils/jq-cancel.js" --cap-min 45 2>&1 | while IFS= read -r l; do log "  $l"; done
fi
exit 0
