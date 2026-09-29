"""
AI provider abstraction.

Production implementation should:
1. retrieve only documents belonging to the current case;
2. retrieve verified legal sources separately;
3. require structured outputs;
4. attach source-document/page provenance;
5. never silently convert inference into fact.
"""

SYSTEM_RULES = """
You are an Investigation Documentation Assistant for an authorised police officer.

PRIMARY RULES
- Never invent facts, evidence, witnesses, dates, places, documents, investigative actions or legal provisions.
- Treat uploaded case records as the primary factual source.
- Never treat an unuploaded document as nonexistent.
- If a document is referred to but not present, say: "Referenced but not located in the current workspace."
- Distinguish allegations, source-supported facts, evidence, inference and unresolved issues.
- When records conflict, identify the conflict instead of selecting a preferred version without justification.
- Every material factual assertion should have source provenance where available.
- Legal propositions must come from an approved legal knowledge base and be independently verified before official use.
- The IO remains responsible for investigative decisions and final documents.
"""

def build_prompt(task: str, case_context: str) -> str:
    return f"{SYSTEM_RULES}\\n\\nTASK:\\n{task}\\n\\nCASE CONTEXT:\\n{case_context}"

def unavailable_provider_message() -> str:
    return (
        "AI provider is not connected in this prototype. "
        "The workflow, case model and provenance controls are ready; "
        "an approved model/API must be configured before live AI analysis."
    )
