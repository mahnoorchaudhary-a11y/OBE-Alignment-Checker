import io
import re
import difflib
import random
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

QUESTION_TYPES = [
    "Same as Current",
    "MCQ",
    "True / False",
    "Fill in the Blank",
    "Short Answer",
    "Essay / Long Answer",
    "Case / Scenario",
    "Numerical",
    "Practical / Application",
]


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
    "revisions": {},
    "generated_questions": {},
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

    text = text.replace(
        "\x00",
        " "
    )

    text = text.replace(
        "\ufeff",
        " "
    )

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
        r"\n\s*\n+",
        "\n",
        text
    )

    return text.strip()


def normalize_text(text):

    text = clean_text(
        text
    ).lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

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
# FILE READERS
# ============================================================

def read_pdf(uploaded_file):

    raw = uploaded_file.getvalue()

    if not raw:
        return "", "The uploaded PDF is empty."

    try:

        import fitz

        pdf = fitz.open(
            stream=raw,
            filetype="pdf"
        )

        pages = []

        for page_number in range(
            len(pdf)
        ):

            try:

                page = pdf.load_page(
                    page_number
                )

                text = page.get_text(
                    "text",
                    sort=True
                )

                if text:
                    pages.append(
                        text
                    )

            except Exception:
                continue

        pdf.close()

        combined = clean_text(
            "\n".join(pages)
        )

        if len(combined) >= 20:

            return (
                combined,
                "PyMuPDF"
            )

    except Exception:
        pass

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
                    pages.append(
                        text
                    )

            except Exception:
                continue

        combined = clean_text(
            "\n".join(pages)
        )

        if len(combined) >= 20:

            return (
                combined,
                "pypdf"
            )

    except Exception:
        pass

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
                        pages.append(
                            text
                        )

                except Exception:
                    continue

        combined = clean_text(
            "\n".join(pages)
        )

        if len(combined) >= 20:

            return (
                combined,
                "pdfplumber"
            )

    except Exception:
        pass

    try:

        import fitz
        from PIL import Image
        import pytesseract

        pdf = fitz.open(
            stream=raw,
            filetype="pdf"
        )

        pages = []

        for page_number in range(
            len(pdf)
        ):

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
                    io.BytesIO(
                        image_bytes
                    )
                )

                text = pytesseract.image_to_string(
                    image,
                    config="--psm 6"
                )

                if text:
                    pages.append(
                        text
                    )

            except Exception:
                continue

        pdf.close()

        combined = clean_text(
            "\n".join(pages)
        )

        if len(combined) >= 20:

            return (
                combined,
                "OCR"
            )

    except Exception:
        pass

    return (
        "",
        "No readable text was extracted from the PDF."
    )


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

                values = []

                for cell in row.cells:

                    if cell.text.strip():

                        values.append(
                            cell.text
                        )

                if values:

                    parts.append(
                        " ".join(values)
                    )

        return (
            clean_text(
                "\n".join(parts)
            ),
            "DOCX"
        )

    except Exception as exc:

        return (
            "",
            f"DOCX error: {exc}"
        )


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

        return (
            clean_text(
                "\n".join(parts)
            ),
            "PPTX"
        )

    except Exception as exc:

        return (
            "",
            f"PPTX error: {exc}"
        )


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
            "Excel"
        )

    except Exception as exc:

        return (
            "",
            f"Excel error: {exc}"
        )


def read_csv(uploaded_file):

    try:

        dataframe = pd.read_csv(
            io.BytesIO(
                uploaded_file.getvalue()
            ),
            header=None
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
            "CSV"
        )

    except Exception as exc:

        return (
            "",
            f"CSV error: {exc}"
        )


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
                        raw.decode(
                            encoding
                        )
                    ),
                    "Text"
                )

            except Exception:
                continue

        return (
            "",
            "Could not decode text file."
        )

    except Exception as exc:

        return (
            "",
            f"Text error: {exc}"
        )


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
            "OCR"
        )

    except Exception as exc:

        return (
            "",
            f"OCR error: {exc}"
        )


def read_uploaded_file(uploaded_file):

    filename = uploaded_file.name.lower()

    if filename.endswith(".pdf"):
        return read_pdf(uploaded_file)

    if filename.endswith(".docx"):
        return read_docx(uploaded_file)

    if filename.endswith(".pptx"):
        return read_pptx(uploaded_file)

    if filename.endswith(
        (
            ".xlsx",
            ".xls",
            ".xlsm",
        )
    ):
        return read_excel(uploaded_file)

    if filename.endswith(".csv"):
        return read_csv(uploaded_file)

    if filename.endswith(
        (
            ".txt",
            ".md",
            ".rtf",
        )
    ):
        return read_text_file(
            uploaded_file
        )

    if filename.endswith(
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

    return (
        "",
        "Unsupported file format."
    )


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


def extract_questions(text):

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

    # ========================================================
    # NUMBERED QUESTIONS ARE AUTHORITATIVE
    # ========================================================

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

        unique = []

        for question in questions:

            duplicate = any(
                similarity(
                    question,
                    old
                ) >= 0.92
                for old in unique
            )

            if not duplicate:

                unique.append(
                    question
                )

        return unique

    # ========================================================
    # QUESTION MARK EXTRACTION
    # ========================================================

    candidates = []

    for line in text.splitlines():

        line = clean_text(
            line
        )

        if (
            line
            and "?" in line
            and len(line.split()) >= 3
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

    # ========================================================
    # VERB FALLBACK
    # ========================================================

    candidates = []

    for line in text.splitlines():

        line = clean_text(
            line
        )

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

    return "Short Answer"


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
# KEYWORD EXTRACTION
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

    for token in tokenize(
        text
    ):

        if len(token) < 3:
            continue

        if token in STOPWORDS:
            continue

        if token not in result:

            result.append(
                token
            )

    return result


def topic_from_question(
    question,
    clo,
    plo
):

    q_terms = extract_keywords(
        question
    )

    if q_terms:

        return " ".join(
            q_terms[:8]
        )

    outcome_terms = extract_keywords(
        clo + " " + plo
    )

    if outcome_terms:

        return " ".join(
            outcome_terms[:8]
        )

    return "the core concept"


# ============================================================
# CLO SCORING
# ============================================================

def score_clo(
    question,
    clo
):

    if not clo.strip():

        return (
            None,
            "CLO was not provided."
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

        return (
            50,
            "The CLO does not contain enough "
            "identifiable terms for analysis."
        )

    overlap = (
        len(
            q_words & clo_words
        )
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

    else:

        feedback = (
            f"CLO alignment is {score}%, "
            f"which is below the {ATTAINMENT}% "
            "attainment threshold."
        )

    return (
        score,
        feedback
    )


# ============================================================
# PLO SCORING
# ============================================================

def score_plo(
    question,
    plo
):

    if not plo.strip():

        return (
            None,
            "PLO was not provided."
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

        return (
            50,
            "The PLO does not contain enough "
            "identifiable terms for analysis."
        )

    overlap = (
        len(
            q_words & plo_words
        )
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
            f"PLO alignment is {score}%, "
            f"which is below the {ATTAINMENT}% "
            "attainment threshold."
        )

    return (
        score,
        feedback
    )


# ============================================================
# BLOOM SCORING
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
            f"the {ATTAINMENT}% threshold."
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
            f"the {ATTAINMENT}% threshold."
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
        feedback
    )


# ============================================================
# OTHER SCORING
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


def clarity_score(question):

    score = 90

    count = len(
        question.split()
    )

    if count < 4:

        score -= 20

    if count > 50:

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

    verbs = [
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
        for verb in verbs
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
# FULL EVALUATION
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
        bloom_feedback
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

    elif overall >= ATTAINMENT_THRESHOLD:

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
# WEAK AREA DETECTION
# ============================================================

def get_weak_metrics(result):

    weak = []

    for metric in METRIC_KEYS:

        value = result[
            "metrics"
        ].get(metric)

        if (
            value is not None
            and value < ATTAINMENT_THRESHOLD
        ):

            weak.append(
                (
                    metric,
                    value
                )
            )

    weak.sort(
        key=lambda x: x[1]
    )

    return weak


# ============================================================
# REVISION / NEW QUESTION GENERATOR
# ============================================================

def replace_opening(
    question,
    target_bloom
):

    topic = clean_text(
        re.sub(
            r"^\s*(what|why|how|explain|describe|define|"
            r"identify|calculate|compute|solve|analyze|"
            r"analyse|compare|contrast|evaluate|assess|"
            r"discuss|justify|interpret|determine|"
            r"demonstrate|apply|design|develop|write|"
            r"state|list|name)\b",
            "",
            question,
            flags=re.I,
        )
    )

    if not topic:

        topic = question

    prompts = {

        "Remember": [
            f"Define {topic} and state its key characteristics.",
            f"Identify the main concept involved in {topic} and list its essential features.",
            f"State the key principles associated with {topic}."
        ],

        "Understand": [
            f"Explain {topic} in your own words and describe why it is important.",
            f"Describe {topic} and explain the relationship among its main components.",
            f"Explain the main idea of {topic} using an appropriate example."
        ],

        "Apply": [
            f"Apply the principles of {topic} to a suitable practical situation and explain the result.",
            f"Using the principles of {topic}, solve an appropriate problem and justify your approach.",
            f"Demonstrate how {topic} can be applied to a realistic situation."
        ],

        "Analyze": [
            f"Analyze {topic} by identifying its major components, relationships, and underlying factors.",
            f"Compare the relevant factors in {topic} and analyze how they influence the outcome.",
            f"Examine {topic} and analyze the relationship between its major elements."
        ],

        "Evaluate": [
            f"Evaluate {topic} using appropriate criteria and justify your conclusion with evidence.",
            f"Assess the effectiveness of the relevant approach to {topic} and justify your judgment.",
            f"Evaluate the alternatives related to {topic} and defend the most appropriate conclusion."
        ],

        "Create": [
            f"Design an appropriate solution related to {topic} and justify the major decisions in your design.",
            f"Develop a suitable approach for addressing a problem involving {topic} and explain your design choices.",
            f"Construct a practical solution involving {topic} and explain how it would achieve the intended outcome."
        ],
    }

    return random.choice(
        prompts.get(
            target_bloom,
            prompts["Understand"]
        )
    )


def generate_mcq(
    topic,
    bloom
):

    stems = {

        "Remember":
            f"Which statement correctly identifies a key characteristic of {topic}?",

        "Understand":
            f"Which statement best explains the main principle of {topic}?",

        "Apply":
            f"Which action best demonstrates the application of {topic} in a practical situation?",

        "Analyze":
            f"Which interpretation best explains the relationship among the major factors in {topic}?",

        "Evaluate":
            f"Which judgment about {topic} is best supported by appropriate criteria?",

        "Create":
            f"Which proposed approach would be most appropriate for developing a solution involving {topic}?",
    }

    return stems.get(
        bloom,
        stems["Understand"]
    )


def generate_true_false(
    topic,
    bloom
):

    statements = {

        "Remember":
            f"True or False: {topic} includes identifiable principles or characteristics that can be stated accurately.",

        "Understand":
            f"True or False: Understanding {topic} requires explaining the relationship between its major concepts.",

        "Apply":
            f"True or False: The principles of {topic} can be applied to an appropriate practical situation.",

        "Analyze":
            f"True or False: Analyzing {topic} involves examining relationships among its major components.",

        "Evaluate":
            f"True or False: Evaluating {topic} requires applying relevant criteria before reaching a conclusion.",

        "Create":
            f"True or False: Creating a solution involving {topic} requires selecting and organizing appropriate elements.",
    }

    return statements.get(
        bloom,
        statements["Understand"]
    )


def generate_fill_blank(
    topic,
    bloom
):

    return (
        f"Complete the statement by providing the appropriate "
        f"concept or principle related to {topic}: "
        f"The central principle that explains the operation "
        f"or application of {topic} is __________."
    )


def generate_short_answer(
    topic,
    bloom
):

    prompts = {

        "Remember":
            f"Identify and briefly describe the essential characteristics of {topic}.",

        "Understand":
            f"Explain the main concept of {topic} in your own words and provide one relevant example.",

        "Apply":
            f"Apply the relevant principles of {topic} to a practical situation and explain your response.",

        "Analyze":
            f"Analyze {topic} by explaining its major components and the relationships among them.",

        "Evaluate":
            f"Evaluate an approach related to {topic} and justify your conclusion using relevant criteria.",

        "Create":
            f"Develop a suitable solution to a problem involving {topic} and explain the major decisions involved.",
    }

    return prompts.get(
        bloom,
        prompts["Understand"]
    )


def generate_essay(
    topic,
    bloom
):

    prompts = {

        "Remember":
            f"Discuss the key facts, terminology, and characteristics associated with {topic}.",

        "Understand":
            f"Explain {topic} comprehensively, including its major concepts, relationships, and significance.",

        "Apply":
            f"Explain how the principles of {topic} can be applied to a realistic situation. Support your response with an appropriate example.",

        "Analyze":
            f"Analyze {topic} by examining its major components, relationships, causes, and consequences.",

        "Evaluate":
            f"Evaluate the major approaches or alternatives related to {topic}. Use appropriate criteria and justify your conclusion.",

        "Create":
            f"Develop a comprehensive solution or framework for addressing a problem related to {topic}. Explain and justify your design decisions.",
    }

    return prompts.get(
        bloom,
        prompts["Understand"]
    )


def generate_case(
    topic,
    bloom
):

    prompts = {

        "Remember":
            f"Case: A learner encounters a situation involving {topic}. Identify the key concepts or principles that are relevant to the case.",

        "Understand":
            f"Case: A realistic situation involves {topic}. Explain the concepts involved and describe how they relate to the situation.",

        "Apply":
            f"Case: A realistic problem involving {topic} has occurred. Apply the relevant principles to determine an appropriate response and explain your reasoning.",

        "Analyze":
            f"Case: A complex situation involves {topic} and several interacting factors. Analyze the factors and explain how they contribute to the outcome.",

        "Evaluate":
            f"Case: Two possible approaches are available for a situation involving {topic}. Evaluate the approaches using appropriate criteria and justify your recommendation.",

        "Create":
            f"Case: An organization faces a new problem involving {topic}. Design a suitable solution and justify how your solution addresses the major requirements.",
    }

    return prompts.get(
        bloom,
        prompts["Analyze"]
    )


def generate_numerical(
    topic,
    bloom
):

    if bloom in [
        "Analyze",
        "Evaluate",
        "Create"
    ]:

        return (
            f"A numerical problem related to {topic} "
            f"involves several measurable variables. "
            f"Determine the appropriate calculation or "
            f"method, solve the problem, and justify why "
            f"your method is appropriate."
        )

    return (
        f"Consider a numerical situation involving "
        f"{topic}. Identify the relevant values, "
        f"select the appropriate formula or method, "
        f"and calculate the required result."
    )


def generate_practical(
    topic,
    bloom
):

    prompts = {

        "Remember":
            f"Identify the main procedure or technique used when working with {topic}.",

        "Understand":
            f"Describe the procedure used to work with {topic} and explain the purpose of its main steps.",

        "Apply":
            f"Demonstrate how you would apply the appropriate procedure for a practical task involving {topic}.",

        "Analyze":
            f"Analyze a practical task involving {topic}, identify the critical steps, and explain the consequences of errors at each stage.",

        "Evaluate":
            f"Evaluate two possible practical approaches to {topic} and justify which approach should be used under the given circumstances.",

        "Create":
            f"Design a practical procedure for addressing a task involving {topic}. Explain and justify the major steps.",
    }

    return prompts.get(
        bloom,
        prompts["Apply"]
    )


def generate_question_by_type(
    topic,
    bloom,
    question_type
):

    if question_type == "MCQ":

        return generate_mcq(
            topic,
            bloom
        )

    if question_type == "True / False":

        return generate_true_false(
            topic,
            bloom
        )

    if question_type == "Fill in the Blank":

        return generate_fill_blank(
            topic,
            bloom
        )

    if question_type == "Short Answer":

        return generate_short_answer(
            topic,
            bloom
        )

    if question_type == "Essay / Long Answer":

        return generate_essay(
            topic,
            bloom
        )

    if question_type == "Case / Scenario":

        return generate_case(
            topic,
            bloom
        )

    if question_type == "Numerical":

        return generate_numerical(
            topic,
            bloom
        )

    if question_type == "Practical / Application":

        return generate_practical(
            topic,
            bloom
        )

    return generate_short_answer(
        topic,
        bloom
    )


def improve_existing_question(
    question,
    target_bloom,
    weak_metrics
):

    topic = topic_from_question(
        question,
        st.session_state.clo_text,
        st.session_state.plo_text
    )

    weak_names = [
        item[0]
        for item in weak_metrics
    ]

    focus = ""

    if "CLO Alignment" in weak_names:

        focus += (
            " Make the course-specific concept "
            "and required skill explicit."
        )

    if "PLO Alignment" in weak_names:

        focus += (
            " Include an observable application "
            "or broader capability."
        )

    if "Bloom Alignment" in weak_names:

        focus += (
            f" Require the learner to operate at "
            f"the {target_bloom} cognitive level."
        )

    # --------------------------------------------------------
    # Revision transformations
    # --------------------------------------------------------

    revision_templates = {

        "Remember":
            f"Define {topic} and state its essential characteristics.",

        "Understand":
            f"Explain {topic} in your own words and describe its significance.",

        "Apply":
            f"Apply the principles of {topic} to a realistic situation and explain your response.",

        "Analyze":
            f"Analyze {topic} by examining its major components, relationships, and contributing factors.",

        "Evaluate":
            f"Evaluate an approach related to {topic} using appropriate criteria and justify your conclusion.",

        "Create":
            f"Design a suitable solution involving {topic} and justify the major decisions in your design.",
    }

    base = revision_templates.get(
        target_bloom,
        revision_templates["Understand"]
    )

    return clean_text(
        base + focus
    )


def create_candidate_set(
    original_question,
    mode,
    target_bloom,
    question_type
):

    topic = topic_from_question(
        original_question,
        st.session_state.clo_text,
        st.session_state.plo_text
    )

    candidates = []

    if mode == "revision":

        weak = get_weak_metrics(
            evaluate_question(
                original_question,
                st.session_state.clo_text,
                st.session_state.plo_text,
                st.session_state.subject,
                st.session_state.course,
            )
        )

        # Generate several distinct transformations.
        for _ in range(8):

            candidate = improve_existing_question(
                original_question,
                target_bloom,
                weak
            )

            if candidate not in candidates:

                candidates.append(
                    candidate
                )

        # Add type-specific alternatives.
        for selected_type in [
            question_type,
            "Short Answer",
            "Case / Scenario",
            "Practical / Application",
        ]:

            if selected_type != "Same as Current":

                candidate = generate_question_by_type(
                    topic,
                    target_bloom,
                    selected_type
                )

                if candidate not in candidates:

                    candidates.append(
                        candidate
                    )

    else:

        for selected_type in [
            question_type,
            "Short Answer",
            "Case / Scenario",
            "Practical / Application",
            "Essay / Long Answer",
            "MCQ",
        ]:

            if selected_type == "Same as Current":

                selected_type = "Short Answer"

            for _ in range(2):

                candidate = generate_question_by_type(
                    topic,
                    target_bloom,
                    selected_type
                )

                if candidate not in candidates:

                    candidates.append(
                        candidate
                    )

    return candidates


def generate_best_candidate(
    original_question,
    mode,
    target_bloom,
    question_type
):

    candidates = create_candidate_set(
        original_question,
        mode,
        target_bloom,
        question_type
    )

    evaluated = []

    for candidate in candidates:

        if similarity(
            candidate,
            original_question
        ) >= 0.90:

            continue

        result = evaluate_question(
            candidate,
            st.session_state.clo_text,
            st.session_state.plo_text,
            st.session_state.subject,
            st.session_state.course,
        )

        evaluated.append(
            (
                result["score"] or 0,
                candidate,
                result
            )
        )

    if not evaluated:

        fallback = generate_question_by_type(
            topic_from_question(
                original_question,
                st.session_state.clo_text,
                st.session_state.plo_text
            ),
            target_bloom,
            "Short Answer"
        )

        fallback_result = evaluate_question(
            fallback,
            st.session_state.clo_text,
            st.session_state.plo_text,
            st.session_state.subject,
            st.session_state.course,
        )

        return (
            fallback,
            fallback_result
        )

    # Select the candidate with the strongest actual
    # evaluated alignment score.
    evaluated.sort(
        key=lambda item: item[0],
        reverse=True
    )

    best_score, best_question, best_result = (
        evaluated[0]
    )

    return (
        best_question,
        best_result
    )


# ============================================================
# METRIC AGGREGATION
# ============================================================

def calculate_metric_averages(
    results
):

    averages = {}

    for metric in METRIC_KEYS:

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


def get_status(value):

    if value is None:

        return "⏳ Not Available"

    if value >= 85:

        return "🟢 Strong"

    if value >= ATTAINMENT_THRESHOLD:

        return "🟢 Attained"

    if value >= 60:

        return "🟠 Needs Attention"

    return "🔴 Weak"


# ============================================================
# ANALYSIS
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

    # New assessment invalidates old generated items.
    st.session_state.revisions = {}
    st.session_state.generated_questions = {}


# ============================================================
# HEADER
# ============================================================

st.title(
    "🎓 OBE Quiz Checker"
)

st.caption(
    "Assessment quality, CLO/PLO alignment and Bloom analysis "
    "with question revision and new-question generation."
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
        placeholder="e.g. Quiz 1"
    )

with col2:

    st.session_state.course = st.text_input(
        "Course",
        value=st.session_state.course,
        placeholder="e.g. General Chemistry"
    )

with col3:

    st.session_state.subject = st.text_input(
        "Subject",
        value=st.session_state.subject,
        placeholder="e.g. Chemistry"
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
        )
    )

with plo_col:

    st.session_state.plo_text = st.text_area(
        "PLO(s)",
        value=st.session_state.plo_text,
        height=140,
        placeholder=(
            "Enter the relevant Program Learning Outcome(s)."
        )
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
    ]
)

if uploaded_file is not None:

    if st.button(
        "📄 Read Assessment",
        use_container_width=True
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
            st.session_state.revisions = {}
            st.session_state.generated_questions = {}

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
# DETECTED QUESTIONS
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
    use_container_width=True
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

    results = results[
        :len(
            st.session_state.questions
        )
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

        if overall >= ATTAINMENT_THRESHOLD:

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

    weak_metrics = []

    for metric in METRIC_KEYS:

        value = averages[metric]

        if (
            value is not None
            and value < ATTAINMENT_THRESHOLD
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

    st.subheader(
        "⚠️ Weak Areas"
    )

    if weak_metrics:

        for metric, value in weak_metrics:

            st.warning(
                f"**{metric}: {value}%** — "
                f"below the {ATTAINMENT_THRESHOLD}% "
                f"attainment threshold."
            )

    else:

        st.success(
            f"🟢 All overall metrics have reached "
            f"{ATTAINMENT_THRESHOLD}%."
        )

    st.info(
        "CLO, PLO, Bloom, subject relevance, clarity "
        "and measurability are evaluated independently. "
        "One strong metric does not hide another weak metric."
    )

    # ========================================================
    # 6. QUESTION DIAGNOSTICS + REVISION/GENERATION
    # ========================================================

    st.header(
        "6. Question Diagnostics & Improvement"
    )

    for number, result in enumerate(
        results,
        start=1
    ):

        current_score = result["score"]

        with st.expander(
            f"Question {number} — "
            f"{current_score}/100"
        ):

            st.markdown(
                "### Current Question"
            )

            st.write(
                result["question"]
            )

            # ------------------------------------------------
            # Current status
            # ------------------------------------------------

            if current_score >= ATTAINMENT_THRESHOLD:

                st.success(
                    f"🟢 Current Score: "
                    f"{current_score}/100 — "
                    f"Alignment Attained"
                )

            elif current_score >= 60:

                st.warning(
                    f"🟠 Current Score: "
                    f"{current_score}/100 — "
                    f"Needs Attention"
                )

            else:

                st.error(
                    f"🔴 Current Score: "
                    f"{current_score}/100 — "
                    f"Weak"
                )

            # ------------------------------------------------
            # Metric breakdown
            # ------------------------------------------------

            st.markdown(
                "### Current Metric Breakdown"
            )

            breakdown_cols = st.columns(6)

            for column, metric in zip(
                breakdown_cols,
                METRIC_KEYS
            ):

                value = result[
                    "metrics"
                ][metric]

                with column:

                    st.metric(
                        metric,
                        (
                            "N/A"
                            if value is None
                            else f"{value}%"
                        )
                    )

            # ------------------------------------------------
            # Weak areas
            # ------------------------------------------------

            weak = get_weak_metrics(
                result
            )

            if weak:

                weak_text = " | ".join(
                    [
                        f"{metric}: {value}%"
                        for metric, value
                        in weak
                    ]
                )

                st.warning(
                    f"**Specific weak areas:** "
                    f"{weak_text}"
                )

            else:

                st.success(
                    "🟢 No individual metric is below "
                    f"{ATTAINMENT_THRESHOLD}%."
                )

            # ------------------------------------------------
            # Diagnostic feedback
            # ------------------------------------------------

            st.markdown(
                "### Diagnostic Feedback"
            )

            st.write(
                f"**CLO:** "
                f"{result['clo_feedback']}"
            )

            st.write(
                f"**PLO:** "
                f"{result['plo_feedback']}"
            )

            st.write(
                f"**Bloom:** "
                f"{result['bloom_feedback']}"
            )

            st.write(
                f"Actual Bloom: "
                f"**{result['actual_bloom']}**"
            )

            st.write(
                f"Target Bloom: "
                f"**{result['target_bloom']}**"
            )

            # =================================================
            # IMPROVEMENT CONTROLS
            # =================================================

            st.markdown(
                "### Improve This Question"
            )

            control_col1, control_col2 = st.columns(2)

            with control_col1:

                target_options = BLOOM_LEVELS

                default_target = result[
                    "target_bloom"
                ]

                if default_target not in target_options:

                    default_target = "Understand"

                target_index = target_options.index(
                    default_target
                )

                selected_bloom = st.selectbox(
                    "Target Bloom Level",
                    target_options,
                    index=target_index,
                    key=f"bloom_{number}"
                )

            with control_col2:

                current_type = result[
                    "question_type"
                ]

                if current_type in [
                    "True / False",
                    "Fill in the Blank",
                    "Matching",
                    "Case / Scenario",
                    "Numerical",
                    "Coding / Practical",
                    "Essay / Long Answer",
                    "Short Answer",
                ]:

                    default_type = current_type

                else:

                    default_type = "Short Answer"

                if default_type == "Coding / Practical":

                    default_type = "Practical / Application"

                type_options = QUESTION_TYPES

                if default_type in type_options:

                    type_index = type_options.index(
                        default_type
                    )

                else:

                    type_index = 0

                selected_type = st.selectbox(
                    "Question Type",
                    type_options,
                    index=type_index,
                    key=f"type_{number}"
                )

            action_col1, action_col2 = st.columns(2)

            with action_col1:

                revise_clicked = st.button(
                    "🔄 Revise Current Question",
                    key=f"revise_{number}",
                    use_container_width=True
                )

            with action_col2:

                generate_clicked = st.button(
                    "✨ Generate New Question",
                    key=f"generate_{number}",
                    use_container_width=True
                )

            # =================================================
            # REVISION ACTION
            # =================================================

            if revise_clicked:

                with st.spinner(
                    "Generating a stronger revision "
                    "based on this question's weak areas..."
                ):

                    revised_question, revised_result = (
                        generate_best_candidate(
                            result["question"],
                            "revision",
                            selected_bloom,
                            selected_type
                        )
                    )

                st.session_state.revisions[
                    number
                ] = {
                    "question":
                        revised_question,

                    "result":
                        revised_result,

                    "target_bloom":
                        selected_bloom,

                    "question_type":
                        selected_type,
                }

            # =================================================
            # NEW QUESTION ACTION
            # =================================================

            if generate_clicked:

                with st.spinner(
                    "Generating a new question "
                    "for this CLO/PLO..."
                ):

                    new_question, new_result = (
                        generate_best_candidate(
                            result["question"],
                            "new",
                            selected_bloom,
                            selected_type
                        )
                    )

                st.session_state.generated_questions[
                    number
                ] = {
                    "question":
                        new_question,

                    "result":
                        new_result,

                    "target_bloom":
                        selected_bloom,

                    "question_type":
                        selected_type,
                }

            # =================================================
            # DISPLAY REVISION
            # =================================================

            if number in st.session_state.revisions:

                revision = st.session_state.revisions[
                    number
                ]

                revised_question = revision[
                    "question"
                ]

                revised_result = revision[
                    "result"
                ]

                st.markdown(
                    "---"
                )

                st.markdown(
                    "### 🔄 Revised Question"
                )

                st.write(
                    revised_question
                )

                st.write(
                    f"**Target Bloom:** "
                    f"{revision['target_bloom']}"
                )

                st.write(
                    f"**Question Type:** "
                    f"{revision['question_type']}"
                )

                revised_score = revised_result[
                    "score"
                ]

                if revised_score >= ATTAINMENT_THRESHOLD:

                    st.success(
                        f"🟢 Revised Alignment Attained — "
                        f"{revised_score}/100"
                    )

                elif revised_score >= 60:

                    st.warning(
                        f"🟠 Revised Score — "
                        f"{revised_score}/100. "
                        f"Still below the "
                        f"{ATTAINMENT_THRESHOLD}% threshold."
                    )

                else:

                    st.error(
                        f"🔴 Revised Score — "
                        f"{revised_score}/100."
                    )

                revised_cols = st.columns(6)

                for column, metric in zip(
                    revised_cols,
                    METRIC_KEYS
                ):

                    with column:

                        st.metric(
                            metric,
                            f"{revised_result['metrics'][metric]}%"
                        )

                revised_weak = get_weak_metrics(
                    revised_result
                )

                if revised_weak:

                    st.warning(
                        "**Remaining weak areas:** "
                        + " | ".join(
                            [
                                f"{metric}: {value}%"
                                for metric, value
                                in revised_weak
                            ]
                        )
                    )

                else:

                    st.success(
                        "🟢 All individual metrics "
                        f"meet {ATTAINMENT_THRESHOLD}%."
                    )

            # =================================================
            # DISPLAY NEW QUESTION
            # =================================================

            if number in st.session_state.generated_questions:

                generated = (
                    st.session_state.generated_questions[
                        number
                    ]
                )

                new_question = generated[
                    "question"
                ]

                new_result = generated[
                    "result"
                ]

                st.markdown(
                    "---"
                )

                st.markdown(
                    "### ✨ Generated New Question"
                )

                st.write(
                    new_question
                )

                st.write(
                    f"**Target Bloom:** "
                    f"{generated['target_bloom']}"
                )

                st.write(
                    f"**Question Type:** "
                    f"{generated['question_type']}"
                )

                new_score = new_result[
                    "score"
                ]

                if new_score >= ATTAINMENT_THRESHOLD:

                    st.success(
                        f"🟢 New Question Alignment Attained — "
                        f"{new_score}/100"
                    )

                elif new_score >= 60:

                    st.warning(
                        f"🟠 New Question Score — "
                        f"{new_score}/100. "
                        f"Still below the "
                        f"{ATTAINMENT_THRESHOLD}% threshold."
                    )

                else:

                    st.error(
                        f"🔴 New Question Score — "
                        f"{new_score}/100."
                    )

                new_cols = st.columns(6)

                for column, metric in zip(
                    new_cols,
                    METRIC_KEYS
                ):

                    with column:

                        st.metric(
                            metric,
                            f"{new_result['metrics'][metric]}%"
                        )

                new_weak = get_weak_metrics(
                    new_result
                )

                if new_weak:

                    st.warning(
                        "**Remaining weak areas:** "
                        + " | ".join(
                            [
                                f"{metric}: {value}%"
                                for metric, value
                                in new_weak
                            ]
                        )
                    )

                else:

                    st.success(
                        "🟢 All individual metrics "
                        f"meet {ATTAINMENT_THRESHOLD}%."
                    )

    # ========================================================
    # 7. ATTAINED QUESTIONS
    # ========================================================

    st.header(
        "7. Attained Questions"
    )

    attained = []

    for number, result in enumerate(
        results,
        start=1
    ):

        if (
            result["score"] is not None
            and result["score"] >= ATTAINMENT_THRESHOLD
        ):

            attained.append(
                (
                    number,
                    result
                )
            )

    if attained:

        for number, result in attained:

            st.success(
                f"Q{number} — "
                f"{result['score']}/100 — "
                f"🟢 Alignment Attained"
            )

    else:

        st.info(
            f"No original question has reached "
            f"{ATTAINMENT_THRESHOLD}%."
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

            chart_rows.append(
                {
                    "Question":
                        f"Q{number}",

                    "Overall Score":
                        result["score"],
                }
            )

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

        overview_rows.append(
            {
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
            }
        )

    overview_df = pd.DataFrame(
        overview_rows
    )

    st.dataframe(
        overview_df,
        use_container_width=True,
        hide_index=True
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
                "**Current Question:**"
            )

            st.write(
                result["question"]
            )

            st.write(
                f"**Question Type:** "
                f"{result['question_type']}"
            )

            detail_cols = st.columns(6)

            for column, metric in zip(
                detail_cols,
                METRIC_KEYS
            ):

                with column:

                    value = result[
                        "metrics"
                    ][metric]

                    st.metric(
                        metric,
                        (
                            "N/A"
                            if value is None
                            else f"{value}%"
                        )
                    )

            st.markdown(
                "### CLO Diagnostic"
            )

            st.write(
                result["clo_feedback"]
            )

            st.markdown(
                "### PLO Diagnostic"
            )

            st.write(
                result["plo_feedback"]
            )

            st.markdown(
                "### Bloom Diagnostic"
            )

            st.write(
                result["bloom_feedback"]
            )

            st.write(
                f"Actual Bloom: "
                f"**{result['actual_bloom']}**"
            )

            st.write(
                f"Target Bloom: "
                f"**{result['target_bloom']}**"
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

        export_rows.append(
            {
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

                "PLO Alignment":
                    result["metrics"][
                        "PLO Alignment"
                    ],

                "Bloom Alignment":
                    result["metrics"][
                        "Bloom Alignment"
                    ],

                "Actual Bloom":
                    result["actual_bloom"],

                "Target Bloom":
                    result["target_bloom"],

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

                "CLO Feedback":
                    result["clo_feedback"],

                "PLO Feedback":
                    result["plo_feedback"],

                "Bloom Feedback":
                    result["bloom_feedback"],
            }
        )

    export_df = pd.DataFrame(
        export_rows
    )

    csv_bytes = export_df.to_csv(
        index=False
    ).encode(
        "utf-8"
    )

    st.download_button(
        "⬇️ Download Original Analysis CSV",
        data=csv_bytes,
        file_name="OBE_Quiz_Checker_Analysis.csv",
        mime="text/csv",
        use_container_width=True
    )
