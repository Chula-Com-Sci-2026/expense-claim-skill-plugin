#!/usr/bin/env bash
# Drive the benchmark: the same three trips reviewed with and without the plugin.
#
#   bash bench/run.sh --dry-run              # print every command, spend nothing
#   bash bench/run.sh                        # all arms, 3 runs, policy A
#   bash bench/run.sh --arm skill --runs 3
#   bash bench/run.sh --policy b
#
# Each run is a fresh session id in a fresh working directory. Nothing is resumed
# and nothing is continued, so no run can see another run's conversation.
# Baseline arms additionally use --safe-mode, which disables CLAUDE.md discovery,
# skills, plugins, hooks and MCP servers. Without it the repo's own CLAUDE.md would
# describe the plugin to the "no plugin" arm — and, worse, this machine has the
# plugin installed globally via enabledPlugins, so the baseline would have been
# running the very thing it is the control for.
#
# --setting-sources project,local drops the USER settings file from every arm; it
# carries a "permissions.defaultMode" that fights --permission-mode. The explicit
# --settings allow rule is what actually makes writes land: without it the skill arm
# completed its whole review and was then denied every output file, reporting the
# result in chat instead. Both flags go through the shared invoke(), so every arm
# runs under byte-identical permission configuration — an allow rule on one arm and
# not the other would compare permission setups, not plugins.
#
# The allow rule lives in bench/bench-settings.json rather than inline: invoke()
# passes its arguments through `eval`, which strips the quoting off inline JSON and
# makes the CLI reject it ("Invalid JSON provided to --settings"). A path has no
# such problem.
#
# Both arms get the same --allowedTools set. An early smoke run had the baseline
# denied a Bash call to read the receipts; it recovered via Read, but a tool denial
# on one arm and not the other would quietly bias the token and time numbers.
set -uo pipefail
cd "$(dirname "$0")/.."
REPO="$PWD"
BENCH="$REPO/bench"

MODEL="${BENCH_MODEL:-sonnet}"
EFFORT="${BENCH_EFFORT:-medium}"
BUDGET="${BENCH_BUDGET:-2.00}"
POLICY="a"
RUNS=3
ARMS="base-strict base-fair skill"
DRY=0
STAMP="$(date +%Y%m%d-%H%M%S)"

while [ $# -gt 0 ]; do
  case "$1" in
    --arm)     ARMS="$2"; shift 2 ;;
    --runs)    RUNS="$2"; shift 2 ;;
    --policy)  POLICY="$2"; shift 2 ;;
    --model)   MODEL="$2"; shift 2 ;;
    --effort)  EFFORT="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    --stamp)   STAMP="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

TRIPS=(trip-1-hanoi trip-2-osaka trip-3-jakarta)
FILING_DATE="$(python3 -c "import re;print(re.search(r'FILING_DATE = \"(.*?)\"',open('$BENCH/datasets.gen.py').read()).group(1))")"

case "$POLICY" in
  a) POLICY_PATH="$BENCH/policies/policy-a.docx"; POLICY_TEXT="$BENCH/policies/policy-a.txt" ;;
  b) POLICY_PATH="$BENCH/policies/policy-b.md";   POLICY_TEXT="$BENCH/policies/policy-b.md" ;;
  *) echo "policy must be a or b" >&2; exit 2 ;;
esac

OUTROOT="$BENCH/results/$STAMP"
mkdir -p "$OUTROOT"

# Run working directories live OUTSIDE the repo. The skill arm passes $REPO to
# --plugin-dir, and writes inside a loaded plugin's own directory are refused as
# tool-configuration tampering ("flagged as sensitive") — the skill would complete a
# whole review and then be denied every output file, while the baseline, loading no
# plugin, wrote to the identical path without complaint. Comparing those two would
# have been comparing sandbox rules, not reviewers. Each workdir is copied back into
# the results tree after its session ends, so the evidence still lands with the run.
WORKROOT="${BENCH_WORKROOT:-${TMPDIR:-/tmp}/expense-bench}/$STAMP"
mkdir -p "$WORKROOT"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
run_or_echo() {
  if [ "$DRY" = 1 ]; then printf '    $ %s\n' "$*"; else eval "$@"; fi
}

# --- the user-global policy store is the skill arm's whole point, so guard it ----
POLICY_HOME="$HOME/.expense-claim-review"
BACKUP=""
restore_policy_home() {
  [ -n "$BACKUP" ] || return 0
  rm -rf "$POLICY_HOME"
  mv "$BACKUP" "$POLICY_HOME"
  echo "restored your existing policy store from $BACKUP"
}
trap restore_policy_home EXIT

assemble_prompt() { # assemble_prompt <arm> <workdir> <ledger-file-or-empty>
  local arm="$1" wd="$2" ledger="${3:-}"
  local src="$BENCH/prompts/$arm.md"
  python3 - "$src" "$POLICY_TEXT" "$BENCH/prompts/template.md" "$FILING_DATE" "$ledger" <<'PY'
import sys
src, policy, template, filing, ledger = sys.argv[1:6]
s = open(src).read()
s = s.replace("{{POLICY}}", open(policy).read().strip())
s = s.replace("{{TEMPLATE}}", open(template).read().strip())
s = s.replace("{{FILING_DATE}}", filing)
led = open(ledger).read().strip() if ledger else "(no previous claims on file)"
s = s.replace("{{LEDGER}}", led)
sys.stdout.write(s)
PY
}

# Stop the whole matrix the first time a session comes back unusable (usage limit,
# auth failure). Such a run still exits 0 and still writes a result event, so
# without this the remaining sessions burn in about a second each for nothing.
check_usable() {
  [ -s "$1" ] || return 0
  local msg rc
  msg="$(python3 "$BENCH/check-usable.py" "$1")"; rc=$?
  if [ "$rc" = 3 ]; then
    printf '\n\033[1mABORTED\033[0m  %s\n' "$msg" >&2
    echo "  partial results kept in $OUTROOT — rerun when it resets." >&2
    exit 3
  fi
}

invoke() { # invoke <workdir> <promptfile> <outfile> <extra flags...>
  local wd="$1" pf="$2" of="$3"; shift 3
  local sid; sid="$(uuidgen)"
  echo "$sid" > "$(dirname "$of")/session-id.txt"
  run_or_echo claude -p --output-format stream-json --verbose \
      --session-id "$sid" \
      --model "$MODEL" --effort "$EFFORT" \
      --permission-mode acceptEdits --permission-prompts none \
      --setting-sources project,local \
      --allowedTools Bash Read Write Edit Glob Grep Agent \
      --settings "$BENCH/bench-settings.json" \
      --max-budget-usd "$BUDGET" \
      --add-dir "$REPO" \
      "$@" \
      '<' "$pf" '>' "$of" '2>' "$(dirname "$of")/stderr.txt"
  [ "$DRY" = 1 ] || check_usable "$of"
}

for arm in $ARMS; do
  say "ARM: $arm   (policy $POLICY, model $MODEL, effort $EFFORT)"

  if [ "$arm" = "skill" ]; then
    # Fresh policy store, then configure it once — exactly as a real team would.
    if [ -d "$POLICY_HOME" ] && [ -z "$BACKUP" ]; then
      BACKUP="$POLICY_HOME.bak-$STAMP"
      run_or_echo mv "$POLICY_HOME" "$BACKUP"
    fi
    run_or_echo rm -rf "$POLICY_HOME"
    run_or_echo mkdir -p "$POLICY_HOME"
    sd="$OUTROOT/$arm/setup"; mkdir -p "$sd"
    swd="$WORKROOT/$arm/setup"; mkdir -p "$swd"
    sed "s#{{POLICY_PATH}}#$POLICY_PATH#; s#{{FILING_DATE}}#$FILING_DATE#" \
      "$BENCH/prompts/setup.md" > "$sd/prompt.txt"
    echo "  setup: /expense-claim-review:setup-expense-policy"
    ( cd "$swd" && invoke . "$sd/prompt.txt" "$sd/stream.jsonl" \
        --plugin-dir "$REPO" --add-dir "$POLICY_HOME" )
    [ "$DRY" = 1 ] || cp -R "$swd" "$sd/workdir"
  fi

  prev_claims=""
  for i in $(seq 1 "$RUNS"); do
    trip="${TRIPS[$((i-1))]}"
    rd="$OUTROOT/$arm/run$i"
    wd="$WORKROOT/$arm/run$i"
    mkdir -p "$wd" "$rd"
    cp -R "$BENCH/datasets/$trip/." "$wd/"
    rm -f "$wd/expected-a.json" "$wd/expected-b.json"   # never show the grader's key

    # Ledger continuity. The skill arm carries claims.csv forward on disk, which is
    # how run 2 and 3 detect duplicates. base-fair gets the same rows pasted into
    # the prompt instead. base-strict gets nothing — that is the arm's definition.
    ledger_arg=""
    case "$arm" in
      skill)
        if [ -n "$prev_claims" ] && [ -f "$prev_claims" ]; then
          cp "$prev_claims" "$wd/claims.csv"
        else
          echo "date,vendor,category,claimable_amount,receipt_file,review_date" > "$wd/claims.csv"
        fi ;;
      base-fair)
        ledger_arg="${prev_claims:-}" ;;
    esac

    assemble_prompt "$arm" "$wd" "$ledger_arg" > "$rd/prompt.txt"

    cat > "$rd/meta.json" <<JSON
{"arm":"$arm","run":$i,"trip":"$trip","policy":"$POLICY","model":"$MODEL",
 "effort":"$EFFORT","filing_date":"$FILING_DATE","stamp":"$STAMP",
 "started_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
JSON

    echo "  run $i: $trip"
    case "$arm" in
      skill)
        ( cd "$wd" && invoke . "$rd/prompt.txt" "$rd/stream.jsonl" \
            --plugin-dir "$REPO" --add-dir "$POLICY_HOME" ) ;;
      skill-noagents)
        ( cd "$wd" && invoke . "$rd/prompt.txt" "$rd/stream.jsonl" \
            --plugin-dir "$REPO" --add-dir "$POLICY_HOME" --disallowedTools Agent ) ;;
      *)
        ( cd "$wd" && invoke . "$rd/prompt.txt" "$rd/stream.jsonl" \
            --safe-mode --strict-mcp-config ) ;;
    esac

    python3 - "$rd/meta.json" <<'PY'
import json, sys, datetime
p = sys.argv[1]; m = json.load(open(p))
m["finished_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
json.dump(m, open(p, "w"), indent=2)
PY

    # Archive the workdir with its results, then keep pointing the ledger at the
    # live copy so the next run of this arm inherits it.
    [ "$DRY" = 1 ] || cp -R "$wd" "$rd/workdir"
    [ -f "$wd/claims.csv" ] && prev_claims="$wd/claims.csv"
  done
done

if [ "$DRY" = 0 ]; then
  ln -sfn "$OUTROOT" "$BENCH/results/latest"
  say "done -> $OUTROOT   (also bench/results/latest)"
  echo "next:  python3 bench/measure.py && python3 bench/score.py && python3 bench/report.py"
else
  say "dry run only — nothing executed, nothing spent"
fi
