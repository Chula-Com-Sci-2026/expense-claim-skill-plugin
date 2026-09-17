---
name: setup-expense-policy
description: Set up, review, or update the expense policy used by every expense review.
argument-hint: [policy PDF/document path, or nothing to be asked]
---

Set up the expense policy from: $ARGUMENTS

Follow the `setup-expense-policy` skill exactly.

First read `~/.expense-claim-review/meta.json` and tell the user what policy is
already active, if any, including whether it has expired. Then ask whether to keep,
update, or replace it.

If no source was given above, ask the user whether they want to attach a policy
document (PDF, DOCX, Markdown, or a photo) or write the rules out in their own
words. Do not invent a default policy, and do not paraphrase any number.

Save the normalized policy to `~/.expense-claim-review/policy.md`, keep the original
in `sources/`, record version and effective dates in `meta.json`, and preserve the
previous version rather than overwriting it.
