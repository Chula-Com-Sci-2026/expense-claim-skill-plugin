## Required output format

Write all three files into the trip folder. These schemas are fixed — a grader reads
them, so column order and header spelling matter.

**1. `EXPENSE_CLAIM_REVIEW.md`** — the audit report. Include:

- a trip summary (traveller, destination, dates, filing date)
- one table row per submitted line with: date, vendor, category, submitted amount,
  claimable amount, decision, reason, and the policy clause the decision rests on
- the arithmetic for every reduced amount, shown (e.g. `1,020 − 800 = 220 excess`)
- the total claimable
- a list of exceptions with their reasons

**2. `claims.csv`** — approved lines only, appended to any existing rows:

```
date,vendor,category,claimable_amount,receipt_file,review_date
```

Never write an exception into this file.

**3. `exceptions-queue.csv`** — one row per line that needs a human decision:

```
date,vendor,amount,reason,receipt_file
```

### Decision vocabulary

Use exactly one of these per line, in the `decision` column and in the exception
`reason` column:

`WITHIN-POLICY`, `OVER-CAP`, `NON-REIMBURSABLE`, `NEEDS-APPROVAL`, `DUPLICATE`,
`OUT-OF-WINDOW`, `MISSING-DATA`, `MISSING-RECEIPT`, `MANIFEST-MISMATCH`,
`UNSPECIFIED`.

Use `UNSPECIFIED` when the policy does not address a line at all and you therefore
cannot decide it.
