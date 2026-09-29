# AI Workflow Contracts

## Document Intelligence
Input: uploaded document.
Output: document type, date, persons, identifiers, references, page-level provenance.

## Record Completeness
Input: extracted cross-references + registered documents.
Output: present / referenced-but-unlocated / requires-confirmation items.

## Chronology
Input: event-bearing passages.
Output: events with date/time, description, source document/page, conflict flags.

## Evidence Matrix
Input: claims + evidence + sources.
Output: fact/evidence/source mappings; never upgrade allegations to facts.

## Legal Ingredient Mapping
Input: verified statute + case evidence.
Output: ingredient/evidence/source/status.

## Drafting
Input: structured case record + approved template.
Output: draft with provenance and warnings.

## Supervisory Audit
Input: draft + structured case record + source index.
Output: unsupported assertions, contradictions, missing references, legal/source issues.
