# Expense policy (example)

All amounts in THB. Applies to domestic and regional business travel.

## Meal caps (per person, per meal)
- Breakfast: up to 250
- Lunch: up to 500
- Dinner: up to 800

Amounts above the cap are not claimable. Claim up to the cap and record the
excess as non-claimable.

## Non-reimbursable items
- Alcohol is never reimbursable, at any amount. On a shared receipt, claim only
  the non-alcohol portion.
- Minibar, personal items, and entertainment are not reimbursable.

## Flights and changes
- Flight change or rebooking fees above 3,000, or any change made on or after the
  trip start date, require manager approval before reimbursement. Route to the
  exception queue with reason NEEDS-APPROVAL.

## Receipts and duplicates
- Every claimed expense needs a legible receipt with a date and a total. Missing
  either -> exception (MISSING-DATA).
- An expense matching an existing row in claims.csv on vendor, date, and amount
  is a duplicate -> exception (DUPLICATE).

## Trip window
- Expenses must fall within the trip dates in trip.md and match the destination.
  Anything outside -> exception (OUT-OF-WINDOW).
