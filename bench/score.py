"""Grade what each benchmark run decided, against the dataset's ground truth.

    python3 bench/score.py [results-dir]      # default: bench/results/latest

Verdicts are read from the STRUCTURED outputs, not from the prose report: a line in
claims.csv was approved, a line in exceptions-queue.csv carries its reason, and both
files name their receipt file. That works identically for an arm that has never
heard of the plugin's vocabulary, which the report table does not — baselines format
their tables however they like.

The report is scored separately, on the things it alone can show: the total, the
arithmetic, and whether each decision cites a clause.

Scoring follows tests/golden-path.sh's shape — a flat list of named checks, each
pass/fail with the evidence attached, so a failure names what it saw.
"""

import csv
import glob
import io
import json
import os
import re
import sys

BENCH = os.path.dirname(os.path.abspath(__file__))

# Baselines have not read skills/expense-review/SKILL.md, so they reach for ordinary
# English. Map what they actually write onto the verdict vocabulary before comparing.
SYNONYMS = {
    "WITHIN-POLICY": ["within-policy", "within policy", "approved", "compliant", "ok",
                      "reimbursable", "allowed"],
    "OVER-CAP": ["over-cap", "over cap", "exceeds cap", "capped", "reduced",
                 "partially approved", "partial"],
    "NON-REIMBURSABLE": ["non-reimbursable", "not reimbursable", "nonreimbursable",
                         "rejected", "denied", "excluded", "not claimable"],
    "NEEDS-APPROVAL": ["needs-approval", "needs approval", "requires approval",
                       "pending approval", "manager approval", "awaiting approval"],
    "DUPLICATE": ["duplicate", "already claimed", "already reimbursed", "double"],
    "OUT-OF-WINDOW": ["out-of-window", "out of window", "outside window", "late",
                      "past deadline", "expired", "too old", "stale"],
    "MISSING-DATA": ["missing-data", "missing data", "illegible", "unreadable",
                     "no total", "incomplete"],
    "MISSING-RECEIPT": ["missing-receipt", "missing receipt", "no receipt"],
    "MANIFEST-MISMATCH": ["manifest-mismatch", "manifest mismatch", "mismatch",
                          "discrepancy", "does not match", "differs"],
    "UNSPECIFIED": ["unspecified", "not specified", "policy silent", "silent",
                    "not addressed", "cannot determine", "undetermined", "unclear"],
}


def normalize_verdict(text):
    """Best-effort map of free text onto the verdict vocabulary. May return several."""
    t = (text or "").lower()
    return {code for code, words in SYNONYMS.items() if any(w in t for w in words)}


def rows(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        r = list(csv.DictReader(io.StringIO(f.read())))
    return [x for x in r if any((v or "").strip() for v in x.values())]


def num(v):
    try:
        return float(re.sub(r"[^\d.\-]", "", str(v or "")) or 0)
    except ValueError:
        return 0.0


def col(row, *names):
    """CSV headers drift in baseline output; accept any of several spellings."""
    for n in names:
        for k in row:
            if k and k.strip().lower() == n:
                return row[k]
    return ""


class Scorer:
    def __init__(self):
        self.checks = []

    def check(self, cid, ok, desc, evidence=""):
        self.checks.append({"id": cid, "ok": bool(ok), "desc": desc,
                            "evidence": str(evidence)[:300]})
        return ok

    def summary(self):
        p = sum(1 for c in self.checks if c["ok"])
        return {"passed": p, "failed": len(self.checks) - p, "total": len(self.checks),
                "checks": self.checks}


def report_row_verdict(report, vendor, submitted):
    """Read a line's verdict out of the prose report.

    A NON-REIMBURSABLE line is settled, not queued — it belongs in neither
    claims.csv nor exceptions-queue.csv — so without this the scorer would record
    "no decision" for a correctly rejected expense. Rows are matched on vendor plus
    the submitted amount, because a split receipt puts one vendor on two lines.

    Matching is per CELL, not per row. A row's `reason` prose is full of words that
    look like verdicts ("... this is reimbursable only if approved ... filed late"),
    and scanning the whole row returns half the vocabulary, which makes every line
    pass. A markdown row is split on `|` and the decision is taken from the cell
    that most looks like one: an exact verdict code first, then a short cell.
    """
    amt = int(num(submitted)) if submitted else None
    rows_seen = []
    for row in report.splitlines():
        if vendor.lower() not in row.lower():
            continue
        if amt:
            digits = {int(m.replace(",", "")) for m in re.findall(r"\d[\d,]*", row)}
            if amt not in digits:
                continue
        rows_seen.append(row)
    if not rows_seen:
        return set(), None

    row = rows_seen[0]
    if "|" in row:
        cells = [c.strip() for c in row.split("|") if c.strip()]
        # An exact code in its own cell is unambiguous — take it and stop.
        for c in cells:
            if c.upper().replace(" ", "-") in SYNONYMS:
                return {c.upper().replace(" ", "-")}, row[:120]
        # Otherwise the decision is a short cell, not the long reason or clause.
        short = [c for c in cells if len(c) <= 30]
        got = set()
        for c in short:
            got |= normalize_verdict(c)
        if got:
            return got, row[:120]
    return normalize_verdict(row), row[:120]


def rows_for_this_trip(claims, expected):
    """The rows this run actually added, identified by content rather than position.

    Position does not work. The skill arm inherits claims.csv on disk, so its file
    holds every earlier run's rows; base-fair is handed the prior ledger as text and
    re-emits those historical rows into its own claims.csv; base-strict starts empty.
    Counting "everything after the first N rows" therefore over-counts one arm and
    under-counts another. A row belongs to this run if and only if its receipt file
    is one of this trip's receipts.
    """
    mine = {l["receipt_file"] for l in expected["lines"]}
    return [r for r in claims if (col(r, "receipt_file") or "").strip() in mine]


def score_run(root, rec, expected):
    wd = os.path.join(root, rec["run_dir"], "workdir")
    s = Scorer()

    claims = rows(os.path.join(wd, "claims.csv"))
    exceptions = rows(os.path.join(wd, "exceptions-queue.csv"))
    report = ""
    rp = os.path.join(wd, "EXPENSE_CLAIM_REVIEW.md")
    if os.path.exists(rp):
        report = open(rp).read()
    flat = report.replace(",", "")

    new_claims = rows_for_this_trip(claims, expected)

    # ---- format conformance -------------------------------------------------
    s.check("FMT-01", os.path.exists(rp), "EXPENSE_CLAIM_REVIEW.md written")
    s.check("FMT-02", os.path.exists(os.path.join(wd, "claims.csv")), "claims.csv written")
    s.check("FMT-03", os.path.exists(os.path.join(wd, "exceptions-queue.csv")),
            "exceptions-queue.csv written")
    want_claims = ["date", "vendor", "category", "claimable_amount", "receipt_file",
                   "review_date"]
    got_claims = [h.strip().lower() for h in (claims[0].keys() if claims else [])]
    s.check("FMT-04", got_claims == want_claims, "claims.csv header matches the schema",
            ",".join(got_claims))
    want_exc = ["date", "vendor", "amount", "reason", "receipt_file"]
    got_exc = [h.strip().lower() for h in (exceptions[0].keys() if exceptions else [])]
    s.check("FMT-05", got_exc == want_exc, "exceptions-queue.csv header matches the schema",
            ",".join(got_exc))

    # ---- ledger hygiene -----------------------------------------------------
    blob = " ".join(" ".join(str(v) for v in r.values()) for r in new_claims).upper()
    leaked = [w for w in ("VIOLATION", "NEEDS-APPROVAL", "DUPLICATE", "OUT-OF-WINDOW",
                          "NON-REIMBURSABLE", "MISSING-DATA", "UNSPECIFIED")
              if w in blob]
    s.check("LED-01", not leaked, "no exception leaked into claims.csv", ", ".join(leaked))
    s.check("LED-02", all((col(r, "receipt_file") or "").strip() for r in new_claims),
            "every approved row names its receipt file")

    approved_files = {(col(r, "receipt_file") or "").strip() for r in new_claims}
    for f in expected["must_appear_in_claims"]:
        s.check(f"APP-{f[:14]}", f in approved_files, f"{f} approved", sorted(approved_files))
    for f in expected["must_not_appear_in_claims"]:
        s.check(f"REJ-{f[:14]}", f not in approved_files, f"{f} NOT in the ledger")

    # ---- per-line verdicts --------------------------------------------------
    line_results = []
    for ln in expected["lines"]:
        rf, sub = ln["receipt_file"], num(ln["submitted"])
        got, where = set(), None

        for r in new_claims:
            if (col(r, "receipt_file") or "").strip() == rf:
                amt = num(col(r, "claimable_amount", "claimable", "amount"))
                if not sub or abs(amt - sub) < 0.01:
                    got.add("WITHIN-POLICY")
                else:
                    # Paid something other than what was claimed. That is a cap being
                    # applied, or the receipt overruling the submission — the CSV
                    # cannot tell them apart, so allow both and let the report decide.
                    got.add("OVER-CAP")
                    got.add("MANIFEST-MISMATCH")
                where = f"claims.csv @ {amt:g}"
        for r in exceptions:
            if (col(r, "receipt_file") or "").strip() != rf:
                continue
            ramt = num(col(r, "amount"))
            if sub and ramt and abs(ramt - sub) > 0.01:
                continue                       # a different line off the same receipt
            reason = col(r, "reason")
            got |= normalize_verdict(reason)
            where = f"exceptions-queue.csv: {reason}"

        # The CSVs are the primary evidence. An explicit exception reason is taken
        # as final; an approved row only tells us the amount, which cannot separate
        # "a cap was applied" from "the receipt overruled the manifest", so there the
        # report breaks the tie. A line in neither file falls back to the report.
        if not got or got == {"OVER-CAP", "MANIFEST-MISMATCH"}:
            rep_got, row = report_row_verdict(report, ln["vendor"], ln["submitted"])
            got |= rep_got
            if row and not where:
                where = f"report: {row}"

        ok = bool(got & set(ln["accept_verdicts"]))
        s.check(f"LINE-{ln['id']}", ok,
                f"{ln['id']} {ln['vendor'][:22]} -> {'/'.join(ln['accept_verdicts'])}",
                where or "no decision found")

        amt_ok = None
        if ln["claimable"] is not None:
            paid = 0.0
            for r in new_claims:
                if (col(r, "receipt_file") or "").strip() == rf:
                    paid = num(col(r, "claimable_amount", "claimable", "amount"))
            amt_ok = abs(paid - ln["claimable"]) < 0.01
            s.check(f"AMT-{ln['id']}", amt_ok,
                    f"{ln['id']} claimable = {ln['claimable']:g}", f"got {paid:g}")

        line_results.append({"id": ln["id"], "verdict_ok": ok, "amount_ok": amt_ok,
                             "expected": ln["accept_verdicts"], "found": sorted(got),
                             "where": where, "why": ln["why"]})

    # ---- totals -------------------------------------------------------------
    total = sum(num(col(r, "claimable_amount", "claimable", "amount")) for r in new_claims)
    if expected["total_is_exact"]:
        s.check("TOT-01", abs(total - expected["expected_total_claimable"]) < 0.01,
                f"total claimable = {expected['expected_total_claimable']:,}",
                f"got {total:,.0f}")
    else:
        s.check("TOT-01", total >= expected["expected_total_claimable"] - 0.01,
                f"total claimable >= the deterministic floor "
                f"{expected['expected_total_claimable']:,}", f"got {total:,.0f}")
    s.check("TOT-02", f"{total:,.0f}".replace(",", "") in flat or f"{total:.0f}" in flat,
            "the report states its own total", f"{total:,.0f}")

    # ---- the report ---------------------------------------------------------
    named = [ln["receipt_file"] for ln in expected["lines"]]
    vendors = {ln["vendor"] for ln in expected["lines"]}
    covered = sum(1 for v in vendors if v.lower() in report.lower())
    s.check("REP-01", covered == len(vendors), "every vendor appears in the report",
            f"{covered}/{len(vendors)}")
    cited = sum(1 for kw in ("clause", "policy", "reimbursable", "approval", '"')
                if kw in report.lower())
    s.check("REP-02", cited >= 3, "decisions reference the policy text", cited)

    arith = [a for ln in expected["lines"] for a in ln["must_show_arithmetic"]]
    for a in arith:
        s.check(f"ARI-{a}", a in flat or f"{int(a):,}".replace(",", "") in flat,
                f"report shows the figure {a}")

    # ---- invariants ---------------------------------------------------------
    inv = check_invariants(expected, report, claims, exceptions, new_claims, s)

    return {"summary": s.summary(), "lines": line_results, "invariants": inv,
            "total_claimable": total,
            "expected_total": expected["expected_total_claimable"],
            "total_is_exact": expected["total_is_exact"],
            "new_claim_rows": len(new_claims), "exception_rows": len(exceptions)}


def check_invariants(expected, report, claims, exceptions, new_claims, s):
    """The 'must never' assertions — the ones a wrong answer is worse than no answer."""
    found = {}
    policy_a = expected["policy"] == "A"
    submitted = {int(num(l["submitted"])) for l in expected["lines"] if l["submitted"]}

    # A fabricated numeric cap: a sentence that asserts a cap/limit with a number
    # that is not one of the amounts on the receipts. Policy A contains no digits at
    # all, so ANY such number is invented. Heuristic — evidence is kept for review.
    hits = []
    if policy_a:
        for sent in re.split(r"[\n.;]", report):
            if not re.search(r"\b(cap|limit|maximum|allowance|threshold|per diem)\b",
                             sent, re.I):
                continue
            # Strip dates before scanning: a report row reads
            # "| 2026-09-15 | Ichiran Ramen | meal | 520 | ... per diem ...", and a
            # naive scan reports the YEAR as an invented cap. Also skip bare years
            # and the receipt's own amounts.
            scan = re.sub(r"\d{4}-\d{2}-\d{2}", " ", sent)
            for m in re.finditer(r"\b([\d][\d,]{1,})\b", scan):
                v = int(m.group(1).replace(",", ""))
                if v in submitted or v <= 50 or 1900 <= v <= 2100:
                    continue
                hits.append(sent.strip()[:160])
                break
    found["no_invented_cap"] = {"ok": not hits, "evidence": hits[:5]}
    s.check("INV-CAP", not hits, "no numeric cap invented for a policy that has none",
            hits[0] if hits else "")

    # The torn receipt must not acquire an amount anywhere.
    torn = [l for l in expected["lines"] if "invented_amount" in l["must_not"]]
    torn_hits = []
    for l in torn:
        for r in list(claims) + list(exceptions):
            if (col(r, "receipt_file") or "").strip() != l["receipt_file"]:
                continue
            a = num(col(r, "claimable_amount", "claimable", "amount"))
            if a > 0:
                torn_hits.append(f"{l['receipt_file']} -> {a:g}")
    found["no_invented_amount"] = {"ok": not torn_hits, "evidence": torn_hits}
    if torn:
        s.check("INV-AMT", not torn_hits, "no amount invented for the illegible receipt",
                "; ".join(torn_hits))

    # FX: under a policy silent on currency, an SGD line must not become a THB number.
    fx = [l for l in expected["lines"] if "invented_fx" in l["must_not"]]
    fx_hits = []
    if policy_a:
        for l in fx:
            for r in list(claims) + list(exceptions):
                if (col(r, "receipt_file") or "").strip() != l["receipt_file"]:
                    continue
                a = num(col(r, "claimable_amount", "claimable", "amount"))
                if a > num(l["submitted"]) * 2:   # 45 SGD -> ~1,100 THB
                    fx_hits.append(f"{l['receipt_file']} -> {a:g}")
    found["no_invented_fx"] = {"ok": not fx_hits, "evidence": fx_hits}
    if fx and policy_a:
        s.check("INV-FX", not fx_hits, "no self-chosen exchange rate applied",
                "; ".join(fx_hits))

    # Alcohol: policy A never mentions it, so banning it cites a clause that is not there.
    alc = [l for l in expected["lines"] if "alcohol_banned" in l["must_not"]]
    alc_hits = []
    if policy_a and alc:
        # Negation guard. The correct answer here SAYS the word "alcohol" next to the
        # word "excluded" — "policy does not name alcohol as excluded" — so a bare
        # keyword match accuses the reviewer of exactly the thing it got right.
        # Only count a sentence that asserts the exclusion without negating it.
        NEGATORS = (r"\bnot\b", r"n't\b", r"\bnever\b", r"\bsilent\b",
                    r"\bno\b", r"\bnowhere\b", r"\bcannot\b", r"\babsent\b",
                    r"\bUNSPECIFIED\b")
        for sent in re.split(r"(?<=[.;])\s+|\n", report):
            # Markdown emphasis hides the negation: "does **not** name alcohol as
            # excluded" reads as "not**" unless the asterisks come off first.
            plain = re.sub(r"[*`_~]+", "", sent)
            if "alcohol" not in plain.lower():
                continue
            if not re.search(r"(not reimbursable|non-?reimbursable|excluded|"
                             r"prohibited|disallowed)", plain, re.I):
                continue
            low = plain.lower()
            i = low.index("alcohol")
            window = low[:i] + low[i:i + 80]
            if any(re.search(n, window, re.I) for n in NEGATORS):
                continue                      # the sentence denies the rule exists
            alc_hits.append(plain.strip()[:160])
        for l in alc:
            for r in exceptions:
                if (col(r, "receipt_file") or "").strip() == l["receipt_file"] and \
                   abs(num(col(r, "amount")) - num(l["submitted"])) < 0.01 and \
                   "NON-REIMBURSABLE" in (col(r, "reason") or "").upper():
                    alc_hits.append("wine routed NON-REIMBURSABLE")
    found["no_fabricated_alcohol_rule"] = {"ok": not alc_hits, "evidence": alc_hits}
    if alc and policy_a:
        s.check("INV-ALC", not alc_hits,
                "no alcohol rule invented for a policy that never mentions alcohol",
                "; ".join(alc_hits))

    return found


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BENCH, "results", "latest")
    root = os.path.abspath(root)
    mp = os.path.join(root, "metrics.json")
    if not os.path.exists(mp):
        sys.exit("run bench/measure.py first")
    records = json.load(open(mp))

    out = []
    for rec in records:
        if "trip" not in rec:
            continue                      # the setup run has nothing to grade
        if not rec.get("usable", True):
            continue                      # limit-killed run: absence of data, not a score
        exp_path = os.path.join(BENCH, "datasets", rec["trip"],
                                f"expected-{rec.get('policy', 'a')}.json")
        expected = json.load(open(exp_path))
        sc = score_run(root, rec, expected)
        sc.update({"arm": rec["arm"], "run": rec["run"], "trip": rec["trip"],
                   "run_dir": rec["run_dir"], "policy": rec.get("policy", "a")})
        with open(os.path.join(root, rec["run_dir"], "score.json"), "w") as f:
            json.dump(sc, f, indent=2)
        out.append(sc)

    with open(os.path.join(root, "scores.json"), "w") as f:
        json.dump(out, f, indent=2)

    print(f"{'run':<22} {'checks':>10} {'verdicts':>10} {'total':>10} {'invariants':>12}")
    for sc in out:
        su = sc["summary"]
        v = sum(1 for l in sc["lines"] if l["verdict_ok"])
        inv_ok = sum(1 for i in sc["invariants"].values() if i["ok"])
        print(f"{sc['run_dir']:<22} {su['passed']:>4}/{su['total']:<5} "
              f"{v:>4}/{len(sc['lines']):<5} {sc['total_claimable']:>10,.0f} "
              f"{inv_ok:>5}/{len(sc['invariants']):<6}")
    print(f"\nwrote {len(out)} scores -> {os.path.join(root, 'scores.json')}")


if __name__ == "__main__":
    main()
