# LedgerLens AI — Backend

## Purpose

This folder will contain the backend services responsible for validating financial data, applying reconciliation logic and generating review recommendations.

## Planned technology

- Python
- FastAPI
- Pandas
- PostgreSQL
- Supabase
- OpenAI API
- Railway or Render

## Core responsibilities

The backend will:

- Accept invoice, payment and bank-transaction CSV files
- Validate required columns and data types
- Normalise dates, amounts, references and customer names
- Detect duplicate records
- Apply deterministic matching rules
- Calculate match confidence
- Send unresolved records for AI-assisted analysis
- Generate explanations and supporting evidence
- Store user review decisions
- Maintain an audit history
- Generate reconciliation exports
- Calculate evaluation metrics

## Matching sequence

1. Validate the uploaded file structure
2. Normalise input data
3. Match exact invoice references
4. Match exact payment references
5. Compare amount and currency
6. Apply date-proximity rules
7. Compare customer identifiers and names
8. Detect potential duplicate payments
9. Send ambiguous cases for AI-assisted analysis
10. Calculate confidence scores
11. Send uncertain cases for human review
12. Record the final decision in the audit history

## Planned API endpoints

### Health check

GET /health

Confirms that the backend service is available.

### Create reconciliation

POST /reconciliations

Creates a reconciliation session using uploaded invoice, payment and bank-transaction files.

### View reconciliation

GET /reconciliations/{session_id}

Returns the reconciliation status and summary.

### View matches

GET /reconciliations/{session_id}/matches

Returns confirmed, suggested, unmatched and duplicate records.

### Submit review decision

POST /matches/{match_id}/review

Records whether the user accepted, rejected or changed a recommendation.

### Export results

GET /reconciliations/{session_id}/export

Generates the completed reconciliation report and audit history.

## AI boundaries

The backend will not use an LLM for records that can be resolved reliably through deterministic rules.

Each AI-assisted recommendation must include:

- Confidence score
- Plain-language explanation
- Supporting fields
- Conflicting fields
- Source-record references

Low-confidence results will not be treated as confirmed.

## Security principles

- API keys will remain on the server.
- Credentials will not be committed to GitHub.
- The public MVP will use synthetic data only.
- Uploaded files will be validated before processing.
- Error messages will not expose sensitive configuration values.
- Audit records will distinguish system recommendations from user decisions.
