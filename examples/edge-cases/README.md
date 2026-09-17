# Edge-case fixtures

Deliberately kept **out of** `examples/bkk-sg-trip/` so the golden-path total stays
THB 980. Copy a file into that trip's `receipts/` to exercise one case, then
`git checkout` the trip folder to reset.

| File | Exercises | Expected |
| --- | --- | --- |
| `receipt-05-torn.txt` | `SUB-09`, `MISSING-DATA` | Amount left blank and flagged. Never guessed. |
| `receipt-06-out-of-window.txt` | `REV-06`, `OUT-OF-WINDOW` | Dated 2026-08-15, after the trip ends 2026-08-12 → exception. |
| `receipt-07-foreign-currency.txt` | `REV-07`, currency handling | SGD against a THB policy. With FX `UNSPECIFIED`, the line is flagged and the user is asked for a rate — never converted at an invented one. |

Two more cases need no fixture, only an edit to `submission.csv`:

- **`REV-03` `MANIFEST-MISMATCH`** — change the lunch `price` from `180` to `1800`.
- **`REV-04` `MISSING-RECEIPT`** — point a row's `receipt_file` at a file that does not exist.

See `docs/TEST-CASES.md` for the full matrix.
