---
name: expense-review
description: Review a submitted expense claim against the expense policy and produce an auditable decision.
argument-hint: [submission Sheet URL, CSV, or folder path]
---

Review the expense submission at: $ARGUMENTS
(If nothing is given, use the current directory.)

Follow the `expense-review` skill exactly.

First check that a policy exists at `~/.expense-claim-review/policy.md`. If it does
not, stop and ask the user to run `/setup-expense-policy` — attaching their policy
PDF or writing the rules out. Never review against assumed rules.

Then re-read the original receipts rather than trusting the submission, assign one
verdict per line with the policy clause behind it, and write
`EXPENSE_CLAIM_REVIEW.md`, `claims.csv` (approved lines only), and
`exceptions-queue.csv`. Finish by creating a review Google Sheet to share back.

Do not approve anything the policy does not allow, and never relabel or split an
expense to make it pass — route it to the exception queue instead.
