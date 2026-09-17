import streamlit as st
import pandas as pd
import re
from io import BytesIO

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="OBE Alignment Checker",
    page_icon="🎯",
    layout="wide"
)

# ============================================================
# BLOOM'S TAXONOMY
# ============================================================

BLOOM_VERBS = {
    "Remember": [
        "define", "list", "name", "identify", "state", "recall",
        "recognize", "describe", "label", "match", "select"
    ],
    "Understand": [
        "explain", "summarize", "interpret", "describe", "classify",
        "discuss", "illustrate", "paraphrase", "compare", "give examples"
    ],
    "Apply": [
        "apply", "use", "demonstrate", "calculate", "solve",
        "implement", "execute", "operate", "practice", "show"
    ],
    "Analyze": [
        "analyze", "analyse", "differentiate", "examine", "compare",
        "contrast", "investigate", "categorize", "break down",
        "distinguish", "deconstruct"
    ],
    "Evaluate": [
        "evaluate", "judge", "justify", "critique", "assess",
        "defend", "argue", "recommend", "appraise", "validate"
    ],
    "Create": [
        "create", "design", "develop", "construct", "formulate",
        "produce", "generate", "compose", "plan", "propose"
    ]
}

BLOOM_ORDER = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create"
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for",
    "with", "by", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "from", "as", "at", "it",
    "its", "into", "your", "you", "their", "them", "they", "we",
    "our", "can", "could", "should", "would", "will", "may",
    "might", "do", "does", "did", "how", "what", "why", "when",
    "where", "which", "who"
}


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text):
    text = str(text or "")

    text = text.replace("\x00", " ")
    text = text.replace("\r", "\n")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def meaningful_words(text):
    words = re.findall(r"[A-Za-z]{3,}", text.lower())

    return {
        word for word in words
        if word not in STOPWORDS
    }


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):

    question_lower = question.lower()

    scores = {}

    for level, verbs in BLOOM_VERBS.items():

        score = 0

        for verb in verbs:

            pattern = r"\b" + re.escape(verb.lower()) + r"\b"

            if re.search(pattern, question_lower):
                score += 1

        scores[level] = score

    max_score = max(scores.values())

    if max_score == 0:

        return "Not Detected", scores

    detected = [
        level
        for level, score in scores.items()
        if score == max_score
    ]

    return detected[0], scores


# ============================================================
# MARK EXTRACTION
# ============================================================

def extract_marks(question):

    patterns = [
        r"\((\d+)\s*marks?\)",
        r"\[(\d+)\s*marks?\]",
        r"(\d+)\s*marks?",
        r"marks?\s*[:\-]\s*(\d+)"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            question,
            flags=re.IGNORECASE
        )

        if match:

            try:
                return int(match.group(1))
            except Exception:
                continue

    return None


# ============================================================
# PDF EXTRACTION + OCR
# ============================================================

def extract_pdf(file):

    # --------------------------------------------------------
    # STEP 1: Try normal PDF text extraction
    # --------------------------------------------------------

    try:

        from pypdf import PdfReader

    except ImportError:

        return (
            "",
            "pypdf is not installed. "
            "Please add pypdf to requirements.txt and redeploy."
        )

    try:

        file.seek(0)

        pdf_bytes = file.read()

        if not pdf_bytes:

            return "", "The uploaded PDF is empty."

        reader = PdfReader(
            BytesIO(pdf_bytes)
        )

        normal_pages = []

        for page_number, page in enumerate(
            reader.pages,
            start=1
        ):

            try:

                page_text = page.extract_text()

            except Exception:

                page_text = ""

            if page_text:

                page_text = clean_text(page_text)

                if page_text:

                    normal_pages.append(
                        "\n--- Page "
                        + str(page_number)
                        + " ---\n"
                        + page_text
                    )

        normal_text = clean_text(
            "\n".join(normal_pages)
        )

        # If normal extraction worked, return it.
        if len(normal_text) > 30:

            return normal_text, ""

    except Exception as e:

        normal_error = str(e)

    # --------------------------------------------------------
    # STEP 2: OCR FALLBACK
    # --------------------------------------------------------

    try:

        from pdf2image import convert_from_bytes

    except ImportError:

        return (
            "",
            "PDF text extraction found no selectable text, "
            "and pdf2image is not installed. "
            "Add pdf2image and Pillow to requirements.txt."
        )

    try:

        import pytesseract

    except ImportError:

        return (
            "",
            "PDF text extraction found no selectable text, "
            "and pytesseract is not installed. "
            "Add pytesseract to requirements.txt."
        )

    try:

        # Convert PDF pages to images.
        images = convert_from_bytes(
            pdf_bytes,
            dpi=250,
            fmt="jpeg"
        )

    except Exception as e:

        return (
            "",
            "OCR could not convert the PDF into images.\n\n"
            "Make sure packages.txt contains:\n"
            "tesseract-ocr\n"
            "poppler-utils\n\n"
            "Technical error: "
            + str(e)
        )

    ocr_pages = []

    total_pages = len(images)

    progress = st.progress(
        0,
        text="Preparing OCR..."
    )

    for index, image in enumerate(images):

        page_number = index + 1

        try:

            # OCR the page.
            page_text = pytesseract.image_to_string(
                image,
                lang="eng",
                config="--psm 6"
            )

        except Exception as e:

            page_text = ""

        page_text = clean_text(page_text)

        if page_text:

            ocr_pages.append(
                "\n--- OCR Page "
                + str(page_number)
                + " ---\n"
                + page_text
            )

        progress.progress(
            int((page_number / total_pages) * 100),
            text=(
                "OCR processing page "
                + str(page_number)
                + " of "
                + str(total_pages)
                + "..."
            )
        )

    progress.empty()

    ocr_text = clean_text(
        "\n".join(ocr_pages)
    )

    if len(ocr_text) > 20:

        return ocr_text, ""

    return (
        "",
        "The PDF was opened, but neither normal text extraction "
        "nor OCR could find readable text. "
        "Please check that the PDF pages contain clear text images."
    )


# ============================================================
# DOCX EXTRACTION
# ============================================================

def extract_docx(file):

    try:

        from docx import Document

    except ImportError:

        return (
            "",
            "python-docx is not installed."
        )

    try:

        file.seek(0)

        document = Document(file)

        parts = []

        for paragraph in document.paragraphs:

            text = paragraph.text.strip()

            if text:

                parts.append(text)

        # Tables
        for table in document.tables:

            for row in table.rows:

                row_text = []

                for cell in row.cells:

                    if cell.text.strip():

                        row_text.append(
                            cell.text.strip()
                        )

                if row_text:

                    parts.append(
                        " | ".join(row_text)
                    )

        return clean_text(
            "\n".join(parts)
        ), ""

    except Exception as e:

        return (
            "",
            "Could not read DOCX: " + str(e)
        )


# ============================================================
# EXCEL EXTRACTION
# ============================================================

def extract_excel(file):

    try:

        file.seek(0)

        excel_file = pd.ExcelFile(file)

        parts = []

        for sheet in excel_file.sheet_names:

            dataframe = pd.read_excel(
                file,
                sheet_name=sheet,
                header=None
            )

            parts.append(
                "\n--- Sheet "
                + str(sheet)
                + " ---\n"
                + dataframe.fillna("")
                .astype(str)
                .to_string(index=False)
            )

        return clean_text(
            "\n".join(parts)
        ), ""

    except Exception as e:

        return (
            "",
            "Could not read Excel file: "
            + str(e)
        )


# ============================================================
# TXT EXTRACTION
# ============================================================

def extract_txt(file):

    try:

        file.seek(0)

        raw = file.read()

        if isinstance(raw, bytes):

            text = raw.decode(
                "utf-8",
                errors="ignore"
            )

        else:

            text = str(raw)

        return clean_text(text), ""

    except Exception as e:

        return (
            "",
            "Could not read TXT file: "
            + str(e)
        )


# ============================================================
# UNIVERSAL FILE READER
# ============================================================

def extract_uploaded_file(file):

    filename = file.name.lower()

    if filename.endswith(".pdf"):

        return extract_pdf(file)

    elif filename.endswith(".docx"):

        return extract_docx(file)

    elif filename.endswith(".xlsx") or filename.endswith(".xls"):

        return extract_excel(file)

    elif filename.endswith(".txt"):

        return extract_txt(file)

    else:

        return (
            "",
            "Unsupported file type. "
            "Please upload PDF, DOCX, XLSX, XLS, or TXT."
        )


# ============================================================
# OUTCOME PARSING
# ============================================================

def split_outcomes(text):

    if not text:

        return []

    lines = text.splitlines()

    outcomes = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # CLO1: ...
        # CLO-1: ...
        # CLO 1: ...
        # PLO1: ...

        match = re.match(
            r"^\s*((?:CLO|PLO)[\s\-]?\d+)\s*[:\-]\s*(.+)$",
            line,
            flags=re.IGNORECASE
        )

        if match:

            code = (
                match.group(1)
                .upper()
                .replace(" ", "")
                .replace("-", "")
            )

            description = match.group(2).strip()

            outcomes.append(
                {
                    "code": code,
                    "description": description
                }
            )

    return outcomes


# ============================================================
# QUESTION PARSING
# ============================================================

def parse_questions(text):

    if not text:

        return []

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    questions = []

    current = ""

    question_pattern = re.compile(
        r"^(?:Q(?:uestion)?\s*)?\d+[\.\):\-]\s+",
        re.IGNORECASE
    )

    for line in lines:

        if question_pattern.match(line):

            if current:

                questions.append(
                    current.strip()
                )

            current = line

        else:

            if current:

                current += " " + line

    if current:

        questions.append(
            current.strip()
        )

    # If no numbered questions were detected,
    # split by paragraphs.
    if not questions:

        paragraphs = re.split(
            r"\n\s*\n",
            text
        )

        questions = [
            clean_text(p)
            for p in paragraphs
            if len(clean_text(p)) > 15
        ]

    return questions


# ============================================================
# ALIGNMENT SCORE
# ============================================================

def alignment_score(question, outcome):

    q_words = meaningful_words(question)

    o_words = meaningful_words(
        outcome
    )

    if not q_words or not o_words:

        return 0

    common = q_words.intersection(
        o_words
    )

    score = (
        len(common)
        / max(len(o_words), 1)
    ) * 100

    return round(
        min(score, 100),
        1
    )


# ============================================================
# BEST OUTCOME
# ============================================================

def best_outcome(question, outcomes):

    if not outcomes:

        return (
            "Not Provided",
            0
        )

    results = []

    for outcome in outcomes:

        score = alignment_score(
            question,
            outcome["description"]
        )

        results.append(
            (
                outcome["code"],
                score
            )
        )

    results.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return results[0]


# ============================================================
# EXPECTED BLOOM MAPPING
# ============================================================

def parse_bloom_mapping(text):

    mapping = {}

    if not text:

        return mapping

    lines = text.splitlines()

    for line in lines:

        match = re.search(
            r"(?:Q(?:uestion)?\s*)?(\d+).*?"
            r"(Remember|Understand|Apply|Analyze|Analyse|Evaluate|Create)",
            line,
            flags=re.IGNORECASE
        )

        if match:

            number = int(
                match.group(1)
            )

            level = match.group(2).title()

            if level == "Analyse":

                level = "Analyze"

            mapping[number] = level

    return mapping


# ============================================================
# QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question,
    clos,
    plos,
    expected_bloom=None
):

    detected_bloom, bloom_scores = detect_bloom(
        question
    )

    marks = extract_marks(
        question
    )

    clo_code, clo_score = best_outcome(
        question,
        clos
    )

    plo_code, plo_score = best_outcome(
        question,
        plos
    )

    bloom_match = "Not Checked"

    if expected_bloom:

        if detected_bloom == expected_bloom:

            bloom_match = "Match"

        else:

            bloom_match = "Review"

    return {
        "Question": question,
        "Marks": marks,
        "Detected Bloom": detected_bloom,
        "Expected Bloom": expected_bloom or "",
        "Bloom Status": bloom_match,
        "CLO": clo_code,
        "CLO Alignment %": clo_score,
        "PLO": plo_code,
        "PLO Alignment %": plo_score
    }


# ============================================================
# REVIEW SCORE
# ============================================================

def calculate_review_score(dataframe):

    if dataframe.empty:

        return 0

    scores = []

    for _, row in dataframe.iterrows():

        bloom_score = 100

        if row["Expected Bloom"]:

            bloom_score = (
                100
                if row["Bloom Status"] == "Match"
                else 40
            )

        clo_score = float(
            row["CLO Alignment %"]
        )

        plo_score = float(
            row["PLO Alignment %"]
        )

        total = (
            bloom_score * 0.4
            + clo_score * 0.3
            + plo_score * 0.3
        )

        scores.append(total)

    return round(
        sum(scores) / len(scores),
        1
    )


# ============================================================
# SESSION STATE
# ============================================================

if "extracted_text" not in st.session_state:

    st.session_state.extracted_text = ""

if "questions" not in st.session_state:

    st.session_state.questions = []

if "analysis" not in st.session_state:

    st.session_state.analysis = pd.DataFrame()


# ============================================================
# HEADER
# ============================================================

st.title(
    "🎯 OBE Alignment Checker"
)

st.write(
    "Check assessment questions for Bloom's Taxonomy, "
    "CLO alignment, PLO alignment, marks, and overall OBE consistency."
)

st.divider()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ Course Setup")

    course_name = st.text_input(
        "Course Name",
        placeholder="e.g., English I"
    )

    st.subheader("CLOs")

    clo_text = st.text_area(
        "Enter CLOs",
        height=180,
        placeholder=(
            "CLO1: Identify main ideas in academic texts\n"
            "CLO2: Analyze patterns of organization\n"
            "CLO3: Apply critical reading strategies"
        )
    )

    st.subheader("PLOs")

    plo_text = st.text_area(
        "Enter PLOs",
        height=180,
        placeholder=(
            "PLO1: Communication Skills\n"
            "PLO2: Critical Thinking\n"
            "PLO3: Problem Solving"
        )
    )

    st.subheader("Expected Bloom Levels")

    bloom_mapping_text = st.text_area(
        "Optional question-to-Bloom mapping",
        height=130,
        placeholder=(
            "Q1: Understand\n"
            "Q2: Apply\n"
            "Q3: Analyze\n"
            "Q4: Evaluate"
        )
    )


# ============================================================
# PARSE OUTCOMES
# ============================================================

clos = [
    item
    for item in split_outcomes(clo_text)
    if item["code"].startswith("CLO")
]

plos = [
    item
    for item in split_outcomes(plo_text)
    if item["code"].startswith("PLO")
]

expected_mapping = parse_bloom_mapping(
    bloom_mapping_text
)


# ============================================================
# FILE UPLOAD
# ============================================================

st.header("📄 Upload Assessment")

uploaded_file = st.file_uploader(
    "Upload your assessment/question paper",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "txt"
    ],
    help=(
        "Scanned PDFs are supported through OCR. "
        "For best OCR results, use a clear PDF scan."
    )
)


# ============================================================
# READ FILE
# ============================================================

if uploaded_file:

    if st.button(
        "📖 Read & Analyze File",
        type="primary"
    ):

        with st.spinner(
            "Reading your assessment..."
        ):

            text, error = extract_uploaded_file(
                uploaded_file
            )

        if error:

            st.error(error)

        elif not text:

            st.error(
                "No text could be extracted from this file."
            )

        else:

            st.session_state.extracted_text = text

            st.session_state.questions = parse_questions(
                text
            )

            st.session_state.analysis = pd.DataFrame()

            st.success(
                "Assessment successfully read."
            )


# ============================================================
# EXTRACTED TEXT
# ============================================================

if st.session_state.extracted_text:

    st.header("📝 Extracted Assessment Text")

    with st.expander(
        "Show extracted text",
        expanded=False
    ):

        st.text_area(
            "Extracted text",
            st.session_state.extracted_text,
            height=400
        )

    st.info(
        "If this text came from a scanned PDF, it was extracted using OCR."
    )


# ============================================================
# QUESTIONS
# ============================================================

questions = st.session_state.questions

if questions:

    st.header("❓ Detected Questions")

    st.write(
        "Questions detected: "
        + str(len(questions))
    )

    for index, question in enumerate(
        questions,
        start=1
    ):

        st.write(
            "**Q"
            + str(index)
            + ":** "
            + question
        )


# ============================================================
# ANALYZE
# ============================================================

if questions:

    st.divider()

    if st.button(
        "🎯 Check OBE Alignment",
        type="primary"
    ):

        results = []

        for index, question in enumerate(
            questions,
            start=1
        ):

            expected = expected_mapping.get(
                index
            )

            result = evaluate_question(
                question,
                clos,
                plos,
                expected
            )

            results.append(
                result
            )

        st.session_state.analysis = pd.DataFrame(
            results
        )


# ============================================================
# RESULTS
# ============================================================

if not st.session_state.analysis.empty:

    dataframe = st.session_state.analysis

    st.header("📊 OBE Analysis Results")

    review_score = calculate_review_score(
        dataframe
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Questions",
            len(dataframe)
        )

    with col2:

        st.metric(
            "Average CLO Alignment",
            str(
                round(
                    dataframe[
                        "CLO Alignment %"
                    ].mean(),
                    1
                )
            )
            + "%"
        )

    with col3:

        st.metric(
            "Average PLO Alignment",
            str(
                round(
                    dataframe[
                        "PLO Alignment %"
                    ].mean(),
                    1
                )
            )
            + "%"
        )

    with col4:

        st.metric(
            "Overall Review Score",
            str(review_score)
            + "%"
        )

    st.divider()

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# BLOOM CHART
# ============================================================

if not st.session_state.analysis.empty:

    dataframe = st.session_state.analysis

    st.header("🧠 Bloom's Taxonomy Distribution")

    bloom_counts = (
        dataframe[
            "Detected Bloom"
        ]
        .value_counts()
        .reindex(
            BLOOM_ORDER,
            fill_value=0
        )
    )

    st.bar_chart(
        bloom_counts
    )


# ============================================================
# CLO COVERAGE
# ============================================================

if not st.session_state.analysis.empty:

    dataframe = st.session_state.analysis

    st.header("🎓 CLO Coverage")

    clo_counts = (
        dataframe["CLO"]
        .value_counts()
    )

    st.bar_chart(
        clo_counts
    )


# ============================================================
# PLO COVERAGE
# ============================================================

if not st.session_state.analysis.empty:

    dataframe = st.session_state.analysis

    st.header("🎯 PLO Coverage")

    plo_counts = (
        dataframe["PLO"]
        .value_counts()
    )

    st.bar_chart(
        plo_counts
    )


# ============================================================
# REVIEW TABLE
# ============================================================

if not st.session_state.analysis.empty:

    dataframe = st.session_state.analysis

    st.header("🔎 Questions Requiring Review")

    review_rows = dataframe[
        (
            dataframe["Bloom Status"] == "Review"
        )
        |
        (
            dataframe["CLO Alignment %"] < 30
        )
        |
        (
            dataframe["PLO Alignment %"] < 30
        )
    ]

    if review_rows.empty:

        st.success(
            "No major alignment issues were automatically detected."
        )

    else:

        st.warning(
            str(len(review_rows))
            + " question(s) may need faculty review."
        )

        st.dataframe(
            review_rows,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# DOWNLOAD REPORT
# ============================================================

if not st.session_state.analysis.empty:

    st.header("📥 Download Report")

    dataframe = st.session_state.analysis

    csv_data = dataframe.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="⬇️ Download CSV Report",
        data=csv_data,
        file_name="OBE_Alignment_Report.csv",
        mime="text/csv"
    )

    excel_buffer = BytesIO()

    with pd.ExcelWriter(
        excel_buffer,
        engine="openpyxl"
    ) as writer:

        dataframe.to_excel(
            writer,
            index=False,
            sheet_name="OBE Analysis"
        )

    st.download_button(
        label="⬇️ Download Excel Report",
        data=excel_buffer.getvalue(),
        file_name="OBE_Alignment_Report.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )


# ============================================================
# FACULTY CHECKLIST
# ============================================================

st.divider()

st.header("✅ Faculty Final Review Checklist")

check1 = st.checkbox(
    "The assessment questions measure the intended CLOs."
)

check2 = st.checkbox(
    "The Bloom's Taxonomy level matches the intended cognitive skill."
)

check3 = st.checkbox(
    "Questions are appropriately mapped to PLOs."
)

check4 = st.checkbox(
    "Marks are appropriate for the complexity of the question."
)

check5 = st.checkbox(
    "The final assessment has been reviewed by the faculty member."
)

if all(
    [
        check1,
        check2,
        check3,
        check4,
        check5
    ]
):

    st.success(
        "✅ Faculty review checklist completed."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "OBE Alignment Checker | AI-assisted academic alignment review | "
    "Final academic judgment should remain with the faculty member."
)
