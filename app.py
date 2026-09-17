import streamlit as st
import pandas as pd
import re
from io import BytesIO

# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="OBE Alignment Checker",
    page_icon="🎯",
    layout="wide"
)

# =========================================================
# TITLE
# =========================================================

st.title("🎯 OBE Alignment Checker")
st.caption(
    "Check assessment questions for Bloom's Taxonomy, CLO alignment, "
    "PLO alignment, marks, and overall OBE consistency."
)

# =========================================================
# BLOOM'S TAXONOMY VERBS
# =========================================================

BLOOM_VERBS = {
    "Remember": [
        "define", "list", "name", "identify", "state", "recall",
        "recognize", "mention", "label", "select", "match"
    ],
    "Understand": [
        "describe", "explain", "summarize", "discuss", "interpret",
        "classify", "compare", "paraphrase", "illustrate", "outline"
    ],
    "Apply": [
        "apply", "use", "demonstrate", "solve", "calculate",
        "implement", "execute", "show", "perform", "construct"
    ],
    "Analyze": [
        "analyze", "analyse", "differentiate", "examine", "compare",
        "contrast", "categorize", "investigate", "deconstruct",
        "distinguish"
    ],
    "Evaluate": [
        "evaluate", "justify", "assess", "critique", "judge",
        "defend", "argue", "recommend", "appraise", "validate"
    ],
    "Create": [
        "create", "design", "develop", "formulate", "produce",
        "construct", "propose", "generate", "plan", "compose"
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

# =========================================================
# STOPWORDS
# =========================================================

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on",
    "for", "with", "by", "from", "is", "are", "was", "were",
    "be", "been", "being", "this", "that", "these", "those",
    "as", "at", "it", "its", "into", "about", "which", "what",
    "when", "where", "who", "why", "how", "your", "you",
    "their", "they", "them", "we", "our", "can", "could",
    "should", "would", "will", "may", "might", "must"
}

# =========================================================
# TEXT CLEANING
# =========================================================

def clean_text(text):
    text = str(text or "")
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def meaningful_words(text):
    text = clean_text(text).lower()
    words = re.findall(r"[a-zA-Z]{3,}", text)

    return {
        word
        for word in words
        if word not in STOPWORDS
    }


# =========================================================
# BLOOM DETECTION
# =========================================================

def detect_bloom(question):
    question_clean = clean_text(question).lower()

    detected = []

    for level in BLOOM_ORDER:
        for verb in BLOOM_VERBS[level]:
            pattern = r"\b" + re.escape(verb) + r"\b"

            if re.search(pattern, question_clean):
                detected.append((level, verb))

    if not detected:
        return {
            "level": "Not Detected",
            "verb": "",
            "confidence": 0.0
        }

    # Prefer the highest Bloom level detected.
    highest_index = -1
    selected_level = "Not Detected"
    selected_verb = ""

    for level, verb in detected:
        index = BLOOM_ORDER.index(level)

        if index > highest_index:
            highest_index = index
            selected_level = level
            selected_verb = verb

    confidence = min(1.0, len(detected) / 2)

    return {
        "level": selected_level,
        "verb": selected_verb,
        "confidence": confidence
    }


# =========================================================
# MARKS EXTRACTION
# =========================================================

def extract_marks(question):
    patterns = [
        r"\[\s*(\d+(?:\.\d+)?)\s*marks?\s*\]",
        r"\(\s*(\d+(?:\.\d+)?)\s*marks?\s*\)",
        r"[-–—]\s*(\d+(?:\.\d+)?)\s*marks?",
        r"(\d+(?:\.\d+)?)\s*marks?"
    ]

    for pattern in patterns:
        match = re.search(pattern, question, flags=re.IGNORECASE)

        if match:
            try:
                return float(match.group(1))
            except Exception:
                return None

    return None


# =========================================================
# PDF EXTRACTION
# =========================================================

def extract_pdf(file):
    try:
        import fitz
    except ImportError:
        return (
            "",
            "PyMuPDF is not installed. Add 'PyMuPDF' to requirements.txt "
            "and redeploy the Streamlit app."
        )

    try:
        file.seek(0)
        pdf_data = file.read()

        document = fitz.open(
            stream=pdf_data,
            filetype="pdf"
        )

        pages = []

        for page_number, page in enumerate(document, start=1):
            page_text = page.get_text("text", sort=True)

            if page_text:
                pages.append(
                    f"\n--- Page {page_number} ---\n{page_text}"
                )

        document.close()

        final_text = clean_text("\n".join(pages))

        if not final_text:
            return (
                "",
                "The PDF was opened successfully, but no selectable text "
                "was found. This usually means the PDF is scanned/image-based. "
                "OCR support is required for this type of PDF."
            )

        return final_text, ""

    except Exception as e:
        return "", f"Could not read PDF: {str(e)}"


# =========================================================
# DOCX EXTRACTION
# =========================================================

def extract_docx(file):
    try:
        from docx import Document
    except ImportError:
        return (
            "",
            "python-docx is not installed. Add 'python-docx' "
            "to requirements.txt."
        )

    try:
        file.seek(0)

        document = Document(file)

        paragraphs = []

        for paragraph in document.paragraphs:
            text = clean_text(paragraph.text)

            if text:
                paragraphs.append(text)

        # Also read tables
        for table in document.tables:
            for row in table.rows:
                row_text = []

                for cell in row.cells:
                    cell_text = clean_text(cell.text)

                    if cell_text:
                        row_text.append(cell_text)

                if row_text:
                    paragraphs.append(" | ".join(row_text))

        return "\n".join(paragraphs), ""

    except Exception as e:
        return "", f"Could not read DOCX: {str(e)}"


# =========================================================
# EXCEL EXTRACTION
# =========================================================

def extract_excel(file):
    try:
        file.seek(0)

        excel_data = pd.read_excel(
            file,
            sheet_name=None,
            header=None
        )

        all_text = []

        for sheet_name, dataframe in excel_data.items():

            all_text.append(
                f"\n--- Sheet: {sheet_name} ---"
            )

            dataframe = dataframe.fillna("")

            for row in dataframe.values:
                values = []

                for value in row:
                    value_text = clean_text(value)

                    if value_text:
                        values.append(value_text)

                if values:
                    all_text.append(" | ".join(values))

        return "\n".join(all_text), ""

    except Exception as e:
        return "", f"Could not read Excel file: {str(e)}"


# =========================================================
# TEXT FILE EXTRACTION
# =========================================================

def extract_txt(file):
    try:
        file.seek(0)

        data = file.read()

        if isinstance(data, bytes):
            data = data.decode(
                "utf-8",
                errors="ignore"
            )

        return clean_text(data), ""

    except Exception as e:
        return "", f"Could not read text file: {str(e)}"


# =========================================================
# GENERAL FILE EXTRACTION
# =========================================================

def extract_uploaded_file(file):
    filename = file.name.lower()

    if filename.endswith(".pdf"):
        return extract_pdf(file)

    if filename.endswith(".docx"):
        return extract_docx(file)

    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        return extract_excel(file)

    if filename.endswith(".txt"):
        return extract_txt(file)

    return (
        "",
        "Unsupported file type. Please upload PDF, DOCX, XLSX, XLS, or TXT."
    )


# =========================================================
# QUESTION PARSING
# =========================================================

def parse_questions(text):
    text = clean_text(text)

    if not text:
        return []

    # Normalize common question labels
    text = re.sub(
        r"\bQuestion\s*(\d+)\s*[:.)-]?",
        r"\nQUESTION \1: ",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\bQ\s*(\d+)\s*[:.)-]?",
        r"\nQUESTION \1: ",
        text,
        flags=re.IGNORECASE
    )

    # Numbered questions
    text = re.sub(
        r"(?<!\w)(\d{1,3})\s*[\.)]\s+",
        r"\nQUESTION \1: ",
        text
    )

    lines = text.splitlines()

    questions = []
    current = []

    for line in lines:
        line = clean_text(line)

        if not line:
            continue

        if re.match(
            r"^QUESTION\s+\d+\s*:",
            line,
            flags=re.IGNORECASE
        ):
            if current:
                questions.append(
                    clean_text(" ".join(current))
                )

            current = [
                re.sub(
                    r"^QUESTION\s+\d+\s*:\s*",
                    "",
                    line,
                    flags=re.IGNORECASE
                )
            ]

        else:
            current.append(line)

    if current:
        questions.append(
            clean_text(" ".join(current))
        )

    # If no question labels were found, split using question marks.
    if len(questions) <= 1:

        candidates = re.split(
            r"(?<=[?])\s+",
            text
        )

        candidates = [
            clean_text(item)
            for item in candidates
            if len(clean_text(item)) > 15
        ]

        if len(candidates) > 1:
            questions = candidates

    # Final fallback
    if not questions and len(text) > 10:
        questions = [text]

    cleaned_questions = []

    for question in questions:

        question = clean_text(question)

        # Remove page markers
        question = re.sub(
            r"--- Page \d+ ---",
            "",
            question,
            flags=re.IGNORECASE
        )

        if len(question) >= 10:
            cleaned_questions.append(question)

    return cleaned_questions


# =========================================================
# CLO / PLO ALIGNMENT
# =========================================================

def alignment_score(question, outcome):
    question_words = meaningful_words(question)
    outcome_words = meaningful_words(outcome)

    if not question_words or not outcome_words:
        return 0.0

    intersection = question_words.intersection(
        outcome_words
    )

    union = question_words.union(
        outcome_words
    )

    if not union:
        return 0.0

    score = len(intersection) / len(union)

    return round(score * 100, 2)


def best_outcome(question, outcomes):
    if not outcomes:
        return "", 0.0

    scores = []

    for outcome in outcomes:
        score = alignment_score(
            question,
            outcome
        )

        scores.append(
            (outcome, score)
        )

    scores.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return scores[0]


# =========================================================
# BLOOM MAPPING
# =========================================================

def parse_bloom_mapping(text):
    mapping = {}

    if not text:
        return mapping

    lines = text.splitlines()

    for line in lines:
        line = clean_text(line)

        if not line:
            continue

        match = re.search(
            r"(CLO\s*\d+)\s*[:=-]\s*(Remember|Understand|Apply|Analyze|Analyse|Evaluate|Create)",
            line,
            flags=re.IGNORECASE
        )

        if match:
            clo = match.group(1).upper()
            level = match.group(2).title()

            if level == "Analyse":
                level = "Analyze"

            mapping[clo] = level

    return mapping


# =========================================================
# QUESTION EVALUATION
# =========================================================

def evaluate_question(
    question,
    clos,
    plos,
    expected_bloom=None
):

    bloom_info = detect_bloom(question)

    marks = extract_marks(question)

    best_clo, clo_score = best_outcome(
        question,
        clos
    )

    best_plo, plo_score = best_outcome(
        question,
        plos
    )

    bloom_level = bloom_info["level"]

    bloom_match = "Not Checked"

    if expected_bloom:
        if bloom_level == expected_bloom:
            bloom_match = "Match"
        elif bloom_level == "Not Detected":
            bloom_match = "Not Detected"
        else:
            bloom_match = "Mismatch"

    # Alignment interpretation
    if clo_score >= 25:
        clo_alignment = "Strong"
    elif clo_score >= 10:
        clo_alignment = "Moderate"
    else:
        clo_alignment = "Weak"

    if plo_score >= 25:
        plo_alignment = "Strong"
    elif plo_score >= 10:
        plo_alignment = "Moderate"
    else:
        plo_alignment = "Weak"

    suggestions = []

    if bloom_level == "Not Detected":
        suggestions.append(
            "Use a clear measurable Bloom's Taxonomy verb."
        )

    if clo_score < 10:
        suggestions.append(
            "Review the question against the selected CLO."
        )

    if plo_score < 10:
        suggestions.append(
            "Review the question against the selected PLO."
        )

    if marks is None:
        suggestions.append(
            "Marks could not be detected automatically."
        )

    if not suggestions:
        suggestions.append(
            "Question shows reasonable alignment based on the available information."
        )

    return {
        "Question": question,
        "Marks": marks,
        "Bloom Level": bloom_level,
        "Bloom Verb": bloom_info["verb"],
        "Best CLO": best_clo,
        "CLO Score": clo_score,
        "CLO Alignment": clo_alignment,
        "Best PLO": best_plo,
        "PLO Score": plo_score,
        "PLO Alignment": plo_alignment,
        "Expected Bloom": expected_bloom or "",
        "Bloom Check": bloom_match,
        "Suggestions": " ".join(suggestions)
    }


# =========================================================
# OVERALL REVIEW SCORE
# =========================================================

def review_score(results):

    if results.empty:
        return 0

    scores = []

    for _, row in results.iterrows():

        score = 0

        # Bloom
        if row["Bloom Level"] != "Not Detected":
            score += 30

        # CLO
        if row["CLO Score"] >= 25:
            score += 25
        elif row["CLO Score"] >= 10:
            score += 15

        # PLO
        if row["PLO Score"] >= 25:
            score += 25
        elif row["PLO Score"] >= 10:
            score += 15

        # Marks
        if pd.notna(row["Marks"]):
            score += 10

        # Suggestions
        if "reasonable alignment" in str(
            row["Suggestions"]
        ):
            score += 10

        scores.append(score)

    return round(
        sum(scores) / len(scores),
        1
    )


# =========================================================
# SESSION STATE
# =========================================================

if "questions" not in st.session_state:
    st.session_state.questions = []

if "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""

if "results" not in st.session_state:
    st.session_state.results = None


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.header("⚙️ OBE Information")

course_name = st.sidebar.text_input(
    "Course Name",
    placeholder="e.g., English I"
)

st.sidebar.subheader("Course Learning Outcomes")

clo_text = st.sidebar.text_area(
    "Enter CLOs",
    placeholder=(
        "CLO1: Explain fundamental concepts.\n"
        "CLO2: Analyze information critically.\n"
        "CLO3: Apply communication skills."
    ),
    height=160
)

st.sidebar.subheader("Program Learning Outcomes")

plo_text = st.sidebar.text_area(
    "Enter PLOs",
    placeholder=(
        "PLO1: Knowledge.\n"
        "PLO2: Problem Analysis.\n"
        "PLO3: Communication Skills."
    ),
    height=160
)

st.sidebar.subheader("Expected Bloom Mapping")

bloom_mapping_text = st.sidebar.text_area(
    "Optional",
    placeholder=(
        "CLO1: Remember\n"
        "CLO2: Analyze\n"
        "CLO3: Apply"
    ),
    height=120
)

# =========================================================
# PARSE CLOs AND PLOs
# =========================================================

def split_outcomes(text):
    outcomes = []

    for line in text.splitlines():

        line = clean_text(line)

        if line:
            outcomes.append(line)

    return outcomes


clos = split_outcomes(clo_text)
plos = split_outcomes(plo_text)

expected_mapping = parse_bloom_mapping(
    bloom_mapping_text
)


# =========================================================
# FILE UPLOAD
# =========================================================

st.header("📄 Upload Assessment")

uploaded_file = st.file_uploader(
    "Upload your assessment document",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "txt"
    ],
    help=(
        "Supported formats: PDF, DOCX, XLSX, XLS and TXT."
    )
)

if uploaded_file:

    st.write(
        f"**Selected file:** {uploaded_file.name}"
    )

    if st.button(
        "📖 Read Assessment",
        type="primary"
    ):

        with st.spinner(
            "Reading your assessment..."
        ):

            extracted_text, error = extract_uploaded_file(
                uploaded_file
            )

        if error:
            st.error(error)
            st.session_state.extracted_text = ""
            st.session_state.questions = []

        else:
            st.session_state.extracted_text = extracted_text

            questions = parse_questions(
                extracted_text
            )

            st.session_state.questions = questions

            if questions:
                st.success(
                    f"Assessment read successfully. "
                    f"{len(questions)} question(s) detected."
                )
            else:
                st.warning(
                    "The file was read, but no questions could be detected."
                )


# =========================================================
# SHOW EXTRACTED TEXT
# =========================================================

if st.session_state.extracted_text:

    with st.expander(
        "🔎 View Extracted Text"
    ):
        st.text_area(
            "Extracted assessment text",
            st.session_state.extracted_text,
            height=300
        )


# =========================================================
# SHOW DETECTED QUESTIONS
# =========================================================

if st.session_state.questions:

    st.subheader(
        "📝 Detected Questions"
    )

    for i, question in enumerate(
        st.session_state.questions,
        start=1
    ):

        st.write(
            f"**Question {i}:** {question}"
        )


# =========================================================
# ANALYZE
# =========================================================

if st.session_state.questions:

    st.divider()

    if st.button(
        "🎯 Analyze OBE Alignment",
        type="primary"
    ):

        if not course_name:
            st.warning(
                "Please enter the Course Name in the sidebar."
            )

        elif not clos:
            st.warning(
                "Please enter at least one CLO in the sidebar."
            )

        elif not plos:
            st.warning(
                "Please enter at least one PLO in the sidebar."
            )

        else:

            results = []

            for index, question in enumerate(
                st.session_state.questions,
                start=1
            ):

                # Try to match expected Bloom to the best CLO
                detected = detect_bloom(question)

                expected_bloom = None

                if expected_mapping:

                    # Find likely CLO
                    best_clo, _ = best_outcome(
                        question,
                        clos
                    )

                    clo_match = re.search(
                        r"(CLO\s*\d+)",
                        best_clo,
                        flags=re.IGNORECASE
                    )

                    if clo_match:
                        clo_key = clo_match.group(1).upper()
                        expected_bloom = expected_mapping.get(
                            clo_key
                        )

                result = evaluate_question(
                    question,
                    clos,
                    plos,
                    expected_bloom
                )

                result["Question No."] = index

                results.append(result)

            results_df = pd.DataFrame(
                results
            )

            # Reorder columns
            column_order = [
                "Question No.",
                "Question",
                "Marks",
                "Bloom Level",
                "Bloom Verb",
                "Best CLO",
                "CLO Score",
                "CLO Alignment",
                "Best PLO",
                "PLO Score",
                "PLO Alignment",
                "Expected Bloom",
                "Bloom Check",
                "Suggestions"
            ]

            results_df = results_df[
                [
                    col
                    for col in column_order
                    if col in results_df.columns
                ]
            ]

            st.session_state.results = results_df


# =========================================================
# RESULTS
# =========================================================

if st.session_state.results is not None:

    results_df = st.session_state.results

    st.divider()

    st.header("📊 OBE Alignment Results")

    score = review_score(
        results_df
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Questions",
            len(results_df)
        )

    with col2:
        detected_count = (
            results_df["Bloom Level"]
            .ne("Not Detected")
            .sum()
        )

        st.metric(
            "Bloom Detected",
            detected_count
        )

    with col3:
        strong_clo = (
            results_df["CLO Alignment"]
            .eq("Strong")
            .sum()
        )

        st.metric(
            "Strong CLO Alignment",
            strong_clo
        )

    with col4:
        st.metric(
            "Overall Review Score",
            f"{score}%"
        )

    # =====================================================
    # OVERVIEW TABLE
    # =====================================================

    st.subheader(
        "📋 Question Overview"
    )

    display_columns = [
        "Question No.",
        "Marks",
        "Bloom Level",
        "Bloom Verb",
        "Best CLO",
        "CLO Alignment",
        "Best PLO",
        "PLO Alignment"
    ]

    st.dataframe(
        results_df[
            [
                col
                for col in display_columns
                if col in results_df.columns
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

    # =====================================================
    # DETAILED REVIEW
    # =====================================================

    st.subheader(
        "🔍 Detailed Question Review"
    )

    for _, row in results_df.iterrows():

        question_number = row["Question No."]

        with st.expander(
            f"Question {question_number}"
        ):

            st.write(
                f"**Question:** {row['Question']}"
            )

            c1, c2, c3 = st.columns(3)

            with c1:
                st.write(
                    f"**Marks:** {row['Marks']}"
                )

            with c2:
                st.write(
                    f"**Bloom Level:** {row['Bloom Level']}"
                )

            with c3:
                st.write(
                    f"**Bloom Verb:** {row['Bloom Verb'] or 'Not detected'}"
                )

            st.write(
                f"**Best CLO:** {row['Best CLO']}"
            )

            st.write(
                f"**CLO Alignment Score:** "
                f"{row['CLO Score']}%"
            )

            st.write(
                f"**Best PLO:** {row['Best PLO']}"
            )

            st.write(
                f"**PLO Alignment Score:** "
                f"{row['PLO Score']}%"
            )

            if row["Expected Bloom"]:
                st.write(
                    f"**Expected Bloom:** "
                    f"{row['Expected Bloom']}"
                )

                st.write(
                    f"**Bloom Check:** "
                    f"{row['Bloom Check']}"
                )

            st.info(
                f"💡 {row['Suggestions']}"
            )

    # =====================================================
    # BLOOM DISTRIBUTION
    # =====================================================

    st.subheader(
        "🧠 Bloom's Taxonomy Distribution"
    )

    bloom_counts = (
        results_df["Bloom Level"]
        .value_counts()
        .reindex(
            BLOOM_ORDER,
            fill_value=0
        )
    )

    st.bar_chart(
        bloom_counts
    )

    # =====================================================
    # CLO COVERAGE
    # =====================================================

    st.subheader(
        "🎯 CLO Coverage"
    )

    clo_coverage = {}

    for clo in clos:
        clo_coverage[clo] = (
            results_df["Best CLO"]
            .eq(clo)
            .sum()
        )

    clo_df = pd.DataFrame(
        {
            "CLO": list(
                clo_coverage.keys()
            ),
            "Questions": list(
                clo_coverage.values()
            )
        }
    )

    st.dataframe(
        clo_df,
        use_container_width=True,
        hide_index=True
    )

    # =====================================================
    # PLO COVERAGE
    # =====================================================

    st.subheader(
        "🎯 PLO Coverage"
    )

    plo_coverage = {}

    for plo in plos:
        plo_coverage[plo] = (
            results_df["Best PLO"]
            .eq(plo)
            .sum()
        )

    plo_df = pd.DataFrame(
        {
            "PLO": list(
                plo_coverage.keys()
            ),
            "Questions": list(
                plo_coverage.values()
            )
        }
    )

    st.dataframe(
        plo_df,
        use_container_width=True,
        hide_index=True
    )

    # =====================================================
    # DOWNLOAD CSV
    # =====================================================

    st.subheader(
        "📥 Download Report"
    )

    csv_data = results_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="⬇️ Download CSV Report",
        data=csv_data,
        file_name="OBE_Alignment_Report.csv",
        mime="text/csv"
    )

    # =====================================================
    # DOWNLOAD EXCEL
    # =====================================================

    excel_buffer = BytesIO()

    with pd.ExcelWriter(
        excel_buffer,
        engine="openpyxl"
    ) as writer:

        results_df.to_excel(
            writer,
            index=False,
            sheet_name="OBE Review"
        )

        clo_df.to_excel(
            writer,
            index=False,
            sheet_name="CLO Coverage"
        )

        plo_df.to_excel(
            writer,
            index=False,
            sheet_name="PLO Coverage"
        )

    st.download_button(
        label="📊 Download Excel Report",
        data=excel_buffer.getvalue(),
        file_name="OBE_Alignment_Report.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

    # =====================================================
    # FACULTY FINAL REVIEW
    # =====================================================

    st.divider()

    st.subheader(
        "✅ Faculty Final Review Checklist"
    )

    st.checkbox(
        "Questions are relevant to the course content."
    )

    st.checkbox(
        "Each question is linked to an appropriate CLO."
    )

    st.checkbox(
        "CLOs are linked to appropriate PLOs."
    )

    st.checkbox(
        "Bloom's Taxonomy level matches the intended cognitive skill."
    )

    st.checkbox(
        "Marks are appropriate for the expected level of difficulty."
    )

    st.checkbox(
        "Questions are clear, measurable, and unambiguous."
    )

    st.checkbox(
        "The final assessment has been reviewed by the faculty member."
    )

# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "OBE Alignment Checker | AI-assisted academic alignment review. "
    "Final academic decisions should be made by the faculty member."
)
