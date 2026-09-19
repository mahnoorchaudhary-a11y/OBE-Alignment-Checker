import io
import re
import difflib
from collections import Counter

import streamlit as st
import pandas as pd


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

WEIGHTS = {
    "CLO": 30,
    "PLO": 20,
    "Bloom": 20,
    "Subject Relevance": 10,
    "Clarity": 10,
    "Measurability": 10,
}

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

DEFAULT_STATE = {
    "questions": [],
    "original_questions": [],
    "question_results": [],
    "accepted_revisions": {},
    "analysis_done": False,
    "assessment_name": "",
    "subject": "",
    "course": "",
    "clo_text": "",
    "plo_text": "",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# BASIC TEXT FUNCTIONS
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
    return re.findall(r"[a-zA-Z][a-zA-Z0-9\-]*", text.lower())


def similarity(a, b):
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)

    if not a_norm or not b_norm:
        return 0.0

    return difflib.SequenceMatcher(
        None,
        a_norm,
        b_norm
    ).ratio()


def token_jaccard(a, b):
    a_set = set(words(a))
    b_set = set(words(b))

    if not a_set or not b_set:
        return 0.0

    return len(a_set & b_set) / len(a_set | b_set)


def sentence_case(text):
    text = clean_text(text)

    if not text:
        return text

    text = text[0].upper() + text[1:]

    return text


def ensure_question_mark(text):
    text = clean_text(text)

    if not text:
        return text

    if text.endswith((".", "!", "?")):
        return text

    return text + "?"


def clean_question_candidate(text):
    text = clean_text(text)

    text = re.sub(
        r"^\s*(?:Q(?:uestion)?\s*)?\d{1,3}\s*[\.\):\-]\s*",
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
# FILE READERS
# ============================================================

def read_pdf(uploaded_file):
    raw = uploaded_file.getvalue()

    if not raw:
        return "", "The uploaded PDF is empty."

    extracted = []

    # PyMuPDF
    try:
        import fitz

        pdf = fitz.open(
            stream=raw,
            filetype="pdf"
        )

        for page_number in range(len(pdf)):
            try:
                page = pdf.load_page(page_number)

                text = page.get_text(
                    "text",
                    sort=True
                )

                if text:
                    extracted.append(text)

            except Exception:
                continue

        pdf.close()

        combined = clean_text(
            "\n".join(extracted)
        )

        if len(combined) >= 20:
            return combined, "PyMuPDF text extraction"

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
            return combined, "pypdf text extraction"

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
            return combined, "pdfplumber text extraction"

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

        ocr_pages = []

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
                    ocr_pages.append(text)

            except Exception:
                continue

        pdf.close()

        combined = clean_text(
            "\n".join(ocr_pages)
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
            if paragraph.text:
                parts.append(
                    paragraph.text
                )

        for table in document.tables:
            for row in table.rows:
                values = []

                for cell in row.cells:
                    values.append(
                        cell.text
                    )

                parts.append(
                    " ".join(values)
                )

        text = clean_text(
            "\n".join(parts)
        )

        return text, "DOCX extraction"

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

                    if shape.text:
                        parts.append(
                            shape.text
                        )

        text = clean_text(
            "\n".join(parts)
        )

        return text, "PPTX extraction"

    except Exception as exc:
        return "", f"PPTX error: {exc}"


def read_excel(uploaded_file):
    try:
        data = pd.read_excel(
            io.BytesIO(
                uploaded_file.getvalue()
            ),
            sheet_name=None,
            header=None,
        )

        parts = []

        for sheet_name, df in data.items():

            parts.append(
                f"Sheet: {sheet_name}"
            )

            for row in df.fillna("").values:

                row_text = " ".join(
                    str(value)
                    for value in row
                    if str(value).strip()
                )

                if row_text:
                    parts.append(
                        row_text
                    )

        return clean_text(
            "\n".join(parts)
        ), "Excel extraction"

    except Exception as exc:
        return "", f"Excel error: {exc}"


def read_csv(uploaded_file):
    try:
        df = pd.read_csv(
            io.BytesIO(
                uploaded_file.getvalue()
            ),
            header=None,
        )

        parts = []

        for row in df.fillna("").values:

            row_text = " ".join(
                str(value)
                for value in row
                if str(value).strip()
            )

            if row_text:
                parts.append(
                    row_text
                )

        return clean_text(
            "\n".join(parts)
        ), "CSV extraction"

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
                text = raw.decode(
                    encoding
                )

                return clean_text(
                    text
                ), "Text extraction"

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
        ), "OCR image extraction"

    except Exception as exc:
        return "", f"Image OCR error: {exc}"


def read_uploaded_file(uploaded_file):
    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        return read_pdf(
            uploaded_file
        )

    if name.endswith(".docx"):
        return read_docx(
            uploaded_file
        )

    if name.endswith(".pptx"):
        return read_pptx(
            uploaded_file
        )

    if name.endswith(
        (".xlsx", ".xls", ".xlsm")
    ):
        return read_excel(
            uploaded_file
        )

    if name.endswith(".csv"):
        return read_csv(
            uploaded_file
        )

    if name.endswith(
        (
            ".txt",
            ".md",
            ".rtf",
        )
    ):
        return read_text_file(
            uploaded_file
        )

    if name.endswith(
        (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        )
    ):
        return read_image(
            uploaded_file
        )

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
    IMPORTANT RULE:

    If numbered questions are detected, they are authoritative.

    Example:
        Q1 ...
        Q2 ...
        Q3 ...
        Q4 ...
        Q5 ...

    returns exactly five question blocks.

    No question-mark fallback is allowed to add
    another question after numbered extraction.
    """

    text = clean_text(text)

    if not text:
        return []

    # --------------------------------------------------------
    # FIRST: NUMBERED QUESTIONS
    # --------------------------------------------------------

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

            # Remove marks at end.
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

            if block and len(
                block.split()
            ) >= 3:

                questions.append(
                    block
                )

        # Remove duplicates while preserving order.
        unique = []

        for question in questions:

            duplicate = False

            for previous in unique:

                if (
                    similarity(
                        question,
                        previous
                    ) >= 0.92
                ):
                    duplicate = True
                    break

            if not duplicate:
                unique.append(
                    question
                )

        # THIS IS CRITICAL:
        # return immediately.
        # Do not run any fallback extraction.
        return unique

    # --------------------------------------------------------
    # SECOND: QUESTIONS WITH QUESTION MARKS
    # --------------------------------------------------------

    candidates = []

    for line in text.splitlines():

        line = clean_text(line)

        if not line:
            continue

        if "?" in line and looks_like_question(
            line
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
    # THIRD: VERB-BASED FALLBACK
    # ONLY if there was no numbering AND
    # no question-mark extraction.
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
        or "_____ " in q
    ):
        return "Fill in the Blank"

    if (
        "match the following" in q
        or "matching" in q
    ):
        return "Matching"

    if (
        "case study" in q
        or "scenario" in q
        or "case:" in q
        or "case " in q
    ):
        return "Case/Scenario"

    if re.search(
        r"\b("
        r"calculate|compute|solve|find the value|"
        r"determine the value|velocity|acceleration|"
        r"percentage|probability|mean|median|"
        r"standard deviation|equation|"
        r"numerical"
        r")\b",
        q,
        re.I,
    ):
        return "Numerical"

    if re.search(
        r"\b("
        r"write code|write a program|"
        r"implement|function|algorithm|"
        r"python|java|c\+\+|sql|"
        r"program"
        r")\b",
        q,
        re.I,
    ):
        return "Coding/Practical"

    if (
        len(q.split()) > 45
        or re.search(
            r"\bessay\b",
            q
        )
    ):
        return "Essay/Long Answer"

    if re.search(
        r"\b("
        r"what|define|name|identify|"
        r"state|list|who|when|where"
        r")\b",
        q,
        re.I,
    ):
        return "Short Answer"

    return "Short Answer"


# ============================================================
# BLOOM DETECTION
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

    best_level = max(
        scores,
        key=scores.get
    )

    if scores[best_level] == 0:
        return "Understand"

    return best_level


def bloom_target_from_outcomes(clo, plo):
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
# KEYWORD / TOPIC EXTRACTION
# ============================================================

STOPWORDS = {
    "what",
    "which",
    "when",
    "where",
    "why",
    "how",
    "does",
    "do",
    "did",
    "is",
    "are",
    "was",
    "were",
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


def extract_numbers(question):
    patterns = re.findall(
        r"\b\d+(?:\.\d+)?\s*"
        r"(?:%|kg|g|mg|m|cm|km|s|sec|"
        r"seconds?|minutes?|hours?|"
        r"V|A|N|J|Pa|Hz|M|mol|°C|°F)?\b",
        question,
        flags=re.I,
    )

    return [
        clean_text(x)
        for x in patterns
    ]


def select_topic(
    original,
    clo,
    plo
):
    """
    Use the original question first.

    CLO/PLO are only supporting information.
    Never use the entire CLO as a question.
    """

    original_keywords = extract_keywords(
        original
    )

    if original_keywords:

        # Prefer distinctive terms.
        return " ".join(
            original_keywords[:5]
        )

    clo_keywords = extract_keywords(
        clo
    )

    if clo_keywords:
        return " ".join(
            clo_keywords[:3]
        )

    plo_keywords = extract_keywords(
        plo
    )

    if plo_keywords:
        return " ".join(
            plo_keywords[:3]
        )

    return "the topic"


# ============================================================
# CLO SCORING
# ============================================================

def score_clo(
    question,
    clo
):
    if not clo:
        return None, (
            "CLO has not been provided."
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
            "The CLO does not contain "
            "enough identifiable content."
        )

    overlap = len(
        q_words & clo_words
    ) / max(
        len(clo_words),
        1
    )

    actual_bloom = detect_bloom(
        question
    )

    target_bloom = bloom_target_from_outcomes(
        clo,
        ""
    )

    bloom_gap = abs(
        BLOOM_ORDER[actual_bloom]
        - BLOOM_ORDER[target_bloom]
    )

    score = 50

    score += min(
        35,
        overlap * 70
    )

    if bloom_gap == 0:
        score += 15
    elif bloom_gap == 1:
        score += 7
    elif bloom_gap >= 3:
        score -= 10

    score = max(
        0,
        min(100, round(score))
    )

    if score >= 80:
        feedback = (
            "The question directly measures "
            "the specific course-level knowledge "
            "or skill required by the CLO."
        )
    elif score >= 60:
        feedback = (
            "The question addresses part of the "
            "CLO, but the required content or "
            "action could be made more explicit."
        )
    else:
        feedback = (
            "The question provides limited evidence "
            "of the specific course-level skill "
            "required by the CLO."
        )

    return score, feedback


# ============================================================
# PLO SCORING
# ============================================================

def score_plo(
    question,
    plo
):
    if not plo:
        return None, (
            "PLO has not been provided."
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
            "The PLO does not contain "
            "enough identifiable content."
        )

    overlap = len(
        q_words & plo_words
    ) / max(
        len(plo_words),
        1
    )

    actual = detect_bloom(
        question
    )

    target = bloom_target_from_outcomes(
        "",
        plo
    )

    capability_bonus = 0

    if actual in [
        "Apply",
        "Analyze",
        "Evaluate",
        "Create",
    ]:
        capability_bonus = 15

    score = 45

    score += min(
        30,
        overlap * 60
    )

    score += capability_bonus

    if (
        actual == target
        or BLOOM_ORDER[actual]
        >= BLOOM_ORDER[target]
    ):
        score += 10

    score = max(
        0,
        min(100, round(score))
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
# BLOOM SCORING
# ============================================================

def bloom_analysis(
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

    actual_number = BLOOM_ORDER[
        actual
    ]

    target_number = BLOOM_ORDER[
        target
    ]

    difference = (
        actual_number
        - target_number
    )

    if difference == 0:
        score = 95
        feedback = (
            f"The question operates at "
            f"{actual}, which matches the intended "
            f"{target} cognitive level."
        )

    elif difference == -1:
        score = 78
        feedback = (
            f"The question operates at "
            f"{actual}, slightly below the intended "
            f"{target} level."
        )

    elif difference < -1:
        score = max(
            35,
            72 + difference * 8
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
# OTHER METRICS
# ============================================================

def subject_relevance_score(
    question,
    subject
):
    if not subject.strip():
        return 75

    subject_words = set(
        extract_keywords(
            subject
        )
    )

    if not subject_words:
        return 75

    q_words = set(
        extract_keywords(
            question
        )
    )

    overlap = len(
        subject_words & q_words
    )

    if overlap >= 2:
        return 95

    if overlap == 1:
        return 88

    return 72


def clarity_score(question):
    q = clean_text(question)

    length = len(
        q.split()
    )

    score = 90

    if length < 4:
        score -= 20

    if length > 45:
        score -= 15

    if "??" in q:
        score -= 10

    if q.count("(") != q.count(")"):
        score -= 10

    return max(
        0,
        min(100, score)
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
    ]

    if any(
        verb in q
        for verb in measurable_verbs
    ):
        return 92

    if "what" in q or "why" in q or "how" in q:
        return 82

    return 68


def overall_score(metrics):
    total = 0.0
    total_weight = 0

    for name, weight in WEIGHTS.items():

        value = metrics.get(
            name
        )

        if value is None:
            continue

        total += (
            value * weight
        )

        total_weight += weight

    if total_weight == 0:
        return None

    return round(
        total / total_weight
    )


# ============================================================
# QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question,
    clo,
    plo,
    subject
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
    ) = bloom_analysis(
        question,
        clo,
        plo
    )

    metrics = {
        "CLO": clo_score,
        "PLO": plo_score,
        "Bloom": bloom_score,
        "Subject Relevance": subject_relevance_score(
            question,
            subject
        ),
        "Clarity": clarity_score(
            question
        ),
        "Measurability": measurability_score(
            question
        ),
    }

    score = overall_score(
        metrics
    )

    if score is None:
        status = "Awaiting Learning Outcomes"

    elif score >= ATTAINMENT:
        status = "Alignment Attained"

    elif score >= 60:
        status = "Revision Required"

    elif score >= 40:
        status = "Weak"

    else:
        status = "Poor"

    return {
        "question": question,
        "metrics": metrics,
        "score": score,
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
# REVISION STRATEGIES
# ============================================================

STRATEGIES = {
    "Remember": [
        "identify",
        "distinguish",
        "state",
        "define",
    ],

    "Understand": [
        "explain_relationship",
        "explain_mechanism",
        "explain_purpose",
        "distinguish",
        "example",
    ],

    "Apply": [
        "calculate",
        "apply_to_case",
        "use_method",
        "solve",
        "demonstrate",
    ],

    "Analyze": [
        "compare",
        "cause_effect",
        "relationship",
        "differentiate",
        "interpret",
    ],

    "Evaluate": [
        "justify",
        "assess",
        "recommend",
        "judge",
        "defend",
    ],

    "Create": [
        "design",
        "develop",
        "propose",
        "construct",
        "plan",
    ],
}


def choose_strategies(
    bloom,
    question_index
):
    strategies = STRATEGIES.get(
        bloom,
        STRATEGIES["Understand"]
    )

    if not strategies:
        return []

    shift = (
        question_index
        % len(strategies)
    )

    rotated = (
        strategies[shift:]
        + strategies[:shift]
    )

    return rotated


# ============================================================
# TOPIC EXTRACTION FOR REVISION
# ============================================================

def find_numeric_context(
    question
):
    values = extract_numbers(
        question
    )

    if not values:
        return ""

    return ", ".join(values)


def topic_phrase(
    original,
    clo,
    plo
):
    """
    Extract a short topic rather than copying
    the entire CLO.
    """

    original_words = extract_keywords(
        original
    )

    # Prefer original question terms.
    if original_words:
        selected = original_words[:4]

        return " ".join(
            selected
        )

    clo_words = extract_keywords(
        clo
    )

    if clo_words:
        return " ".join(
            clo_words[:3]
        )

    plo_words = extract_keywords(
        plo
    )

    if plo_words:
        return " ".join(
            plo_words[:3]
        )

    return "the concept"


# ============================================================
# SPECIAL QUESTION CANDIDATES
# ============================================================

def numerical_candidates(
    original,
    topic,
    bloom
):
    candidates = []

    numbers = find_numeric_context(
        original
    )

    if numbers:

        if bloom in [
            "Apply",
            "Analyze",
        ]:

            candidates.append(
                f"Calculate the required result using the given values: {numbers}."
            )

        candidates.append(
            f"Use the given values to solve the problem involving {topic}."
        )

    return candidates


def coding_candidates(
    original,
    topic,
    bloom
):
    candidates = []

    if bloom in [
        "Apply",
        "Create",
    ]:

        candidates.extend([
            f"Write a program that applies {topic} to solve the given task.",
            f"Implement {topic} for a practical problem.",
            f"Develop a simple solution using {topic}.",
        ])

    else:

        candidates.extend([
            f"Explain how {topic} is used in a program.",
            f"Identify the role of {topic} in programming.",
        ])

    return candidates


def case_candidates(
    original,
    topic,
    bloom
):
    if bloom == "Analyze":

        return [
            f"Analyze the main issue in the case involving {topic}.",
            f"What factors in the case explain the outcome related to {topic}?",
            f"How does {topic} contribute to the problem described in the case?",
        ]

    if bloom == "Evaluate":

        return [
            f"Evaluate the most appropriate response to the case involving {topic}.",
            f"Which solution is most suitable for the case involving {topic}, and why?",
        ]

    if bloom == "Apply":

        return [
            f"Apply {topic} to the situation described in the case.",
            f"Use {topic} to solve the problem presented in the case.",
        ]

    return [
        f"Explain the role of {topic} in the case.",
        f"Identify the key issue related to {topic} in the case.",
    ]


# ============================================================
# GENERAL REVISION CANDIDATES
# ============================================================

def general_candidates(
    topic,
    bloom,
    strategy
):
    t = topic.strip()

    if not t:
        t = "the concept"

    candidates = []

    if strategy == "identify":
        candidates.extend([
            f"Identify the key features of {t}.",
            f"Identify the main components of {t}.",
            f"Which features distinguish {t}?",
        ])

    elif strategy == "distinguish":
        candidates.extend([
            f"Distinguish between the main forms of {t}.",
            f"How can {t} be distinguished from related concepts?",
            f"What distinguishes the key forms of {t}?",
        ])

    elif strategy == "state":
        candidates.extend([
            f"State the main characteristics of {t}.",
            f"List the essential features of {t}.",
            f"Name the main components of {t}.",
        ])

    elif strategy == "define":
        candidates.extend([
            f"Define {t} and state its key feature.",
            f"What is {t}?",
            f"How would you define {t}?",
        ])

    elif strategy == "explain_relationship":
        candidates.extend([
            f"How does {t} relate to its main outcome?",
            f"How does {t} affect the related process?",
            f"Explain the relationship between {t} and its main effect.",
        ])

    elif strategy == "explain_mechanism":
        candidates.extend([
            f"How does {t} work?",
            f"How does {t} produce its main effect?",
            f"What process explains how {t} works?",
        ])

    elif strategy == "explain_purpose":
        candidates.extend([
            f"Why is {t} important?",
            f"What is the main purpose of {t}?",
            f"Why is {t} used?",
        ])

    elif strategy == "example":
        candidates.extend([
            f"Give an example that demonstrates {t}.",
            f"Provide an example of {t} in practice.",
            f"Which example best illustrates {t}?",
        ])

    elif strategy == "calculate":
        candidates.extend([
            f"Calculate the result using {t}.",
            f"Use {t} to calculate the required result.",
            f"Solve the problem using {t}.",
        ])

    elif strategy == "apply_to_case":
        candidates.extend([
            f"Apply {t} to a practical situation.",
            f"How would you apply {t} in practice?",
            f"Use {t} to solve a practical problem.",
        ])

    elif strategy == "use_method":
        candidates.extend([
            f"Use {t} to solve the problem.",
            f"Apply {t} to the given situation.",
            f"Demonstrate how {t} can be used.",
        ])

    elif strategy == "solve":
        candidates.extend([
            f"Solve the problem using {t}.",
            f"Determine the result using {t}.",
            f"Use {t} to obtain the required result.",
        ])

    elif strategy == "demonstrate":
        candidates.extend([
            f"Demonstrate how {t} can be applied.",
            f"Demonstrate the use of {t} in practice.",
            f"Show how {t} can solve a practical problem.",
        ])

    elif strategy == "compare":
        candidates.extend([
            f"Compare the main approaches to {t}.",
            f"How do the key forms of {t} differ?",
            f"Compare two important aspects of {t}.",
        ])

    elif strategy == "cause_effect":
        candidates.extend([
            f"How does {t} affect the outcome?",
            f"What causes the main effect associated with {t}?",
            f"How does a change in {t} affect the result?",
        ])

    elif strategy == "relationship":
        candidates.extend([
            f"Analyze the relationship between {t} and its outcome.",
            f"How are {t} and its main effect related?",
            f"What relationship exists between {t} and the outcome?",
        ])

    elif strategy == "differentiate":
        candidates.extend([
            f"Differentiate between the key aspects of {t}.",
            f"How can the main forms of {t} be differentiated?",
            f"What differences are important when examining {t}?",
        ])

    elif strategy == "interpret":
        candidates.extend([
            f"Interpret the result in relation to {t}.",
            f"What does the result indicate about {t}?",
            f"How would you interpret a change in {t}?",
        ])

    elif strategy == "justify":
        candidates.extend([
            f"Justify the most appropriate approach to {t}.",
            f"Why is this approach appropriate for {t}?",
            f"Justify the choice made when applying {t}.",
        ])

    elif strategy == "assess":
        candidates.extend([
            f"Assess the effectiveness of {t}.",
            f"How would you assess the effectiveness of {t}?",
            f"Assess the main limitation of {t}.",
        ])

    elif strategy == "recommend":
        candidates.extend([
            f"Recommend an appropriate solution involving {t}.",
            f"What solution would you recommend for a problem involving {t}?",
            f"Recommend the most suitable approach to {t}.",
        ])

    elif strategy == "judge":
        candidates.extend([
            f"Evaluate the effectiveness of {t}.",
            f"Assess whether the approach to {t} is appropriate.",
            f"Judge the suitability of the approach to {t}.",
        ])

    elif strategy == "defend":
        candidates.extend([
            f"Defend the most suitable approach to {t}.",
            f"Justify why the selected approach to {t} is appropriate.",
            f"Provide evidence to support the chosen approach to {t}.",
        ])

    elif strategy == "design":
        candidates.extend([
            f"Design a simple solution using {t}.",
            f"Design an approach that applies {t}.",
            f"Develop a simple design using {t}.",
        ])

    elif strategy == "develop":
        candidates.extend([
            f"Develop a practical solution using {t}.",
            f"Develop an approach for applying {t}.",
            f"Create a simple solution based on {t}.",
        ])

    elif strategy == "propose":
        candidates.extend([
            f"Propose a practical solution involving {t}.",
            f"Propose an approach for applying {t}.",
            f"What solution would you propose for {t}?",
        ])

    elif strategy == "construct":
        candidates.extend([
            f"Construct a solution using {t}.",
            f"Construct an example that demonstrates {t}.",
            f"Develop a solution based on {t}.",
        ])

    elif strategy == "plan":
        candidates.extend([
            f"Develop a plan for applying {t}.",
            f"How would you plan an approach using {t}?",
            f"Create a practical plan based on {t}.",
        ])

    return candidates


# ============================================================
# REVISION QUALITY CHECKS
# ============================================================

def contains_outcome_language(
    candidate,
    clo,
    plo
):
    text = normalize_text(
        candidate
    )

    forbidden_phrases = [
        "clo",
        "plo",
        "course learning outcome",
        "program learning outcome",
        "learning outcome",
        "learning outcomes",
    ]

    for phrase in forbidden_phrases:

        if phrase in text:
            return True

    # Reject if the candidate is essentially the CLO.
    if similarity(
        candidate,
        clo
    ) >= 0.78:
        return True

    if similarity(
        candidate,
        plo
    ) >= 0.78:
        return True

    return False


def is_duplicate_revision(
    candidate,
    used_suggestions
):
    candidate_norm = normalize_text(
        candidate
    )

    if not candidate_norm:
        return True

    for old in used_suggestions:

        old_norm = normalize_text(
            old
        )

        if candidate_norm == old_norm:
            return True

        if similarity(
            candidate,
            old
        ) >= 0.76:
            return True

        if token_jaccard(
            candidate,
            old
        ) >= 0.72:
            return True

        # Same opening structure.
        candidate_start = " ".join(
            words(candidate)[:5]
        )

        old_start = " ".join(
            words(old)[:5]
        )

        if (
            candidate_start
            and candidate_start == old_start
            and similarity(
                candidate,
                old
            ) >= 0.62
        ):
            return True

    return False


def revision_candidate_valid(
    candidate,
    original,
    clo,
    plo,
    used_suggestions
):
    candidate = clean_text(
        candidate
    )

    if not candidate:
        return False

    word_count = len(
        candidate.split()
    )

    if word_count < 5:
        return False

    # Keep questions concise.
    if word_count > 32:
        return False

    if contains_outcome_language(
        candidate,
        clo,
        plo
    ):
        return False

    # Don't simply reproduce original.
    if similarity(
        candidate,
        original
    ) >= 0.84:
        return False

    if is_duplicate_revision(
        candidate,
        used_suggestions
    ):
        return False

    return True


# ============================================================
# PRESERVE QUESTION TYPE
# ============================================================

def type_specific_candidates(
    original,
    topic,
    bloom
):
    qtype = detect_question_type(
        original
    )

    if qtype == "Numerical":
        return numerical_candidates(
            original,
            topic,
            bloom
        )

    if qtype == "Coding/Practical":
        return coding_candidates(
            original,
            topic,
            bloom
        )

    if qtype == "Case/Scenario":
        return case_candidates(
            original,
            topic,
            bloom
        )

    if qtype == "True/False":
        return [
            f"True or False: {sentence_case(topic)} directly affects the stated outcome."
        ]

    if qtype == "Fill in the Blank":
        return [
            f"Complete the statement by identifying the key term related to {topic}."
        ]

    if qtype == "Matching":
        return [
            f"Match the key terms of {topic} with their correct descriptions."
        ]

    return []


# ============================================================
# CANDIDATE SCORING
# ============================================================

def candidate_revision_score(
    candidate,
    original,
    clo,
    plo,
    subject,
    target_bloom
):
    evaluation = evaluate_question(
        candidate,
        clo,
        plo,
        subject
    )

    score = evaluation[
        "score"
    ]

    if score is None:
        score = 0

    # Reward exact Bloom match.
    if (
        evaluation["actual_bloom"]
        == target_bloom
    ):
        score += 10

    # Reward concise wording.
    length = len(
        candidate.split()
    )

    if 8 <= length <= 22:
        score += 5

    elif length > 28:
        score -= 5

    # Reward question-specific terms.
    original_terms = set(
        extract_keywords(
            original
        )
    )

    candidate_terms = set(
        extract_keywords(
            candidate
        )
    )

    overlap = len(
        original_terms
        & candidate_terms
    )

    if overlap:
        score += min(
            8,
            overlap * 2
        )

    # Reward measurable task.
    if (
        evaluation["metrics"]
        ["Measurability"]
        >= 90
    ):
        score += 4

    return min(
        100,
        round(score)
    ), evaluation


# ============================================================
# GENERATE BEST UNIQUE REVISION
# ============================================================

def generate_best_revision(
    original,
    clo,
    plo,
    subject,
    question_index,
    used_suggestions
):
    target_bloom = bloom_target_from_outcomes(
        clo,
        plo
    )

    # Use the original question to determine
    # the most relevant topic.
    topic = topic_phrase(
        original,
        clo,
        plo
    )

    candidates = []

    # --------------------------------------------------------
    # 1. Question-type candidates first.
    # --------------------------------------------------------

    candidates.extend(
        type_specific_candidates(
            original,
            topic,
            target_bloom
        )
    )

    # --------------------------------------------------------
    # 2. Rotating Bloom strategies.
    # --------------------------------------------------------

    strategies = choose_strategies(
        target_bloom,
        question_index
    )

    for strategy in strategies:

        candidates.extend(
            general_candidates(
                topic,
                target_bloom,
                strategy
            )
        )

    # --------------------------------------------------------
    # 3. Additional strategies.
    # --------------------------------------------------------

    for level in BLOOM_LEVELS:

        if level != target_bloom:

            for strategy in STRATEGIES[
                level
            ]:

                candidates.extend(
                    general_candidates(
                        topic,
                        target_bloom,
                        strategy
                    )
                )

    # --------------------------------------------------------
    # 4. Numerical context should be preserved.
    # --------------------------------------------------------

    if detect_question_type(
        original
    ) == "Numerical":

        numbers = extract_numbers(
            original
        )

        if numbers:

            numeric_text = ", ".join(
                numbers
            )

            candidates.extend([
                f"Calculate the required result using {numeric_text}.",
                f"Use the given values to solve the problem involving {topic}.",
            ])

    # --------------------------------------------------------
    # 5. Remove duplicates inside candidate pool.
    # --------------------------------------------------------

    clean_candidates = []

    for candidate in candidates:

        candidate = sentence_case(
            clean_text(
                candidate
            )
        )

        candidate = ensure_question_mark(
            candidate
        )

        if not candidate:
            continue

        if any(
            similarity(
                candidate,
                old
            ) >= 0.94
            for old in clean_candidates
        ):
            continue

        clean_candidates.append(
            candidate
        )

    # --------------------------------------------------------
    # 6. Evaluate all unique candidates.
    # --------------------------------------------------------

    scored = []

    for candidate in clean_candidates:

        if not revision_candidate_valid(
            candidate,
            original,
            clo,
            plo,
            used_suggestions
        ):
            continue

        score, evaluation = candidate_revision_score(
            candidate,
            original,
            clo,
            plo,
            subject,
            target_bloom
        )

        scored.append(
            (
                score,
                candidate,
                evaluation
            )
        )

    # --------------------------------------------------------
    # 7. Sort by actual evaluated quality.
    # --------------------------------------------------------

    scored.sort(
        key=lambda item: item[0],
        reverse=True
    )

    # --------------------------------------------------------
    # 8. Prefer a genuinely attained candidate.
    # --------------------------------------------------------

    for score, candidate, evaluation in scored:

        actual_score = evaluation[
            "score"
        ]

        if (
            actual_score is not None
            and actual_score >= ATTAINMENT
        ):
            return (
                candidate,
                evaluation
            )

    # --------------------------------------------------------
    # 9. If no candidate reaches 80,
    # return the strongest unique candidate.
    #
    # We do NOT fake the score.
    # --------------------------------------------------------

    if scored:

        _, candidate, evaluation = scored[0]

        return (
            candidate,
            evaluation
        )

    return (
        "",
        None
    )


# ============================================================
# REVISION FOCUS
# ============================================================

def revision_focus(result):
    metrics = result["metrics"]

    weak = []

    for name, value in metrics.items():

        if value is not None and value < ATTAINMENT:
            weak.append(
                name
            )

    if not weak:
        return (
            "The question is already aligned."
        )

    return (
        "Strengthen: "
        + ", ".join(weak)
        + "."
    )


# ============================================================
# STATUS DISPLAY
# ============================================================

def status_badge(score):
    if score is None:
        return "⏳ Awaiting Analysis"

    if score >= ATTAINMENT:
        return "🟢 Alignment Attained"

    if score >= 60:
        return "🟠 Revision Required"

    if score >= 40:
        return "🔴 Weak"

    return "🔴 Poor"


# ============================================================
# ANALYZE ALL QUESTIONS
# ============================================================

def analyze_assessment():
    questions = list(
        st.session_state.questions
    )

    clo = st.session_state.clo_text
    plo = st.session_state.plo_text
    subject = st.session_state.subject

    results = []

    used_suggestions = []

    for index, question in enumerate(
        questions
    ):

        evaluation = evaluate_question(
            question,
            clo,
            plo,
            subject
        )

        # Only generate a revision when needed.
        if (
            evaluation["score"]
            is not None
            and evaluation["score"]
            < ATTAINMENT
        ):

            revision, revision_eval = generate_best_revision(
                question,
                clo,
                plo,
                subject,
                index,
                used_suggestions
            )

            if revision:

                used_suggestions.append(
                    revision
                )

            evaluation[
                "revision"
            ] = revision

            evaluation[
                "revision_evaluation"
            ] = revision_eval

            evaluation[
                "revision_focus"
            ] = revision_focus(
                evaluation
            )

        else:

            evaluation[
                "revision"
            ] = ""

            evaluation[
                "revision_evaluation"
            ] = None

            evaluation[
                "revision_focus"
            ] = ""

        evaluation[
            "question_number"
        ] = index + 1

        results.append(
            evaluation
        )

    st.session_state.question_results = results
    st.session_state.analysis_done = True
    st.session_state.accepted_revisions = {}


# ============================================================
# APPLY REVISION
# ============================================================

def apply_revision(
    question_index
):
    results = st.session_state.question_results

    if (
        question_index < 0
        or question_index >= len(results)
    ):
        return

    result = results[
        question_index
    ]

    revision = result.get(
        "revision",
        ""
    )

    revision_eval = result.get(
        "revision_evaluation"
    )

    if not revision or revision_eval is None:
        return

    before = result["score"]

    # Replace original question.
    st.session_state.questions[
        question_index
    ] = revision

    # Recalculate using the actual revised question.
    new_result = evaluate_question(
        revision,
        st.session_state.clo_text,
        st.session_state.plo_text,
        st.session_state.subject,
    )

    after = new_result[
        "score"
    ]

    new_result[
        "question_number"
    ] = question_index + 1

    new_result[
        "revision"
    ] = ""

    new_result[
        "revision_evaluation"
    ] = None

    new_result[
        "revision_focus"
    ] = ""

    new_result[
        "before_score"
    ] = before

    new_result[
        "after_score"
    ] = after

    st.session_state.question_results[
        question_index
    ] = new_result

    st.session_state.accepted_revisions[
        question_index
    ] = {
        "before": before,
        "after": after,
        "question": revision,
    }


# ============================================================
# APP HEADER
# ============================================================

st.title("🎓 OBE Quiz Checker")

st.caption(
    "Check assessment questions for CLO, PLO, Bloom, "
    "subject relevance, clarity and measurability."
)


# ============================================================
# ASSESSMENT INFORMATION
# ============================================================

st.header("1. Assessment Information")

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
# LEARNING OUTCOMES
# ============================================================

st.header("2. Learning Outcomes")

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

    st.warning(
        "⏳ Enter the CLO(s) and PLO(s) before analysis."
    )


# ============================================================
# UPLOAD
# ============================================================

st.header("3. Upload Complete Assessment")

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
        use_container_width=True
    ):

        with st.spinner(
            "Reading assessment..."
        ):

            extracted_text, method = read_uploaded_file(
                uploaded_file
            )

        if not extracted_text:

            st.error(
                "The file could not be read. "
                "Please check that it contains readable text "
                "or upload a clearer file."
            )

        else:

            questions = extract_questions(
                extracted_text
            )

            st.session_state.questions = questions
            st.session_state.original_questions = list(
                questions
            )
            st.session_state.question_results = []
            st.session_state.analysis_done = False
            st.session_state.accepted_revisions = {}

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
        "Numbered questions are treated as authoritative. "
        "The checker does not create additional questions "
        "from fallback extraction after numbered questions "
        "have been detected."
    )


# ============================================================
# ANALYZE BUTTON
# ============================================================

st.header("4. Analyze Assessment")

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
            "⏳ Enter both CLO(s) and PLO(s) before analysis."
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
        f"{len(st.session_state.questions)} "
        f"question(s) analyzed."
    )


# ============================================================
# RESULTS
# ============================================================

if st.session_state.analysis_done:

    results = st.session_state.question_results

    # Safety check.
    # This guarantees the result count cannot exceed
    # the extracted question count.
    results = results[
        :len(
            st.session_state.questions
        )
    ]

    # ========================================================
    # OVERALL
    # ========================================================

    st.header(
        "5. Overall Alignment"
    )

    valid_scores = [
        result["score"]
        for result in results
        if result["score"] is not None
    ]

    if valid_scores:

        overall = round(
            sum(valid_scores)
            / len(valid_scores)
        )

        overall_col1, overall_col2 = st.columns(
            [1, 2]
        )

        with overall_col1:

            st.metric(
                "Overall Score",
                f"{overall}/100"
            )

        with overall_col2:

            if overall >= ATTAINMENT:

                st.success(
                    f"🟢 Alignment Attained — "
                    f"{overall}/100"
                )

                # Celebration only after actual analysis.
                st.balloons()

            else:

                st.warning(
                    f"🟠 Revision Required — "
                    f"{overall}/100"
                )

    else:

        st.info(
            "No score could be calculated."
        )

    # ========================================================
    # REVISIONS FIRST
    # ========================================================

    st.header(
        "6. Questions Requiring Revision"
    )

    weak_results = [
        result
        for result in results
        if (
            result["score"] is not None
            and result["score"] < ATTAINMENT
        )
    ]

    if not weak_results:

        st.success(
            "🎉 No questions require revision."
        )

    else:

        st.write(
            f"**{len(weak_results)} "
            f"question(s) require revision.**"
        )

        for result in weak_results:

            qnum = result[
                "question_number"
            ]

            st.subheader(
                f"Question {qnum} "
                f"— {result['score']}/100"
            )

            st.error(
                status_badge(
                    result["score"]
                )
            )

            st.markdown(
                "**Current Question**"
            )

            st.write(
                result["question"]
            )

            st.markdown(
                "**Question Type:** "
                + result["question_type"]
            )

            # ----------------------------------------------
            # METRICS
            # ----------------------------------------------

            metric_cols = st.columns(6)

            metric_names = [
                "CLO",
                "PLO",
                "Bloom",
                "Subject Relevance",
                "Clarity",
                "Measurability",
            ]

            for col, name in zip(
                metric_cols,
                metric_names
            ):

                with col:

                    value = result[
                        "metrics"
                    ].get(name)

                    if value is None:
                        st.metric(
                            name,
                            "N/A"
                        )
                    else:
                        st.metric(
                            name,
                            f"{value}%"
                        )

            # ----------------------------------------------
            # DISTINCT FEEDBACK
            # ----------------------------------------------

            with st.expander(
                "CLO Evaluation"
            ):

                clo_value = result[
                    "metrics"
                ]["CLO"]

                st.write(
                    f"**CLO Score:** "
                    f"{clo_value}%"
                )

                st.write(
                    result[
                        "clo_feedback"
                    ]
                )

            with st.expander(
                "PLO Evaluation"
            ):

                plo_value = result[
                    "metrics"
                ]["PLO"]

                st.write(
                    f"**PLO Score:** "
                    f"{plo_value}%"
                )

                st.write(
                    result[
                        "plo_feedback"
                    ]
                )

            with st.expander(
                "Bloom Evaluation"
            ):

                bloom_value = result[
                    "metrics"
                ]["Bloom"]

                st.write(
                    f"**Bloom Score:** "
                    f"{bloom_value}%"
                )

                st.write(
                    f"**Actual Level:** "
                    f"{result['actual_bloom']}"
                )

                st.write(
                    f"**Target Level:** "
                    f"{result['target_bloom']}"
                )

                st.write(
                    result[
                        "bloom_feedback"
                    ]
                )

            st.markdown(
                "**Revision Focus**"
            )

            st.write(
                result[
                    "revision_focus"
                ]
            )

            # ----------------------------------------------
            # SUGGESTED QUESTION
            # ----------------------------------------------

            revision = result.get(
                "revision",
                ""
            )

            if revision:

                st.markdown(
                    "### 💡 Suggested Question"
                )

                st.success(
                    revision
                )

                revision_eval = result.get(
                    "revision_evaluation"
                )

                if revision_eval:

                    suggested_score = revision_eval[
                        "score"
                    ]

                    st.write(
                        f"**Predicted alignment after "
                        f"revision: "
                        f"{suggested_score}/100**"
                    )

                    if suggested_score >= ATTAINMENT:

                        st.success(
                            "🟢 This suggested question "
                            "meets the alignment threshold."
                        )

                    else:

                        st.warning(
                            "The generated question is the "
                            "strongest unique candidate available "
                            "but still requires improvement."
                        )

                if st.button(
                    "✅ Use This Suggested Question",
                    key=f"use_revision_{qnum}",
                    use_container_width=True,
                ):

                    apply_revision(
                        qnum - 1
                    )

                    st.rerun()

            # ----------------------------------------------
            # ACCEPTED REVISION RESULT
            # ----------------------------------------------

            if (
                qnum - 1
                in st.session_state.accepted_revisions
            ):

                accepted = (
                    st.session_state
                    .accepted_revisions[
                        qnum - 1
                    ]
                )

                st.markdown(
                    "### Revision Applied"
                )

                st.write(
                    accepted[
                        "question"
                    ]
                )

                st.write(
                    f"Before: "
                    f"**{accepted['before']}/100**"
                )

                st.write(
                    f"After: "
                    f"**{accepted['after']}/100**"
                )

                if (
                    accepted["after"]
                    >= ATTAINMENT
                ):

                    st.success(
                        "🟢 Alignment Attained"
                    )

                else:

                    st.warning(
                        "🟠 Alignment still requires revision."
                    )

            st.divider()

    # ========================================================
    # ATTAINED QUESTIONS
    # ========================================================

    st.header(
        "7. Attained Questions"
    )

    attained_results = [
        result
        for result in results
        if (
            result["score"] is not None
            and result["score"] >= ATTAINMENT
        )
    ]

    if attained_results:

        for result in attained_results:

            st.success(
                f"Q{result['question_number']} "
                f"— {result['score']}/100 "
                f"— 🟢 Alignment Attained"
            )

            st.write(
                result["question"]
            )

    else:

        st.info(
            "No questions have currently attained "
            "the 80% alignment threshold."
        )

    # ========================================================
    # ONE GRAPH ONLY
    # ========================================================

    st.header(
        "8. Alignment Overview"
    )

    chart_data = pd.DataFrame({
        "Question": [
            f"Q{r['question_number']}"
            for r in results
        ],
        "Score": [
            r["score"]
            for r in results
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

    for result in results:

        overview_rows.append({
            "Question":
                f"Q{result['question_number']}",

            "Question Type":
                result["question_type"],

            "Score":
                result["score"],

            "CLO":
                result["metrics"]["CLO"],

            "PLO":
                result["metrics"]["PLO"],

            "Bloom":
                result["metrics"]["Bloom"],

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
                status_badge(
                    result["score"]
                ),
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

    for result in results:

        with st.expander(
            f"Q{result['question_number']} "
            f"— {result['score']}/100"
        ):

            st.write(
                "**Question:**"
            )

            st.write(
                result["question"]
            )

            st.write(
                f"**Type:** "
                f"{result['question_type']}"
            )

            st.write(
                f"**Actual Bloom:** "
                f"{result['actual_bloom']}"
            )

            st.write(
                f"**Target Bloom:** "
                f"{result['target_bloom']}"
            )

            st.write(
                "**CLO Evaluation:**"
            )

            st.write(
                result[
                    "clo_feedback"
                ]
            )

            st.write(
                "**PLO Evaluation:**"
            )

            st.write(
                result[
                    "plo_feedback"
                ]
            )

            st.write(
                "**Bloom Evaluation:**"
            )

            st.write(
                result[
                    "bloom_feedback"
                ]
            )

    # ========================================================
    # EXPORT
    # ========================================================

    st.header(
        "11. Export"
    )

    export_rows = []

    for result in results:

        export_rows.append({
            "Question Number":
                result["question_number"],

            "Question":
                result["question"],

            "Question Type":
                result["question_type"],

            "Overall Score":
                result["score"],

            "CLO Score":
                result["metrics"]["CLO"],

            "CLO Feedback":
                result["clo_feedback"],

            "PLO Score":
                result["metrics"]["PLO"],

            "PLO Feedback":
                result["plo_feedback"],

            "Bloom Score":
                result["metrics"]["Bloom"],

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

            "Status":
                status_badge(
                    result["score"]
                ),

            "Suggested Revision":
                result.get(
                    "revision",
                    ""
                ),
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
