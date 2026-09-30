#!/usr/bin/env python3
"""Check a finished review against template-schema.json -> finance_review.

    python3 scripts/validate_review.py <folder>

finance-review.csv is the source of truth: one row per submitted line, one decision
each, with claims.csv and exceptions-queue.csv derived from it. This script enforces
exactly that, plus the per-row arithmetic. Exits 1 and lists every problem.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _checks as C  # noqa: E402
import _schema as S  # noqa: E402


def read_rows(path):
    if not os.path.exists(path):
        return None, []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows = [r for r in reader if any((v or "").strip() for v in r.values())]
    return header, rows


def check_row(row, schema, problems):
    """The row_rules in the schema, in the order the template states them."""
    line = (row.get("line") or "?").strip()
    tag = "line %s " % line
    decision = (row.get("decision") or "").strip()
    decisions = S.enum(schema, "decision")
    verdicts = S.enum(schema, "verdict_code")

    if decision not in decisions:
        problems.append("%s decision %r is not one of %s" % (tag, decision, ", ".join(decisions)))
        return

    verdict = (row.get("verdict_code") or "").strip()
    if verdict not in verdicts:
        problems.append("%s verdict_code %r is not a plugin verdict" % (tag, verdict))

    if C.is_blank(row.get("policy_clause")):
        problems.append("%s policy_clause is empty; every decision cites a clause or UNSPECIFIED" % tag)
    if C.is_blank(row.get("reason")):
        problems.append("%s reason is empty" % tag)

    submitted = C.number(row.get("submitted_amount"))
    receipt = C.number(row.get("receipt_amount"))
    base = receipt if receipt is not None else submitted
    claimable = C.number(row.get("claimable_amount"))
    non_claimable = C.number(row.get("non_claimable_amount"))

    if claimable is None or non_claimable is None:
        problems.append("%s claimable_amount and non_claimable_amount are both required numbers" % tag)
        return

    if receipt is not None and submitted is not None and abs(receipt - submitted) > 0.01:
        if verdict != "MANIFEST-MISMATCH":
            problems.append("%s receipt %.2f differs from submitted %.2f; verdict_code must be MANIFEST-MISMATCH"
                            % (tag, receipt, submitted))
        for number in ("%.2f" % receipt, "%.2f" % submitted):
            if number.rstrip("0").rstrip(".") not in (row.get("reason") or "").replace(",", ""):
                problems.append("%s reason must state both numbers (%.2f and %.2f)" % (tag, receipt, submitted))
                break

    if decision == "ESCALATE":
        if claimable != 0 or non_claimable != 0:
            problems.append("%s ESCALATE pays nothing yet: both amounts must be 0" % tag)
        if C.is_blank(row.get("action_needed")):
            problems.append("%s ESCALATE needs action_needed: who must act, and what they need" % tag)
        return

    if base is None:
        problems.append("%s no submitted_amount and no receipt_amount to decide against" % tag)
        return

    if decision == "APPROVE":
        if abs(claimable - base) > 0.01 or abs(non_claimable) > 0.01:
            problems.append("%s APPROVE must pay the full %.2f with 0 non-claimable (got %.2f / %.2f)"
                            % (tag, base, claimable, non_claimable))
    elif decision == "REDUCE":
        if not (0 < claimable < base - 0.01):
            problems.append("%s REDUCE must pay part of %.2f, not %.2f" % (tag, base, claimable))
        if abs(non_claimable - (base - claimable)) > 0.01:
            problems.append("%s REDUCE arithmetic: %.2f - %.2f = %.2f, but non_claimable_amount is %.2f"
                            % (tag, base, claimable, base - claimable, non_claimable))
    elif decision == "REJECT":
        if abs(claimable) > 0.01 or abs(non_claimable - base) > 0.01:
            problems.append("%s REJECT pays 0 and records %.2f as non-claimable (got %.2f / %.2f)"
                            % (tag, base, claimable, non_claimable))


def check(folder, schema):
    spec = schema["finance_review"]
    problems = []
    path = os.path.join(folder, spec["file"])
    header, rows = read_rows(path)

    if header is None:
        return ["%s  not found; the review writes it before any ledger" % spec["file"]]

    trouble = C.header_problem(header, S.columns(spec))
    if trouble:
        return ["header  %s" % trouble]

    for name in S.required(spec):
        for row in rows:
            if C.is_blank(row.get(name)):
                problems.append("line %s  %s is empty" % ((row.get("line") or "?").strip(), name))

    for row in rows:
        check_row(row, schema, problems)

    # one row per submitted line, same line numbers
    sub_header, sub_rows = read_rows(os.path.join(folder, schema["submission"]["file"]))
    if sub_header is not None:
        submitted_lines = [(r.get("line") or "").strip() for r in sub_rows]
        reviewed_lines = [(r.get("line") or "").strip() for r in rows]
        for line in submitted_lines:
            if reviewed_lines.count(line) == 0:
                problems.append("line %s  submitted but never decided" % line)
            elif reviewed_lines.count(line) > 1:
                problems.append("line %s  decided %d times; one line, one decision"
                                % (line, reviewed_lines.count(line)))
        for line in reviewed_lines:
            if line not in submitted_lines:
                problems.append("line %s  decided but not in %s" % (line, schema["submission"]["file"]))

    problems += check_derived(folder, schema, rows)
    return problems


def check_derived(folder, schema, rows):
    """claims.csv and exceptions-queue.csv must match what the decision sheet says."""
    problems = []
    derived = schema["finance_review"]["derived_outputs"]

    for name, rule in derived.items():
        expected = [r for r in rows if (r.get("decision") or "").strip() in rule["from_decisions"]]
        header, present = read_rows(os.path.join(folder, name))
        if header is None:
            if expected:
                problems.append("%s  not found, but %d row(s) decided %s"
                                % (name, len(expected), "/".join(rule["from_decisions"])))
            continue
        trouble = C.header_problem(header, rule["columns"])
        if trouble:
            problems.append("%s  %s" % (name, trouble))
            continue
        if len(present) < len(expected):
            problems.append("%s  holds %d row(s); this review decided %d line(s) %s"
                            % (name, len(present), len(expected), "/".join(rule["from_decisions"])))
            continue
        appended = present[len(present) - len(expected):] if expected else []
        if name == "claims.csv" and expected:
            want = sum(C.number(r.get("claimable_amount")) or 0.0 for r in expected)
            got = sum(C.number(r.get("claimable_amount")) or 0.0 for r in appended)
            if abs(want - got) > 0.01:
                problems.append("claims.csv  appended rows total %.2f, the decision sheet says %.2f"
                                % (got, want))
    return problems


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    folder = args[0] if args else "."
    explicit = None
    for a in sys.argv[1:]:
        if a.startswith("--schema="):
            explicit = a.split("=", 1)[1]
    schema, _ = S.load(explicit)
    problems = check(folder, schema)
    name = schema["finance_review"]["file"]
    if problems:
        print("FAIL %s" % name)
        for p in problems:
            print("  %s" % p)
        return 1
    print("PASS %s" % name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
