import io
import re
import difflib
from pathlib import Path

import streamlit as st
import pandas as pd


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Checker",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CONSTANTS
# ============================================================

ATTAINMENT = 80

WEIGHTS = {
    "CLO Alignment": 30,
    "PLO Alignment": 20,
    "Bloom Alignment": 20,
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

BLOOM_RANK = {
    "Remember": 1,
    "Understand": 2,
    "Apply": 3,
    "Analyze": 4,
    "Evaluate": 5,
    "Create": 6,
}


# ============================================================
# BASIC TEXT UTILITIES
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\x00", " ")
    text = text.replace("\u00a0", " ")
    text = text.replace("\u200b", "")
    text = text.replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


def normalize_text(text):
    text = clean_text(text).lower()

    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def tokenize(text):
    return set(
        word
        for word in normalize_text(text).split()
        if len(word) > 2
    )


def similarity(a, b):
    a = normalize_text(a)
    b = normalize_text(b)

    if not a or not b:
        return 0.0

    return difflib.SequenceMatcher(None, a, b).ratio()


def safe_percent(value):
    try:
        return int(round(float(value)))
    except Exception:
        return 0


def truncate(text, limit=300):
    text = clean_text(text)

    if len(text) <= limit:
        return text

    return text[: limit - 3].rstrip() + "..."


# ============================================================
# FILE READERS
# ============================================================

def read_pdf(uploaded_file):
    raw = uploaded_file.getvalue()

    if not raw:
        return "", "The uploaded PDF is empty."

    # 1. PyMuPDF
    try:
        import fitz

        pdf = fitz.open(stream=raw, filetype="pdf")
        pages = []

        for page_number in range(len(pdf)):
            try:
                page = pdf.load_page(page_number)
                text = page.get_text("text", sort=True)

                if text:
                    pages.append(text)
            except Exception:
                continue

        pdf.close()

        combined = clean_text("\n".join(pages))

        if len(combined) >= 20:
            return combined, "PyMuPDF"
    except Exception:
        pass

    # 2. pypdf
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        pages = []

        for page in reader.pages:
            try:
                text = page.extract_text()

                if text:
                    pages.append(text)
            except Exception:
                continue

        combined = clean_text("\n".join(pages))

        if len(combined) >= 20:
            return combined, "pypdf"
    except Exception:
        pass

    # 3. pdfplumber
    try:
        import pdfplumber

        pages = []

        with pdfplumber.open(io.BytesIO(raw)) as pdf:
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

        combined = clean_text("\n".join(pages))

        if len(combined) >= 20:
            return combined, "pdfplumber"
    except Exception:
        pass

    # 4. OCR
    try:
        import fitz
        from PIL import Image
        import pytesseract

        pdf = fitz.open(stream=raw, filetype="pdf")
        ocr_pages = []

        for page_number in range(len(pdf)):
            try:
                page = pdf.load_page(page_number)

                pix = page.get_pixmap(
                    matrix=fitz.Matrix(2.0, 2.0),
                    alpha=False
                )

                image_bytes = pix.tobytes("png")
                image = Image.open(io.BytesIO(image_bytes))

                text = pytesseract.image_to_string(
                    image,
                    config="--psm 6"
                )

                if text:
                    ocr_pages.append(text)

            except Exception:
                continue

        pdf.close()

        combined = clean_text("\n".join(ocr_pages))

        if len(combined) >= 20:
            return combined, "OCR"
    except Exception:
        pass

    return "", "No readable text was extracted from the PDF."


def read_docx(uploaded_file):
    try:
        from docx import Document

        doc = Document(
            io.BytesIO(uploaded_file.getvalue())
        )

        parts = []

        for paragraph in doc.paragraphs:
            text = clean_text(paragraph.text)

            if text:
                parts.append(text)

        for table in doc.tables:
            for row in table.rows:
                row_text = []

                for cell in row.cells:
                    cell_text = clean_text(cell.text)

                    if cell_text:
                        row_text.append(cell_text)

                if row_text:
                    parts.append(" | ".join(row_text))

        return clean_text("\n".join(parts)), "DOCX"

    except Exception as exc:
        return "", f"DOCX reading error: {exc}"


def read_pptx(uploaded_file):
    try:
        from pptx import Presentation

        presentation = Presentation(
            io.BytesIO(uploaded_file.getvalue())
        )

        parts = []

        for slide in presentation.slides:
            slide_parts = []

            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text = clean_text(shape.text)

                    if text:
                        slide_parts.append(text)

            if slide_parts:
                parts.append("\n".join(slide_parts))

        return clean_text("\n\n".join(parts)), "PPTX"

    except Exception as exc:
        return "", f"PPTX reading error: {exc}"


def read_excel(uploaded_file):
    try:
        excel = pd.ExcelFile(
            io.BytesIO(uploaded_file.getvalue())
        )

        parts = []

        for sheet in excel.sheet_names:
            try:
                df = pd.read_excel(
                    io.BytesIO(uploaded_file.getvalue()),
                    sheet_name=sheet,
                    header=None
                )

                parts.append(f"Sheet: {sheet}")

                for row in df.fillna("").astype(str).values.tolist():
                    values = [
                        clean_text(x)
                        for x in row
                        if clean_text(x)
                    ]

                    if values:
                        parts.append(" | ".join(values))

            except Exception:
                continue

        return clean_text("\n".join(parts)), "Excel"

    except Exception as exc:
        return "", f"Excel reading error: {exc}"


def read_csv(uploaded_file):
    try:
        df = pd.read_csv(
            io.BytesIO(uploaded_file.getvalue()),
            header=None
        )

        lines = []

        for row in df.fillna("").astype(str).values.tolist():
            values = [
                clean_text(x)
                for x in row
                if clean_text(x)
            ]

            if values:
                lines.append(" | ".join(values))

        return clean_text("\n".join(lines)), "CSV"

    except Exception as exc:
        return "", f"CSV reading error: {exc}"


def read_image(uploaded_file):
    try:
        from PIL import Image
        import pytesseract

        image = Image.open(
            io.BytesIO(uploaded_file.getvalue())
        )

        text = pytesseract.image_to_string(
            image,
            config="--psm 6"
        )

        text = clean_text(text)

        if text:
            return text, "OCR"

        return "", "No readable text found in image."

    except Exception as exc:
        return "", f"Image OCR error: {exc}"


def read_text_file(uploaded_file):
    try:
        raw = uploaded_file.getvalue()

        for encoding in [
            "utf-8",
            "utf-16",
            "cp1252",
            "latin-1",
        ]:
            try:
                text = raw.decode(encoding)

                if text.strip():
                    return clean_text(text), "Text"

            except Exception:
                continue

        return "", "Could not decode text file."

    except Exception as exc:
        return "", f"Text reading error: {exc}"


def read_uploaded_file(uploaded_file):
    suffix = Path(
        uploaded_file.name
    ).suffix.lower()

    if suffix == ".pdf":
        return read_pdf(uploaded_file)

    if suffix == ".docx":
        return read_docx(uploaded_file)

    if suffix == ".pptx":
        return read_pptx(uploaded_file)

    if suffix in [".xlsx", ".xls", ".xlsm"]:
        return read_excel(uploaded_file)

    if suffix == ".csv":
        return read_csv(uploaded_file)

    if suffix in [
        ".txt",
        ".md",
        ".rtf",
    ]:
        return read_text_file(uploaded_file)

    if suffix in [
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
        ".tiff",
    ]:
        return read_image(uploaded_file)

    # Last attempt as text
    return read_text_file(uploaded_file)


# ============================================================
# QUESTION EXTRACTION
# ============================================================

QUESTION_START_RE = re.compile(
    r"(?im)^\s*"
    r"(?:"
    r"Q(?:uestion)?\s*)?"
    r"(\d{1,3})"
    r"\s*[\.\):\-]\s+"
)

QUESTION_WORD_RE = re.compile(
    r"(?i)^\s*(what|why|how|explain|describe|define|"
    r"identify|calculate|compare|analyze|analyse|"
    r"evaluate|discuss|determine|derive|solve|"
    r"illustrate|differentiate|justify|design|"
    r"develop|write|find|state|list|mention|"
    r"give|name|interpret|apply|demonstrate)\b"
)


def clean_question_candidate(text):
    text = clean_text(text)

    text = re.sub(
        r"^(?:Q(?:uestion)?\s*)?\d{1,3}\s*[\.\):\-]\s*",
        "",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"^(?:Q(?:uestion)?\s*)\d{1,3}\s*$",
        "",
        text,
        flags=re.I,
    )

    return clean_text(text)


def looks_like_question(text):
    text = clean_text(text)

    if len(text) < 8:
        return False

    lower = text.lower()

    if re.match(
        r"^(name|course|subject|semester|date|"
        r"student|roll\s*no|marks|total marks|time)\b",
        lower,
    ):
        return False

    if len(text.split()) < 2:
        return False

    if "?" in text:
        return True

    if QUESTION_WORD_RE.search(text):
        return True

    if re.search(
        r"\b(calculate|solve|derive|determine|"
        r"compute|evaluate|analyze|analyse|compare|"
        r"design|discuss|explain|describe)\b",
        lower,
    ):
        return True

    return False


def split_long_question_blocks(text):
    blocks = re.split(
        r"\n(?=\s*(?:Q(?:uestion)?\s*)?\d{1,3}\s*[\.\):\-])",
        text,
        flags=re.I,
    )

    return blocks


def extract_questions(text):
    text = clean_text(text)

    if not text:
        return []

    questions = []

    # --------------------------------------------------------
    # METHOD 1: numbered questions
    # --------------------------------------------------------

    matches = list(
        QUESTION_START_RE.finditer(text)
    )

    if matches:
        for index, match in enumerate(matches):
            start = match.end()

            if index + 1 < len(matches):
                end = matches[index + 1].start()
            else:
                end = len(text)

            block = text[start:end].strip()

            block = re.split(
                r"\n\s*(?:Marks?|Points?)\s*[:\-]?\s*\d+",
                block,
                flags=re.I,
            )[0]

            block = re.split(
                r"\n\s*(?:OR|EITHER|CHOICE)\s*[:\-]?",
                block,
                flags=re.I,
            )[0]

            block = clean_question_candidate(block)

            if looks_like_question(block):
                questions.append(block)

    # --------------------------------------------------------
    # METHOD 2: question-mark lines
    # --------------------------------------------------------

    if len(questions) < 2:
        for line in text.splitlines():
            line = clean_text(line)

            if "?" in line and looks_like_question(line):
                q = clean_question_candidate(line)

                if q and q not in questions:
                    questions.append(q)

    # --------------------------------------------------------
    # METHOD 3: question-style lines
    # --------------------------------------------------------

    if len(questions) < 2:
        for line in text.splitlines():
            line = clean_text(line)

            if QUESTION_WORD_RE.search(line):
                q = clean_question_candidate(line)

                if (
                    q
                    and len(q.split()) >= 3
                    and q not in questions
                ):
                    questions.append(q)

    # --------------------------------------------------------
    # METHOD 4: paragraph blocks
    # --------------------------------------------------------

    if len(questions) < 2:
        blocks = split_long_question_blocks(text)

        for block in blocks:
            block = clean_question_candidate(block)

            if looks_like_question(block):
                if block not in questions:
                    questions.append(block)

    # --------------------------------------------------------
    # METHOD 5: final meaningful lines
    # --------------------------------------------------------

    if not questions:
        for line in text.splitlines():
            line = clean_text(line)

            if (
                len(line.split()) >= 5
                and len(line) <= 500
                and not re.match(
                    r"^(course|subject|date|semester|"
                    r"student|name|roll|marks|time|"
                    r"instructions?)\b",
                    line,
                    flags=re.I,
                )
            ):
                questions.append(
                    clean_question_candidate(line)
                )

    # Remove duplicates
    unique = []

    for q in questions:
        q = clean_text(q)

        if not q:
            continue

        duplicate = False

        for old in unique:
            if similarity(q, old) >= 0.93:
                duplicate = True
                break

        if not duplicate:
            unique.append(q)

    return unique[:100]


# ============================================================
# BLOOM ANALYSIS
# ============================================================

BLOOM_VERBS = {
    "Remember": [
        "define",
        "identify",
        "list",
        "name",
        "state",
        "recall",
        "recognize",
        "mention",
        "label",
    ],
    "Understand": [
        "explain",
        "describe",
        "summarize",
        "interpret",
        "illustrate",
        "classify",
        "discuss",
    ],
    "Apply": [
        "calculate",
        "solve",
        "use",
        "apply",
        "demonstrate",
        "compute",
        "execute",
        "implement",
        "show how",
    ],
    "Analyze": [
        "analyze",
        "analyse",
        "compare",
        "contrast",
        "differentiate",
        "examine",
        "investigate",
        "distinguish",
        "relate",
    ],
    "Evaluate": [
        "evaluate",
        "justify",
        "assess",
        "critique",
        "judge",
        "recommend",
        "defend",
        "appraise",
    ],
    "Create": [
        "design",
        "develop",
        "create",
        "construct",
        "formulate",
        "propose",
        "plan",
        "produce",
    ],
}


def detect_bloom(question):
    text = normalize_text(question)

    detected = []

    for level, verbs in BLOOM_VERBS.items():
        for verb in verbs:
            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                text,
            ):
                detected.append(
                    (level, verb)
                )

    if detected:
        detected.sort(
            key=lambda item: BLOOM_RANK[item[0]],
            reverse=True,
        )

        return detected[0][0], detected[0][1]

    # Task-based fallback
    if re.search(
        r"\b(calculate|solve|compute|derive|"
        r"find|determine)\b",
        text,
    ):
        return "Apply", "task-based"

    if "?" in question:
        return "Understand", "question-based"

    return "Remember", "default"


def detect_target_bloom(clo, plo):
    text = normalize_text(
        f"{clo} {plo}"
    )

    detected = []

    for level, verbs in BLOOM_VERBS.items():
        for verb in verbs:
            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                text,
            ):
                detected.append(
                    (level, verb)
                )

    if detected:
        detected.sort(
            key=lambda item: BLOOM_RANK[item[0]],
            reverse=True,
        )

        return detected[0][0]

    return "Understand"


def bloom_score(actual, target):
    actual_rank = BLOOM_RANK.get(actual, 1)
    target_rank = BLOOM_RANK.get(target, 2)

    difference = actual_rank - target_rank

    if difference == 0:
        return 100

    if difference == 1:
        return 94

    if difference == -1:
        return 84

    if difference == 2:
        return 88

    if difference == -2:
        return 68

    if difference >= 3:
        return 72

    return 48


def bloom_feedback(actual, target):
    if actual == target:
        return (
            f"The question operates at {actual}, "
            f"which matches the intended cognitive level."
        )

    actual_rank = BLOOM_RANK.get(actual, 1)
    target_rank = BLOOM_RANK.get(target, 2)

    if actual_rank < target_rank:
        return (
            f"The question mainly operates at {actual}, "
            f"below the intended {target}. "
            f"It needs a stronger cognitive task."
        )

    return (
        f"The question operates at {actual}, "
        f"above the intended {target}. "
        f"The task may be more demanding than required."
    )


# ============================================================
# CONCEPT EXTRACTION
# ============================================================

GENERIC_WORDS = {
    "explain",
    "describe",
    "define",
    "identify",
    "analyze",
    "analyse",
    "evaluate",
    "apply",
    "use",
    "discuss",
    "compare",
    "contrast",
    "determine",
    "calculate",
    "solve",
    "derive",
    "design",
    "develop",
    "create",
    "construct",
    "formulate",
    "propose",
    "state",
    "list",
    "mention",
    "understand",
    "knowledge",
    "concept",
    "concepts",
    "fundamental",
    "principles",
    "principle",
    "ability",
    "skill",
    "skills",
    "students",
    "student",
    "learners",
    "learning",
    "outcome",
    "outcomes",
    "course",
    "program",
    "programme",
    "demonstrate",
    "demonstrates",
    "appropriate",
    "relevant",
    "effectively",
    "effect",
    "effects",
}


def content_words(text):
    words = re.findall(
        r"[A-Za-z][A-Za-z0-9\-]{2,}",
        text.lower(),
    )

    return [
        word
        for word in words
        if word not in GENERIC_WORDS
    ]


def extract_key_terms(text, max_terms=8):
    words = content_words(text)

    frequency = {}

    for word in words:
        frequency[word] = frequency.get(word, 0) + 1

    ranked = sorted(
        frequency.items(),
        key=lambda item: (-item[1], -len(item[0])),
    )

    return [
        word
        for word, _ in ranked[:max_terms]
    ]


def extract_subject_phrase(question):
    q = clean_question_candidate(question)

    # Remove common instruction beginnings.
    q = re.sub(
        r"(?i)^(what is|what are|why is|why are|"
        r"how does|how do|how can|how would|"
        r"explain|describe|define|identify|"
        r"calculate|solve|determine|analyze|analyse|"
        r"compare|contrast|evaluate|discuss|"
        r"state|list|mention)\s+",
        "",
        q,
    )

    q = re.sub(
        r"(?i)\b(the following|this|these|above)\b",
        "",
        q,
    )

    q = clean_text(q)

    if q:
        # Keep the most meaningful first part.
        if "," in q:
            q = q.split(",")[0]

        if len(q.split()) > 12:
            q = " ".join(q.split()[:12])

    return q.strip(" .?:")


def select_subject_topic(original, clo, plo):
    """
    IMPORTANT:
    Original question is the primary source for the topic.
    CLO/PLO are used only to fill missing subject concepts.
    The complete CLO/PLO is NEVER used as a question.
    """

    original_topic = extract_subject_phrase(original)

    if original_topic:
        return original_topic

    original_terms = extract_key_terms(
        original,
        max_terms=5
    )

    if original_terms:
        return " ".join(original_terms)

    clo_terms = extract_key_terms(
        clo,
        max_terms=4
    )

    if clo_terms:
        return " ".join(clo_terms)

    plo_terms = extract_key_terms(
        plo,
        max_terms=4
    )

    if plo_terms:
        return " ".join(plo_terms)

    return "the topic"


# ============================================================
# CLO / PLO ALIGNMENT
# ============================================================

def score_clo(question, clo):
    q_tokens = tokenize(question)
    c_tokens = tokenize(clo)

    if not q_tokens or not c_tokens:
        return 0, (
            "The CLO has not been provided, so CLO alignment "
            "cannot be established."
        )

    overlap = len(
        q_tokens.intersection(c_tokens)
    ) / max(
        1,
        len(c_tokens)
    )

    actual_bloom, _ = detect_bloom(question)
    target_bloom = detect_target_bloom(clo, "")

    bloom_component = 1.0 if (
        actual_bloom == target_bloom
    ) else 0.65

    if overlap >= 0.45:
        score = 88 + int(
            min(12, overlap * 20)
        )
        feedback = (
            "The question directly measures the "
            "specific knowledge or skill represented by the CLO."
        )

    elif overlap >= 0.25:
        score = 72 + int(
            min(13, overlap * 25)
        )
        feedback = (
            "The question addresses part of the CLO, "
            "but some required content or action is missing."
        )

    elif overlap >= 0.12:
        score = 52 + int(
            min(13, overlap * 25)
        )
        feedback = (
            "The question has limited connection to the "
            "specific course-level outcome."
        )

    else:
        score = 35
        feedback = (
            "The question does not directly measure the "
            "specific knowledge or skill required by the CLO."
        )

    score = int(
        round(
            score * 0.8
            + 100 * bloom_component * 0.2
        )
    )

    return min(100, score), feedback


def score_plo(question, plo):
    q_tokens = tokenize(question)
    p_tokens = tokenize(plo)

    if not q_tokens or not p_tokens:
        return 0, (
            "The PLO has not been provided, so PLO alignment "
            "cannot be established."
        )

    overlap = len(
        q_tokens.intersection(p_tokens)
    ) / max(
        1,
        len(p_tokens)
    )

    actual_bloom, _ = detect_bloom(question)

    # Broader capability evidence
    higher_level = actual_bloom in [
        "Analyze",
        "Evaluate",
        "Create",
    ]

    if overlap >= 0.35 and higher_level:
        score = 96
        feedback = (
            "The question provides clear evidence of the "
            "broader program-level capability represented by the PLO."
        )

    elif overlap >= 0.22 and (
        higher_level
        or actual_bloom == "Apply"
    ):
        score = 88
        feedback = (
            "The question demonstrates the broader capability "
            "reasonably well, although the evidence could be stronger."
        )

    elif overlap >= 0.12:
        score = 70
        feedback = (
            "The question demonstrates some broader capability, "
            "but evidence of the PLO is incomplete."
        )

    else:
        score = 48
        feedback = (
            "The question mainly tests isolated knowledge and "
            "provides limited evidence of the broader PLO capability."
        )

    return min(100, score), feedback


# ============================================================
# SUBJECT RELEVANCE
# ============================================================

def score_subject_relevance(question, subject):
    if not subject.strip():
        return 82, (
            "The subject was not specified, so relevance is "
            "judged from the question itself."
        )

    subject_terms = tokenize(subject)
    question_terms = tokenize(question)

    if not subject_terms:
        return 82, (
            "The question is treated as relevant because no "
            "specific subject terms were supplied."
        )

    overlap = len(
        subject_terms.intersection(question_terms)
    )

    if overlap >= 2:
        return 100, (
            "The question clearly uses terminology appropriate "
            "to the selected subject."
        )

    if overlap == 1:
        return 90, (
            "The question contains terminology connected to "
            "the selected subject."
        )

    return 82, (
        "The question is understandable and can be assessed "
        "within the selected subject."
    )


# ============================================================
# CLARITY
# ============================================================

def score_clarity(question):
    words = question.split()

    if not words:
        return 0, "No question text is available."

    score = 100

    if len(words) > 35:
        score -= 18
    elif len(words) > 25:
        score -= 8

    if question.count("?") > 1:
        score -= 8

    if question.count(";") > 1:
        score -= 5

    vague_phrases = [
        "discuss the above",
        "comment on",
        "write something about",
        "say something about",
        "as appropriate",
        "etc.",
        "and so on",
    ]

    lower = question.lower()

    for phrase in vague_phrases:
        if phrase in lower:
            score -= 15

    if len(words) <= 20:
        score = max(score, 92)

    if score >= 85:
        feedback = (
            "The question is concise, direct, and easy to understand."
        )
    elif score >= 70:
        feedback = (
            "The question is understandable but could be more concise."
        )
    else:
        feedback = (
            "The question contains unnecessary or unclear wording."
        )

    return max(0, min(100, score)), feedback


# ============================================================
# MEASURABILITY
# ============================================================

def score_measurability(question):
    lower = question.lower()

    measurable_verbs = [
        "define",
        "identify",
        "explain",
        "describe",
        "calculate",
        "solve",
        "compare",
        "contrast",
        "analyze",
        "analyse",
        "evaluate",
        "justify",
        "design",
        "develop",
        "determine",
        "derive",
        "classify",
        "interpret",
        "apply",
        "recommend",
        "construct",
        "demonstrate",
        "list",
        "state",
        "find",
    ]

    if any(
        re.search(
            r"\b" + re.escape(verb) + r"\b",
            lower
        )
        for verb in measurable_verbs
    ):
        return 100, (
            "The question uses a clear, assessable task that "
            "can be evaluated consistently."
        )

    if "?" in question:
        return 86, (
            "The question is assessable, although its expected "
            "response could be made more explicit."
        )

    return 68, (
        "The expected evidence is not sufficiently explicit."
    )


# ============================================================
# OVERALL QUESTION EVALUATION
# ============================================================

def evaluate_question(question, clo, plo, subject):
    clo_score, clo_feedback = score_clo(
        question,
        clo
    )

    plo_score, plo_feedback = score_plo(
        question,
        plo
    )

    actual_bloom, bloom_verb = detect_bloom(
        question
    )

    target_bloom = detect_target_bloom(
        clo,
        plo
    )

    bloom_value = bloom_score(
        actual_bloom,
        target_bloom
    )

    bloom_text = bloom_feedback(
        actual_bloom,
        target_bloom
    )

    subject_score, subject_feedback = (
        score_subject_relevance(
            question,
            subject
        )
    )

    clarity_score, clarity_feedback = (
        score_clarity(question)
    )

    measurability_score, measurability_feedback = (
        score_measurability(question)
    )

    total = (
        clo_score * 0.30
        + plo_score * 0.20
        + bloom_value * 0.20
        + subject_score * 0.10
        + clarity_score * 0.10
        + measurability_score * 0.10
    )

    total = int(round(total))

    return {
        "question": question,
        "score": max(0, min(100, total)),
        "clo_score": clo_score,
        "plo_score": plo_score,
        "bloom_score": bloom_value,
        "subject_score": subject_score,
        "clarity_score": clarity_score,
        "measurability_score": measurability_score,
        "actual_bloom": actual_bloom,
        "target_bloom": target_bloom,
        "bloom_verb": bloom_verb,
        "clo_feedback": clo_feedback,
        "plo_feedback": plo_feedback,
        "bloom_feedback": bloom_text,
        "subject_feedback": subject_feedback,
        "clarity_feedback": clarity_feedback,
        "measurability_feedback": measurability_feedback,
        "attained": total >= ATTAINMENT,
    }


# ============================================================
# REVISION FOCUS
# ============================================================

def determine_revision_focus(evaluation):
    actual = evaluation["actual_bloom"]
    target = evaluation["target_bloom"]

    if actual == target:
        if evaluation["clo_score"] < 80:
            return "strengthen the specific course concept"

        if evaluation["plo_score"] < 80:
            return "show clearer evidence of the broader capability"

        if evaluation["clarity_score"] < 80:
            return "make the task shorter and more direct"

        if evaluation["measurability_score"] < 80:
            return "use a clearly assessable task"

        return "strengthen the connection to the required concept"

    target_rank = BLOOM_RANK.get(target, 2)
    actual_rank = BLOOM_RANK.get(actual, 1)

    if target_rank > actual_rank:
        if target == "Understand":
            return "ask students to explain meaning or relationships"

        if target == "Apply":
            return "ask students to use the concept in a practical task"

        if target == "Analyze":
            return "ask students to examine relationships, factors, or causes"

        if target == "Evaluate":
            return "ask students to judge or justify an appropriate option"

        if target == "Create":
            return "ask students to design or develop a solution"

    return "match the intended cognitive task more precisely"


# ============================================================
# QUESTION TYPE DETECTION
# ============================================================

def detect_question_type(question):
    lower = question.lower()

    if re.search(
        r"\bcalculate|compute|solve|derive|find the value|"
        r"determine the value|numerical\b",
        lower,
    ):
        return "Numerical / Problem Solving"

    if re.search(
        r"\bcase study|scenario|situation|given case|"
        r"read the case\b",
        lower,
    ):
        return "Case / Scenario"

    if re.search(
        r"\bwrite a program|code|algorithm|function|"
        r"implement\b",
        lower,
    ):
        return "Practical / Coding"

    if re.search(
        r"\bdesign|develop|construct|create|prototype\b",
        lower,
    ):
        return "Design / Creation"

    if re.search(
        r"\btrue or false\b",
        lower,
    ):
        return "True / False"

    if re.search(
        r"\bmatch|matching\b",
        lower,
    ):
        return "Matching"

    if re.search(
        r"\bfill in the blank|fill the blank\b",
        lower,
    ):
        return "Fill in the Blank"

    if re.search(
        r"\b(a\)|b\)|c\)|d\))",
        lower,
    ):
        return "MCQ"

    if len(question.split()) <= 18:
        return "Short Answer"

    return "Written Response"


# ============================================================
# REVISION QUESTION GENERATION
# ============================================================

def simplify_topic(topic):
    topic = clean_text(topic)

    topic = re.sub(
        r"^(the|a|an)\s+",
        "",
        topic,
        flags=re.I,
    )

    if len(topic.split()) > 10:
        topic = " ".join(
            topic.split()[:10]
        )

    return topic.strip(" .?:")


def build_understand_questions(topic):
    return [
        f"How does {topic} work?",
        f"Why is {topic} important?",
        f"How would you explain {topic}?",
        f"What is the role of {topic}?",
    ]


def build_apply_questions(topic):
    return [
        f"How can {topic} be used in a practical situation?",
        f"How would you apply {topic} to solve a problem?",
        f"Use {topic} to solve the given problem.",
        f"How is {topic} applied in practice?",
    ]


def build_analyze_questions(topic):
    return [
        f"How do the main factors affecting {topic} relate to each other?",
        f"What factors affect {topic}, and how do they influence the outcome?",
        f"How does {topic} affect the result?",
        f"Compare the main factors involved in {topic}.",
    ]


def build_evaluate_questions(topic):
    return [
        f"Which approach to {topic} is most suitable, and why?",
        f"Which option best addresses the problem involving {topic}? Justify your answer.",
        f"How would you justify the most appropriate approach to {topic}?",
        f"Which solution to the {topic} problem is most appropriate? Explain why.",
    ]


def build_create_questions(topic):
    return [
        f"How would you design a practical solution involving {topic}?",
        f"Design a solution to a practical problem involving {topic}.",
        f"How would you develop a practical approach using {topic}?",
        f"Propose a suitable solution involving {topic}.",
    ]


def build_remember_questions(topic):
    return [
        f"What is {topic}?",
        f"Define {topic}.",
        f"Identify the main feature of {topic}.",
        f"State the key principle of {topic}.",
    ]


def preserve_special_type(original, topic, target):
    qtype = detect_question_type(original)

    candidates = []

    if qtype == "Numerical / Problem Solving":
        candidates.extend([
            f"Calculate the required value using {topic}.",
            f"Solve the problem using {topic}.",
            f"Apply {topic} to calculate the required result.",
        ])

    elif qtype == "Practical / Coding":
        candidates.extend([
            f"Write a solution that applies {topic}.",
            f"Implement {topic} to solve the given problem.",
            f"Use {topic} to complete the task.",
        ])

    elif qtype == "Case / Scenario":
        candidates.extend([
            f"How does {topic} affect the situation described?",
            f"Analyze the situation using {topic}.",
            f"Which solution involving {topic} best addresses the situation?",
        ])

    if target == "Remember":
        candidates.extend(build_remember_questions(topic))

    elif target == "Understand":
        candidates.extend(build_understand_questions(topic))

    elif target == "Apply":
        candidates.extend(build_apply_questions(topic))

    elif target == "Analyze":
        candidates.extend(build_analyze_questions(topic))

    elif target == "Evaluate":
        candidates.extend(build_evaluate_questions(topic))

    elif target == "Create":
        candidates.extend(build_create_questions(topic))

    return candidates


def is_bad_revision(candidate, original, clo, plo):
    candidate = clean_text(candidate)

    if not candidate:
        return True

    lower = candidate.lower()

    # Never expose alignment terminology.
    forbidden = [
        "clo",
        "plo",
        "learning outcome",
        "learning outcomes",
        "program outcome",
        "course learning outcome",
    ]

    if any(
        phrase in lower
        for phrase in forbidden
    ):
        return True

    # Candidate must be a real question/task.
    if len(candidate.split()) < 4:
        return True

    # Avoid excessively long generated questions.
    if len(candidate.split()) > 28:
        return True

    # Do not simply reproduce the CLO.
    if similarity(candidate, clo) >= 0.68:
        return True

    # Do not reproduce the PLO.
    if plo and similarity(candidate, plo) >= 0.68:
        return True

    # Do not simply reproduce original.
    if similarity(candidate, original) >= 0.88:
        return True

    # Prevent "CLO copied with a question mark".
    clo_terms = tokenize(clo)
    candidate_terms = tokenize(candidate)

    if clo_terms:
        overlap = len(
            clo_terms.intersection(candidate_terms)
        ) / len(clo_terms)

        if overlap >= 0.78:
            return True

    return False


def make_candidate_topic(original, clo, plo):
    topic = select_subject_topic(
        original,
        clo,
        plo,
    )

    topic = simplify_topic(topic)

    # If original is very generic, use a small concept
    # from the CLO without reproducing the CLO.
    generic_originals = [
        "the topic",
        "this topic",
        "the concept",
        "the given topic",
    ]

    if (
        not topic
        or topic.lower() in generic_originals
    ):
        terms = extract_key_terms(
            clo,
            max_terms=4
        )

        if terms:
            topic = " ".join(terms)

    return topic


def generate_candidates(original, clo, plo):
    target = detect_target_bloom(
        clo,
        plo,
    )

    topic = make_candidate_topic(
        original,
        clo,
        plo,
    )

    candidates = preserve_special_type(
        original,
        topic,
        target,
    )

    # Additional concept-based alternatives.
    clo_terms = extract_key_terms(
        clo,
        max_terms=5
    )

    if clo_terms:
        short_topic = " ".join(
            clo_terms[:4]
        )

        candidates.extend(
            preserve_special_type(
                original,
                short_topic,
                target,
            )
        )

    # Original-question-driven alternatives.
    original_terms = extract_key_terms(
        original,
        max_terms=5
    )

    if original_terms:
        original_topic = " ".join(
            original_terms[:4]
        )

        candidates.extend(
            preserve_special_type(
                original,
                original_topic,
                target,
            )
        )

    unique = []

    for candidate in candidates:
        candidate = clean_text(candidate)

        if not candidate:
            continue

        if not candidate.endswith("?"):
            candidate += "."

        if is_bad_revision(
            candidate,
            original,
            clo,
            plo,
        ):
            continue

        duplicate = False

        for old in unique:
            if similarity(
                candidate,
                old,
            ) >= 0.85:
                duplicate = True
                break

        if not duplicate:
            unique.append(candidate)

    return unique


# ============================================================
# STRONG FALLBACK REVISION
# ============================================================

def build_strong_fallback(original, clo, plo):
    target = detect_target_bloom(
        clo,
        plo,
    )

    topic = make_candidate_topic(
        original,
        clo,
        plo,
    )

    topic = simplify_topic(topic)

    if target == "Remember":
        candidate = f"Identify the key feature of {topic}."

    elif target == "Understand":
        candidate = f"How does {topic} work?"

    elif target == "Apply":
        candidate = f"How would you apply {topic} to solve a practical problem?"

    elif target == "Analyze":
        candidate = f"How do the main factors affecting {topic} influence the outcome?"

    elif target == "Evaluate":
        candidate = f"Which approach to {topic} is most suitable, and why?"

    else:
        candidate = f"How would you design a practical solution involving {topic}?"

    if not is_bad_revision(
        candidate,
        original,
        clo,
        plo,
    ):
        return candidate

    # Last safe generic fallback.
    if target == "Analyze":
        return f"How does {topic} affect the outcome?"

    if target == "Apply":
        return f"How can {topic} be applied in practice?"

    if target == "Evaluate":
        return f"Which approach to {topic} is most appropriate, and why?"

    if target == "Create":
        return f"How would you design a solution involving {topic}?"

    return f"How does {topic} work?"


def generate_best_revision(original, clo, plo, subject):
    candidates = generate_candidates(
        original,
        clo,
        plo,
    )

    scored = []

    for candidate in candidates:
        evaluation = evaluate_question(
            candidate,
            clo,
            plo,
            subject,
        )

        # Prefer genuinely strong alignment.
        score = evaluation["score"]

        # Reward concise questions.
        word_count = len(candidate.split())

        if 6 <= word_count <= 18:
            score += 4

        # Reward stronger Bloom match.
        if (
            evaluation["actual_bloom"]
            == evaluation["target_bloom"]
        ):
            score += 5

        scored.append(
            (
                min(100, score),
                candidate,
                evaluation,
            )
        )

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    # Prefer an actually attained candidate.
    for item in scored:
        if item[2]["score"] >= ATTAINMENT:
            return item[1], item[2]

    # If no candidate attained 80, create a stronger fallback
    # and evaluate it honestly.
    fallback = build_strong_fallback(
        original,
        clo,
        plo,
    )

    fallback_eval = evaluate_question(
        fallback,
        clo,
        plo,
        subject,
    )

    if (
        not is_bad_revision(
            fallback,
            original,
            clo,
            plo,
        )
        and fallback_eval["score"]
        >= max(
            [item[2]["score"] for item in scored],
            default=0,
        )
    ):
        return fallback, fallback_eval

    if scored:
        return scored[0][1], scored[0][2]

    return fallback, fallback_eval


# ============================================================
# SESSION STATE
# ============================================================

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = []

if "accepted_revisions" not in st.session_state:
    st.session_state.accepted_revisions = {}

if "file_text" not in st.session_state:
    st.session_state.file_text = ""

if "file_name" not in st.session_state:
    st.session_state.file_name = ""

if "file_method" not in st.session_state:
    st.session_state.file_method = ""

if "questions" not in st.session_state:
    st.session_state.questions = []


# ============================================================
# HEADER
# ============================================================

st.title("🎓 OBE Quiz Checker")

st.caption(
    "Subject-agnostic assessment checking and automatic question revision"
)

st.divider()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header("Assessment Information")

    subject = st.text_input(
        "Subject / Course",
        placeholder="e.g., Chemistry, Physics, English, Mathematics",
    )

    assessment_type = st.selectbox(
        "Assessment Type",
        [
            "Quiz",
            "Assignment",
            "Test",
            "Exam",
            "Question Paper",
            "Mixed Assessment",
        ],
    )

    st.markdown("---")

    st.subheader("Scoring")

    st.write(
        "CLO Alignment: 30%"
    )

    st.write(
        "PLO Alignment: 20%"
    )

    st.write(
        "Bloom Alignment: 20%"
    )

    st.write(
        "Subject Relevance: 10%"
    )

    st.write(
        "Clarity: 10%"
    )

    st.write(
        "Measurability: 10%"
    )

    st.markdown("---")

    st.info(
        "Questions are revised automatically. "
        "CLO/PLO statements guide the revision but "
        "are never copied into the student-facing question."
    )


# ============================================================
# LEARNING OUTCOMES
# ============================================================

st.header("1. Learning Outcomes")

col1, col2 = st.columns(2)

with col1:
    clo = st.text_area(
        "Course Learning Outcome (CLO)",
        height=150,
        placeholder=(
            "Example: Explain fundamental concepts "
            "of acids, bases, and pH."
        ),
    )

with col2:
    plo = st.text_area(
        "Program Learning Outcome (PLO)",
        height=150,
        placeholder=(
            "Example: Apply knowledge to solve "
            "problems in the relevant discipline."
        ),
    )


# ============================================================
# FILE UPLOAD
# ============================================================

st.header("2. Upload Complete Assessment")

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
        "bmp",
        "tiff",
    ],
)

if uploaded_file is not None:
    if (
        st.session_state.file_name
        != uploaded_file.name
    ):
        text, method = read_uploaded_file(
            uploaded_file
        )

        st.session_state.file_text = text
        st.session_state.file_name = uploaded_file.name
        st.session_state.file_method = method
        st.session_state.analysis_results = []
        st.session_state.accepted_revisions = {}

        if text:
            questions = extract_questions(
                text
            )

            st.session_state.questions = questions
        else:
            st.session_state.questions = []

    if st.session_state.file_text:
        st.success(
            f"File read successfully using "
            f"{st.session_state.file_method}."
        )

        st.caption(
            f"Extracted {len(st.session_state.questions)} "
            f"assessment question(s)."
        )

        with st.expander(
            "Preview extracted text",
            expanded=False,
        ):
            st.text(
                truncate(
                    st.session_state.file_text,
                    5000,
                )
            )

    else:
        st.error(
            "The file could not be read. "
            "Please check that it contains readable text "
            "or upload a clearer file."
        )


# ============================================================
# ANALYZE
# ============================================================

st.header("3. Analyze Assessment")

analyze_clicked = st.button(
    "🔍 Analyze Assessment",
    type="primary",
    use_container_width=True,
)

if analyze_clicked:
    if not clo.strip():
        st.warning(
            "Please enter the CLO before analysis."
        )

    elif not plo.strip():
        st.warning(
            "Please enter the PLO before analysis."
        )

    elif not subject.strip():
        st.warning(
            "Please enter the subject/course."
        )

    elif not st.session_state.questions:
        st.error(
            "No assessment questions could be extracted. "
            "Please upload a file containing readable questions."
        )

    else:
        results = []

        progress = st.progress(0)

        for index, question in enumerate(
            st.session_state.questions
        ):
            evaluation = evaluate_question(
                question,
                clo,
                plo,
                subject,
            )

            revision = None
            revision_eval = None

            if evaluation["score"] < ATTAINMENT:
                revision, revision_eval = (
                    generate_best_revision(
                        question,
                        clo,
                        plo,
                        subject,
                    )
                )

            results.append(
                {
                    "number": index + 1,
                    "original": question,
                    "evaluation": evaluation,
                    "revision": revision,
                    "revision_eval": revision_eval,
                    "accepted": False,
                }
            )

            progress.progress(
                int(
                    ((index + 1)
                    / len(st.session_state.questions))
                    * 100
                )
            )

        st.session_state.analysis_results = results

        st.success(
            "Assessment analysis completed."
        )

        st.rerun()


# ============================================================
# RESULTS
# ============================================================

results = st.session_state.analysis_results

if results:

    # --------------------------------------------------------
    # ACCEPTED REVISIONS
    # --------------------------------------------------------

    for item in results:
        number = item["number"]

        if number in st.session_state.accepted_revisions:
            accepted = (
                st.session_state.accepted_revisions[number]
            )

            item["original"] = accepted["question"]
            item["evaluation"] = accepted["evaluation"]
            item["accepted"] = True

    current_scores = [
        item["evaluation"]["score"]
        for item in results
    ]

    overall_score = int(
        round(
            sum(current_scores)
            / max(1, len(current_scores))
        )
    )

    overall_attained = (
        overall_score >= ATTAINMENT
    )

    # --------------------------------------------------------
    # OVERALL SCORE
    # --------------------------------------------------------

    st.header("4. Overall Alignment")

    if overall_attained:
        st.success(
            f"🟢 Alignment Attained — {overall_score}%"
        )

        if not st.session_state.get(
            "balloons_shown",
            False,
        ):
            st.balloons()

            st.session_state.balloons_shown = True

    else:
        st.warning(
            f"🟠 Revision Required — {overall_score}%"
        )

        st.session_state.balloons_shown = False

    st.progress(
        min(100, overall_score)
    )

    # --------------------------------------------------------
    # QUESTION COUNTS
    # --------------------------------------------------------

    attained_count = sum(
        1
        for item in results
        if item["evaluation"]["score"]
        >= ATTAINMENT
    )

    revision_count = len(results) - attained_count

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Overall Score",
            f"{overall_score}%",
        )

    with c2:
        st.metric(
            "Questions Attained",
            attained_count,
        )

    with c3:
        st.metric(
            "Questions Requiring Revision",
            revision_count,
        )

    # --------------------------------------------------------
    # QUESTIONS REQUIRING REVISION
    # --------------------------------------------------------

    weak_items = [
        item
        for item in results
        if item["evaluation"]["score"]
        < ATTAINMENT
        and not item["accepted"]
    ]

    if weak_items:
        st.header(
            "5. Questions Requiring Revision"
        )

        st.caption(
            "Suggestions are generated from the original "
            "question and the required learning expectations. "
            "The CLO/PLO is never used as the student-facing question."
        )

        for item in weak_items:
            number = item["number"]
            evaluation = item["evaluation"]

            with st.container(border=True):

                st.subheader(
                    f"Question {number} — "
                    f"{evaluation['score']}%"
                )

                st.write(
                    "**Current Question**"
                )

                st.info(
                    evaluation["question"]
                )

                # --------------------------------------------
                # CURRENT ANALYSIS
                # --------------------------------------------

                metrics = pd.DataFrame(
                    {
                        "Metric": [
                            "CLO Alignment",
                            "PLO Alignment",
                            "Bloom Alignment",
                            "Subject Relevance",
                            "Clarity",
                            "Measurability",
                            "Overall",
                        ],
                        "Score": [
                            evaluation["clo_score"],
                            evaluation["plo_score"],
                            evaluation["bloom_score"],
                            evaluation["subject_score"],
                            evaluation["clarity_score"],
                            evaluation["measurability_score"],
                            evaluation["score"],
                        ],
                    }
                )

                st.dataframe(
                    metrics,
                    hide_index=True,
                    use_container_width=True,
                )

                st.markdown(
                    "**Problem Identified:** "
                    + determine_revision_focus(
                        evaluation
                    )
                )

                # --------------------------------------------
                # DISTINCT FEEDBACK
                # --------------------------------------------

                with st.expander(
                    "View detailed analysis",
                    expanded=False,
                ):
                    st.write(
                        f"**CLO Evaluation:** "
                        f"{evaluation['clo_feedback']}"
                    )

                    st.write(
                        f"**PLO Evaluation:** "
                        f"{evaluation['plo_feedback']}"
                    )

                    st.write(
                        f"**Bloom Evaluation:** "
                        f"{evaluation['bloom_feedback']}"
                    )

                    st.write(
                        f"**Subject Relevance:** "
                        f"{evaluation['subject_feedback']}"
                    )

                    st.write(
                        f"**Clarity:** "
                        f"{evaluation['clarity_feedback']}"
                    )

                    st.write(
                        f"**Measurability:** "
                        f"{evaluation['measurability_feedback']}"
                    )

                # --------------------------------------------
                # SUGGESTED QUESTION
                # --------------------------------------------

                revision = item["revision"]
                revision_eval = item["revision_eval"]

                if revision:
                    st.markdown(
                        "### 💡 Suggested Question"
                    )

                    st.success(
                        revision
                    )

                    if revision_eval:

                        before_after = pd.DataFrame(
                            {
                                "": [
                                    "Before Revision",
                                    "After Revision",
                                ],
                                "Score": [
                                    evaluation["score"],
                                    revision_eval["score"],
                                ],
                            }
                        )

                        st.dataframe(
                            before_after,
                            hide_index=True,
                            use_container_width=True,
                        )

                        if (
                            revision_eval["score"]
                            >= ATTAINMENT
                        ):
                            st.success(
                                f"🟢 Suggested question "
                                f"reaches {revision_eval['score']}% "
                                f"alignment."
                            )
                        else:
                            st.warning(
                                f"Suggested question scores "
                                f"{revision_eval['score']}%. "
                                f"The strongest concise revision "
                                f"available for this question is shown."
                            )

                    button_key = (
                        f"use_revision_{number}"
                    )

                    if st.button(
                        "✅ Use This Suggested Question",
                        key=button_key,
                        use_container_width=True,
                    ):
                        st.session_state.accepted_revisions[
                            number
                        ] = {
                            "question": revision,
                            "evaluation": revision_eval,
                        }

                        st.rerun()

    # --------------------------------------------------------
    # ATTAINED QUESTIONS
    # --------------------------------------------------------

    attained_items = [
        item
        for item in results
        if item["evaluation"]["score"]
        >= ATTAINMENT
    ]

    if attained_items:
        st.header(
            "6. Attained Questions"
        )

        for item in attained_items:
            evaluation = item["evaluation"]

            with st.container(border=True):

                st.markdown(
                    f"### Question {item['number']} "
                    f"— 🟢 {evaluation['score']}%"
                )

                st.write(
                    evaluation["question"]
                )

                st.caption(
                    f"CLO: {evaluation['clo_score']}%  |  "
                    f"PLO: {evaluation['plo_score']}%  |  "
                    f"Bloom: {evaluation['bloom_score']}%  |  "
                    f"Subject: {evaluation['subject_score']}%  |  "
                    f"Clarity: {evaluation['clarity_score']}%  |  "
                    f"Measurability: "
                    f"{evaluation['measurability_score']}%"
                )

    # --------------------------------------------------------
    # ALIGNMENT OVERVIEW — ONLY GRAPH
    # --------------------------------------------------------

    st.header(
        "7. Alignment Overview"
    )

    graph_df = pd.DataFrame(
        {
            "Question": [
                f"Q{item['number']}"
                for item in results
            ],
            "Score": [
                item["evaluation"]["score"]
                for item in results
            ],
        }
    )

    st.bar_chart(
        graph_df.set_index("Question")
    )

    # --------------------------------------------------------
    # QUESTION OVERVIEW
    # --------------------------------------------------------

    st.header(
        "8. Question Overview"
    )

    overview_rows = []

    for item in results:
        evaluation = item["evaluation"]

        overview_rows.append(
            {
                "Question": f"Q{item['number']}",
                "Question Text": truncate(
                    evaluation["question"],
                    160,
                ),
                "CLO": evaluation["clo_score"],
                "PLO": evaluation["plo_score"],
                "Bloom": evaluation["bloom_score"],
                "Subject": evaluation["subject_score"],
                "Clarity": evaluation["clarity_score"],
                "Measurability": evaluation[
                    "measurability_score"
                ],
                "Overall": evaluation["score"],
                "Status": (
                    "Attained"
                    if evaluation["score"]
                    >= ATTAINMENT
                    else "Revision Required"
                ),
            }
        )

    overview_df = pd.DataFrame(
        overview_rows
    )

    st.dataframe(
        overview_df,
        hide_index=True,
        use_container_width=True,
    )

    # --------------------------------------------------------
    # DETAILED ANALYSIS
    # --------------------------------------------------------

    st.header(
        "9. Detailed Question Analysis"
    )

    selected_question = st.selectbox(
        "Select a question",
        [
            f"Question {item['number']}"
            for item in results
        ],
    )

    selected_number = int(
        re.search(
            r"\d+",
            selected_question
        ).group()
    )

    selected_item = next(
        item
        for item in results
        if item["number"]
        == selected_number
    )

    evaluation = selected_item["evaluation"]

    st.markdown(
        f"### Question {selected_number}"
    )

    st.write(
        evaluation["question"]
    )

    detail_df = pd.DataFrame(
        {
            "Metric": [
                "CLO Alignment",
                "PLO Alignment",
                "Bloom Alignment",
                "Subject Relevance",
                "Clarity",
                "Measurability",
                "Overall Score",
            ],
            "Score": [
                evaluation["clo_score"],
                evaluation["plo_score"],
                evaluation["bloom_score"],
                evaluation["subject_score"],
                evaluation["clarity_score"],
                evaluation["measurability_score"],
                evaluation["score"],
            ],
        }
    )

    st.dataframe(
        detail_df,
        hide_index=True,
        use_container_width=True,
    )

    st.write(
        "**CLO:** "
        + evaluation["clo_feedback"]
    )

    st.write(
        "**PLO:** "
        + evaluation["plo_feedback"]
    )

    st.write(
        "**Bloom:** "
        + evaluation["bloom_feedback"]
    )

    st.write(
        "**Subject Relevance:** "
        + evaluation["subject_feedback"]
    )

    st.write(
        "**Clarity:** "
        + evaluation["clarity_feedback"]
    )

    st.write(
        "**Measurability:** "
        + evaluation["measurability_feedback"]
    )

    # --------------------------------------------------------
    # EXPORT
    # --------------------------------------------------------

    st.header(
        "10. Export Results"
    )

    export_rows = []

    for item in results:
        evaluation = item["evaluation"]

        export_rows.append(
            {
                "Question No.": item["number"],
                "Question": evaluation["question"],
                "Overall Score": evaluation["score"],
                "CLO Alignment": evaluation["clo_score"],
                "PLO Alignment": evaluation["plo_score"],
                "Bloom Alignment": evaluation["bloom_score"],
                "Actual Bloom": evaluation["actual_bloom"],
                "Target Bloom": evaluation["target_bloom"],
                "Subject Relevance": evaluation["subject_score"],
                "Clarity": evaluation["clarity_score"],
                "Measurability": evaluation[
                    "measurability_score"
                ],
                "Status": (
                    "Alignment Attained"
                    if evaluation["score"]
                    >= ATTAINMENT
                    else "Revision Required"
                ),
            }
        )

    export_df = pd.DataFrame(
        export_rows
    )

    csv_data = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Analysis as CSV",
        data=csv_data,
        file_name="OBE_Quiz_Checker_Results.csv",
        mime="text/csv",
        use_container_width=True,
    )

else:
    # --------------------------------------------------------
    # PRE-ANALYSIS STATE
    # --------------------------------------------------------

    if not clo.strip() or not plo.strip():
        st.info(
            "⏳ Awaiting Learning Outcomes — "
            "enter the CLO and PLO to begin."
        )

    elif not st.session_state.questions:
        st.info(
            "⏳ Awaiting Assessment — "
            "upload the complete assessment."
        )

    else:
        st.info(
            "⏳ Ready for Analysis — "
            "click **Analyze Assessment** to evaluate the questions."
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "OBE Quiz Checker evaluates assessment questions using "
    "CLO alignment, PLO alignment, Bloom alignment, subject "
    "relevance, clarity, and measurability."
)
