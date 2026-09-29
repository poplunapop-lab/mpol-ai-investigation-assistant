"""
M-POL AI Investigation Documentation Assistant
AI provider layer.

This version sends the actual uploaded case documents to the model.
The API key is supplied through Streamlit Secrets and is never stored here.
"""

import os
from typing import Iterable

import streamlit as st
from openai import OpenAI


SYSTEM_RULES = """
You are M-POL AI, an Investigation Documentation Assistant for an authorised
police officer.

CORE RULES

1. Never invent facts, evidence, witnesses, dates, places, documents,
   investigative actions or legal provisions.

2. The uploaded case records are the primary factual source. READ THE
   ACTUAL CONTENT of the supplied files before answering.

3. A filename or document category alone is NOT evidence of the contents of
   that document.

4. Distinguish clearly between allegation, source-supported fact, evidence,
   inference and unresolved issue.

5. If records conflict, identify the conflict and cite the relevant files.
   Do not silently choose one version.

6. If a document is referred to in an uploaded record but is not among the
   uploaded documents, say exactly:
   "Referenced but not located in the current workspace."
   Do not say that the document does not exist.

7. Reconstruct chronology internally from dates, times and events found in
   the records. The IO is NOT required to upload documents chronologically.
   Never invent a date merely to complete a chronology.

8. For every important factual assertion, give a useful source reference such
   as the document filename and page/section when that information is
   available from the supplied file.

9. Do not create evidence merely because it would strengthen a case.

10. Do not assume that a person, document, seizure, expert opinion, medical
    finding or investigative action exists unless supported by the records.

11. Legal propositions must be checked against an approved legal source
    before they are used in an official police document. Do not fabricate
    case law, section numbers or quotations.

12. When asked to improve drafting, preserve the underlying facts. Improve
    clarity, structure and legal drafting without adding facts.

13. The Investigating Officer remains responsible for the investigation and
    final official document. AI output is a draft for human verification.
"""


def get_openai_client():
    api_key = None

    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        pass

    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. Add it to Streamlit Secrets."
        )

    return OpenAI(api_key=api_key)


def _upload_document(client, document):
    """Upload one stored case document to OpenAI and return its file id."""
    data = document["file_data"]
    filename = document["filename"]
    mime_type = document["mime_type"] or "application/octet-stream"

    if not data:
        raise ValueError(
            f"The file contents for '{filename}' are not stored. "
            "Please delete and re-upload this document."
        )

    uploaded = client.files.create(
        file=(filename, data, mime_type),
        purpose="user_data",
    )
    return uploaded.id


def _document_content_type(document, file_id):
    filename = document["filename"].lower()
    mime_type = (document["mime_type"] or "").lower()

    image_exts = (".jpg", ".jpeg", ".png", ".webp", ".gif")
    if mime_type.startswith("image/") or filename.endswith(image_exts):
        return {"type": "input_image", "file_id": file_id}

    return {"type": "input_file", "file_id": file_id}


def run_ai(task: str, case_context: str, documents: Iterable) -> str:
    """
    Analyse the actual uploaded case files together with the case metadata.
    """
    client = get_openai_client()

    document_list = list(documents)
    file_ids = []
    content = []

    # Give the model the case metadata first.
    content.append(
        {
            "type": "input_text",
            "text": f"""
TASK:
{task}

CASE INFORMATION:
{case_context}

IMPORTANT:
The following files are the actual investigation records available in the
current workspace. Read their contents before making factual assertions.
""",
        }
    )

    # Upload and attach every document whose binary contents are available.
    for document in document_list:
        if not document["file_data"]:
            # Old prototype records have metadata but no file bytes.
            content.append(
                {
                    "type": "input_text",
                    "text": (
                        f"DOCUMENT REGISTERED BUT CONTENT NOT AVAILABLE: "
                        f"{document['filename']} | Category: {document['category']}"
                    ),
                }
            )
            continue

        file_id = _upload_document(client, document)
        file_ids.append(file_id)
        content.append(
            {
                "type": "input_text",
                "text": (
                    f"DOCUMENT: {document['filename']}\n"
                    f"CATEGORY: {document['category']}\n"
                    f"DOCUMENT ID: {document['id']}"
                ),
            }
        )
        content.append(_document_content_type(document, file_id))

    if not document_list:
        content.append(
            {
                "type": "input_text",
                "text": "No investigation documents have been uploaded.",
            }
        )

    response = client.responses.create(
        model="gpt-6-astra",
        instructions=SYSTEM_RULES,
        input=[
            {
                "role": "user",
                "content": content,
            }
        ],
    )

    return response.output_text


def unavailable_provider_message() -> str:
    return (
        "AI provider is not connected. Check the OPENAI_API_KEY Streamlit Secret."
    )
