"""
M-POL AI Investigation Documentation Assistant
Fast/batched provider for the current prototype.

Design goal:
- IO uploads documents once.
- Large case files are processed in manageable batches.
- A cheaper/faster model reads document batches.
- The stronger model is used only for the final synthesis/drafting.
- The IO does not have to sequence documents.
"""

import os
import io
import tempfile
from pathlib import Path

import streamlit as st
from openai import OpenAI


# Current OpenAI models:
# Luna = cost-sensitive/high-volume document work
# Astra = stronger final synthesis
READ_MODEL = "gpt-6-luna"
FINAL_MODEL = "gpt-6-astra"

# Keep each PDF chunk reasonably sized. 10 pages is a practical
# compromise for the current 43-page test case.
PDF_PAGES_PER_BATCH = 10

SYSTEM_RULES = """
You are M-POL AI, an Investigation Documentation Assistant for an
authorised police officer.

NON-NEGOTIABLE RULES
1. Never invent facts, evidence, witnesses, dates, places, documents,
   investigative actions or legal provisions.
2. Use the supplied investigation record as the factual source.
3. Clearly distinguish allegation, established fact, evidence,
   inference and unresolved issue.
4. If records conflict, identify the conflict.
5. Never assume a document exists merely because another document
   refers to it.
6. If a document is referred to but not supplied, say:
   "Referenced but not located in the current workspace."
7. Preserve filename and page references whenever available.
8. Do not manufacture evidence or fill evidentiary gaps.
9. Legal provisions and case law must be independently verified before
   official use.
10. The IO remains responsible for the investigation and final report.
11. AI output is a draft for human verification.
12. The IO is not required to upload documents chronologically.
    Reconstruct chronology internally from document contents and dates.
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


def build_prompt(task, case_context):
    return f"""
TASK:
{task}

CASE CONTEXT:
{case_context}
"""


def _document_name(doc):
    if isinstance(doc, dict):
        return str(
            doc.get("filename")
            or doc.get("name")
            or "Unnamed document"
        )

    return str(
        getattr(doc, "name", "Unnamed document")
    )


def _document_category(doc):
    if isinstance(doc, dict):
        return str(
            doc.get("category")
            or "Uncategorised"
        )

    return "Uncategorised"


def _get_bytes(doc):
    """
    Recover bytes from the representations used by the current prototype.
    """
    name = _document_name(doc)
    suffix = Path(name).suffix.lower()

    if isinstance(doc, dict):

        for key in (
            "content_bytes",
            "bytes",
            "data",
            "content",
        ):
            value = doc.get(key)

            if isinstance(value, bytes):
                return value, suffix

        for key in (
            "uploaded_file",
            "file",
        ):
            obj = doc.get(key)

            if obj is not None and hasattr(obj, "getvalue"):
                return obj.getvalue(), suffix

        for key in (
            "filepath",
            "file_path",
            "path",
        ):
            value = doc.get(key)

            if value:
                path = Path(str(value))

                if path.exists() and path.is_file():
                    return path.read_bytes(), path.suffix.lower()

    else:

        if hasattr(doc, "getvalue"):

            try:
                return doc.getvalue(), suffix
            except Exception:
                pass

        for key in (
            "filepath",
            "file_path",
            "path",
        ):
            value = getattr(doc, key, None)

            if value:
                path = Path(str(value))

                if path.exists() and path.is_file():
                    return path.read_bytes(), path.suffix.lower()

    return None, suffix


def _upload_file(client, data, filename):
    """
    Upload one document/chunk to OpenAI.
    """
    with tempfile.NamedTemporaryFile(
        suffix=Path(filename).suffix,
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

        return uploaded.id

    finally:

        try:
            os.unlink(temp_path)
        except OSError:
            pass


def _split_pdf(data, filename):
    """
    Split only when necessary. The IO does not see this.
    """
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(
        io.BytesIO(data)
    )

    total_pages = len(reader.pages)

    if total_pages <= PDF_PAGES_PER_BATCH:
        return [
            (
                filename,
                data,
                1,
                total_pages,
            )
        ]

    chunks = []

    for start in range(
        0,
        total_pages,
        PDF_PAGES_PER_BATCH,
    ):

        end = min(
            start + PDF_PAGES_PER_BATCH,
            total_pages,
        )

        writer = PdfWriter()

        for page_index in range(
            start,
            end,
        ):
            writer.add_page(
                reader.pages[page_index]
            )

        buffer = io.BytesIO()

        writer.write(buffer)

        chunk_name = (
            f"{Path(filename).stem}_"
            f"pages_{start + 1}-{end}.pdf"
        )

        chunks.append(
            (
                chunk_name,
                buffer.getvalue(),
                start + 1,
                end,
            )
        )

    return chunks


def _prepare_chunks(documents):
    chunks = []

    for doc in documents or []:

        data, suffix = _get_bytes(doc)

        name = _document_name(doc)
        category = _document_category(doc)

        if data is None:

            chunks.append(
                {
                    "name": name,
                    "category": category,
                    "bytes": None,
                    "pages": "",
                    "note": (
                        "The document is registered in the "
                        "case record, but its actual file bytes "
                        "are not available to the AI."
                    ),
                }
            )

            continue

        if suffix == ".pdf":

            pdf_chunks = _split_pdf(
                data,
                name,
            )

            for (
                chunk_name,
                chunk_bytes,
                first_page,
                last_page,
            ) in pdf_chunks:

                chunks.append(
                    {
                        "name": chunk_name,
                        "category": category,
                        "bytes": chunk_bytes,
                        "pages": (
                            f"{first_page}-{last_page}"
                        ),
                        "note": "",
                    }
                )

        else:

            chunks.append(
                {
                    "name": name,
                    "category": category,
                    "bytes": data,
                    "pages": "",
                    "note": "",
                }
            )

    return chunks


def _read_one_batch(
    client,
    task,
    case_context,
    batch,
):

    content = [
        {
            "type": "input_text",
            "text": f"""
Read the supplied investigation documents carefully.

TASK:
{task}

CASE:
{case_context}

This is document-reading stage only.

Extract concise, source-grounded findings:
- allegations/material facts
- persons/witnesses
- dates/times/places
- investigative actions
- seizures/recoveries
- medical/expert findings
- electronic evidence
- contradictions
- important admissions/denials
- documents referred to but not supplied
- facts relevant to the selected task

Preserve filename and page references.

Do NOT draft a final FR or chargesheet at this stage.
Be concise. Do not repeat the same fact unnecessarily.
""",
        }
    ]

    uploaded_ids = []

    for item in batch:

        if item["bytes"] is None:

            content.append(
                {
                    "type": "input_text",
                    "text": (
                        f"REGISTERED DOCUMENT:\n"
                        f"{item['name']}\n"
                        f"Category: {item['category']}\n"
                        f"{item['note']}"
                    ),
                }
            )

            continue

        file_id = _upload_file(
            client,
            item["bytes"],
            item["name"],
        )

        uploaded_ids.append(
            file_id
        )

        content.append(
            {
                "type": "input_file",
                "file_id": file_id,
            }
        )

    try:

        response = client.responses.create(
            model=READ_MODEL,
            instructions=SYSTEM_RULES,
            input=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
            max_output_tokens=5000,
        )

        return response.output_text

    finally:

        # Delete temporary OpenAI files after processing.
        for file_id in uploaded_ids:

            try:
                client.files.delete(
                    file_id
                )
            except Exception:
                pass


def _final_synthesis(
    client,
    task,
    case_context,
    findings,
):

    combined = "\n\n".join(
        f"===== DOCUMENT FINDINGS {i + 1} =====\n{result}"
        for i, result in enumerate(findings)
    )

    prompt = f"""
You are now performing the FINAL investigation-level task.

TASK:
{task}

CASE CONTEXT:
{case_context}

M-POL has already read the source documents in batches.
The verified findings from those readings are below:

{combined}

Using ONLY those findings:

1. Reconstruct the material chronology internally.
2. Identify the material allegations.
3. Identify what is actually supported by evidence.
4. Identify contradictions or inconsistencies.
5. Identify important investigation gaps.
6. Identify documents referred to but not supplied.
7. Distinguish facts from inference.
8. Preserve source filenames/page references where available.

If the task is "Analyse Investigation", provide a structured
investigation analysis.

If the task is "Draft Final Report", prepare a professional draft
based only on established facts and clearly identify anything that
requires IO verification.

If the task is "Draft Chargesheet", prepare a structured draft based
only on evidence actually reflected in the findings. Do not invent
missing ingredients, witnesses or evidence.

If the task is "Improve Existing Police Report", improve its legal and
professional drafting without changing substantive facts.

IMPORTANT:
Do not make the case stronger by inventing facts.
If evidence is insufficient, say so.
Do not silently resolve contradictions.
This is a draft for review by the Investigating Officer.
"""

    response = client.responses.create(
        model=FINAL_MODEL,
        instructions=SYSTEM_RULES,
        input=prompt,
        max_output_tokens=16000,
    )

    return response.output_text


def run_ai(
    task,
    case_context,
    documents=None,
):

    client = get_openai_client()

    if not documents:

        response = client.responses.create(
            model=FINAL_MODEL,
            instructions=SYSTEM_RULES,
            input=build_prompt(
                task,
                case_context,
            ),
            max_output_tokens=12000,
        )

        return response.output_text

    chunks = _prepare_chunks(
        documents
    )

    if not chunks:
        return (
            "No readable investigation documents were supplied."
        )

    # Keep batches simple and predictable. Each PDF chunk is already
    # capped at 10 pages, so the same case can be processed in stages.
    batches = [
        chunks[i:i + 2]
        for i in range(
            0,
            len(chunks),
            2,
        )
    ]

    findings = []

    progress = st.progress(
        0
    )

    status = st.empty()

    total = len(batches)

    for index, batch in enumerate(
        batches,
        start=1,
    ):

        status.write(
            f"Reading documents: "
            f"{index} of {total} batches..."
        )

        result = _read_one_batch(
            client,
            task,
            case_context,
            batch,
        )

        findings.append(
            result
        )

        progress.progress(
            index / total
        )

    status.write(
        "Preparing final investigation analysis..."
    )

    final_result = _final_synthesis(
        client,
        task,
        case_context,
        findings,
    )

    progress.empty()
    status.empty()

    return final_result


def unavailable_provider_message():
    return (
        "AI provider is not connected. "
        "Check the OPENAI_API_KEY Streamlit Secret."
    )
