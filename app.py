import streamlit as st
import pandas as pd
import re
from io import BytesIO


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Alignment Checker",
    page_icon="🎯",
    layout="wide"
)


# ============================================================
# TITLE
# ============================================================

st.title("🎯 OBE Alignment Checker")

st.write(
    "Upload an assessment and check questions for "
    "Bloom's Taxonomy, CLO alignment, PLO alignment, "
    "marks, and overall OBE consistency."
)


# ============================================================
# BLOOM'S TAXONOMY
# ============================================================

BLOOM_VERBS = {
    "Remember": [
        "define",
        "list",
        "name",
        "identify",
        "state",
        "recall",
        "recognize",
        "recognise",
        "mention",
        "label",
        "select",
        "match"
    ],

    "Understand": [
        "describe",
        "explain",
        "summarize",
        "summarise",
        "discuss",
        "interpret",
        "classify",
        "compare",
        "paraphrase",
        "illustrate",
        "outline"
    ],

    "Apply": [
        "apply",
        "use",
        "demonstrate",
        "solve",
        "calculate",
        "implement",
        "execute",
        "perform",
        "construct",
        "practice",
        "practise"
    ],

    "Analyze": [
        "analyze",
        "analyse",
        "differentiate",
        "examine",
        "compare",
        "contrast",
        "categorize",
        "categorise",
        "investigate",
        "deconstruct",
        "distinguish"
    ],

    "Evaluate": [
        "evaluate",
        "justify",
        "assess",
        "critique",
        "judge",
        "defend",
        "argue",
        "recommend",
        "appraise",
        "validate"
    ],

    "Create": [
        "create",
        "design",
        "develop",
        "formulate",
        "produce",
        "construct",
        "propose",
        "generate",
        "plan",
        "compose"
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


# ============================================================
# STOP WORDS
# ============================================================

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "by",
    "from",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "this",
    "that",
    "these",
    "those",
    "as",
    "at",
    "it",
    "its",
    "into",
    "about",
    "which",
    "what",
    "when",
    "where",
    "who",
    "why",
    "how",
    "your",
    "you",
    "their",
    "they",
    "them",
    "we",
    "our",
    "can",
    "could",
    "should",
    "would",
    "will",
    "may",
    "might",
    "must"
}


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text):
    text = str(text or "")

    text = text.replace("\xa0", " ")

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# MEANINGFUL WORDS
# ============================================================

def meaningful_words(text):

    text = clean_text(text).lower()

    words = re.findall(
        r"[a-zA-Z]{3,}",
        text
    )

    return {
        word
        for word in words
        if word not in STOPWORDS
    }


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):

    question_text = clean_text(
        question
    ).lower()

    detected = []

    for level in BLOOM_ORDER:

        for verb in BLOOM_VERBS[level]:

            pattern = (
                r"\b"
                + re.escape(verb)
                + r"\b"
            )

            if re.search(
                pattern,
                question_text
            ):
                detected.append(
                    (level, verb)
                )

    if not detected:

        return {
            "level": "Not Detected",
            "verb": "",
            "confidence": 0
        }

    highest_index = -1
    selected_level = "Not Detected"
    selected_verb = ""

    for level, verb in detected:

        index = BLOOM_ORDER.index(
            level
        )

        if index > highest_index:

            highest_index = index
            selected_level = level
            selected_verb = verb

    confidence = min(
        1.0,
        len(detected) / 2
    )

    return {
        "level": selected_level,
        "verb": selected_verb,
        "confidence": confidence
    }


# ============================================================
# MARK EXTRACTION
# ============================================================

def extract_marks(question):

    patterns = [

        r"\[\s*(\d+(?:\.\d+)?)\s*marks?\s*\]",

        r"\(\s*(\d+(?:\.\d+)?)\s*marks?\s*\)",

        r"[-–—]\s*(\d+(?:\.\d+)?)\s*marks?",

        r"(\d+(?:\.\d+)?)\s*marks?"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            question,
            flags=re.IGNORECASE
        )

        if match:

            try:
                return float(
                    match.group(1)
                )

            except Exception:
                return None

    return None


# ============================================================
# PDF EXTRACTION USING PYPDF
# ============================================================

def extract_pdf(file):

    try:

        from pypdf import PdfReader

    except ImportError:

        return (
            "",
            "pypdf is not installed. "
            "Please add pypdf to requirements.txt "
            "and redeploy the Streamlit app."
        )

    try:

        file.seek(0)

        reader = PdfReader(file)

        pages = []

        for page_number, page in enumerate(
            reader.pages,
            start=1
        ):

            try:

                page_text = (
                    page.extract_text()
                    or ""
                )

            except Exception:

                page_text = ""

            if page_text.strip():

                pages.append(
                    "\n--- Page "
                    + str(page_number)
                    + " ---\n"
                    + page_text
                )

        final_text = clean_text(
            "\n".join(pages)
        )

        if not final_text:

            return (
                "",
                "The PDF was opened successfully, "
                "but no selectable text could be extracted. "
                "This usually means the PDF is scanned or "
                "image-based. Please upload a text-based PDF "
                "or use OCR before uploading."
            )

        return final_text, ""

    except Exception as e:

        return (
            "",
            "Could not read PDF: "
            + str(e)
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

        content = []

        for paragraph in document.paragraphs:

            text = clean_text(
                paragraph.text
            )

            if text:

                content.append(
                    text
                )

        # Read tables as well

        for table in document.tables:

            for row in table.rows:

                row_values = []

                for cell in row.cells:

                    cell_text = clean_text(
                        cell.text
                    )

                    if cell_text:

                        row_values.append(
                            cell_text
                        )

                if row_values:

                    content.append(
                        " | ".join(
                            row_values
                        )
                    )

        return (
            "\n".join(content),
            ""
        )

    except Exception as e:

        return (
            "",
            "Could not read DOCX: "
            + str(e)
        )


# ============================================================
# EXCEL EXTRACTION
# ============================================================

def extract_excel(file):

    try:

        file.seek(0)

        sheets = pd.read_excel(
            file,
            sheet_name=None,
            header=None
        )

        content = []

        for sheet_name, dataframe in sheets.items():

            content.append(
                "\n--- Sheet: "
                + str(sheet_name)
                + " ---"
            )

            dataframe = dataframe.fillna("")

            for row in dataframe.values:

                values = []

                for value in row:

                    value_text = clean_text(
                        value
                    )

                    if value_text:

                        values.append(
                            value_text
                        )

                if values:

                    content.append(
                        " | ".join(values)
                    )

        return (
            "\n".join(content),
            ""
        )

    except Exception as e:

        return (
            "",
            "Could not read Excel file: "
            + str(e)
        )


# ============================================================
# TEXT FILE EXTRACTION
# ============================================================

def extract_txt(file):

    try:

        file.seek(0)

        data = file.read()

        if isinstance(
            data,
            bytes
        ):

            data = data.decode(
                "utf-8",
                errors="ignore"
            )

        return (
            clean_text(data),
            ""
        )

    except Exception as e:

        return (
            "",
            "Could not read text file: "
            + str(e)
        )


# ============================================================
# GENERAL FILE READER
# ============================================================

def extract_uploaded_file(file):

    filename = file.name.lower()

    if filename.endswith(".pdf"):

        return extract_pdf(file)

    elif filename.endswith(".docx"):

        return extract_docx(file)

    elif (
        filename.endswith(".xlsx")
        or filename.endswith(".xls")
    ):

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
# SPLIT CLOs / PLOs
# ============================================================

def split_outcomes(text):

    outcomes = []

    if not text:
        return outcomes

    for line in text.splitlines():

        line = clean_text(line)

        if line:

            outcomes.append(
                line
            )

    return outcomes


# ============================================================
# QUESTION PARSER
# ============================================================

def parse_questions(text):

    text = clean_text(text)

    if not text:

        return []

    # Convert Question 1, Question 2, etc.
    text = re.sub(
        r"\bQuestion\s*(\d+)\s*[:.)-]?",
        r"\nQUESTION \1: ",
        text,
        flags=re.IGNORECASE
    )

    # Convert Q1, Q2, etc.
    text = re.sub(
        r"\bQ\s*(\d+)\s*[:.)-]?",
        r"\nQUESTION \1: ",
        text,
        flags=re.IGNORECASE
    )

    # Convert 1. / 2. / 3)
    text = re.sub(
        r"(?<!\w)(\d{1,3})\s*[\.)]\s+",
        r"\nQUESTION \1: ",
        text
    )

    lines = text.splitlines()

    questions = []

    current_question = []

    found_question_label = False

    for line in lines:

        line = clean_text(line)

        if not line:
            continue

        question_match = re.match(
            r"^QUESTION\s+\d+\s*:",
            line,
            flags=re.IGNORECASE
        )

        if question_match:

            found_question_label = True

            if current_question:

                questions.append(
                    clean_text(
                        " ".join(
                            current_question
                        )
                    )
                )

            question_text = re.sub(
                r"^QUESTION\s+\d+\s*:\s*",
                "",
                line,
                flags=re.IGNORECASE
            )

            current_question = [
                question_text
            ]

        else:

            current_question.append(
                line
            )

    if current_question:

        questions.append(
            clean_text(
                " ".join(
                    current_question
                )
            )
        )

    # Remove very short items

    questions = [
        q
        for q in questions
        if len(q) >= 10
    ]

    # If no numbered questions were detected,
    # try question marks.

    if (
        not found_question_label
        and len(questions) <= 1
    ):

        candidates = re.split(
            r"(?<=[?])\s+",
            text
        )

        candidates = [
            clean_text(q)
            for q in candidates
            if len(clean_text(q)) >= 15
        ]

        if len(candidates) > 1:

            questions = candidates

    # Final fallback

    if not questions and len(text) >= 10:

        questions = [
            text
        ]

    return questions


# ============================================================
# ALIGNMENT SCORE
# ============================================================

def alignment_score(
    question,
    outcome
):

    question_words = meaningful_words(
        question
    )

    outcome_words = meaningful_words(
        outcome
    )

    if (
        not question_words
        or not outcome_words
    ):

        return 0.0

    intersection = (
        question_words
        .intersection(
            outcome_words
        )
    )

    union = (
        question_words
        .union(
            outcome_words
        )
    )

    if not union:

        return 0.0

    score = (
        len(intersection)
        / len(union)
    )

    return round(
        score * 100,
        2
    )


# ============================================================
# FIND BEST OUTCOME
# ============================================================

def best_outcome(
    question,
    outcomes
):

    if not outcomes:

        return (
            "",
            0.0
        )

    scores = []

    for outcome in outcomes:

        score = alignment_score(
            question,
            outcome
        )

        scores.append(
            (
                outcome,
                score
            )
        )

    scores.sort(
        key=lambda item: item[1],
        reverse=True
    )

    return scores[0]


# ============================================================
# BLOOM MAPPING PARSER
# ============================================================

def parse_bloom_mapping(text):

    mapping = {}

    if not text:

        return mapping

    for line in text.splitlines():

        line = clean_text(
            line
        )

        if not line:

            continue

        match = re.search(
            r"(CLO\s*\d+)\s*[:=-]\s*"
            r"(Remember|Understand|Apply|Analyze|Analyse|Evaluate|Create)",
            line,
            flags=re.IGNORECASE
        )

        if match:

            clo = match.group(
                1
            ).upper()

            level = match.group(
                2
            ).title()

            if level == "Analyse":

                level = "Analyze"

            mapping[clo] = level

    return mapping


# ============================================================
# EVALUATE QUESTION
# ============================================================

def evaluate_question(
    question,
    clos,
    plos,
    expected_bloom=None
):

    bloom = detect_bloom(
        question
    )

    marks = extract_marks(
        question
    )

    best_clo, clo_score = best_outcome(
        question,
        clos
    )

    best_plo, plo_score = best_outcome(
        question,
        plos
    )

    bloom_level = bloom["level"]

    if expected_bloom:

        if bloom_level == expected_bloom:

            bloom_check = "Match"

        elif bloom_level == "Not Detected":

            bloom_check = "Not Detected"

        else:

            bloom_check = "Mismatch"

    else:

        bloom_check = "Not Checked"

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
            "The question shows reasonable alignment "
            "based on the information provided."
        )

    return {

        "Question": question,

        "Marks": marks,

        "Bloom Level": bloom_level,

        "Bloom Verb": bloom["verb"],

        "Best CLO": best_clo,

        "CLO Score": clo_score,

        "CLO Alignment": clo_alignment,

        "Best PLO": best_plo,

        "PLO Score": plo_score,

        "PLO Alignment": plo_alignment,

        "Expected Bloom": (
            expected_bloom
            or ""
        ),

        "Bloom Check": bloom_check,

        "Suggestions": " ".join(
            suggestions
        )
    }


# ============================================================
# OVERALL SCORE
# ============================================================

def calculate_review_score(
    dataframe
):

    if dataframe.empty:

        return 0

    scores = []

    for _, row in dataframe.iterrows():

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
        if pd.notna(
            row["Marks"]
        ):

            score += 10

        # Good alignment
        if (
            "reasonable alignment"
            in str(
                row["Suggestions"]
            )
        ):

            score += 10

        scores.append(
            score
        )

    if not scores:

        return 0

    return round(
        sum(scores)
        / len(scores),
        1
    )


# ============================================================
# SESSION STATE
# ============================================================

if "questions" not in st.session_state:

    st.session_state.questions = []


if "extracted_text" not in st.session_state:

    st.session_state.extracted_text = ""


if "results" not in st.session_state:

    st.session_state.results = None


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header(
    "⚙️ OBE Information"
)


course_name = st.sidebar.text_input(
    "Course Name",
    placeholder="Example: English I"
)


st.sidebar.subheader(
    "Course Learning Outcomes (CLOs)"
)


clo_text = st.sidebar.text_area(
    "Enter CLOs",
    placeholder=(
        "CLO1: Explain fundamental concepts.\n"
        "CLO2: Analyze information critically.\n"
        "CLO3: Apply communication skills."
    ),
    height=170
)


st.sidebar.subheader(
    "Program Learning Outcomes (PLOs)"
)


plo_text = st.sidebar.text_area(
    "Enter PLOs",
    placeholder=(
        "PLO1: Knowledge.\n"
        "PLO2: Problem Analysis.\n"
        "PLO3: Communication Skills."
    ),
    height=170
)


st.sidebar.subheader(
    "Expected Bloom Mapping"
)


bloom_mapping_text = st.sidebar.text_area(
    "Optional",
    placeholder=(
        "CLO1: Remember\n"
        "CLO2: Analyze\n"
        "CLO3: Apply"
    ),
    height=120
)


# ============================================================
# PREPARE CLOs / PLOs
# ============================================================

clos = split_outcomes(
    clo_text
)

plos = split_outcomes(
    plo_text
)

expected_mapping = parse_bloom_mapping(
    bloom_mapping_text
)


# ============================================================
# FILE UPLOAD
# ============================================================

st.header(
    "📄 Upload Assessment"
)


uploaded_file = st.file_uploader(
    "Upload PDF, DOCX, Excel, or TXT",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "txt"
    ]
)


if uploaded_file:

    st.write(
        "**Selected file:** "
        + uploaded_file.name
    )

    if st.button(
        "📖 Read Assessment",
        type="primary"
    ):

        with st.spinner(
            "Reading assessment..."
        ):

            extracted_text, error = (
                extract_uploaded_file(
                    uploaded_file
                )
            )

        if error:

            st.error(
                error
            )

            st.session_state.extracted_text = ""

            st.session_state.questions = []

        else:

            st.session_state.extracted_text = (
                extracted_text
            )

            questions = parse_questions(
                extracted_text
            )

            st.session_state.questions = (
                questions
            )

            if questions:

                st.success(
                    "Assessment read successfully. "
                    + str(len(questions))
                    + " question(s) detected."
                )

            else:

                st.warning(
                    "The file was read, but "
                    "no questions were detected."
                )


# ============================================================
# SHOW EXTRACTED TEXT
# ============================================================

if st.session_state.extracted_text:

    with st.expander(
        "🔎 View Extracted Text"
    ):

        st.text_area(
            "Extracted Text",
            st.session_state.extracted_text,
            height=300
        )


# ============================================================
# SHOW QUESTIONS
# ============================================================

if st.session_state.questions:

    st.subheader(
        "📝 Detected Questions"
    )

    for number, question in enumerate(
        st.session_state.questions,
        start=1
    ):

        st.write(
            "**Question "
            + str(number)
            + ":** "
            + question
        )


# ============================================================
# ANALYZE BUTTON
# ============================================================

if st.session_state.questions:

    st.divider()

    if st.button(
        "🎯 Analyze OBE Alignment",
        type="primary"
    ):

        if not course_name:

            st.warning(
                "Please enter the Course Name."
            )

        elif not clos:

            st.warning(
                "Please enter at least one CLO."
            )

        elif not plos:

            st.warning(
                "Please enter at least one PLO."
            )

        else:

            results = []

            for number, question in enumerate(
                st.session_state.questions,
                start=1
            ):

                expected_bloom = None

                if expected_mapping:

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

                        clo_key = (
                            clo_match.group(
                                1
                            ).upper()
                        )

                        expected_bloom = (
                            expected_mapping.get(
                                clo_key
                            )
                        )

                result = evaluate_question(
                    question,
                    clos,
                    plos,
                    expected_bloom
                )

                result[
                    "Question No."
                ] = number

                results.append(
                    result
                )

            results_df = pd.DataFrame(
                results
            )

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
                    column
                    for column in column_order
                    if column in results_df.columns
                ]
            ]

            st.session_state.results = (
                results_df
            )


# ============================================================
# RESULTS
# ============================================================

if st.session_state.results is not None:

    results_df = (
        st.session_state.results
    )

    st.divider()

    st.header(
        "📊 OBE Alignment Results"
    )

    overall_score = (
        calculate_review_score(
            results_df
        )
    )

    col1, col2, col3, col4 = st.columns(
        4
    )

    with col1:

        st.metric(
            "Questions",
            len(results_df)
        )

    with col2:

        bloom_count = (
            results_df[
                "Bloom Level"
            ]
            .ne("Not Detected")
            .sum()
        )

        st.metric(
            "Bloom Detected",
            bloom_count
        )

    with col3:

        strong_clo = (
            results_df[
                "CLO Alignment"
            ]
            .eq("Strong")
            .sum()
        )

        st.metric(
            "Strong CLO Alignment",
            strong_clo
        )

    with col4:

        st.metric(
            "Overall Review",
            str(overall_score)
            + "%"
        )


    # ========================================================
    # OVERVIEW
    # ========================================================

    st.subheader(
        "📋 Question Overview"
    )

    overview_columns = [

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
                column
                for column in overview_columns
                if column in results_df.columns
            ]
        ],
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # DETAILED REVIEW
    # ========================================================

    st.subheader(
        "🔍 Detailed Question Review"
    )

    for _, row in results_df.iterrows():

        with st.expander(
            "Question "
            + str(
                row["Question No."]
            )
        ):

            st.write(
                "**Question:** "
                + str(
                    row["Question"]
                )
            )

            col1, col2, col3 = st.columns(
                3
            )

            with col1:

                st.write(
                    "**Marks:** "
                    + str(
                        row["Marks"]
                    )
                )

            with col2:

                st.write(
                    "**Bloom Level:** "
                    + str(
                        row["Bloom Level"]
                    )
                )

            with col3:

                verb = (
                    row["Bloom Verb"]
                    or "Not detected"
                )

                st.write(
                    "**Bloom Verb:** "
                    + str(verb)
                )

            st.write(
                "**Best CLO:** "
                + str(
                    row["Best CLO"]
                )
            )

            st.write(
                "**CLO Alignment Score:** "
                + str(
                    row["CLO Score"]
                )
                + "%"
            )

            st.write(
                "**Best PLO:** "
                + str(
                    row["Best PLO"]
                )
            )

            st.write(
                "**PLO Alignment Score:** "
                + str(
                    row["PLO Score"]
                )
                + "%"
            )

            if row["Expected Bloom"]:

                st.write(
                    "**Expected Bloom:** "
                    + str(
                        row["Expected Bloom"]
                    )
                )

                st.write(
                    "**Bloom Check:** "
                    + str(
                        row["Bloom Check"]
                    )
                )

            st.info(
                "💡 "
                + str(
                    row["Suggestions"]
                )
            )


    # ========================================================
    # BLOOM DISTRIBUTION
    # ========================================================

    st.subheader(
        "🧠 Bloom's Taxonomy Distribution"
    )

    bloom_counts = (
        results_df[
            "Bloom Level"
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


    # ========================================================
    # CLO COVERAGE
    # ========================================================

    st.subheader(
        "🎯 CLO Coverage"
    )

    clo_coverage = []

    for clo in clos:

        count = (
            results_df[
                "Best CLO"
            ]
            .eq(clo)
            .sum()
        )

        clo_coverage.append(
            {
                "CLO": clo,
                "Questions": count
            }
        )

    clo_df = pd.DataFrame(
        clo_coverage
    )

    st.dataframe(
        clo_df,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # PLO COVERAGE
    # ========================================================

    st.subheader(
        "🎯 PLO Coverage"
    )

    plo_coverage = []

    for plo in plos:

        count = (
            results_df[
                "Best PLO"
            ]
            .eq(plo)
            .sum()
        )

        plo_coverage.append(
            {
                "PLO": plo,
                "Questions": count
            }
        )

    plo_df = pd.DataFrame(
        plo_coverage
    )

    st.dataframe(
        plo_df,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # CSV DOWNLOAD
    # ========================================================

    st.subheader(
        "📥 Download Reports"
    )

    csv_data = results_df.to_csv(
        index=False
    ).encode(
        "utf-8"
    )

    st.download_button(
        "⬇️ Download CSV Report",
        data=csv_data,
        file_name="OBE_Alignment_Report.csv",
        mime="text/csv"
    )


    # ========================================================
    # EXCEL DOWNLOAD
    # ========================================================

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
        "📊 Download Excel Report",
        data=excel_buffer.getvalue(),
        file_name="OBE_Alignment_Report.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )


    # ========================================================
    # FACULTY REVIEW
    # ========================================================

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
        "Marks are appropriate for the expected difficulty."
    )

    st.checkbox(
        "Questions are clear, measurable, and unambiguous."
    )

    st.checkbox(
        "Final assessment has been reviewed by the faculty member."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "OBE Alignment Checker | AI-assisted academic alignment review. "
    "Final academic decisions should be made by the faculty member."
)
