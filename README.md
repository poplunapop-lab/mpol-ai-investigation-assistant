# M-POL AI Investigation Documentation Assistant v0.1

A local-first prototype specification and starter implementation for a police investigation-documentation assistant.

## MVP
- Case creation
- Document registration/upload
- Case-document completeness/reference checking
- Chronology
- Evidence matrix
- Legal-ingredient mapping
- Investigation-gap review
- FR/chargesheet drafting workflow
- Supervisory audit
- Source/provenance tracking

## Important
This is a prototype, not a production police system. Do not upload live sensitive case material into this prototype until the department's security, legal, hosting, access-control and data-handling requirements have been approved.

## Run
Requires Python 3.11+.

```bash
pip install -r requirements.txt
streamlit run app/main.py
```

The prototype runs locally and stores demo metadata in SQLite. The AI provider is intentionally abstracted behind `app/ai_provider.py`; connect an approved model/API only after departmental approval.
