# LedgerLens AI — Evaluation Plan

## Objective

The evaluation will measure whether LedgerLens AI can reduce manual reconciliation work without creating unacceptable financial risk.

The product will be assessed across:

- Matching accuracy
- AI recommendation quality
- Human review efficiency
- Explainability
- Technical performance
- Cost

## Evaluation dataset

The initial dataset will contain synthetic financial records only.

Target size:

- 100 invoices
- 90–110 payment records
- 90–110 bank transactions
- Labelled expected matches
- Labelled unmatched and duplicate records

The dataset will include both straightforward and ambiguous cases.

## Test scenarios

The evaluation set will include:

- Exact invoice-reference matches
- Exact amount and customer matches
- Missing payment references
- Misspelled customer names
- Partial payments
- Duplicate payments
- Combined payments
- Bank-fee deductions
- Similar invoice amounts
- Delayed payment dates
- Currency mismatches
- Completely unmatched transactions

## Matching metrics

### Precision

The percentage of suggested matches that are correct.

```text
Precision = Correct suggested matches / All suggested matches
```

### Recall

The percentage of true matches that the system successfully identifies.

```text
Recall = Correctly identified matches / All true matches
```

### False-positive rate

The percentage of unrelated records incorrectly suggested as matches.

```text
False-positive rate = Incorrect suggested matches / All unrelated records
```

### False-negative rate

The percentage of valid matches that the system fails to identify.

```text
False-negative rate = Missed valid matches / All true matches
```

### Manual-review rate

The percentage of records that require human review.

```text
Manual-review rate = Records requiring review / Total records
```

## AI-specific metrics

For AI-assisted recommendations, the evaluation will measure:

- Recommendation accuracy
- Explanation relevance
- Confidence-score reliability
- Percentage accepted by users
- Percentage corrected by users
- Percentage rejected by users

## Confidence thresholds

Initial thresholds:

- 90–100: High confidence
- 70–89: Review recommended
- Below 70: Do not recommend automatically

These thresholds are hypotheses and will be adjusted after testing.

## User-testing metrics

The initial user test will involve at least five participants familiar with finance, billing, accounting, payments or operations.

The test will measure:

- Reconciliation task-completion rate
- Average review time per uncertain record
- Number of incorrect user decisions
- Recommendation acceptance rate
- User confidence rating
- Explanation clarity rating
- Number of times users request additional information

## Technical metrics

The product will monitor:

- File-processing time
- Average LLM response time
- Failed-processing rate
- API-error rate
- Cost per 100 records
- Percentage of records sent to the LLM

## Initial success criteria

The first MVP will be considered promising if it achieves:

- At least 95% precision for confirmed rule-based matches
- At least 80% precision for AI-assisted suggestions
- Less than 5% false-positive rate
- At least 30% reduction in manual review
- At least 80% task-completion rate during user testing
- Average explanation-clarity rating of 4 out of 5

These are initial targets, not claimed results.

## Evaluation principles

- No performance metrics will be invented.
- Failures will be documented openly.
- Rule-based and AI-assisted results will be evaluated separately.
- Uncertain results will not be presented as confirmed.
- Product changes will be linked to evaluation findings.
