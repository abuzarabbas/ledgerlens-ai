# LedgerLens AI — Frontend

## Purpose

This folder will contain the user-facing LedgerLens AI application.

The frontend will allow users to:

- Start a new reconciliation session
- Upload invoice, payment and bank-transaction CSV files
- Preview and validate uploaded records
- View confirmed, suggested and unmatched records
- Review uncertain AI-assisted recommendations
- Accept, reject or edit suggested matches
- Add review notes
- View reconciliation summaries
- Export reconciliation results and audit history

## Planned technology

- Next.js
- TypeScript
- Tailwind CSS
- Vercel

## Initial screens

1. Landing page
2. New reconciliation
3. File upload and validation
4. Reconciliation results
5. Review queue
6. Match details
7. Reconciliation summary
8. Export results

## Product principles

- Clearly distinguish rule-based and AI-assisted results
- Keep financially consequential decisions under human control
- Display confidence scores with supporting evidence
- Make uncertain records easy to review
- Avoid presenting AI suggestions as confirmed facts
