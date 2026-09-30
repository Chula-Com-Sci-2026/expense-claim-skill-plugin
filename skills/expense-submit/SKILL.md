---
name: expense-submit
description: >-
  Prepare an expense submission from the user's own receipts. Use when an employee
  wants to file, submit, or package their receipts for reimbursement — from receipt
  photos, scans, PDFs, or a folder of saved files — and get a submission CSV and
  Google Sheet to send to finance. Extracts date, vendor, description, category,
  price, and currency per line and flags likely problems before submission.
---

# Prepare an expense submission

You are on the **employee side**. Your job is to turn a pile of receipts into one
clean, complete submission package. You do **not** decide what gets reimbursed —
finance does that in `/expense-claim-review:expense-review`.

## Templates

Read `${CLAUDE_PLUGIN_ROOT}/templates/README.md` first and follow its resolution
rule. This skill uses **§2** (`submission.csv`) and points the user at **§1**
(`trip-template.md`). Never restate a column list from memory — read it from
`template-schema.json`.

If `~/.expense-claim-review/templates/` does not exist, copy the plugin's
`templates/` there before anything else and say one line — "Templates are already
set up (v1.0, default); edit `~/.expense-claim-review/templates/` any time" — then
carry on. Do not ask first.

## Inputs

Accept any of:

- **receipt images** — photos or scans attached in chat (JPG, PNG, HEIC)
- **PDFs** — a scanned receipt, an e-receipt, or a multi-receipt statement
- **a path** — a folder or file the user has saved locally
- **text receipts** — plain-text e-receipts pasted or stored as files

### If the user gives you nothing

Running this with no argument is normal. **Ask, do not guess.** Request the
receipts ("attach the photos or PDFs here, or give me the folder path"). Do not
start extracting until you have at least one receipt. Do not invent a trip.

## Delegate these steps

**Use the Agent tool with `subagent_type: receipt-reader` to extract the line items.**
Do not read the receipts inline. Give it the receipt paths and the output columns
from §2, and have it return one table. Batch the receipts into a single call unless
there are more than about a dozen.

The agent reads; you decide the packaging, run the checks, and talk to the user.

## Procedure

1. **Collect the receipts into `<folder>/receipts/`.** Every receipt the submission
   names must live there — that is where finance looks. Copy in anything attached in
   chat or saved elsewhere, and keep the filenames stable.

2. **Extract one line per expense** via `receipt-reader`, into the §2 columns.

   **Split a receipt into multiple lines** when it mixes things finance treats
   differently — food and alcohol, a hotel night and a minibar charge. One line per
   thing that could get a different decision. Every split row repeats the receipt's
   printed total in `receipt_total`, so the parts can be checked back against the
   paper.

3. **Never guess a number.** If the total, the date, or the currency is unreadable,
   write the line with the field blank and flag it `MISSING-DATA`. Then tell the
   user exactly which receipt needs a better photo. A blank you flagged is
   recoverable; a number you invented is fraud.

4. **Self-check — advisory only, and optional.** If a policy is configured at
   `~/.expense-claim-review/policy.md`, read it and set `self_flag` on lines that
   look likely to be reduced or rejected:

   - `LIKELY-OVER-CAP` — "this dinner is THB 1,280 against an 800 cap, so expect a
     reduction of about 480"
   - `LIKELY-NON-REIMBURSABLE` — "the receipt includes alcohol, which is usually
     excluded"
   - `LIKELY-NEEDS-APPROVAL` — "this change fee is over the 3,000 threshold, so it
     will need your manager's sign-off"
   - `MISSING-DATA` — "no date on this receipt; finance will bounce it"

   **Write these as warnings, never as verdicts.** You must not write "claimable:
   800", "approved", or "rejected" anywhere in the submission. Stating a claimable
   amount here quietly moves the reimbursement decision to the employee's side,
   which is exactly the control this split exists to preserve. Report the full
   amount on the receipt and let finance do the arithmetic.

   **A missing policy is not a blocker on this side.** Say so in one line — "no
   policy configured, so no advisory flags; finance will apply theirs" — and
   continue. Only the finance side requires a stored policy.

5. **Show the user the table before writing anything.** Let them correct a vendor,
   fix a category, or add context you could not read off the paper (that goes in
   `employee_note`). This is the only point where a human can catch a misread
   receipt cheaply.

6. **Check your own output.** Run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_submission.py" <folder>
   ```

   Fix everything you can fix yourself — a wrong category, a split that does not add
   up, a receipt filed under the wrong name.

## Output

**`submission.csv`, and nothing else.** No cover note, no report, no `trip.md`
written on the employee's behalf — a submission is one machine-readable file plus
the receipts it names. Its columns are §2's, in §2's order.

Then **create a Google Sheet** — upload `submission.csv` with
`contentMimeType: "text/csv"`; Drive converts it to a real spreadsheet
automatically. Title it `Expense Submission — <traveller> — <trip> — <dates>`.
Give the user the link to send to finance. If the Drive integration is not
available, say so plainly, leave `submission.csv` on disk, and tell the user they
can import it themselves. Do not fail the run over it.

## What the user sees

Only the **"Needed from you"** list — the things you could not resolve alone:

```
Needed from you
  receipt-05-taxi.jpg  the total is cut off; a clearer photo would fix it
  trip.md              not present — copy templates/trip-template.md and fill it in
```

If there is nothing, say "Nothing needed from you." Never show the user a PASS/FAIL
gate; the validator's output is for you, not for them.

## The handoff

Finance re-reads the original receipts and verifies them against your submission —
so keep `receipts/` with the package, and make sure every `receipt_file` value
actually resolves to a file. A line finance cannot trace back to a receipt gets
escalated, no matter how correct it is.
