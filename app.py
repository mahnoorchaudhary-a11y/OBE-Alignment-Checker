import io
import re
import difflib
import pandas as pd
import streamlit as st


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Checker",
    page_icon="🎓",
    layout="wide",
)


# ============================================================
# GLOBAL SETTINGS
# ============================================================

ATTAINMENT_THRESHOLD = 80

METRIC_KEYS = [
    "CLO Alignment",
    "PLO Alignment",
    "Bloom Alignment",
    "Subject Relevance",
    "Clarity",
    "Measurability",
]

BLOOM_LEVELS = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create",
]

BLOOM_ORDER = {
    "Remember": 1,
    "Understand": 2,
    "Apply": 3,
    "Analyze": 4,
    "Evaluate": 5,
    "Create": 6,
}


# ============================================================
# SESSION STATE
# ============================================================

if "questions" not in st.session_state:
    st.session_state.questions = []

if "question_results" not in st.session_state:
    st.session_state.question_results = []

if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False

if "assessment_name" not in st.session_state:
    st.session_state.assessment_name = ""

if "course" not in st.session_state:
    st.session_state.course = ""

if "subject" not in st.session_state:
    st.session_state.subject = ""

if "clo_text" not in st.session_state:
    st.session_state.clo_text = ""

if "plo_text" not in st.session_state:
    st.session_state.plo_text = ""


# ============================================================
# TEXT FUNCTIONS
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\x00", " ")
    text = text.replace("\ufeff", " ")
    text = text.replace("\r", "\n")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)

    return text.strip()


def normalize_text(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def similarity(a, b):
    a = normalize_text(a)
    b = normalize_text(b)

    if not a or not b:
        return 0.0

    return difflib.SequenceMatcher(
        None,
        a,
        b
    ).ratio()


def tokenize(text):
    return re.findall(
        r"[a-zA-Z][a-zA-Z0-9\-]*",
        str(text).lower()
    )


# ============================================================
# FILE READING
# ============================================================

def read_pdf(uploaded_file):

    raw = uploaded_file.getvalue()

    if not raw:
        return "", "The uploaded PDF is empty."

    # --------------------------------------------------------
    # PyMuPDF
    # --------------------------------------------------------

    try:

        import fitz

        pdf = fitz.open(
            stream=raw,
            filetype="pdf"
        )

        pages = []

        for page_number in range(len(pdf)):

            try:

                page = pdf.load_page(
                    page_number
                )

                text = page.get_text(
                    "text",
                    sort=True
                )

                if text:
                    pages.append(text)

            except Exception:
                continue

        pdf.close()

        combined = clean_text(
            "\n".join(pages)
        )

        if len(combined) >= 20:
            return combined, "PyMuPDF"

    except Exception:
        pass

    # --------------------------------------------------------
    # pypdf
    # --------------------------------------------------------

    try:

        from pypdf import PdfReader

        reader = PdfReader(
            io.BytesIO(raw)
        )

        pages = []

        for page in reader.pages:

            try:

                text = page.extract_text()

                if text:
                    pages.append(text)

            except Exception:
                continue

        combined = clean_text(
            "\n".join(pages)
        )

        if len(combined) >= 20:
            return combined, "pypdf"

    except Exception:
        pass

    # --------------------------------------------------------
    # pdfplumber
    # --------------------------------------------------------

    try:

        import pdfplumber

        pages = []

        with pdfplumber.open(
            io.BytesIO(raw)
        ) as pdf:

            for page in pdf.pages:

                try:

                    text = page.extract_text(
                        x_tolerance=2,
                        y_tolerance=3
                    )

                    if text:
                        pages.append(text)

                except Exception:
                    continue

        combined = clean_text(
            "\n".join(pages)
        )

        if len(combined) >= 20:
            return combined, "pdfplumber"

    except Exception:
        pass

    # --------------------------------------------------------
    # OCR
    # --------------------------------------------------------

    try:

        import fitz
        from PIL import Image
        import pytesseract

        pdf = fitz.open(
            stream=raw,
            filetype="pdf"
        )

        pages = []

        for page_number in range(len(pdf)):

            try:

                page = pdf.load_page(
                    page_number
                )

                pix = page.get_pixmap(
                    matrix=fitz.Matrix(
                        2.0,
                        2.0
                    ),
                    alpha=False
                )

                image_bytes = pix.tobytes(
                    "png"
                )

                image = Image.open(
                    io.BytesIO(image_bytes)
                )

                text = pytesseract.image_to_string(
                    image,
                    config="--psm 6"
                )

                if text:
                    pages.append(text)

            except Exception:
                continue

        pdf.close()

        combined = clean_text(
            "\n".join(pages)
        )

        if len(combined) >= 20:
            return combined, "OCR"

    except Exception:
        pass

    return "", "No readable text was extracted from the PDF."


def read_docx(uploaded_file):

    try:

        from docx import Document

        document = Document(
            io.BytesIO(
                uploaded_file.getvalue()
            )
        )

        parts = []

        for paragraph in document.paragraphs:

            text = paragraph.text.strip()

            if text:
                parts.append(text)

        for table in document.tables:

            for row in table.rows:

                values = []

                for cell in row.cells:

                    value = cell.text.strip()

                    if value:
                        values.append(value)

                if values:
                    parts.append(
                        " ".join(values)
                    )

        return (
            clean_text(
                "\n".join(parts)
            ),
            "DOCX",
        )

    except Exception as exc:

        return "", f"DOCX error: {exc}"


def read_pptx(uploaded_file):

    try:

        from pptx import Presentation

        presentation = Presentation(
            io.BytesIO(
                uploaded_file.getvalue()
            )
        )

        parts = []

        for slide in presentation.slides:

            for shape in slide.shapes:

                if hasattr(shape, "text"):

                    if shape.text.strip():
                        parts.append(
                            shape.text
                        )

        return (
            clean_text(
                "\n".join(parts)
            ),
            "PPTX",
        )

    except Exception as exc:

        return "", f"PPTX error: {exc}"


def read_excel(uploaded_file):

    try:

        sheets = pd.read_excel(
            io.BytesIO(
                uploaded_file.getvalue()
            ),
            sheet_name=None,
            header=None,
        )

        parts = []

        for sheet_name, dataframe in sheets.items():

            parts.append(
                f"Sheet: {sheet_name}"
            )

            for row in dataframe.fillna("").values:

                values = [
                    str(value).strip()
                    for value in row
                    if str(value).strip()
                ]

                if values:
                    parts.append(
                        " ".join(values)
                    )

        return (
            clean_text(
                "\n".join(parts)
            ),
            "Excel",
        )

    except Exception as exc:

        return "", f"Excel error: {exc}"


def read_csv(uploaded_file):

    try:

        dataframe = pd.read_csv(
            io.BytesIO(
                uploaded_file.getvalue()
            ),
            header=None,
        )

        parts = []

        for row in dataframe.fillna("").values:

            values = [
                str(value).strip()
                for value in row
                if str(value).strip()
            ]

            if values:
                parts.append(
                    " ".join(values)
                )

        return (
            clean_text(
                "\n".join(parts)
            ),
            "CSV",
        )

    except Exception as exc:

        return "", f"CSV error: {exc}"


def read_text_file(uploaded_file):

    try:

        raw = uploaded_file.getvalue()

        for encoding in [
            "utf-8",
            "utf-8-sig",
            "cp1252",
            "latin-1",
        ]:

            try:

                return (
                    clean_text(
                        raw.decode(encoding)
                    ),
                    "Text",
                )

            except Exception:
                continue

        return "", "Could not decode the text file."

    except Exception as exc:

        return "", f"Text error: {exc}"


def read_image(uploaded_file):

    try:

        from PIL import Image
        import pytesseract

        image = Image.open(
            io.BytesIO(
                uploaded_file.getvalue()
            )
        )

        text = pytesseract.image_to_string(
            image,
            config="--psm 6"
        )

        return (
            clean_text(text),
            "OCR",
        )

    except Exception as exc:

        return "", f"OCR error: {exc}"


def read_uploaded_file(uploaded_file):

    filename = uploaded_file.name.lower()

    if filename.endswith(".pdf"):
        return read_pdf(uploaded_file)

    if filename.endswith(".docx"):
        return read_docx(uploaded_file)

    if filename.endswith(".pptx"):
        return read_pptx(uploaded_file)

    if filename.endswith(
        (".xlsx", ".xls", ".xlsm")
    ):
        return read_excel(uploaded_file)

    if filename.endswith(".csv"):
        return read_csv(uploaded_file)

    if filename.endswith(
        (".txt", ".md", ".rtf")
    ):
        return read_text_file(uploaded_file)

    if filename.endswith(
        (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        )
    ):
        return read_image(uploaded_file)

    return "", "Unsupported file format."


# ============================================================
# QUESTION EXTRACTION
# ============================================================

QUESTION_WORD_RE = re.compile(
    r"\b("
    r"define|describe|explain|identify|"
    r"calculate|compute|solve|analyze|analyse|"
    r"compare|contrast|evaluate|assess|"
    r"discuss|justify|interpret|predict|"
    r"determine|demonstrate|apply|design|"
    r"develop|write|state|list|name|"
    r"what|why|how|which|when|where"
    r")\b",
    re.I,
)


def clean_question_candidate(text):

    text = clean_text(text)

    text = re.sub(
        r"^\s*(?:Q(?:uestion)?\s*)?"
        r"\d{1,3}\s*[\.\):\-]\s*",
        "",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"^\s*Question\s+\d+\s*[:\-]\s*",
        "",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"\s*[\(\[]?\s*\d+\s*"
        r"(?:marks?|points?)\s*[\)\]]?\s*$",
        "",
        text,
        flags=re.I,
    )

    return clean_text(text)


def looks_like_question(text):

    text = clean_text(text)

    if len(text.split()) < 3:
        return False

    if "?" in text:
        return True

    return bool(
        QUESTION_WORD_RE.search(text)
    )


def extract_questions(text):

    text = clean_text(text)

    if not text:
        return []

    # --------------------------------------------------------
    # NUMBERED QUESTIONS ARE AUTHORITATIVE
    # --------------------------------------------------------

    numbered_pattern = re.compile(
        r"(?im)^\s*"
        r"(?:Q(?:uestion)?\s*)?"
        r"(\d{1,3})"
        r"\s*[\.\):\-]\s+"
    )

    matches = list(
        numbered_pattern.finditer(text)
    )

    if matches:

        questions = []

        for index, match in enumerate(matches):

            start = match.end()

            if index + 1 < len(matches):
                end = matches[
                    index + 1
                ].start()
            else:
                end = len(text)

            block = text[
                start:end
            ]

            block = clean_text(block)

            block = re.split(
                r"\n\s*(?:OR|EITHER|CHOICE)\s*\n",
                block,
                maxsplit=1,
                flags=re.I,
            )[0]

            block = clean_question_candidate(
                block
            )

            if (
                block
                and len(block.split()) >= 3
            ):
                questions.append(
                    block
                )

        unique_questions = []

        for question in questions:

            duplicate = any(
                similarity(
                    question,
                    old
                ) >= 0.92
                for old in unique_questions
            )

            if not duplicate:
                unique_questions.append(
                    question
                )

        # NEVER FALL THROUGH.
        return unique_questions

    # --------------------------------------------------------
    # QUESTION-MARK EXTRACTION
    # --------------------------------------------------------

    candidates = []

    for line in text.splitlines():

        line = clean_text(line)

        if (
            line
            and "?" in line
            and looks_like_question(line)
        ):

            candidate = clean_question_candidate(
                line
            )

            if candidate:
                candidates.append(
                    candidate
                )

    if candidates:

        unique = []

        for candidate in candidates:

            if not any(
                similarity(
                    candidate,
                    old
                ) >= 0.92
                for old in unique
            ):
                unique.append(
                    candidate
                )

        return unique

    # --------------------------------------------------------
    # VERB-BASED EXTRACTION
    # --------------------------------------------------------

    candidates = []

    for line in text.splitlines():

        line = clean_text(line)

        if len(line.split()) < 4:
            continue

        if QUESTION_WORD_RE.search(line):

            candidate = clean_question_candidate(
                line
            )

            if candidate:
                candidates.append(
                    candidate
                )

    unique = []

    for candidate in candidates:

        if not any(
            similarity(
                candidate,
                old
            ) >= 0.92
            for old in unique
        ):
            unique.append(candidate)

    return unique


# ============================================================
# QUESTION TYPE
# ============================================================

def detect_question_type(question):

    q = question.lower()

    if re.search(
        r"\b(true|false)\b",
        q
    ):
        return "True / False"

    if (
        "fill in the blank" in q
        or "fill in blanks" in q
        or "________" in q
        or "_____" in q
    ):
        return "Fill in the Blank"

    if (
        "matching" in q
        or "match the following" in q
    ):
        return "Matching"

    if (
        "case study" in q
        or "scenario" in q
    ):
        return "Case / Scenario"

    if re.search(
        r"\b("
        r"calculate|compute|solve|"
        r"equation|probability|"
        r"percentage|mean|median|"
        r"standard deviation"
        r")\b",
        q,
        re.I,
    ):
        return "Numerical"

    if re.search(
        r"\b("
        r"write code|write a program|"
        r"implement|algorithm|"
        r"python|java|c\+\+|sql"
        r")\b",
        q,
        re.I,
    ):
        return "Coding / Practical"

    if len(q.split()) > 45:
        return "Essay / Long Answer"

    return "Question"


# ============================================================
# BLOOM
# ============================================================

BLOOM_VERBS = {
    "Remember": [
        "define",
        "identify",
        "list",
        "name",
        "state",
        "recall",
        "label",
        "recognize",
    ],

    "Understand": [
        "explain",
        "describe",
        "summarize",
        "interpret",
        "classify",
        "illustrate",
        "discuss",
    ],

    "Apply": [
        "calculate",
        "compute",
        "solve",
        "use",
        "apply",
        "demonstrate",
        "implement",
        "execute",
    ],

    "Analyze": [
        "analyze",
        "analyse",
        "compare",
        "contrast",
        "differentiate",
        "examine",
        "investigate",
        "relate",
    ],

    "Evaluate": [
        "evaluate",
        "assess",
        "justify",
        "critique",
        "judge",
        "defend",
        "recommend",
    ],

    "Create": [
        "design",
        "develop",
        "create",
        "construct",
        "formulate",
        "propose",
        "produce",
        "plan",
    ],
}


def detect_bloom(question):

    question_words = tokenize(
        question
    )

    scores = {
        level: 0
        for level in BLOOM_LEVELS
    }

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if verb in question_words:
                scores[level] += 1

    best = max(
        scores,
        key=scores.get
    )

    if scores[best] == 0:
        return "Understand"

    return best


def bloom_target_from_outcomes(
    clo,
    plo
):

    combined = (
        str(clo)
        + " "
        + str(plo)
    ).lower()

    for level in reversed(
        BLOOM_LEVELS
    ):

        for verb in BLOOM_VERBS[level]:

            if re.search(
                rf"\b{re.escape(verb)}\b",
                combined
            ):
                return level

    return "Understand"


# ============================================================
# KEYWORDS
# ============================================================

STOPWORDS = {
    "what",
    "which",
    "when",
    "where",
    "why",
    "how",
    "does",
    "the",
    "a",
    "an",
    "of",
    "to",
    "in",
    "on",
    "for",
    "and",
    "or",
    "with",
    "from",
    "by",
    "that",
    "this",
    "these",
    "those",
    "it",
    "its",
    "their",
    "your",
    "you",
    "can",
    "could",
    "should",
    "would",
    "be",
    "as",
    "at",
    "into",
    "about",
    "using",
    "used",
    "use",
    "explain",
    "describe",
    "define",
    "identify",
    "discuss",
    "calculate",
    "compute",
    "solve",
    "analyze",
    "analyse",
    "evaluate",
    "compare",
    "contrast",
    "apply",
    "state",
    "list",
    "name",
    "write",
    "give",
    "provide",
}


def extract_keywords(text):

    result = []

    for token in tokenize(text):

        if len(token) < 3:
            continue

        if token in STOPWORDS:
            continue

        if token not in result:
            result.append(token)

    return result


# ============================================================
# CLO SCORE
# ============================================================

def score_clo(
    question,
    clo
):

    if not clo.strip():

        return None, (
            "CLO was not provided."
        )

    q_words = set(
        extract_keywords(question)
    )

    clo_words = set(
        extract_keywords(clo)
    )

    if not clo_words:

        return 50, (
            "The CLO does not contain enough "
            "identifiable terms for analysis."
        )

    overlap = (
        len(q_words & clo_words)
        / len(clo_words)
    )

    actual = detect_bloom(
        question
    )

    target = bloom_target_from_outcomes(
        clo,
        ""
    )

    difference = abs(
        BLOOM_ORDER[actual]
        - BLOOM_ORDER[target]
    )

    score = 45

    score += min(
        40,
        overlap * 80
    )

    if difference == 0:
        score += 15

    elif difference == 1:
        score += 8

    else:
        score -= 5

    score = max(
        0,
        min(
            100,
            round(score)
        )
    )

    if score >= ATTAINMENT:

        feedback = (
            "The question directly measures "
            "the specific course-level knowledge "
            "or skill required by the CLO."
        )

    elif score >= 60:

        feedback = (
            f"The CLO alignment score is {score}%. "
            f"This is below the {ATTAINMENT}% "
            "attainment threshold."
        )

    else:

        feedback = (
            f"The CLO alignment score is {score}%. "
            f"This is below the {ATTAINMENT}% "
            "attainment threshold."
        )

    return score, feedback


# ============================================================
# PLO SCORE
# ============================================================

def score_plo(
    question,
    plo
):

    if not plo.strip():

        return None, (
            "PLO was not provided."
        )

    q_words = set(
        extract_keywords(question)
    )

    plo_words = set(
        extract_keywords(plo)
    )

    if not plo_words:

        return 50, (
            "The PLO does not contain enough "
            "identifiable terms for analysis."
        )

    overlap = (
        len(q_words & plo_words)
        / len(plo_words)
    )

    actual = detect_bloom(
        question
    )

    target = bloom_target_from_outcomes(
        "",
        plo
    )

    score = 40

    score += min(
        35,
        overlap * 70
    )

    if actual in [
        "Apply",
        "Analyze",
        "Evaluate",
        "Create",
    ]:
        score += 15

    if actual == target:
        score += 10

    elif (
        BLOOM_ORDER[actual]
        >= BLOOM_ORDER[target]
    ):
        score += 5

    score = max(
        0,
        min(
            100,
            round(score)
        )
    )

    if score >= ATTAINMENT:

        feedback = (
            "The question provides clear evidence "
            "of the broader program-level capability."
        )

    else:

        feedback = (
            f"The PLO alignment score is {score}%. "
            f"This is below the {ATTAINMENT}% "
            "attainment threshold."
        )

    return score, feedback


# ============================================================
# BLOOM SCORE
# ============================================================

def score_bloom(
    question,
    clo,
    plo
):

    actual = detect_bloom(
        question
    )

    target = bloom_target_from_outcomes(
        clo,
        plo
    )

    difference = (
        BLOOM_ORDER[actual]
        - BLOOM_ORDER[target]
    )

    if difference == 0:

        score = 95

        feedback = (
            f"The question operates at {actual}, "
            f"which matches the intended {target} level."
        )

    elif difference == -1:

        score = 75

        feedback = (
            f"The question operates at {actual}, "
            f"below the intended {target} level. "
            f"Bloom alignment is {score}%, below "
            f"the {ATTAINMENT}% attainment threshold."
        )

    elif difference < -1:

        score = max(
            35,
            70 + difference * 8
        )

        feedback = (
            f"The question operates at {actual}, "
            f"below the intended {target} level. "
            f"Bloom alignment is {score}%, below "
            f"the {ATTAINMENT}% attainment threshold."
        )

    elif difference == 1:

        score = 88

        feedback = (
            f"The question operates at {actual}, "
            f"slightly above the intended {target} level."
        )

    else:

        score = 82

        feedback = (
            f"The question operates at {actual}, "
            f"above the intended {target} level."
        )

    return (
        round(score),
        actual,
        target,
        feedback,
    )


# ============================================================
# OTHER METRICS
# ============================================================

def subject_relevance_score(
    question,
    subject,
    course
):

    context = (
        str(subject)
        + " "
        + str(course)
    ).strip()

    if not context:
        return 75

    context_words = set(
        extract_keywords(context)
    )

    question_words = set(
        extract_keywords(question)
    )

    if not context_words:
        return 75

    overlap = len(
        context_words
        & question_words
    )

    if overlap >= 3:
        return 95

    if overlap == 2:
        return 90

    if overlap == 1:
        return 82

    return 68


def clarity_score(question):

    score = 90

    word_count = len(
        question.split()
    )

    if word_count < 4:
        score -= 20

    if word_count > 50:
        score -= 20

    if "??" in question:
        score -= 10

    if question.count("(") != question.count(")"):
        score -= 10

    if question.count("[") != question.count("]"):
        score -= 10

    return max(
        0,
        min(
            100,
            score
        )
    )


def measurability_score(question):

    q = question.lower()

    measurable_verbs = [
        "calculate",
        "compute",
        "solve",
        "explain",
        "compare",
        "analyze",
        "analyse",
        "evaluate",
        "justify",
        "identify",
        "define",
        "describe",
        "interpret",
        "predict",
        "design",
        "develop",
        "write",
        "apply",
        "determine",
        "demonstrate",
        "classify",
        "differentiate",
    ]

    if any(
        verb in q
        for verb in measurable_verbs
    ):
        return 92

    if (
        "what" in q
        or "why" in q
        or "how" in q
    ):
        return 82

    return 68


# ============================================================
# QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question,
    clo,
    plo,
    subject,
    course
):

    clo_score, clo_feedback = score_clo(
        question,
        clo
    )

    plo_score, plo_feedback = score_plo(
        question,
        plo
    )

    (
        bloom_score,
        actual_bloom,
        target_bloom,
        bloom_feedback,
    ) = score_bloom(
        question,
        clo,
        plo
    )

    subject_score = subject_relevance_score(
        question,
        subject,
        course
    )

    clarity = clarity_score(
        question
    )

    measurability = measurability_score(
        question
    )

    metrics = {
        "CLO Alignment": clo_score,
        "PLO Alignment": plo_score,
        "Bloom Alignment": bloom_score,
        "Subject Relevance": subject_score,
        "Clarity": clarity,
        "Measurability": measurability,
    }

    valid_values = [
        value
        for value in metrics.values()
        if value is not None
    ]

    if valid_values:

        overall = round(
            sum(valid_values)
            / len(valid_values)
        )

    else:

        overall = None

    if overall is None:

        status = "Not Available"

    elif overall >= ATTAINMENT:

        status = "Alignment Attained"

    elif overall >= 60:

        status = "Needs Attention"

    else:

        status = "Weak"

    return {
        "question": question,
        "metrics": metrics,
        "score": overall,
        "status": status,
        "clo_feedback": clo_feedback,
        "plo_feedback": plo_feedback,
        "bloom_feedback": bloom_feedback,
        "actual_bloom": actual_bloom,
        "target_bloom": target_bloom,
        "question_type": detect_question_type(
            question
        ),
    }


# ============================================================
# METRIC AGGREGATION
# ============================================================

def calculate_metric_averages(results):

    averages = {}

    for metric in METRIC_KEYS:

        values = []

        for result in results:

            value = result[
                "metrics"
            ].get(metric)

            if value is not None:
                values.append(value)

        if values:

            averages[metric] = round(
                sum(values)
                / len(values)
            )

        else:

            averages[metric] = None

    valid = [
        value
        for value in averages.values()
        if value is not None
    ]

    if valid:

        averages[
            "Overall Alignment"
        ] = round(
            sum(valid)
            / len(valid)
        )

    else:

        averages[
            "Overall Alignment"
        ] = None

    return averages


# ============================================================
# STATUS
# ============================================================

def get_status(value):

    if value is None:
        return "⏳ Not Available"

    if value >= 85:
        return "🟢 Strong"

    if value >= ATTAINMENT:
        return "🟢 Attained"

    if value >= 60:
        return "🟠 Needs Attention"

    return "🔴 Weak"


def display_status(value, label):

    if value is None:

        st.info(
            f"{label}: Not Available"
        )

    elif value >= 85:

        st.success(
            f"{label}: {value}% — Strong"
        )

    elif value >= ATTAINMENT:

        st.success(
            f"{label}: {value}% — Attained"
        )

    elif value >= 60:

        st.warning(
            f"{label}: {value}% — Needs Attention"
        )

    else:

        st.error(
            f"{label}: {value}% — Weak"
        )


# ============================================================
# RUN ANALYSIS
# ============================================================

def run_analysis():

    results = []

    for question in st.session_state.questions:

        result = evaluate_question(
            question,
            st.session_state.clo_text,
            st.session_state.plo_text,
            st.session_state.subject,
            st.session_state.course,
        )

        results.append(
            result
        )

    st.session_state.question_results = results
    st.session_state.analysis_done = True


# ============================================================
# APP HEADER
# ============================================================

st.title(
    "🎓 OBE Quiz Checker"
)

st.caption(
    "Assessment alignment analysis across CLO, PLO, "
    "Bloom, subject relevance, clarity and measurability."
)


# ============================================================
# 1. ASSESSMENT INFORMATION
# ============================================================

st.header(
    "1. Assessment Information"
)

col1, col2, col3 = st.columns(3)

with col1:

    st.session_state.assessment_name = st.text_input(
        "Assessment / Quiz Name",
        value=st.session_state.assessment_name,
        placeholder="e.g. Quiz 1",
    )

with col2:

    st.session_state.course = st.text_input(
        "Course",
        value=st.session_state.course,
        placeholder="e.g. Chemistry",
    )

with col3:

    st.session_state.subject = st.text_input(
        "Subject",
        value=st.session_state.subject,
        placeholder="e.g. General Chemistry",
    )


# ============================================================
# 2. LEARNING OUTCOMES
# ============================================================

st.header(
    "2. Learning Outcomes"
)

clo_col, plo_col = st.columns(2)

with clo_col:

    st.session_state.clo_text = st.text_area(
        "CLO(s)",
        value=st.session_state.clo_text,
        height=140,
        placeholder=(
            "Enter the relevant Course Learning Outcome(s)."
        ),
    )

with plo_col:

    st.session_state.plo_text = st.text_area(
        "PLO(s)",
        value=st.session_state.plo_text,
        height=140,
        placeholder=(
            "Enter the relevant Program Learning Outcome(s)."
        ),
    )


# ============================================================
# 3. UPLOAD
# ============================================================

st.header(
    "3. Upload Complete Assessment"
)

uploaded_file = st.file_uploader(
    "Upload the complete assessment / quiz",
    type=[
        "pdf",
        "docx",
        "pptx",
        "xlsx",
        "xls",
        "xlsm",
        "csv",
        "txt",
        "md",
        "rtf",
        "png",
        "jpg",
        "jpeg",
        "webp",
    ],
)


if uploaded_file is not None:

    if st.button(
        "📄 Read Assessment",
        use_container_width=True,
    ):

        with st.spinner(
            "Reading the assessment..."
        ):

            text, method = read_uploaded_file(
                uploaded_file
            )

        if not text:

            st.error(
                "The file could not be read. "
                "Please check that it contains readable "
                "text or upload a clearer file."
            )

        else:

            detected_questions = extract_questions(
                text
            )

            st.session_state.questions = (
                detected_questions
            )

            st.session_state.question_results = []
            st.session_state.analysis_done = False

            if detected_questions:

                st.success(
                    f"✅ {len(detected_questions)} "
                    f"question(s) detected."
                )

                st.caption(
                    f"Extraction method: {method}"
                )

            else:

                st.error(
                    "No assessment questions could be extracted. "
                    "Please check the file format and content."
                )


# ============================================================
# QUESTION LIST
# ============================================================

if st.session_state.questions:

    st.subheader(
        "Detected Questions"
    )

    st.info(
        f"📄 {len(st.session_state.questions)} "
        f"question(s) detected from the uploaded assessment."
    )

    st.write(
        f"**Questions that will be analyzed: "
        f"{len(st.session_state.questions)}**"
    )

    for number, question in enumerate(
        st.session_state.questions,
        start=1
    ):

        with st.expander(
            f"Question {number}"
        ):

            st.write(
                question
            )


# ============================================================
# 4. ANALYZE
# ============================================================

st.header(
    "4. Analyze Assessment"
)

ready = (
    len(st.session_state.questions) > 0
    and bool(
        st.session_state.clo_text.strip()
    )
    and bool(
        st.session_state.plo_text.strip()
    )
)

if not st.session_state.questions:

    st.info(
        "⏳ Upload an assessment first."
    )

elif (
    not st.session_state.clo_text.strip()
    or not st.session_state.plo_text.strip()
):

    st.info(
        "⏳ Enter both CLO(s) and PLO(s) before analysis."
    )


if st.button(
    "🔍 Analyze Assessment",
    type="primary",
    disabled=not ready,
    use_container_width=True,
):

    with st.spinner(
        f"Analyzing exactly "
        f"{len(st.session_state.questions)} "
        f"question(s)..."
    ):

        run_analysis()

    st.success(
        f"Analysis complete. "
        f"{len(st.session_state.question_results)} "
        f"question(s) analyzed."
    )


# ============================================================
# RESULTS
# ============================================================

if st.session_state.analysis_done:

    results = st.session_state.question_results

    # Ensure exactly one result per extracted question.
    results = results[
        :len(st.session_state.questions)
    ]

    # ========================================================
    # 5. OVERALL ALIGNMENT
    # ========================================================

    st.header(
        "5. Overall Alignment"
    )

    averages = calculate_metric_averages(
        results
    )

    overall = averages[
        "Overall Alignment"
    ]

    if overall is not None:

        if overall >= ATTAINMENT:

            st.success(
                f"🟢 Overall Alignment Attained — "
                f"{overall}/100"
            )

        elif overall >= 60:

            st.warning(
                f"🟠 Overall Alignment Needs Attention — "
                f"{overall}/100"
            )

        else:

            st.error(
                f"🔴 Overall Alignment is Weak — "
                f"{overall}/100"
            )

    # --------------------------------------------------------
    # TOP SIX METRICS
    # --------------------------------------------------------

    metric_cols = st.columns(6)

    for column, metric in zip(
        metric_cols,
        METRIC_KEYS
    ):

        value = averages[metric]

        with column:

            if value is None:

                st.metric(
                    metric,
                    "N/A"
                )

                st.caption(
                    "⏳ Not Available"
                )

            else:

                st.metric(
                    metric,
                    f"{value}%"
                )

                st.caption(
                    get_status(value)
                )

    # --------------------------------------------------------
    # WEAK AREAS
    # --------------------------------------------------------

    st.subheader(
        "⚠️ Weak Areas"
    )

    weak_metrics = []

    for metric in METRIC_KEYS:

        value = averages[metric]

        if (
            value is not None
            and value < ATTAINMENT
        ):

            weak_metrics.append(
                (
                    metric,
                    value
                )
            )

    weak_metrics.sort(
        key=lambda item: item[1]
    )

    if weak_metrics:

        for metric, value in weak_metrics:

            st.warning(
                f"**{metric}: {value}%** — "
                f"below the {ATTAINMENT}% "
                f"attainment threshold."
            )

    else:

        st.success(
            f"🟢 No overall metric is below "
            f"the {ATTAINMENT}% attainment threshold."
        )

    st.info(
        f"All diagnostic descriptions use the same "
        f"{ATTAINMENT}% attainment threshold. "
        "A question's overall score and its individual "
        "metric scores are reported separately."
    )

    # ========================================================
    # 6. QUESTION-LEVEL DIAGNOSTICS
    # ========================================================

    st.header(
        "6. Question-Level Diagnostics"
    )

    for number, result in enumerate(
        results,
        start=1
    ):

        question_score = result["score"]

        weak_metrics = []

        for metric in METRIC_KEYS:

            value = result[
                "metrics"
            ].get(metric)

            if (
                value is not None
                and value < ATTAINMENT
            ):

                weak_metrics.append(
                    (
                        metric,
                        value
                    )
                )

        # ----------------------------------------------------
        # IMPORTANT:
        # Do NOT describe a 76 score as below 75.
        # Use the actual score and the single 80 threshold.
        # ----------------------------------------------------

        if question_score is not None:

            if question_score >= ATTAINMENT:

                st.success(
                    f"Q{number} — "
                    f"{question_score}/100 — "
                    f"🟢 Alignment Attained"
                )

            elif question_score >= 60:

                st.warning(
                    f"Q{number} — "
                    f"{question_score}/100 — "
                    f"🟠 Needs Attention"
                )

            else:

                st.error(
                    f"Q{number} — "
                    f"{question_score}/100 — "
                    f"🔴 Weak"
                )

        st.write(
            f"**Current Question:** "
            f"{result['question']}"
        )

        if weak_metrics:

            weak_text = ", ".join(
                [
                    f"{metric} ({value}%)"
                    for metric, value
                    in weak_metrics
                ]
            )

            st.warning(
                f"**Weak metrics for Q{number}:** "
                f"{weak_text}. "
                f"Each is below the "
                f"{ATTAINMENT}% attainment threshold."
            )

        else:

            st.success(
                f"All individual metrics for Q{number} "
                f"meet the {ATTAINMENT}% threshold."
            )

        # Feedback is diagnostic only.
        # No generated replacement questions.
        # No revisions.
        # No suggestion buttons.

        with st.expander(
            f"View Q{number} diagnostic details"
        ):

            st.write(
                f"**Question Type:** "
                f"{result['question_type']}"
            )

            st.write(
                f"**CLO Alignment:** "
                f"{result['metrics']['CLO Alignment']}%"
            )

            st.write(
                result["clo_feedback"]
            )

            st.write(
                f"**PLO Alignment:** "
                f"{result['metrics']['PLO Alignment']}%"
            )

            st.write(
                result["plo_feedback"]
            )

            st.write(
                f"**Bloom Alignment:** "
                f"{result['metrics']['Bloom Alignment']}%"
            )

            st.write(
                f"Actual Bloom: "
                f"**{result['actual_bloom']}**"
            )

            st.write(
                f"Target Bloom: "
                f"**{result['target_bloom']}**"
            )

            st.write(
                result["bloom_feedback"]
            )

            st.write(
                f"**Subject Relevance:** "
                f"{result['metrics']['Subject Relevance']}%"
            )

            st.write(
                f"**Clarity:** "
                f"{result['metrics']['Clarity']}%"
            )

            st.write(
                f"**Measurability:** "
                f"{result['metrics']['Measurability']}%"
            )

    # ========================================================
    # 7. ATTAINED QUESTIONS
    # ========================================================

    st.header(
        "7. Attained Questions"
    )

    attained_questions = []

    for number, result in enumerate(
        results,
        start=1
    ):

        if (
            result["score"] is not None
            and result["score"] >= ATTAINMENT
        ):

            attained_questions.append(
                (
                    number,
                    result
                )
            )

    if attained_questions:

        for number, result in attained_questions:

            st.success(
                f"Q{number} — "
                f"{result['score']}/100 — "
                f"🟢 Alignment Attained"
            )

    else:

        st.info(
            f"No question has reached "
            f"{ATTAINMENT}%."
        )

    # ========================================================
    # 8. ONLY ONE GRAPH
    # ========================================================

    st.header(
        "8. Alignment Overview"
    )

    chart_rows = []

    for number, result in enumerate(
        results,
        start=1
    ):

        if result["score"] is not None:

            chart_rows.append({
                "Question":
                    f"Q{number}",

                "Overall Score":
                    result["score"],
            })

    if chart_rows:

        chart_df = pd.DataFrame(
            chart_rows
        )

        st.bar_chart(
            chart_df.set_index(
                "Question"
            )
        )

    # ========================================================
    # 9. QUESTION OVERVIEW
    # ========================================================

    st.header(
        "9. Question Overview"
    )

    overview_rows = []

    for number, result in enumerate(
        results,
        start=1
    ):

        overview_rows.append({
            "Question":
                f"Q{number}",

            "Type":
                result["question_type"],

            "Overall":
                result["score"],

            "CLO":
                result["metrics"][
                    "CLO Alignment"
                ],

            "PLO":
                result["metrics"][
                    "PLO Alignment"
                ],

            "Bloom":
                result["metrics"][
                    "Bloom Alignment"
                ],

            "Subject Relevance":
                result["metrics"][
                    "Subject Relevance"
                ],

            "Clarity":
                result["metrics"][
                    "Clarity"
                ],

            "Measurability":
                result["metrics"][
                    "Measurability"
                ],

            "Status":
                result["status"],
        })

    overview_df = pd.DataFrame(
        overview_rows
    )

    st.dataframe(
        overview_df,
        use_container_width=True,
        hide_index=True,
    )

    # ========================================================
    # 10. DETAILED ANALYSIS
    # ========================================================

    st.header(
        "10. Detailed Question Analysis"
    )

    for number, result in enumerate(
        results,
        start=1
    ):

        with st.expander(
            f"Q{number} — "
            f"{result['score']}/100"
        ):

            st.write(
                "**Current Question**"
            )

            st.write(
                result["question"]
            )

            st.write(
                f"**Question Type:** "
                f"{result['question_type']}"
            )

            st.markdown(
                "### CLO Alignment"
            )

            display_status(
                result["metrics"][
                    "CLO Alignment"
                ],
                "CLO Alignment"
            )

            st.write(
                result["clo_feedback"]
            )

            st.markdown(
                "### PLO Alignment"
            )

            display_status(
                result["metrics"][
                    "PLO Alignment"
                ],
                "PLO Alignment"
            )

            st.write(
                result["plo_feedback"]
            )

            st.markdown(
                "### Bloom Alignment"
            )

            display_status(
                result["metrics"][
                    "Bloom Alignment"
                ],
                "Bloom Alignment"
            )

            st.write(
                f"Actual Bloom Level: "
                f"**{result['actual_bloom']}**"
            )

            st.write(
                f"Target Bloom Level: "
                f"**{result['target_bloom']}**"
            )

            st.write(
                result["bloom_feedback"]
            )

            st.markdown(
                "### Other Metrics"
            )

            c1, c2, c3 = st.columns(3)

            with c1:

                display_status(
                    result["metrics"][
                        "Subject Relevance"
                    ],
                    "Subject Relevance"
                )

            with c2:

                display_status(
                    result["metrics"][
                        "Clarity"
                    ],
                    "Clarity"
                )

            with c3:

                display_status(
                    result["metrics"][
                        "Measurability"
                    ],
                    "Measurability"
                )

    # ========================================================
    # 11. EXPORT
    # ========================================================

    st.header(
        "11. Export"
    )

    export_rows = []

    for number, result in enumerate(
        results,
        start=1
    ):

        export_rows.append({

            "Question Number":
                number,

            "Current Question":
                result["question"],

            "Question Type":
                result["question_type"],

            "Overall Score":
                result["score"],

            "Overall Status":
                result["status"],

            "CLO Alignment":
                result["metrics"][
                    "CLO Alignment"
                ],

            "CLO Feedback":
                result["clo_feedback"],

            "PLO Alignment":
                result["metrics"][
                    "PLO Alignment"
                ],

            "PLO Feedback":
                result["plo_feedback"],

            "Bloom Alignment":
                result["metrics"][
                    "Bloom Alignment"
                ],

            "Actual Bloom":
                result["actual_bloom"],

            "Target Bloom":
                result["target_bloom"],

            "Bloom Feedback":
                result["bloom_feedback"],

            "Subject Relevance":
                result["metrics"][
                    "Subject Relevance"
                ],

            "Clarity":
                result["metrics"][
                    "Clarity"
                ],

            "Measurability":
                result["metrics"][
                    "Measurability"
                ],

        })

    export_df = pd.DataFrame(
        export_rows
    )

    csv_bytes = export_df.to_csv(
        index=False
    ).encode(
        "utf-8"
    )

    st.download_button(
        "⬇️ Download Analysis CSV",
        data=csv_bytes,
        file_name="OBE_Quiz_Checker_Analysis.csv",
        mime="text/csv",
        use_container_width=True,
    )
