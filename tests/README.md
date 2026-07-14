# LedgerLens AI — Testing Strategy

## Purpose

This folder will contain automated and manual tests for LedgerLens AI.

The testing strategy will verify that the product:

- Validates uploaded financial data correctly
- Produces accurate deterministic matches
- Identifies ambiguous and unmatched records
- Detects duplicate payments
- Handles partial payments and currency mismatches
- Calculates confidence scores consistently
- Routes uncertain recommendations to human review
- Produces reliable evaluation metrics
- Fails safely when input data is invalid

## Planned test categories

### Unit tests

Unit tests will verify individual functions such as:

- Reference normalisation
- Customer-name normalisation
- Date parsing
- Currency validation
- Amount comparison
- Exact-reference matching
- Date-proximity matching
- Duplicate detection
- Confidence calculation

### Integration tests

Integration tests will verify that multiple components work together correctly.

Examples include:

- Uploading valid CSV files and receiving reconciliation results
- Uploading files with missing columns
- Processing exact and ambiguous matches in one session
- Recording user review decisions
- Exporting reconciliation results
- Handling AI-provider errors safely

### Evaluation tests

Evaluation tests will compare system output against:

data/synthetic/expected-matches.csv

The evaluation will calculate:

- Precision
- Recall
- False-positive rate
- False-negative rate
- Manual-review rate
- Accuracy by matching method

### User acceptance testing

The MVP will be tested with users familiar with:

- Finance
- Accounting
- Billing
- Payments
- Financial operations

Users will be asked to:

1. Upload the synthetic datasets
2. Review validation results
3. Inspect confirmed and suggested matches
4. Accept or reject uncertain recommendations
5. Complete the reconciliation
6. Export the results

## Initial test scenarios

The first test suite will include:

1. Exact reference and amount match
2. Exact amount with missing reference
3. Payment reduced by a bank fee
4. Partial payment
5. Duplicate payment
6. Delayed payment
7. Currency mismatch
8. Missing customer identifier
9. Similar customer names
10. Completely unmatched bank transaction
11. Missing required CSV column
12. Invalid date format
13. Invalid amount value
14. Empty uploaded file
15. AI-provider failure

## Expected safety behaviour

The system should:

- Never confirm a low-confidence match automatically
- Clearly identify invalid records
- Preserve original source data
- Distinguish rule-based and AI-assisted recommendations
- Record user decisions in the audit history
- Avoid exposing API keys or configuration values
- Return understandable error messages

## Planned testing tools

- Pytest
- FastAPI TestClient
- Pandas testing utilities
- GitHub Actions

## Testing principles

- Tests will use synthetic data only.
- Expected results will be labelled before evaluation.
- Rule-based and AI-assisted results will be tested separately.
- Failed tests will be documented and corrected.
- Performance claims will be based on actual test results.
