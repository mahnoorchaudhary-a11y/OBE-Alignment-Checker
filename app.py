import re
import io
import html
from pathlib import Path

import streamlit as st
import pandas as pd


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Assessment Alignment Checker",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except Exception:
    PDF_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

try:
    from pptx import Presentation
    PPTX_AVAILABLE = True
except Exception:
    PPTX_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

try:
    import pytesseract
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

try:
    import openpyxl
    EXCEL_AVAILABLE = True
except Exception:
    EXCEL_AVAILABLE = False


# ============================================================
# SIMPLE CSS
# ============================================================

st.markdown(
    """
    <style>
    .main-title {
        font-size: 34px;
        font-weight: 800;
        margin-bottom: 4px;
    }

    .subtitle {
        color: #666;
        font-size: 16px;
        margin-bottom: 20px;
    }

    .score-box {
        padding: 22px;
        border-radius: 18px;
        text-align: center;
        margin-bottom: 18px;
        border: 1px solid #ddd;
    }

    .score-number {
        font-size: 48px;
        font-weight: 800;
        line-height: 1.1;
    }

    .score-label {
        font-size: 20px;
        font-weight: 700;
        margin-top: 5px;
    }

    .metric-card {
        padding: 18px;
        border-radius: 15px;
        border: 1px solid #ddd;
        background: white;
        min-height: 115px;
        text-align: center;
    }

    .metric-title {
        font-size: 14px;
        color: #666;
        font-weight: 600;
    }

    .metric-value {
        font-size: 29px;
        font-weight: 800;
        margin-top: 8px;
    }

    .revision-box {
        padding: 18px;
        border-radius: 14px;
        border: 1px solid #ddd;
        background: #fafafa;
        margin-bottom: 12px;
    }

    .attained-box {
        padding: 20px;
        border-radius: 16px;
        border: 2px solid #54b36a;
        background: #f1fff4;
        margin: 10px 0;
    }

    .review-box {
        padding: 20px;
        border-radius: 16px;
        border: 2px solid #e2b93b;
        background: #fffdf0;
        margin: 10px 0;
    }

    .needs-box {
        padding: 20px;
        border-radius: 16px;
        border: 2px solid #df5c5c;
        background: #fff5f5;
        margin: 10px 0;
    }

    .small-note {
        color: #666;
        font-size: 13px;
    }

    .question-text {
        font-size: 17px;
        line-height: 1.55;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "assessment_text": "",
    "questions": [],
    "results": [],
    "analyzed": False,
    "revision_version": 0,
    "last_attained_count": 0,
    "celebrate_overall": False,
    "selected_question": 0,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# BASIC TEXT UTILITIES
# ============================================================

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "of", "to", "in", "on",
    "for", "from", "with", "by", "at", "as", "is", "are", "was",
    "were", "be", "been", "being", "this", "that", "these", "those",
    "it", "its", "into", "about", "which", "who", "what", "when",
    "where", "why", "how", "does", "do", "did", "can", "could",
    "should", "would", "will", "may", "might", "must", "than",
    "their", "there", "they", "them", "he", "she", "his", "her",
    "we", "you", "your", "our", "i", "me", "my", "through",
    "using", "use", "used", "following", "given", "based"
}


BLOOM_VERBS = {
    "Remember": [
        "define", "identify", "list", "name", "state", "recall",
        "recognize", "mention", "label", "select"
    ],
    "Understand": [
        "describe", "explain", "summarize", "interpret", "discuss",
        "classify", "illustrate", "paraphrase", "outline"
    ],
    "Apply": [
        "apply", "calculate", "solve", "use", "demonstrate",
        "implement", "execute", "compute", "perform"
    ],
    "Analyze": [
        "analyze", "analyse", "compare", "contrast", "differentiate",
        "examine", "investigate", "categorize", "distinguish",
        "break down"
    ],
    "Evaluate": [
        "evaluate", "justify", "assess", "critique", "judge",
        "defend", "argue", "appraise", "validate"
    ],
    "Create": [
        "design", "develop", "create", "formulate", "construct",
        "produce", "propose", "plan", "generate", "develop"
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


def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\x00", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def words(text):
    text = text.lower()
    return re.findall(r"[a-zA-Z][a-zA-Z0-9\-']+", text)


def meaningful_words(text):
    result = []

    for word in words(text):
        if word in STOPWORDS:
            continue

        if len(word) <= 2:
            continue

        result.append(word)

    return result


def content_words(text):
    result = []

    bloom_words = set()

    for level_words in BLOOM_VERBS.values():
        bloom_words.update(level_words)

    for word in meaningful_words(text):
        if word not in bloom_words:
            result.append(word)

    return result


def unique_preserved_terms(text):
    terms = []

    # Important numbers
    numbers = re.findall(
        r"\b\d+(?:\.\d+)?(?:\s?(?:kg|g|mg|cm|m|km|s|min|hr|%|°C|°F))?\b",
        text,
        flags=re.I
    )

    terms.extend(numbers)

    # Technical-looking words
    technical = re.findall(
        r"\b[A-Z]{2,}[A-Za-z0-9\-]*\b",
        text
    )

    terms.extend(technical)

    # Meaningful terms
    terms.extend(content_words(text))

    unique = []

    for term in terms:
        term = term.strip()
        if len(term) >= 3 and term.lower() not in [x.lower() for x in unique]:
            unique.append(term)

    return unique


def overlap_score(text1, text2):
    a = set(content_words(text1))
    b = set(content_words(text2))

    if not a or not b:
        return 0

    overlap = len(a.intersection(b))

    coverage_a = overlap / max(len(a), 1)
    coverage_b = overlap / max(len(b), 1)

    score = (
        coverage_a * 50 +
        coverage_b * 50
    )

    return round(min(100, score), 1)


# ============================================================
# BLOOM FUNCTIONS
# ============================================================

def find_bloom_verb(text):
    lower = text.lower()

    for level in BLOOM_ORDER:
        for verb in BLOOM_VERBS[level]:
            pattern = r"\b" + re.escape(verb) + r"\b"

            if re.search(pattern, lower):
                return verb, level

    return "", ""


def detect_bloom(text):
    _, level = find_bloom_verb(text)
    return level if level else "Understand"


def bloom_index(level):
    if level in BLOOM_ORDER:
        return BLOOM_ORDER.index(level)

    return 1


def bloom_score(question, target_level):
    _, question_level = find_bloom_verb(question)

    if not question_level:
        return 72

    difference = abs(
        bloom_index(question_level) -
        bloom_index(target_level)
    )

    if difference == 0:
        return 100

    if difference == 1:
        return 88

    if difference == 2:
        return 75

    return 62


# ============================================================
# OUTCOME EXTRACTION
# ============================================================

def parse_outcomes(text, prefix):
    outcomes = []

    if not text:
        return outcomes

    pattern = re.compile(
        rf"(?i)\b({prefix}\s*\d+)\s*[:\-–—]\s*(.+)"
    )

    for line in text.splitlines():
        line = clean_text(line)

        if not line:
            continue

        match = pattern.search(line)

        if match:
            code = re.sub(r"\s+", "", match.group(1).upper())
            description = clean_text(match.group(2))

            outcomes.append({
                "code": code,
                "description": description
            })

    # If the user simply pasted paragraphs, make each non-empty
    # line an outcome.
    if not outcomes:
        lines = [
            clean_text(x)
            for x in text.splitlines()
            if clean_text(x)
        ]

        for i, line in enumerate(lines, start=1):
            outcomes.append({
                "code": f"{prefix}{i}",
                "description": line
            })

    return outcomes


# ============================================================
# FILE READING
# ============================================================

def read_pdf(file_bytes):
    if not PDF_AVAILABLE:
        return (
            "",
            "PDF reader is unavailable. Add PyMuPDF to requirements.txt."
        )

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")

        pages = []

        for page in doc:
            text = page.get_text("text")

            if text and text.strip():
                pages.append(text)

        text = "\n\n".join(pages).strip()

        # OCR fallback for scanned PDF
        if len(text) < 80 and OCR_AVAILABLE and PIL_AVAILABLE:
            ocr_pages = []

            for page in doc:
                pix = page.get_pixmap(
                    matrix=fitz.Matrix(1.5, 1.5),
                    alpha=False
                )

                image = Image.open(
                    io.BytesIO(pix.tobytes("png"))
                )

                try:
                    ocr_text = pytesseract.image_to_string(image)
                except Exception:
                    ocr_text = ""

                if ocr_text.strip():
                    ocr_pages.append(ocr_text)

            text = "\n\n".join(ocr_pages).strip()

        if not text:
            return "", "No readable text was found in the PDF."

        return clean_text(text), ""

    except Exception as exc:
        return "", f"Could not read PDF: {exc}"


def read_docx(file_bytes):
    if not DOCX_AVAILABLE:
        return "", "python-docx is not installed."

    try:
        doc = Document(io.BytesIO(file_bytes))

        parts = []

        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                parts.append(paragraph.text)

        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(
                    cell.text.strip()
                    for cell in row.cells
                )

                if row_text.strip():
                    parts.append(row_text)

        return clean_text("\n".join(parts)), ""

    except Exception as exc:
        return "", f"Could not read DOCX: {exc}"


def read_pptx(file_bytes):
    if not PPTX_AVAILABLE:
        return "", "python-pptx is not installed."

    try:
        presentation = Presentation(io.BytesIO(file_bytes))

        parts = []

        for slide_number, slide in enumerate(
            presentation.slides,
            start=1
        ):
            parts.append(f"Slide {slide_number}")

            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text = shape.text.strip()

                    if text:
                        parts.append(text)

        return clean_text("\n".join(parts)), ""

    except Exception as exc:
        return "", f"Could not read PPTX: {exc}"


def read_excel(file_bytes):
    try:
        workbook = pd.ExcelFile(io.BytesIO(file_bytes))

        parts = []

        for sheet in workbook.sheet_names:
            df = pd.read_excel(
                io.BytesIO(file_bytes),
                sheet_name=sheet,
                header=None
            )

            parts.append(f"Sheet: {sheet}")

            for row in df.fillna("").astype(str).values.tolist():
                row_text = " | ".join(
                    cell.strip()
                    for cell in row
                    if cell.strip()
                )

                if row_text:
                    parts.append(row_text)

        return clean_text("\n".join(parts)), ""

    except Exception as exc:
        return "", f"Could not read Excel file: {exc}"


def read_csv(file_bytes):
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))

        parts = []

        for row in df.fillna("").astype(str).values.tolist():
            row_text = " | ".join(
                cell.strip()
                for cell in row
                if cell.strip()
            )

            if row_text:
                parts.append(row_text)

        return clean_text("\n".join(parts)), ""

    except Exception as exc:
        return "", f"Could not read CSV: {exc}"


def read_image(file_bytes):
    if not PIL_AVAILABLE:
        return "", "Pillow is not installed."

    if not OCR_AVAILABLE:
        return "", "pytesseract is not installed."

    try:
        image = Image.open(io.BytesIO(file_bytes))

        text = pytesseract.image_to_string(image)

        return clean_text(text), ""

    except Exception as exc:
        return "", f"Could not read image: {exc}"


def read_svg(file_bytes):
    try:
        text = file_bytes.decode("utf-8", errors="ignore")

        text = re.sub(
            r"<script.*?</script>",
            " ",
            text,
            flags=re.I | re.S
        )

        text = re.sub(
            r"<style.*?</style>",
            " ",
            text,
            flags=re.I | re.S
        )

        text = re.sub(r"<[^>]+>", " ", text)

        text = html.unescape(text)

        return clean_text(text), ""

    except Exception as exc:
        return "", f"Could not read SVG: {exc}"


def read_uploaded_file(uploaded_file):
    name = uploaded_file.name.lower()
    file_bytes = uploaded_file.getvalue()

    if name.endswith(".pdf"):
        return read_pdf(file_bytes)

    if name.endswith(".docx"):
        return read_docx(file_bytes)

    if name.endswith(".pptx"):
        return read_pptx(file_bytes)

    if name.endswith(".xlsx") or name.endswith(".xls"):
        return read_excel(file_bytes)

    if name.endswith(".csv"):
        return read_csv(file_bytes)

    if (
        name.endswith(".txt")
        or name.endswith(".md")
        or name.endswith(".text")
    ):
        return clean_text(
            file_bytes.decode("utf-8", errors="ignore")
        ), ""

    if name.endswith(".svg"):
        return read_svg(file_bytes)

    if name.endswith(
        (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")
    ):
        return read_image(file_bytes)

    return "", (
        "Unsupported file format. "
        "Use PDF, DOCX, PPTX, XLSX, XLS, CSV, TXT, MD, SVG, "
        "PNG, JPG, JPEG, WEBP, BMP or TIFF."
    )


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def remove_question_label(text):
    text = re.sub(
        r"^\s*(?:Q(?:uestion)?\s*)?\d+\s*[\.\):\-–—]\s*",
        "",
        text,
        flags=re.I
    )

    return text.strip()


def detect_question_type(question):
    q = question.lower().strip()

    if re.search(r"\btrue\s*/?\s*false\b", q):
        return "True / False"

    if re.search(
        r"\b(fill|complete)\s+(in\s+the\s+)?blank",
        q
    ):
        return "Fill in the Blank"

    if "match the following" in q or "matching" in q:
        return "Matching"

    if re.search(
        r"(^|\n)\s*[a-dA-D][\.\)]\s+",
        question
    ):
        return "Multiple Choice"

    if any(
        phrase in q
        for phrase in [
            "case study",
            "scenario",
            "given situation",
            "read the case"
        ]
    ):
        return "Case Study / Scenario"

    if any(
        word in q
        for word in [
            "calculate",
            "compute",
            "solve",
            "find the value",
            "determine the value"
        ]
    ):
        return "Numerical / Problem Solving"

    if any(
        word in q
        for word in [
            "design",
            "develop",
            "implement",
            "demonstrate",
            "perform",
            "construct"
        ]
    ):
        return "Practical / Application"

    if any(
        word in q
        for word in [
            "essay",
            "write an essay"
        ]
    ):
        return "Essay"

    if len(question.split()) > 45:
        return "Long Answer"

    return "Short Answer"


def split_question_blocks(text):
    text = clean_text(text)

    if not text:
        return []

    # Normalize common question numbering.
    text = re.sub(
        r"(?m)^\s*(?:Question\s*)?(\d{1,3})\s*[\.\):\-–—]\s*",
        r"\nQUESTION_\1 ",
        text,
        flags=re.I
    )

    blocks = re.split(
        r"\nQUESTION_\d+\s*",
        text
    )

    questions = []

    for block in blocks:
        block = clean_text(block)

        if len(block) < 8:
            continue

        # Remove answer keys and obvious headers.
        if re.match(
            r"^(answer key|answers|instructions|section [a-z])\b",
            block,
            flags=re.I
        ):
            continue

        questions.append(remove_question_label(block))

    # If numbering was not found, use paragraphs with questions.
    if len(questions) < 2:
        paragraphs = [
            clean_text(x)
            for x in text.split("\n")
            if clean_text(x)
        ]

        possible = []

        for paragraph in paragraphs:
            if (
                "?" in paragraph
                or find_bloom_verb(paragraph)[0]
                or re.match(
                    r"^\s*[a-dA-D][\.\)]\s+",
                    paragraph
                )
            ):
                if len(paragraph) >= 10:
                    possible.append(paragraph)

        if len(possible) > len(questions):
            questions = possible

    # Limit absurdly large blocks caused by page text.
    cleaned = []

    for question in questions:
        question = clean_text(question)

        if len(question) > 1800:
            pieces = re.split(
                r"(?<=[\?\.])\s+(?=(?:What|Why|How|Explain|Describe|Analyze|Analyse|Define|Calculate|Discuss|Compare|Evaluate|Identify|Design|Solve)\b)",
                question,
                flags=re.I
            )

            if len(pieces) > 1:
                cleaned.extend(
                    p.strip()
                    for p in pieces
                    if len(p.strip()) >= 10
                )
            else:
                cleaned.append(question)
        else:
            cleaned.append(question)

    return cleaned


# ============================================================
# QUESTION CORE / PRESERVATION
# ============================================================

def remove_action_verb_from_start(question):
    text = remove_question_label(question).strip()

    patterns = []

    for level in BLOOM_ORDER:
        for verb in BLOOM_VERBS[level]:
            patterns.append(verb)

    verb_pattern = "|".join(
        sorted(
            [re.escape(x) for x in patterns],
            key=len,
            reverse=True
        )
    )

    text = re.sub(
        rf"^\s*(?:{verb_pattern})\b\s*",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"^\s*(?:what|why|how|when|where|which|who)\s+(?:is|are|does|do|did|can|could|would|will)?\s*",
        "",
        text,
        flags=re.I
    )

    return text.strip(" .?:;,-")


def extract_question_core(question):
    """
    Keeps the original subject/topic.
    This is intentionally based on the ORIGINAL QUESTION,
    not generated from the CLO/PLO.
    """

    text = remove_action_verb_from_start(question)

    # Remove obvious MCQ option lines.
    text = re.split(
        r"\n\s*[A-Da-d][\.\)]\s+",
        text
    )[0]

    text = clean_text(text)

    if len(text) > 400:
        text = text[:400].rstrip()

    return text


def preservation_score(original, candidate):
    original_terms = set(
        unique_preserved_terms(original)
    )

    candidate_terms = set(
        unique_preserved_terms(candidate)
    )

    if not original_terms:
        return 80

    preserved = len(
        original_terms.intersection(candidate_terms)
    )

    return round(
        min(
            100,
            preserved / len(original_terms) * 100
        ),
        1
    )


def same_question_type(original, candidate):
    return detect_question_type(original) == detect_question_type(candidate)


# ============================================================
# SCORING
# ============================================================

def outcome_match_score(question, outcome):
    if not outcome:
        return 50

    description = outcome.get("description", "")

    if not description:
        return 50

    question_terms = set(content_words(question))
    outcome_terms = set(content_words(description))

    if not question_terms or not outcome_terms:
        return 55

    overlap = question_terms.intersection(outcome_terms)

    if not overlap:
        # Still give credit if Bloom/action skill matches.
        q_verb, q_level = find_bloom_verb(question)
        o_verb, o_level = find_bloom_verb(description)

        if q_level and o_level:
            if q_level == o_level:
                return 62
            if abs(
                bloom_index(q_level) -
                bloom_index(o_level)
            ) == 1:
                return 57

        return 50

    outcome_coverage = (
        len(overlap) /
        max(len(outcome_terms), 1)
    )

    question_coverage = (
        len(overlap) /
        max(len(question_terms), 1)
    )

    score = (
        50 +
        outcome_coverage * 35 +
        question_coverage * 15
    )

    return round(min(100, score), 1)


def clarity_score(question):
    text = clean_text(question)
    length = len(text.split())

    score = 94

    if length < 5:
        score -= 20
    elif length < 8:
        score -= 10

    if length > 100:
        score -= 8

    if text.count("?") > 1:
        score -= 5

    vague_phrases = [
        "discuss everything",
        "write something",
        "say something",
        "what do you know",
        "write about",
        "comment on this"
    ]

    lower = text.lower()

    for phrase in vague_phrases:
        if phrase in lower:
            score -= 12

    return round(max(45, min(100, score)), 1)


def measurability_score(question):
    _, level = find_bloom_verb(question)

    if level:
        return 96

    if "?" in question:
        return 85

    return 76


def relevance_score(question, clo, plo):
    clo_score = outcome_match_score(
        question,
        clo
    )

    plo_score = outcome_match_score(
        question,
        plo
    )

    return round(
        clo_score * 0.65 +
        plo_score * 0.35,
        1
    )


def choose_best_outcome(question, outcomes):
    if not outcomes:
        return None

    scored = []

    for outcome in outcomes:
        score = outcome_match_score(
            question,
            outcome
        )

        scored.append(
            (score, outcome)
        )

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return scored[0][1]


def evaluate_question(
    question,
    clos,
    plos
):
    best_clo = choose_best_outcome(
        question,
        clos
    )

    best_plo = choose_best_outcome(
        question,
        plos
    )

    clo_score = outcome_match_score(
        question,
        best_clo
    ) if best_clo else 50

    plo_score = outcome_match_score(
        question,
        best_plo
    ) if best_plo else 50

    target_bloom = (
        detect_bloom(
            best_clo["description"]
        )
        if best_clo
        else "Understand"
    )

    bloom = bloom_score(
        question,
        target_bloom
    )

    clarity = clarity_score(question)

    measurability = measurability_score(question)

    relevance = relevance_score(
        question,
        best_clo,
        best_plo
    )

    overall = (
        clo_score * 0.20 +
        plo_score * 0.15 +
        bloom * 0.20 +
        relevance * 0.15 +
        clarity * 0.15 +
        measurability * 0.15
    )

    overall = round(
        min(100, max(0, overall)),
        1
    )

    if overall >= 75:
        status = "Attained"
    elif overall >= 50:
        status = "Review"
    else:
        status = "Needs Revision"

    return {
        "question": question,
        "type": detect_question_type(question),
        "clo": best_clo["code"] if best_clo else "—",
        "clo_description": (
            best_clo["description"]
            if best_clo
            else ""
        ),
        "plo": best_plo["code"] if best_plo else "—",
        "plo_description": (
            best_plo["description"]
            if best_plo
            else ""
        ),
        "clo_score": round(clo_score, 1),
        "plo_score": round(plo_score, 1),
        "bloom": target_bloom,
        "bloom_score": round(bloom, 1),
        "relevance": round(relevance, 1),
        "clarity": round(clarity, 1),
        "measurability": round(measurability, 1),
        "overall": overall,
        "status": status
    }


# ============================================================
# SMART REVISION GENERATOR
# ============================================================

def replace_leading_verb(question, new_verb):
    """
    Changes only the action verb.
    The subject/topic remains from the original question.
    """

    original = remove_question_label(question).strip()

    old_verb, _ = find_bloom_verb(original)

    if old_verb:
        pattern = (
            r"^\s*" +
            re.escape(old_verb) +
            r"\b"
        )

        changed = re.sub(
            pattern,
            new_verb,
            original,
            count=1,
            flags=re.I
        )

        if changed != original:
            return changed

    return (
        new_verb.capitalize() +
        " " +
        extract_question_core(original)
    )


def make_clear_revision(question):
    """
    Improves clarity without changing the topic.
    """

    original = clean_text(question)
    lower = original.lower()
    q_type = detect_question_type(original)

    if q_type == "Numerical / Problem Solving":
        if "show" not in lower and "step" not in lower:
            return (
                original.rstrip(" .?") +
                " and show the steps used to obtain your answer."
            )

    if q_type == "True / False":
        return original

    if q_type == "Multiple Choice":
        stem = re.split(
            r"\n\s*[A-Da-d][\.\)]\s+",
            original
        )[0]

        if "select" not in stem.lower():
            return (
                "Select the best answer: " +
                stem.rstrip(" .?")
            )

    if q_type == "Case Study / Scenario":
        if "explain" not in lower and "analyze" not in lower:
            return (
                original.rstrip(" .?") +
                " and explain your reasoning."
            )

    if q_type in [
        "Essay",
        "Long Answer",
        "Short Answer"
    ]:
        verb, level = find_bloom_verb(original)

        if verb:
            if "example" not in lower:
                return (
                    original.rstrip(" .?") +
                    " and support your answer with one relevant example."
                )

            return original

        core = extract_question_core(original)

        return (
            "Explain " +
            core.rstrip(" .?") +
            " clearly and support your answer with one relevant example."
        )

    if q_type == "Practical / Application":
        if "show" not in lower and "demonstrate" not in lower:
            return (
                original.rstrip(" .?") +
                " and demonstrate the expected result."
            )

    return original


def make_measurable_revision(question):
    """
    Makes the task observable without introducing a new subject.
    """

    original = clean_text(question)
    lower = original.lower()
    q_type = detect_question_type(original)

    if q_type == "Numerical / Problem Solving":
        if "show" not in lower and "steps" not in lower:
            return (
                original.rstrip(" .?") +
                " Show the steps and give the final answer with appropriate units."
            )

        return original

    if q_type == "Multiple Choice":
        stem = re.split(
            r"\n\s*[A-Da-d][\.\)]\s+",
            original
        )[0]

        return (
            "Select the best answer for the following: " +
            stem.rstrip(" .?")
        )

    if q_type == "Case Study / Scenario":
        if "justify" not in lower and "explain" not in lower:
            return (
                original.rstrip(" .?") +
                " Explain the reasoning behind your response."
            )

    if q_type in [
        "Short Answer",
        "Long Answer",
        "Essay"
    ]:
        verb, _ = find_bloom_verb(original)

        if verb:
            if "explain" not in lower and "justify" not in lower:
                return (
                    original.rstrip(" .?") +
                    " and explain the reasoning behind your answer."
                )

            return original

        return (
            "Explain " +
            extract_question_core(original) +
            " and give one relevant example."
        )

    if q_type == "Practical / Application":
        return (
            original.rstrip(" .?") +
            " and demonstrate the expected outcome."
        )

    return original


def make_bloom_revision(question, target_bloom):
    """
    Changes the cognitive action while preserving the original topic.
    """

    original = clean_text(question)

    target_verbs = {
        "Remember": "Identify",
        "Understand": "Explain",
        "Apply": "Apply",
        "Analyze": "Analyze",
        "Evaluate": "Evaluate",
        "Create": "Design"
    }

    new_verb = target_verbs.get(
        target_bloom,
        "Explain"
    )

    return replace_leading_verb(
        original,
        new_verb
    )


def add_shared_outcome_concept(
    question,
    outcome
):
    """
    Adds a concept ONLY when the concept already exists
    in the original question. This prevents unrelated
    suggested questions.
    """

    if not outcome:
        return question

    q_terms = set(content_words(question))
    outcome_terms = content_words(
        outcome.get("description", "")
    )

    shared = []

    for term in outcome_terms:
        if term in q_terms:
            shared.append(term)

    if not shared:
        return question

    # Do not overcomplicate the question.
    return question


def candidate_is_safe(
    original,
    candidate,
    old_result,
    new_result
):
    candidate = clean_text(candidate)

    if not candidate:
        return False

    if candidate.lower() == original.lower():
        return False

    # Preserve original subject.
    preservation = preservation_score(
        original,
        candidate
    )

    if preservation < 65:
        return False

    # Do not accidentally change question type.
    if not same_question_type(
        original,
        candidate
    ):
        return False

    # Candidate should actually improve.
    if new_result["overall"] <= old_result["overall"]:
        return False

    return True


def generate_revisions(
    question,
    clos,
    plos
):
    """
    Generates a small number of safe revisions.
    Recommendations are based primarily on the original
    question, not on generic templates.
    """

    old_result = evaluate_question(
        question,
        clos,
        plos
    )

    candidates = []

    # --------------------------------------------------------
    # Candidate 1: clarity
    # --------------------------------------------------------

    candidate = make_clear_revision(
        question
    )

    candidate = add_shared_outcome_concept(
        candidate,
        choose_best_outcome(
            question,
            clos
        )
    )

    result = evaluate_question(
        candidate,
        clos,
        plos
    )

    if candidate_is_safe(
        question,
        candidate,
        old_result,
        result
    ):
        candidates.append({
            "text": candidate,
            "result": result,
            "reason": "The original topic is preserved while the task is made clearer."
        })

    # --------------------------------------------------------
    # Candidate 2: measurability
    # --------------------------------------------------------

    candidate = make_measurable_revision(
        question
    )

    result = evaluate_question(
        candidate,
        clos,
        plos
    )

    if candidate_is_safe(
        question,
        candidate,
        old_result,
        result
    ):
        candidates.append({
            "text": candidate,
            "result": result,
            "reason": "The question now asks for an observable response."
        })

    # --------------------------------------------------------
    # Candidate 3: Bloom alignment
    # --------------------------------------------------------

    best_clo = choose_best_outcome(
        question,
        clos
    )

    target_bloom = (
        detect_bloom(
            best_clo["description"]
        )
        if best_clo
        else detect_bloom(question)
    )

    candidate = make_bloom_revision(
        question,
        target_bloom
    )

    result = evaluate_question(
        candidate,
        clos,
        plos
    )

    if candidate_is_safe(
        question,
        candidate,
        old_result,
        result
    ):
        candidates.append({
            "text": candidate,
            "result": result,
            "reason": (
                "The question keeps its original topic while "
                "using an action verb closer to the intended learning outcome."
            )
        })

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    unique = []

    seen = set()

    for item in candidates:
        key = item["text"].lower().strip()

        if key not in seen:
            seen.add(key)
            unique.append(item)

    # Highest score first.
    unique.sort(
        key=lambda x: x["result"]["overall"],
        reverse=True
    )

    return unique[:3], old_result


# ============================================================
# DISPLAY HELPERS
# ============================================================

def score_color(score):
    if score >= 75:
        return "#188038"

    if score >= 50:
        return "#b77900"

    return "#c5221f"


def status_emoji(status):
    if status == "Attained":
        return "🟢"

    if status == "Review":
        return "🟡"

    return "🔴"


def show_score_banner(score, label=None):
    color = score_color(score)

    if label is None:
        if score >= 75:
            label = "Attained"
        elif score >= 50:
            label = "Review"
        else:
            label = "Needs Revision"

    st.markdown(
        f"""
        <div class="score-box"
             style="border: 2px solid {color};">
            <div class="score-number"
                 style="color:{color};">
                {score:.0f}%
            </div>
            <div class="score-label">
                {status_emoji(label)} {label}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def show_metric_card(title, value):
    color = score_color(value)

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">{html.escape(title)}</div>
            <div class="metric-value" style="color:{color};">
                {value:.0f}%
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def calculate_overall(results):
    if not results:
        return 0

    return round(
        sum(
            r["overall"]
            for r in results
        ) / len(results),
        1
    )


def create_results_dataframe(results):
    rows = []

    for i, result in enumerate(
        results,
        start=1
    ):
        rows.append({
            "Question": f"Q{i}",
            "Type": result["type"],
            "CLO": result["clo"],
            "PLO": result["plo"],
            "Bloom": result["bloom"],
            "CLO Match": result["clo_score"],
            "PLO Match": result["plo_score"],
            "Relevance": result["relevance"],
            "Clarity": result["clarity"],
            "Measurability": result["measurability"],
            "Overall": result["overall"],
            "Status": result["status"]
        })

    return pd.DataFrame(rows)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header("🎓 OBE Alignment Checker")

    st.markdown(
        """
        **Simple workflow**

        1. Enter CLOs
        2. Enter PLOs
        3. Upload assessment
        4. Analyze
        5. Revise questions
        6. Move questions into **Attained**
        """
    )

    st.divider()

    st.markdown("### Score guide")

    st.markdown(
        """
        🟢 **75–100 — Attained**

        🟡 **50–74 — Review**

        🔴 **0–49 — Needs Revision**
        """
    )

    st.divider()

    st.caption(
        "The tool evaluates complete assessments and "
        "supports different question formats."
    )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🎓 OBE Assessment Alignment Checker</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">Analyze an assessment, make simple revisions, and improve alignment with CLOs and PLOs.</div>',
    unsafe_allow_html=True
)


# ============================================================
# COURSE / ASSESSMENT INFORMATION
# ============================================================

with st.expander(
    "📚 Assessment Information",
    expanded=True
):
    col1, col2, col3 = st.columns(3)

    with col1:
        course_name = st.text_input(
            "Course",
            placeholder="e.g., Chemistry"
        )

    with col2:
        assessment_name = st.text_input(
            "Assessment",
            placeholder="e.g., Midterm Examination"
        )

    with col3:
        instructor = st.text_input(
            "Instructor",
            placeholder="Optional"
        )


# ============================================================
# CLO / PLO INPUT
# ============================================================

col1, col2 = st.columns(2)

with col1:
    st.subheader("🎯 Course Learning Outcomes (CLOs)")

    clo_text = st.text_area(
        "Enter CLOs",
        height=180,
        placeholder=(
            "CLO1: Explain fundamental concepts of chemistry.\n"
            "CLO2: Apply chemical principles to solve problems.\n"
            "CLO3: Analyze experimental results."
        )
    )

with col2:
    st.subheader("🌐 Program Learning Outcomes (PLOs)")

    plo_text = st.text_area(
        "Enter PLOs",
        height=180,
        placeholder=(
            "PLO1: Apply knowledge to solve problems.\n"
            "PLO2: Communicate effectively.\n"
            "PLO3: Use analytical thinking."
        )
    )


# ============================================================
# FILE UPLOAD
# ============================================================

st.subheader("📄 Upload Complete Assessment")

uploaded_file = st.file_uploader(
    "Upload your assessment file",
    type=[
        "pdf",
        "docx",
        "pptx",
        "xlsx",
        "xls",
        "csv",
        "txt",
        "md",
        "svg",
        "png",
        "jpg",
        "jpeg",
        "webp",
        "bmp",
        "tiff"
    ]
)


# ============================================================
# READ FILE
# ============================================================

if uploaded_file is not None:

    if st.button(
        "📖 Read Assessment",
        type="primary",
        use_container_width=True
    ):
        with st.spinner("Reading assessment..."):
            text, error = read_uploaded_file(
                uploaded_file
            )

        if error:
            st.error(error)
        else:
            st.session_state.assessment_text = text
            st.session_state.analyzed = False
            st.session_state.results = []

            st.success(
                f"Assessment read successfully: {uploaded_file.name}"
            )

            if len(text.strip()) < 50:
                st.warning(
                    "Very little text was detected. "
                    "If this is a scanned document, OCR may be required."
                )


# ============================================================
# TEXT PREVIEW
# ============================================================

if st.session_state.assessment_text:

    with st.expander(
        "👁️ View Extracted Assessment Text",
        expanded=False
    ):
        st.text_area(
            "Extracted text",
            value=st.session_state.assessment_text,
            height=300,
            label_visibility="collapsed"
        )


# ============================================================
# ANALYZE
# ============================================================

if st.session_state.assessment_text:

    st.divider()

    if st.button(
        "🔍 Analyze Assessment",
        type="primary",
        use_container_width=True
    ):

        clos = parse_outcomes(
            clo_text,
            "CLO"
        )

        plos = parse_outcomes(
            plo_text,
            "PLO"
        )

        if not clos:
            st.error(
                "Please enter at least one CLO."
            )
            st.stop()

        if not plos:
            st.error(
                "Please enter at least one PLO."
            )
            st.stop()

        questions = split_question_blocks(
            st.session_state.assessment_text
        )

        if not questions:
            st.error(
                "No assessment questions could be identified."
            )
            st.stop()

        results = []

        for question in questions:
            results.append(
                evaluate_question(
                    question,
                    clos,
                    plos
                )
            )

        st.session_state.questions = questions
        st.session_state.results = results
        st.session_state.analyzed = True
        st.session_state.selected_question = 0

        st.rerun()


# ============================================================
# ANALYSIS RESULTS
# ============================================================

if (
    st.session_state.analyzed
    and st.session_state.results
):

    results = st.session_state.results

    overall_score = calculate_overall(
        results
    )

    attained_count = sum(
        1
        for r in results
        if r["status"] == "Attained"
    )

    review_count = sum(
        1
        for r in results
        if r["status"] == "Review"
    )

    revision_count = sum(
        1
        for r in results
        if r["status"] == "Needs Revision"
    )

    # --------------------------------------------------------
    # OVERALL SCORE
    # --------------------------------------------------------

    st.divider()

    st.subheader("📊 Overall Assessment Alignment")

    show_score_banner(
        overall_score
    )

    st.progress(
        min(
            1.0,
            max(
                0.0,
                overall_score / 100
            )
        )
    )

    # Celebrate overall attainment.
    previous_attained = st.session_state.last_attained_count

    if attained_count > previous_attained:
        st.balloons()

    st.session_state.last_attained_count = attained_count

    # --------------------------------------------------------
    # SIMPLE METRICS
    # --------------------------------------------------------

    avg_clo = round(
        sum(r["clo_score"] for r in results) /
        len(results),
        1
    )

    avg_plo = round(
        sum(r["plo_score"] for r in results) /
        len(results),
        1
    )

    avg_bloom = round(
        sum(r["bloom_score"] for r in results) /
        len(results),
        1
    )

    avg_relevance = round(
        sum(r["relevance"] for r in results) /
        len(results),
        1
    )

    avg_clarity = round(
        sum(r["clarity"] for r in results) /
        len(results),
        1
    )

    avg_measurability = round(
        sum(r["measurability"] for r in results) /
        len(results),
        1
    )

    metric_cols = st.columns(6)

    metrics = [
        ("CLO Match", avg_clo),
        ("PLO Match", avg_plo),
        ("Bloom", avg_bloom),
        ("Relevance", avg_relevance),
        ("Clarity", avg_clarity),
        ("Measurability", avg_measurability)
    ]

    for col, (title, value) in zip(
        metric_cols,
        metrics
    ):
        with col:
            show_metric_card(
                title,
                value
            )

    # --------------------------------------------------------
    # GRAPH
    # --------------------------------------------------------

    st.subheader("📈 Alignment Overview")

    graph_df = pd.DataFrame({
        "Metric": [
            "CLO Match",
            "PLO Match",
            "Bloom",
            "Relevance",
            "Clarity",
            "Measurability"
        ],
        "Score": [
            avg_clo,
            avg_plo,
            avg_bloom,
            avg_relevance,
            avg_clarity,
            avg_measurability
        ]
    })

    st.bar_chart(
        graph_df.set_index("Metric")
    )

    # --------------------------------------------------------
    # STATUS SUMMARY
    # --------------------------------------------------------

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "🟢 Attained",
            attained_count
        )

    with c2:
        st.metric(
            "🟡 Review",
            review_count
        )

    with c3:
        st.metric(
            "🔴 Needs Revision",
            revision_count
        )

    # ========================================================
    # ATTAINED SECTION
    # ========================================================

    st.divider()

    st.subheader("🏆 Attained Questions")

    attained_results = [
        (i, r)
        for i, r in enumerate(results)
        if r["status"] == "Attained"
    ]

    if attained_results:

        for index, result in attained_results:

            st.markdown(
                f"""
                <div class="attained-box">
                    <strong>🎉 Q{index + 1} — {result['overall']:.0f}%</strong>
                    <br>
                    <span class="question-text">
                    {html.escape(result['question'])}
                    </span>
                    <br><br>
                    <strong>CLO:</strong> {html.escape(result['clo'])}
                    &nbsp;&nbsp;
                    <strong>PLO:</strong> {html.escape(result['plo'])}
                    &nbsp;&nbsp;
                    <strong>Bloom:</strong> {html.escape(result['bloom'])}
                </div>
                """,
                unsafe_allow_html=True
            )

    else:
        st.info(
            "Questions that reach 75% or above will appear here. "
            "Revise a question below to move it into Attained."
        )

    # ========================================================
    # EASY REVISION AREA
    # ========================================================

    st.divider()

    st.subheader("✏️ Easy Assessment Revision")

    st.write(
        "Select a question that needs improvement. "
        "The tool will suggest revisions while preserving "
        "the original subject, concepts, numbers, and question type."
    )

    question_options = [
        f"Q{i + 1} — {r['overall']:.0f}% — {r['status']}"
        for i, r in enumerate(results)
    ]

    selected_label = st.selectbox(
        "Select a question to revise",
        question_options,
        index=min(
            st.session_state.selected_question,
            len(question_options) - 1
        )
    )

    selected_index = question_options.index(
        selected_label
    )

    st.session_state.selected_question = selected_index

    selected_result = results[selected_index]

    # --------------------------------------------------------
    # CURRENT QUESTION
    # --------------------------------------------------------

    current_class = (
        "attained-box"
        if selected_result["overall"] >= 75
        else (
            "review-box"
            if selected_result["overall"] >= 50
            else "needs-box"
        )
    )

    st.markdown(
        f"""
        <div class="{current_class}">
            <strong>
                Q{selected_index + 1}
                — {selected_result['overall']:.0f}%
                {status_emoji(selected_result['status'])}
            </strong>
            <br><br>
            <span class="question-text">
            {html.escape(selected_result['question'])}
            </span>
        </div>
        """,
        unsafe_allow_html=True
    )

    info_cols = st.columns(4)

    with info_cols[0]:
        st.metric(
            "CLO",
            selected_result["clo"]
        )

    with info_cols[1]:
        st.metric(
            "PLO",
            selected_result["plo"]
        )

    with info_cols[2]:
        st.metric(
            "Question Type",
            selected_result["type"]
        )

    with info_cols[3]:
        st.metric(
            "Bloom",
            selected_result["bloom"]
        )

    # --------------------------------------------------------
    # CLO / PLO DETAILS
    # --------------------------------------------------------

    with st.expander(
        "🎯 View Current CLO and PLO Mapping"
    ):

        st.write(
            f"**{selected_result['clo']}:** "
            f"{selected_result['clo_description']}"
        )

        st.write(
            f"**{selected_result['plo']}:** "
            f"{selected_result['plo_description']}"
        )

    # --------------------------------------------------------
    # GENERATE REVISIONS
    # --------------------------------------------------------

    if st.button(
        "✨ Suggest Simple Revisions",
        type="primary",
        use_container_width=True
    ):

        clos = parse_outcomes(
            clo_text,
            "CLO"
        )

        plos = parse_outcomes(
            plo_text,
            "PLO"
        )

        suggestions, old_result = generate_revisions(
            selected_result["question"],
            clos,
            plos
        )

        st.session_state[
            f"suggestions_{selected_index}"
        ] = suggestions

        st.session_state[
            f"suggestion_base_{selected_index}"
        ] = old_result

    suggestions = st.session_state.get(
        f"suggestions_{selected_index}",
        []
    )

    # --------------------------------------------------------
    # SHOW SUGGESTIONS
    # --------------------------------------------------------

    if suggestions:

        st.markdown("### ✨ Suggested Revisions")

        st.caption(
            "These suggestions are generated from the original "
            "question. The tool does not replace the subject "
            "with an unrelated topic."
        )

        for suggestion_index, suggestion in enumerate(
            suggestions
        ):

            new_result = suggestion["result"]
            old_score = selected_result["overall"]
            new_score = new_result["overall"]
            gain = round(
                new_score - old_score,
                1
            )

            st.markdown(
                f"""
                <div class="revision-box">
                    <strong>
                        Suggested Revision {suggestion_index + 1}
                    </strong>
                    <br><br>

                    <span class="question-text">
                    {html.escape(suggestion['text'])}
                    </span>

                    <br><br>

                    <strong>Predicted score:</strong>
                    {old_score:.0f}% →
                    <span style="color:#188038;font-weight:800;">
                    {new_score:.0f}%
                    </span>

                    &nbsp;&nbsp;

                    <strong>Improvement:</strong>
                    <span style="color:#188038;font-weight:800;">
                    +{gain:.0f}%
                    </span>

                    <br>

                    <span class="small-note">
                    {html.escape(suggestion['reason'])}
                    </span>
                </div>
                """,
                unsafe_allow_html=True
            )

            button_key = (
                f"use_revision_"
                f"{selected_index}_"
                f"{suggestion_index}_"
                f"{st.session_state.revision_version}"
            )

            if st.button(
                f"✅ Use Revision {suggestion_index + 1}",
                key=button_key,
                use_container_width=True
            ):

                # Replace the question.
                st.session_state.questions[
                    selected_index
                ] = suggestion["text"]

                # Recalculate the entire assessment.
                clos = parse_outcomes(
                    clo_text,
                    "CLO"
                )

                plos = parse_outcomes(
                    plo_text,
                    "PLO"
                )

                updated_results = []

                for q in st.session_state.questions:
                    updated_results.append(
                        evaluate_question(
                            q,
                            clos,
                            plos
                        )
                    )

                old_overall = calculate_overall(
                    st.session_state.results
                )

                new_overall = calculate_overall(
                    updated_results
                )

                old_status = (
                    st.session_state.results[
                        selected_index
                    ]["status"]
                )

                new_status = (
                    updated_results[
                        selected_index
                    ]["status"]
                )

                st.session_state.results = (
                    updated_results
                )

                st.session_state.revision_version += 1

                # Clear suggestions for this question.
                st.session_state.pop(
                    f"suggestions_{selected_index}",
                    None
                )

                st.session_state.pop(
                    f"suggestion_base_{selected_index}",
                    None
                )

                # Celebration when the individual question
                # reaches Attained.
                if (
                    old_status != "Attained"
                    and new_status == "Attained"
                ):
                    st.balloons()

                    st.success(
                        f"🎉 Excellent! Q{selected_index + 1} "
                        f"has reached the Attained level."
                    )

                # Celebration if overall assessment reaches Attained.
                if (
                    old_overall < 75
                    and new_overall >= 75
                ):
                    st.balloons()

                    st.success(
                        "🎉 Congratulations! "
                        "The overall assessment has reached "
                        "the Attained level."
                    )

                st.rerun()

    elif selected_result["overall"] >= 75:

        st.success(
            "🎉 This question is already Attained. "
            "No revision is necessary."
        )

    else:

        st.info(
            "Click **Suggest Simple Revisions** to receive "
            "topic-preserving revision options."
        )

    # ========================================================
    # ALL QUESTIONS
    # ========================================================

    st.divider()

    st.subheader("📋 Assessment Overview")

    overview_df = create_results_dataframe(
        st.session_state.results
    )

    st.dataframe(
        overview_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # QUESTION TYPE DISTRIBUTION
    # ========================================================

    st.subheader("📚 Question Type Distribution")

    type_counts = pd.Series(
        [
            r["type"]
            for r in st.session_state.results
        ]
    ).value_counts()

    if not type_counts.empty:
        st.bar_chart(type_counts)

    # ========================================================
    # CLO MAPPING
    # ========================================================

    st.subheader("🎯 CLO Mapping")

    clo_counts = {}

    for result in st.session_state.results:
        clo = result["clo"]

        if clo not in clo_counts:
            clo_counts[clo] = 0

        clo_counts[clo] += 1

    if clo_counts:
        clo_df = pd.DataFrame(
            {
                "CLO": list(clo_counts.keys()),
                "Questions": list(
                    clo_counts.values()
                )
            }
        )

        st.bar_chart(
            clo_df.set_index("CLO")
        )

    # ========================================================
    # PLO MAPPING
    # ========================================================

    st.subheader("🌐 PLO Mapping")

    plo_counts = {}

    for result in st.session_state.results:
        plo = result["plo"]

        if plo not in plo_counts:
            plo_counts[plo] = 0

        plo_counts[plo] += 1

    if plo_counts:
        plo_df = pd.DataFrame(
            {
                "PLO": list(plo_counts.keys()),
                "Questions": list(
                    plo_counts.values()
                )
            }
        )

        st.bar_chart(
            plo_df.set_index("PLO")
        )

    # ========================================================
    # BLOOM DISTRIBUTION
    # ========================================================

    st.subheader("🧠 Bloom Level Distribution")

    bloom_counts = pd.Series(
        [
            r["bloom"]
            for r in st.session_state.results
        ]
    ).value_counts()

    if not bloom_counts.empty:
        st.bar_chart(bloom_counts)

    # ========================================================
    # SUMMARY
    # ========================================================

    st.divider()

    st.subheader("📝 Simple Summary")

    if overall_score >= 75:
        st.success(
            "🎉 The assessment has reached the Attained level. "
            "Most alignment areas are sufficiently addressed."
        )

    elif overall_score >= 50:
        st.warning(
            "The assessment is in the Review range. "
            "Use the revision assistant to improve questions "
            "that need attention."
        )

    else:
        st.error(
            "The assessment needs revision. "
            "Start with the lowest-scoring questions."
        )

    # ========================================================
    # LOWEST QUESTIONS
    # ========================================================

    st.subheader("🔧 Questions to Review First")

    sorted_results = sorted(
        enumerate(
            st.session_state.results
        ),
        key=lambda x: x[1]["overall"]
    )

    for index, result in sorted_results[:5]:

        if result["overall"] >= 75:
            continue

        st.markdown(
            f"""
            **Q{index + 1} — {result['overall']:.0f}%**
            {status_emoji(result['status'])}

            {result['question']}
            """
        )

    # ========================================================
    # EXPORT
    # ========================================================

    st.divider()

    st.subheader("📥 Export Results")

    export_df = create_results_dataframe(
        st.session_state.results
    )

    csv_data = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Alignment Report",
        data=csv_data,
        file_name="OBE_Assessment_Alignment_Report.csv",
        mime="text/csv",
        use_container_width=True
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "🎓 OBE Assessment Alignment Checker | "
    "Simple assessment review and revision"
)
