# LedgerLens AI — Initial Architecture

## Frontend

**Technology**

- Next.js
- TypeScript
- Tailwind CSS
- Vercel

**Responsibilities**

- Upload financial CSV files
- Preview uploaded data
- Display validation errors
- Show reconciliation results
- Present uncertain matches for review
- Record user decisions
- Export reconciliation reports

## Backend

**Technology**

- Python
- FastAPI
- Pandas
- Railway or Render

**Responsibilities**

- Validate uploaded CSV files
- Normalise financial records
- Apply deterministic matching rules
- Calculate confidence scores
- Send unresolved cases for AI analysis
- Store review decisions
- Generate export files
- Run evaluation tests

## Database

**Technology**

- Supabase PostgreSQL

**Data stored**

- Reconciliation sessions
- Uploaded record metadata
- Match recommendations
- Confidence scores
- User review decisions
- Audit history
- Processing errors

## AI provider

The initial version will use an LLM API for ambiguous records that cannot be resolved through deterministic matching.

AI will not be used when a reliable rule-based match is available.

## Matching sequence

1. Validate uploaded files
2. Normalise dates, amounts, references and customer names
3. Match exact invoice and payment references
4. Match amount and currency
5. Apply date-proximity rules
6. Apply customer-name similarity
7. Analyse unresolved descriptions using AI
8. Calculate confidence score
9. Send uncertain cases to human review
10. Record the final decision in the audit history

## Trust model

The system distinguishes between:

- Rule-confirmed matches
- AI-suggested matches
- Human-approved matches
- Rejected matches
- Unresolved records

Low-confidence AI recommendations must be reviewed by a user before they are treated as confirmed.

## Initial deployment model

- Frontend: Vercel
- Backend: Railway or Render
- Database: Supabase
- Source control: GitHub
- AI access: Server-side API only

API keys and credentials will never be committed to the repository.
