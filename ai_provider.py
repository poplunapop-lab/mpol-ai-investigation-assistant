import os
import time
from pathlib import Path

import streamlit as st
from openai import OpenAI

# Fast model for retrieval/synthesis of ordinary investigation material.
# Stronger model is reserved for final legal/document drafting.
READ_MODEL = "gpt-5.6-luna"
FINAL_MODEL = "gpt-5.6-sol"

SYSTEM_RULES = """
You are M-POL AI, an Investigation Documentation Assistant for an
authorised police officer.

RULES:
1. Never invent facts, evidence, witnesses, dates, places, documents,
   investigative actions or legal provisions.
2. Use only information supported by the supplied case records.
3. Distinguish allegation, source-supported fact, evidence, inference
   and unresolved issue.
4. Identify contradictions instead of silently resolving them.
5. If a document is referred to but not available in the case record,
   say: "Referenced but not located in the current workspace."
6. Preserve filename and page references whenever available.
7. Never manufacture missing evidence or make a case stronger by guesswork.
8. Reconstruct chronology internally. The IO does not need to upload
   documents chronologically.
9. The IO remains responsible for the investigation and final official
   document.
10. AI output is a draft and must be verified before official use.
"""


def get_client():
    api_key = None

    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        pass

    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured in Streamlit Secrets."
        )

    return OpenAI(api_key=api_key)


def _read_file_bytes(document):
    file_path = document.get("file_path")

    if not file_path:
        return None

    path = Path(file_path)

    if not path.exists():
        return None

    return path.read_bytes()


def _wait_for_vector_store_file(client, vector_store_id, file_id):
    """
    Wait until OpenAI has processed the file. This happens once per
    uploaded document, not once per AI question.
    """
    for _ in range(60):

        item = client.vector_stores.files.retrieve(
            vector_store_id=vector_store_id,
            file_id=file_id,
        )

        status = getattr(item, "status", None)

        if status == "completed":
            return

        if status in ("failed", "cancelled"):
            raise RuntimeError(
                f"OpenAI file indexing failed: {status}"
            )

        time.sleep(2)

    raise TimeoutError(
        "OpenAI file indexing took too long."
    )


def _get_or_create_vector_store(client, case_id):
    from database import get_case_vector_store_id

    existing = get_case_vector_store_id(case_id)

    if existing:
        return existing

    vector_store = client.vector_stores.create(
        name=f"M-POL Case {case_id}"
    )

    return vector_store.id


def _ensure_documents_indexed(client, case_id, documents):
    from database import set_openai_document_ids

    vector_store_id = _get_or_create_vector_store(
        client,
        case_id,
    )

    indexed_count = 0

    for document in documents:

        # Already indexed.
        if document.get("openai_file_id"):

            indexed_count += 1
            continue

        data = _read_file_bytes(document)

        if not data:

            raise RuntimeError(
                f"The actual file for '{document['filename']}' is not "
                f"stored in the current workspace. This document must be "
                f"uploaded once more. No re-scanning is required."
            )

        import tempfile

        suffix = Path(
            document["filename"]
        ).suffix

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as tmp:

            tmp.write(data)
            temp_path = tmp.name

        try:

            with open(temp_path, "rb") as file_handle:

                uploaded = client.files.create(
                    file=file_handle,
                    purpose="user_data",
                )

            client.vector_stores.files.create(
                vector_store_id=vector_store_id,
                file_id=uploaded.id,
            )

            _wait_for_vector_store_file(
                client,
                vector_store_id,
                uploaded.id,
            )

            set_openai_document_ids(
                document["id"],
                uploaded.id,
                vector_store_id,
            )

            indexed_count += 1

        finally:

            try:
                os.unlink(temp_path)
            except OSError:
                pass

    return vector_store_id, indexed_count


def run_ai(
    task,
    case_context,
    documents,
):

    if not documents:
        raise ValueError(
            "No investigation documents are available."
        )

    client = get_client()

    case_id = documents[0]["case_id"]

    progress = st.progress(0)
    status = st.empty()

    status.write(
        "Preparing the case documents for M-POL..."
    )

    vector_store_id, indexed_count = _ensure_documents_indexed(
        client,
        case_id,
        documents,
    )

    progress.progress(0.35)

    status.write(
        "Searching the investigation record..."
    )

    if task == "Analyse Investigation":

        prompt = f"""
Analyse the investigation record in the case workspace.

CASE CONTEXT:
{case_context}

Provide:
1. Brief case synopsis
2. Material allegations
3. Chronology reconstructed from the records
4. Persons/witnesses and their material roles
5. Documentary/material evidence
6. Medical/FSL/expert evidence
7. Electronic evidence
8. Evidence supporting each material allegation
9. Contradictions/inconsistencies
10. Investigation gaps
11. Documents referred to but not located
12. Legal issues requiring verification
13. Specific further investigation points, if any

Every important factual statement must be grounded in the retrieved
case documents. Do not invent anything.
"""

    elif task == "Draft Final Report":

        prompt = f"""
Prepare a DRAFT Final Report based only on the investigation records.

CASE CONTEXT:
{case_context}

First determine from the records what is established and what is not.
Then draft the report in a professional police/legal style.

Do not invent facts, witnesses, evidence or investigative steps.
Do not convert allegations into established facts.
Where the record is insufficient, flag the issue for IO verification.

Preserve useful source references in an accompanying "Verification
Notes" section.
"""

    elif task == "Draft Chargesheet":

        prompt = f"""
Prepare a DRAFT chargesheet based only on the investigation records.

CASE CONTEXT:
{case_context}

Analyse the proposed offences and their legal ingredients against the
actual evidence in the records.

For every material ingredient, identify supporting evidence and source
document/page where available.

Then prepare a structured draft chargesheet.

Do not invent evidence, witnesses, expert opinions, dates or facts.
Flag unsupported ingredients instead of filling the gap.

Include a "Verification Notes / Evidence Gaps" section for the IO.
"""

    else:

        prompt = f"""
Improve the existing police report/documentation found in the case
workspace.

CASE CONTEXT:
{case_context}

Improve clarity, structure, legal drafting quality and professional
language without changing substantive facts.

Do not introduce facts or conclusions that are absent from the record.
Clearly flag any apparent factual inconsistency instead of silently
correcting it.
"""

    response = client.responses.create(
        model=FINAL_MODEL,
        instructions=SYSTEM_RULES,
        tools=[
            {
                "type": "file_search",
                "vector_store_ids": [vector_store_id],
            }
        ],
        include=[
            "file_search_call.results",
        ],
        input=prompt,
        max_output_tokens=20000,
    )

    progress.progress(1.0)

    status.write(
        "M-POL completed the analysis."
    )

    time.sleep(0.5)

    progress.empty()
    status.empty()

    return response.output_text


def unavailable_provider_message():
    return (
        "AI provider is not connected. "
        "Check the OPENAI_API_KEY Streamlit Secret."
    )
