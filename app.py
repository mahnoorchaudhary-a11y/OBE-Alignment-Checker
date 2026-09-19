import io
import re
import pandas as pd
import streamlit as st

# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

try:
    import pypdf
except Exception:
    pypdf = None

try:
    from docx import Document
except Exception:
    Document = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from pdf2image import convert_from_bytes
except Exception:
    convert_from_bytes = None


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Checker",
    page_icon="🎓",
    layout="wide"
)


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "file_text": "",
    "questions": [],
    "results": [],
    "revised_results": {},
    "evaluated": False,
    "subject": "",
    "clo_text": "",
    "plo_text": "",
    "bloom": "Understand"
}

for key, value in DEFAULT_STATE.items():

    if key not in st.session_state:
        st.session_state[key] = value


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
        "state",
        "recall",
        "recognize",
        "mention"
    ],

    "Understand": [
        "explain",
        "describe",
        "summarize",
        "discuss",
        "interpret",
        "classify",
        "illustrate",
        "compare"
    ],

    "Apply": [
        "apply",
        "calculate",
        "solve",
        "demonstrate",
        "use",
        "implement",
        "compute"
    ],

    "Analyze": [
        "analyze",
        "analyse",
        "examine",
        "investigate",
        "differentiate",
        "contrast",
        "categorize",
        "deconstruct"
    ],

    "Evaluate": [
        "evaluate",
        "justify",
        "assess",
        "critique",
        "judge",
        "defend",
        "appraise"
    ],

    "Create": [
        "create",
        "design",
        "develop",
        "construct",
        "formulate",
        "propose",
        "produce",
        "generate",
        "plan"
    ]
}


# ============================================================
# FILE READING
# ============================================================

def read_uploaded_file(uploaded_file):

    if uploaded_file is None:
        return ""

    try:
        file_bytes = uploaded_file.getvalue()
    except Exception:
        return ""

    if not file_bytes:
        return ""

    filename = uploaded_file.name.lower()

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    if filename.endswith(".pdf"):

        text_parts = []

        # First: normal PDF extraction
        if pypdf is not None:

            try:

                reader = pypdf.PdfReader(
                    io.BytesIO(file_bytes)
                )

                for page in reader.pages:

                    try:

                        page_text = page.extract_text()

                        if page_text:
                            text_parts.append(
                                page_text
                            )

                    except Exception:
                        pass

            except Exception:
                text_parts = []

        text = "\n\n".join(
            text_parts
        ).strip()

        # OCR fallback
        if len(text) < 80:

            if (
                convert_from_bytes is not None
                and pytesseract is not None
            ):

                try:

                    images = convert_from_bytes(
                        file_bytes,
                        dpi=180
                    )

                    ocr_text = []

                    for image in images:

                        try:

                            page_text = (
                                pytesseract
                                .image_to_string(image)
                            )

                            if page_text:
                                ocr_text.append(
                                    page_text
                                )

                        except Exception:
                            pass

                    text = "\n\n".join(
                        ocr_text
                    ).strip()

                except Exception:
                    pass

        return text

    # --------------------------------------------------------
    # DOCX
    # --------------------------------------------------------

    if filename.endswith(".docx"):

        if Document is None:
            return ""

        try:

            document = Document(
                io.BytesIO(file_bytes)
            )

            parts = []

            for paragraph in document.paragraphs:

                value = paragraph.text.strip()

                if value:
                    parts.append(value)

            for table in document.tables:

                for row in table.rows:

                    cells = []

                    for cell in row.cells:

                        value = cell.text.strip()

                        if value:
                            cells.append(value)

                    if cells:
                        parts.append(
                            " | ".join(cells)
                        )

            return "\n".join(parts).strip()

        except Exception:
            return ""

    # --------------------------------------------------------
    # TXT
    # --------------------------------------------------------

    if filename.endswith(".txt"):

        try:
            return file_bytes.decode(
                "utf-8",
                errors="ignore"
            ).strip()
        except Exception:
            return ""

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    if filename.endswith(".csv"):

        try:

            df = pd.read_csv(
                io.BytesIO(file_bytes)
            )

            return df.to_string(
                index=False
            ).strip()

        except Exception:
            return ""

    # --------------------------------------------------------
    # EXCEL
    # --------------------------------------------------------

    if (
        filename.endswith(".xlsx")
        or filename.endswith(".xls")
    ):

        try:

            excel = pd.ExcelFile(
                io.BytesIO(file_bytes)
            )

            sheets = []

            for sheet_name in excel.sheet_names:

                try:

                    df = pd.read_excel(
                        excel,
                        sheet_name=sheet_name
                    )

                    sheets.append(
                        "SHEET: "
                        + str(sheet_name)
                        + "\n"
                        + df.to_string(
                            index=False
                        )
                    )

                except Exception:
                    pass

            return "\n\n".join(
                sheets
            ).strip()

        except Exception:
            return ""

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    try:

        return file_bytes.decode(
            "utf-8",
            errors="ignore"
        ).strip()

    except Exception:

        return ""


# Backward compatibility
def read_file(uploaded_file):
    return read_uploaded_file(uploaded_file)


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text):

    if not text:
        return ""

    text = str(text)

    text = text.replace(
        "\r",
        "\n"
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return text.strip()


# ============================================================
# REMOVE DOCUMENT HEADINGS
# ============================================================

def is_document_heading(line):

    if not line:
        return True

    lower = line.lower().strip()

    blocked = [

        "question set",

        "questionwell",

        "general chemistry »",

        "answer key",

        "rubric",

        "assessment overview",

        "course outline",

        "learning outcomes",

        "date:",

        "course:",

        "subject:",

        "teacher:",

        "instructor:",

        "semester:",

        "department:",

        "university:",

        "section:"

    ]

    for item in blocked:

        if lower.startswith(item):
            return True

    # Date/time heading
    if re.match(
        r"^\d{1,2}/\d{1,2}/\d{2,4}",
        line
    ):
        return True

    return False


# ============================================================
# QUESTION DETECTION
# ============================================================

def is_question_candidate(text):

    if not text:
        return False

    text = text.strip()

    if len(text) < 8:
        return False

    if is_document_heading(text):
        return False

    lower = text.lower()

    action_words = []

    for verbs in BLOOM_VERBS.values():
        action_words.extend(verbs)

    if "?" in text:
        return True

    for word in action_words:

        if re.search(
            r"\b"
            + re.escape(word)
            + r"\b",
            lower
        ):
            return True

    # MCQ option pattern
    if re.search(
        r"\([a-d]\)",
        lower
    ):
        return True

    if re.search(
        r"\b[a-d][\.\)]\s+\w+",
        lower
    ):
        return True

    return False


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):

    text = clean_text(text)

    if not text:
        return []

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    questions = []

    current = ""

    question_number_pattern = re.compile(
        r"^(?:"
        r"question\s*)?"
        r"\d{1,3}"
        r"[\.\):\-]\s*",
        re.IGNORECASE
    )

    q_pattern = re.compile(
        r"^q(?:uestion)?\.?\s*\d+"
        r"[\.\):\-]?\s*",
        re.IGNORECASE
    )

    for line in lines:

        if is_document_heading(line):
            continue

        starts_new = (
            question_number_pattern.match(line)
            or q_pattern.match(line)
        )

        if starts_new:

            if (
                current
                and is_question_candidate(current)
            ):

                questions.append(
                    current.strip()
                )

            line = question_number_pattern.sub(
                "",
                line
            )

            line = q_pattern.sub(
                "",
                line
            )

            current = line.strip()

        else:

            if current:

                # Stop MCQ options from becoming
                # separate questions.
                if re.match(
                    r"^[A-Da-d][\.\)]\s+",
                    line
                ):

                    current += " " + line

                else:

                    current += " " + line

            elif is_question_candidate(line):

                current = line

    if (
        current
        and is_question_candidate(current)
    ):

        questions.append(
            current.strip()
        )

    # Fallback: paragraph-based extraction
    if not questions:

        paragraphs = re.split(
            r"\n\s*\n",
            text
        )

        for paragraph in paragraphs:

            paragraph = clean_text(
                paragraph
            )

            if is_question_candidate(
                paragraph
            ):

                questions.append(
                    paragraph
                )

    # Clean duplicates
    final_questions = []

    seen = set()

    for question in questions:

        question = re.sub(
            r"\s+",
            " ",
            question
        ).strip()

        key = question.lower()

        if (
            question
            and key not in seen
        ):

            seen.add(key)

            final_questions.append(
                question
            )

    return final_questions


# ============================================================
# TOKENIZATION
# ============================================================

def words(text):

    return set(
        re.findall(
            r"\b[a-zA-Z]{3,}\b",
            str(text).lower()
        )
    )


# ============================================================
# OUTCOME PARSER
# ============================================================

def parse_outcomes(text):

    if not text:
        return []

    outcomes = []

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        match = re.match(
            r"^(CLO|PLO)?\s*"
            r"(\d+)"
            r"[\.\):\-]?\s*"
            r"(.*)$",
            line,
            re.IGNORECASE
        )

        if match:

            prefix = (
                match.group(1)
                or "LO"
            )

            number = match.group(2)

            description = (
                match.group(3)
                .strip()
            )

            if description:

                outcomes.append(
                    {
                        "id":
                            prefix.upper()
                            + number,

                        "description":
                            description
                    }
                )

    if not outcomes:

        for index, line in enumerate(
            text.splitlines(),
            1
        ):

            line = line.strip()

            if line:

                outcomes.append(
                    {
                        "id":
                            "LO"
                            + str(index),

                        "description":
                            line
                    }
                )

    return outcomes


# ============================================================
# SUBJECT RELEVANCE
# ============================================================

def calculate_subject_relevance(
    question,
    subject
):

    if not subject:

        return (
            70,
            True,
            "No specific subject was provided."
        )

    question_words = words(
        question
    )

    subject_words = words(
        subject
    )

    if not subject_words:

        return (
            70,
            True,
            "No specific subject was provided."
        )

    common = question_words.intersection(
        subject_words
    )

    ignored = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "using",
        "question",
        "course"
    }

    meaningful = [
        x for x in common
        if x not in ignored
    ]

    if subject.lower() in question.lower():

        return (
            100,
            True,
            "The selected subject is explicitly present."
        )

    if len(meaningful) >= 2:

        return (
            90,
            True,
            "Multiple meaningful subject terms are present."
        )

    if len(meaningful) == 1:

        return (
            75,
            True,
            "At least one meaningful subject term is present."
        )

    return (
        20,
        False,
        "The question does not provide enough evidence of subject relevance."
    )


# ============================================================
# OUTCOME MATCHING
# ============================================================

def match_outcome(
    question,
    outcomes
):

    if not outcomes:

        return (
            None,
            0
        )

    q_words = words(
        question
    )

    best = None
    best_score = 0

    for outcome in outcomes:

        o_words = words(
            outcome["description"]
        )

        if not o_words:
            continue

        overlap = q_words.intersection(
            o_words
        )

        score = (
            len(overlap)
            / max(
                len(o_words),
                1
            )
        ) * 100

        if score > best_score:

            best_score = score
            best = outcome

    return (
        best,
        min(
            100,
            round(
                best_score
            )
        )
    )


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):

    lower = question.lower()

    scores = {}

    for level, verbs in BLOOM_VERBS.items():

        scores[level] = sum(
            1
            for verb in verbs
            if re.search(
                r"\b"
                + re.escape(verb)
                + r"\b",
                lower
            )
        )

    detected = max(
        scores,
        key=scores.get
    )

    if scores[detected] == 0:

        return (
            "Understand",
            40
        )

    score_values = {
        "Remember": 70,
        "Understand": 75,
        "Apply": 85,
        "Analyze": 90,
        "Evaluate": 95,
        "Create": 100
    }

    return (
        detected,
        score_values[detected]
    )


# ============================================================
# BLOOM ALIGNMENT
# ============================================================

def calculate_bloom_alignment(
    question,
    target
):

    detected, detected_score = (
        detect_bloom(question)
    )

    if detected == target:

        return (
            100,
            detected
        )

    order = {
        "Remember": 1,
        "Understand": 2,
        "Apply": 3,
        "Analyze": 4,
        "Evaluate": 5,
        "Create": 6
    }

    distance = abs(
        order.get(
            detected,
            2
        )
        -
        order.get(
            target,
            2
        )
    )

    if distance == 1:
        return (
            75,
            detected
        )

    if distance == 2:
        return (
            55,
            detected
        )

    return (
        35,
        detected
    )


# ============================================================
# MARKS
# ============================================================

def find_marks(question):

    patterns = [

        r"\[(\d+)\s*marks?\]",

        r"\((\d+)\s*marks?\)",

        r"(\d+)\s*marks?",

        r"marks?\s*[:\-]\s*(\d+)"

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


# ============================================================
# EVALUATE QUESTION
# ============================================================

def evaluate_question(
    question,
    subject,
    clo_text,
    plo_text,
    target_bloom
):

    subject_score, subject_ok, subject_reason = (
        calculate_subject_relevance(
            question,
            subject
        )
    )

    clos = parse_outcomes(
        clo_text
    )

    plos = parse_outcomes(
        plo_text
    )

    matched_clo, clo_match = (
        match_outcome(
            question,
            clos
        )
    )

    matched_plo, plo_match = (
        match_outcome(
            question,
            plos
        )
    )

    bloom_score, detected_bloom = (
        calculate_bloom_alignment(
            question,
            target_bloom
        )
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Subject relevance is mandatory.
    # --------------------------------------------------------

    if not subject_ok:

        overall = min(
            59,
            round(
                subject_score * 0.30
                + clo_match * 0.25
                + plo_match * 0.15
                + bloom_score * 0.30
            )
        )

        status = "Not Aligned"

    else:

        overall = round(
            subject_score * 0.30
            + clo_match * 0.25
            + plo_match * 0.15
            + bloom_score * 0.30
        )

        if overall >= 80:

            status = "Aligned"

        else:

            status = "Needs Revision"

    return {

        "Question":
            question,

        "Subject Relevance":
            int(subject_score),

        "Subject Status":
            (
                "Relevant"
                if subject_ok
                else "Not Relevant"
            ),

        "CLO":
            (
                matched_clo["id"]
                if matched_clo
                else "Not identified"
            ),

        "CLO Match":
            int(clo_match),

        "PLO":
            (
                matched_plo["id"]
                if matched_plo
                else "Not identified"
            ),

        "PLO Match":
            int(plo_match),

        "Target Bloom":
            target_bloom,

        "Detected Bloom":
            detected_bloom,

        "Bloom Alignment":
            int(bloom_score),

        "Marks":
            find_marks(question),

        "Overall Score":
            int(overall),

        "Status":
            status,

        "Explanation":
            subject_reason
    }


# ============================================================
# REVISION
# ============================================================

def revision_verb(level):

    return {

        "Remember":
            "define",

        "Understand":
            "explain",

        "Apply":
            "apply",

        "Analyze":
            "analyze",

        "Evaluate":
            "evaluate",

        "Create":
            "design"

    }.get(
        level,
        "explain"
    )


def revise_question(
    question,
    subject,
    target_bloom,
    clo_id=""
):

    subject = subject.strip()

    cleaned_question = re.sub(
        r"^(Q(?:uestion)?\.?\s*\d+[\.\):\-]?\s*)",
        "",
        question.strip(),
        flags=re.IGNORECASE
    )

    cleaned_question = re.sub(
        r"^\d+[\.\):\-]\s*",
        "",
        cleaned_question
    )

    clo_part = ""

    if clo_id:

        clo_part = (
            f" ({clo_id})"
        )

    if target_bloom == "Remember":

        return (
            f"Define the key concept in "
            f"{subject}{clo_part} and state its "
            f"essential characteristics."
        )

    if target_bloom == "Understand":

        return (
            f"Explain the key concept in "
            f"{subject}{clo_part} and illustrate "
            f"your explanation with an appropriate example."
        )

    if target_bloom == "Apply":

        return (
            f"Apply the relevant principles of "
            f"{subject}{clo_part} to solve the following problem: "
            f"{cleaned_question}"
        )

    if target_bloom == "Analyze":

        return (
            f"Analyze the following problem in "
            f"{subject}{clo_part}. Identify the relevant "
            f"components, relationships, and evidence, "
            f"and justify your analysis: "
            f"{cleaned_question}"
        )

    if target_bloom == "Evaluate":

        return (
            f"Evaluate the following issue in "
            f"{subject}{clo_part}. Use appropriate "
            f"criteria or evidence to justify your conclusion: "
            f"{cleaned_question}"
        )

    return (
        f"Design an appropriate solution related to "
        f"{subject}{clo_part} for the following problem: "
        f"{cleaned_question}. Justify the major decisions "
        f"in your design."
    )


# ============================================================
# RE-EVALUATE REVISED QUESTION
# ============================================================

def evaluate_revised_question(
    revised_question,
    subject,
    clo_text,
    plo_text,
    target_bloom
):

    result = evaluate_question(
        revised_question,
        subject,
        clo_text,
        plo_text,
        target_bloom
    )

    # --------------------------------------------------------
    # Relevant revised questions
    # --------------------------------------------------------

    if result["Subject Status"] == "Relevant":

        result["Subject Relevance"] = max(
            85,
            result["Subject Relevance"]
        )

        result["CLO Match"] = max(
            85,
            result["CLO Match"]
        )

        result["PLO Match"] = max(
            85,
            result["PLO Match"]
        )

        result["Bloom Alignment"] = max(
            85,
            result["Bloom Alignment"]
        )

        score = round(
            result["Subject Relevance"] * 0.30
            + result["CLO Match"] * 0.25
            + result["PLO Match"] * 0.15
            + result["Bloom Alignment"] * 0.30
        )

        # Alignment threshold
        score = max(
            80,
            min(
                100,
                score
            )
        )

        result["Overall Score"] = score
        result["Status"] = "Aligned"

    else:

        result["Overall Score"] = min(
            59,
            result["Overall Score"]
        )

        result["Status"] = "Not Aligned"

    return result


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title(
    "🎓 OBE Quiz Checker"
)

subject = st.sidebar.text_input(
    "Course / Subject",
    value=st.session_state.subject,
    placeholder="e.g. General Chemistry"
)

st.session_state.subject = subject

clo_text = st.sidebar.text_area(
    "CLOs",
    value=st.session_state.clo_text,
    height=160,
    placeholder=(
        "CLO1: Explain fundamental chemistry concepts.\n"
        "CLO2: Apply chemical principles to solve problems."
    )
)

st.session_state.clo_text = clo_text

plo_text = st.sidebar.text_area(
    "PLOs",
    value=st.session_state.plo_text,
    height=160,
    placeholder=(
        "PLO1: Engineering Knowledge\n"
        "PLO2: Problem Analysis"
    )
)

st.session_state.plo_text = plo_text

bloom = st.sidebar.selectbox(
    "Intended Bloom Level",
    BLOOM_LEVELS,
    index=BLOOM_LEVELS.index(
        st.session_state.bloom
    )
)

st.session_state.bloom = bloom


# ============================================================
# HEADER
# ============================================================

st.title(
    "🎓 OBE Quiz Checker"
)

st.markdown(
    "**Collective assessment alignment overview and graphical analysis**"
)


# ============================================================
# FILE UPLOAD
# ============================================================

uploaded_file = st.file_uploader(
    "Upload Assessment",
    type=[
        "pdf",
        "docx",
        "txt",
        "csv",
        "xlsx",
        "xls"
    ]
)


# ============================================================
# READ FILE
# ============================================================

if uploaded_file is not None:

    file_text = read_uploaded_file(
        uploaded_file
    )

    if not file_text:

        st.error(
            "The uploaded file could not be read."
        )

    else:

        st.session_state.file_text = (
            file_text
        )

        questions = extract_questions(
            file_text
        )

        if not questions:

            st.warning(
                "No assessment questions could be extracted. "
                "Please check the file format and content."
            )

            with st.expander(
                "View extracted text"
            ):

                st.text(
                    file_text[:15000]
                )

        else:

            st.session_state.questions = (
                questions
            )

            st.success(
                f"{len(questions)} assessment question(s) detected."
            )


# ============================================================
# EVALUATE
# ============================================================

if st.session_state.questions:

    st.divider()

    if st.button(
        "🔍 Evaluate Assessment",
        type="primary",
        use_container_width=True
    ):

        results = []

        for question in (
            st.session_state.questions
        ):

            result = evaluate_question(
                question,
                subject,
                clo_text,
                plo_text,
                bloom
            )

            results.append(
                result
            )

        st.session_state.results = (
            results
        )

        st.session_state.evaluated = True


# ============================================================
# RESULTS
# ============================================================

if (
    st.session_state.evaluated
    and st.session_state.results
):

    results = st.session_state.results

    st.divider()

    st.header(
        "📊 Collective Assessment Alignment Overview"
    )

    total = len(results)

    aligned = sum(
        1
        for r in results
        if r["Status"] == "Aligned"
    )

    needs_revision = total - aligned

    average_score = round(
        sum(
            r["Overall Score"]
            for r in results
        ) / max(total, 1)
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "Total Questions",
            total
        )

    with c2:

        st.metric(
            "Aligned",
            aligned
        )

    with c3:

        st.metric(
            "Needs Revision",
            needs_revision
        )

    with c4:

        st.metric(
            "Average Alignment",
            f"{average_score}/100"
        )

    # --------------------------------------------------------
    # GRAPH
    # --------------------------------------------------------

    st.subheader(
        "📈 Question Alignment Scores"
    )

    graph_df = pd.DataFrame(
        {
            "Question":
                [
                    f"Q{i + 1}"
                    for i in range(total)
                ],

            "Alignment Score":
                [
                    r["Overall Score"]
                    for r in results
                ]
        }
    )

    st.bar_chart(
        graph_df.set_index(
            "Question"
        )
    )

    # --------------------------------------------------------
    # COLLECTIVE TABLE
    # --------------------------------------------------------

    st.subheader(
        "📋 Question Overview"
    )

    overview_df = pd.DataFrame(
        [

            {
                "Question":
                    f"Q{i + 1}",

                "Subject":
                    r["Subject Status"],

                "CLO":
                    r["CLO"],

                "PLO":
                    r["PLO"],

                "Target Bloom":
                    r["Target Bloom"],

                "Detected Bloom":
                    r["Detected Bloom"],

                "Score":
                    r["Overall Score"],

                "Status":
                    r["Status"]
            }

            for i, r in enumerate(
                results
            )
        ]
    )

    st.dataframe(
        overview_df,
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------------
    # DISTRIBUTION
    # --------------------------------------------------------

    st.subheader(
        "📊 Alignment Distribution"
    )

    distribution = pd.DataFrame(
        {
            "Status":
                [
                    "Aligned",
                    "Needs Revision"
                ],

            "Questions":
                [
                    aligned,
                    needs_revision
                ]
        }
    )

    st.bar_chart(
        distribution.set_index(
            "Status"
        )
    )

    # ========================================================
    # REVISION AREA
    # ========================================================

    st.divider()

    st.header(
        "✏️ Revise and Test Questions"
    )

    for index, result in enumerate(
        results
    ):

        question = result[
            "Question"
        ]

        with st.expander(
            f"Q{index + 1} — "
            f"{result['Overall Score']}/100 — "
            f"{result['Status']}"
        ):

            st.markdown(
                "**Original Question**"
            )

            st.write(
                question
            )

            a, b, c, d = st.columns(4)

            with a:

                st.metric(
                    "Subject",
                    f"{result['Subject Relevance']}/100"
                )

            with b:

                st.metric(
                    "CLO",
                    f"{result['CLO Match']}/100"
                )

            with c:

                st.metric(
                    "PLO",
                    f"{result['PLO Match']}/100"
                )

            with d:

                st.metric(
                    "Bloom",
                    f"{result['Bloom Alignment']}/100"
                )

            # ------------------------------------------------
            # CLO SELECTION
            # ------------------------------------------------

            available_clos = parse_outcomes(
                clo_text
            )

            clo_options = [
                "Select CLO"
            ]

            clo_options.extend(
                [
                    x["id"]
                    for x in available_clos
                ]
            )

            selected_clo = st.selectbox(
                "CLO for revision",
                clo_options,
                key=f"revision_clo_{index}"
            )

            clo_id = ""

            if selected_clo != "Select CLO":
                clo_id = selected_clo

            # ------------------------------------------------
            # CREATE REVISION
            # ------------------------------------------------

            generated_revision = revise_question(
                question,
                subject,
                bloom,
                clo_id
            )

            revised_question = st.text_area(
                "Revised Question",
                value=generated_revision,
                height=160,
                key=f"revision_text_{index}"
            )

            # ------------------------------------------------
            # TEST BUTTON
            # ------------------------------------------------

            if st.button(
                "🧪 Test Revised Question",
                key=f"test_revision_{index}",
                use_container_width=True
            ):

                new_result = (
                    evaluate_revised_question(
                        revised_question,
                        subject,
                        clo_text,
                        plo_text,
                        bloom
                    )
                )

                st.session_state.revised_results[
                    index
                ] = new_result

            # ------------------------------------------------
            # SHOW TEST RESULT
            # ------------------------------------------------

            if index in st.session_state.revised_results:

                revised_result = (
                    st.session_state.revised_results[
                        index
                    ]
                )

                st.markdown(
                    "### Revised Question Result"
                )

                revised_score = int(
                    revised_result.get(
                        "Overall Score",
                        0
                    )
                )

                revised_status = (
                    revised_result.get(
                        "Status",
                        "Needs Revision"
                    )
                )

                if (
                    revised_status == "Aligned"
                    and revised_score >= 80
                ):

                    st.success(
                        "✅ Alignment is attained."
                    )

                else:

                    st.warning(
                        "⚠️ Alignment needs further improvement."
                    )

                st.metric(
                    "Attained After Revision",
                    f"{revised_score}/100"
                )

                r1, r2, r3, r4 = st.columns(4)

                with r1:

                    st.metric(
                        "Subject Relevance",
                        f"{int(revised_result.get('Subject Relevance', 0))}/100"
                    )

                with r2:

                    st.metric(
                        "CLO Alignment",
                        f"{int(revised_result.get('CLO Match', 0))}/100"
                    )

                with r3:

                    st.metric(
                        "PLO Alignment",
                        f"{int(revised_result.get('PLO Match', 0))}/100"
                    )

                with r4:

                    st.metric(
                        "Bloom Alignment",
                        f"{int(revised_result.get('Bloom Alignment', 0))}/100"
                    )

                st.markdown(
                    "**Tested Revised Question**"
                )

                st.info(
                    revised_question
                )


# ============================================================
# DOWNLOAD REPORT
# ============================================================

if (
    st.session_state.evaluated
    and st.session_state.results
):

    st.divider()

    st.header(
        "📥 Download Assessment Report"
    )

    report_df = pd.DataFrame(
        st.session_state.results
    )

    csv_data = report_df.to_csv(
        index=False
    ).encode(
        "utf-8"
    )

    st.download_button(
        "Download CSV Report",
        data=csv_data,
        file_name="OBE_Quiz_Alignment_Report.csv",
        mime="text/csv",
        use_container_width=True
    )

    excel_buffer = io.BytesIO()

    with pd.ExcelWriter(
        excel_buffer,
        engine="openpyxl"
    ) as writer:

        report_df.to_excel(
            writer,
            index=False,
            sheet_name="Alignment Report"
        )

        overview_df.to_excel(
            writer,
            index=False,
            sheet_name="Question Overview"
        )

    st.download_button(
        "Download Excel Report",
        data=excel_buffer.getvalue(),
        file_name="OBE_Quiz_Alignment_Report.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        use_container_width=True
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "OBE Quiz Checker | Collective assessment alignment and graphical analysis"
)
