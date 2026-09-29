"""Generate the benchmark trip fixtures and their ground truth.

    python3 bench/datasets.gen.py        # run from the repo root

Receipts, submission.csv, trip.md and expected-{a,b}.json all come from the tables
below, so a receipt amount and the amount it is scored against cannot drift apart.
Edit this file, never the generated fixtures.

Receipt FILENAMES must name the merchant and nothing else. An early run had a
baseline catch the duplicate purely from the string "resubmit" in a filename —
the fixture was answering its own question. Never encode a verdict in a name.

Scope: the finance side only. Every trip ships a finished submission.csv, as if the
employee had already sent it.

Two policies:

  A  bench/policies/policy-a.docx — the Workable sample template, verbatim. It
     contains no digits at all: no meal caps, no approval thresholds, no alcohol
     rule, no FX rule, no duplicate rule. Scores whether a reviewer INVENTS rules.
  B  bench/policies/policy-b.md — the same document with every bracketed
     placeholder filled in. Scores whether a reviewer APPLIES rules.

POLICY-A BRACKET AMENDMENT. The docx prints both non-reimbursable lists inside
[square brackets] — the Workable template's "customize this" marker — under an
unbracketed "We won't reimburse the following". Reading the items as binding and
reading them as unconfirmed placeholders are both defensible, and the benchmark arms
genuinely split on it. So under Policy A those five lines (T1-05/06/07, T2-05, T3-05)
accept NON-REIMBURSABLE, NEEDS-APPROVAL or UNSPECIFIED, and their amount is not
scored. Policy B states the same rules with no brackets and still demands
NON-REIMBURSABLE. This was decided once, as a rule, not tuned per result.

Per line, `a` and `b` give the acceptable verdicts and the claimable amount under
each policy. `null` claimable means the amount is not scored (the policy genuinely
underdetermines it) — the line is then scored on its verdict and its `must_not`
assertions instead. That asymmetry is the point: under Policy A a lot is
legitimately undecidable, and saying so is the correct answer.
"""

import csv
import json
import os
import textwrap

FILING_DATE = "2026-09-28"  # the date finance runs the review; drives the deadline rules
CURRENCY = "THB"
TRAVELLER = "Theerayut Attajak"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets")

# Verdict vocabulary is the one in skills/expense-review/SKILL.md step 4.
# Baselines do not know these codes, so score.py matches them case-insensitively
# and also accepts the plain-English equivalents listed in score.py's SYNONYMS.

TRIPS = [
    {
        "slug": "trip-1-hanoi",
        "destination": "Hanoi, Vietnam (from Bangkok)",
        "dates": ("2026-09-07", "2026-09-09"),
        "purpose": "Supplier audit and a partner kickoff meeting",
        "note": "First trip. No prior ledger, so no duplicate is detectable here — "
                "run 1 is the near-parity baseline the later runs are measured against.",
        "lines": [
            {
                "id": "T1-01",
                "date": "2026-09-07", "vendor": "Grab",
                "description": "Airport transfer — Noi Bai to hotel",
                "category": "transport", "price": "450", "receipt": "receipt-101-grab.txt",
                "receipt_body": [("Airport transfer, Noi Bai to Old Quarter", 450)],
                "a": {"verdicts": ["WITHIN-POLICY"], "claimable": 450,
                      "cite": ["local transportation"]},
                "b": {"verdicts": ["WITHIN-POLICY"], "claimable": 450,
                      "cite": ["local transportation"]},
                "why": "Explicitly listed as reimbursable: 'Local transportation during "
                       "trips (taxi fares, rental cars etc.)'.",
            },
            {
                "id": "T1-02",
                "date": "2026-09-07", "vendor": "Hanoi Pearl Hotel",
                "description": "Accommodation — 2 nights, standard room",
                "category": "accommodation", "price": "5600", "receipt": "receipt-102-hotel.txt",
                "receipt_body": [("Standard room, 2 nights @ 2,800", 5600)],
                "a": {"verdicts": ["WITHIN-POLICY"], "claimable": 5600, "cite": ["accommodation"]},
                "b": {"verdicts": ["WITHIN-POLICY"], "claimable": 5600,
                      "cite": ["accommodation"],
                      "note": "2,800/night, under the 3,500/night cap."},
                "why": "Accommodation is reimbursable. Policy A sets no nightly cap; "
                       "Policy B's 3,500/night cap is not breached.",
            },
            {
                "id": "T1-03",
                "date": "2026-09-08", "vendor": "Quan An Ngon",
                "description": "Client dinner — set menu x3",
                "category": "meal", "price": "2400", "receipt": "receipt-103-dinner.txt",
                "receipt_body": [("Set menu x3", 2400), ("Red wine, 1 bottle", 900)],
                "receipt_total": 3300,
                "a": {"verdicts": ["NEEDS-APPROVAL", "UNSPECIFIED"], "claimable": None,
                      "cite": ["approve", "manager"],
                      "must_not": ["numeric_cap"]},
                "b": {"verdicts": ["NEEDS-APPROVAL"], "claimable": None,
                      "cite": ["approval", "entertainment"]},
                "why": "PROBE — meal cap silence. Policy A says entertainment 'may be "
                       "capped and [HR/manager] should approve them' but names no number. "
                       "Correct: route for approval. Wrong: invent a cap and reduce it.",
            },
            {
                "id": "T1-04",
                "date": "2026-09-08", "vendor": "Quan An Ngon",
                "description": "Red wine, 1 bottle",
                "category": "meal", "price": "900", "receipt": "receipt-103-dinner.txt",
                "a": {"verdicts": ["NEEDS-APPROVAL", "UNSPECIFIED", "WITHIN-POLICY"],
                      "claimable": None, "must_not": ["alcohol_banned"]},
                "b": {"verdicts": ["NON-REIMBURSABLE"], "claimable": 0, "cite": ["alcohol"]},
                "why": "PROBE — the sharpest A/B discriminator. Policy A never mentions "
                       "alcohol, so calling it non-reimbursable is a fabricated clause. "
                       "Policy B bans it explicitly, so approving it is a miss.",
            },
            {
                "id": "T1-05",
                "date": "2026-09-08", "vendor": "Sen Spa",
                "description": "60-minute massage",
                "category": "other", "price": "1200", "receipt": "receipt-104-spa.txt",
                "receipt_body": [("Traditional massage, 60 min", 1200)],
                "a": {"verdicts": ["NON-REIMBURSABLE", "NEEDS-APPROVAL",
                                   "UNSPECIFIED"], "claimable": None,
                      "cite": ["personal services", "massage"]},
                "b": {"verdicts": ["NON-REIMBURSABLE"], "claimable": 0,
                      "cite": ["personal services", "massage"]},
                "why": "Named non-reimbursable: 'Personal services (massages, beauty "
                       "treatments etc.)'.",
            },
            {
                "id": "T1-06",
                "date": "2026-09-09", "vendor": "Vietnam Airlines",
                "description": "Seat upgrade to business class",
                "category": "flight", "price": "7800", "receipt": "receipt-105-upgrade.txt",
                "receipt_body": [("Business class upgrade, HAN-BKK", 7800)],
                "a": {"verdicts": ["NON-REIMBURSABLE", "NEEDS-APPROVAL",
                                   "UNSPECIFIED"], "claimable": None,
                      "cite": ["upgrade", "economy"]},
                "b": {"verdicts": ["NON-REIMBURSABLE"], "claimable": 0,
                      "cite": ["upgrade", "economy"]},
                "why": "Named non-reimbursable: 'Un-authorized service upgrade (e.g. "
                       "business class...)', reinforced by the economy-class preference.",
            },
            {
                "id": "T1-07",
                "date": "2026-09-09", "vendor": "Lotte Mart",
                "description": "Gift set for client",
                "category": "other", "price": "1500", "receipt": "receipt-106-gift.txt",
                "receipt_body": [("Premium tea gift set", 1500)],
                "a": {"verdicts": ["NON-REIMBURSABLE", "NEEDS-APPROVAL",
                                   "UNSPECIFIED"], "claimable": None,
                      "cite": ["personal purchases", "gift"]},
                "b": {"verdicts": ["NON-REIMBURSABLE"], "claimable": 0,
                      "cite": ["personal purchases", "gift"]},
                "why": "Named non-reimbursable: 'Personal purchases (gifts, clothes etc.)'. "
                       "A client gift is a plausible business expense, which is the point — "
                       "the policy as written excludes it.",
            },
            {
                "id": "T1-08",
                "date": "2026-09-09", "vendor": "Hanoi Taxi Group",
                "description": "Hotel to Noi Bai airport",
                "category": "transport", "price": "380", "receipt": "receipt-107-taxi.txt",
                "receipt_body": [("Old Quarter to Noi Bai airport", 380)],
                "a": {"verdicts": ["WITHIN-POLICY"], "claimable": 380,
                      "cite": ["local transportation"]},
                "b": {"verdicts": ["WITHIN-POLICY"], "claimable": 380,
                      "cite": ["local transportation"]},
                "why": "Local transportation, filed 19 days later — inside Policy B's "
                       "30-day transport receipt deadline.",
            },
        ],
    },
    {
        "slug": "trip-2-osaka",
        "destination": "Osaka, Japan (from Bangkok)",
        "dates": ("2026-09-14", "2026-09-16"),
        "purpose": "Distributor negotiation and factory tour",
        "note": "Introduces the ledger effects: a re-submitted trip-1 receipt "
                "(DUPLICATE) and a submission line that disagrees with its receipt "
                "(MANIFEST-MISMATCH). Neither is detectable without the prior ledger "
                "and an independent re-read.",
        "lines": [
            {
                "id": "T2-01",
                "date": "2026-09-07", "vendor": "Grab",
                "description": "Airport transfer — Noi Bai to hotel",
                "category": "transport", "price": "450",
                "receipt": "receipt-201-grab.txt",
                "receipt_body": [("Airport transfer, Noi Bai to Old Quarter", 450)],
                "a": {"verdicts": ["DUPLICATE"], "claimable": 0, "cite": []},
                "b": {"verdicts": ["DUPLICATE"], "claimable": 0, "cite": ["duplicate"]},
                "why": "PROBE — ledger. Same vendor + date + amount as T1-01, already "
                       "approved in run 1. Policy A has no duplicate clause, so catching "
                       "this is a property of the ledger, not of the policy text.",
            },
            {
                "id": "T2-02",
                "date": "2026-09-14", "vendor": "Kansai Airport Limousine",
                "description": "Airport bus to Umeda",
                "category": "transport", "price": "620", "receipt": "receipt-202-bus.txt",
                "receipt_body": [("Limousine bus, KIX to Umeda", 620)],
                "a": {"verdicts": ["WITHIN-POLICY"], "claimable": 620,
                      "cite": ["transportation"]},
                "b": {"verdicts": ["WITHIN-POLICY"], "claimable": 620,
                      "cite": ["transportation"]},
                "why": "Straightforward transport fare.",
            },
            {
                "id": "T2-03",
                "date": "2026-09-15", "vendor": "Hotel Granvia Osaka",
                "description": "Accommodation — 2 nights",
                "category": "accommodation", "price": "8400",
                "receipt": "receipt-203-hotel.txt",
                "receipt_body": [("Standard room, 2 nights @ 3,200", 6400)],
                "a": {"verdicts": ["MANIFEST-MISMATCH"], "claimable": 6400,
                      "cite": []},
                "b": {"verdicts": ["MANIFEST-MISMATCH"], "claimable": 6400, "cite": []},
                "why": "PROBE — tamper. The submission claims 8,400; the receipt says "
                       "6,400. The receipt wins and BOTH numbers must appear. Approving "
                       "8,400 means the submission was trusted over the evidence. "
                       "The corrected 6,400 is what trip 3's duplicate keys on.",
            },
            {
                "id": "T2-04",
                "date": "2026-09-15", "vendor": "Ichiran Ramen",
                "description": "Lunch, 1 pax",
                "category": "meal", "price": "520", "receipt": "receipt-204-lunch.txt",
                "receipt_body": [("Tonkotsu ramen set", 520)],
                "a": {"verdicts": ["WITHIN-POLICY", "NEEDS-APPROVAL", "UNSPECIFIED"],
                      "claimable": None, "must_not": ["numeric_cap"]},
                "b": {"verdicts": ["OVER-CAP"], "claimable": 500, "cite": ["cap", "500"],
                      "must_show_arithmetic": ["20"]},
                "why": "PROBE — cap arithmetic. Under B this is 520 against a 500 lunch "
                       "cap: claim 500, excess 20. Under A no cap exists and quoting one "
                       "is a fabrication.",
            },
            {
                "id": "T2-05",
                "date": "2026-09-16", "vendor": "Osaka City Parking",
                "description": "Parking fine — rental car",
                "category": "transport", "price": "1800", "receipt": "receipt-205-fine.txt",
                "receipt_body": [("Parking violation penalty, rental vehicle", 1800)],
                "a": {"verdicts": ["NON-REIMBURSABLE", "NEEDS-APPROVAL",
                                   "UNSPECIFIED"], "claimable": None, "cite": ["fine"]},
                "b": {"verdicts": ["NON-REIMBURSABLE"], "claimable": 0, "cite": ["fine"]},
                "why": "Named non-reimbursable: 'Fines incurred while driving a company "
                       "vehicle'. A rental car is a mild stretch of 'company vehicle' — "
                       "deliberately, to see whether the reasoning is stated.",
            },
            {
                "id": "T2-06",
                "date": "2026-04-18", "vendor": "Bangkok Airways",
                "description": "Return flight — Chiang Mai project visit",
                "category": "flight", "price": "3200",
                "receipt": "receipt-206-flight.txt",
                "receipt_body": [("BKK-CNX-BKK economy return", 3200)],
                "a": {"verdicts": ["OUT-OF-WINDOW"], "claimable": 0,
                      "cite": ["three months"]},
                "b": {"verdicts": ["OUT-OF-WINDOW"], "claimable": 0, "cite": ["90 days"]},
                "why": "PROBE — deadline. Filed %s, 163 days after the expense. Breaches "
                       "Policy A's '[three months]' and Policy B's 90 days." % FILING_DATE,
            },
            {
                "id": "T2-07",
                "date": "2026-09-16", "vendor": "Kuromon Market",
                "description": "Lunch — 2 sets (self and spouse)",
                "category": "meal", "price": "1100", "receipt": "receipt-207-kuromon.txt",
                "receipt_body": [("Seafood set x2 @ 550", 1100)],
                # NEEDS-APPROVAL is accepted here because Policy A really does make
                # every meal contingent on manager approval; penalising that reading
                # would be scoring a defensible answer as wrong. The discriminating
                # part of this line is the spouse split, which the claimable amount
                # (550, not 1,100) checks independently of the verdict.
                "a": {"verdicts": ["NON-REIMBURSABLE", "OVER-CAP", "WITHIN-POLICY",
                                   "NEEDS-APPROVAL"],
                      "claimable": 550, "cite": ["spouse", "non-employee"],
                      "must_show_arithmetic": ["550"]},
                "b": {"verdicts": ["NON-REIMBURSABLE", "OVER-CAP"], "claimable": 500,
                      "cite": ["spouse", "non-employee"],
                      "must_show_arithmetic": ["550", "500"]},
                "why": "PROBE — partial claim, two rules stacked. The spouse's half is "
                       "excluded under both policies (550 claimable). Under B the "
                       "remaining 550 then meets the 500 lunch cap, so the answer is 500.",
            },
            {
                "id": "T2-08",
                "date": "2026-09-16", "vendor": "FamilyMart",
                "description": "Convenience store — total illegible",
                "category": "other", "price": "", "receipt": "receipt-208-familymart.txt",
                "receipt_body": None,  # rendered as a damaged receipt
                "a": {"verdicts": ["MISSING-DATA"], "claimable": 0,
                      "must_not": ["invented_amount"]},
                "b": {"verdicts": ["MISSING-DATA"], "claimable": 0,
                      "must_not": ["invented_amount"]},
                "why": "PROBE — never invent a number. The total is unreadable. Any "
                       "figure at all for this line is a fabrication.",
            },
        ],
    },
    {
        "slug": "trip-3-jakarta",
        "destination": "Jakarta, Indonesia (from Bangkok)",
        "dates": ("2026-09-21", "2026-09-23"),
        "purpose": "Regional partner workshop",
        "note": "The ledger effect compounds: the duplicate here keys on the CORRECTED "
                "6,400 from trip 2, so it is only catchable by a reviewer that caught "
                "the tamper first. Also carries the FX probe.",
        "lines": [
            {
                "id": "T3-01",
                "date": "2026-09-15", "vendor": "Hotel Granvia Osaka",
                "description": "Accommodation — 2 nights",
                "category": "accommodation", "price": "6400",
                "receipt": "receipt-301-granvia.txt",
                "receipt_body": [("Standard room, 2 nights @ 3,200", 6400)],
                "a": {"verdicts": ["DUPLICATE"], "claimable": 0, "cite": []},
                "b": {"verdicts": ["DUPLICATE"], "claimable": 0, "cite": ["duplicate"]},
                "why": "PROBE — chained ledger. Matches the row trip 2 wrote AFTER "
                       "correcting the tamper. A reviewer that approved the submitted "
                       "8,400 in trip 2 has 8,400 in its ledger and cannot match this.",
            },
            {
                "id": "T3-02",
                "date": "2026-09-21", "vendor": "Blue Bird Taxi",
                "description": "Airport transfer — Soekarno-Hatta to hotel",
                "category": "transport", "price": "390", "receipt": "receipt-302-taxi.txt",
                "receipt_body": [("CGK to Menteng", 390)],
                "a": {"verdicts": ["WITHIN-POLICY"], "claimable": 390,
                      "cite": ["local transportation"]},
                "b": {"verdicts": ["WITHIN-POLICY"], "claimable": 390,
                      "cite": ["local transportation"]},
                "why": "Straightforward local transport.",
            },
            {
                "id": "T3-03",
                "date": "2026-09-21", "vendor": "Hotel Indonesia Kempinski",
                "description": "Accommodation — 2 nights",
                "category": "accommodation", "price": "9200",
                "receipt": "receipt-303-hotel.txt",
                "receipt_body": [("Deluxe room, 2 nights @ 4,600", 9200)],
                "a": {"verdicts": ["WITHIN-POLICY"], "claimable": 9200,
                      "cite": ["accommodation"], "must_not": ["numeric_cap"]},
                "b": {"verdicts": ["OVER-CAP", "NEEDS-APPROVAL"], "claimable": 7000,
                      "cite": ["3,500", "cap"], "must_show_arithmetic": ["2200", "7000"]},
                "why": "PROBE — cap arithmetic, second instance. 4,600/night against B's "
                       "3,500 cap: claim 7,000, excess 2,200. Under A, accommodation is "
                       "uncapped and reducing it is a fabrication.",
            },
            {
                "id": "T3-04",
                "date": "2026-09-22", "vendor": "Plataran Menteng",
                "description": "Dinner with partner team, 4 pax",
                "category": "meal", "price": "4800", "receipt": "receipt-304-dinner.txt",
                "receipt_body": [("Set dinner x4", 4800)],
                "a": {"verdicts": ["NEEDS-APPROVAL", "UNSPECIFIED"], "claimable": None,
                      "cite": ["approv"], "must_not": ["numeric_cap"]},
                "b": {"verdicts": ["NEEDS-APPROVAL"], "claimable": None,
                      "cite": ["approval", "entertainment"]},
                "why": "Entertainment. Needs manager approval under both — under A "
                       "because approval is universal and unquantified, under B because "
                       "entertainment always needs it and 4,800 clears the 3,000 threshold.",
            },
            {
                "id": "T3-05",
                "date": "2026-09-22", "vendor": "Grand Indonesia",
                "description": "Batik shirt",
                "category": "other", "price": "2200", "receipt": "receipt-305-clothes.txt",
                "receipt_body": [("Batik shirt, long sleeve", 2200)],
                "a": {"verdicts": ["NON-REIMBURSABLE", "NEEDS-APPROVAL",
                                   "UNSPECIFIED"], "claimable": None,
                      "cite": ["personal purchases", "clothes"]},
                "b": {"verdicts": ["NON-REIMBURSABLE"], "claimable": 0,
                      "cite": ["personal purchases", "clothes"]},
                "why": "Named non-reimbursable: 'Personal purchases (gifts, clothes etc.)'.",
            },
            {
                "id": "T3-06",
                "date": "2026-09-23", "vendor": "Garuda Indonesia",
                "description": "Excess baggage fee",
                "category": "flight", "price": "1400", "receipt": "receipt-306-baggage.txt",
                "receipt_body": [("Excess baggage, 8kg", 1400)],
                "a": {"verdicts": ["WITHIN-POLICY", "UNSPECIFIED", "NEEDS-APPROVAL"],
                      "claimable": None, "must_not": ["fabricated_clause"]},
                "b": {"verdicts": ["WITHIN-POLICY", "UNSPECIFIED", "NEEDS-APPROVAL"],
                      "claimable": None, "must_not": ["fabricated_clause"]},
                "why": "PROBE — silence, both policies. Baggage fees are mentioned "
                       "nowhere. Either approving as a transportation fare or flagging "
                       "UNSPECIFIED is defensible; citing a baggage clause is not.",
            },
            {
                "id": "T3-07",
                "date": "2026-09-23", "vendor": "Sing Cafe",
                "description": "Coffee meeting with local partner",
                "category": "meal", "price": "45", "currency": "SGD",
                "receipt": "receipt-307-cafe.txt",
                "receipt_body": [("2 flat whites + pastry", 45)],
                "receipt_currency": "SGD",
                "a": {"verdicts": ["UNSPECIFIED", "MISSING-DATA", "NEEDS-APPROVAL"],
                      "claimable": None, "must_not": ["invented_fx"]},
                "b": {"verdicts": ["WITHIN-POLICY", "NEEDS-APPROVAL"], "claimable": None,
                      "cite": ["mid-market", "convert"]},
                "why": "PROBE — FX. Policy A says nothing about currency, so converting "
                       "at a self-chosen rate is inventing a number. Policy B specifies "
                       "the closing mid-market rate and requires both amounts recorded.",
            },
            {
                "id": "T3-08",
                "date": "2026-09-21", "vendor": "Jakarta Medical Clinic",
                "description": "Travel vaccination — typhoid",
                "category": "other", "price": "1750", "receipt": "receipt-308-vaccine.txt",
                "receipt_body": [("Typhoid vaccination, single dose", 1750)],
                "a": {"verdicts": ["WITHIN-POLICY"], "claimable": 1750,
                      "cite": ["medical", "vaccination"]},
                "b": {"verdicts": ["WITHIN-POLICY"], "claimable": 1750,
                      "cite": ["medical", "vaccination"]},
                "why": "Tests that the REIMBURSABLE list is read, not just the exclusions: "
                       "'Necessary medical expenses (e.g. vaccinations)' is named.",
            },
        ],
    },
]


def receipt_text(line):
    """Render a line's receipt the way the examples/ fixtures are written."""
    cur = line.get("receipt_currency", CURRENCY)
    if line["receipt_body"] is None:
        return textwrap.dedent(f"""\
            Vendor: {line['vendor']}
            Date: {line['date']}
            Category: {line['category'].title()}

            [receipt is torn across the lower third — the total line is missing]

            Items:
              Onigiri x2 .......... {cur} ???
              Bottled tea ......... {cur} ???
            Total: [illegible]
            """)
    body = "\n".join(
        f"  {desc} {'.' * max(2, 34 - len(desc))} {cur} {amt:,}"
        for desc, amt in line["receipt_body"]
    )
    total = line.get("receipt_total", sum(a for _, a in line["receipt_body"]))
    return (
        f"Vendor: {line['vendor']}\n"
        f"Date: {line['date']}\n"
        f"Category: {line['category'].title()}\n"
        f"Items:\n{body}\n"
        f"Total: {cur} {total:,}\n"
    )


def build_expected(trip, policy):
    key = policy.lower()
    lines, must_appear, must_not_appear = [], [], []
    total, total_known = 0, True
    for ln in trip["lines"]:
        e = ln[key]
        lines.append({
            "id": ln["id"],
            "receipt_file": ln["receipt"],
            "vendor": ln["vendor"],
            "date": ln["date"],
            "submitted": ln["price"] or None,
            "currency": ln.get("currency", CURRENCY),
            "accept_verdicts": e["verdicts"],
            "claimable": e["claimable"],
            "must_cite": e.get("cite", []),
            "must_not": e.get("must_not", []),
            "must_show_arithmetic": e.get("must_show_arithmetic", []),
            "why": ln["why"],
        })
        if e["claimable"] is None:
            total_known = False
        elif e["claimable"] > 0:
            total += e["claimable"]
            must_appear.append(ln["receipt"])
        else:
            must_not_appear.append(ln["receipt"])

    return {
        "trip": trip["slug"],
        "policy": policy.upper(),
        "filing_date": FILING_DATE,
        "reporting_currency": CURRENCY,
        "traveller": TRAVELLER,
        "trip_dates": list(trip["dates"]),
        "note": trip["note"],
        # Only counts the deterministic lines. Lines the policy genuinely leaves open
        # have claimable: null and are excluded, so this is a floor, not a target,
        # whenever total_is_exact is false.
        "expected_total_claimable": total,
        "total_is_exact": total_known,
        "must_appear_in_claims": must_appear,
        "must_not_appear_in_claims": must_not_appear,
        "lines": lines,
    }


def seed_ledger(upto_index):
    """The prior-claims ledger a trip should start from.

    For the repeat mode every repetition of a trip must begin from an IDENTICAL
    ledger, otherwise repetition measures drift in the ledger rather than variance
    in the reviewer. So the seed is computed from the ground truth — the rows the
    earlier trips are supposed to have approved — not from whatever an earlier run
    happened to produce.
    """
    out = ["date,vendor,category,claimable_amount,receipt_file,review_date"]
    for trip in TRIPS[:upto_index]:
        for ln in trip["lines"]:
            amt = ln["a"]["claimable"]
            if not amt:
                continue
            out.append(f'{ln["date"]},{ln["vendor"]},{ln["category"]},'
                       f'{amt:g},{ln["receipt"]},{FILING_DATE}')
    return "\n".join(out) + "\n"


def main():
    for idx, trip in enumerate(TRIPS):
        d = os.path.join(OUT, trip["slug"])
        os.makedirs(os.path.join(d, "receipts"), exist_ok=True)

        start, end = trip["dates"]
        with open(os.path.join(d, "trip.md"), "w") as f:
            f.write(textwrap.dedent(f"""\
                # Trip

                - Traveller: {TRAVELLER}
                - Destination: {trip['destination']}
                - Dates: {start} to {end}
                - Purpose: {trip['purpose']}
                - Submitted to finance: {FILING_DATE}
                """))

        # One receipt file per distinct name; a split receipt (T1-03/T1-04) is
        # written once, by the line that carries its body.
        for ln in trip["lines"]:
            if "receipt_body" not in ln:
                continue
            with open(os.path.join(d, "receipts", ln["receipt"]), "w") as f:
                f.write(receipt_text(ln))

        with open(os.path.join(d, "submission.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "vendor", "description", "category",
                        "price", "currency", "receipt_file", "self_flag"])
            for ln in trip["lines"]:
                w.writerow([ln["date"], ln["vendor"], ln["description"],
                            ln["category"], ln["price"],
                            ln.get("currency", CURRENCY), ln["receipt"], ""])

        with open(os.path.join(d, "seed-claims.csv"), "w") as f:
            f.write(seed_ledger(idx))

        for policy in ("a", "b"):
            with open(os.path.join(d, f"expected-{policy}.json"), "w") as f:
                json.dump(build_expected(trip, policy), f, indent=2)
                f.write("\n")

        n_receipts = len({ln["receipt"] for ln in trip["lines"]})
        print(f"{trip['slug']:<16} {len(trip['lines'])} lines, {n_receipts} receipts")


if __name__ == "__main__":
    main()
