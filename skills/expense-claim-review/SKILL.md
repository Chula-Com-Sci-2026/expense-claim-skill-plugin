---
name: expense-claim-review
description: >-
  Review travel expense claims. Use when the user points at a trip folder that
  contains receipts, an expense policy, and prior claims, and wants each expense
  itemized, checked against policy, and turned into an auditable claim or
  exception record. Handles per-meal caps, non-reimbursable items such as
  alcohol, approval-required items, missing receipts, out-of-window dates, and
  duplicate claims.
---

# Expense claim review

You review a trip's expenses and produce an auditable reimbursement decision.
Follow every step. Never skip a policy check to make a claim "go through."

## Inputs

Read these from the target folder (the folder the user names, else the current
directory):

- `expense-policy.md` — the rules. Read this first and in full.
- `trip.md` — trip dates, destination, traveller, purpose.
- `receipts/` — one file per receipt.
- `claims.csv` — prior claims, used to catch duplicates.

If any required input is missing, stop and tell the user which file is missing.
Do not invent policy or amounts.

## Procedure

1. **Read receipt** — for each file in `receipts/`, extract vendor, date,
   category, currency, and total. If a receipt is unreadable or missing a total
   or date, mark it `MISSING-DATA` and route it to an exception. Never guess an
   amount.

2. **Itemize** — build one line per expense: date, vendor, category, amount, and
   the receipt filename it came from. Split a receipt into separate lines when it
   mixes claimable and non-claimable items (e.g. food + alcohol).

3. **Check trip** — confirm each expense date falls within the trip dates and the
   location matches `trip.md`. Anything outside the window is an exception
   (`OUT-OF-WINDOW`).

4. **Check policy** — apply `expense-policy.md` to every line:
   - **over a per-category cap** → claimable up to the cap; the excess is
     non-claimable. Record both numbers and show the arithmetic.
   - **a non-reimbursable item (e.g. alcohol)** → non-claimable. If it shares a
     receipt with claimable items, claim only the eligible portion.
   - **an item that needs approval (e.g. a high-value or late flight change)** →
     do not approve it yourself; route to an exception, reason `NEEDS-APPROVAL`.
   - **a duplicate** of a row already in `claims.csv` (same vendor, date, amount)
     → route to an exception, reason `DUPLICATE`.

5. **Approve / exception** — decide each line:
   - fully within policy → **approved**, with the claimable amount.
   - partially within policy → **approve the eligible amount**, note the reduction.
   - needs approval, duplicate, missing data, or out of window → **exception**.

6. **Log** — write the outputs below, then confirm what you wrote.

## No-workaround rule

Never rewrite, relabel, or split an expense to get a non-compliant amount
approved. If an amount cannot be approved under the policy as written, it is an
exception. Report the violation plainly; do not soften or hide it.

(A `PreToolUse` hook also blocks writing a line flagged `VIOLATION` into
`claims.csv`. Treat that as a backstop, not a substitute for this rule.)

## Outputs

Write all three to the target folder:

1. **`EXPENSE_CLAIM_REVIEW.md`** — the audit-ready report:
   - trip summary (traveller, dates, destination)
   - a table of every line: date, vendor, category, amount, claimable amount,
     decision, reason, and the policy clause the decision rests on
   - total claimable amount
   - a list of exceptions with reasons

2. **`claims.csv`** — append one row per **approved** line:
   `date,vendor,category,claimable_amount,receipt_file,review_date`.
   Never append an exception here.

3. **`exceptions-queue.csv`** — append one row per **exception**:
   `date,vendor,amount,reason,receipt_file`. These await a human decision.

## Audit-ready format

Write so an auditor who was not present can follow every decision: cite the
policy clause, show the arithmetic for any capped amount, and name the receipt
file behind each line. Prefer plain numbers and clear reasons over prose.
