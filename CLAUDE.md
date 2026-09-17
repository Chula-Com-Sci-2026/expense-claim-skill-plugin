# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A **Claude Code plugin** (`expense-claim-review`) that splits reimbursement into two
roles: an employee prepares a submission from receipts, finance reviews it against a
stored policy. There is no application code and no build step — the "source" is
prompt-shaped Markdown (three skills, three commands, four agents) plus two
shell/Python hook scripts. Editing behaviour means editing prose, so changes are
validated by running the plugin against `examples/bkk-sg-trip`, not by unit tests.

The repo is simultaneously a plugin **and** a one-plugin marketplace: `.claude-plugin/plugin.json`
is the manifest, `.claude-plugin/marketplace.json` (`source: "./"`) makes the same repo
installable from GitHub.

## Commands

```bash
claude plugin validate .            # schema-check the manifests before pushing
claude --plugin-dir .               # load the plugin from this working tree
claude plugin list                  # confirm it loaded
bash tests/hooks.sh                 # the only automated tests (hook scripts)

/setup-expense-policy examples/bkk-sg-trip/expense-policy.md   # once
/expense-submit examples/bkk-sg-trip                           # employee side
/expense-review examples/bkk-sg-trip                           # finance side
```

`tests/hooks.sh` covers the deterministic hook scripts. Everything else is prose
executed by a model, so skill behaviour is verified manually — the full matrix,
including the adversarial invariant cases, is in `docs/TEST-CASES.md`, with fixtures
in `examples/edge-cases/`. The regression check is the example trip: a correct
review yields **THB 980** total claimable, with receipt 01 approved in full, 02 capped
at 800 (alcohol + excess non-claimable), 03 an exception `NEEDS-APPROVAL`, 04 an
exception `DUPLICATE`. Any change to a skill or to the policy wording should be
re-verified against those four outcomes.

Run artifacts (`EXPENSE_CLAIM_REVIEW.md`, `exceptions-queue.csv`, `audit-log.txt`) are
gitignored, but `examples/bkk-sg-trip/claims.csv` is **tracked** and gets appended to by
a review — revert it (`git checkout examples/bkk-sg-trip/claims.csv`) after testing, or
the seeded row that makes receipt 04 a `DUPLICATE` stops being the only match.

## Architecture

Three skills, one per stage, each with a thin command wrapper that delegates rather
than restating the procedure. Skills also auto-trigger from natural language, so the
commands are a convenience, not the only path — their frontmatter `description`s are
deliberately role-disjoint ("preparing your own receipts" vs "checking a submission
someone sent") so the wrong one does not fire.

```
/setup-expense-policy  →  ~/.expense-claim-review/{policy.md, meta.json, sources/}
/expense-submit        →  submission.csv + submission.md + a Google Sheet
/expense-review        →  EXPENSE_CLAIM_REVIEW.md + claims.csv + exceptions-queue.csv + a review Sheet
```

- **Policy store is user-global**, deliberately: it is configured once and outlives any
  trip folder. `meta.json` carries version, effective dates, source path, and the list
  of `UNSPECIFIED` rules; an update bumps the version and keeps `policy-v<n>.md`.
  Never write the policy into a trip folder — a trip folder is evidence, not config.
- `agents/receipt-reader.md` (sonnet, needs vision for photo/PDF receipts) is shared by
  both sides. `policy-normalizer` serves setup; `policy-checker` and `claim-writer` are
  finance-only. Their verdict vocabulary must stay in sync with `expense-review`'s step 4.
- `hooks/hooks.json` + `hooks/scripts/` — deterministic backstops on `Write|Edit`.
  `block-out-of-policy.sh` exits 2 (blocking, stderr fed back to Claude) when a payload
  targeting `claims.csv` contains the string `VIOLATION`; `log-decision.sh` appends an
  audit line to `$CLAUDE_PROJECT_DIR/audit-log.txt`. Both read hook JSON on stdin, parse
  it with an inline `python3` heredoc, and exit 0 on unparseable input so a malformed
  payload never wedges the session.

### Invariants worth preserving

- **Submit never approves.** The employee side emits advisory flags only
  (`LIKELY-OVER-CAP`, `LIKELY-NON-REIMBURSABLE`, `LIKELY-NEEDS-APPROVAL`,
  `MISSING-DATA`) and must never write a claimable amount, "approved", or "rejected".
  Letting it stamp verdicts collapses the separation of duties the split exists for.
- **Finance re-reads the receipts.** The submission is treated as a claim *about* the
  receipts, not as truth — it was written by the person being paid. Disagreement is
  `MANIFEST-MISMATCH` and the receipt's value wins.
- **Review refuses to run without a stored policy.** No assumed or remembered rules;
  a decision that cannot cite a stored clause is not auditable.
- **Never invent a number.** Unreadable field → blank + `MISSING-DATA`. Policy silent
  on a rule → `UNSPECIFIED` + ask the user, never a plausible default.
- **The no-workaround rule** — no relabelling or splitting an expense to make it pass —
  appears in the review skill, its command, and both policy-facing agents.
- **Fixed schemas.** `submission.csv` = `date,vendor,description,category,price,currency,receipt_file,self_flag`
  (`vendor` is required because the duplicate key is vendor + date + amount);
  `claims.csv` = `date,vendor,category,claimable_amount,receipt_file,review_date` (approved only);
  `exceptions-queue.csv` = `date,vendor,amount,reason,receipt_file`.
- **Verdict codes** — `WITHIN-POLICY`, `OVER-CAP`, `NON-REIMBURSABLE`, `NEEDS-APPROVAL`,
  `DUPLICATE`, `OUT-OF-WINDOW`, `MISSING-DATA`, `MISSING-RECEIPT`, `MANIFEST-MISMATCH` —
  live in `expense-review`, the agents, and the example policy. Renaming one means
  touching all three.
- Hook commands reference `${CLAUDE_PLUGIN_ROOT}`; keep that indirection so the plugin
  works from any install location.

### Google Sheets integration

Both output Sheets are created by uploading CSV text with `contentMimeType: "text/csv"`,
which Drive auto-converts to a spreadsheet. **There is no append-rows or edit-cells
operation** — `update_file` changes metadata (title, parent) only. That is why finance
creates a *separate* review Sheet instead of writing decisions back into the employee's
submission Sheet. Drive being unavailable must degrade gracefully: the local files are
the source of truth, the Sheet is a convenience.

## Example data

`examples/bkk-sg-trip/` is synthetic and is the test fixture: `expense-policy.md` (caps,
non-reimbursables, the 3,000 flight-change approval threshold — and a sample source
document for `/setup-expense-policy`), `trip.md` (the 2026-08-10 to 2026-08-12 window
used for `OUT-OF-WINDOW`), four plaintext receipts, a pre-built `submission.csv` /
`submission.md` so the finance side can be tested without running submit first, and the
seeded `claims.csv`. New test cases belong here as new receipt files plus a row in the
README table.
