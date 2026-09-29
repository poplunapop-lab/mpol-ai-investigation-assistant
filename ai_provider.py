"""
M-POL AI Investigation Documentation Assistant
Batching-aware AI provider.

Keeps the existing M-POL workflow while preventing very large
investigation files from being sent in one request.
"""

import os
import io
import tempfile
from pathlib import Path

import streamlit as st
from openai import OpenAI


MODEL = "gpt-6-astra"

# Keep individual requests comfortably below the 500k TPM limit
# encountered in the current prototype.
TARGET_BATCH_BYTES = 220_000

SYSTEM_RULES = """
You are M-POL AI, an Investigation Documentation Assistant for an
authorised police officer.

CORE RULES
1. Never invent facts, evidence, witnesses, dates, places, documents,
   investigative actions or legal provisions.
2. Treat supplied case records as the primary factual source.
3. Distinguish allegation, source-supported fact, evidence, inference,
   and unresolved issue.
4. If records conflict, identify the conflict; do not silently choose.
5. Do not assume a document exists merely because another document
   mentions it.
6. If a document is referred to but is not supplied, say:
   "Referenced but not located in the current workspace."
7. Preserve source provenance whenever possible: filename and page.
8. Do not manufacture missing evidence to make a case stronger.
9. Legal propositions must be verified against approved legal sources
   before official use.
10. The IO remains responsible for the investigation and final document.
11. AI output is a draft and must be reviewed by the IO.
12. When analysing multiple documents, reconstruct chronology internally.
    The IO is NOT required to upload documents chronologically.
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


def build_prompt(task: str, case_context: str) -> str:
    return f"""
TASK:
{task}

CASE CONTEXT:
{case_context}
"""


def _document_name(doc):
    if isinstance(doc, dict):
        return str(doc.get("filename") or doc.get("name") or "Unnamed document")
    return str(getattr(doc, "name", "Unnamed document"))


def _document_category(doc):
    if isinstance(doc, dict):
        return str(doc.get("category") or "Uncategorised")
    return "Uncategorised"


def _get_bytes(doc):
    """Accept common document representations used by the prototype."""
    suffix = Path(_document_name(doc)).suffix.lower()

    if isinstance(doc, dict):
        for key in ("content_bytes", "bytes", "data", "content"):
            value = doc.get(key)
            if isinstance(value, bytes):
                return value, suffix

        for key in ("uploaded_file", "file"):
            obj = doc.get(key)
            if obj is not None and hasattr(obj, "getvalue"):
                return obj.getvalue(), suffix

        for key in ("filepath", "file_path", "path"):
            value = doc.get(key)
            if value:
                p = Path(str(value))
                if p.exists() and p.is_file():
                    return p.read_bytes(), p.suffix.lower()

    else:
        if hasattr(doc, "getvalue"):
            try:
                return doc.getvalue(), suffix
            except Exception:
                pass

        for key in ("filepath", "file_path", "path"):
            value = getattr(doc, key, None)
            if value:
                p = Path(str(value))
                if p.exists() and p.is_file():
                    return p.read_bytes(), p.suffix.lower()

    return None, suffix


def _upload_bytes(client, data: bytes, filename: str):
    """Upload a document to OpenAI for use as a model input."""
    with tempfile.NamedTemporaryFile(
        suffix=Path(filename).suffix,
        delete=False,
    ) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as fh:
            uploaded = client.files.create(
                file=fh,
                purpose="user_data",
            )
        return uploaded.id
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _split_pdf_bytes(pdf_bytes: bytes, filename: str, max_pages=8):
    """
    Split large PDFs into page groups. This prevents a large scanned PDF
    from becoming one enormous model request.
    """
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(pdf_bytes))

    if len(reader.pages) <= max_pages:
        return [(filename, pdf_bytes)]

    chunks = []

    for start in range(0, len(reader.pages), max_pages):
        writer = PdfWriter()
        end = min(start + max_pages, len(reader.pages))

        for page_no in range(start, end):
            writer.add_page(reader.pages[page_no])

        buffer = io.BytesIO()
        writer.write(buffer)

        chunk_name = (
            f"{Path(filename).stem}_pages_{start + 1}-{end}.pdf"
        )
        chunks.append((chunk_name, buffer.getvalue()))

    return chunks


def _make_document_chunks(documents):
    chunks = []

    for doc in documents or []:
        data, suffix = _get_bytes(doc)
        name = _document_name(doc)
        category = _document_category(doc)

        if data is None:
            chunks.append({
                "name": name,
                "category": category,
                "bytes": None,
                "note": (
                    "The application has the document register entry "
                    "but not the document bytes."
                ),
            })
            continue

        if suffix == ".pdf":
            pdf_chunks = _split_pdf_bytes(data, name, max_pages=8)

            for chunk_name, chunk_bytes in pdf_chunks:
                chunks.append({
                    "name": chunk_name,
                    "category": category,
                    "bytes": chunk_bytes,
                    "note": "",
                })
        else:
            chunks.append({
                "name": name,
                "category": category,
                "bytes": data,
                "note": "",
            })

    return chunks


def _analyse_batch(client, task, case_context, batch):
    content = [{
        "type": "input_text",
        "text": f"""
You are analysing one batch of investigation documents.

TASK:
{task}

CASE CONTEXT:
{case_context}

Read ALL supplied documents carefully.

For this batch, extract only information actually supported by the
documents. Preserve filename and page references where possible.

Return:
1. Material facts
2. Persons/witnesses
3. Dates/times/places
4. Investigative actions
5. Seizures/recoveries
6. Medical/expert findings
7. Electronic evidence
8. Contradictions or inconsistencies
9. Documents referred to but not supplied
10. Other facts relevant to the requested task

Do not draft a final FR/chargesheet yet.
"""
    }]

    file_ids = []

    for item in batch:
        if item["bytes"] is None:
            content.append({
                "type": "input_text",
                "text": (
                    f"DOCUMENT REGISTER ENTRY:\n"
                    f"{item['name']} | {item['category']}\n"
                    f"{item['note']}\n"
                ),
            })
            continue

        file_id = _upload_bytes(client, item["bytes"], item["name"])
        file_ids.append(file_id)

        content.append({
            "type": "input_file",
            "file_id": file_id,
        })

    try:
        response = client.responses.create(
            model=MODEL,
            instructions=SYSTEM_RULES,
            input=[{"role": "user", "content": content}],
            max_output_tokens=12000,
        )
        return response.output_text
    finally:
        for file_id in file_ids:
            try:
                client.files.delete(file_id)
            except Exception:
                pass


def _final_analysis(client, task, case_context, batch_results):
    combined = "\n\n".join(
        f"===== BATCH {i + 1} =====\n{result}"
        for i, result in enumerate(batch_results)
    )

    prompt = f"""
TASK:
{task}

CASE CONTEXT:
{case_context}

The following are structured findings produced by M-POL after reading
the investigation documents in batches:

{combined}

Now perform the requested investigation-level task.

IMPORTANT:
- Use only facts supported by the supplied findings.
- Do not invent facts.
- Identify contradictions and gaps.
- Reconstruct chronology internally.
- Identify referenced-but-unlocated documents.
- Distinguish allegation, established fact, evidence, inference and gap.
- For a draft FR/chargesheet, do not treat AI inference as evidence.
- Preserve source filename/page references appearing in the findings.
- If the record is insufficient to reach a conclusion, say so clearly.

Produce a clear, professionally structured output suitable for review
by the Investigating Officer.
"""

    response = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_RULES,
        input=prompt,
        max_output_tokens=20000,
    )

    return response.output_text


def run_ai(task: str, case_context: str, documents=None) -> str:
    """
    Main entry point.

    Supports the current three-argument call:
        run_ai(action, case_context, documents)

    Older two-argument calls also work.
    """
    client = get_openai_client()

    if not documents:
        response = client.responses.create(
            model=MODEL,
            instructions=SYSTEM_RULES,
            input=build_prompt(task, case_context),
            max_output_tokens=20000,
        )
        return response.output_text

    chunks = _make_document_chunks(documents)

    batches = []
    current = []
    current_size = 0

    for chunk in chunks:
        chunk_size = len(chunk["bytes"]) if chunk["bytes"] else 1000

        if current and current_size + chunk_size > TARGET_BATCH_BYTES:
            batches.append(current)
            current = []
            current_size = 0

        current.append(chunk)
        current_size += chunk_size

    if current:
        batches.append(current)

    batch_results = []

    progress = st.progress(0)
    status = st.empty()

    for index, batch in enumerate(batches):
        status.write(
            f"Reading investigation documents: batch "
            f"{index + 1} of {len(batches)}..."
        )

        result = _analyse_batch(
            client,
            task,
            case_context,
            batch,
        )

        batch_results.append(result)
        progress.progress((index + 1) / len(batches))

    status.write(
        "Combining document findings into the investigation analysis..."
    )

    final = _final_analysis(
        client,
        task,
        case_context,
        batch_results,
    )

    progress.empty()
    status.empty()

    return final


def unavailable_provider_message() -> str:
    return (
        "AI provider is not connected. "
        "Check the OPENAI_API_KEY Streamlit Secret."
    )
