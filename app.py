````python
import streamlit as st
import re
import os
import json

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Alignment Checker",
    page_icon="🎯",
    layout="wide"
)

# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    from docx import Document
except Exception:
    Document = None

try:
    import pandas as pd
except Exception:
    pd = None


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 38px;
        font-weight: 800;
        margin-bottom: 5px;
    }

    .subtitle {
        color: #666;
        font-size: 17px;
        margin-bottom: 25px;
    }

    .score-card {
        padding: 22px;
        border-radius: 14px;
        border: 1px solid #ddd;
        background-color: #fafafa;
        text-align: center;
    }

    .score-number {
        font-size: 42px;
        font-weight: 800;
    }

    .good-box {
        padding: 15px;
        border-left: 5px solid #2e8b57;
        background-color: #eef9f1;
        border-radius: 8px;
        margin-bottom: 10px;
    }

    .warning-box {
        padding: 15px;
        border-left: 5px solid #d99a00;
        background-color: #fff8e5;
        border-radius: 8px;
        margin-bottom: 10px;
    }

    .bad-box {
        padding: 15px;
        border-left: 5px solid #d9534f;
        background-color: #fff0ef;
        border-radius: 8px;
        margin-bottom: 10px;
    }

    .info-box {
        padding: 15px;
        border-left: 5px solid #3182ce;
        background-color: #eef6ff;
        border-radius: 8px;
        margin-bottom: 10px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🎯 OBE Quiz Alignment Checker</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Upload a pre-built quiz and evaluate how well it aligns with '
    'CLOs, PLOs, Bloom’s Taxonomy and assessment marks.'
    '</div>',
    unsafe_allow_html=True
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
        "recall",
        "state",
        "mention"
    ],

    "Understand": [
        "explain",
        "summarize",
        "interpret",
        "classify",
        "describe",
        "discuss",
        "illustrate"
    ],

    "Apply": [
        "apply",
        "calculate",
        "demonstrate",
        "use",
        "solve",
        "implement",
        "execute"
    ],

    "Analyze": [
        "analyze",
        "analyse",
        "differentiate",
        "examine",
        "investigate",
        "compare",
        "contrast"
    ],

    "Evaluate": [
        "evaluate",
        "assess",
        "justify",
        "critique",
        "judge",
        "defend",
        "argue",
        "recommend"
    ],

    "Create": [
        "create",
        "design",
        "develop",
        "construct",
        "formulate",
        "propose",
        "produce",
        "generate"
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
# FILE EXTRACTION
# ============================================================

def extract_pdf(uploaded_file):

    if PdfReader is None:
        return ""

    try:
        reader = PdfReader(uploaded_file)

        text = []

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                text.append(page_text)

        return "\n".join(text)

    except Exception:
        return ""


def extract_docx(uploaded_file):

    if Document is None:
        return ""

    try:

        document = Document(uploaded_file)

        content = []

        # Paragraphs
        for paragraph in document.paragraphs:

            if paragraph.text.strip():
                content.append(paragraph.text.strip())

        # Tables
        for table in document.tables:

            for row in table.rows:

                row_text = []

                for cell in row.cells:
                    row_text.append(cell.text.strip())

                content.append(" | ".join(row_text))

        return "\n".join(content)

    except Exception:
        return ""


def extract_excel(uploaded_file):

    if pd is None:
        return ""

    try:

        sheets = pd.read_excel(
            uploaded_file,
            sheet_name=None
        )

        content = []

        for sheet_name, dataframe in sheets.items():

            content.append(
                f"Sheet: {sheet_name}"
            )

            dataframe = dataframe.fillna("")

            content.append(
                dataframe.astype(str).to_csv(index=False)
            )

        return "\n".join(content)

    except Exception:
        return ""


def extract_txt(uploaded_file):

    try:

        return uploaded_file.read().decode(
            "utf-8",
            errors="ignore"
        )

    except Exception:

        return ""


def extract_file(uploaded_file):

    filename = uploaded_file.name.lower()

    if filename.endswith(".pdf"):
        return extract_pdf(uploaded_file)

    elif filename.endswith(".docx"):
        return extract_docx(uploaded_file)

    elif filename.endswith(".xlsx"):

        return extract_excel(uploaded_file)

    elif filename.endswith(".xls"):

        return extract_excel(uploaded_file)

    elif filename.endswith(".txt"):

        return extract_txt(uploaded_file)

    return ""


# ============================================================
# QUESTION DETECTION
# ============================================================

def split_questions(text):

    text = re.sub(
        r"\r\n?",
        "\n",
        text
    )

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    questions = []

    current_question = []

    pattern = re.compile(
        r"^(?:q(?:uestion)?\s*)?"
        r"(\d{1,3})"
        r"[\.\):\-]\s*(.+)$",
        re.IGNORECASE
    )

    for line in lines:

        match = pattern.match(line)

        if match:

            if current_question:

                questions.append(
                    " ".join(current_question)
                )

            current_question = [
                match.group(2)
            ]

        else:

            current_question.append(line)

    if current_question:

        questions.append(
            " ".join(current_question)
        )

    # If numbering wasn't detected,
    # try paragraph-based splitting.

    if len(questions) <= 1:

        paragraphs = [
            p.strip()
            for p in re.split(
                r"\n\s*\n",
                text
            )
            if p.strip()
        ]

        if len(paragraphs) > 1:

            questions = paragraphs

    return questions[:100]


# ============================================================
# TEXT PROCESSING
# ============================================================

def clean_words(text):

    return set(
        re.findall(
            r"[a-zA-Z]+",
            text.lower()
        )
    )


# ============================================================
# BLOOM CHECK
# ============================================================

def detect_bloom(question):

    question_words = clean_words(question)

    detected = {}

    for level, verbs in BLOOM_VERBS.items():

        found = [
            verb
            for verb in verbs
            if verb in question_words
        ]

        if found:

            detected[level] = found

    return detected


def bloom_check(
    question,
    expected_level
):

    detected = detect_bloom(question)

    if expected_level in detected:

        verbs = detected[
            expected_level
        ]

        return (
            100,
            f"Clear {expected_level}-level "
            f"action verb(s) detected: "
            f"{', '.join(verbs)}."
        )

    if detected:

        levels = ", ".join(
            detected.keys()
        )

        return (
            45,
            f"The question appears to use "
            f"verbs associated with {levels}, "
            f"rather than clearly targeting "
            f"{expected_level}."
        )

    return (
        35,
        f"No clear {expected_level}-level "
        f"action verb was detected."
    )


# ============================================================
# CLO ALIGNMENT
# ============================================================

def clo_check(
    question,
    clo
):

    stopwords = {
        "the",
        "a",
        "an",
        "of",
        "to",
        "and",
        "in",
        "on",
        "for",
        "with",
        "students",
        "student",
        "will",
        "be",
        "able",
        "should",
        "can",
        "demonstrate",
        "understand"
    }

    question_words = (
        clean_words(question)
        - stopwords
    )

    clo_words = (
        clean_words(clo)
        - stopwords
    )

    if not clo_words:

        return (
            50,
            "The CLO could not be analyzed."
        )

    overlap = (
        question_words
        .intersection(clo_words)
    )

    ratio = (
        len(overlap)
        /
        max(1, len(clo_words))
    )

    if ratio >= 0.50:

        return (
            100,
            "Strong conceptual overlap with the CLO."
        )

    elif ratio >= 0.25:

        return (
            70,
            "Partial overlap with the CLO. "
            "Review whether the question measures "
            "the intended learning outcome."
        )

    else:

        return (
            40,
            "Limited direct overlap with the CLO."
        )


# ============================================================
# MARKS / SCOPE CHECK
# ============================================================

def marks_check(question):

    match = re.search(
        r"\b(\d+)\s*marks?\b",
        question,
        re.IGNORECASE
    )

    if not match:

        return (
            75,
            "No marks value was detected. "
            "Faculty should verify the marks manually."
        )

    marks = int(
        match.group(1)
    )

    word_count = len(
        question.split()
    )

    if marks <= 2 and word_count <= 40:

        return (
            100,
            f"{marks} mark(s) appears reasonable "
            f"for the question scope."
        )

    if marks <= 5 and word_count <= 80:

        return (
            90,
            f"{marks} mark(s) appears broadly reasonable. "
            f"Confirm against the expected response."
        )

    if marks >= 10 and word_count < 15:

        return (
            65,
            f"{marks} marks may require a more "
            f"substantial task or clearer scope."
        )

    return (
        80,
        f"Review whether {marks} marks matches "
        f"the expected response and cognitive demand."
    )


# ============================================================
# EXPECTED BLOOM MAPPING
# ============================================================

def parse_bloom_mapping(
    bloom_text
):

    mapping = {}

    for line in bloom_text.splitlines():

        if ":" in line:

            key, value = line.split(
                ":",
                1
            )

            mapping[
                key.strip()
            ] = value.strip()

    return mapping


# ============================================================
# FIND CLO FOR QUESTION
# ============================================================

def find_best_clo(
    question,
    clos
):

    results = []

    for clo in clos:

        score, message = clo_check(
            question,
            clo
        )

        results.append(
            (
                score,
                message,
                clo
            )
        )

    if not results:

        return (
            0,
            "No CLO available.",
            ""
        )

    return max(
        results,
        key=lambda item: item[0]
    )


# ============================================================
# OPTIONAL AI SEMANTIC REVIEW
# ============================================================

def ai_review(
    course,
    clos,
    plos,
    bloom_map,
    questions
):

    api_key = (
        st.secrets.get(
            "OPENAI_API_KEY",
            os.getenv("OPENAI_API_KEY")
        )
    )

    if not api_key:

        return (
            None,
            "No OPENAI_API_KEY found. "
            "The built-in alignment checker will be used."
        )

    try:

        from openai import OpenAI

        client = OpenAI(
            api_key=api_key
        )

        data = {

            "course": course,

            "clos": clos,

            "plos": plos,

            "bloom_expectations": bloom_map,

            "questions": questions
        }

        prompt = f"""
You are an Outcome-Based Education assessment expert.

Review the uploaded pre-built quiz.

Evaluate EACH question for:

1. CLO alignment
2. PLO alignment
3. Bloom's Taxonomy alignment
4. Marks and cognitive demand
5. Clarity
6. Relevance to the stated CLO
7. Whether the question actually measures the intended learning outcome
8. Whether the cognitive process required matches the intended Bloom level

IMPORTANT:

Do not evaluate based only on matching words.

Consider the meaning and cognitive task.

If a question says "analyze" but only asks students to recall a fact,
flag the mismatch.

If the question is suitable but could be improved, explain exactly how.

Provide detailed teacher-friendly suggestions.

Return ONLY valid JSON in this structure:

{{
    "overall_score": 0,

    "summary": "Overall summary",

    "strengths": [
        "strength 1",
        "strength 2"
    ],

    "priority_issues": [
        "issue 1",
        "issue 2"
    ],

    "questions": [

        {{
            "number": 1,

            "clo_alignment": 0,

            "plo_alignment": 0,

            "bloom_alignment": 0,

            "marks_alignment": 0,

            "identified_bloom":
                "Remember / Understand / Apply / Analyze / Evaluate / Create / Unclear",

            "clo_comment":
                "Detailed CLO explanation",

            "plo_comment":
                "Detailed PLO explanation",

            "bloom_comment":
                "Detailed Bloom explanation",

            "marks_comment":
                "Detailed marks explanation",

            "suggestion":
                "Specific improvement suggestion",

            "revised_question":
                "Optional improved version"
        }}

    ]
}}

Do not invent CLOs or PLOs.

Do not change the teacher's intended learning outcomes.

A faculty member must make the final academic decision.

DATA:

{json.dumps(
    data,
    ensure_ascii=False
)}
"""

        response = client.responses.create(

            model="gpt-5-mini",

            input=prompt
        )

        output = (
            response
            .output_text
            .strip()
        )

        output = re.sub(
            r"^```json\s*",
            "",
            output
        )

        output = re.sub(
            r"\s*```$",
            "",
            output
        )

        return (
            json.loads(output),
            None
        )

    except Exception as error:

        return (
            None,
            f"AI review unavailable: {error}"
        )


# ============================================================
# SIDEBAR — OBE SETUP
# ============================================================

with st.sidebar:

    st.header("⚙️ OBE Review Setup")

    course = st.text_input(
        "📚 Course",
        placeholder="Example: English I"
    )

    st.subheader("🎯 Course Learning Outcomes")

    clo_text = st.text_area(
        "Enter one CLO per line",
        placeholder=(
            "CLO1: Identify main ideas in a text.\n"
            "CLO2: Analyze patterns of organization.\n"
            "CLO3: Evaluate author's purpose and tone."
        ),
        height=170
    )

    st.subheader("🔗 Program Learning Outcomes")

    plo_text = st.text_area(
        "Enter relevant PLOs",
        placeholder=(
            "PLO1: Communication Skills\n"
            "PLO2: Critical Thinking\n"
            "PLO3: Problem Analysis"
        ),
        height=140
    )

    st.subheader("🧠 Expected Bloom Levels")

    bloom_text = st.text_area(
        "Optional — one mapping per line",
        placeholder=(
            "CLO1: Understand\n"
            "CLO2: Analyze\n"
            "CLO3: Evaluate"
        ),
        height=130
    )

    st.caption(
        "Tip: You can enter only CLOs and let the tool "
        "identify possible Bloom levels from the questions."
    )


# ============================================================
# UPLOAD
# ============================================================

st.subheader(
    "📄 Step 1 — Upload Your Existing Quiz"
)

uploaded_file = st.file_uploader(
    "Upload your pre-built quiz or exam",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "txt"
    ],
    help=(
        "Supported formats: PDF, Word, Excel and TXT."
    )
)


if uploaded_file:

    with st.spinner(
        "Reading your quiz..."
    ):

        quiz_text = extract_file(
            uploaded_file
        )

    if not quiz_text.strip():

        st.error(
            "I could not extract readable text "
            "from this file."
        )

        st.info(
            "If your PDF is a scanned image, "
            "OCR support may be required."
        )

        st.stop()

    questions = split_questions(
        quiz_text
    )

    st.success(
        f"Quiz loaded successfully — "
        f"{len(questions)} question(s) detected."
    )

    with st.expander(
        "👀 Preview Extracted Quiz"
    ):

        st.text(
            quiz_text[:15000]
        )

    st.divider()

    st.subheader(
        "🔍 Step 2 — Evaluate OBE Alignment"
    )

    if not clo_text.strip():

        st.warning(
            "Please enter your CLOs in the sidebar."
        )

    if st.button(
        "🚀 EVALUATE COMPLETE QUIZ",
        type="primary",
        use_container_width=True
    ):

        clos = [
            x.strip()
            for x in clo_text.splitlines()
            if x.strip()
        ]

        plos = [
            x.strip()
            for x in plo_text.splitlines()
            if x.strip()
        ]

        bloom_map = parse_bloom_mapping(
            bloom_text
        )

        if not clos:

            st.error(
                "Please enter at least one CLO."
            )

            st.stop()

        # ----------------------------------------------------
        # BUILT-IN REVIEW
        # ----------------------------------------------------

        review_rows = []

        for number, question in enumerate(
            questions,
            start=1
        ):

            best_score, best_message, best_clo = find_best_clo(
                question,
                clos
            )

            expected_bloom = "Analyze"

            # Try to find matching CLO mapping.
            for clo_key, level in bloom_map.items():

                if clo_key.lower() in question.lower():

                    expected_bloom = level

                    break

            bloom_score_value, bloom_message = bloom_check(
                question,
                expected_bloom
            )

            marks_score_value, marks_message = marks_check(
                question
            )

            plo_score_value = (
                100
                if plos
                else 0
            )

            overall_question_score = round(
                (
                    best_score
                    +
                    bloom_score_value
                    +
                    plo_score_value
                    +
                    marks_score_value
                )
                / 4
            )

            review_rows.append({

                "number":
                    number,

                "question":
                    question,

                "clo_score":
                    best_score,

                "clo":
                    best_clo,

                "clo_message":
                    best_message,

                "bloom_score":
                    bloom_score_value,

                "bloom_expected":
                    expected_bloom,

                "bloom_message":
                    bloom_message,

                "plo_score":
                    plo_score_value,

                "marks_score":
                    marks_score_value,

                "marks_message":
                    marks_message,

                "overall":
                    overall_question_score
            })

        # ----------------------------------------------------
        # OPTIONAL AI REVIEW
        # ----------------------------------------------------

        with st.spinner(
            "Performing detailed semantic OBE review..."
        ):

            ai_result, ai_error = ai_review(
                course,
                clos,
                plos,
                bloom_map,
                questions
            )

        st.session_state[
            "review_rows"
        ] = review_rows

        st.session_state[
            "ai_result"
        ] = ai_result

        if ai_result:

            st.success(
                "🤖 AI-assisted semantic review completed."
            )

        else:

            st.info(
                ai_error
            )


# ============================================================
# RESULTS
# ============================================================

if "review_rows" in st.session_state:

    review_rows = st.session_state[
        "review_rows"
    ]

    ai_result = st.session_state.get(
        "ai_result"
    )

    st.divider()

    st.header(
        "📊 OBE Alignment Report"
    )

    # --------------------------------------------------------
    # OVERALL SCORE
    # --------------------------------------------------------

    if ai_result:

        overall_score = int(
            ai_result.get(
                "overall_score",
                0
            )
        )

    else:

        overall_score = round(
            sum(
                row["overall"]
                for row in review_rows
            )
            /
            max(
                1,
                len(review_rows)
            )
        )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "🎯 Overall Alignment",
            f"{overall_score}%"
        )

    with col2:

        strong_questions = sum(
            1
            for row in review_rows
            if row["overall"] >= 85
        )

        st.metric(
            "🟢 Strong Items",
            strong_questions
        )

    with col3:

        needs_review = sum(
            1
            for row in review_rows
            if row["overall"] < 65
        )

        st.metric(
            "🔴 Need Review",
            needs_review
        )

    with col4:

        st.metric(
            "📝 Questions",
            len(review_rows)
        )


    # --------------------------------------------------------
    # OVERALL INTERPRETATION
    # --------------------------------------------------------

    if overall_score >= 85:

        st.success(
            "🟢 The quiz shows strong overall OBE alignment. "
            "Individual questions should still be reviewed by the faculty member."
        )

    elif overall_score >= 65:

        st.warning(
            "🟡 The quiz shows partial OBE alignment. "
            "Several questions may benefit from revision."
        )

    else:

        st.error(
            "🔴 The quiz contains significant alignment issues "
            "and should be reviewed before final approval."
        )


    # --------------------------------------------------------
    # AI SUMMARY
    # --------------------------------------------------------

    if ai_result:

        st.divider()

        st.subheader(
            "🤖 AI Review Summary"
        )

        summary = ai_result.get(
            "summary",
            ""
        )

        if summary:

            st.info(
                summary
            )

        summary_col1, summary_col2 = st.columns(2)

        with summary_col1:

            st.markdown(
                "### ✅ Strengths"
            )

            strengths = ai_result.get(
                "strengths",
                []
            )

            if strengths:

                for item in strengths:

                    st.write(
                        "• " + item
                    )

            else:

                st.write(
                    "No strengths were returned."
                )

        with summary_col2:

            st.markdown(
                "### ⚠️ Priority Issues"
            )

            issues = ai_result.get(
                "priority_issues",
                []
            )

            if issues:

                for item in issues:

                    st.write(
                        "• " + item
                    )

            else:

                st.write(
                    "No priority issues were returned."
                )


    # --------------------------------------------------------
    # QUESTION-BY-QUESTION REVIEW
    # --------------------------------------------------------

    st.divider()

    st.header(
        "🔎 Question-by-Question Review"
    )

    if ai_result:

        ai_questions = ai_result.get(
            "questions",
            []
        )

        for item in ai_questions:

            number = item.get(
                "number",
                0
            )

            if (
                isinstance(number, int)
                and
                1 <= number <= len(review_rows)
            ):

                question_text = review_rows[
                    number - 1
                ]["question"]

            else:

                question_text = ""

            with st.expander(
                f"Question {number} — Detailed Alignment Review"
            ):

                st.markdown(
                    "**📄 Question:**"
                )

                st.write(
                    question_text
                )

                st.divider()

                score1, score2, score3, score4 = st.columns(4)

                with score1:

                    st.metric(
                        "🎯 CLO",
                        f'{item.get("clo_alignment", 0)}%'
                    )

                with score2:

                    st.metric(
                        "🔗 PLO",
                        f'{item.get("plo_alignment", 0)}%'
                    )

                with score3:

                    st.metric(
                        "🧠 Bloom",
                        f'{item.get("bloom_alignment", 0)}%'
                    )

                with score4:

                    st.metric(
                        "⚖️ Marks",
                        f'{item.get("marks_alignment", 0)}%'
                    )


                st.markdown(
                    "**🧠 Detected Bloom Level:**"
                )

                st.write(
                    item.get(
                        "identified_bloom",
                        "Unclear"
                    )
                )


                st.markdown(
                    "### 🎯 CLO Analysis"
                )

                st.write(
                    item.get(
                        "clo_comment",
                        "No CLO comment provided."
                    )
                )


                st.markdown(
                    "### 🔗 PLO Analysis"
                )

                st.write(
                    item.get(
                        "plo_comment",
                        "No PLO comment provided."
                    )
                )


                st.markdown(
                    "### 🧠 Bloom's Analysis"
                )

                st.write(
                    item.get(
                        "bloom_comment",
                        "No Bloom comment provided."
                    )
                )


                st.markdown(
                    "### ⚖️ Marks Analysis"
                )

                st.write(
                    item.get(
                        "marks_comment",
                        "No marks comment provided."
                    )
                )


                st.markdown(
                    "### 💡 Detailed Suggestion"
                )

                suggestion = item.get(
                    "suggestion",
                    "No suggestion provided."
                )

                st.info(
                    suggestion
                )


                revised_question = item.get(
                    "revised_question",
                    ""
                )

                if revised_question:

                    st.markdown(
                        "### ✏️ Suggested Revision"
                    )

                    st.success(
                        revised_question
                    )


    else:

        # ----------------------------------------------------
        # BUILT-IN REVIEW
        # ----------------------------------------------------

        for row in review_rows:

            with st.expander(
                f"Question {row['number']} — Alignment Review"
            ):

                st.markdown(
                    "**📄 Question:**"
                )

                st.write(
                    row["question"]
                )

                st.divider()

                c1, c2 = st.columns(2)

                with c1:

                    st.markdown(
                        "### 🎯 CLO Alignment"
                    )

                    if row["clo_score"] >= 85:

                        st.success(
                            f'{row["clo_score"]}% — '
                            f'{row["clo_message"]}'
                        )

                    elif row["clo_score"] >= 65:

                        st.warning(
                            f'{row["clo_score"]}% — '
                            f'{row["clo_message"]}'
                        )

                    else:

                        st.error(
                            f'{row["clo_score"]}% — '
                            f'{row["clo_message"]}'
                        )

                    st.write(
                        "**Possible CLO:**"
                    )

                    st.write(
                        row["clo"]
                    )


                    st.markdown(
                        "### 🔗 PLO Alignment"
                    )

                    st.write(
                        f'{row["plo_score"]}%'
                    )

                with c2:

                    st.markdown(
                        "### 🧠 Bloom's Alignment"
                    )

                    if row["bloom_score"] >= 85:

                        st.success(
                            f'{row["bloom_score"]}% — '
                            f'{row["bloom_message"]}'
                        )

                    elif row["bloom_score"] >= 65:

                        st.warning(
                            f'{row["bloom_score"]}% — '
                            f'{row["bloom_message"]}'
                        )

                    else:

                        st.error(
                            f'{row["bloom_score"]}% — '
                            f'{row["bloom_message"]}'
                        )


                    st.write(
                        "**Expected Bloom:**"
                    )

                    st.write(
                        row["bloom_expected"]
                    )


                    st.markdown(
                        "### ⚖️ Marks / Scope"
                    )

                    st.write(
                        f'{row["marks_score"]}% — '
                        f'{row["marks_message"]}'
                    )


                st.divider()

                st.markdown(
                    "### 💡 Suggested Improvement"
                )

                if row["clo_score"] < 85:

                    st.write(
                        "🎯 Make the question more directly "
                        "measure the stated CLO."
                    )

                if row["bloom_score"] < 85:

                    st.write(
                        f"🧠 Revise the cognitive demand so it "
                        f"clearly reaches the intended "
                        f"{row['bloom_expected']} level."
                    )

                if row["marks_score"] < 85:

                    st.write(
                        "⚖️ Review whether the marks match "
                        "the expected response."
                    )

                if (
                    row["clo_score"] >= 85
                    and
                    row["bloom_score"] >= 85
                    and
                    row["marks_score"] >= 85
                ):

                    st.success(
                        "✨ No major issues detected by the "
                        "built-in checker."
                    )


    # ========================================================
    # BLOOM DISTRIBUTION
    # ========================================================

    st.divider()

    st.header(
        "🧠 Bloom's Taxonomy Distribution"
    )

    bloom_counts = {
        level: 0
        for level in BLOOM_ORDER
    }

    for row in review_rows:

        detected = detect_bloom(
            row["question"]
        )

        if detected:

            selected = max(
                detected.keys(),
                key=lambda level:
                BLOOM_ORDER.index(level)
            )

            bloom_counts[
                selected
            ] += 1

    bloom_table = {
        "Bloom Level":
            list(bloom_counts.keys()),

        "Questions":
            list(bloom_counts.values())
    }

    st.dataframe(
        bloom_table,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # FACULTY REVIEW CHECKLIST
    # ========================================================

    st.divider()

    st.header(
        "👩‍🏫 Final Faculty Review"
    )

    st.write(
        "Use the AI report as a review aid. "
        "The faculty member should make the final academic decision."
    )

    checklist = [

        "Does each question measure the intended CLO?",

        "Does each question require the intended Bloom's cognitive process?",

        "Is the CLO appropriately connected to the selected PLO?",

        "Are the marks appropriate for the expected response?",

        "Are questions based on content actually taught?",

        "Are questions clear and unambiguous?",

        "Is the overall distribution of Bloom's levels appropriate?",

        "Are there any questions that should be rewritten?"
    ]

    for index, item in enumerate(
        checklist
    ):

        st.checkbox(
            item,
            key=f"faculty_review_{index}"
        )


    st.divider()

    st.success(
        "🎓 OBE principle: AI assists the review; "
        "the faculty member makes the final academic decision."
    )


else:

    st.info(
        "👈 Start by entering your CLOs/PLOs in the sidebar "
        "and uploading your existing quiz."
    )

````
