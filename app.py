import io
import re
import difflib
import pandas as pd
import streamlit as st


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Checker",
    page_icon="🎓",
    layout="wide",
)


# ============================================================
# CONSTANTS
# ============================================================

ATTAINMENT = 80

METRIC_NAMES = [
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

defaults = {
    "questions": [],
    "question_results": [],
    "analysis_done": False,
    "assessment_name": "",
    "course": "",
    "subject": "",
    "clo_text": "",
    "plo_text": "",
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# TEXT UTILITIES
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


def words(text):
    return re.findall(
        r"[a-zA-Z][a-zA-Z0-9\-]*",
        str(text).lower()
    )


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


def clean_question_candidate(text):
    text = clean_text(text)

    text = re.sub(
        r"^\s*(?:Q(?:uestion)?\s*)?\d{1,3}"
        r"\s*[\.\):\-]\s*",
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
        r"\s*\(\s*\d+\s*marks?\s*\)\s*$",
        "",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"\s*\[\s*\d+\s*marks?\s*\]\s*$",
        "",
        text,
        flags=re.I,
    )

    return clean_text(text)


# ============================================================
# FILE READING
# ============================================================

def read_pdf(uploaded_file):
    raw = uploaded_file.getvalue()

    if not raw:
        return "", "The uploaded PDF is empty."

    # PyMuPDF
    try:
        import fitz

        pdf = fitz.open(
            stream=raw,
            filetype="pdf"
        )

        pages = []

        for i in range(len(pdf)):
            try:
                page = pdf.load_page(i)
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

    # pypdf
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

    # pdfplumber
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

    # OCR
    try:
        import fitz
        from PIL import Image
        import pytesseract

        pdf = fitz.open(
            stream=raw,
            filetype="pdf"
        )

        pages = []

        for i in range(len(pdf)):

            try:
                page = pdf.load_page(i)

                pix = page.get_pixmap(
                    matrix=fitz.Matrix(
                        2,
                        2
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
            if paragraph.text.strip():
                parts.append(
                    paragraph.text
                )

        for table in document.tables:

            for row in table.rows:

                row_values = []

                for cell in row.cells:
                    if cell.text.strip():
                        row_values.append(
                            cell.text
                        )

                if row_values:
                    parts.append(
                        " ".join(row_values)
                    )

        return clean_text(
            "\n".join(parts)
        ), "DOCX"

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

                if hasattr(
                    shape,
                    "text"
                ):

                    if shape.text.strip():
                        parts.append(
                            shape.text
                        )

        return clean_text(
            "\n".join(parts)
        ), "PPTX"

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

        for sheet_name, df in sheets.items():

            parts.append(
                f"Sheet: {sheet_name}"
            )

            for row in df.fillna("").values:

                values = [
                    str(x).strip()
                    for x in row
                    if str(x).strip()
                ]

                if values:
                    parts.append(
                        " ".join(values)
                    )

        return clean_text(
            "\n".join(parts)
        ), "Excel"

    except Exception as exc:
        return "", f"Excel error: {exc}"


def read_csv(uploaded_file):
    try:
        df = pd.read_csv(
            io.BytesIO(
                uploaded_file.getvalue()
            ),
            header=None
        )

        parts = []

        for row in df.fillna("").values:

            values = [
                str(x).strip()
                for x in row
                if str(x).strip()
            ]

            if values:
                parts.append(
                    " ".join(values)
                )

        return clean_text(
            "\n".join(parts)
        ), "CSV"

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
                return clean_text(
                    raw.decode(encoding)
                ), "Text"

            except Exception:
                continue

        return "", "Could not decode text file."

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

        return clean_text(
            text
        ), "OCR"

    except Exception as exc:
        return "", f"OCR error: {exc}"


def read_uploaded_file(uploaded_file):
    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        return read_pdf(uploaded_file)

    if name.endswith(".docx"):
        return read_docx(uploaded_file)

    if name.endswith(".pptx"):
        return read_pptx(uploaded_file)

    if name.endswith(
        (".xlsx", ".xls", ".xlsm")
    ):
        return read_excel(uploaded_file)

    if name.endswith(".csv"):
        return read_csv(uploaded_file)

    if name.endswith(
        (".txt", ".md", ".rtf")
    ):
        return read_text_file(uploaded_file)

    if name.endswith(
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
    """
    NUMBERED QUESTIONS ARE AUTHORITATIVE.

    If Q1-Q5 are found, exactly those five blocks
    are returned. No fallback extraction is run.
    """

    text = clean_text(text)

    if not text:
        return []

    numbered_pattern = re.compile(
        r"(?im)^\s*"
        r"(?:Q(?:uestion)?\s*)?"
        r"(\d{1,3})"
        r"\s*[\.\):\-]\s+"
    )

    matches = list(
        numbered_pattern.finditer(
            text
        )
    )

    # --------------------------------------------------------
    # NUMBERED QUESTIONS
    # --------------------------------------------------------

    if matches:

        questions = []

        for index, match in enumerate(
            matches
        ):

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

            block = clean_text(
                block
            )

            # Remove marks.
            block = re.sub(
                r"\s*[\(\[]?\s*\d+\s*"
                r"(?:marks?|points?)\s*[\)\]]?\s*$",
                "",
                block,
                flags=re.I,
            )

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

        unique = []

        for question in questions:

            duplicate = any(
                similarity(
                    question,
                    previous
                ) >= 0.92
                for previous in unique
            )

            if not duplicate:
                unique.append(
                    question
                )

        # CRITICAL RETURN.
        # No fallback extraction.
        return unique

    # --------------------------------------------------------
    # QUESTION MARK EXTRACTION
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
    # VERB FALLBACK
    # --------------------------------------------------------

    candidates = []

    for line in text.splitlines():

        line = clean_text(line)

        if len(line.split()) < 4:
            continue

        if QUESTION_WORD_RE.search(
            line
        ):

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
            unique.append(
                candidate
            )

    return unique


# ============================================================
# QUESTION TYPE
# ============================================================

def detect_question_type(question):
    q = question.lower()

    if re.search(
        r"\b(true|false)\b",
        q
    ) and len(q.split()) < 50:
        return "True/False"

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
        or "case:" in q
    ):
        return "Case / Scenario"

    if re.search(
        r"\b("
        r"calculate|compute|solve|"
        r"velocity|acceleration|"
        r"percentage|probability|"
        r"mean|median|equation|"
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
        r"python|java|c\+\+|sql|"
        r"program"
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
    q_words = words(question)

    scores = {
        level: 0
        for level in BLOOM_LEVELS
    }

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if verb in q_words:
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

    for token in words(text):

        if len(token) < 3:
            continue

        if token in STOPWORDS:
            continue

        if token not in result:
            result.append(
                token
            )

    return result


# ============================================================
# CLO ALIGNMENT
# ============================================================

def score_clo(
    question,
    clo
):
    if not clo.strip():
        return None, (
            "CLO not provided."
        )

    q_words = set(
        extract_keywords(
            question
        )
    )

    clo_words = set(
        extract_keywords(
            clo
        )
    )

    if not clo_words:
        return 50, (
            "The CLO does not contain enough "
            "identifiable terms for alignment."
        )

    overlap = len(
        q_words & clo_words
    ) / len(clo_words)

    actual_bloom = detect_bloom(
        question
    )

    target_bloom = bloom_target_from_outcomes(
        clo,
        ""
    )

    bloom_difference = abs(
        BLOOM_ORDER[actual_bloom]
        - BLOOM_ORDER[target_bloom]
    )

    score = 45

    score += min(
        40,
        overlap * 80
    )

    if bloom_difference == 0:
        score += 15

    elif bloom_difference == 1:
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

    if score >= 80:
        feedback = (
            "The question directly measures "
            "the specific course-level knowledge "
            "or skill required by the CLO."
        )

    elif score >= 60:
        feedback = (
            "The question addresses some CLO content, "
            "but the required course-level skill is "
            "not fully demonstrated."
        )

    else:
        feedback = (
            "The question provides limited evidence "
            "of the specific course-level skill "
            "required by the CLO."
        )

    return score, feedback


# ============================================================
# PLO ALIGNMENT
# ============================================================

def score_plo(
    question,
    plo
):
    if not plo.strip():
        return None, (
            "PLO not provided."
        )

    q_words = set(
        extract_keywords(
            question
        )
    )

    plo_words = set(
        extract_keywords(
            plo
        )
    )

    if not plo_words:
        return 50, (
            "The PLO does not contain enough "
            "identifiable terms for alignment."
        )

    overlap = len(
        q_words & plo_words
    ) / len(plo_words)

    actual_bloom = detect_bloom(
        question
    )

    target_bloom = bloom_target_from_outcomes(
        "",
        plo
    )

    score = 40

    score += min(
        35,
        overlap * 70
    )

    # Broader PLO evidence.
    if actual_bloom in [
        "Apply",
        "Analyze",
        "Evaluate",
        "Create",
    ]:
        score += 15

    if (
        actual_bloom
        == target_bloom
    ):
        score += 10

    elif (
        BLOOM_ORDER[actual_bloom]
        >= BLOOM_ORDER[target_bloom]
    ):
        score += 5

    score = max(
        0,
        min(
            100,
            round(score)
        )
    )

    if score >= 80:
        feedback = (
            "The question provides clear evidence "
            "of the broader program-level capability."
        )

    elif score >= 60:
        feedback = (
            "The question provides some evidence "
            "of the PLO, but stronger evidence of "
            "the broader capability is needed."
        )

    else:
        feedback = (
            "The question mainly tests isolated "
            "knowledge and provides limited evidence "
            "of the broader PLO capability."
        )

    return score, feedback


# ============================================================
# BLOOM ALIGNMENT
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

    actual_num = BLOOM_ORDER[
        actual
    ]

    target_num = BLOOM_ORDER[
        target
    ]

    difference = (
        actual_num
        - target_num
    )

    if difference == 0:

        score = 95

        feedback = (
            f"The question operates at "
            f"{actual}, matching the intended "
            f"{target} cognitive level."
        )

    elif difference == -1:

        score = 75

        feedback = (
            f"The question operates at "
            f"{actual}, slightly below the intended "
            f"{target} level."
        )

    elif difference < -1:

        score = max(
            35,
            70 + difference * 8
        )

        feedback = (
            f"The question operates at "
            f"{actual}, below the intended "
            f"{target} level."
        )

    elif difference == 1:

        score = 88

        feedback = (
            f"The question operates at "
            f"{actual}, slightly above the intended "
            f"{target} level."
        )

    else:

        score = 82

        feedback = (
            f"The question operates at "
            f"{actual}, above the intended "
            f"{target} level."
        )

    return (
        round(score),
        actual,
        target,
        feedback,
    )


# ============================================================
# SUBJECT RELEVANCE
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
        extract_keywords(
            context
        )
    )

    question_words = set(
        extract_keywords(
            question
        )
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


# ============================================================
# CLARITY
# ============================================================

def clarity_score(question):
    q = clean_text(question)

    score = 90

    count = len(
        q.split()
    )

    if count < 4:
        score -= 20

    if count > 50:
        score -= 20

    if "??" in q:
        score -= 10

    if q.count("(") != q.count(")"):
        score -= 10

    if q.count("[") != q.count("]"):
        score -= 10

    return max(
        0,
        min(
            100,
            score
        )
    )


# ============================================================
# MEASURABILITY
# ============================================================

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
# EVALUATE QUESTION
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

    available = [
        value
        for value in metrics.values()
        if value is not None
    ]

    if available:
        overall = round(
            sum(available)
            / len(available)
        )
    else:
        overall = None

    if overall is None:
        status = "Awaiting Analysis"

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
# OVERALL METRIC CALCULATION
# ============================================================

def calculate_overall_metrics(results):
    overall_metrics = {}

    for metric in METRIC_NAMES:

        values = []

        for result in results:

            value = result[
                "metrics"
            ].get(metric)

            if value is not None:
                values.append(
                    value
                )

        if values:

            overall_metrics[
                metric
            ] = round(
                sum(values)
                / len(values)
            )

        else:

            overall_metrics[
                metric
            ] = None

    valid = [
        value
        for value in overall_metrics.values()
        if value is not None
    ]

    if valid:

        overall_metrics[
            "Overall Alignment"
        ] = round(
            sum(valid)
            / len(valid)
        )

    else:

        overall_metrics[
            "Overall Alignment"
        ] = None

    return overall_metrics


# ============================================================
# METRIC STATUS
# ============================================================

def metric_status(value):
    if value is None:
        return "⏳ Not Available"

    if value >= 85:
        return "🟢 Strong"

    if value >= 80:
        return "🟢 Attained"

    if value >= 60:
        return "🟠 Needs Attention"

    return "🔴 Weak"


def metric_color_message(
    value,
    label
):
    if value is None:
        st.info(
            f"{label}: Not available"
        )

    elif value >= 85:
        st.success(
            f"{label}: {value}% — Strong"
        )

    elif value >= 80:
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
# ANALYSIS
# ============================================================

def analyze_assessment():
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
# HEADER
# ============================================================

st.title(
    "🎓 OBE Quiz Checker"
)

st.caption(
    "Subject-agnostic assessment analysis for "
    "CLO, PLO, Bloom and question quality."
)


# ============================================================
# ASSESSMENT INFORMATION
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
        placeholder="e.g. General Chemistry",
    )

with col3:

    st.session_state.subject = st.text_input(
        "Subject",
        value=st.session_state.subject,
        placeholder="e.g. Chemistry",
    )


# ============================================================
# LEARNING OUTCOMES
# ============================================================

st.header(
    "2. Learning Outcomes"
)

clo_col, plo_col = st.columns(2)

with clo_col:

    st.session_state.clo_text = st.text_area(
        "CLO(s)",
        value=st.session_state.clo_text,
        height=130,
        placeholder=(
            "Enter the relevant Course Learning Outcome(s)."
        ),
    )

with plo_col:

    st.session_state.plo_text = st.text_area(
        "PLO(s)",
        value=st.session_state.plo_text,
        height=130,
        placeholder=(
            "Enter the relevant Program Learning Outcome(s)."
        ),
    )

if (
    not st.session_state.clo_text.strip()
    or not st.session_state.plo_text.strip()
):

    st.info(
        "⏳ Enter both CLO(s) and PLO(s) before analysis."
    )


# ============================================================
# UPLOAD
# ============================================================

st.header(
    "3. Upload Complete Assessment"
)

uploaded_file = st.file_uploader(
    "Upload the complete quiz / assessment",
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
            "Reading assessment..."
        ):

            text, method = read_uploaded_file(
                uploaded_file
            )

        if not text:

            st.error(
                "The file could not be read. "
                "Please check that the file contains "
                "readable text or upload a clearer file."
            )

        else:

            questions = extract_questions(
                text
            )

            st.session_state.questions = questions
            st.session_state.question_results = []
            st.session_state.analysis_done = False

            if questions:

                st.success(
                    f"✅ {len(questions)} question(s) detected."
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
# DETECTED QUESTIONS
# ============================================================

if st.session_state.questions:

    st.subheader(
        "Detected Questions"
    )

    st.info(
        f"📄 **{len(st.session_state.questions)} "
        f"question(s) detected from the uploaded assessment.**"
    )

    st.write(
        f"**Questions that will be analyzed: "
        f"{len(st.session_state.questions)}**"
    )

    for index, question in enumerate(
        st.session_state.questions
    ):

        with st.expander(
            f"Question {index + 1}"
        ):

            st.write(
                question
            )

    st.caption(
        "Numbered questions are authoritative. "
        "No additional questions are created by "
        "fallback extraction."
    )


# ============================================================
# ANALYZE
# ============================================================

st.header(
    "4. Analyze Assessment"
)

can_analyze = (
    bool(st.session_state.questions)
    and bool(
        st.session_state.clo_text.strip()
    )
    and bool(
        st.session_state.plo_text.strip()
    )
)

if not can_analyze:

    if not st.session_state.questions:

        st.info(
            "⏳ Upload an assessment first."
        )

    elif (
        not st.session_state.clo_text.strip()
        or not st.session_state.plo_text.strip()
    ):

        st.info(
            "⏳ Enter CLO(s) and PLO(s) before analysis."
        )


if st.button(
    "🔍 Analyze Assessment",
    type="primary",
    disabled=not can_analyze,
    use_container_width=True,
):

    with st.spinner(
        f"Analyzing exactly "
        f"{len(st.session_state.questions)} "
        f"question(s)..."
    ):

        analyze_assessment()

    st.success(
        f"Analysis complete: "
        f"{len(st.session_state.question_results)} "
        f"question(s) analyzed."
    )


# ============================================================
# RESULTS
# ============================================================

if st.session_state.analysis_done:

    results = st.session_state.question_results

    # Never allow more results than questions.
    results = results[
        :len(
            st.session_state.questions
        )
    ]

    # ========================================================
    # TOP METRICS
    # ========================================================

    st.header(
        "5. Overall Alignment & Weak Areas"
    )

    overall_metrics = calculate_overall_metrics(
        results
    )

    overall_score = overall_metrics[
        "Overall Alignment"
    ]

    # --------------------------------------------------------
    # OVERALL SCORE
    # --------------------------------------------------------

    if overall_score is not None:

        if overall_score >= ATTAINMENT:

            st.success(
                f"🟢 Overall Alignment Attained — "
                f"{overall_score}/100"
            )

        else:

            st.warning(
                f"🟠 Overall Alignment Needs Attention — "
                f"{overall_score}/100"
            )

    # --------------------------------------------------------
    # SIX INDEPENDENT METRICS
    # --------------------------------------------------------

    metric_columns = st.columns(6)

    for column, metric in zip(
        metric_columns,
        METRIC_NAMES
    ):

        value = overall_metrics[
            metric
        ]

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
                    metric_status(
                        value
                    )
                )

    # --------------------------------------------------------
    # WEAK AREAS
    # --------------------------------------------------------

    weak_areas = []

    for metric in METRIC_NAMES:

        value = overall_metrics[
            metric
        ]

        if (
            value is not None
            and value < ATTAINMENT
        ):

            weak_areas.append(
                (
                    metric,
                    value
                )
            )

    st.subheader(
        "⚠️ Areas Requiring Attention"
    )

    if weak_areas:

        weak_text = " | ".join(
            [
                f"**{name}: {value}%**"
                for name, value
                in weak_areas
            ]
        )

        st.warning(
            "The following areas are below the "
            f"{ATTAINMENT}% attainment threshold: "
            + weak_text
        )

    else:

        st.success(
            "🟢 All overall metrics have reached "
            f"the {ATTAINMENT}% attainment threshold."
        )

    # --------------------------------------------------------
    # STRONG AREAS
    # --------------------------------------------------------

    strong_areas = []

    for metric in METRIC_NAMES:

        value = overall_metrics[
            metric
        ]

        if (
            value is not None
            and value >= ATTAINMENT
        ):

            strong_areas.append(
                (
                    metric,
                    value
                )
            )

    if strong_areas:

        st.caption(
            "Strong/attained areas: "
            + " | ".join(
                [
                    f"{name} ({value}%)"
                    for name, value
                    in strong_areas
                ]
            )
        )

    # --------------------------------------------------------
    # IMPORTANT INTERPRETATION
    # --------------------------------------------------------

    st.info(
        "Each metric is calculated independently. "
        "A strong CLO score does not compensate for a weak "
        "PLO, Bloom, subject relevance, clarity or "
        "measurability score."
    )

    # ========================================================
    # QUESTION-LEVEL WEAK AREAS
    # ========================================================

    st.header(
        "6. Question-Level Weak Areas"
    )

    for result in results:

        weak_metrics = []

        for metric in METRIC_NAMES:

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

        if weak_metrics:

            st.warning(
                f"Q{results.index(result) + 1}: "
                + " | ".join(
                    [
                        f"{name} {value}%"
                        for name, value
                        in weak_metrics
                    ]
                )
            )

            st.write(
                result["question"]
            )

    # ========================================================
    # ATTAINED QUESTIONS
    # ========================================================

    st.header(
        "7. Attained Questions"
    )

    attained = [
        result
        for result in results
        if (
            result["score"] is not None
            and result["score"] >= ATTAINMENT
        )
    ]

    if attained:

        for index, result in enumerate(
            results
        ):

            if result in attained:

                st.success(
                    f"Q{index + 1} — "
                    f"{result['score']}/100 — "
                    f"🟢 Alignment Attained"
                )

                st.write(
                    result["question"]
                )

    else:

        st.info(
            "No question has reached the "
            f"{ATTAINMENT}% threshold."
        )

    # ========================================================
    # ONE GRAPH ONLY
    # ========================================================

    st.header(
        "8. Alignment Overview"
    )

    chart_data = pd.DataFrame({
        "Question": [
            f"Q{i + 1}"
            for i in range(
                len(results)
            )
        ],

        "Score": [
            result["score"]
            for result in results
        ],
    })

    if not chart_data.empty:

        st.bar_chart(
            chart_data.set_index(
                "Question"
            )
        )

    # ========================================================
    # QUESTION OVERVIEW
    # ========================================================

    st.header(
        "9. Question Overview"
    )

    overview_rows = []

    for index, result in enumerate(
        results
    ):

        overview_rows.append({
            "Question":
                f"Q{index + 1}",

            "Question Type":
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
    # DETAILED ANALYSIS
    # ========================================================

    st.header(
        "10. Detailed Question Analysis"
    )

    for index, result in enumerate(
        results
    ):

        with st.expander(
            f"Q{index + 1} — "
            f"{result['score']}/100"
        ):

            st.write(
                "**Question**"
            )

            st.write(
                result["question"]
            )

            st.write(
                f"**Question Type:** "
                f"{result['question_type']}"
            )

            # ----------------------------------------------
            # CLO
            # ----------------------------------------------

            st.markdown(
                "### CLO Alignment"
            )

            st.write(
                f"**Score:** "
                f"{result['metrics']['CLO Alignment']}%"
            )

            st.write(
                result[
                    "clo_feedback"
                ]
            )

            # ----------------------------------------------
            # PLO
            # ----------------------------------------------

            st.markdown(
                "### PLO Alignment"
            )

            st.write(
                f"**Score:** "
                f"{result['metrics']['PLO Alignment']}%"
            )

            st.write(
                result[
                    "plo_feedback"
                ]
            )

            # ----------------------------------------------
            # BLOOM
            # ----------------------------------------------

            st.markdown(
                "### Bloom Alignment"
            )

            st.write(
                f"**Score:** "
                f"{result['metrics']['Bloom Alignment']}%"
            )

            st.write(
                f"**Actual Bloom Level:** "
                f"{result['actual_bloom']}"
            )

            st.write(
                f"**Target Bloom Level:** "
                f"{result['target_bloom']}"
            )

            st.write(
                result[
                    "bloom_feedback"
                ]
            )

            # ----------------------------------------------
            # OTHER METRICS
            # ----------------------------------------------

            st.markdown(
                "### Other Quality Metrics"
            )

            other_cols = st.columns(3)

            with other_cols[0]:

                st.metric(
                    "Subject Relevance",
                    f"{result['metrics']['Subject Relevance']}%"
                )

            with other_cols[1]:

                st.metric(
                    "Clarity",
                    f"{result['metrics']['Clarity']}%"
                )

            with other_cols[2]:

                st.metric(
                    "Measurability",
                    f"{result['metrics']['Measurability']}%"
                )

            # ----------------------------------------------
            # WEAK AREA SUMMARY
            # ----------------------------------------------

            question_weak = []

            for metric in METRIC_NAMES:

                value = result[
                    "metrics"
                ].get(metric)

                if (
                    value is not None
                    and value < ATTAINMENT
                ):

                    question_weak.append(
                        f"{metric}: {value}%"
                    )

            if question_weak:

                st.error(
                    "Weak areas: "
                    + " | ".join(
                        question_weak
                    )
                )

            else:

                st.success(
                    "🟢 All evaluated areas meet "
                    f"the {ATTAINMENT}% threshold."
                )

    # ========================================================
    # EXPORT
    # ========================================================

    st.header(
        "11. Export"
    )

    export_rows = []

    for index, result in enumerate(
        results
    ):

        export_rows.append({
            "Question Number":
                index + 1,

            "Question":
                result["question"],

            "Question Type":
                result["question_type"],

            "Overall Score":
                result["score"],

            "CLO Alignment":
                result["metrics"][
                    "CLO Alignment"
                ],

            "CLO Feedback":
                result[
                    "clo_feedback"
                ],

            "PLO Alignment":
                result["metrics"][
                    "PLO Alignment"
                ],

            "PLO Feedback":
                result[
                    "plo_feedback"
                ],

            "Bloom Alignment":
                result["metrics"][
                    "Bloom Alignment"
                ],

            "Actual Bloom":
                result[
                    "actual_bloom"
                ],

            "Target Bloom":
                result[
                    "target_bloom"
                ],

            "Bloom Feedback":
                result[
                    "bloom_feedback"
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

    export_df = pd.DataFrame(
        export_rows
    )

    csv_data = export_df.to_csv(
        index=False
    ).encode(
        "utf-8"
    )

    st.download_button(
        "⬇️ Download Analysis CSV",
        data=csv_data,
        file_name="OBE_Quiz_Checker_Analysis.csv",
        mime="text/csv",
        use_container_width=True,
    )
