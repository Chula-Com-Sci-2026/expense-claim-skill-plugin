# Expense Claim Review — a Claude Code plugin

Turn receipts and a policy into **auditable reimbursement decisions**. The plugin
reads a trip folder, itemizes each receipt, checks it against the policy and the
trip window, and produces a claim or an exception record — with a deterministic
hook that blocks out-of-policy writes and logs every decision.

This repo is both a **plugin** and a one-plugin **marketplace**, so it installs
straight from GitHub.

## Install

```bash
# In Claude Code
/plugin marketplace add <your-github-user>/expense-claim-review
/plugin install expense-claim-review@expense-tools
```

Or, for local development without a marketplace:

```bash
git clone https://github.com/<your-github-user>/expense-claim-review.git
claude --plugin-dir ./expense-claim-review
```

Verify it loaded:

```bash
claude plugin list
claude plugin validate ./expense-claim-review   # schema check before you push
```

## Use

```bash
/expense examples/bkk-sg-trip
```

Claude reads the folder's `expense-policy.md`, `trip.md`, `receipts/`, and
`claims.csv`, then writes three artifacts into that folder:

- `EXPENSE_CLAIM_REVIEW.md` — audit-ready report with a decision per line
- `claims.csv` — approved lines appended
- `exceptions-queue.csv` — flagged lines awaiting a human decision

The `expense-claim-review` skill also fires automatically when you ask Claude to
review a trip's expenses, without typing the command.

## What's inside

```
expense-claim-review/
├── .claude-plugin/
│   ├── plugin.json          # plugin manifest
│   └── marketplace.json     # makes the repo installable from GitHub
├── commands/
│   └── expense.md           # /expense entry point
├── skills/
│   └── expense-claim-review/
│       └── SKILL.md         # the core: the whole review flow
├── agents/                  # optional sub-agents (bonus)
│   ├── receipt-reader.md
│   ├── policy-checker.md
│   └── claim-writer.md
├── hooks/
│   ├── hooks.json           # PreToolUse (block) + PostToolUse (log)
│   └── scripts/
│       ├── block-out-of-policy.sh
│       └── log-decision.sh
└── examples/
    └── bkk-sg-trip/         # synthetic test data (4 receipts)
```

## Test cases in `examples/bkk-sg-trip`

| Receipt | Expected outcome |
| --- | --- |
| 01 lunch (THB 180) | approved in full |
| 02 dinner + alcohol (THB 1280) | claim THB 800 (dinner cap), excess + alcohol non-claimable |
| 03 flight change (THB 4500) | exception — NEEDS-APPROVAL (fee > 3,000) |
| 04 Grab (THB 220) | exception — DUPLICATE of a row in claims.csv |

Expected total claimable: **THB 980**.

## Prove it works (baseline vs plugin)

Run the same 4 receipts twice and compare:

1. **Baseline** — a plain prompt ("review these expenses") with no plugin.
2. **Plugin** — `/expense examples/bkk-sg-trip`.

Compare on: policy violations caught, missing-approval detection, duplicate
prevention, and whether each decision cites a policy clause (audit clarity).

## License

MIT
