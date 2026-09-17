---
name: setup-expense-policy
description: >-
  Capture, review, or update the expense policy used by expense reviews. Use when
  the user wants to set up their reimbursement rules for the first time, attach or
  replace a policy PDF or document, check which policy version is currently active,
  or renew a policy that has expired. Stores the policy once, at user level, so
  every later review reuses it.
---

# Set up the expense policy

The policy is configured **once** and reused by every `/expense-review`. It lives
outside any trip folder so it survives across trips, repos, and travellers.

## Where it lives

```
~/.expense-claim-review/
├── policy.md      # the normalized, machine-readable policy
├── meta.json      # version, effective date, source, captured date
└── sources/       # the original PDF/DOCX the user supplied, kept verbatim
```

Create the directory if it does not exist. Never store the policy inside a trip
folder — a trip folder is evidence, not configuration.

## Procedure

1. **Check what is already there.** Read `~/.expense-claim-review/meta.json` if it
   exists and show the user the active policy: version, effective date, and where
   it came from. If `effective_until` has passed, say so plainly and offer to renew.

2. **Decide the action.** If a policy exists, ask whether to *keep*, *update*
   (amend specific rules), or *replace* (new document supersedes the old). Never
   overwrite silently — an auditor needs to know which rules applied when.

3. **Capture the source.** Accept either:
   - **a file** — a PDF, DOCX, Markdown, or image the user attaches or names by
     path. Read it in full. Copy the original into `sources/` unchanged.
   - **the user's own words** — they describe the rules in chat. Write them down,
     then read the result back for confirmation before saving.

   If the user runs this with no input at all, ask which of the two they want to do.
   Do not invent a default policy.

4. **Normalize into `policy.md`.** Rewrite the source into the sections below.
   Every rule must be checkable by a later review — a number, a category, and a
   consequence. Quote the original clause text alongside each rule so the review
   can cite it.

   - **Meal caps** — per category, per person, per meal, with currency.
   - **Non-reimbursable items** — e.g. alcohol, minibar, entertainment.
   - **Approval-required items** — thresholds and what triggers `NEEDS-APPROVAL`.
   - **Receipts and duplicates** — what makes a receipt valid; the duplicate key.
   - **Trip window** — how dates and destination are matched.
   - **Currency** — the reporting currency and how FX is handled.

5. **Flag what is missing.** If the source does not cover one of those sections,
   do not guess a number. Record it as `UNSPECIFIED` in `policy.md` and tell the
   user which rules a review will not be able to enforce until they fill it in.

6. **Write `meta.json`:**

   ```json
   {
     "version": "1.0",
     "effective_from": "2026-01-01",
     "effective_until": null,
     "currency": "THB",
     "source": "sources/company-expense-policy-2026.pdf",
     "captured_at": "2026-09-17",
     "unspecified": ["currency.fx_rate_source"]
   }
   ```

   On an update, bump `version`, set the previous entry's `effective_until`, and
   keep the old `policy.md` as `policy-v<n>.md`. History is not optional here.

7. **Confirm.** Show the user a short summary of the rules now in force and the
   path they were written to.

## Rules

- Do not paraphrase a number. If the source says 800, the policy says 800.
- Do not add rules the source does not contain, however reasonable they sound.
- If the source is ambiguous (e.g. "reasonable meal costs"), record it as
  `UNSPECIFIED` and ask the user for a number rather than choosing one.
