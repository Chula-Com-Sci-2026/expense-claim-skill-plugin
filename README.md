# Expense Claim Review — a Claude Code plugin

Two roles, two commands, one separation of duties. An **employee** turns a pile of
receipts into a clean submission Google Sheet; **finance** checks that submission
against a stored policy and produces an auditable reimbursement decision — with a
deterministic hook that blocks out-of-policy writes and logs every decision.

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

### 0. Once — set up the policy

```bash
/setup-expense-policy ./company-policy.pdf
```

Attach a PDF, DOCX, or photo of the policy, or just write the rules out. It is
normalized and stored at `~/.expense-claim-review/policy.md` with a version and
effective dates, and reused by every later review. Run it again to check what's
active, amend a rule, or replace an expired policy — old versions are kept.

### 1. Employee — submit

```bash
/expense-submit ./my-trip
```

Or run it bare and attach receipt photos when asked. Reads images, PDFs, or text
receipts and writes `submission.csv` + `submission.md`, then uploads the CSV to
Drive as a **Google Sheet** with one row per expense: date, vendor, description,
category, price, currency, receipt file, and an advisory flag.

It never says *approved* or *claimable* — only "this looks likely to be reduced."
The decision stays with finance.

### 2. Finance — review

```bash
/expense-review ./my-trip
```

Accepts the submission Sheet URL, a `submission.csv`, or a bare trip folder. It
re-reads the original receipts rather than trusting the submission, applies the
stored policy line by line, and writes:

- `EXPENSE_CLAIM_REVIEW.md` — audit-ready report, a policy clause per decision
- `claims.csv` — approved lines appended
- `exceptions-queue.csv` — flagged lines awaiting a human decision
- a **review Google Sheet** to share back with the employee

Both skills also fire from plain English — "help me file these receipts", "check
this claim against our policy" — without typing a command.

## What's inside

```
expense-claim-review/
├── .claude-plugin/
│   ├── plugin.json          # plugin manifest
│   └── marketplace.json     # makes the repo installable from GitHub
├── commands/
│   ├── setup-expense-policy.md
│   ├── expense-submit.md    # employee entry point
│   └── expense-review.md    # finance entry point
├── skills/
│   ├── setup-expense-policy/SKILL.md
│   ├── expense-submit/SKILL.md
│   └── expense-review/SKILL.md
├── agents/
│   ├── receipt-reader.md    # shared — reads images, PDFs, text
│   ├── policy-normalizer.md # setup side
│   ├── policy-checker.md    # finance side
│   └── claim-writer.md      # finance side
├── hooks/
│   ├── hooks.json           # PreToolUse (block) + PostToolUse (log)
│   └── scripts/
│       ├── block-out-of-policy.sh
│       └── log-decision.sh
└── examples/
    └── bkk-sg-trip/         # synthetic test data (4 receipts + a submission)
```

## Why the split matters

| | `/expense-submit` | `/expense-review` |
| --- | --- | --- |
| Role | Employee | Finance |
| Reads | `receipts/`, `trip.md` | policy, `claims.csv`, **and the receipts again** |
| Question | "Is my package complete?" | "Does it pass policy?" |
| May say "approved" | Never | Yes |

Three controls keep it honest:

1. **Submit is advisory only.** If the employee side could stamp verdicts, finance
   would be rubber-stamping the claimant's own conclusion.
2. **Finance re-derives from the receipts.** The submission is a *claim about* the
   receipts, written by the person being paid, and could have been edited after the
   fact. Mismatches are flagged `MANIFEST-MISMATCH` and the receipt wins.
3. **Some checks only exist on the finance side.** `DUPLICATE` needs `claims.csv` —
   prior claims across people and trips, which an employee should not be reading.

## Test cases in `examples/bkk-sg-trip`

| Receipt | Expected outcome |
| --- | --- |
| 01 lunch (THB 180) | approved in full |
| 02 dinner + alcohol (THB 1280) | claim THB 800 (dinner cap), excess + alcohol non-claimable |
| 03 flight change (THB 4500) | exception — NEEDS-APPROVAL (fee > 3,000) |
| 04 Grab (THB 220) | exception — DUPLICATE of a row in claims.csv |

Expected total claimable: **THB 980**.

`expense-policy.md` in that folder doubles as a sample source document for
`/setup-expense-policy`. To exercise `MANIFEST-MISMATCH`, edit a `price` in
`submission.csv` so it disagrees with its receipt.

## Prove it works (baseline vs plugin)

Run the same 4 receipts twice and compare:

1. **Baseline** — a plain prompt ("review these expenses") with no plugin.
2. **Plugin** — `/expense-submit` then `/expense-review`.

Compare on: policy violations caught, missing-approval detection, duplicate
prevention, tampering detection, and whether each decision cites a policy clause.

## License

MIT
