# LedgerLens AI — Synthetic Dataset

## Purpose

This folder contains synthetic financial records used to develop and evaluate LedgerLens AI.

The dataset represents invoices, payment records and bank transactions that a finance or operations team might reconcile.

No real customer, employer, bank or transaction data is included.

## Files

### invoices.csv

Contains invoice records including:

- Invoice identifier
- Customer identifier
- Customer name
- Invoice date
- Due date
- Currency
- Invoice amount
- Invoice reference
- Invoice status

### payments.csv

Contains payment records including:

- Payment identifier
- Customer identifier
- Payment date
- Currency
- Payment amount
- Payment reference
- Payment description

### bank-transactions.csv

Contains bank transaction records including:

- Transaction identifier
- Booking date
- Value date
- Currency
- Transaction amount
- Sender name
- Bank reference
- Transaction description

### expected-matches.csv

Contains the labelled expected outcome for each reconciliation case.

It will be used to measure:

- Precision
- Recall
- False-positive rate
- False-negative rate
- Manual-review rate

## Dataset scenarios

The synthetic dataset will include:

- Exact invoice-reference matches
- Missing payment references
- Misspelled customer names
- Partial payments
- Duplicate payments
- Combined payments
- Bank-fee deductions
- Similar invoice amounts
- Delayed payments
- Currency mismatches
- Unmatched transactions

## Data principles

- All names and transactions are fictional.
- No real financial information is stored.
- Every expected match will be labelled.
- Difficult cases will be added deliberately.
- Dataset changes will be version-controlled.
- Evaluation results will not be fabricated.

## Initial dataset target

The first complete dataset will contain approximately:

- 100 invoices
- 90–110 payment records
- 90–110 bank transactions
- One labelled expected result for each reconciliation case
