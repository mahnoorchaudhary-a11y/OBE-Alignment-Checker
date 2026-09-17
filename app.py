````python
import streamlit as st
import re
import os
import json

# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from docx import Document
except ImportError:
    Document = None


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="OBE Alignment Checker",
    page_icon="🎯",
    layout="wide"
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    .title {
        font-size: 38px;
        font-weight: 800;
        margin-bottom: 5px;
    }

    .subtitle {
        font-size: 17px;
        color: #666;
        margin-bottom: 25px;
    }

    .review-box {
        padding: 16px;
        border-radius: 10px;
        margin: 10px 0;
        border: 1px solid #ddd;
    }

    .small-text {
        color: #666;
        font-size: 14px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# TITLE
# ============================================================

st.markdown(
    '<div class="title">🎯 OBE Alignment Checker</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Upload your existing quiz and check its alignment with '
    'CLOs, PLOs, Bloom’s Taxonomy, and marks.'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# BLOOM TAXONOMY
# ============================================================

BLOOM_LEVELS = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create"
]

BLOOM_VERBS = {

    "Remember": [
        "define",
        "identify",
        "list",
        "name",
        "recall",
        "recognize",
        "state",
        "mention"
    ],

    "Understand": [
        "describe",
        "explain",
        "summarize",
        "interpret",
        "classify",
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
        "compare",
        "contrast",
        "differentiate",
        "examine",
        "investigate",
        "break down"
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


# ============================================================
# FILE EXTRACTION
# ============================================================

def extract_pdf(file):

    if PdfReader is None:
        return ""

    try:

        reader = PdfReader(file)

        pages = []

        for page in reader.pages:

            text = page.extract_text()

            if text:
                pages.append(text)

        return "\n".join(pages)

    except Exception:
        return ""


def extract_docx(file):

    if Document is None:
        return ""

    try:

        doc = Document(file)

        parts = []

        for paragraph in doc.paragraphs:

            text = paragraph.text.strip()

            if text:
                parts.append(text)

        for table in doc.tables:

            for row in table.rows:

                cells = []

                for cell in row.cells:

                    cells.append(
                        cell.text.strip()
                    )

                parts.append(
                    " | ".join(cells)
                )

        return "\n".join(parts)

    except Exception:
        return ""


def extract_excel(file):

    if pd is None:
        return ""

    try:

        sheets = pd.read_excel(
            file,
            sheet_name=None
        )

        parts = []

        for sheet_name, dataframe in sheets.items():

            parts.append(
                f"Sheet: {sheet_name}"
            )

            dataframe = dataframe.fillna("")

            parts.append(
                dataframe.astype(str).to_string(
                    index=False
                )
            )

        return "\n".join(parts)

    except Exception:
        return ""


def extract_text(file):

    try:

        return file.read().decode(
            "utf-8",
            errors="ignore"
        )

    except Exception:
        return ""


def extract_file(file):

    filename = file.name.lower()

    if filename.endswith(".pdf"):
        return extract_pdf(file)

    if filename.endswith(".docx"):
        return extract_docx(file)

    if filename.endswith(".xlsx"):
        return extract_excel(file)

    if filename.endswith(".xls"):
        return extract_excel(file)

    if filename.endswith(".txt"):
        return extract_text(file)

    return ""


# ============================================================
# QUESTION PARSER
# ============================================================

def parse_questions(text):

    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    questions = []

    current = None

    # Supports:
    # 1.
    # 1)
    # Q1.
    # Question 1:
    pattern = re.compile(
        r"^(?:question\s*|q\s*)?"
        r"(\d{1,3})"
        r"[\.\):\-]\s*(.*)$",
        re.IGNORECASE
    )

    for line in lines:

        match = pattern.match(line)

        if match:

            if current is not None:

                questions.append(
                    current.strip()
                )

            current = match.group(2).strip()

        else:

            if current is not None:

                current += " " + line

    if current is not None:

        questions.append(
            current.strip()
        )

    # If numbered questions were not found,
    # try paragraphs.

    if len(questions) < 2:

        paragraphs = re.split(
            r"\n\s*\n",
            text
        )

        paragraphs = [
            p.strip()
            for p in paragraphs
            if p.strip()
        ]

        if len(paragraphs) >= 2:

            questions = paragraphs

    return questions


# ============================================================
# BASIC TEXT FUNCTIONS
# ============================================================

def words(text):

    return set(
        re.findall(
            r"[a-zA-Z]+",
            text.lower()
        )
    )


def meaningful_words(text):

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
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "will",
        "can",
        "should",
        "students",
        "student",
        "able",
        "demonstrate",
        "understand"
    }

    return words(text) - stopwords


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):

    q_words = words(question)

    detected = []

    for level in BLOOM_LEVELS:

        for verb in BLOOM_VERBS[level]:

            if verb in q_words:

                detected.append(
                    level
                )

                break

    return detected


def get_bloom_level(question):

    detected = detect_bloom(question)

    if not detected:

        return "Unclear"

    # Use the highest detected cognitive level.
    for level in reversed(BLOOM_LEVELS):

        if level in detected:

            return level

    return "Unclear"


# ============================================================
# CLO ALIGNMENT
# ============================================================

def calculate_clo_alignment(
    question,
    clo
):

    q_words = meaningful_words(
        question
    )

    clo_words = meaningful_words(
        clo
    )

    if not clo_words:

        return 0

    overlap = q_words.intersection(
        clo_words
    )

    ratio = (
        len(overlap)
        /
        max(
            1,
            len(clo_words)
        )
    )

    if ratio >= 0.50:
        return 95

    if ratio >= 0.30:
        return 80

    if ratio >= 0.15:
        return 60

    if ratio > 0:
        return 40

    return 25


def find_best_clo(
    question,
    clos
):

    results = []

    for clo in clos:

        score = calculate_clo_alignment(
            question,
            clo
        )

        results.append(
            (
                score,
                clo
            )
        )

    if not results:

        return 0, ""

    return max(
        results,
        key=lambda x: x[0]
    )


# ============================================================
# PLO ALIGNMENT
# ============================================================

def calculate_plo_alignment(
    clo,
    plo
):

    clo_words = meaningful_words(
        clo
    )

    plo_words = meaningful_words(
        plo
    )

    if not plo_words:

        return 0

    overlap = clo_words.intersection(
        plo_words
    )

    ratio = (
        len(overlap)
        /
        max(
            1,
            len(plo_words)
        )
    )

    if ratio >= 0.50:
        return 90

    if ratio >= 0.30:
        return 75

    if ratio >= 0.15:
        return 55

    if ratio > 0:
        return 40

    return 25


def find_best_plo(
    clo,
    plos
):

    if not plos:

        return 0, ""

    results = []

    for plo in plos:

        score = calculate_plo_alignment(
            clo,
            plo
        )

        results.append(
            (
                score,
                plo
            )
        )

    return max(
        results,
        key=lambda x: x[0]
    )


# ============================================================
# MARKS DETECTION
# ============================================================

def detect_marks(question):

    patterns = [
        r"\((\d+)\s*marks?\)",
        r"\[(\d+)\s*marks?\]",
        r"(\d+)\s*marks?",
        r"(\d+)\s*mark"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            question,
            re.IGNORECASE
        )

        if match:

            try:
                return int(
                    match.group(1)
                )
            except Exception:
                pass

    return None


def marks_alignment(question):

    marks = detect_marks(
        question
    )

    if marks is None:

        return (
            70,
            "Marks were not detected. "
            "Please verify them manually."
        )

    bloom = get_bloom_level(
        question
    )

    if bloom in [
        "Remember",
        "Understand"
    ]:

        if marks <= 5:

            return (
                95,
                f"{marks} marks appears reasonable "
                "for this cognitive demand."
            )

        return (
            70,
            f"{marks} marks may be high for a "
            f"{bloom}-level question."
        )

    if bloom in [
        "Apply",
        "Analyze"
    ]:

        if 3 <= marks <= 10:

            return (
                95,
                f"{marks} marks appears broadly "
                "reasonable for the task."
            )

        return (
            75,
            f"Review whether {marks} marks "
            "matches the expected response."
        )

    if bloom in [
        "Evaluate",
        "Create"
    ]:

        if marks >= 5:

            return (
                95,
                f"{marks} marks may be appropriate "
                "for a higher-order task."
            )

        return (
            65,
            "A higher-order task may require "
            "more marks depending on the expected response."
        )

    return (
        70,
        "Review marks against the expected response."
    )


# ============================================================
# EXPECTED BLOOM MAPPING
# ============================================================

def parse_bloom_mapping(text):

    mapping = {}

    for line in text.splitlines():

        if ":" not in line:
            continue

        key, value = line.split(
            ":",
            1
        )

        key = key.strip()

        value = value.strip()

        if key and value:

            mapping[key] = value

    return mapping


def expected_bloom_for_clo(
    clo,
    mapping
):

    for key, level in mapping.items():

        if key.lower() in clo.lower():

            return level

    return ""


# ============================================================
# SUGGESTION ENGINE
# ============================================================

def generate_suggestion(
    question,
    clo,
    expected_bloom,
    detected_bloom,
    clo_score,
    bloom_score,
    plo_score,
    marks_score
):

    suggestions = []

    if clo_score < 70:

        suggestions.append(
            "Make the question more directly measure "
            "the stated CLO instead of only mentioning "
            "the topic."
        )

    if expected_bloom:

        if detected_bloom == "Unclear":

            suggestions.append(
                f"Use a clearer action verb associated "
                f"with {expected_bloom}."
            )

        elif detected_bloom != expected_bloom:

            suggestions.append(
                f"The question appears to operate at "
                f"{detected_bloom}, while the intended "
                f"level is {expected_bloom}. "
                f"Revise the cognitive task rather than "
                f"only changing the verb."
            )

    if plo_score < 60:

        suggestions.append(
            "Check whether the selected CLO is genuinely "
            "connected to the intended PLO."
        )

    if marks_score < 70:

        suggestions.append(
            "Review the marks in relation to the "
            "complexity and expected length of the answer."
        )

    if not suggestions:

        suggestions.append(
            "No major issue was detected by the "
            "initial checker. Faculty review is still required."
        )

    return " ".join(
        suggestions
    )


# ============================================================
# OPTIONAL AI REVIEW
# ============================================================

def run_ai_review(
    course,
    clos,
    plos,
    bloom_mapping,
    questions
):

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    try:

        if "OPENAI_API_KEY" in st.secrets:

            api_key = st.secrets[
                "OPENAI_API_KEY"
            ]

    except Exception:
        pass

    if not api_key:

        return None

    try:

        from openai import OpenAI

        client = OpenAI(
            api_key=api_key
        )

        prompt = f"""
You are an expert in Outcome-Based Education.

Evaluate this existing quiz for assessment alignment.

Course:
{course}

CLOs:
{json.dumps(clos, ensure_ascii=False)}

PLOs:
{json.dumps(plos, ensure_ascii=False)}

Expected Bloom mapping:
{json.dumps(bloom_mapping, ensure_ascii=False)}

Questions:
{json.dumps(questions, ensure_ascii=False)}

For every question evaluate:

- CLO alignment
- PLO alignment
- Bloom's Taxonomy level
- Marks/cognitive demand
- Clarity
- Whether the question actually measures the CLO
- Whether the cognitive demand matches the intended Bloom level
- Specific improvement suggestion
- Suggested revised question when useful

Do not judge based only on matching words.

Return valid JSON only:

{{
    "overall_score": 0,
    "summary": "",
    "strengths": [],
    "priority_issues": [],
    "questions": [
        {{
            "number": 1,
            "clo_alignment": 0,
            "plo_alignment": 0,
            "bloom_alignment": 0,
            "marks_alignment": 0,
            "identified_bloom": "",
            "clo_comment": "",
            "plo_comment": "",
            "bloom_comment": "",
            "marks_comment": "",
            "suggestion": "",
            "revised_question": ""
        }}
    ]
}}

Do not invent information.
The faculty member makes the final academic decision.
"""

        response = client.responses.create(
            model="gpt-5-mini",
            input=prompt
        )

        result = response.output_text.strip()

        result = re.sub(
            r"^```json",
            "",
            result
        )

        result = re.sub(
            r"```$",
            "",
            result
        )

        return json.loads(
            result.strip()
        )

    except Exception as error:

        st.warning(
            f"AI semantic review was not available. "
            f"The built-in checker will still be used. "
            f"Details: {error}"
        )

        return None


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "⚙️ Assessment Setup"
    )

    course = st.text_input(
        "📚 Course Name",
        placeholder="Example: English I"
    )

    st.markdown(
        "### 🎯 CLOs"
    )

    clo_input = st.text_area(
        "Enter one CLO per line",
        height=180,
        placeholder=(
            "CLO1: Identify main ideas in a text.\n"
            "CLO2: Analyze patterns of organization.\n"
            "CLO3: Evaluate author's purpose and tone."
        )
    )

    st.markdown(
        "### 🔗 PLOs"
    )

    plo_input = st.text_area(
        "Enter one PLO per line",
        height=150,
        placeholder=(
            "PLO1: Communication Skills\n"
            "PLO2: Critical Thinking\n"
            "PLO3: Problem Analysis"
        )
    )

    st.markdown(
        "### 🧠 Intended Bloom Levels"
    )

    bloom_input = st.text_area(
        "Optional",
        height=120,
        placeholder=(
            "CLO1: Understand\n"
            "CLO2: Analyze\n"
            "CLO3: Evaluate"
        )
    )

    st.caption(
        "You can leave Bloom mapping empty. "
        "The tool will still identify the apparent "
        "Bloom level of each question."
    )


# ============================================================
# FILE UPLOAD
# ============================================================

st.header(
    "📄 1. Upload Existing Quiz"
)

uploaded_file = st.file_uploader(
    "Choose your quiz/exam file",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "txt"
    ]
)


if uploaded_file:

    with st.spinner(
        "Reading your assessment..."
    ):

        quiz_text = extract_file(
            uploaded_file
        )

    if not quiz_text.strip():

        st.error(
            "No readable text could be extracted "
            "from this file."
        )

        st.stop()

    questions = parse_questions(
        quiz_text
    )

    st.success(
        f"Assessment uploaded successfully. "
        f"{len(questions)} question(s) detected."
    )

    with st.expander(
        "👀 Preview Uploaded Assessment"
    ):

        st.text(
            quiz_text[:12000]
        )

    st.divider()

    # ========================================================
    # EVALUATION BUTTON
    # ========================================================

    if st.button(
        "🚀 CHECK OBE ALIGNMENT",
        type="primary",
        use_container_width=True
    ):

        clos = [
            x.strip()
            for x in clo_input.splitlines()
            if x.strip()
        ]

        plos = [
            x.strip()
            for x in plo_input.splitlines()
            if x.strip()
        ]

        bloom_mapping = parse_bloom_mapping(
            bloom_input
        )

        if not clos:

            st.error(
                "Please enter at least one CLO "
                "in the sidebar."
            )

            st.stop()

        results = []

        for index, question in enumerate(
            questions,
            start=1
        ):

            clo_score, best_clo = find_best_clo(
                question,
                clos
            )

            plo_score, best_plo = find_best_plo(
                best_clo,
                plos
            )

            detected_bloom = get_bloom_level(
                question
            )

            expected_bloom = (
                expected_bloom_for_clo(
                    best_clo,
                    bloom_mapping
                )
            )

            if expected_bloom:

                if (
                    detected_bloom.lower()
                    ==
                    expected_bloom.lower()
                ):

                    bloom_score = 100

                elif detected_bloom == "Unclear":

                    bloom_score = 40

                else:

                    bloom_score = 50

            else:

                bloom_score = (
                    85
                    if detected_bloom != "Unclear"
                    else 55
                )

            marks_score, marks_message = (
                marks_alignment(
                    question
                )
            )

            overall = round(
                (
                    clo_score
                    +
                    plo_score
                    +
                    bloom_score
                    +
                    marks_score
                )
                / 4
            )

            suggestion = generate_suggestion(
                question,
                best_clo,
                expected_bloom,
                detected_bloom,
                clo_score,
                bloom_score,
                plo_score,
                marks_score
            )

            results.append({

                "number": index,

                "question": question,

                "clo": best_clo,

                "clo_score": clo_score,

                "plo": best_plo,

                "plo_score": plo_score,

                "expected_bloom":
                    expected_bloom
                    if expected_bloom
                    else "Not specified",

                "detected_bloom":
                    detected_bloom,

                "bloom_score":
                    bloom_score,

                "marks_score":
                    marks_score,

                "marks_message":
                    marks_message,

                "overall":
                    overall,

                "suggestion":
                    suggestion
            })

        # ====================================================
        # AI REVIEW
        # ====================================================

        with st.spinner(
            "Performing deeper semantic review..."
        ):

            ai_result = run_ai_review(
                course,
                clos,
                plos,
                bloom_mapping,
                questions
            )

        st.session_state[
            "results"
        ] = results

        st.session_state[
            "ai_result"
        ] = ai_result


# ============================================================
# DISPLAY RESULTS
# ============================================================

if "results" in st.session_state:

    results = st.session_state[
        "results"
    ]

    ai_result = st.session_state.get(
        "ai_result"
    )

    st.divider()

    st.header(
        "📊 OBE Alignment Report"
    )

    # ========================================================
    # SCORE
    # ========================================================

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
                item["overall"]
                for item in results
            )
            /
            max(
                1,
                len(results)
            )
        )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "🎯 Overall Alignment",
            f"{overall_score}%"
        )

    with c2:

        st.metric(
            "📝 Questions",
            len(results)
        )

    with c3:

        strong = sum(
            1
            for item in results
            if item["overall"] >= 80
        )

        st.metric(
            "🟢 Strong",
            strong
        )

    with c4:

        review = sum(
            1
            for item in results
            if item["overall"] < 65
        )

        st.metric(
            "🔴 Review Needed",
            review
        )


    # ========================================================
    # SUMMARY
    # ========================================================

    if ai_result:

        st.subheader(
            "🤖 AI Summary"
        )

        summary = ai_result.get(
            "summary",
            ""
        )

        if summary:

            st.info(
                summary
            )

        col1, col2 = st.columns(2)

        with col1:

            st.markdown(
                "### ✅ Strengths"
            )

            for item in ai_result.get(
                "strengths",
                []
            ):

                st.write(
                    "• " + item
                )

        with col2:

            st.markdown(
                "### ⚠️ Priority Issues"
            )

            for item in ai_result.get(
                "priority_issues",
                []
            ):

                st.write(
                    "• " + item
                )


    # ========================================================
    # QUESTION TABLE
    # ========================================================

    st.subheader(
        "📋 Question-Level Overview"
    )

    table_data = []

    for item in results:

        table_data.append({

            "Q":
                item["number"],

            "CLO":
                item["clo"],

            "CLO %":
                item["clo_score"],

            "PLO":
                item["plo"],

            "PLO %":
                item["plo_score"],

            "Expected Bloom":
                item["expected_bloom"],

            "Detected Bloom":
                item["detected_bloom"],

            "Bloom %":
                item["bloom_score"],

            "Marks %":
                item["marks_score"],

            "Overall %":
                item["overall"]
        })

    if pd is not None:

        dataframe = pd.DataFrame(
            table_data
        )

        st.dataframe(
            dataframe,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.write(
            table_data
        )


    # ========================================================
    # DETAILED REVIEW
    # ========================================================

    st.divider()

    st.header(
        "🔎 Detailed Question Review"
    )

    ai_questions = {}

    if ai_result:

        for item in ai_result.get(
            "questions",
            []
        ):

            ai_questions[
                item.get(
                    "number"
                )
            ] = item

    for item in results:

        number = item["number"]

        with st.expander(
            f"Question {number} — "
            f"{item['overall']}% Alignment"
        ):

            st.markdown(
                "### 📄 Original Question"
            )

            st.info(
                item["question"]
            )

            st.markdown(
                "### 🎯 CLO"
            )

            st.write(
                item["clo"]
            )

            st.progress(
                min(
                    100,
                    item["clo_score"]
                )
                / 100
            )

            st.write(
                f"CLO Alignment: "
                f"{item['clo_score']}%"
            )

            st.markdown(
                "### 🔗 PLO"
            )

            if item["plo"]:

                st.write(
                    item["plo"]
                )

            else:

                st.write(
                    "No PLO was provided."
                )

            st.write(
                f"PLO Alignment: "
                f"{item['plo_score']}%"
            )

            st.markdown(
                "### 🧠 Bloom's Taxonomy"
            )

            b1, b2 = st.columns(2)

            with b1:

                st.write(
                    "**Expected:** "
                    + item["expected_bloom"]
                )

            with b2:

                st.write(
                    "**Detected:** "
                    + item["detected_bloom"]
                )

            st.write(
                f"Bloom Alignment: "
                f"{item['bloom_score']}%"
            )

            st.markdown(
                "### ⚖️ Marks"
            )

            st.write(
                item["marks_message"]
            )

            st.write(
                f"Marks Alignment: "
                f"{item['marks_score']}%"
            )

            st.divider()

            # =================================================
            # AI DETAIL
            # =================================================

            if number in ai_questions:

                ai_item = ai_questions[
                    number
                ]

                st.markdown(
                    "### 🤖 AI Analysis"
                )

                st.write(
                    ai_item.get(
                        "clo_comment",
                        ""
                    )
                )

                st.write(
                    ai_item.get(
                        "plo_comment",
                        ""
                    )
                )

                st.write(
                    ai_item.get(
                        "bloom_comment",
                        ""
                    )
                )

                st.write(
                    ai_item.get(
                        "marks_comment",
                        ""
                    )
                )

                st.markdown(
                    "### 💡 Detailed Suggestion"
                )

                st.warning(
                    ai_item.get(
                        "suggestion",
                        ""
                    )
                )

                revised = ai_item.get(
                    "revised_question",
                    ""
                )

                if revised:

                    st.markdown(
                        "### ✏️ Suggested Revision"
                    )

                    st.success(
                        revised
                    )

            else:

                st.markdown(
                    "### 💡 Detailed Suggestion"
                )

                st.warning(
                    item["suggestion"]
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
        for level in BLOOM_LEVELS
    }

    bloom_counts[
        "Unclear"
    ] = 0

    for item in results:

        level = item[
            "detected_bloom"
        ]

        if level in bloom_counts:

            bloom_counts[
                level
            ] += 1

        else:

            bloom_counts[
                "Unclear"
            ] += 1

    if pd is not None:

        bloom_df = pd.DataFrame({

            "Bloom Level":
                list(
                    bloom_counts.keys()
                ),

            "Number of Questions":
                list(
                    bloom_counts.values()
                )
        })

        st.bar_chart(
            bloom_df.set_index(
                "Bloom Level"
            )
        )


    # ========================================================
    # CLO COVERAGE
    # ========================================================

    st.header(
        "🎯 CLO Coverage"
    )

    clo_counts = {}

    for item in results:

        clo = item["clo"]

        if clo:

            clo_counts[
                clo
            ] = clo_counts.get(
                clo,
                0
            ) + 1

    if clo_counts:

        if pd is not None:

            clo_df = pd.DataFrame({

                "CLO":
                    list(
                        clo_counts.keys()
                    ),

                "Questions":
                    list(
                        clo_counts.values()
                    )
            })

            st.dataframe(
                clo_df,
                use_container_width=True,
                hide_index=True
            )


    # ========================================================
    # FINAL FACULTY CHECK
    # ========================================================

    st.divider()

    st.header(
        "👩‍🏫 Faculty Review Checklist"
    )

    st.caption(
        "The tool provides recommendations. "
        "The teacher makes the final academic decision."
    )

    checklist = [

        "Each question measures the intended CLO.",

        "The cognitive demand matches the intended Bloom level.",

        "The CLO is appropriately connected to the PLO.",

        "Marks are appropriate for the expected response.",

        "Questions are based on taught content.",

        "Questions are clear and unambiguous.",

        "The assessment provides reasonable coverage of the CLOs.",

        "Questions identified for revision have been reviewed."
    ]

    for i, statement in enumerate(
        checklist
    ):

        st.checkbox(
            statement,
            key=f"check_{i}"
        )

    st.success(
        "🎓 Final principle: AI assists assessment review; "
        "academic judgment remains with the faculty member."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "OBE Alignment Checker • "
    "CLO • PLO • Bloom's Taxonomy • Assessment Review"
)
````
