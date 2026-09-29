"""
M-POL AI Investigation Documentation Assistant
DEPLOYMENT DIAGNOSTIC VERSION

This temporary provider deliberately makes NO OpenAI API call.
It is used only to verify that Streamlit is executing this exact
ai_provider.py file.
"""

from __future__ import annotations


PROVIDER_VERSION = "M-POL-DEPLOYMENT-DIAGNOSTIC-2026-09-30"


def run_ai(
    task: str,
    case_context: str,
    documents: list[dict] | None = None,
) -> str:
    """
    Temporary deployment test.

    IMPORTANT:
    - No OpenAI API call is made.
    - No documents are uploaded.
    - No vector store is accessed.
    - No images are processed.
    - No case data is sent anywhere.

    If this function is actually running, the Streamlit app will display
    the diagnostic success message immediately.
    """

    return (
        "DEPLOYMENT TEST SUCCESS — NEW ai_provider.py IS RUNNING\n\n"
        "Provider version: "
        f"{PROVIDER_VERSION}"
    )


def unavailable_provider_message() -> str:
    return (
        "AI provider is not connected. "
        "Check the OPENAI_API_KEY Streamlit Secret."
    )
