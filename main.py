import streamlit as st
import sys
from ai_provider import run_ai, PROVIDER_VERSION


from pathlib import Path
from io import BytesIO


from PIL import Image

st.write("AI PROVIDER:", PROVIDER_VERSION)
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
    ["Dashboard", "New Case", "Case Workspace", "AI Rules"],
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
        district = st.text_input("District", value="Noney")
        sections = st.text_input(
            "Sections",
            placeholder="Example: BNS / NDPS / UAPA etc.",
        )
        io_name = st.text_input("Investigating Officer")

        submitted = st.form_submit_button("Create Case")

        if submitted:
            if not fir_no or not police_station:
                st.error("FIR Number and Police Station are required.")
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
                "Upload documents in any order. M-POL reconstructs chronology "
                "internally from the records."
            )

            st.markdown("### 1. Case Documents")

            uploaded_files = st.file_uploader(
                "Upload Case Documents",
                type=["pdf", "docx", "txt"],
                accept_multiple_files=True,
                key="case_documents_uploader",
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
                key="document_category",
            )

            other_type = ""

            if document_category == "Other":
                other_type = st.text_input(
                    "Specify document type",
                    placeholder="Example: Bank record / Wireless message",
                    key="other_document_type",
                )

            if st.button(
                "Register Uploaded Documents",
                key="register_documents",
            ):

                if not uploaded_files:
                    st.warning("Please select at least one document.")

                elif document_category == "Other" and not other_type.strip():
                    st.warning("Please specify the document type.")

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

                    st.toast(
                        "Documents registered successfully.",
                        icon="✅",
                    )
                    st.rerun()

            st.divider()

            st.markdown("### 2. Photographs / Images")

            st.caption(
                "M-POL automatically names photographs by type: "
                "FIR1.jpg, FIR2.jpg, SITE1.jpg, etc."
            )

            photo_type_options = {
                "FIR Photograph": "FIR",
                "Scene / Site Photograph": "SITE",
                "Seizure / Recovery Photograph": "SEIZURE",
                "Injury / Medical Photograph": "INJURY",
                "Property / Material Evidence Photograph": "EVIDENCE",
                "Other Photograph": "PHOTO",
            }

            photo_type = st.selectbox(
                "Photograph Type",
                list(photo_type_options.keys()),
                key="photo_type",
            )

            photo_prefix = photo_type_options[photo_type]

            photo_source = st.radio(
                "Photo Source",
                ["Take Photo", "Upload Existing Photo"],
                horizontal=True,
                key="photo_source",
            )

            photo_file = None

            if photo_source == "Take Photo":
                st.warning(
                    "Camera flash: Streamlit/browser cannot force the iPhone "
                    "hardware flash ON. Turn the iPhone flash ON before capture."
                )
                photo_file = st.camera_input(
                    "Take Photograph",
                    key="case_camera",
                )

            else:
                photo_file = st.file_uploader(
                    "Select Photograph",
                    type=["jpg", "jpeg", "png"],
                    accept_multiple_files=False,
                    key="existing_photo_uploader",
                )

            if photo_file is not None:

                try:
                    image = Image.open(photo_file).convert("RGB")
                    width, height = image.size

                    crop_photo = st.checkbox(
                        "Crop photograph before saving",
                        value=False,
                        key="crop_photo",
                    )

                    cropped_image = image

                    if crop_photo:
                        st.caption(
                            "Use the four sliders to define the crop rectangle."
                        )

                        col1, col2 = st.columns(2)

                        with col1:
                            left_pct = st.slider(
                                "Left (%)",
                                0,
                                90,
                                0,
                                key="crop_left",
                            )
                            right_pct = st.slider(
                                "Right (%)",
                                10,
                                100,
                                100,
                                key="crop_right",
                            )

                        with col2:
                            top_pct = st.slider(
                                "Top (%)",
                                0,
                                90,
                                0,
                                key="crop_top",
                            )
                            bottom_pct = st.slider(
                                "Bottom (%)",
                                10,
                                100,
                                100,
                                key="crop_bottom",
                            )

                        if (
                            left_pct >= right_pct
                            or top_pct >= bottom_pct
                        ):
                            st.error(
                                "Invalid crop rectangle. "
                                "Left must be less than Right and "
                                "Top must be less than Bottom."
                            )
                            crop_valid = False
                        else:
                            crop_valid = True

                            x1 = int(width * left_pct / 100)
                            x2 = int(width * right_pct / 100)
                            y1 = int(height * top_pct / 100)
                            y2 = int(height * bottom_pct / 100)

                            cropped_image = image.crop(
                                (x1, y1, x2, y2)
                            )

                    else:
                        crop_valid = True

                    st.image(
                        cropped_image,
                        caption="Photograph preview",
                        use_container_width=True,
                    )

                    if st.button(
                        "Save Photograph",
                        type="primary",
                        key="save_photo",
                        disabled=not crop_valid,
                    ):

                        output = BytesIO()
                        cropped_image.save(
                            output,
                            format="JPEG",
                            quality=95,
                            optimize=True,
                        )

                        existing_documents = list_documents(case_id)

                        number = 1

                        while True:
                            proposed_name = f"{photo_prefix}{number}.jpg"

                            collision = any(
                                d["filename"].lower()
                                == proposed_name.lower()
                                for d in existing_documents
                            )

                            if not collision:
                                break

                            number += 1

                        add_document(
                            case_id,
                            proposed_name,
                            photo_type,
                            output.getvalue(),
                            "image/jpeg",
                        )

                        st.toast(
                            f"{proposed_name} saved successfully.",
                            icon="📷",
                        )
                        st.rerun()

                except Exception as error:
                    st.error("The photograph could not be processed.")
                    st.exception(error)

            st.divider()
            st.subheader("Documents in Case")

            documents = list_documents(case_id)

            if not documents:
                st.info("No documents have been uploaded yet.")

            else:

                for document in documents:

                    left, middle, right = st.columns([5, 3, 1])

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
                            delete_document(document["id"])
                            st.toast("Document deleted.", icon="🗑️")
                            st.rerun()

        with tabs[1]:
            st.subheader("Investigation Record Completeness")
            st.info(
                "The AI workflow will identify documents referenced in the "
                "uploaded record but not present in the current workspace."
            )
            st.markdown(
                """
- 🟢 Present
- 🟡 Referenced but not located
- ⚠️ Requires IO verification
"""
            )

        with tabs[2]:
            st.subheader("Investigation Chronology")
            st.info(
                "Upload documents in any order. M-POL reconstructs dates, "
                "times, places and investigative events internally."
            )
            st.markdown(
                """
- Incident
- FIR registration
- Investigation actions
- Statements
- Seizures/recoveries
- Arrests
- Medical examination
- Expert examination
- Electronic evidence collection
- Court proceedings
"""
            )

        with tabs[3]:
            st.subheader("Evidence Matrix")
            st.info(
                "M-POL will map allegations/material facts against witnesses, "
                "documents, objects and expert evidence."
            )

        with tabs[4]:
            st.subheader("Legal Ingredient Mapping")
            st.warning(
                "Legal provisions and case law must be independently verified "
                "before use in an official police document."
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
                key="ai_action",
            )

            if st.button("Run M-POL AI", key="run_ai"):

                if not documents:
                    st.error(
                        "No investigation documents have been uploaded."
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

DOCUMENTS CURRENTLY REGISTERED
"""

                    for document in documents:
                        case_context += (
                            f"- {document['filename']} | "
                            f"Category: {document['category']}\n"
                        )

                    try:
                        result = run_ai(
                            action,
                            case_context,
                            documents,
                        )

                        st.success("AI analysis completed.")
                        st.subheader("M-POL AI Output")
                        st.markdown(result)

                    except Exception as error:
                        st.error("AI workflow failed.")
                        st.exception(error)

        with tabs[6]:
            st.subheader("Supervisory Audit")
            st.info(
                "Supervisory audit will check unsupported factual assertions, "
                "missing documents, contradictions, chronology issues, legal "
                "ingredient gaps and unverified conclusions."
            )


elif page == "AI Rules":

    st.header("M-POL AI — Investigation Rules")

    st.markdown(
        """
### Core safeguards

**No invented facts:** The AI must not create facts, witnesses, evidence,
dates, places or investigative actions.

**Source-first:** Uploaded records are the factual source.

**Missing documents:** If a record refers to an unavailable document, the
AI must say it is "Referenced but not located in the current workspace."

**Contradictions:** Conflicting records must be identified, not silently
resolved.

**Legal verification:** Legal provisions and case law must be verified
against approved legal sources before official use.

**Human responsibility:** The Investigating Officer remains responsible
for the investigation and final official document.

**AI output:** Every generated FR, chargesheet or report is a draft and
must be reviewed and verified before official use.
"""
    )

    st.divider()
    st.write("M-POL AI — current prototype")
    st.write("OpenAI API key: Streamlit Secrets")
    st.write("Document retrieval: OpenAI File Search")
    st.write("Photograph analysis: Responses API vision input")
