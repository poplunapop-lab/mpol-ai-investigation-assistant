import streamlit as st
from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parent

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from database import (
    init_db,
    create_case,
    list_cases,
    add_document,
    list_documents,
    delete_document,
)

from ai_provider import run_ai


init_db()

st.set_page_config(
    page_title="M-POL AI Investigation Assistant",
    page_icon="🇮🇳",
    layout="wide",
)

st.title("🇮🇳 M-POL AI")
st.subheader("Investigation Documentation Assistant")
st.caption(
    "AI-assisted investigation documentation for authorised police officers"
)

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


if page == "Dashboard":

    st.header("Investigation Dashboard")

    cases = list_cases()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Cases", len(cases))

    with col2:
        st.metric(
            "Investigation",
            sum(
                1 for case in cases
                if case["status"] == "Investigation"
            ),
        )

    with col3:
        st.metric("FR / Chargesheet", 0)

    with col4:
        st.metric("Under Review", 0)

    st.divider()

    if not cases:
        st.info(
            "No cases have been created yet. "
            "Go to 'New Case' to create an investigation workspace."
        )
    else:
        for case in cases:
            st.write(
                f"**FIR {case['fir_no']} — {case['police_station']}**"
            )
            st.write(
                f"District: {case['district']} | "
                f"Sections: {case['sections']} | "
                f"IO: {case['io_name']} | "
                f"Status: {case['status']}"
            )
            st.divider()


elif page == "New Case":

    st.header("Create Investigation Workspace")

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

        submitted = st.form_submit_button("Create Case")

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
                    f"Case workspace created successfully. Case ID: {case_id}"
                )


elif page == "Case Workspace":

    st.header("Case Workspace")

    cases = list_cases()

    if not cases:

        st.info("No cases available. Create a case first.")

    else:

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

        st.info(
            f"FIR: {case['fir_no']} | "
            f"Police Station: {case['police_station']} | "
            f"District: {case['district']} | "
            f"Sections: {case['sections']} | "
            f"IO: {case['io_name']}"
        )

        documents = list_documents(case_id)

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

        with tabs[0]:

            st.subheader("Investigation Documents")

            st.write(
                "Upload documents in any order. M-POL will analyse their "
                "contents and reconstruct chronology internally."
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

            other_type = ""

            if document_category == "Other":
                other_type = st.text_input(
                    "Specify document type",
                    placeholder="Example: Bank record / Wireless message",
                )

            if st.button("Register Uploaded Documents"):

                if not uploaded_files:

                    st.warning(
                        "Please select at least one document."
                    )

                elif document_category == "Other" and not other_type.strip():

                    st.warning(
                        "Please specify the document type."
                    )

                else:

                    category_to_store = (
                        f"Other — {other_type.strip()}"
                        if document_category == "Other"
                        else document_category
                    )

                    for uploaded_file in uploaded_files:

                        add_document(
                            case_id,
                            uploaded_file.name,
                            category_to_store,
                            uploaded_file.getvalue(),
                            uploaded_file.type,
                        )

                    st.success(
                        "Documents uploaded and stored successfully."
                    )

                    st.rerun()

            st.divider()

            st.subheader("Documents in Case")

            documents = list_documents(case_id)

            if not documents:

                st.info("No documents have been uploaded yet.")

            else:

                for document in documents:

                    left, middle, right = st.columns(
                        [5, 3, 1]
                    )

                    with left:
                        st.write(
                            f"📄 **{document['filename']}**"
                        )

                    with middle:
                        if document["file_size"]:
                            size_kb = document["file_size"] / 1024
                            st.caption(
                                f"{document['category']} | "
                                f"{size_kb:.0f} KB | Stored"
                            )
                        else:
                            st.caption(
                                f"{document['category']} | "
                                "Content not stored"
                            )

                    with right:

                        if st.button(
                            "Delete",
                            key=f"delete_{document['id']}",
                        ):

                            delete_document(
                                document["id"]
                            )

                            st.success(
                                "Document deleted."
                            )

                            st.rerun()

        with tabs[1]:

            st.subheader("Investigation Record Completeness")

            st.info(
                "M-POL will inspect the actual document contents and "
                "identify documents referred to in the record but not "
                "available in the case workspace."
            )

        with tabs[2]:

            st.subheader("Investigation Chronology")

            st.info(
                "The IO does not need to upload documents chronologically. "
                "M-POL will reconstruct chronology internally from dates, "
                "times and investigative events found in the documents."
            )

        with tabs[3]:

            st.subheader("Evidence Matrix")

            st.info(
                "M-POL will map material facts to supporting witnesses, "
                "documents, expert evidence and other material."
            )

        with tabs[4]:

            st.subheader("Legal Ingredient Mapping")

            st.info(
                "M-POL will identify statutory ingredients and map available evidence against them."
            )

            st.warning(
                "Legal provisions and case law must be independently "
                "verified before use in an official police document."
            )

        with tabs[5]:

            st.subheader("FR / Chargesheet Documentation")

            action = st.selectbox(
                "Select Documentation Task",
                [
                    "Analyse Investigation",
                    "Draft Final Report",
                    "Draft Chargesheet",
                    "Improve Existing Police Report",
                ],
            )

            if st.button("Run M-POL AI"):

                if not documents:

                    st.warning(
                        "Upload at least one investigation document first."
                    )

                else:

                    case_context = f"""
CASE INFORMATION

Case ID: {case_id}
FIR Number: {case['fir_no']}
Police Station: {case['police_station']}
District: {case['district']}
Sections: {case['sections']}
Investigating Officer: {case['io_name']}
"""

                    with st.spinner(
                        "M-POL is reading the case record..."
                    ):

                        try:

                            result = run_ai(
                                action,
                                case_context,
                                documents,
                            )

                            st.success(
                                "M-POL analysis completed."
                            )

                            st.subheader("M-POL AI Output")
                            st.markdown(result)

                        except Exception as error:

                            st.error(
                                "AI workflow failed."
                            )

                            st.exception(error)

        with tabs[6]:

            st.subheader("Supervisory Audit")

            st.info(
                "The supervisory audit will check the AI draft against "
                "the available case record, source references, evidence "
                "gaps and contradictions."
            )


elif page == "AI Rules":

    st.header("M-POL AI — Investigation Rules")

    st.markdown(
        """
### Core safeguards

**No invented facts:** M-POL must not create facts, witnesses,
evidence, dates, places or investigative actions.

**Source-based drafting:** Important factual assertions should be
traceable to the uploaded record.

**Referenced documents:** A document mentioned in another record but
not uploaded is reported as "Referenced but not located in the current
workspace" — not treated as proof that it does not exist.

**Conflicts:** Contradictions are identified rather than silently
resolved.

**Human responsibility:** The Investigating Officer remains responsible
for the investigation and final official document.

**AI draft:** Every generated FR, chargesheet or report must be
reviewed and verified by the authorised officer before official use.
"""
    )
