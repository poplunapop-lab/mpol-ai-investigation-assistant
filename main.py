import streamlit as st
from pathlib import Path
import sys

# ---------------------------------------------------------
# PATH SETUP
# ---------------------------------------------------------

APP_DIR = Path(__file__).resolve().parent

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from database import (
    init_db,
    create_case,
    list_cases,
    add_document,
    list_documents,
)

from ai_provider import run_ai


# ---------------------------------------------------------
# INITIALISE DATABASE
# ---------------------------------------------------------

init_db()


# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="M-POL AI Investigation Assistant",
    page_icon="🇮🇳",
    layout="wide",
)


# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.title("🇮🇳 M-POL AI")
st.subheader("Investigation Documentation Assistant")

st.caption(
    "Prototype — AI-assisted investigation documentation for authorised police officers"
)


# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------

st.sidebar.title("M-POL AI")

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "New Case",
        "Case Workspace",
        "AI Rules",
    ],
)


# =========================================================
# DASHBOARD
# =========================================================

if page == "Dashboard":

    st.header("Investigation Dashboard")

    cases = list_cases()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Cases", len(cases))

    with col2:
        investigation_cases = sum(
            1 for case in cases
            if case["status"] == "Investigation"
        )

        st.metric(
            "Investigation",
            investigation_cases,
        )

    with col3:
        st.metric(
            "FR / Chargesheet",
            0,
        )

    with col4:
        st.metric(
            "Under Review",
            0,
        )

    st.divider()

    st.subheader("Cases")

    if not cases:

        st.info(
            "No cases have been created yet. "
            "Go to 'New Case' to create an investigation workspace."
        )

    else:

        for case in cases:

            st.write(
                f"**FIR {case['fir_no']} — "
                f"{case['police_station']}**"
            )

            st.write(
                f"District: {case['district']} | "
                f"Sections: {case['sections']} | "
                f"IO: {case['io_name']} | "
                f"Status: {case['status']}"
            )

            st.divider()


# =========================================================
# NEW CASE
# =========================================================

elif page == "New Case":

    st.header("Create Investigation Workspace")

    st.write(
        "Create a separate workspace for each FIR."
    )

    with st.form("new_case_form"):

        fir_no = st.text_input(
            "FIR Number",
            placeholder="Example: 42/2026",
        )

        police_station = st.text_input(
            "Police Station",
            placeholder="Example: Noney PS",
        )

        district = st.text_input(
            "District",
            value="Noney",
        )

        sections = st.text_input(
            "Sections",
            placeholder="Example: BNS / NDPS / UAPA etc.",
        )

        io_name = st.text_input(
            "Investigating Officer",
        )

        submitted = st.form_submit_button(
            "Create Case"
        )

        if submitted:

            if not fir_no or not police_station:

                st.error(
                    "FIR Number and Police Station are required."
                )

            else:

                case_id = create_case(
                    fir_no,
                    police_station,
                    district,
                    sections,
                    io_name,
                )

                st.success(
                    f"Case workspace created successfully. "
                    f"Case ID: {case_id}"
                )


# =========================================================
# CASE WORKSPACE
# =========================================================

elif page == "Case Workspace":

    st.header("Case Workspace")

    cases = list_cases()

    if not cases:

        st.info(
            "No cases available. "
            "Create a case first."
        )

    else:

        # -------------------------------------------------
        # CASE SELECTION
        # -------------------------------------------------

        case_options = {}

        for case in cases:

            label = (
                f"FIR {case['fir_no']} — "
                f"{case['police_station']} "
                f"(Case ID {case['id']})"
            )

            case_options[label] = case

        selected_case = st.selectbox(
            "Select Case",
            list(case_options.keys()),
        )

        case = case_options[selected_case]

        case_id = case["id"]

        # -------------------------------------------------
        # CASE HEADER
        # -------------------------------------------------

        st.info(
            f"FIR: {case['fir_no']} | "
            f"Police Station: {case['police_station']} | "
            f"District: {case['district']} | "
            f"Sections: {case['sections']} | "
            f"IO: {case['io_name']}"
        )

        # -------------------------------------------------
        # LOAD DOCUMENTS
        # -------------------------------------------------

        documents = list_documents(case_id)

        # -------------------------------------------------
        # TABS
        # -------------------------------------------------

        tabs = st.tabs(
            [
                "Documents",
                "Completeness",
                "Chronology",
                "Evidence Matrix",
                "Legal Ingredients",
                "FR / Chargesheet",
                "Supervisory Audit",
            ]
        )

        # =================================================
        # DOCUMENTS
        # =================================================

        with tabs[0]:

            st.subheader(
                "Investigation Documents"
            )

            st.write(
                "Upload documents belonging to this case."
            )

            uploaded_files = st.file_uploader(
                "Upload Case Documents",
                type=[
                    "pdf",
                    "docx",
                    "txt",
                    "jpg",
                    "jpeg",
                    "png",
                ],
                accept_multiple_files=True,
            )

            document_category = st.selectbox(
                "Document Category",
                [
                    "FIR / Complaint",
                    "Witness Statement",
                    "Case Diary",
                    "Seizure / Recovery",
                    "Medical",
                    "FSL / Expert",
                    "Electronic Evidence",
                    "Arrest",
                    "Court",
                    "Site / Sketch",
                    "Other",
                ],
            )

            if st.button(
                "Register Uploaded Documents"
            ):

                if not uploaded_files:

                    st.warning(
                        "Please select at least one document."
                    )

                else:

                    for uploaded_file in uploaded_files:

                        add_document(
                            case_id,
                            uploaded_file.name,
                            document_category,
                        )

                    st.success(
                        "Documents registered successfully."
                    )

                    st.rerun()

            st.divider()

            st.subheader(
                "Documents in Case"
            )

            documents = list_documents(case_id)

            if not documents:

                st.info(
                    "No documents have been registered yet."
                )

            else:

                for document in documents:

                    st.write(
                        f"📄 **{document['filename']}**"
                    )

                    st.caption(
                        f"Category: {document['category']}"
                    )

        # =================================================
        # COMPLETENESS
        # =================================================

        with tabs[1]:

            st.subheader(
                "Investigation Record Completeness"
            )

            st.write(
                "M-POL AI will eventually examine the case "
                "documents for cross-references and identify "
                "documents that are mentioned but not available "
                "in the workspace."
            )

            st.markdown(
                """
### Document status

🟢 **Present**

Document is available in the case workspace.

🟡 **Referenced but not located**

Another document refers to it, but the document has not
been located in the current workspace.

🔵 **Not referenced**

No cross-reference has been identified.

⚠️ **Requires IO confirmation**

The AI cannot determine the status reliably and requires
human verification.
"""
            )

        # =================================================
        # CHRONOLOGY
        # =================================================

        with tabs[2]:

            st.subheader(
                "Investigation Chronology"
            )

            st.info(
                "The chronology engine will extract dates, "
                "times, places and investigative events from "
                "the actual documents."
            )

            st.write(
                "This module will identify:"
            )

            st.markdown(
                """
- Date and time of incident
- FIR registration
- Investigation actions
- Statements recorded
- Seizures
- Arrests
- Medical examination
- Expert examination
- Electronic evidence collection
- Court proceedings
"""
            )

        # =================================================
        # EVIDENCE MATRIX
        # =================================================

        with tabs[3]:

            st.subheader(
                "Evidence Matrix"
            )

            st.info(
                "The evidence engine will map allegations and "
                "material facts against witnesses, documents, "
                "objects and expert evidence."
            )

            st.markdown(
                """
### Planned structure

**Fact / Allegation**

↓

**Supporting Evidence**

↓

**Witness / Document**

↓

**Source Page**

↓

**Relevant Legal Ingredient**

↓

**Status**
"""
            )

        # =================================================
        # LEGAL INGREDIENTS
        # =================================================

        with tabs[4]:

            st.subheader(
                "Legal Ingredient Mapping"
            )

            st.info(
                "The production version will map each statutory "
                "ingredient against evidence actually available "
                "in the case."
            )

            st.warning(
                "Legal provisions must be independently verified "
                "before use in an official police document."
            )

        # =================================================
        # FR / CHARGESHEET
        # =================================================

        with tabs[5]:

            st.subheader(
                "FR / Chargesheet Documentation"
            )

            action = st.selectbox(
                "Select Documentation Task",
                [
                    "Analyse Investigation",
                    "Draft Final Report",
                    "Draft Chargesheet",
                    "Improve Existing Police Report",
                ],
            )

            st.write(
                f"Selected task: **{action}**"
            )

            if st.button(
                "Run M-POL AI"
            ):

                # -----------------------------------------
                # BUILD CASE CONTEXT
                # -----------------------------------------

                case_context = f"""
CASE INFORMATION

Case ID:
{case_id}

FIR Number:
{case['fir_no']}

Police Station:
{case['police_station']}

District:
{case['district']}

Sections:
{case['sections']}

Investigating Officer:
{case['io_name']}

DOCUMENTS CURRENTLY REGISTERED

"""

                for document in documents:

                    case_context += (
                        f"- {document['filename']} "
                        f"| Category: {document['category']}\n"
                    )

                # -----------------------------------------
                # AI CALL
                # -----------------------------------------

                with st.spinner(
                    "M-POL AI is analysing the case..."
                ):

                    try:

                        result = run_ai(
                            action,
                            case_context,
                        )

                        st.success(
                            "AI analysis completed."
                        )

                        st.subheader(
                            "M-POL AI Output"
                        )

                        st.markdown(
                            result
                        )

                    except Exception as error:

                        st.error(
                            "AI workflow failed."
                        )

                        st.exception(
                            error
                        )

        # =================================================
        # SUPERVISORY AUDIT
        # =================================================

        with tabs[6]:

            st.subheader(
                "Supervisory Audit"
            )

            st.info(
                "The supervisory audit module will compare "
                "the draft against the case record, source "
                "documents, evidence matrix and legal "
                "ingredient mapping."
            )

            st.markdown(
                """
### Planned checks

- Unsupported factual assertions
- Missing documents
- Contradictory statements
- Missing witnesses
- Missing expert reports
- Missing seizure/recovery documentation
- Chronology inconsistencies
- Legal ingredient gaps
- Unverified conclusions
- Drafting inconsistencies
"""
            )


# =========================================================
# AI RULES
# =========================================================

elif page == "AI Rules":

    st.header(
        "M-POL AI — Investigation Rules"
    )

    st.markdown(
        """
### Core AI safeguards

**1. No invented facts**

The AI must never create facts, witnesses, evidence,
dates, places or investigative actions.

**2. Missing documents**

If a document is referred to but not available, the AI
must say:

> "Referenced but not located in the current workspace."

It must not assume that the document does not exist.

**3. Evidence vs allegation**

The AI must distinguish allegations from
source-supported facts.

**4. Conflicting records**

The AI must identify contradictions rather than
silently choosing one version.

**5. Legal verification**

Legal provisions and case law must be verified against
approved legal sources before official use.

**6. Human responsibility**

The Investigating Officer remains responsible for the
investigation and final police document.

**7. AI output is a draft**

Every AI-generated FR, chargesheet or report must be
reviewed and verified by the authorised officer before
official use.
"""
    )

    st.divider()

    st.subheader(
        "Prototype Status"
    )

    st.write(
        "Current version: M-POL AI v0.1"
    )

    st.write(
        "OpenAI connection: configured through Streamlit Secrets"
    )

    st.write(
        "Document-content analysis: next development stage"
    )
