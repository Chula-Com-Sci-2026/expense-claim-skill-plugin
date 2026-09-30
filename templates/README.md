# Templates

Every file format this plugin reads or writes. Skills point here instead of restating
column lists, so renaming a column in one place changes what the checks accept.

## How a skill resolves a template

> Look for the template in `~/.expense-claim-review/templates/`. If it is not there, use
> `${CLAUDE_PLUGIN_ROOT}/templates/`. Never hardcode a column list — read it from
> `template-schema.json`.

The user copy always wins. A skill that finds no `~/.expense-claim-review/templates/`
copies this directory there on its first run, records `"template_version": "1.0"` in
`~/.expense-claim-review/meta.json`, and says so in one line — it never asks first.

## Sections

| § | Topic | File |
| --- | --- | --- |
| §1 | Trip context (employee fills it) | `trip-template.md` |
| §2 | `submission.csv` — the employee handoff | `SUBMISSION_TEMPLATE.md`, `submission-template.csv`, `submission-example.csv` |
| §3 | `finance-review.csv` — the decision sheet, source of truth | `FINANCE_REVIEW_TEMPLATE.md` part 1, `finance-review-template.csv`, `finance-review-example.csv` |
| §4 | Derived ledgers — `claims.csv`, `exceptions-queue.csv` | `FINANCE_REVIEW_TEMPLATE.md` (the tree at the top) + `template-schema.json` → `derived_outputs` |
| §5 | Summary block at the top of `EXPENSE_CLAIM_REVIEW.md` | `FINANCE_REVIEW_TEMPLATE.md` part 2 |
| §6 | The checks | `template-schema.json`, run by `scripts/validate_submission.py` and `scripts/validate_review.py` |

## Overriding

Edit the copy under `~/.expense-claim-review/templates/`. Add a column to
`template-schema.json` and the validators require it; rename one and they expect the new
name. Bump `template_version` in `meta.json` when you do, so a review report can say which
template it was written against.
