# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A **Claude Code plugin** (`expense-claim-review`) that splits reimbursement into two
roles: an employee prepares a submission from receipts, finance reviews it against a
stored policy. There is almost no application code and no build step — the "source" is
prompt-shaped Markdown (three skills, four agents) plus three shell/Python hook
scripts and two Python validators. Editing behaviour means editing prose, so changes are
validated by running the plugin against `examples/bkk-sg-trip`, not by unit tests.

The repo is simultaneously a plugin **and** a one-plugin marketplace: `.claude-plugin/plugin.json`
is the manifest, `.claude-plugin/marketplace.json` (`source: "./"`) makes the same repo
installable from GitHub.

## Commands

```bash
claude plugin validate .            # schema-check the manifests before pushing
claude --plugin-dir .               # load the plugin from this working tree
claude plugin list                  # confirm it loaded
bash tests/hooks.sh                 # automated: hook scripts (9 checks)
bash tests/templates.sh             # automated: the two validators (14 checks)
bash tests/golden-path.sh           # grades the artifacts of a review run (25 checks)
bash tests/golden-path.sh --reset   # restore claims.csv, clear outputs, before re-running

# inside a session started with --plugin-dir . (or an installed plugin)
/expense-claim-review:setup-expense-policy examples/bkk-sg-trip/expense-policy.md   # once
/expense-claim-review:expense-submit examples/bkk-sg-trip                           # employee side
/expense-claim-review:expense-review examples/bkk-sg-trip                           # finance side
```

`tests/hooks.sh` and `tests/templates.sh` cover the real code (hook scripts, validators),
and `tests/golden-path.sh` grades the artifacts a review leaves behind — you drive the
skill, the script scores the result. The rest is prose executed by a model, so it is
verified manually — the full matrix, including the adversarial invariant cases, is in
`docs/TEST-CASES.md`, with fixtures in `examples/edge-cases/`. The regression check is
the example trip: a correct review yields **THB 980** claimable and **THB 480**
non-claimable, with line 1 `APPROVE`, line 2 `REDUCE` to the 800 dinner cap, line 3
(the beer) `REJECT`, line 4 `ESCALATE` (`NEEDS-APPROVAL`), line 5 `ESCALATE`
(`DUPLICATE`). Any change to a skill or to the policy wording should be re-verified
against those five outcomes.

Run artifacts (`EXPENSE_CLAIM_REVIEW.md`, `finance-review.csv`, `exceptions-queue.csv`,
`audit-log.txt`, `agent-invocations.log`) are
gitignored, but `examples/bkk-sg-trip/claims.csv` is **tracked** and gets appended to by
a review — revert it (`git checkout examples/bkk-sg-trip/claims.csv`) after testing, or
the seeded row that makes receipt 04 a `DUPLICATE` stops being the only match.

## Architecture

Three skills, one per stage, and nothing else — `commands/` was deleted in 0.2.0, so a
skill *is* the entry point. Each is reachable two ways: the namespaced slash form
`/expense-claim-review:<skill>`, and natural language, which is the path that matters.
The frontmatter `description`s are deliberately role-disjoint ("preparing your own
receipts" vs "checking a submission someone sent") so the wrong one does not fire —
that wording is load-bearing routing logic, not documentation.

Every doc now writes the namespaced form. If you find a bare `/expense-submit` or
`/expense-review` left over from the 0.1.x `commands/` layout, read it as "invoke the
skill" and fix the wording rather than re-adding a command wrapper.

```
setup-expense-policy  →  ~/.expense-claim-review/{policy.md, meta.json, sources/, templates/}
expense-submit        →  submission.csv + a Google Sheet        (nothing else)
expense-review        →  finance-review.csv  →  claims.csv
                                            →  exceptions-queue.csv
                                            →  EXPENSE_CLAIM_REVIEW.md + a review Sheet
```

- **`templates/` is the schema.** Every file format lives there and installs itself to
  `~/.expense-claim-review/templates/` on first run — the user copy wins, and the two
  validators read `template-schema.json` rather than a hardcoded column list. Skills
  point at `templates/README.md` and its §1–§6 index; they never restate columns. A
  missing template directory is never a question to the user, just a one-line notice.
- **Policy store is user-global**, deliberately: it is configured once and outlives any
  trip folder. `meta.json` carries version, effective dates, source path, and the list
  of `UNSPECIFIED` rules; an update bumps the version and keeps `policy-v<n>.md`.
  Never write the policy into a trip folder — a trip folder is evidence, not config.
- `agents/receipt-reader.md` (sonnet, needs vision for photo/PDF receipts) is shared by
  both sides. `policy-normalizer` serves setup; `policy-checker` and `claim-writer` are
  finance-only. Their verdict vocabulary must stay in sync with `expense-review`'s step 4.
  Since 0.3.0 **delegation is mandatory, not optional**: each skill names its agents and
  says not to do the step inline. `agent-invocations.log` is the evidence, and
  `golden-path.sh` fails if the three finance-side agents are not in it.
- `hooks/hooks.json` + `hooks/scripts/` — deterministic backstops on `Write|Edit`,
  plus an observer on `Agent`.
  `block-out-of-policy.sh` exits 2 (blocking, stderr fed back to Claude) when a payload
  targeting `claims.csv` contains the string `VIOLATION`; `log-decision.sh` appends an
  audit line to `$CLAUDE_PROJECT_DIR/audit-log.txt`. Both read hook JSON on stdin, parse
  it with an inline `python3` heredoc, and exit 0 on unparseable input so a malformed
  payload never wedges the session. `log-agent-call.sh` (`PreToolUse`, matcher
  `Agent`) appends the `subagent_type` and instruction head to `agent-invocations.log`
  — the matcher is **`Agent`**, not `Task`; that is the tool's name in Claude Code 2.x,
  and grepping for `Task` finds nothing.

### Docs and diagrams

`docs/flow.mmd` is the **only** diagram source — three views in one Mermaid file: a
simple one for a non-technical reader, the detailed two-lane pipeline, and the agent
lane. A generated `flow.excalidraw` and its `flow.gen.py` generator used to sit beside
it; all three drifted apart, so the copies were deleted rather than maintained. Paste
the Mermaid into Excalidraw (hamburger menu > Mermaid to Excalidraw) if you need an
editable picture.

Keep the diagram honest about agents. A September 2026 benchmark measured **zero**
invocations across sixteen runs of **0.2.0**, and the agent lane was drawn dashed for
that reason. 0.3.0 makes delegation an instruction, so the lane is now solid — backed by
`agent-invocations.log` and `GP-22`…`GP-24`. If a future measurement shows the calls are
not happening, redraw it dashed rather than leaving the diagram ahead of the facts. The
0.2.0 evidence is `docs/benchmark-report.html`.

The marketplace is named `expense-tools`, not the plugin name, so the install id is
`expense-claim-review@expense-tools`.

`audit-log.txt` is written to `$CLAUDE_PROJECT_DIR` — the repo root, not the trip folder.

There are no bare `/expense-submit`-style aliases any more; only the namespaced
`/expense-claim-review:expense-submit` form resolves.

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
- **Fixed schemas.** They live in `templates/template-schema.json` and nowhere else —
  do not re-list columns in a skill, a doc, or this file. `vendor` stays required because
  the duplicate key is vendor + date + amount.
- **`finance-review.csv` is the source of truth; the ledgers are derived.** Every
  submitted line gets exactly one row and one decision (`APPROVE`/`REDUCE`/`REJECT`/
  `ESCALATE`). `claims.csv` and `exceptions-queue.csv` are projections of it, and a
  `REJECT` stays only in the decision sheet — that is how a non-claimable amount stays
  visible instead of falling between two files.
- **Submit's only file output is `submission.csv`.** No cover note, no `trip.md` written
  for the employee; anything missing goes in the "Needed from you" list instead.
- **Submit never requires a policy.** A missing policy means no advisory flags, not a
  stop — only the review side hard-stops.
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
document for `/expense-claim-review:setup-expense-policy`), `trip.md` (the full §1 trip
context, including the 2026-08-10 to 2026-08-12 window used for `OUT-OF-WINDOW`), four
plaintext receipts, a pre-built `submission.csv` in the §2 schema so the finance side can
be tested without running submit first, and the seeded `claims.csv`. New test cases belong here as new receipt files plus a row in the
README table.
