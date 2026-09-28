# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A **Claude Code plugin** (`expense-claim-review`) that splits reimbursement into two
roles: an employee prepares a submission from receipts, finance reviews it against a
stored policy. There is no application code and no build step — the "source" is
prompt-shaped Markdown (three skills, four agents) plus three shell/Python hook
scripts. Editing behaviour means editing prose, so changes are
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
bash tests/golden-path.sh           # grades the artifacts of a review run (14 checks)
bash tests/golden-path.sh --reset   # restore claims.csv, clear outputs, before re-running
python3 bench/datasets.gen.py       # regenerate the benchmark fixtures + ground truth
bash bench/run.sh --dry-run         # benchmark: print every command, spend nothing

# inside a session started with --plugin-dir . (or an installed plugin)
/expense-claim-review:setup-expense-policy examples/bkk-sg-trip/expense-policy.md   # once
/expense-claim-review:expense-submit examples/bkk-sg-trip                           # employee side
/expense-claim-review:expense-review examples/bkk-sg-trip                           # finance side
```

`tests/hooks.sh` covers the deterministic hook scripts, and `tests/golden-path.sh`
grades the artifacts a review leaves behind — you drive the skill, the script scores
the result. The rest is prose executed by a model, so it is verified manually — the full matrix,
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

Three skills, one per stage, and nothing else — `commands/` was deleted in 0.2.0, so a
skill *is* the entry point. Each is reachable two ways: the namespaced slash form
`/expense-claim-review:<skill>`, and natural language, which is the path that matters.
The frontmatter `description`s are deliberately role-disjoint ("preparing your own
receipts" vs "checking a submission someone sent") so the wrong one does not fire —
that wording is load-bearing routing logic, not documentation.

Older prose (`README.md`, `docs/flow.mmd`, `docs/TEST-CASES.md`, the tests' help text)
still writes the bare `/expense-submit` / `/expense-review` from the 0.1.x
`commands/` layout. Read those as "invoke the skill", and prefer updating them to
re-adding command wrappers.

```
setup-expense-policy  →  ~/.expense-claim-review/{policy.md, meta.json, sources/}
expense-submit        →  submission.csv + submission.md + a Google Sheet
expense-review        →  EXPENSE_CLAIM_REVIEW.md + claims.csv + exceptions-queue.csv + a review Sheet
```

- **Policy store is user-global**, deliberately: it is configured once and outlives any
  trip folder. `meta.json` carries version, effective dates, source path, and the list
  of `UNSPECIFIED` rules; an update bumps the version and keeps `policy-v<n>.md`.
  Never write the policy into a trip folder — a trip folder is evidence, not config.
- `agents/receipt-reader.md` (sonnet, needs vision for photo/PDF receipts) is shared by
  both sides. `policy-normalizer` serves setup; `policy-checker` and `claim-writer` are
  finance-only. Their verdict vocabulary must stay in sync with `expense-review`'s step 4.
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

Keep the diagram honest about agents: the plugin declares four, and `bench/` measured
**zero** invocations of any of them. The agent lane is drawn dashed and labelled
"available, not observed" for that reason — do not redraw it as a live pipeline
without a measurement that says otherwise.

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

## Benchmark

`bench/` is the instrumented version of `E2E-02`: the same submissions reviewed with
and without the plugin, scored on accuracy, tokens, cost, time and subagent calls.
`bench/README.md` has the full design. Three things to know before touching it:

- `bench/datasets.gen.py` is the single source of both the fixtures and the ground
  truth, so an amount cannot drift from what it is scored against. Edit the
  generator, never `bench/datasets/`.
- **Receipt filenames name the merchant only.** An early run had a baseline catch the
  duplicate purely from the string `resubmit` in a filename — the fixture was
  answering its own question.
- Token accounting has three traps, all of which fail silently: usage rows repeat per
  content block (dedupe by `message.id`, keep the highest `apiBlockIndex`), subagent
  tokens live in separate `<session-id>/subagents/*.jsonl` files, and the tool is
  called `Agent`. `bench/measure.py` handles all three; anything reimplementing it
  must too.

The sample policy the benchmark uses (`bench/policies/policy-a.docx`, the Workable
template) contains **no digits at all**, which is the point — it tests whether a
reviewer invents the caps it does not have.

## Example data

`examples/bkk-sg-trip/` is synthetic and is the test fixture: `expense-policy.md` (caps,
non-reimbursables, the 3,000 flight-change approval threshold — and a sample source
document for `/setup-expense-policy`), `trip.md` (the 2026-08-10 to 2026-08-12 window
used for `OUT-OF-WINDOW`), four plaintext receipts, a pre-built `submission.csv` /
`submission.md` so the finance side can be tested without running submit first, and the
seeded `claims.csv`. New test cases belong here as new receipt files plus a row in the
README table.
