---
description: Review a trip's expense claims against policy and produce an auditable claim or exception record.
argument-hint: [path-to-trip-folder]
---

Review the travel expenses in this folder: $ARGUMENTS
(If no path is given, use the current directory.)

Follow the `expense-claim-review` skill exactly:

1. Read `expense-policy.md`, `trip.md`, every file in `receipts/`, and `claims.csv` from that folder.
2. Itemize each receipt, check it against the trip window and the policy, and decide approve-or-exception for every line.
3. Write `EXPENSE_CLAIM_REVIEW.md`, append approved lines to `claims.csv`, and route every exception to `exceptions-queue.csv`.

Do not approve anything the policy does not allow, and never relabel or split an expense to make it pass — route it to the exception queue instead.
