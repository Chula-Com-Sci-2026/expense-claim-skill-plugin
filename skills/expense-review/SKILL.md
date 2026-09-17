---
name: expense-review
description: >-
  Review an employee's expense submission against the expense policy and produce an
  auditable reimbursement decision. Use when finance, accounting, or an approver is
  checking a submitted claim — a submission Google Sheet, a CSV, or a trip folder of
  receipts — for policy compliance. Handles per-meal caps, non-reimbursable items,
  approval thresholds, missing receipts, out-of-window dates, and duplicate claims.
---

# Review an expense submission

You are on the **finance side**. You decide what gets reimbursed. Follow every
step; never skip a policy check to make a claim go through.

## Step 0 — the policy must exist

Read `~/.expense-claim-review/policy.md` and `meta.json` before anything else.

**If no policy is configured, stop.** Tell the user:

> No expense policy is set up yet. Run `/setup-expense-policy` and either attach
> your policy PDF or write the rules out, and I'll save it once for every future
> review.

Do not review against remembered, assumed, or invented rules — a decision that
cannot cite a stored clause is not auditable. If `meta.json` shows the policy has
expired (`effective_until` in the past), warn the user and ask whether to proceed
or renew first. If sections are marked `UNSPECIFIED`, say which checks you cannot
perform before you start.

## Inputs

Accept any of:

- **a submission Google Sheet URL** — read it via the Drive integration
- **a `submission.csv`** or a folder containing one
- **a bare trip folder** of receipts with no submission (itemize it yourself)

You also need `claims.csv` — the prior-claims ledger — for duplicate detection. If
it does not exist, create it with the header row and note that this is the first
review, so duplicates cannot be detected yet.

## Procedure

1. **Re-read the original receipts.** Do not trust the submission. It is a *claim
   about* the receipts, written by the person being reimbursed, and it may have been
   edited after extraction. Independently extract date, vendor, amount, and currency
   from each file in `receipts/`.

2. **Reconcile.** Compare your extraction against the submission line by line:

   - amount, date, vendor, or currency differs → `MANIFEST-MISMATCH`; use the
     **receipt's** value and record both numbers in the report
   - a submission line has no matching receipt → `MISSING-RECEIPT`, exception
   - a receipt exists with no submission line → note it as unclaimed; do not
     silently add it to the claim on the employee's behalf

3. **Check the trip window.** Every expense date must fall inside the trip dates and
   the location must match. Outside → `OUT-OF-WINDOW`.

4. **Apply the policy**, one verdict per line:

   | Verdict | When | Result |
   | --- | --- | --- |
   | `WITHIN-POLICY` | Complies fully | Approved at full amount |
   | `OVER-CAP` | Exceeds a per-category cap | Approve **up to the cap**; record the excess as non-claimable, showing the arithmetic |
   | `NON-REIMBURSABLE` | Excluded item (alcohol, minibar, entertainment) | Not claimable. On a shared receipt, claim only the eligible portion |
   | `NEEDS-APPROVAL` | Over an approval threshold, or otherwise requires a manager | **Do not approve it yourself** — exception |
   | `DUPLICATE` | Matches a `claims.csv` row on vendor, date, and amount | Exception |
   | `OUT-OF-WINDOW` | Outside trip dates or destination | Exception |
   | `MISSING-DATA` | No legible total or date | Exception. Never guess an amount |

   Cite the policy clause behind every verdict. Show the arithmetic for every
   capped or reduced amount.

5. **Handle currency.** If a receipt currency differs from the reporting currency in
   `meta.json`, apply only the FX handling the policy specifies. If the policy is
   `UNSPECIFIED` on FX, keep the original currency, flag the line, and ask the user
   for a rate rather than choosing one.

6. **Decide each line** — approved in full, approved at a reduced amount, or
   exception — then write the outputs.

## No-workaround rule

Never rewrite, relabel, or split an expense to get a non-compliant amount approved.
If an amount cannot be approved under the policy as written, it is an exception.
Report the violation plainly; do not soften or hide it.

A `PreToolUse` hook also blocks writing a line flagged `VIOLATION` into
`claims.csv`. Treat that as a backstop, not a substitute for this rule.

## Outputs

Write all three into the submission folder:

1. **`EXPENSE_CLAIM_REVIEW.md`** — the audit-ready report: trip summary; a table of
   every line with date, vendor, category, submitted amount, claimable amount,
   decision, reason, and the policy clause it rests on; total claimable; and a list
   of exceptions with reasons.

2. **`claims.csv`** — append one row per **approved** line:
   `date,vendor,category,claimable_amount,receipt_file,review_date`.
   Never append an exception here.

3. **`exceptions-queue.csv`** — append one row per exception:
   `date,vendor,amount,reason,receipt_file`. These await a human decision.

Then **create a review Google Sheet** from the decision table (upload as
`text/csv`; Drive converts it), titled
`Expense Review — <traveller> — <trip> — <dates>`, and give the user the link to
share back with the employee. The integration cannot write into the employee's
original submission Sheet — only create a new file — so this review Sheet is the
reply, not an edit of theirs. If Drive is unavailable, the three local files stand
on their own; say so and continue.

## Audit-ready format

Write so an auditor who was not present can follow every decision: cite the clause,
show the arithmetic, and name the receipt file behind each line. Prefer plain
numbers and clear reasons over prose.
