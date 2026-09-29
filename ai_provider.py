import os
import time
from pathlib import Path

import streamlit as st
from openai import OpenAI, RateLimitError

# Current API model IDs verified against OpenAI's current documentation.
# Astra is used for both retrieval and drafting here to keep the workflow
# simple and avoid unnecessary model switching.
MODEL = "gpt-6-astra"

SYSTEM_RULES = """
You are M-POL AI, an Investigation Documentation Assistant for an
authorised police officer.

CORE RULES:
1. Never invent facts, evidence, witnesses, dates, places, documents,
   investigative actions or legal provisions.
2. The uploaded case records are the primary factual source.
3. A filename or category alone is NOT evidence of document contents.
4. Distinguish allegation, source-supported fact, evidence, inference,
   and unresolved issue.
5. If records conflict, identify the conflict; do not silently choose.
6. If a referenced document is not uploaded, say:
   "Referenced but not located in the current workspace."
7. Preserve filenames and page/section references whenever available.
8. Reconstruct chronology internally. The IO does not need to upload
   documents chronologically.
9. Never manufacture missing evidence or strengthen a case by guesswork.
10. Legal provisions and case law must be independently verified before
    official use. Never fabricate section numbers or quotations.
11. Preserve the underlying facts when improving drafting.
12. The Investigating Officer remains responsible for the investigation
    and final official document.
13. AI output is a draft and must be reviewed by the IO before official use.
"""

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


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


def _is_image_document(document):
    filename = (document.get("filename") or "").lower()
    return filename.endswith(IMAGE_EXTENSIONS)


def _wait_for_vector_store_file(client, vector_store_id, file_id):
    # Poll only while a newly uploaded retrieval document is being indexed.
    for _ in range(90):
        item = client.vector_stores.files.retrieve(
            vector_store_id=vector_store_id,
            file_id=file_id,
        )

        status = getattr(item, "status", None)

        if status == "completed":
            return

        if status in ("failed", "cancelled"):
            last_error = getattr(item, "last_error", None)
            raise RuntimeError(
                f"OpenAI File Search indexing failed for file {file_id}: "
                f"{status}. {last_error or ''}"
            )

        time.sleep(2)

    raise TimeoutError(
        "OpenAI File Search indexing did not finish within 3 minutes."
    )


def _get_existing_vector_store_id(case_id):
    from database import get_case_vector_store_id
    return get_case_vector_store_id(case_id)


def _create_vector_store(client, case_id):
    return client.vector_stores.create(
        name=f"M-POL Case {case_id}"
    ).id


def _upload_image(client, document, data):
    """
    Images are uploaded for visual input, NOT for File Search retrieval.
    OpenAI's vision documentation explicitly supports JPEG/JPG/PNG etc.
    """
    filename = Path(document["filename"]).name

    lower = filename.lower()
    mime = "image/jpeg" if lower.endswith((".jpg", ".jpeg")) else "image/png"

    uploaded = client.files.create(
        file=(filename, data, mime),
        purpose="vision",
    )
    return uploaded.id


def _upload_retrieval_document(client, document, data):
    filename = Path(document["filename"]).name

    # File Search supported formats include PDF, DOCX and TXT.
    # Use the original filename so File Search/source references retain the
    # actual case-document name rather than a temporary filesystem name.
    uploaded = client.files.create(
        file=(filename, data),
        purpose="assistants",
    )
    return uploaded.id


def _ensure_documents_indexed(client, case_id, documents):
    """
    Returns:
        vector_store_id: None if the case has no retrieval-supported files
        image_file_ids: images to send directly to the vision model
        indexed_count: retrieval files newly/previously indexed
    """
    from database import set_openai_document_ids

    vector_store_id = _get_existing_vector_store_id(case_id)
    image_file_ids = []
    retrieval_documents = []

    for document in documents:
        if _is_image_document(document):
            image_file_ids.append(document.get("openai_file_id"))
        else:
            retrieval_documents.append(document)

    # Remove empty IDs; these documents need uploading below.
    image_file_ids = [x for x in image_file_ids if x]

    # Only create a vector store if there is at least one retrieval document.
    if retrieval_documents and not vector_store_id:
        vector_store_id = _create_vector_store(client, case_id)

    indexed_count = 0

    for document in retrieval_documents:
        existing_file_id = document.get("openai_file_id")

        if existing_file_id:
            indexed_count += 1
            continue

        data = _read_file_bytes(document)

        if not data:
            raise RuntimeError(
                f"The actual file for '{document['filename']}' is not "
                "available in the current workspace. Please upload that "
                "existing file again; no rescanning is required."
            )

        uploaded_id = _upload_retrieval_document(
            client,
            document,
            data,
        )

        client.vector_stores.files.create(
            vector_store_id=vector_store_id,
            file_id=uploaded_id,
        )

        _wait_for_vector_store_file(
            client,
            vector_store_id,
            uploaded_id,
        )

        set_openai_document_ids(
            document["id"],
            uploaded_id,
            vector_store_id,
        )

        indexed_count += 1

    for document in documents:
        if not _is_image_document(document):
            continue

        if document.get("openai_file_id"):
            continue

        data = _read_file_bytes(document)

        if not data:
            raise RuntimeError(
                f"The actual photograph '{document['filename']}' is not "
                "available in the current workspace. Please upload that "
                "existing photograph again."
            )

        image_id = _upload_image(client, document, data)

        # No vector-store call here. This is the deliberate fix for the
        # JPEG/JPG File Search error.
        set_openai_document_ids(
            document["id"],
            image_id,
            None,
        )

        image_file_ids.append(image_id)

    return vector_store_id, image_file_ids, indexed_count


def _build_prompt(task, case_context):
    if task == "Analyse Investigation":
        task_instruction = """
Analyse the investigation record and provide:
1. Brief case synopsis
2. Material allegations
3. Reconstructed chronology
4. Persons/witnesses and roles
5. Documentary/material evidence
6. Medical/FSL/expert evidence
7. Electronic evidence
8. Evidence supporting each material allegation
9. Contradictions/inconsistencies
10. Investigation gaps
11. Referenced but unavailable documents
12. Legal issues requiring verification
13. Specific further investigation points

Every material factual statement must be grounded in the records.
"""

    elif task == "Draft Final Report":
        task_instruction = """
Prepare a DRAFT Final Report based only on the investigation records.

First determine what is established and what remains unestablished.
Then draft it in professional police/legal style.

Do not invent facts, witnesses, evidence or investigative steps.
Do not convert allegations into established facts.
Flag insufficiency for IO verification.
Include a Verification Notes / Evidence Gaps section.
"""

    elif task == "Draft Chargesheet":
        task_instruction = """
Prepare a DRAFT chargesheet based only on the investigation records.

Map every proposed offence and every material legal ingredient against
actual evidence in the records. Identify the supporting witness/document
and page/section where available.

Do not invent evidence, witnesses, dates, expert opinions or facts.
Flag unsupported ingredients rather than filling gaps.
Include Verification Notes / Evidence Gaps.
"""

    else:
        task_instruction = """
Improve the existing police report/documentation found in the records.

Improve clarity, structure and professional/legal drafting without
changing substantive facts. Do not silently correct contradictions.
Do not add facts or conclusions absent from the record.
"""

    return f"""
TASK:
{task}

CASE CONTEXT:
{case_context}

TASK-SPECIFIC INSTRUCTION:
{task_instruction}

The case documents are authoritative for factual assertions.
Search the case workspace before answering.
"""


def run_ai(task, case_context, documents):
    if not documents:
        raise ValueError("No investigation documents are available.")

    client = get_client()
    case_id = documents[0]["case_id"]

    progress = st.progress(0)
    status = st.empty()

    try:
        status.write("Preparing case documents...")

        vector_store_id, image_file_ids, indexed_count = (
            _ensure_documents_indexed(
                client,
                case_id,
                documents,
            )
        )

        progress.progress(0.35)

        prompt = _build_prompt(task, case_context)

        input_content = [
            {
                "type": "input_text",
                "text": prompt,
            }
        ]

        # Direct visual inputs. This is supported by the Responses API.
        for image_file_id in image_file_ids:
            input_content.append(
                {
                    "type": "input_image",
                    "file_id": image_file_id,
                    "detail": "auto",
                }
            )

        tools = []

        if vector_store_id:
            tools.append(
                {
                    "type": "file_search",
                    "vector_store_ids": [vector_store_id],
                    "max_num_results": 12,
                }
            )

        status.write("M-POL AI is analysing the investigation record...")

        response_kwargs = {
            "model": MODEL,
            "instructions": SYSTEM_RULES,
            "input": [
                {
                    "role": "user",
                    "content": input_content,
                }
            ],
            "max_output_tokens": 20000,
        }

        if tools:
            response_kwargs["tools"] = tools

        try:
            response = client.responses.create(**response_kwargs)
        except RateLimitError as error:
            # A very large retrieval result can exceed the organisation's TPM
            # limit even though the vector store itself is valid. Retry once
            # with a smaller retrieval set instead of failing the workflow.
            error_text = str(error)
            if "Request too large" not in error_text and "tokens per min" not in error_text:
                raise

            status.write("Large retrieval detected; retrying with a smaller evidence set...")
            response_kwargs["tools"] = [
                {
                    "type": "file_search",
                    "vector_store_ids": [vector_store_id],
                    "max_num_results": 6,
                }
            ]
            response = client.responses.create(**response_kwargs)

        progress.progress(1.0)
        status.write("M-POL AI completed the analysis.")
        time.sleep(0.4)

        return response.output_text

    finally:
        progress.empty()
        status.empty()


def unavailable_provider_message():
    return (
        "AI provider is not connected. "
        "Check the OPENAI_API_KEY Streamlit Secret."
    )
