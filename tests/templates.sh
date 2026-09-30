#!/usr/bin/env bash
# Automated tests for the two schema-driven validators.
# Usage: bash tests/templates.sh
#
# Builds a throwaway trip folder out of the shipped example CSVs, so a pass here
# also proves the examples in templates/ are internally consistent.
set -u
cd "$(dirname "$0")/.."
ROOT="$PWD"
SUB=scripts/validate_submission.py
REV=scripts/validate_review.py
SCHEMA="--schema=$ROOT/templates/template-schema.json"
pass=0; fail=0

check() { # check <id> <expected-exit> <actual-exit> <description>
  if [ "$2" = "$3" ]; then
    printf '  ok   %-9s %s\n' "$1" "$4"; pass=$((pass+1))
  else
    printf '  FAIL %-9s %s (expected exit %s, got %s)\n' "$1" "$4" "$2" "$3"; fail=$((fail+1))
  fi
}

says() { # says <id> <needle> <output> <description>
  case "$3" in
    *"$2"*) printf '  ok   %-9s %s\n' "$1" "$4"; pass=$((pass+1)) ;;
    *) printf '  FAIL %-9s %s (no "%s" in output)\n' "$1" "$4" "$2"; fail=$((fail+1)) ;;
  esac
}

build() { # build <dir> — a clean, valid trip folder from the shipped examples
  local d="$1"
  mkdir -p "$d/receipts"
  cp "$ROOT/templates/submission-example.csv" "$d/submission.csv"
  cp "$ROOT/templates/finance-review-example.csv" "$d/finance-review.csv"
  cp "$ROOT/templates/trip-template.md" "$d/trip.md"
  # every receipt_file named by either example
  python3 - "$d" <<'PY'
import csv, os, sys
d = sys.argv[1]
names = set()
for f in ("submission.csv", "finance-review.csv"):
    for row in csv.DictReader(open(os.path.join(d, f), newline="")):
        if (row.get("receipt_file") or "").strip():
            names.add(row["receipt_file"].strip())
for n in names:
    open(os.path.join(d, "receipts", n), "w").write("fixture receipt\n")

# derive the two ledgers the way a review would
rows = list(csv.DictReader(open(os.path.join(d, "finance-review.csv"), newline="")))
with open(os.path.join(d, "claims.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date", "vendor", "category", "claimable_amount", "receipt_file", "review_date"])
    for r in rows:
        if r["decision"] in ("APPROVE", "REDUCE"):
            w.writerow([r["date"], r["vendor"], r["category"], r["claimable_amount"],
                        r["receipt_file"], "2026-08-21"])
with open(os.path.join(d, "exceptions-queue.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date", "vendor", "amount", "reason", "receipt_file"])
    for r in rows:
        if r["decision"] == "ESCALATE":
            w.writerow([r["date"], r["vendor"], r["submitted_amount"],
                        r["verdict_code"] + ": " + r["reason"], r["receipt_file"]])
PY
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "validate_submission.py"
build "$tmp/good"
out="$(python3 "$SUB" "$tmp/good" "$SCHEMA" 2>&1)"; code=$?
check TPL-01 0 "$code" "the shipped submission example passes"

build "$tmp/nosum"
python3 - "$tmp/nosum/submission.csv" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read().replace(",62.00,USD,receipt-02-group-dinner.txt", ",50.00,USD,receipt-02-group-dinner.txt")
open(p, "w").write(s)
PY
out="$(python3 "$SUB" "$tmp/nosum" "$SCHEMA" 2>&1)"; code=$?
check TPL-02 1 "$code" "split rows that miss receipt_total are caught"
says TPL-03 "receipt_total is 246.00" "$out" "the gap is named in the employee's own terms"

build "$tmp/noreceipt"
rm "$tmp/noreceipt/receipts/receipt-04-hotel.txt"
out="$(python3 "$SUB" "$tmp/noreceipt" "$SCHEMA" 2>&1)"; code=$?
check TPL-04 1 "$code" "a receipt_file with no file is caught"
says TPL-05 "not found in receipts/" "$out" "the missing receipt is named"

build "$tmp/notrip"
rm "$tmp/notrip/trip.md"
out="$(python3 "$SUB" "$tmp/notrip" "$SCHEMA" 2>&1)"; code=$?
check TPL-06 1 "$code" "a missing trip.md is caught"

echo "validate_review.py"
out="$(python3 "$REV" "$tmp/good" "$SCHEMA" 2>&1)"; code=$?
check TPL-07 0 "$code" "the shipped review example passes"

build "$tmp/arith"
python3 - "$tmp/arith/finance-review.csv" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read().replace("REDUCE,34.00,34.00", "REDUCE,34.00,10.00")
open(p, "w").write(s)
PY
out="$(python3 "$REV" "$tmp/arith" "$SCHEMA" 2>&1)"; code=$?
check TPL-08 1 "$code" "REDUCE arithmetic that does not add up is caught"
says TPL-09 "REDUCE arithmetic" "$out" "the arithmetic is shown"

build "$tmp/escalate"
python3 - "$tmp/escalate/finance-review.csv" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read().replace(
    "Employee: add attendee names with titles/affiliations and the business purpose", "")
open(p, "w").write(s)
PY
out="$(python3 "$REV" "$tmp/escalate" "$SCHEMA" 2>&1)"; code=$?
check TPL-10 1 "$code" "an ESCALATE with no action_needed is caught"

build "$tmp/missingline"
python3 - "$tmp/missingline/finance-review.csv" <<'PY'
import sys
p = sys.argv[1]
lines = open(p).read().splitlines(True)
open(p, "w").writelines(lines[:-1])
PY
out="$(python3 "$REV" "$tmp/missingline" "$SCHEMA" 2>&1)"; code=$?
check TPL-11 1 "$code" "a submitted line with no decision is caught"
says TPL-12 "submitted but never decided" "$out" "the undecided line is named"

build "$tmp/ledger"
python3 - "$tmp/ledger/claims.csv" <<'PY'
import sys
p = sys.argv[1]
lines = open(p).read().splitlines(True)
open(p, "w").writelines(lines[:-1])
PY
out="$(python3 "$REV" "$tmp/ledger" "$SCHEMA" 2>&1)"; code=$?
check TPL-13 1 "$code" "a ledger that lost a row is caught"

echo "schema is the single source of column names"
build "$tmp/override"
python3 - "$tmp/override/schema.json" "$ROOT/templates/template-schema.json" <<'PY'
import json, sys
schema = json.load(open(sys.argv[2]))
for col in schema["submission"]["columns"]:
    if col["name"] == "employee_note":
        col["name"] = "note_for_finance"
json.dump(schema, open(sys.argv[1], "w"))
PY
out="$(python3 "$SUB" "$tmp/override" "--schema=$tmp/override/schema.json" 2>&1)"; code=$?
check TPL-14 1 "$code" "renaming a column in the schema changes what is accepted"

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
