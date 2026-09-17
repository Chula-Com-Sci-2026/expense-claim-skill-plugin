---
name: expense-submit
description: Prepare an expense submission from your receipts and produce a Google Sheet to send to finance.
argument-hint: [receipt files or folder path]
---

Prepare an expense submission from: $ARGUMENTS

Follow the `expense-submit` skill exactly.

If no receipts were given above, ask the user for them before doing anything else —
they can attach receipt images or PDFs directly, or give you the path to a folder
where they saved them. Also ask for the trip context (traveller, dates, destination,
purpose) unless a `trip.md` is already there. Do not invent receipts or a trip.

Extract date, description, category, price, and currency for every line, show the
user the table for correction, then write `submission.csv` and upload it to Google
Drive as a Sheet.

You are preparing a submission, not approving one. Flag likely problems as warnings;
never write "approved", "rejected", or a claimable amount — finance decides that.
