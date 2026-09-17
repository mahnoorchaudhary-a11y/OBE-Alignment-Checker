```python
import streamlit as st
import re
import os
import json

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
# PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="OBE Alignment Checker",
    page_icon="🎯",
    layout="wide"
)


# ============================================================
# HEADER
# ============================================================

st.title("🎯 OBE Alignment Checker")

st.write(
    "Upload an existing quiz and review its alignment with "
    "CLOs, PLOs, Bloom's Taxonomy, and marks."
)


# ============================================================
# BLOOM TAXONOMY
# ============================================================

BLOOM = {
    "Remember": [
        "define", "identify", "list", "name",
        "recall", "state", "mention"
    ],

    "Understand": [
        "describe", "explain", "summarize",
        "interpret", "classify", "discuss"
    ],

    "Apply": [
        "apply", "calculate", "demonstrate",
        "use", "solve", "implement"
    ],

    "Analyze": [
        "analyze", "analyse", "compare",
        "contrast", "differentiate",
        "examine", "investigate"
    ],

    "Evaluate": [
        "evaluate", "assess", "justify",
        "critique", "judge", "defend",
        "argue", "recommend"
    ],

    "Create": [
        "create", "design", "develop",
        "construct", "formulate",
        "propose", "produce"
    ]
}

BLOOM_LEVELS = list(BLOOM.keys())


# ============================================================
# FILE READING
# ============================================================

def read_pdf(file):

    if PdfReader is None:
        return ""

    try:
        reader = PdfReader(file)

        text = []

        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:
                text.append(page_text)

        return "\n".join(text)

    except Exception as e:

        st.error(
            f"Could not read PDF: {e}"
        )

        return ""


def read_docx(file):

    if Document is None:
        return ""

    try:

        document = Document(file)

        text = []

        for paragraph in document.paragraphs:

            if paragraph.text.strip():

                text.append(
                    paragraph.text.strip()
                )

        for table in document.tables:

            for row in table.rows:

                cells = []

                for cell in row.cells:

                    cells.append(
                        cell.text.strip()
                    )

                text.append(
                    " | ".join(cells)
                )

        return "\n".join(text)

    except Exception as e:

        st.error(
            f"Could not read Word file: {e}"
        )

        return ""


def read_excel(file):

    if pd is None:
        return ""

    try:

        sheets = pd.read_excel(
            file,
            sheet_name=None
        )

        text = []

        for sheet_name, dataframe in sheets.items():

            text.append(
                f"Sheet: {sheet_name}"
            )

            dataframe = dataframe.fillna("")

            text.append(
                dataframe.to_string(
                    index=False
                )
            )

        return "\n".join(text)

    except Exception as e:

        st.error(
            f"Could not read Excel file: {e}"
        )

        return ""


def read_txt(file):

    try:

        return file.read().decode(
            "utf-8",
            errors="ignore"
        )

    except Exception as e:

        st.error(
            f"Could not read text file: {e}"
        )

        return ""


def read_file(file):

    name = file.name.lower()

    if name.endswith(".pdf"):
        return read_pdf(file)

    if name.endswith(".docx"):
        return read_docx(file)

    if name.endswith(".xlsx"):
        return read_excel(file)

    if name.endswith(".xls"):
        return read_excel(file)

    if name.endswith(".txt"):
        return read_txt(file)

    return ""


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):

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

    current = ""

    pattern = re.compile(
        r"^(?:question\s*|q\s*)?"
        r"(\d+)"
        r"[\.\):\-]\s*(.*)$",
        re.IGNORECASE
    )

    for line in lines:

        match = pattern.match(line)

        if match:

            if current:

                questions.append(
                    current.strip()
                )

            current = match.group(2).strip()

        else:

            if current:

                current += " " + line

    if current:

        questions.append(
            current.strip()
        )

    # If numbering was not detected,
    # split by paragraphs.

    if len(questions) <= 1:

        paragraphs = re.split(
            r"\n\s*\n",
            text
        )

        paragraphs = [
            p.strip()
            for p in paragraphs
            if p.strip()
        ]

        if len(paragraphs) > 1:

            questions = paragraphs

    return questions


# ============================================================
# WORD PROCESSING
# ============================================================

STOPWORDS = {
    "the", "a", "an", "of", "to", "and",
    "in", "on", "for", "with", "by",
    "from", "is", "are", "was", "were",
    "be", "been", "being", "will",
    "can", "should", "students",
    "student", "able", "demonstrate"
}


def get_words(text):

    return set(
        re.findall(
            r"[a-zA-Z]+",
            text.lower()
        )
    )


def useful_words(text):

    return (
        get_words(text)
        - STOPWORDS
    )


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):

    question_words = get_words(
        question
    )

    found = []

    for level, verbs in BLOOM.items():

        for verb in verbs:

            if verb in question_words:

                found.append(
                    level
                )

                break

    if not found:

        return "Unclear"

    # Return highest detected level
    for level in reversed(BLOOM_LEVELS):

        if level in found:

            return level

    return "Unclear"


# ============================================================
# CLO MATCHING
# ============================================================

def clo_score(
    question,
    clo
):

    q = useful_words(
        question
    )

    c = useful_words(
        clo
    )

    if not c:

        return 0

    overlap = q.intersection(c)

    ratio = (
        len(overlap)
        /
        len(c)
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


def best_clo(
    question,
    clos
):

    if not clos:

        return 0, ""

    results = []

    for clo in clos:

        results.append(
            (
                clo_score(
                    question,
                    clo
                ),
                clo
            )
        )

    return max(
        results,
        key=lambda x: x[0]
    )


# ============================================================
# PLO MATCHING
# ============================================================

def plo_score(
    clo,
    plo
):

    c = useful_words(
        clo
    )

    p = useful_words(
        plo
    )

    if not p:

        return 0

    overlap = c.intersection(p)

    ratio = (
        len(overlap)
        /
        len(p)
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


def best_plo(
    clo,
    plos
):

    if not plos:

        return 0, ""

    results = []

    for plo in plos:

        results.append(
            (
                plo_score(
                    clo,
                    plo
                ),
                plo
            )
        )

    return max(
        results,
        key=lambda x: x[0]
    )


# ============================================================
# MARKS
# ============================================================

def get_marks(question):

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

            return int(
                match.group(1)
            )

    return None


def marks_check(question):

    marks = get_marks(
        question
    )

    if marks is None:

        return (
            70,
            "Marks could not be detected."
        )

    bloom = detect_bloom(
        question
    )

    if bloom in [
        "Remember",
        "Understand"
    ]:

        if marks <= 5:

            return (
                95,
                f"{marks} mark(s) appears reasonable."
            )

        return (
            70,
            f"{marks} marks may be high for "
            f"a {bloom}-level question."
        )

    if bloom in [
        "Apply",
        "Analyze"
    ]:

        if 3 <= marks <= 10:

            return (
                95,
                f"{marks} marks appears reasonable."
            )

        return (
            75,
            f"Review whether {marks} marks "
            "matches the expected answer."
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
            "A higher-order question may require "
            "more marks depending on the expected response."
        )

    return (
        70,
        "Review the marks manually."
    )


# ============================================================
# BLOOM MAPPING
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

        mapping[
            key.strip()
        ] = value.strip()

    return mapping


def expected_bloom(
    clo,
    mapping
):

    for key, value in mapping.items():

        if key.lower() in clo.lower():

            return value

    return ""


# ============================================================
# SUGGESTIONS
# ============================================================

def make_suggestion(
    clo_alignment,
    plo_alignment,
    bloom_alignment,
    marks_alignment,
    expected,
    detected
):

    suggestions = []

    if clo_alignment < 70:

        suggestions.append(
            "Strengthen the connection between "
            "the question and the intended CLO. "
            "The question should measure the learning "
            "outcome, not simply mention the topic."
        )

    if plo_alignment < 60:

        suggestions.append(
            "Review the CLO-PLO connection and confirm "
            "that the question contributes to the intended PLO."
        )

    if expected:

        if detected == "Unclear":

            suggestions.append(
                f"Use a clearer cognitive task "
                f"appropriate for {expected}."
            )

        elif detected.lower() != expected.lower():

            suggestions.append(
                f"The question appears to operate at "
                f"{detected}, while the intended level is "
                f"{expected}. Change the task itself, "
                f"not only the action verb."
            )

    if marks_alignment < 70:

        suggestions.append(
            "Review whether the marks reflect "
            "the complexity and expected response."
        )

    if not suggestions:

        suggestions.append(
            "No major issue was detected. "
            "Faculty should still review the question "
            "for content accuracy and academic suitability."
        )

    return " ".join(
        suggestions
    )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "⚙️ OBE Setup"
    )

    course = st.text_input(
        "📚 Course",
        placeholder="English I"
    )

    st.subheader(
        "🎯 CLOs"
    )

    clo_text = st.text_area(
        "One CLO per line",
        height=180,
        placeholder=(
            "CLO1: Identify main ideas in a text.\n"
            "CLO2: Analyze patterns of organization.\n"
            "CLO3: Evaluate author's purpose and tone."
        )
    )

    st.subheader(
        "🔗 PLOs"
    )

    plo_text = st.text_area(
        "One PLO per line",
        height=150,
        placeholder=(
            "PLO1: Communication Skills\n"
            "PLO2: Critical Thinking\n"
            "PLO3: Problem Analysis"
        )
    )

    st.subheader(
        "🧠 Intended Bloom Levels"
    )

    bloom_text = st.text_area(
        "Optional",
        height=120,
        placeholder=(
            "CLO1: Understand\n"
            "CLO2: Analyze\n"
            "CLO3: Evaluate"
        )
    )


# ============================================================
# UPLOAD
# ============================================================

st.header(
    "📄 Step 1 — Upload Your Existing Quiz"
)

uploaded_file = st.file_uploader(
    "Upload PDF, Word, Excel or TXT",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "txt"
    ]
)


if uploaded_file:

    quiz_text = read_file(
        uploaded_file
    )

    if not quiz_text.strip():

        st.error(
            "The file could not be read."
        )

        st.stop()

    questions = extract_questions(
        quiz_text
    )

    st.success(
        f"{len(questions)} question(s) detected."
    )

    with st.expander(
        "👀 View Extracted Text"
    ):

        st.text(
            quiz_text[:12000]
        )

    st.divider()

    st.header(
        "🔍 Step 2 — Check Alignment"
    )

    if st.button(
        "🚀 CHECK OBE ALIGNMENT",
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

        mapping = parse_bloom_mapping(
            bloom_text
        )

        if not clos:

            st.error(
                "Please enter at least one CLO."
            )

            st.stop()

        results = []

        for number, question in enumerate(
            questions,
            1
        ):

            c_score, matched_clo = best_clo(
                question,
                clos
            )

            p_score, matched_plo = best_plo(
                matched_clo,
                plos
            )

            detected = detect_bloom(
                question
            )

            expected = expected_bloom(
                matched_clo,
                mapping
            )

            if expected:

                if detected.lower() == expected.lower():

                    b_score = 100

                elif detected == "Unclear":

                    b_score = 40

                else:

                    b_score = 50

            else:

                b_score = (
                    85
                    if detected != "Unclear"
                    else 55
                )

            m_score, m_message = marks_check(
                question
            )

            overall = round(
                (
                    c_score
                    +
                    p_score
                    +
                    b_score
                    +
                    m_score
                ) / 4
            )

            suggestion = make_suggestion(
                c_score,
                p_score,
                b_score,
                m_score,
                expected,
                detected
            )

            results.append({

                "number": number,

                "question": question,

                "clo": matched_clo,

                "clo_score": c_score,

                "plo": matched_plo,

                "plo_score": p_score,

                "expected_bloom": (
                    expected
                    if expected
                    else "Not specified"
                ),

                "detected_bloom": detected,

                "bloom_score": b_score,

                "marks_score": m_score,

                "marks_message": m_message,

                "overall": overall,

                "suggestion": suggestion
            })

        st.session_state[
            "results"
        ] = results


# ============================================================
# RESULTS
# ============================================================

if "results" in st.session_state:

    results = st.session_state[
        "results"
    ]

    st.divider()

    st.header(
        "📊 Alignment Report"
    )

    overall = round(
        sum(
            r["overall"]
            for r in results
        )
        /
        max(
            1,
            len(results)
        )
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "🎯 Overall",
            f"{overall}%"
        )

    with col2:

        st.metric(
            "📝 Questions",
            len(results)
        )

    with col3:

        st.metric(
            "🟢 Strong",
            sum(
                1
                for r in results
                if r["overall"] >= 80
            )
        )

    with col4:

        st.metric(
            "🔴 Review",
            sum(
                1
                for r in results
                if r["overall"] < 65
            )
        )


    if overall >= 80:

        st.success(
            "The assessment shows generally strong "
            "alignment based on the initial checks."
        )

    elif overall >= 60:

        st.warning(
            "The assessment shows partial alignment. "
            "Some questions should be reviewed."
        )

    else:

        st.error(
            "Several questions may require revision."
        )


    # ========================================================
    # TABLE
    # ========================================================

    st.subheader(
        "📋 Question Overview"
    )

    table = []

    for r in results:

        table.append({

            "Question":
                r["number"],

            "CLO":
                r["clo"],

            "CLO %":
                r["clo_score"],

            "PLO":
                r["plo"],

            "PLO %":
                r["plo_score"],

            "Expected Bloom":
                r["expected_bloom"],

            "Detected Bloom":
                r["detected_bloom"],

            "Bloom %":
                r["bloom_score"],

            "Marks %":
                r["marks_score"],

            "Overall %":
                r["overall"]
        })

    if pd is not None:

        st.dataframe(
            pd.DataFrame(table),
            use_container_width=True,
            hide_index=True
        )

    # ========================================================
    # DETAILED REVIEW
    # ========================================================

    st.divider()

    st.header(
        "🔎 Detailed Review"
    )

    for r in results:

        with st.expander(
            f"Question {r['number']} — "
            f"{r['overall']}% Alignment"
        ):

            st.markdown(
                "### 📄 Original Question"
            )

            st.info(
                r["question"]
            )

            c1, c2 = st.columns(2)

            with c1:

                st.markdown(
                    "### 🎯 CLO Alignment"
                )

                st.write(
                    r["clo"]
                )

                st.progress(
                    r["clo_score"] / 100
                )

                st.write(
                    f"{r['clo_score']}%"
                )

            with c2:

                st.markdown(
                    "### 🔗 PLO Alignment"
                )

                if r["plo"]:

                    st.write(
                        r["plo"]
                    )

                else:

                    st.write(
                        "No PLO entered."
                    )

                st.progress(
                    r["plo_score"] / 100
                )

                st.write(
                    f"{r['plo_score']}%"
                )


            st.markdown(
                "### 🧠 Bloom's Taxonomy"
            )

            b1, b2, b3 = st.columns(3)

            with b1:

                st.write(
                    "**Expected:**"
                )

                st.write(
                    r["expected_bloom"]
                )

            with b2:

                st.write(
                    "**Detected:**"
                )

                st.write(
                    r["detected_bloom"]
                )

            with b3:

                st.write(
                    "**Alignment:**"
                )

                st.write(
                    f"{r['bloom_score']}%"
                )


            st.markdown(
                "### ⚖️ Marks"
            )

            st.write(
                r["marks_message"]
            )

            st.write(
                f"Marks alignment: "
                f"{r['marks_score']}%"
            )


            st.markdown(
                "### 💡 Detailed Suggestion"
            )

            st.warning(
                r["suggestion"]
            )


            st.markdown(
                "### ✏️ Teacher Revision"
            )

            revised = st.text_area(
                "You can edit the question here:",
                value=r["question"],
                key=f"revision_{r['number']}",
                height=120
            )

            if st.button(
                "🔍 Re-check Revised Question",
                key=f"recheck_{r['number']}"
            ):

                new_clo_score, new_clo = best_clo(
                    revised,
                    [
                        x.strip()
                        for x in clo_text.splitlines()
                        if x.strip()
                    ]
                )

                new_bloom = detect_bloom(
                    revised
                )

                st.success(
                    "Revised question checked."
                )

                st.write(
                    f"Possible CLO: {new_clo}"
                )

                st.write(
                    f"Detected Bloom level: {new_bloom}"
                )

                st.write(
                    f"CLO alignment: "
                    f"{new_clo_score}%"
                )


    # ========================================================
    # BLOOM DISTRIBUTION
    # ========================================================

    st.divider()

    st.header(
        "🧠 Bloom's Distribution"
    )

    bloom_counts = {
        level: 0
        for level in BLOOM_LEVELS
    }

    bloom_counts["Unclear"] = 0

    for r in results:

        level = r[
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

            "Questions":
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

    coverage = {}

    for r in results:

        clo = r["clo"]

        if clo:

            coverage[clo] = (
                coverage.get(
                    clo,
                    0
                ) + 1
            )

    if coverage:

        if pd is not None:

            coverage_df = pd.DataFrame({

                "CLO":
                    list(
                        coverage.keys()
                    ),

                "Questions":
                    list(
                        coverage.values()
                    )
            })

            st.dataframe(
                coverage_df,
                use_container_width=True,
                hide_index=True
            )


    # ========================================================
    # FACULTY CHECKLIST
    # ========================================================

    st.divider()

    st.header(
        "👩‍🏫 Faculty Final Review"
    )

    st.write(
        "Use the results as a review aid. "
        "The teacher should make the final academic decision."
    )

    checklist = [

        "Does the question actually measure the intended CLO?",

        "Does the cognitive task match the intended Bloom level?",

        "Is the CLO appropriately connected to the PLO?",

        "Are the marks appropriate?",

        "Was the content taught?",

        "Is the question clear and unambiguous?",

        "Is the CLO coverage balanced?",

        "Have all flagged questions been reviewed?"
    ]

    for i, item in enumerate(checklist):

        st.checkbox(
            item,
            key=f"faculty_{i}"
        )


st.divider()

st.caption(
    "OBE Alignment Checker • "
    "CLO • PLO • Bloom's Taxonomy • "
    "Assessment Quality Review"
)
```
