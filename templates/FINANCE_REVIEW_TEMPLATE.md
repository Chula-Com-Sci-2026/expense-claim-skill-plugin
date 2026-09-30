# Finance review template

What finance receives for every reviewed claim. Two parts: the **decision sheet**
`finance-review.csv` (one row per submitted line — the source of truth) and a **summary block**
at the top of `EXPENSE_CLAIM_REVIEW.md`. `claims.csv` and `exceptions-queue.csv` are derived from
the decision sheet, never written independently.

```
finance-review.csv   every line, one decision each         ← source of truth
  ├─ APPROVE / REDUCE → append to claims.csv            (ledger, duplicate detection)
  ├─ ESCALATE         → append to exceptions-queue.csv  (waits for a human)
  └─ REJECT           → stays in finance-review.csv     (non-claimable; recover if paid)
EXPENSE_CLAIM_REVIEW.md  summary block + reasoning an auditor can follow
```

## Part 1 — Decision sheet: `finance-review.csv`

| Column | Filled from | Format / allowed values |
| --- | --- | --- |
| `claim_id` | trip.md | as given |
| `line` | submission.csv | same line numbers, same order |
| `date`, `vendor`, `description`, `category`, `currency` | submission.csv | copied unchanged |
| `submitted_amount` | submission.csv `price` | copied unchanged |
| `receipt_amount` | **finance's own re-read of the receipt** | blank if unreadable |
| `decision` | reviewer | `APPROVE` · `REDUCE` · `REJECT` · `ESCALATE` |
| `claimable_amount` | reviewer | amount to pay now |
| `non_claimable_amount` | reviewer | amount that will never be paid |
| `verdict_code` | reviewer | plugin verdict (WITHIN-POLICY, OVER-CAP, …) |
| `policy_clause` | reviewer | clause ID from the stored policy, or `UNSPECIFIED` |
| `reason` | reviewer | one sentence an auditor can follow; show arithmetic for REDUCE |
| `receipt_file` | reviewer | receipt the decision rests on |
| `action_needed` | reviewer | ESCALATE only: who must act, and what they need |

### Decisions

| Decision | Use when | `claimable_amount` | `non_claimable_amount` |
| --- | --- | --- | --- |
| **APPROVE** | complies in full | full amount | 0 |
| **REDUCE** | only part is eligible (cap, spouse's share, personal nights) | eligible part | the rest |
| **REJECT** | the policy names it non-reimbursable | 0 | full amount |
| **ESCALATE** | a human must approve, or a document / rate / receipt is missing, or it is a duplicate or out of window | 0 | 0 (still pending) |

"Full amount" is `receipt_amount` when present, otherwise `submitted_amount`. When the two
differ, the receipt wins: `verdict_code` = `MANIFEST-MISMATCH` and `reason` states both numbers.

Every number traces to a receipt or a clause. A missing amount, rate or document is an
ESCALATE with `action_needed` filled in. Foreign currency stays in its original currency and
escalates unless the policy names an FX source. A line is decided as filed — one line, one decision.

## Part 2 — Summary block (top of `EXPENSE_CLAIM_REVIEW.md`)

```
Claim:               <claim_id> — <traveller> — <destination> — <dates>
Policy:              <policy name> v<version>, captured <date> · template v<template_version>
Submitted:           <sum of submitted_amount> <currency>   (other currencies listed separately)
Pay now:             <sum of claimable_amount>             → claims.csv (<n> rows)
Not reimbursable:    <sum of non_claimable_amount>         (recover if already paid)
Pending (escalated): <n> lines, <sum of submitted_amount>  → exceptions-queue.csv
Claim-level flags:   <late submission, FX pending, … | none>
Checks not possible: <UNSPECIFIED rules that affected this claim | none>
Sign-off:            Reviewer ________   Departmental approver ________
```

The sign-off line reflects NA-13 of the Vanderbilt policy (two approvals). A different policy may
name different approvers; the line follows whatever the stored policy requires.

## Check before handing over

`validate_review.py` enforces the rules in `template-schema.json` → `finance_review`:
one row per submitted line, amounts consistent with the decision, a clause on every row,
`action_needed` on every ESCALATE, and the derived CSVs matching the sheet.
