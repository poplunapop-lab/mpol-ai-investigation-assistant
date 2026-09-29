import streamlit as st
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent))
from database import init_db, create_case, list_cases, add_document, list_documents
from ai_provider import build_prompt, unavailable_provider_message

init_db()

st.set_page_config(page_title="M-POL AI Investigation Assistant", layout="wide")

st.title("M-POL AI Investigation Documentation Assistant")
st.caption("Prototype v0.1 — Manipur Police")

with st.sidebar:
    st.header("Navigation")
    page = st.radio(
        "Go to",
        ["Dashboard", "New Case", "Case Workspace", "Prototype AI Rules"]
    )

if page == "Dashboard":
    st.header("Investigation Dashboard")
    cases = list_cases()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cases", len(cases))
    c2.metric("Investigation", sum(1 for x in cases if x["status"] == "Investigation"))
    c3.metric("FR / Chargesheet", 0)
    c4.metric("Review", 0)

    st.subheader("Cases")
    for c in cases:
        st.write(
            f"**FIR {c['fir_no']} — {c['police_station']}** | "
            f"{c['sections']} | IO: {c['io_name']} | {c['status']}"
        )

elif page == "New Case":
    st.header("Create Investigation Workspace")
    with st.form("new_case"):
        fir = st.text_input("FIR Number")
        ps = st.text_input("Police Station")
        district = st.text_input("District", "Noney")
        sections = st.text_input("Sections")
        io = st.text_input("Investigating Officer")
        submitted = st.form_submit_button("Create Case")
        if submitted:
            if fir and ps:
                cid = create_case(fir, ps, district, sections, io)
                st.success(f"Case workspace created: Case ID {cid}")
            else:
                st.error("FIR Number and Police Station are required.")

elif page == "Case Workspace":
    st.header("Case Workspace")
    cases = list_cases()
    if not cases:
        st.info("Create a case first.")
    else:
        options = {f"FIR {c['fir_no']} — {c['police_station']} (ID {c['id']})": c for c in cases}
        selected_label = st.selectbox("Select case", list(options))
        case = options[selected_label]
        cid = case["id"]

        st.write(
            f"**FIR:** {case['fir_no']}  |  **PS:** {case['police_station']}  |  "
            f"**District:** {case['district']}  |  **Sections:** {case['sections']}"
        )

        tabs = st.tabs([
            "Documents", "Completeness", "Chronology",
            "Evidence Matrix", "Legal Ingredients", "FR / Chargesheet", "Audit"
        ])

        with tabs[0]:
            st.subheader("Case Documents")
            uploaded = st.file_uploader(
                "Upload investigation documents",
                accept_multiple_files=True,
                type=["pdf", "docx", "txt", "jpg", "jpeg", "png"]
            )
            category = st.selectbox(
                "Category",
                ["FIR/Complaint","Witness Statement","Case Diary","Seizure/Recovery",
                 "Medical","FSL/Expert","Electronic Evidence","Arrest","Court",
                 "Site/Sketch","Other"]
            )
            if uploaded and st.button("Register Uploaded Documents"):
                for f in uploaded:
                    add_document(cid, f.name, category)
                st.success("Documents registered. In production, document extraction and indexing will run here.")

            docs = list_documents(cid)
            for d in docs:
                st.write(f"📄 **{d['filename']}** — {d['category']}")

        with tabs[1]:
            st.subheader("Investigation Record Completeness")
            st.info(
                "Prototype rule: the system must distinguish 'not located in workspace' "
                "from 'does not exist'. A production reference engine will scan all "
                "documents for cross-references and create a dependency graph."
            )
            st.markdown("""
**Statuses**
- 🟢 Present in workspace
- 🟡 Referenced but not located
- 🔵 Not referenced / no evidence of reference
- ⚠ Requires IO confirmation
""")

        with tabs[2]:
            st.subheader("Chronology")
            st.info("AI chronology engine will extract events, preserve source/page references, and flag time/date discrepancies.")

        with tabs[3]:
            st.subheader("Evidence Matrix")
            st.info("Evidence engine will map fact → evidence → source → accused/person → relevant legal ingredient.")

        with tabs[4]:
            st.subheader("Legal Ingredient Mapping")
            st.info("Legal engine will retrieve the verified statutory provision and map each ingredient to case evidence. It will not invent missing evidence.")

        with tabs[5]:
            st.subheader("FR / Chargesheet")
            action = st.selectbox("Action", ["Draft Final Report", "Draft Chargesheet", "Improve Existing Report"])
            if st.button("Run documentation workflow"):
                st.warning(unavailable_provider_message())
                st.code(build_prompt(action, f"Case ID: {cid}; FIR: {case['fir_no']}"))

        with tabs[6]:
            st.subheader("Supervisory Audit")
            st.info("Production audit will compare the draft against the structured case record, source documents, referenced-but-unlocated documents and legal ingredient matrix.")

elif page == "Prototype AI Rules":
    st.header("AI Governance Rules")
    st.code("""
1. Never invent facts, evidence, witnesses, dates, places or documents.
2. Never treat an unuploaded document as nonexistent.
3. Say "Referenced but not located in the current workspace" when appropriate.
4. Separate allegations, evidence, inference and established facts.
5. Identify conflicts instead of silently choosing one source.
6. Every material factual assertion should have source provenance.
7. Legal propositions must come from an approved legal knowledge base.
8. The IO remains responsible for investigative decisions and final documents.
9. AI output requires human verification before official use.
10. All access, generation and document changes must be auditable.
""")
