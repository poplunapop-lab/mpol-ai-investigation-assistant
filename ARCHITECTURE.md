# Production Architecture

## Recommended logical layers

1. Web UI
2. Authentication/RBAC
3. Case management API
4. Secure object/document storage
5. Document extraction/OCR
6. Case-specific retrieval/index
7. Verified legal knowledge base
8. AI orchestration layer
9. Structured-output validators
10. Provenance/citation service
11. Document generation service
12. Immutable audit logging

## Separation

- Case knowledge stores must be isolated by case ID and user permissions.
- Legal knowledge must be separate from case evidence.
- Departmental templates/SOPs must be a separate knowledge collection.
- AI must never be the system of record.
- Final official records remain departmental records.

## Production security

Use department-approved hosting, identity provider, encryption, secrets management, backup, retention and logging. Obtain departmental/legal/IT approval before connecting live case data.
