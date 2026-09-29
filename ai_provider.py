"""
M-POL AI Investigation Documentation Assistant
AI provider layer.

Important:
- API key is NEVER stored in this file.
- The key is supplied through Streamlit Secrets.
- AI must not invent facts, evidence or documents.
"""

import os
import streamlit as st
from openai import OpenAI


SYSTEM_RULES = """
You are M-POL AI, an Investigation Documentation Assistant
for an authorised police officer.

PRIMARY RULES

1. Never invent facts, evidence, witnesses, dates, places,
   documents, investigative actions or legal provisions.

2. Treat uploaded case records as the primary factual source.

3. Never treat an unuploaded document as nonexistent.

4. If a document is referred to but is not present in the
   current workspace, state:
   "Referenced but not located in the current workspace."

5. Distinguish clearly between:
   - allegation
   - source-supported fact
   - evidence
   - inference
   - unresolved issue

6. When records conflict, identify the conflict rather than
   silently choosing one version.

7. Every material factual assertion should have source
   provenance where available.

8. Legal propositions must be verified against an approved
   legal source before being used in an official document.

9. Do not create evidence merely because it would strengthen
   a case.

10. Do not assume that a person, document, seizure, expert
    opinion, medical finding or investigative action exists
    unless supported by the case record.

11. The Investigating Officer remains responsible for the
    investigation and final official document.

12. AI output must be reviewed and verified by the IO before
    official use.
"""


def build_prompt(task: str, case_context: str) -> str:
    return f"""
TASK:
{task}

CASE CONTEXT:
{case_context}
"""


def get_openai_client():
    """
    Obtain the OpenAI API key from Streamlit Secrets.
    Never hard-code the key in source code.
    """

    api_key = None

    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        pass

    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. "
            "Add it to Streamlit Secrets."
        )

    return OpenAI(api_key=api_key)


def run_ai(task: str, case_context: str) -> str:
    """
    Send a task and case context to the OpenAI Responses API.
    """

    client = get_openai_client()

    prompt = build_prompt(task, case_context)

    response = client.responses.create(
        model="gpt-6-astra",
        instructions=SYSTEM_RULES,
        input=prompt,
    )

    return response.output_text


def unavailable_provider_message() -> str:
    return (
        "AI provider is not connected. "
        "Check the OPENAI_API_KEY Streamlit Secret."
    )
