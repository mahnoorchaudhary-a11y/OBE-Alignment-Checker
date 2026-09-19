import io
import re
from typing import List, Dict, Tuple, Optional

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

WEIGHTS = {
    "CLO Alignment": 30,
    "PLO Alignment": 20,
    "Bloom Alignment": 20,
    "Subject Relevance": 10,
    "Clarity": 10,
    "Measurability": 10,
}


BLOOM_LEVELS = {
    "remember": 1,
    "recall": 1,
    "define": 1,
    "identify": 1,
    "list": 1,
    "name": 1,
    "state": 1,

    "understand": 2,
    "describe": 2,
    "explain": 2,
    "summarize": 2,
    "discuss": 2,
    "interpret": 2,
    "classify": 2,

    "apply": 3,
    "calculate": 3,
    "solve": 3,
    "demonstrate": 3,
    "use": 3,
    "implement": 3,
    "execute": 3,

    "analyze": 4,
    "analyse": 4,
    "compare": 4,
    "contrast": 4,
    "differentiate": 4,
    "examine": 4,
    "investigate": 4,
    "categorize": 4,

    "evaluate": 5,
    "assess": 5,
    "judge": 5,
    "critique": 5,
    "justify": 5,
    "defend": 5,
    "recommend": 5,

    "create": 6,
    "design": 6,
    "develop": 6,
    "construct": 6,
    "formulate": 6,
    "produce": 6,
    "propose": 6,
}


BLOOM_NAMES = {
    1: "Remember",
    2: "Understand",
    3: "Apply",
    4: "Analyze",
    5: "Evaluate",
    6: "Create",
}


# ============================================================
# SESSION STATE
# ============================================================

def init_state():

    defaults = {
        "analysis_done": False,
        "analysis_results": [],
        "accepted_revisions": {},
        "uploaded_text": "",
        "extraction_method": "",
        "last_file_name": "",
        "overall_score": None,
    }

    for key, value in defaults.items():

        if key not in st.session_state:
            st.session_state[key] = value


init_state()


# ============================================================
# TEXT UTILITIES
# ============================================================

def clean_text(text: str) -> str:

    if not text:
        return ""

    text = text.replace("\x00", " ")
    text = text.replace("\u00a0", " ")
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_text(text: str) -> str:

    text = text.lower()

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


def tokens(text: str) -> set:

    stop_words = {
        "the", "a", "an", "and", "or", "of", "to",
        "in", "on", "for", "with", "by", "from",
        "is", "are", "was", "were", "be", "been",
        "being", "as", "at", "that", "this",
        "these", "those", "it", "its", "their",
        "they", "them", "he", "she", "his", "her",
        "you", "your", "we", "our", "will",
        "can", "may", "should", "must", "into",
        "through", "using", "student", "students",
    }

    words = re.findall(
        r"[a-zA-Z0-9]+",
        text.lower()
    )

    return {
        word
        for word in words
        if len(word) > 2 and word not in stop_words
    }


def keyword_overlap(
    question: str,
    outcome: str
) -> float:

    q = tokens(question)
    o = tokens(outcome)

    if not q or not o:
        return 0.0

    intersection = q.intersection(o)

    return (
        len(intersection)
        / max(1, len(o))
    ) * 100


# ============================================================
# FILE READING
# ============================================================

def read_pdf(uploaded_file):

    raw = uploaded_file.getvalue()

    if not raw:
        return "", "PDF is empty."

    # PyMuPDF
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

        if len(combined) >= 30:
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

        if len(combined) >= 30:
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

        if len(combined) >= 30:
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

        if len(combined) >= 30:
            return combined, "OCR"

    except Exception:
        pass

    return "", (
        "No readable text was extracted. "
        "For scanned PDFs, install Tesseract OCR."
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

                cells = []

                for cell in row.cells:

                    if cell.text.strip():
                        cells.append(
                            cell.text.strip()
                        )

                if cells:
                    parts.append(
                        " | ".join(cells)
                    )

        text = clean_text(
            "\n".join(parts)
        )

        if len(text) < 20:
            return "", "DOCX has insufficient text."

        return text, "DOCX"

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

                    value = shape.text.strip()

                    if value:
                        parts.append(value)

        text = clean_text(
            "\n".join(parts)
        )

        if len(text) < 20:
            return "", "PPTX has insufficient text."

        return text, "PPTX"

    except Exception as exc:

        return "", f"PPTX error: {exc}"


def read_excel(uploaded_file):

    try:

        excel = pd.ExcelFile(
            io.BytesIO(
                uploaded_file.getvalue()
            )
        )

        parts = []

        for sheet in excel.sheet_names:

            try:

                df = pd.read_excel(
                    io.BytesIO(
                        uploaded_file.getvalue()
                    ),
                    sheet_name=sheet,
                    header=None
                )

                parts.append(
                    f"Sheet: {sheet}"
                )

                for row in (
                    df.fillna("")
                    .astype(str)
                    .values
                    .tolist()
                ):

                    row_text = " | ".join(
                        cell.strip()
                        for cell in row
                        if cell.strip()
                    )

                    if row_text:
                        parts.append(
                            row_text
                        )

            except Exception:
                continue

        text = clean_text(
            "\n".join(parts)
        )

        if len(text) < 20:
            return "", "Excel has insufficient text."

        return text, "Excel"

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

        for row in (
            df.fillna("")
            .astype(str)
            .values
            .tolist()
        ):

            row_text = " | ".join(
                cell.strip()
                for cell in row
                if cell.strip()
            )

            if row_text:
                parts.append(row_text)

        text = clean_text(
            "\n".join(parts)
        )

        if len(text) < 20:
            return "", "CSV has insufficient text."

        return text, "CSV"

    except Exception as exc:

        return "", f"CSV error: {exc}"


def read_text_file(uploaded_file):

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

            text = clean_text(text)

            if len(text) >= 20:
                return text, "Text"

        except Exception:
            continue

    return "", "Text file could not be decoded."


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

        text = clean_text(text)

        if len(text) < 20:
            return "", "OCR found insufficient text."

        return text, "OCR"

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
            ".bmp",
            ".tiff",
        )
    ):
        return read_image(uploaded_file)

    return "", "Unsupported file format."


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def clean_question(text):

    text = clean_text(text)

    text = re.sub(
        r"^(question\s*)?\d+\s*[\.\):\-]\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^q\s*\d+\s*[\.\):\-]\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    return text.strip()


def looks_like_question(text):

    if not text:
        return False

    if len(text.split()) < 4:
        return False

    normalized = normalize_text(text)

    if "?" in text:
        return True

    starters = [
        "what",
        "why",
        "how",
        "which",
        "define",
        "explain",
        "describe",
        "discuss",
        "identify",
        "calculate",
        "solve",
        "analyze",
        "analyse",
        "compare",
        "evaluate",
        "assess",
        "design",
        "develop",
        "apply",
        "demonstrate",
        "justify",
        "recommend",
        "differentiate",
        "examine",
        "interpret",
    ]

    first = normalized.split()[0]

    return first in starters


def extract_questions(text):

    text = clean_text(text)

    if not text:
        return []

    candidates = []

    # Numbered questions
    pieces = re.split(
        r"(?im)(?=^\s*(?:question\s*)?\d+\s*[\.\):\-])",
        text
    )

    for piece in pieces:

        piece = clean_question(piece)

        if looks_like_question(piece):
            candidates.append(piece)

    # Question marks
    if len(candidates) < 2:

        pieces = re.split(
            r"(?<=[?])\s+",
            text
        )

        for piece in pieces:

            piece = clean_question(piece)

            if looks_like_question(piece):
                candidates.append(piece)

    # Lines
    if len(candidates) < 2:

        for line in text.splitlines():

            line = clean_question(line)

            if looks_like_question(line):
                candidates.append(line)

    # Paragraph fallback
    if len(candidates) < 2:

        for paragraph in re.split(
            r"\n\s*\n",
            text
        ):

            paragraph = clean_question(
                paragraph
            )

            if len(paragraph.split()) >= 5:
                candidates.append(paragraph)

    # Deduplicate
    final = []
    seen = set()

    for candidate in candidates:

        key = normalize_text(
            candidate
        )

        if not key or key in seen:
            continue

        seen.add(key)

        final.append(
            {
                "number": len(final) + 1,
                "text": candidate,
            }
        )

    return final[:100]


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text):

    if not text:
        return []

    outcomes = []

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        line = re.sub(
            r"^(CLO|PLO)\s*\d*\s*[:\.\)\-]?\s*",
            "",
            line,
            flags=re.IGNORECASE
        )

        line = re.sub(
            r"^\d+\s*[\.\)\-:]\s*",
            "",
            line
        )

        if len(line.split()) >= 3:
            outcomes.append(line)

    if not outcomes:

        for chunk in re.split(
            r"[;\n]+",
            text
        ):

            chunk = clean_text(chunk)

            if len(chunk.split()) >= 3:
                outcomes.append(chunk)

    return outcomes[:20]


# ============================================================
# CLO ANALYSIS
# ============================================================

def extract_action_verbs(text):

    normalized = normalize_text(text)

    found = []

    for verb in BLOOM_LEVELS:

        if re.search(
            r"\b" + re.escape(verb) + r"\b",
            normalized
        ):
            found.append(verb)

    return found


def extract_content_terms(text):

    words = list(
        tokens(text)
    )

    action_words = set(
        BLOOM_LEVELS.keys()
    )

    return [
        word
        for word in words
        if word not in action_words
    ]


def score_clo(question, clo):

    if not clo:
        return 0, "No CLO provided."

    q_words = tokens(question)
    clo_words = tokens(clo)

    if not q_words or not clo_words:
        return 0, "Insufficient text for CLO analysis."

    content_terms = [
        word
        for word in clo_words
        if word not in BLOOM_LEVELS
    ]

    content_overlap = (
        len(
            set(content_terms).intersection(q_words)
        )
        / max(1, len(set(content_terms)))
    ) * 100

    clo_actions = extract_action_verbs(clo)
    q_actions = extract_action_verbs(question)

    action_match = False

    for clo_action in clo_actions:

        if clo_action in q_actions:
            action_match = True
            break

    score = 0

    if content_overlap >= 70:
        score += 60
    elif content_overlap >= 45:
        score += 45
    elif content_overlap >= 25:
        score += 30
    elif content_overlap >= 10:
        score += 18
    else:
        score += 5

    if action_match:
        score += 25
    elif clo_actions:
        score += 10

    # Direct semantic indicators.
    if "explain" in clo.lower() and (
        "explain" in question.lower()
        or "describe" in question.lower()
    ):
        score += 10

    if "analyze" in clo.lower() or "analyse" in clo.lower():
        if (
            "analyze" in question.lower()
            or "analyse" in question.lower()
        ):
            score += 10

    if "apply" in clo.lower():
        if any(
            word in question.lower()
            for word in [
                "calculate",
                "solve",
                "apply",
                "demonstrate",
                "use",
            ]
        ):
            score += 10

    score = min(100, score)

    if score >= 80:
        feedback = (
            "The question directly measures the specific "
            "knowledge or skill stated in the CLO."
        )
    elif score >= 60:
        feedback = (
            "The question addresses part of the CLO, but "
            "some required content or action is missing."
        )
    elif score >= 40:
        feedback = (
            "The question has a partial connection to the CLO "
            "but does not sufficiently measure its intended skill."
        )
    else:
        feedback = (
            "The question does not directly measure the "
            "specific knowledge or skill required by the CLO."
        )

    return round(score, 1), feedback


# ============================================================
# PLO ANALYSIS
# ============================================================

def score_plo(question, plo):

    if not plo:
        return 0, "No PLO provided."

    q_words = tokens(question)
    plo_words = tokens(plo)

    if not q_words or not plo_words:
        return 0, "Insufficient text for PLO analysis."

    # PLO is evaluated as a broader capability.
    plo_verbs = extract_action_verbs(plo)

    broader_capability_words = [
        word
        for word in plo_words
        if word not in BLOOM_LEVELS
    ]

    concept_match = (
        len(
            set(broader_capability_words).intersection(q_words)
        )
        / max(
            1,
            len(set(broader_capability_words))
        )
    ) * 100

    # Evidence of a broader capability.
    capability_score = 0

    if any(
        word in q_words
        for word in [
            "analyze",
            "analyse",
            "evaluate",
            "justify",
            "recommend",
            "compare",
            "design",
            "develop",
            "solve",
            "apply",
            "interpret",
        ]
    ):
        capability_score += 25

    if concept_match >= 50:
        capability_score += 55
    elif concept_match >= 30:
        capability_score += 42
    elif concept_match >= 15:
        capability_score += 28
    elif concept_match > 0:
        capability_score += 15
    else:
        capability_score += 5

    if plo_verbs:

        q_level = detect_bloom_level(
            question
        )

        plo_levels = [
            BLOOM_LEVELS[v]
            for v in plo_verbs
        ]

        target = max(plo_levels)

        difference = abs(
            q_level - target
        )

        if difference == 0:
            capability_score += 20
        elif difference == 1:
            capability_score += 12
        else:
            capability_score += 5

    score = min(
        100,
        capability_score
    )

    if score >= 80:
        feedback = (
            "The question provides clear evidence of the broader "
            "program-level capability represented by the PLO."
        )
    elif score >= 60:
        feedback = (
            "The question demonstrates some of the broader "
            "capability, but the evidence is incomplete."
        )
    elif score >= 40:
        feedback = (
            "The question has limited evidence of the broader "
            "program capability."
        )
    else:
        feedback = (
            "The question mainly tests isolated knowledge and "
            "provides little evidence of the broader PLO capability."
        )

    return round(score, 1), feedback


# ============================================================
# BLOOM ANALYSIS
# ============================================================

def detect_bloom_level(question):

    normalized = normalize_text(
        question
    )

    found = []

    for word, level in BLOOM_LEVELS.items():

        if re.search(
            r"\b" + re.escape(word) + r"\b",
            normalized
        ):
            found.append(level)

    if not found:

        if "why" in normalized:
            return 2

        if "how" in normalized:
            return 2

        if "?" in question:
            return 2

        return 1

    return max(found)


def bloom_analysis(
    question,
    clo,
    plo
):

    actual_level = detect_bloom_level(
        question
    )

    target_text = (
        f"{clo} {plo}"
    )

    target_levels = []

    for word in BLOOM_LEVELS:

        if re.search(
            r"\b" + re.escape(word) + r"\b",
            normalize_text(target_text)
        ):
            target_levels.append(
                BLOOM_LEVELS[word]
            )

    if not target_levels:
        target_level = actual_level
    else:
        target_level = max(
            target_levels
        )

    difference = abs(
        actual_level - target_level
    )

    if difference == 0:
        score = 100
    elif difference == 1:
        score = 88
    elif difference == 2:
        score = 70
    elif difference == 3:
        score = 55
    else:
        score = 40

    actual_name = BLOOM_NAMES[
        actual_level
    ]

    target_name = BLOOM_NAMES[
        target_level
    ]

    if score >= 80:
        feedback = (
            f"The question operates at {actual_name}, which is "
            f"appropriate for the intended {target_name} cognitive demand."
        )
    elif actual_level < target_level:
        feedback = (
            f"The question operates at {actual_name}, below the "
            f"intended {target_name} level. It requires a stronger "
            "cognitive task such as applying, analyzing, evaluating "
            "or creating."
        )
    else:
        feedback = (
            f"The question operates at {actual_name}, while the "
            f"intended demand is {target_name}. The cognitive task "
            "should be adjusted to better match the required level."
        )

    return (
        round(score, 1),
        actual_name,
        target_name,
        feedback
    )


# ============================================================
# OTHER METRICS
# ============================================================

def relevance_score(
    question,
    course,
    clo,
    plo
):

    reference = (
        f"{course} {clo} {plo}"
    )

    overlap = keyword_overlap(
        question,
        reference
    )

    if overlap >= 50:
        return 95
    if overlap >= 35:
        return 90
    if overlap >= 20:
        return 82
    if overlap >= 10:
        return 72

    return 60


def clarity_score(question):

    score = 90

    words = question.split()

    if len(words) < 5:
        score -= 15

    if len(words) > 80:
        score -= 12

    if question.count("?") > 2:
        score -= 10

    if re.search(
        r"\b(etc|something|anything|and so on)\b",
        question,
        flags=re.IGNORECASE
    ):
        score -= 10

    return max(
        40,
        min(100, score)
    )


def measurability_score(question):

    score = 80

    measurable_verbs = [
        "define",
        "identify",
        "calculate",
        "solve",
        "explain",
        "describe",
        "compare",
        "analyze",
        "analyse",
        "evaluate",
        "justify",
        "design",
        "develop",
        "recommend",
        "classify",
        "differentiate",
    ]

    normalized = normalize_text(
        question
    )

    if any(
        word in normalized.split()
        for word in measurable_verbs
    ):
        score += 15

    if "?" in question:
        score += 5

    if re.search(
        r"\b(discuss|write about)\b",
        normalized
    ):
        score -= 10

    return max(
        40,
        min(100, score)
    )


# ============================================================
# QUESTION TYPE
# ============================================================

def question_type(question):

    text = question.lower()

    if re.search(
        r"(?m)^\s*[a-d][\.\)]",
        text
    ):
        return "MCQ"

    if "true or false" in text:
        return "True / False"

    if "match the following" in text:
        return "Matching"

    if "fill in the blank" in text:
        return "Fill in the Blank"

    if re.search(
        r"\b(case|scenario|situation)\b",
        text
    ):
        return "Case / Application"

    if re.search(
        r"\b(calculate|compute|solve|find)\b",
        text
    ):
        return "Numerical / Problem"

    if re.search(
        r"\b(design|develop|construct|create)\b",
        text
    ):
        return "Practical / Design"

    if len(text.split()) > 45:
        return "Essay / Long Answer"

    return "Short Answer"


# ============================================================
# SPECIFIC FEEDBACK
# ============================================================

def build_revision_reason(
    clo_score,
    plo_score,
    bloom_score,
    clo_feedback,
    plo_feedback,
    bloom_feedback
):

    reasons = []

    if clo_score < ATTAINMENT:
        reasons.append(
            f"CLO ({clo_score:.0f}%): {clo_feedback}"
        )

    if plo_score < ATTAINMENT:
        reasons.append(
            f"PLO ({plo_score:.0f}%): {plo_feedback}"
        )

    if bloom_score < ATTAINMENT:
        reasons.append(
            f"Bloom ({bloom_score:.0f}%): {bloom_feedback}"
        )

    if not reasons:
        reasons.append(
            "The question requires only minor refinement."
        )

    return reasons


# ============================================================
# CONCEPT EXTRACTION FOR REVISION
# ============================================================

def outcome_concepts(outcome):

    if not outcome:
        return []

    words = tokens(outcome)

    action_words = set(
        BLOOM_LEVELS.keys()
    )

    concepts = [
        word
        for word in words
        if word not in action_words
    ]

    return concepts[:10]


def primary_revision_target(
    clo,
    plo
):

    if clo:
        return clo

    return plo


def target_action(
    clo,
    plo,
    original_question
):

    text = f"{clo} {plo}"

    for action in [
        "create",
        "design",
        "develop",
        "evaluate",
        "assess",
        "justify",
        "recommend",
        "analyze",
        "analyse",
        "compare",
        "differentiate",
        "apply",
        "calculate",
        "solve",
        "demonstrate",
        "explain",
        "describe",
        "identify",
    ]:

        if re.search(
            r"\b" + action + r"\b",
            normalize_text(text)
        ):
            return action

    current_level = detect_bloom_level(
        original_question
    )

    return {
        1: "explain",
        2: "explain",
        3: "apply",
        4: "analyze",
        5: "evaluate",
        6: "design",
    }.get(
        current_level,
        "explain"
    )


# ============================================================
# PRESERVE MCQ OPTIONS
# ============================================================

def get_options(question):

    options = re.findall(
        r"(?im)^\s*[A-D][\.\)]\s+.+$",
        question
    )

    return options


# ============================================================
# SUGGESTED QUESTION GENERATOR
# ============================================================

def generate_suggested_question(
    original,
    clo,
    plo,
    course
):

    target = primary_revision_target(
        clo,
        plo
    )

    concepts = outcome_concepts(
        target
    )

    action = target_action(
        clo,
        plo,
        original
    )

    qtype = question_type(
        original
    )

    # --------------------------------------------------------
    # MCQ
    # --------------------------------------------------------

    if qtype == "MCQ":

        options = get_options(
            original
        )

        if concepts:

            concept_text = " ".join(
                concepts[:4]
            )

            stem = (
                f"Which option best demonstrates "
                f"the application or explanation of "
                f"{concept_text}?"
            )

            if options:
                return stem + "\n" + "\n".join(
                    options
                )

            return stem

    # --------------------------------------------------------
    # NUMERICAL
    # --------------------------------------------------------

    if qtype == "Numerical / Problem":

        if action in {
            "apply",
            "calculate",
            "solve",
            "demonstrate",
        }:

            return (
                original.rstrip(".? ")
                + ". Show the calculation steps, "
                "apply the relevant principle, and "
                "state the final answer with the "
                "appropriate unit."
            )

    # --------------------------------------------------------
    # CASE
    # --------------------------------------------------------

    if qtype == "Case / Application":

        if concepts:

            concept_text = ", ".join(
                concepts[:4]
            )

            return (
                f"Analyze the case using "
                f"{concept_text} and recommend "
                "an appropriate solution based "
                "on the evidence provided."
            )

    # --------------------------------------------------------
    # ANALYZE
    # --------------------------------------------------------

    if action in {
        "analyze",
        "analyse",
    }:

        concept_text = ", ".join(
            concepts[:5]
        )

        return (
            f"Analyze {concept_text} and explain "
            "the key factors, relationships, "
            "causes, effects, or implications involved."
        )

    # --------------------------------------------------------
    # EVALUATE
    # --------------------------------------------------------

    if action in {
        "evaluate",
        "assess",
        "justify",
        "recommend",
    }:

        concept_text = ", ".join(
            concepts[:5]
        )

        return (
            f"Evaluate {concept_text} and justify "
            "your conclusion using relevant evidence "
            "or appropriate criteria."
        )

    # --------------------------------------------------------
    # APPLY
    # --------------------------------------------------------

    if action in {
        "apply",
        "demonstrate",
    }:

        concept_text = ", ".join(
            concepts[:5]
        )

        return (
            f"Apply the relevant principles of "
            f"{concept_text} to the given situation "
            "and demonstrate how they are used."
        )

    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------

    if action in {
        "create",
        "design",
        "develop",
    }:

        concept_text = ", ".join(
            concepts[:5]
        )

        return (
            f"Design or develop a practical solution "
            f"that applies {concept_text}, and explain "
            "the main features of your solution."
        )

    # --------------------------------------------------------
    # EXPLAIN
    # --------------------------------------------------------

    if action in {
        "explain",
        "describe",
    }:

        concept_text = ", ".join(
            concepts[:5]
        )

        return (
            f"Explain {concept_text} and describe "
            "its main features, process, or significance."
        )

    # --------------------------------------------------------
    # DEFAULT
    # --------------------------------------------------------

    concept_text = ", ".join(
        concepts[:5]
    )

    if concept_text:

        return (
            f"Explain {concept_text} and "
            "demonstrate its practical significance."
        )

    return original


# ============================================================
# AUTOMATIC REVISION REFINEMENT
# ============================================================

def refine_until_attained(
    original,
    initial_revision,
    clo,
    plo,
    course
):

    candidates = [
        initial_revision
    ]

    action = target_action(
        clo,
        plo,
        original
    )

    concepts = outcome_concepts(
        primary_revision_target(
            clo,
            plo
        )
    )

    concept_text = ", ".join(
        concepts[:5]
    )

    if action in {
        "analyze",
        "analyse",
    } and concept_text:

        candidates.append(
            f"Analyze {concept_text}, "
            "explain the key relationships or effects, "
            "and support your analysis with relevant evidence."
        )

    if action in {
        "evaluate",
        "assess",
        "justify",
        "recommend",
    } and concept_text:

        candidates.append(
            f"Evaluate {concept_text}, "
            "compare the relevant alternatives or factors, "
            "and justify your conclusion using appropriate evidence."
        )

    if action in {
        "apply",
        "demonstrate",
        "calculate",
        "solve",
    } and concept_text:

        candidates.append(
            f"Apply the relevant principles of "
            f"{concept_text} to the given problem or situation, "
            "show the steps used, and explain the result."
        )

    if action in {
        "design",
        "develop",
        "create",
    } and concept_text:

        candidates.append(
            f"Design a practical solution using "
            f"{concept_text}, explain how it works, "
            "and justify the main decisions in your design."
        )

    if action in {
        "explain",
        "describe",
    } and concept_text:

        candidates.append(
            f"Explain {concept_text}, "
            "describe the process or main features, "
            "and explain their significance."
        )

    # Return the strongest candidate after actual scoring.
    best_question = initial_revision
    best_score = -1

    for candidate in candidates:

        result = calculate_question_metrics(
            candidate,
            course,
            [clo] if clo else [],
            [plo] if plo else []
        )

        score = result["Overall"]

        if score is not None and score > best_score:

            best_score = score
            best_question = candidate

        if score is not None and score >= 80:
            return candidate

    return best_question


# ============================================================
# COMPLETE METRIC CALCULATION
# ============================================================

def calculate_question_metrics(
    question,
    course,
    clos,
    plos
):

    # CLO
    clo_scores = []

    for clo in clos:

        score, feedback = score_clo(
            question,
            clo
        )

        clo_scores.append(
            (
                score,
                clo,
                feedback
            )
        )

    if clo_scores:

        best_clo_score, best_clo, best_clo_feedback = max(
            clo_scores,
            key=lambda x: x[0]
        )

    else:

        best_clo_score = None
        best_clo = ""
        best_clo_feedback = (
            "CLO analysis is unavailable."
        )

    # PLO
    plo_scores = []

    for plo in plos:

        score, feedback = score_plo(
            question,
            plo
        )

        plo_scores.append(
            (
                score,
                plo,
                feedback
            )
        )

    if plo_scores:

        best_plo_score, best_plo, best_plo_feedback = max(
            plo_scores,
            key=lambda x: x[0]
        )

    else:

        best_plo_score = None
        best_plo = ""
        best_plo_feedback = (
            "PLO analysis is unavailable."
        )

    # Bloom
    bloom_score, actual_bloom, target_bloom, bloom_feedback = (
        bloom_analysis(
            question,
            best_clo,
            best_plo
        )
    )

    relevance = relevance_score(
        question,
        course,
        best_clo,
        best_plo
    )

    clarity = clarity_score(
        question
    )

    measurability = measurability_score(
        question
    )

    if (
        best_clo_score is None
        or best_plo_score is None
    ):

        overall = None

    else:

        overall = (
            best_clo_score * 0.30
            + best_plo_score * 0.20
            + bloom_score * 0.20
            + relevance * 0.10
            + clarity * 0.10
            + measurability * 0.10
        )

        overall = round(
            overall,
            1
        )

    return {
        "Question": question,
        "CLO Alignment": best_clo_score,
        "CLO Feedback": best_clo_feedback,
        "Best CLO": best_clo,

        "PLO Alignment": best_plo_score,
        "PLO Feedback": best_plo_feedback,
        "Best PLO": best_plo,

        "Bloom Alignment": bloom_score,
        "Actual Bloom": actual_bloom,
        "Target Bloom": target_bloom,
        "Bloom Feedback": bloom_feedback,

        "Subject Relevance": relevance,
        "Clarity": clarity,
        "Measurability": measurability,

        "Overall": overall,

        "Question Type": question_type(
            question
        ),
    }


# ============================================================
# FULL ANALYSIS
# ============================================================

def analyze_question(
    question,
    number,
    course,
    clos,
    plos
):

    metrics = calculate_question_metrics(
        question,
        course,
        clos,
        plos
    )

    overall = metrics["Overall"]

    if overall is None:

        status = "Awaiting Analysis"

        needs_revision = False

    elif overall >= 85:

        status = "Strong"

        needs_revision = False

    elif overall >= 80:

        status = "Attained"

        needs_revision = False

    elif overall >= 60:

        status = "Needs Revision"

        needs_revision = True

    else:

        status = "Weak"

        needs_revision = True

    revision = ""

    if needs_revision:

        revision = generate_suggested_question(
            question,
            metrics["Best CLO"],
            metrics["Best PLO"],
            course
        )

        revision = refine_until_attained(
            question,
            revision,
            metrics["Best CLO"],
            metrics["Best PLO"],
            course
        )

    reasons = build_revision_reason(
        metrics["CLO Alignment"] or 0,
        metrics["PLO Alignment"] or 0,
        metrics["Bloom Alignment"],
        metrics["CLO Feedback"],
        metrics["PLO Feedback"],
        metrics["Bloom Feedback"]
    )

    metrics.update(
        {
            "Number": number,
            "Status": status,
            "Needs Revision": needs_revision,
            "Revision": revision,
            "Revision Reasons": reasons,
            "Accepted": False,
        }
    )

    return metrics


# ============================================================
# RE-SCORE ACCEPTED REVISION
# ============================================================

def rescore_accepted_revision(
    original_result,
    revised_question,
    course,
    clos,
    plos
):

    revised = analyze_question(
        revised_question,
        original_result["Number"],
        course,
        clos,
        plos
    )

    revised["Original Question"] = (
        original_result["Question"]
    )

    revised["Accepted"] = True

    return revised


# ============================================================
# PAGE
# ============================================================

st.title("🎓 OBE Quiz Checker")

st.caption(
    "Distinct CLO, PLO and Bloom evaluation with "
    "automatic attainment-focused question revision."
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("Assessment Information")

    course = st.text_input(
        "Course / Subject",
        placeholder="e.g. Chemistry"
    )

    assessment_type = st.selectbox(
        "Assessment Type",
        [
            "Quiz",
            "Assignment",
            "Test",
            "Midterm",
            "Final Exam",
            "Class Activity",
            "Other",
        ]
    )

    total_marks = st.number_input(
        "Total Marks",
        min_value=1,
        value=100
    )

    st.divider()

    st.subheader(
        "Scoring Weights"
    )

    for metric, weight in WEIGHTS.items():

        st.write(
            f"**{metric}:** {weight}%"
        )

    st.divider()

    st.info(
        "Target after revision: 80% or above."
    )


# ============================================================
# CLO / PLO
# ============================================================

st.header("1. Learning Outcomes")

col1, col2 = st.columns(2)

with col1:

    st
