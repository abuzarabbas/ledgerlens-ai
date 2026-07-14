# LedgerLens AI — Product Decisions

## Purpose

This document records the major product and technical decisions made while building LedgerLens AI.

Each decision includes:

- The problem
- The decision
- The reasoning
- The trade-off
- The validation method

The goal is to make product thinking visible and prevent important decisions from becoming undocumented assumptions.

---

## Decision 1: Use deterministic matching before AI

### Problem

Many financial records can be matched reliably using exact references, amounts, currencies and customer identifiers.

Using an LLM for every transaction would increase:

- Cost
- Processing time
- Inconsistency
- Privacy exposure
- Risk of incorrect recommendations

### Decision

LedgerLens AI will apply deterministic rules before sending any record to an LLM.

The matching sequence will begin with:

1. Exact invoice reference
2. Exact payment reference
3. Amount and currency
4. Customer identifier
5. Date proximity
6. Normalised customer name

AI will only analyse unresolved or ambiguous cases.

### Reasoning

Traditional rules are more reliable and explainable when the necessary structured data is available.

AI provides the most value when information is incomplete, inconsistent or written in unstructured descriptions.

### Trade-off

A rule-first approach requires more matching logic and maintenance than sending all records to an LLM.

However, it produces a safer and more cost-efficient financial workflow.

### Validation

Rule-based and AI-assisted results will be measured separately.

---

## Decision 2: Require human review for uncertain recommendations

### Problem

An incorrect financial match could create false accounting records, hide unpaid invoices or incorrectly close a transaction.

### Decision

Low- and medium-confidence recommendations will require human review before being treated as confirmed.

Initial confidence bands:

- 90–100: High confidence
- 70–89: Human review required
- Below 70: No match recommendation

### Reasoning

Confidence scores should guide review priority, not replace human accountability.

### Trade-off

Human review limits full automation.

However, the product prioritises accuracy and appropriate trust over maximum automation.

### Validation

User testing will measure whether people understand the confidence levels and review uncertain cases appropriately.

---

## Decision 3: Explain every suggested match

### Problem

Users may not trust an AI recommendation when they cannot understand how it was produced.

### Decision

Each suggested match will display:

- Matching fields
- Conflicting fields
- Confidence score
- Matching method
- Plain-language explanation
- Source records used

### Reasoning

Financial users need enough evidence to make an informed decision.

### Trade-off

Detailed explanations may increase interface complexity.

The product will therefore use concise summaries with optional detailed views.

### Validation

Users will rate explanation clarity during testing.

---

## Decision 4: Keep rule-based and AI-generated decisions separate

### Problem

Users may assume that all matches were produced through the same method.

### Decision

The interface and audit report will distinguish between:

- Rule-confirmed match
- AI-suggested match
- Human-approved match
- Human-rejected match
- Unresolved record

### Reasoning

The origin of a recommendation affects how much scrutiny it should receive.

### Trade-off

Additional categories create more product complexity but improve transparency and auditability.

---

## Decision 5: Use synthetic financial data for the MVP

### Problem

Real financial records may contain confidential customer, company and banking information.

### Decision

The public MVP and GitHub repository will use synthetic data only.

No real customer or employer information will be uploaded or committed.

### Reasoning

Synthetic data enables public testing without creating privacy or confidentiality risks.

### Trade-off

Synthetic records may not reproduce every complexity found in real financial systems.

Difficult and realistic edge cases will therefore be added deliberately.

---

## Decision 6: Do not allow automatic ledger changes

### Problem

Automatically modifying accounting records would significantly increase product, security and compliance risk.

### Decision

The MVP will only recommend and document matches.

It will not:

- Post journal entries
- Modify accounting systems
- Approve financial adjustments
- Connect directly to live bank accounts
- Make irreversible financial decisions

### Reasoning

The first product goal is to validate reconciliation assistance, not accounting-system automation.

### Trade-off

The MVP delivers less end-to-end automation but remains safer and easier to test.

---

## Decision 7: Use CSV as the initial input format

### Problem

Supporting PDFs, spreadsheets, APIs and accounting platforms would increase the MVP scope significantly.

### Decision

The initial product will support standardised CSV files for:

- Invoices
- Payments
- Bank transactions

### Reasoning

CSV files are simple to create, validate and process. They allow the team to focus on matching quality and review experience.

### Trade-off

Users must prepare files in the expected format.

Additional formats can be considered after validating the core workflow.

---

## Decision 8: Build a review queue instead of a chatbot

### Problem

A generic chatbot would not provide a structured reconciliation workflow or clear task completion.

### Decision

The primary interface will be a review queue showing uncertain records and recommended actions.

AI explanations may appear within the workflow, but chat will not be the main product experience.

### Reasoning

The user’s objective is to complete reconciliation, not to have an open-ended conversation.

### Trade-off

A structured workflow offers less flexibility than chat but provides clearer actions, status and measurable outcomes.

---

## Decision 9: Store an audit history

### Problem

Financial review decisions must be traceable.

### Decision

The system will record:

- Original records
- Matching method
- Initial confidence score
- AI explanation
- User decision
- User note
- Decision timestamp

### Reasoning

An audit history supports transparency, troubleshooting and future evaluation.

### Trade-off

Audit storage adds database and privacy requirements.

The MVP will store synthetic records only.

---

## Decision 10: Treat confidence scores as product hypotheses

### Problem

A confidence score can appear scientifically precise even when it has not been properly calibrated.

### Decision

Initial confidence thresholds will be treated as hypotheses rather than established facts.

They will be adjusted based on labelled test results and user behaviour.

### Reasoning

A confidence score should correspond to observed accuracy, not merely an arbitrary number produced by the system.

### Validation

Confidence calibration will compare score ranges against actual match accuracy.

---

## Open decisions

The following questions will be resolved during implementation and testing:

- How should partial payments be represented?
- How should one payment covering multiple invoices be handled?
- Should users be able to change confidence thresholds?
- What information should appear in the default explanation?
- How should conflicting currency information be displayed?
- When should an unmatched record be escalated rather than rejected?
- How long should audit records be retained?
- Which LLM provides the best balance of quality, latency and cost?
