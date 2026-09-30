#!/usr/bin/env python3
"""Check an employee submission against template-schema.json -> submission.

    python3 scripts/validate_submission.py <folder>

Prints one line per problem so the employee knows exactly what to fix, and exits 1.
Exits 0 and prints "PASS submission.csv" when the package is ready for finance.

The rules are not written here — they are read from the schema, so an override at
~/.expense-claim-review/templates/template-schema.json changes what is accepted.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _checks as C  # noqa: E402
import _schema as S  # noqa: E402


def read_rows(path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows = [r for r in reader if any((v or "").strip() for v in r.values())]
    return header, rows


def check(folder, schema):
    spec = schema["submission"]
    expected = S.columns(spec)
    required = set(S.required(spec))
    problems = []
    path = os.path.join(folder, spec["file"])

    if not os.path.exists(path):
        return ["%s  not found" % spec["file"]]

    header, rows = read_rows(path)
    trouble = C.header_problem(header, expected)
    if trouble:
        problems.append("header  %s" % trouble)
        return problems  # nothing below can be trusted

    for name in spec.get("forbidden_columns", []):
        if name in header:
            problems.append("header  %s is a finance column; the submission never decides" % name)

    categories = S.enum(schema, "category")
    flags = S.enum(schema, "self_flag")
    receipts_dir = os.path.join(folder, "receipts")
    seen_lines = {}
    seen_keys = {}
    totals = {}

    for row in rows:
        line = (row.get("line") or "?").strip()
        tag = "line %s " % line

        for name in required:
            if C.is_blank(row.get(name)):
                problems.append("%s %s is empty" % (tag, name))

        if not line.isdigit():
            problems.append("%s line must be a whole number" % tag)
        elif line in seen_lines:
            problems.append("%s line number is used twice" % tag)
        else:
            seen_lines[line] = row

        if not C.is_blank(row.get("date")) and C.bad_date(row.get("date")):
            problems.append("%s date %r is not YYYY-MM-DD" % (tag, row.get("date")))

        if not C.is_blank(row.get("currency")) and C.bad_currency(row.get("currency")):
            problems.append("%s currency %r is not an ISO code" % (tag, row.get("currency")))

        category = (row.get("category") or "").strip()
        if category and category not in categories:
            problems.append("%s category %r is not one of %s" % (tag, category, ", ".join(categories)))

        flag = (row.get("self_flag") or "").strip()
        if flag not in flags:
            problems.append("%s self_flag %r is not an advisory flag" % (tag, flag))

        price = C.number(row.get("price"))
        if C.is_blank(row.get("price")):
            if flag != "MISSING-DATA":
                problems.append("%s price is blank; blank is only allowed with self_flag MISSING-DATA" % tag)
        elif price is None:
            problems.append("%s price %r is not a number" % (tag, row.get("price")))

        receipt = (row.get("receipt_file") or "").strip()
        if receipt:
            if not os.path.exists(os.path.join(receipts_dir, receipt)):
                problems.append("%s receipt_file %s not found in receipts/" % (tag, receipt))
            total = C.number(row.get("receipt_total"))
            if total is None:
                if not C.is_blank(row.get("receipt_total")):
                    problems.append("%s receipt_total %r is not a number" % (tag, row.get("receipt_total")))
            else:
                bucket = totals.setdefault(receipt, {"total": total, "sum": 0.0, "lines": []})
                if abs(bucket["total"] - total) > 0.01:
                    problems.append("%s receipt_total %.2f disagrees with %.2f on an earlier line of the same receipt"
                                    % (tag, total, bucket["total"]))
                bucket["sum"] += price or 0.0
                bucket["lines"].append(line)

        key = (
            (row.get("vendor") or "").strip().lower(),
            (row.get("date") or "").strip(),
            "" if price is None else "%.2f" % price,
            receipt,
        )
        if key in seen_keys:
            problems.append("%s duplicates line %s (same vendor, date, price and receipt)"
                            % (tag, seen_keys[key]))
        else:
            seen_keys[key] = line

    for receipt, bucket in totals.items():
        gap = bucket["total"] - bucket["sum"]
        if abs(gap) > 0.01:
            problems.append("line %s  %s: lines sum to %.2f, receipt_total is %.2f (%s %.2f)"
                            % (bucket["lines"][0], receipt, bucket["sum"], bucket["total"],
                               "missing" if gap > 0 else "over by", abs(gap)))

    numbers = sorted(int(n) for n in seen_lines if n.isdigit())
    if numbers and numbers != list(range(1, len(numbers) + 1)):
        problems.append("header  line numbers must run 1..%d without gaps" % len(numbers))

    companion = spec.get("companion_file", {}).get("file")
    if companion and not os.path.exists(os.path.join(folder, companion)):
        problems.append("%s  not found; copy templates/%s and fill every field"
                        % (companion, spec["companion_file"].get("template", "trip-template.md")))

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
    name = schema["submission"]["file"]
    if problems:
        print("FAIL %s" % name)
        for p in problems:
            print("  %s" % p)
        return 1
    print("PASS %s" % name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
