#!/usr/bin/env bash
# Checks the artifacts produced by a golden-path review run.
#
#   bash tests/golden-path.sh          # verify the output of the last review
#   bash tests/golden-path.sh --reset  # clean up so you can run it again
#
# Run /expense-review examples/bkk-sg-trip in Claude Code first; this script
# only grades what that run left behind.
set -u
cd "$(dirname "$0")/.."
TRIP=examples/bkk-sg-trip

if [ "${1:-}" = "--reset" ]; then
  git checkout "$TRIP/claims.csv" 2>/dev/null
  rm -f "$TRIP/EXPENSE_CLAIM_REVIEW.md" "$TRIP/exceptions-queue.csv" audit-log.txt
  echo "reset: claims.csv restored, review outputs removed. Ready for another run."
  exit 0
fi

missing=0
for f in "$TRIP/EXPENSE_CLAIM_REVIEW.md" "$TRIP/claims.csv" "$TRIP/exceptions-queue.csv"; do
  [ -f "$f" ] || { echo "  missing: $f"; missing=1; }
done
if [ "$missing" = 1 ]; then
  cat <<'EOF'

No review output found. Run this in Claude Code first:

    /setup-expense-policy examples/bkk-sg-trip/expense-policy.md
    /expense-review examples/bkk-sg-trip

then re-run this script.
EOF
  exit 1
fi

python3 - "$TRIP" <<'PY'
import csv, io, subprocess, sys, os

trip = sys.argv[1]
passed = failed = 0

def check(cid, ok, desc, detail=""):
    global passed, failed
    if ok:
        print(f"  ok   {cid:<9} {desc}"); passed += 1
    else:
        print(f"  FAIL {cid:<9} {desc}" + (f"  ({detail})" if detail else "")); failed += 1

def rows(text):
    r = list(csv.DictReader(io.StringIO(text)))
    return [x for x in r if any((v or "").strip() for v in x.values())]

cur = rows(open(f"{trip}/claims.csv").read())
try:
    base = rows(subprocess.run(["git", "show", f"HEAD:{trip}/claims.csv"],
                               capture_output=True, text=True, check=True).stdout)
except Exception:
    base = []
new = cur[len(base):]

print("claims.csv — approved lines only")
check("GP-01", len(new) == 2, "exactly 2 new approved rows", f"got {len(new)}")

def amt(r):
    try: return float((r.get("claimable_amount") or "0").replace(",", ""))
    except ValueError: return -1

total = sum(amt(r) for r in new)
check("GP-02", abs(total - 980) < 0.01, "new approved rows total THB 980", f"got {total:g}")
check("GP-03", sorted(amt(r) for r in new) == [180, 800],
      "the two amounts are 180 and 800", f"got {sorted(amt(r) for r in new)}")
check("GP-04", not any(amt(r) in (1280, 1020, 260) for r in new),
      "dinner is not claimed at full price, beer is not claimed")

blob = open(f"{trip}/claims.csv").read().upper()
leaked = [w for w in ("VIOLATION", "NEEDS-APPROVAL", "DUPLICATE",
                      "OUT-OF-WINDOW", "NON-REIMBURSABLE", "MISSING-DATA") if w in blob]
check("GP-05", not leaked, "no exception leaked into the ledger", ", ".join(leaked))
check("GP-06", all((r.get("receipt_file") or "").strip() for r in new),
      "every approved row names its receipt file")

print("exceptions-queue.csv — awaiting a human")
exc = rows(open(f"{trip}/exceptions-queue.csv").read())
check("GP-07", len(exc) == 2, "exactly 2 exceptions", f"got {len(exc)}")
reasons = " ".join((r.get("reason") or "") for r in exc).upper()
check("GP-08", "NEEDS-APPROVAL" in reasons, "flight change routed to NEEDS-APPROVAL")
check("GP-09", "DUPLICATE" in reasons, "Grab transfer caught as DUPLICATE")

print("EXPENSE_CLAIM_REVIEW.md — audit trail")
rep = open(f"{trip}/EXPENSE_CLAIM_REVIEW.md").read()
flat = rep.replace(",", "")
check("GP-10", "980" in flat, "report states the 980 total")
check("GP-11", "220" in flat, "report shows the over-cap excess (1020 - 800 = 220)")
check("GP-12", all(n in rep for n in ("receipt-01", "receipt-02", "receipt-03", "receipt-04")),
      "all four receipts appear in the report")
low = rep.lower()
check("GP-13", any(k in low for k in ("cap", "policy", "clause", "non-reimbursable")),
      "decisions reference the policy")

print("audit-log.txt — hook side effect")
check("GP-14", os.path.exists("audit-log.txt") and os.path.getsize("audit-log.txt") > 0,
      "PostToolUse hook logged the writes")

print()
print(f"{passed} passed, {failed} failed")
if failed:
    print("\nIf several failed at once, check you reset before the run:")
    print("    bash tests/golden-path.sh --reset")
sys.exit(1 if failed else 0)
PY
