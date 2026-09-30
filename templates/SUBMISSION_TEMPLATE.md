# Submission template

What an employee hands to finance. Two files, both checked by `validate_submission.py`
before the package leaves the employee side: **PASS** → send to finance · **FAIL** → fix the
listed rows and resubmit.

The submission describes; it never decides. It carries no decision, no claimable amount and
no "approved" — those belong to finance.

## File 1 — `trip.md`

Copy `trip-template.md` and fill every field. The policy uses these fields to pick its rules
(funding source decides alcohol and GPS; meal method decides whether meal receipts count;
personal days mark the non-business portion). A field that does not apply is written as `none`.

## File 2 — `submission.csv`

One row per line item. A receipt that mixes things finance treats differently (room + movie,
food + wine) is split into one row per item, and every split row repeats the receipt's printed total.

| Column | Format | Notes |
| --- | --- | --- |
| `line` | 1, 2, 3 … | unique, consecutive |
| `date` | YYYY-MM-DD | date on the receipt; hotel folio = check-out date |
| `vendor` | text | as printed on the receipt |
| `description` | text | what was bought, in plain words |
| `category` | meal · transport · accommodation · flight · supplies · other | |
| `price` | 123.45 | amount on the receipt for this item; blank only with `MISSING-DATA` |
| `currency` | ISO code (USD, CAD, THB …) | currency printed on the receipt; never converted |
| `receipt_file` | file name in `receipts/` | blank only for per-diem lines or receipt-exempt items |
| `receipt_total` | 123.45 | printed total of that receipt |
| `self_flag` | blank · LIKELY-OVER-CAP · LIKELY-NON-REIMBURSABLE · LIKELY-NEEDS-APPROVAL · MISSING-DATA | advisory only |
| `employee_note` | text | context finance cannot read off the receipt |

## What the gate checks

The rules live in `template-schema.json` → `submission`. In short:

1. All columns present, in order; no decision columns.
2. Dates, currency codes and amounts are well-formed.
3. Every `receipt_file` exists in `receipts/`.
4. Split rows add back to `receipt_total` for every receipt.
5. `trip.md` has every field filled.

Gate output — one line per problem, so the employee knows exactly what to fix:

```
FAIL submission.csv
  line 3  receipt-02-group-dinner.txt: lines sum to 184.00, receipt_total is 246.00 (missing 62.00)
  line 6  receipt_file receipt-09.pdf not found in receipts/
  trip.md  Funding source is empty
```
