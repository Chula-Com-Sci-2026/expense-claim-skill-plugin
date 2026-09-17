#!/usr/bin/env bash
# Automated tests for the deterministic hook scripts.
# Usage: bash tests/hooks.sh
set -u
cd "$(dirname "$0")/.."
BLOCK=hooks/scripts/block-out-of-policy.sh
LOG=hooks/scripts/log-decision.sh
pass=0; fail=0

check() { # check <id> <expected-exit> <actual-exit> <description>
  if [ "$2" = "$3" ]; then
    printf '  ok   %-9s %s\n' "$1" "$4"; pass=$((pass+1))
  else
    printf '  FAIL %-9s %s (expected exit %s, got %s)\n' "$1" "$4" "$2" "$3"; fail=$((fail+1))
  fi
}

run_block() { printf '%s' "$1" | bash "$BLOCK" >/dev/null 2>&1; echo $?; }

echo "block-out-of-policy.sh"
check HOOK-01 2 "$(run_block '{"tool_name":"Write","tool_input":{"file_path":"/t/claims.csv","content":"2026-08-11,Jumbo,meal,1280,r2.txt,VIOLATION"}}')" \
  "VIOLATION into claims.csv is blocked"
check HOOK-02 0 "$(run_block '{"tool_name":"Write","tool_input":{"file_path":"/t/claims.csv","content":"2026-08-10,Tian Tian,meal,180,r1.txt,2026-09-17"}}')" \
  "clean claims.csv row is allowed"
check HOOK-03 0 "$(run_block '{"tool_name":"Write","tool_input":{"file_path":"/t/exceptions-queue.csv","content":"2026-08-12,SQ,4500,VIOLATION,r3.txt"}}')" \
  "VIOLATION in exceptions-queue.csv is allowed"
check HOOK-04 2 "$(run_block '{"tool_name":"Edit","tool_input":{"file_path":"/t/claims.csv","new_string":"VIOLATION row"}}')" \
  "Edit path is covered, not just Write"
check HOOK-05 0 "$(run_block 'not json at all')" \
  "malformed payload does not wedge the session"
check HOOK-06 0 "$(run_block '{"tool_name":"Write","tool_input":{"file_path":"/t/notes.md","content":"VIOLATION"}}')" \
  "VIOLATION outside claims.csv is allowed"

echo "log-decision.sh"
tmp="$(mktemp -d)"
printf '%s' '{"tool_name":"Write","tool_input":{"file_path":"/t/claims.csv"}}' \
  | CLAUDE_PROJECT_DIR="$tmp" bash "$LOG" >/dev/null 2>&1
line="$(cat "$tmp/audit-log.txt" 2>/dev/null)"
case "$line" in
  *"	Write	/t/claims.csv") check HOOK-07 0 0 "audit line is written tab-separated" ;;
  *) check HOOK-07 0 1 "audit line is written tab-separated (got: ${line:-<empty>})" ;;
esac
rm -rf "$tmp"

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
