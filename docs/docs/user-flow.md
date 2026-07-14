# LedgerLens AI — Primary User Flow

## 1. Start reconciliation

The user opens LedgerLens AI and selects **New Reconciliation**.

## 2. Upload files

The user uploads:

- invoices.csv
- payments.csv
- bank-transactions.csv

## 3. Validate data

The system checks for:

- Missing fields
- Invalid values
- Duplicate rows
- Incorrect date formats
- Unsupported currencies

## 4. Run reconciliation

The system performs:

1. Exact reference matching
2. Amount and customer matching
3. Date-proximity matching
4. Normalised text matching
5. AI-assisted analysis for unresolved cases

## 5. View results

Records are grouped into:

- Confirmed matches
- Suggested matches
- Unmatched records
- Potential duplicates
- Records requiring review

## 6. Review uncertain cases

The user sees:

- Invoice details
- Payment details
- Suggested match
- Confidence score
- Matching explanation
- Alternative candidates

## 7. Make a decision

The user can:

- Accept the recommendation
- Reject the recommendation
- Select an alternative match
- Add a review note
- Mark the case for further investigation

## 8. Complete reconciliation

The system shows:

- Total records processed
- Confirmed matches
- Reviewed matches
- Unmatched records
- Duplicate records

## 9. Export results

The user exports:

- Reconciliation CSV
- Review decisions
- Audit history
