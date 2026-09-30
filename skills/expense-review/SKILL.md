---
name: expense-review
description: >-
  Review an employee's expense submission against the expense policy and produce an
  auditable reimbursement decision. Use when finance, accounting, or an approver is
  checking a submission someone sent — a submission Google Sheet, a CSV, or a trip
  folder of receipts — for policy compliance. Handles per-meal caps, non-reimbursable
  items, approval thresholds, missing receipts, out-of-window dates, and duplicates.
---

# Review an expense submission

You are on the **finance side**. You decide what gets reimbursed. Follow every
step; never skip a policy check to make a claim go through.

## Step 0 — the policy must exist

Read `~/.expense-claim-review/policy.md` and `meta.json` before anything else.

**If no policy is configured, stop.** Tell the user:

> No expense policy is set up yet. Run
> `/expense-claim-review:setup-expense-policy` and either attach your policy PDF or
> write the rules out, and I'll save it once for every future review.

Do not review against remembered, assumed, or invented rules — a decision that
cannot cite a stored clause is not auditable. If `meta.json` shows the policy has
expired (`effective_until` in the past), warn the user and ask whether to proceed
or renew first. If sections are marked `UNSPECIFIED`, say which checks you cannot
perform before you start, and carry them into the summary block's "Checks not
possible" line.

Templates are a different matter: read
`${CLAUDE_PLUGIN_ROOT}/templates/README.md` and follow its resolution rule. If
`~/.expense-claim-review/templates/` does not exist, copy the plugin's `templates/`
there, say one line about it, and carry on — never ask. This skill uses **§2**
(what arrives), **§3** (`finance-review.csv`), **§4** (the derived ledgers) and
**§5** (the summary block). Never restate a column list from memory.

## Inputs

Accept any of:

- **a submission Google Sheet URL** — read it via the Drive integration
- **a `submission.csv`** or a folder containing one
- **a bare trip folder** of receipts with no submission (itemize it yourself)

You also need `claims.csv` — the prior-claims ledger — for duplicate detection. If
it does not exist, create it with the §4 header row and note that this is the first
review, so duplicates cannot be detected yet.

## Delegate these steps

This skill coordinates; three agents do the work. Use the **Agent** tool:

| Step | `subagent_type` | What it gets, what it returns |
| --- | --- | --- |
| 1 | `receipt-reader` | the files in `receipts/` → an independent extraction table |
| 2 | `policy-checker` | that table + the submission + trip context → one decision and verdict per line |
| 3 | `claim-writer` | those decisions → `finance-review.csv`, the derived ledgers, the report, the Sheet |

**Do not do these three steps inline.** The separation is the point: the agent that
reads the paper is not the agent that applies the rules, and neither one writes the
ledger. Pass each agent what it needs explicitly — it does not see this
conversation.

## Procedure

1. **Re-read the original receipts** (`receipt-reader`). Do not trust the
   submission. It is a *claim about* the receipts, written by the person being
   reimbursed, and it may have been edited after extraction. Extract date, vendor,
   amount, and currency independently from each file in `receipts/`.

2. **Reconcile.** Compare that extraction against the submission line by line:

   - amount, date, vendor, or currency differs → `MANIFEST-MISMATCH`; use the
     **receipt's** value and record both numbers in `reason`
   - a submission line has no matching receipt → `MISSING-RECEIPT`, escalate
   - a receipt exists with no submission line → note it as unclaimed; do not
     silently add it to the claim on the employee's behalf

3. **Check the trip window.** Every expense date must fall inside the trip dates in
   `trip.md` and the location must match. Outside → `OUT-OF-WINDOW`. If `trip.md`
   is missing, say so, state the window you are assuming from the submission dates,
   and flag it in the report rather than stalling.

4. **Apply the policy** (`policy-checker`) — one verdict *and one decision* per line:

   | Verdict | When | Decision |
   | --- | --- | --- |
   | `WITHIN-POLICY` | Complies fully | `APPROVE` at the full amount |
   | `OVER-CAP` | Exceeds a per-category cap | `REDUCE` to the cap; the excess becomes `non_claimable_amount`, showing the arithmetic |
   | `NON-REIMBURSABLE` | Excluded item (alcohol, minibar, entertainment) | `REJECT`, or `REDUCE` when only part of a shared receipt is excluded |
   | `NEEDS-APPROVAL` | Over an approval threshold, or otherwise requires a manager | `ESCALATE` — **do not approve it yourself** |
   | `DUPLICATE` | Matches a `claims.csv` row on vendor, date, and amount | `ESCALATE` |
   | `OUT-OF-WINDOW` | Outside trip dates or destination | `ESCALATE` |
   | `MISSING-DATA` | No legible total or date | `ESCALATE`. Never guess an amount |
   | `MISSING-RECEIPT` | No receipt behind a claimed line | `ESCALATE` |
   | `MANIFEST-MISMATCH` | Submission disagrees with the receipt | decide on the **receipt's** number; state both |

   The full mapping, including what each decision does to the two amount columns, is
   §3 of `FINANCE_REVIEW_TEMPLATE.md`. Cite the policy clause behind every verdict.
   Show the arithmetic for every capped or reduced amount. Every `ESCALATE` needs
   `action_needed`: who must act, and what they need.

5. **Handle currency.** If a receipt currency differs from the reporting currency in
   `meta.json`, apply only the FX handling the policy specifies. If the policy is
   `UNSPECIFIED` on FX, keep the original currency and `ESCALATE` with
   `action_needed` naming the rate you need — never choose one yourself.

## No-workaround rule

Never rewrite, relabel, or split an expense to get a non-compliant amount approved.
If an amount cannot be approved under the policy as written, it is a `REJECT` or an
`ESCALATE`. Report the violation plainly; do not soften or hide it.

A `PreToolUse` hook also blocks writing a line flagged `VIOLATION` into
`claims.csv`. Treat that as a backstop, not a substitute for this rule.

## Outputs

Written by `claim-writer`, in this order — the order matters:

```
finance-review.csv          source of truth, one row per submitted line   (§3)
  ├─ APPROVE / REDUCE  →  claims.csv            (append)                  (§4)
  ├─ ESCALATE          →  exceptions-queue.csv  (append)                  (§4)
  └─ REJECT            →  stays here only
EXPENSE_CLAIM_REVIEW.md     summary block first, then the reasoning       (§5)
```

`finance-review.csv` carries **every** submitted line, including the rejected ones —
that is how a non-claimable amount stays visible instead of vanishing between two
ledgers. The two ledgers are *derived* from it; never write a row into either one
that the decision sheet does not justify.

Then **create a review Google Sheet** from `finance-review.csv` (upload as
`text/csv`; Drive converts it), titled
`Expense Review — <traveller> — <trip> — <dates>`, and give the user the link to
share back with the employee. The integration cannot write into the employee's
original submission Sheet — only create a new file — so this review Sheet is the
reply, not an edit of theirs. If Drive is unavailable, the local files stand on
their own; say so and continue.

## Check before handing over

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_review.py" <folder>
```

Fix what it reports and run it again until it passes. It enforces §6: one row per
submitted line, the amount arithmetic behind each decision, a clause on every row,
`action_needed` on every `ESCALATE`, and the derived ledgers matching the sheet.

## Audit-ready format

Write so an auditor who was not present can follow every decision: cite the clause,
show the arithmetic, and name the receipt file behind each line. Prefer plain
numbers and clear reasons over prose. The report opens with the §5 summary block —
submitted, pay now, not reimbursable, pending — before any table.
