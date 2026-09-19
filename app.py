import streamlit as st
import pandas as pd
import re
import io
import os
import math
from collections import Counter

# ============================================================
# OBE QUIZ CHECKER
# Complete replacement app.py
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Checker",
    page_icon="🎓",
    layout="wide"
)

# ============================================================
# OPTIONAL IMPORTS
# ============================================================

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    from docx import Document
except Exception:
    Document = None

try:
    from pptx import Presentation
except Exception:
    Presentation = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import pytesseract
except Exception:
    pytesseract = None

# ============================================================
# CONSTANTS
# ============================================================

ATTAINMENT = 75

STOP_WORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on",
    "for", "from", "with", "by", "is", "are", "was", "were",
    "be", "been", "being", "this", "that", "these", "those",
    "as", "at", "it", "its", "their", "them", "they", "you",
    "your", "into", "through", "using", "use", "used",
    "students", "student", "course", "learners", "learner",
    "will", "can", "should", "may", "must"
}

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
        "define", "identify", "list", "name", "state", "recall",
        "recognize", "label", "mention", "select", "match"
    ],
    "Understand": [
        "describe", "explain", "summarize", "interpret",
        "classify", "discuss", "illustrate", "compare",
        "paraphrase", "outline"
    ],
    "Apply": [
        "calculate", "solve", "apply", "demonstrate", "use",
        "implement", "execute", "compute", "perform",
        "construct", "show"
    ],
    "Analyze": [
        "analyze", "analyse", "differentiate", "examine",
        "investigate", "contrast", "distinguish", "break down",
        "categorize", "deconstruct"
    ],
    "Evaluate": [
        "evaluate", "justify", "assess", "critique", "judge",
        "defend", "recommend", "appraise", "argue"
    ],
    "Create": [
        "create", "design", "develop", "formulate", "produce",
        "construct", "propose", "generate", "plan", "design"
    ]
}

QUESTION_STARTERS = [
    "what", "why", "how", "when", "where", "which", "who",
    "define", "describe", "explain", "discuss", "identify",
    "calculate", "solve", "analyze", "analyse", "evaluate",
    "compare", "contrast", "justify", "design", "develop",
    "create", "state", "list", "mention", "give", "write",
    "derive", "prove", "demonstrate", "apply", "interpret",
    "examine", "assess", "recommend", "classify", "differentiate"
]

FORBIDDEN_REVISION_PHRASES = [
    "clo",
    "plo",
    "learning outcome",
    "course learning outcome",
    "program learning outcome",
    "course outcome",
    "according to the clo",
    "according to the plo",
    "according to the learning outcome",
    "as stated in the clo",
    "as stated in the plo",
    "as stated in the learning outcome",
    "using the learning outcome",
    "based on the learning outcome",
    "in line with the clo",
    "in line with the plo"
]

# ============================================================
# BASIC TEXT HELPERS
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)

    text = text.replace("\x00", " ")
    text = text.replace("\uf0b7", "•")
    text = text.replace("\u00a0", " ")
    text = text.replace("\u2013", "-")
    text = text.replace("\u2014", "-")
    text = text.replace("\u2018", "'")
    text = text.replace("\u2019", "'")
    text = text.replace("\u201c", '"')
    text = text.replace("\u201d", '"')

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def word_set(text):
    words = normalize(text).split()

    result = set()

    for word in words:
        if len(word) <= 2:
            continue
        if word in STOP_WORDS:
            continue

        # Lightweight normalization
        if word.endswith("ies") and len(word) > 4:
            word = word[:-3] + "y"
        elif word.endswith("ing") and len(word) > 5:
            word = word[:-3]
        elif word.endswith("ed") and len(word) > 4:
            word = word[:-2]
        elif word.endswith("s") and len(word) > 4:
            word = word[:-1]

        result.add(word)

    return result


def numbers(text):
    return re.findall(
        r"\b\d+(?:\.\d+)?\b",
        clean_text(text)
    )


def safe_float(value, default=0):
    try:
        return float(value)
    except Exception:
        return default


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text):
    if not text:
        return []

    lines = re.split(r"[\n;]+", text)
    outcomes = []

    for line in lines:
        line = clean_text(line)

        if not line:
            continue

        line = re.sub(
            r"^(?:CLO|PLO|CO|PO)\s*[-_:]?\s*\d*\s*[:.)-]?\s*",
            "",
            line,
            flags=re.I
        )

        line = re.sub(
            r"^\d+\s*[\).:-]\s*",
            "",
            line
        )

        line = clean_text(line)

        if len(line) >= 8:
            outcomes.append(line)

    # Remove duplicates
    final = []
    seen = set()

    for item in outcomes:
        key = normalize(item)

        if key and key not in seen:
            seen.add(key)
            final.append(item)

    return final


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(text):
    normalized = normalize(text)

    # Prefer verbs appearing early
    first_words = normalized.split()[:15]

    for level in BLOOM_LEVELS:
        for verb in BLOOM_VERBS[level]:
            if verb in first_words:
                return level

    for level in BLOOM_LEVELS:
        for verb in BLOOM_VERBS[level]:
            if re.search(r"\b" + re.escape(verb) + r"\b", normalized):
                return level

    return "Understand"


def bloom_index(level):
    try:
        return BLOOM_LEVELS.index(level)
    except Exception:
        return 1


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def split_numbered_questions(text):
    """
    Handles:
    Q1.
    Q1)
    Question 1:
    1.
    1)
    1:
    01.
    """

    text = clean_text(text)

    pattern = re.compile(
        r"(?im)(?=(?:^|\n)\s*"
        r"(?:question\s*)?"
        r"(?:q\s*)?"
        r"\d{1,3}"
        r"\s*[\.\):\-])"
    )

    parts = pattern.split(text)

    questions = []

    for part in parts:
        part = clean_text(part)

        part = re.sub(
            r"^(?:question\s*)?(?:q\s*)?\d{1,3}\s*[\.\):\-]\s*",
            "",
            part,
            flags=re.I
        )

        if len(part) < 12:
            continue

        questions.append(part)

    return questions


def split_inline_numbered_questions(text):
    """
    Handles PDF text where questions are placed on the same line:

    1. What is X? 2. Explain Y? 3. Calculate Z.
    """

    pattern = re.compile(
        r"(?:^|\s)"
        r"(?=(?:question\s*)?(?:q\s*)?\d{1,3}\s*[\.\):\-]\s+)",
        re.I
    )

    pieces = pattern.split(text)

    results = []

    for piece in pieces:
        piece = clean_text(piece)

        piece = re.sub(
            r"^(?:question\s*)?(?:q\s*)?\d{1,3}\s*[\.\):\-]\s*",
            "",
            piece,
            flags=re.I
        )

        if len(piece) >= 12:
            results.append(piece)

    return results


def split_question_marks(text):
    """
    Splits text around actual question marks.
    """

    results = []

    for sentence in re.split(r"(?<=[?])\s+", clean_text(text)):
        sentence = clean_text(sentence)

        if len(sentence) < 12:
            continue

        if "?" in sentence:
            results.append(sentence)

    return results


def split_by_lines(text):
    results = []

    lines = clean_text(text).splitlines()

    buffer = ""

    for raw in lines:
        line = clean_text(raw)

        if not line:
            continue

        lower = normalize(line)

        is_question_like = (
            "?" in line
            or any(
                lower.startswith(v + " ")
                or lower == v
                for v in QUESTION_STARTERS
            )
        )

        if is_question_like:
            if buffer:
                results.append(clean_text(buffer))
                buffer = ""

            results.append(line)

        else:
            if buffer:
                buffer += " " + line
            else:
                buffer = line

    if buffer:
        results.append(clean_text(buffer))

    return results


def extract_question_sentences(text):
    candidates = []

    candidates.extend(split_numbered_questions(text))
    candidates.extend(split_inline_numbered_questions(text))

    if not candidates:
        candidates.extend(split_question_marks(text))

    if not candidates:
        candidates.extend(split_by_lines(text))

    cleaned = []

    for item in candidates:
        item = clean_text(item)

        if len(item) < 12:
            continue

        # Remove obvious headers
        if normalize(item) in {
            "assessment",
            "quiz",
            "questions",
            "quiz questions",
            "assignment",
            "assignment questions",
            "instructions",
            "instructions:"
        }:
            continue

        cleaned.append(item)

    return cleaned


def looks_like_question(text):
    t = normalize(text)

    if len(t) < 12:
        return False

    if "?" in text:
        return True

    if re.match(
        r"^(what|why|how|when|where|which|who)\b",
        t
    ):
        return True

    for level in BLOOM_LEVELS:
        for verb in BLOOM_VERBS[level]:
            if re.match(r"^" + re.escape(verb) + r"\b", t):
                return True

    return False


def extract_questions(text):
    """
    Main robust extraction function.

    It deliberately uses several fallback methods so that
    imperfect PDFs, Word files, copied text, and scanned files
    do not immediately produce zero questions.
    """

    text = clean_text(text)

    if not text:
        return []

    candidates = extract_question_sentences(text)

    final = []

    for candidate in candidates:

        # Remove page markers
        candidate = re.sub(
            r"---\s*PAGE\s*\d+\s*---",
            "",
            candidate,
            flags=re.I
        )

        candidate = clean_text(candidate)

        if len(candidate) < 12:
            continue

        # Remove instruction-like headings
        if re.match(
            r"^(instructions?|section|part|quiz|assessment)\s*[:\-]",
            candidate,
            flags=re.I
        ):
            continue

        final.append(candidate)

    # If the normal methods found nothing, use paragraph fallback
    if not final:

        paragraphs = re.split(r"\n\s*\n", text)

        for paragraph in paragraphs:
            paragraph = clean_text(paragraph)

            if len(paragraph) >= 15:
                final.append(paragraph)

    # If still nothing, use non-empty lines
    if not final:

        for line in text.splitlines():
            line = clean_text(line)

            if len(line) >= 15:
                final.append(line)

    # Merge obvious option-only lines with previous question
    merged = []

    for item in final:

        if re.match(
            r"^[A-Da-d][\)\.\:]\s+",
            item
        ):
            if merged:
                merged[-1] += "\n" + item
            continue

        merged.append(item)

    # Remove duplicates
    unique = []
    seen = set()

    for item in merged:
        key = normalize(item)

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    # Remove overly long page-like blocks if we have better questions
    question_like = [
        q for q in unique
        if looks_like_question(q)
    ]

    if len(question_like) >= 1:
        return question_like

    return unique


# ============================================================
# FILE READERS
# ============================================================

def read_pdf(uploaded_file):
    if fitz is None:
        raise RuntimeError(
            "PyMuPDF is not installed. Add PyMuPDF to requirements.txt."
        )

    data = uploaded_file.getvalue()

    document = fitz.open(
        stream=data,
        filetype="pdf"
    )

    pages = []

    for page_number, page in enumerate(document, start=1):

        text = page.get_text(
            "text",
            sort=True
        )

        text = clean_text(text)

        # OCR when text extraction is empty OR suspiciously short
        use_ocr = (
            len(text) < 25
            and pytesseract is not None
            and Image is not None
        )

        if use_ocr:
            try:
                pix = page.get_pixmap(
                    matrix=fitz.Matrix(2.5, 2.5),
                    alpha=False
                )

                image = Image.open(
                    io.BytesIO(
                        pix.tobytes("png")
                    )
                )

                ocr_text = pytesseract.image_to_string(
                    image
                )

                ocr_text = clean_text(ocr_text)

                if len(ocr_text) > len(text):
                    text = ocr_text

            except Exception:
                pass

        if text:
            pages.append(
                f"\n--- PAGE {page_number} ---\n{text}"
            )

    document.close()

    return clean_text("\n".join(pages))


def read_docx(uploaded_file):
    if Document is None:
        raise RuntimeError(
            "python-docx is not installed."
        )

    document = Document(
        io.BytesIO(uploaded_file.getvalue())
    )

    parts = []

    for paragraph in document.paragraphs:
        text = clean_text(paragraph.text)

        if text:
            parts.append(text)

    for table in document.tables:
        for row in table.rows:
            values = []

            for cell in row.cells:
                value = clean_text(cell.text)

                if value:
                    values.append(value)

            if values:
                parts.append(" | ".join(values))

    return clean_text("\n".join(parts))


def read_pptx(uploaded_file):
    if Presentation is None:
        raise RuntimeError(
            "python-pptx is not installed."
        )

    presentation = Presentation(
        io.BytesIO(uploaded_file.getvalue())
    )

    parts = []

    for slide_number, slide in enumerate(
        presentation.slides,
        start=1
    ):
        parts.append(
            f"--- SLIDE {slide_number} ---"
        )

        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text = clean_text(shape.text)

                if text:
                    parts.append(text)

    return clean_text("\n".join(parts))


def read_excel(uploaded_file):
    data = uploaded_file.getvalue()

    workbook = pd.ExcelFile(
        io.BytesIO(data)
    )

    parts = []

    for sheet in workbook.sheet_names:

        try:
            df = pd.read_excel(
                io.BytesIO(data),
                sheet_name=sheet,
                header=None
            )

            parts.append(
                f"--- SHEET {sheet} ---"
            )

            for row in df.fillna("").astype(str).values:
                values = [
                    clean_text(x)
                    for x in row
                    if clean_text(x)
                ]

                if values:
                    parts.append(
                        " | ".join(values)
                    )

        except Exception:
            continue

    return clean_text("\n".join(parts))


def read_csv(uploaded_file):
    data = uploaded_file.getvalue()

    try:
        df = pd.read_csv(
            io.BytesIO(data),
            header=None
        )
    except Exception:
        df = pd.read_csv(
            io.BytesIO(data),
            header=None,
            encoding="latin-1"
        )

    parts = []

    for row in df.fillna("").astype(str).values:
        values = [
            clean_text(x)
            for x in row
            if clean_text(x)
        ]

        if values:
            parts.append(
                " | ".join(values)
            )

    return clean_text("\n".join(parts))


def read_image(uploaded_file):
    if Image is None:
        raise RuntimeError(
            "Pillow is not installed."
        )

    if pytesseract is None:
        raise RuntimeError(
            "pytesseract is not installed."
        )

    image = Image.open(
        io.BytesIO(
            uploaded_file.getvalue()
        )
    )

    text = pytesseract.image_to_string(
        image
    )

    return clean_text(text)


def read_text_file(uploaded_file):
    data = uploaded_file.getvalue()

    try:
        return clean_text(
            data.decode("utf-8")
        )
    except Exception:
        return clean_text(
            data.decode("latin-1")
        )


def read_uploaded_file(uploaded_file):
    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        return read_pdf(uploaded_file)

    if name.endswith(".docx"):
        return read_docx(uploaded_file)

    if name.endswith(".pptx"):
        return read_pptx(uploaded_file)

    if name.endswith(".xlsx") or name.endswith(".xls"):
        return read_excel(uploaded_file)

    if name.endswith(".csv"):
        return read_csv(uploaded_file)

    if name.endswith(
        (
            ".txt",
            ".md",
            ".text"
        )
    ):
        return read_text_file(uploaded_file)

    if name.endswith(
        (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".bmp",
            ".tif",
            ".tiff"
        )
    ):
        return read_image(uploaded_file)

    raise ValueError(
        "Unsupported file format."
    )


# ============================================================
# MCQ / QUESTION TYPE DETECTION
# ============================================================

def question_type(question):
    q = clean_text(question)

    # MCQ
    option_matches = re.findall(
        r"(?im)(?:^|\n|\s)([A-Da-d])[\)\.\:]\s+([^\n]+)",
        q
    )

    if len(option_matches) >= 2:
        return "MCQ"

    # True / False
    if re.search(
        r"\btrue\s*/\s*false\b",
        q,
        flags=re.I
    ):
        return "True / False"

    if re.search(
        r"\b(true|false)\s*$",
        q,
        flags=re.I
    ):
        return "True / False"

    # Fill in blank
    if "_" in q or "fill in the blank" in q.lower():
        return "Fill in the Blank"

    # Numerical
    if re.search(
        r"\b(calculate|compute|solve|derive)\b",
        q,
        flags=re.I
    ):
        if re.search(
            r"\d",
            q
        ):
            return "Numerical / Problem Solving"

    # Case study
    if re.search(
        r"\b(case study|scenario|case)\b",
        q,
        flags=re.I
    ):
        return "Case Study / Application"

    # Essay
    if len(q.split()) > 45:
        return "Essay / Long Answer"

    return "Short Answer"


def extract_mcq_options(question):
    lines = question.splitlines()

    options = []

    for line in lines:
        line = clean_text(line)

        if re.match(
            r"^[A-Da-d][\)\.\:]\s+",
            line
        ):
            options.append(line)

    # Inline options
    if len(options) < 2:
        inline = re.findall(
            r"(?:^|\s)([A-Da-d])[\)\.\:]\s+([^A-Da-d]+?)(?=\s+[A-Da-d][\)\.\:]\s+|$)",
            question
        )

        for letter, text in inline:
            item = f"{letter}) {clean_text(text)}"

            if item not in options:
                options.append(item)

    return options


def question_stem(question):
    lines = question.splitlines()

    stem_lines = []

    for line in lines:

        if re.match(
            r"^[A-Da-d][\)\.\:]\s+",
            clean_text(line)
        ):
            continue

        stem_lines.append(line)

    return clean_text(
        "\n".join(stem_lines)
    )


# ============================================================
# SEMANTIC MATCHING
# ============================================================

def semantic_match(question, outcome):
    q_words = word_set(question)
    o_words = word_set(outcome)

    if not q_words or not o_words:
        return 55

    overlap = q_words.intersection(o_words)

    ratio_q = len(overlap) / max(
        len(q_words),
        1
    )

    ratio_o = len(overlap) / max(
        len(o_words),
        1
    )

    combined = (
        0.45 * ratio_q
        + 0.55 * ratio_o
    )

    # Phrase overlap bonus
    q_norm = normalize(question)
    o_norm = normalize(outcome)

    phrase_bonus = 0

    outcome_tokens = normalize(outcome).split()

    for n in [3, 2]:
        for i in range(
            max(0, len(outcome_tokens) - n + 1)
        ):
            phrase = " ".join(
                outcome_tokens[i:i+n]
            )

            if len(phrase) >= 8 and phrase in q_norm:
                phrase_bonus += 0.06

    combined = min(
        1.0,
        combined + phrase_bonus
    )

    if combined >= 0.70:
        return 95

    if combined >= 0.50:
        return 88

    if combined >= 0.35:
        return 78

    if combined >= 0.20:
        return 68

    if combined > 0:
        return 60

    return 55


# ============================================================
# OUTCOME CONTENT EXTRACTION
# ============================================================

def outcome_content(outcome):
    outcome = clean_text(outcome)

    if not outcome:
        return ""

    words = outcome.split()

    if not words:
        return outcome

    first = words[0].lower().strip(
        ".,:;()-"
    )

    for level in BLOOM_LEVELS:
        verbs = BLOOM_VERBS[level]

        if first in verbs:
            return clean_text(
                " ".join(words[1:])
            )

    return outcome


def extract_content_phrases(outcome):
    """
    Extracts meaningful content after the Bloom/action verb.
    """

    content = outcome_content(outcome)

    if not content:
        return []

    # Split major clauses
    pieces = re.split(
        r"\s+(?:and|or|including|such as|by|through)\s+",
        content,
        flags=re.I
    )

    cleaned = []

    for piece in pieces:
        piece = clean_text(piece)

        if len(piece) >= 4:
            cleaned.append(piece)

    return cleaned


# ============================================================
# METRIC CALCULATIONS
# ============================================================

def outcome_score(question, outcome):
    return semantic_match(
        question,
        outcome
    )


def bloom_score(question, target_bloom):
    q_bloom = detect_bloom(question)

    q_index = bloom_index(q_bloom)
    target_index = bloom_index(target_bloom)

    distance = abs(
        q_index - target_index
    )

    if distance == 0:
        return 100

    if distance == 1:
        return 92

    if distance == 2:
        return 84

    if distance == 3:
        return 78

    return 72


def clarity_score(question):
    score = 98

    words = question.split()

    if len(words) > 60:
        score -= 6
    elif len(words) > 45:
        score -= 3

    if question.count("?") > 1:
        score -= 2

    if re.search(
        r"\b(etc|and so on)\b",
        question,
        flags=re.I
    ):
        score -= 3

    if re.search(
        r"\b(thing|things|stuff)\b",
        question,
        flags=re.I
    ):
        score -= 4

    if question.count("(") != question.count(")"):
        score -= 2

    return max(
        60,
        min(100, score)
    )


def measurability_score(question):
    score = 94

    q = normalize(question)

    measurable_verbs = set()

    for values in BLOOM_VERBS.values():
        measurable_verbs.update(values)

    if any(
        re.search(
            r"\b" + re.escape(v) + r"\b",
            q
        )
        for v in measurable_verbs
    ):
        score += 4

    if "discuss" in q:
        score -= 1

    if "comment" in q:
        score -= 2

    if "think about" in q:
        score -= 4

    if "your thoughts" in q:
        score -= 4

    return max(
        70,
        min(100, score)
    )


def relevance_score(question, best_clo, best_plo):
    values = []

    if best_clo:
        values.append(
            semantic_match(
                question,
                best_clo
            )
        )

    if best_plo:
        values.append(
            semantic_match(
                question,
                best_plo
            )
        )

    if not values:
        return 80

    return round(
        sum(values) / len(values)
    )


def best_outcome(question, outcomes):
    if not outcomes:
        return "", 80

    scores = []

    for outcome in outcomes:
        score = semantic_match(
            question,
            outcome
        )

        scores.append(
            (score, outcome)
        )

    scores.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return scores[0][1], scores[0][0]


def evaluate(
    question,
    clos,
    plos,
    target_bloom
):
    best_clo, clo_score = best_outcome(
        question,
        clos
    )

    best_plo, plo_score = best_outcome(
        question,
        plos
    )

    bloom = bloom_score(
        question,
        target_bloom
    )

    relevance = relevance_score(
        question,
        best_clo,
        best_plo
    )

    clarity = clarity_score(
        question
    )

    measurability = measurability_score(
        question
    )

    overall = (
        clo_score * 0.20
        + plo_score * 0.15
        + bloom * 0.20
        + relevance * 0.15
        + clarity * 0.15
        + measurability * 0.15
    )

    return {
        "CLO Match": round(clo_score),
        "PLO Match": round(plo_score),
        "Bloom": round(bloom),
        "Relevance": round(relevance),
        "Clarity": round(clarity),
        "Measurability": round(measurability),
        "Overall": round(overall),
        "Best CLO": best_clo,
        "Best PLO": best_plo,
        "Detected Bloom": detect_bloom(question),
        "Question Type": question_type(question)
    }


def status(score):
    if score >= 85:
        return "Strong"
    if score >= 75:
        return "Attained"
    if score >= 65:
        return "Minor Revision"
    if score >= 50:
        return "Review"
    return "Needs Revision"


# ============================================================
# PROBLEM IDENTIFICATION
# ============================================================

def identify_problems(result):
    problems = []

    if result["CLO Match"] < ATTAINMENT:
        problems.append(
            "The question does not adequately address the selected CLO."
        )

    if result["PLO Match"] < ATTAINMENT:
        problems.append(
            "The question does not adequately support the selected PLO."
        )

    if result["Bloom"] < ATTAINMENT:
        problems.append(
            f"The question is not sufficiently aligned with the target Bloom's level "
            f"({result['Detected Bloom']} detected)."
        )

    if result["Relevance"] < ATTAINMENT:
        problems.append(
            "The question has weak alignment with the intended learning content."
        )

    if result["Clarity"] < ATTAINMENT:
        problems.append(
            "The wording can be made clearer and more precise."
        )

    if result["Measurability"] < ATTAINMENT:
        problems.append(
            "The task is not sufficiently observable or measurable."
        )

    if not problems:
        problems.append(
            "No major alignment problem was detected."
        )

    return problems


def revision_focus(result):
    focus = []

    if result["CLO Match"] < ATTAINMENT:
        focus.append("CLO content")

    if result["PLO Match"] < ATTAINMENT:
        focus.append("PLO-related content")

    if result["Bloom"] < ATTAINMENT:
        focus.append("Bloom's cognitive demand")

    if result["Clarity"] < ATTAINMENT:
        focus.append("clarity")

    if result["Measurability"] < ATTAINMENT:
        focus.append("measurability")

    if not focus:
        return "No revision required"

    return ", ".join(focus)


# ============================================================
# REVISION ENGINE
# ============================================================

def preserve_numbers(original, revised):
    return numbers(original) == numbers(revised)


def forbidden_revision_language(text):
    normalized = normalize(text)

    for phrase in FORBIDDEN_REVISION_PHRASES:
        if phrase in normalized:
            return True

    return False


def preserve_mcq_options(original, revised):
    original_options = extract_mcq_options(
        original
    )

    revised_options = extract_mcq_options(
        revised
    )

    if not original_options:
        return True

    if not revised_options:
        return False

    return (
        [
            normalize(x)
            for x in original_options
        ]
        ==
        [
            normalize(x)
            for x in revised_options
        ]
    )


def revise_short_answer(
    original,
    clo,
    plo,
    target_bloom
):
    content = outcome_content(clo)

    if not content:
        content = outcome_content(plo)

    if not content:
        return original

    original_stem = question_stem(
        original
    )

    # Direct transformation by Bloom
    if target_bloom == "Remember":
        return (
            f"Identify and state the key "
            f"points about {content}."
        )

    if target_bloom == "Understand":
        return (
            f"Explain {content}."
        )

    if target_bloom == "Apply":
        return (
            f"Apply the relevant principles of "
            f"{content} to the given problem or situation."
        )

    if target_bloom == "Analyze":
        return (
            f"Analyze {content}."
        )

    if target_bloom == "Evaluate":
        return (
            f"Evaluate {content} and justify your conclusion."
        )

    if target_bloom == "Create":
        return (
            f"Design or develop an appropriate solution "
            f"for {content}."
        )

    return original_stem


def revise_case_study(
    original,
    clo,
    target_bloom
):
    content = outcome_content(clo)

    if not content:
        return original

    original_stem = question_stem(
        original
    )

    if target_bloom == "Analyze":
        task = (
            f"Analyze the case and identify the main issues "
            f"related to {content}."
        )

    elif target_bloom == "Evaluate":
        task = (
            f"Evaluate the case in relation to {content} "
            f"and justify your conclusion."
        )

    elif target_bloom == "Apply":
        task = (
            f"Apply the relevant principles of {content} "
            f"to the case and determine an appropriate response."
        )

    else:
        task = (
            f"Using the case information, explain {content}."
        )

    # Preserve the original scenario where possible
    if len(original_stem.split()) > 10:
        return (
            original_stem.rstrip(".? ")
            + ". "
            + task
        )

    return task


def revise_numerical(
    original,
    clo,
    target_bloom
):
    content = outcome_content(clo)

    if not content:
        return original

    stem = question_stem(
        original
    )

    # Keep the original problem exactly and improve the required action.
    if target_bloom in [
        "Apply",
        "Analyze",
        "Evaluate"
    ]:
        addition = (
            f" Show the calculation steps and explain the result "
            f"using the relevant principles of {content}."
        )
    else:
        addition = (
            f" Show the calculation steps and state the final answer "
            f"with the appropriate unit."
        )

    if addition.strip() in stem:
        return original

    return stem.rstrip(".? ") + "." + addition


def revise_true_false(
    original,
    clo,
    target_bloom
):
    content = outcome_content(clo)

    if not content:
        return original

    return (
        f"True or False: {content}."
    )


def revise_fill_blank(
    original,
    clo
):
    content = outcome_content(clo)

    if not content:
        return original

    # Preserve the blank if present
    if "_" in original:
        prefix = original.split("_")[0].strip()

        if prefix:
            return (
                prefix.rstrip(":.? ")
                + ": ________."
            )

    return (
        f"Complete the statement: {content}: ________."
    )


def revise_mcq(
    original,
    clo,
    target_bloom
):
    options = extract_mcq_options(
        original
    )

    stem = question_stem(
        original
    )

    content = outcome_content(clo)

    if not content:
        return original

    if target_bloom == "Remember":
        new_stem = (
            f"Which statement correctly identifies "
            f"{content}?"
        )

    elif target_bloom == "Understand":
        new_stem = (
            f"Which statement best explains {content}?"
        )

    elif target_bloom == "Apply":
        new_stem = (
            f"Which option correctly applies the relevant "
            f"principles of {content}?"
        )

    elif target_bloom == "Analyze":
        new_stem = (
            f"Which option best analyzes {content}?"
        )

    elif target_bloom == "Evaluate":
        new_stem = (
            f"Which option provides the most appropriate "
            f"evaluation of {content}?"
        )

    else:
        new_stem = (
            f"Which option represents an appropriate solution "
            f"for {content}?"
        )

    if options:
        return new_stem + "\n" + "\n".join(
            options
        )

    return new_stem


def create_revision(
    original,
    result,
    clos,
    plos,
    target_bloom
):
    """
    Creates a direct student-facing question.

    IMPORTANT:
    CLO/PLO language is used internally only.
    It is NEVER inserted into the revised question.
    """

    qtype = result["Question Type"]

    # Prefer CLO because it is the direct course outcome.
    primary = result["Best CLO"]

    if not primary and plos:
        primary = result["Best PLO"]

    if not primary:
        return original

    if qtype == "MCQ":
        revision = revise_mcq(
            original,
            primary,
            target_bloom
        )

    elif qtype == "True / False":
        revision = revise_true_false(
            original,
            primary,
            target_bloom
        )

    elif qtype == "Fill in the Blank":
        revision = revise_fill_blank(
            original,
            primary
        )

    elif qtype == "Numerical / Problem Solving":
        revision = revise_numerical(
            original,
            primary,
            target_bloom
        )

    elif qtype == "Case Study / Application":
        revision = revise_case_study(
            original,
            primary,
            target_bloom
        )

    elif qtype == "Essay / Long Answer":
        revision = revise_short_answer(
            original,
            primary,
            plos[0] if plos else "",
            target_bloom
        )

    else:
        revision = revise_short_answer(
            original,
            primary,
            plos[0] if plos else "",
            target_bloom
        )

    revision = clean_text(revision)

    # Preserve MCQ line structure
    if qtype == "MCQ":
        revision = (
            clean_text(revision.split("\n")[0])
            + "\n"
            + "\n".join(
                extract_mcq_options(original)
            )
        )

    return revision


def revision_is_valid(
    original,
    revised,
    result
):
    if not revised:
        return False

    if normalize(original) == normalize(revised):
        return False

    if forbidden_revision_language(
        revised
    ):
        return False

    if not preserve_numbers(
        original,
        revised
    ):
        return False

    if result["Question Type"] == "MCQ":
        if not preserve_mcq_options(
            original,
            revised
        ):
            return False

    # Revision must remain a question/task
    if len(revised.split()) < 5:
        return False

    return True


# ============================================================
# TARGET BLOOM
# ============================================================

def target_bloom_from_input(selected):
    if selected in BLOOM_LEVELS:
        return selected

    return "Understand"


# ============================================================
# SESSION STATE
# ============================================================

if "questions" not in st.session_state:
    st.session_state.questions = []

if "results" not in st.session_state:
    st.session_state.results = []

if "revisions" not in st.session_state:
    st.session_state.revisions = {}

if "accepted" not in st.session_state:
    st.session_state.accepted = {}

if "source_text" not in st.session_state:
    st.session_state.source_text = ""

# ============================================================
# HEADER
# ============================================================

st.title("🎓 OBE Quiz Checker")

st.write(
    "Check your assessment questions for CLO, PLO, Bloom's Taxonomy, "
    "clarity, relevance, and measurability — and improve weak questions "
    "with practical, context-preserving revisions."
)

# ============================================================
# ASSESSMENT INFORMATION
# ============================================================

st.subheader("1. Assessment Information")

col1, col2, col3 = st.columns(3)

with col1:
    course_name = st.text_input(
        "Course / Subject",
        placeholder="e.g., Chemistry, English I, Programming"
    )

with col2:
    assessment_name = st.text_input(
        "Assessment Name",
        placeholder="e.g., Quiz 1, Assignment 1"
    )

with col3:
    target_bloom = st.selectbox(
        "Target Bloom's Level",
        BLOOM_LEVELS,
        index=1
    )

# ============================================================
# OUTCOMES
# ============================================================

st.subheader("2. Learning Outcomes")

clo_text = st.text_area(
    "Enter CLOs",
    placeholder=(
        "CLO 1: Explain the process of photosynthesis and its importance to plant growth.\n"
        "CLO 2: Analyze the factors affecting plant growth."
    ),
    height=150
)

plo_text = st.text_area(
    "Enter PLOs",
    placeholder=(
        "PLO 1: Apply knowledge of the relevant discipline to solve problems.\n"
        "PLO 2: Analyze and communicate solutions effectively."
    ),
    height=150
)

clos = parse_outcomes(
    clo_text
)

plos = parse_outcomes(
    plo_text
)

if clos:
    st.success(
        f"{len(clos)} CLO(s) detected."
    )

if plos:
    st.success(
        f"{len(plos)} PLO(s) detected."
    )

# ============================================================
# FILE UPLOAD
# ============================================================

st.subheader("3. Upload Complete Assessment")

uploaded_file = st.file_uploader(
    "Upload your complete assessment",
    type=[
        "pdf",
        "docx",
        "pptx",
        "xlsx",
        "xls",
        "csv",
        "txt",
        "md",
        "png",
        "jpg",
        "jpeg",
        "webp",
        "bmp",
        "tif",
        "tiff"
    ]
)

if uploaded_file is not None:

    st.caption(
        f"File: {uploaded_file.name}"
    )

    try:
        extracted_text = read_uploaded_file(
            uploaded_file
        )

        st.session_state.source_text = extracted_text

        if not extracted_text.strip():

            st.error(
                "The file was opened, but no readable text was found."
            )

            st.info(
                "If this is a scanned PDF/image, make sure OCR is available "
                "in requirements.txt."
            )

        else:

            extracted_questions = extract_questions(
                extracted_text
            )

            st.session_state.questions = (
                extracted_questions
            )

            st.success(
                f"File read successfully. "
                f"{len(extracted_questions)} question(s) detected."
            )

            with st.expander(
                "Preview extracted text"
            ):
                st.text(
                    extracted_text[:12000]
                )

            if not extracted_questions:
                st.warning(
                    "Readable text was found, but the question structure "
                    "could not be identified automatically."
                )

                st.info(
                    "The extracted text is shown above. "
                    "Use a PDF/DOCX with question numbering or clear question wording."
                )

    except Exception as exc:
        st.error(
            "The file could not be read."
        )

        st.exception(exc)

# ============================================================
# ANALYZE BUTTON
# ============================================================

st.subheader("4. Analyze Assessment")

if st.button(
    "🔍 Analyze Assessment",
    type="primary",
    use_container_width=True
):

    if not uploaded_file:
        st.error(
            "Please upload an assessment file first."
        )
        st.stop()

    if not st.session_state.source_text:
        st.error(
            "The uploaded file contains no readable text."
        )
        st.stop()

    if not st.session_state.questions:
        st.error(
            "No assessment questions could be identified from the readable text."
        )

        with st.expander(
            "Show extracted text for diagnosis"
        ):
            st.text(
                st.session_state.source_text[:15000]
            )

        st.stop()

    results = []

    progress = st.progress(0)

    total = len(
        st.session_state.questions
    )

    for index, question in enumerate(
        st.session_state.questions
    ):

        result = evaluate(
            question,
            clos,
            plos,
            target_bloom_from_input(
                target_bloom
            )
        )

        result["Number"] = index + 1
        result["Question"] = question
        result["Status"] = status(
            result["Overall"]
        )

        results.append(result)

        progress.progress(
            int(
                ((index + 1) / total) * 100
            )
        )

    st.session_state.results = results

    # Generate revisions only for weak questions
    revisions = {}

    for result in results:

        needs_revision = (
            result["Overall"] < ATTAINMENT
            or result["CLO Match"] < ATTAINMENT
            or result["PLO Match"] < ATTAINMENT
            or result["Bloom"] < ATTAINMENT
            or result["Clarity"] < ATTAINMENT
            or result["Measurability"] < ATTAINMENT
        )

        if not needs_revision:
            continue

        revised = create_revision(
            result["Question"],
            result,
            clos,
            plos,
            target_bloom_from_input(
                target_bloom
            )
        )

        if revision_is_valid(
            result["Question"],
            revised,
            result
        ):
            revisions[
                result["Number"]
            ] = revised

    st.session_state.revisions = revisions
    st.session_state.accepted = {}

    st.success(
        f"Analysis completed for {len(results)} question(s)."
    )

# ============================================================
# RESULTS
# ============================================================

if st.session_state.results:

    results = st.session_state.results

    # ========================================================
    # OVERALL
    # ========================================================

    st.subheader("5. Overall Alignment")

    overall_score = round(
        sum(
            r["Overall"]
            for r in results
        ) / len(results)
    )

    strong_count = sum(
        r["Overall"] >= 85
        for r in results
    )

    attained_count = sum(
        75 <= r["Overall"] < 85
        for r in results
    )

    revision_count = sum(
        r["Overall"] < 75
        for r in results
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Overall Score",
            f"{overall_score}%"
        )

    with c2:
        st.metric(
            "Strong",
            strong_count
        )

    with c3:
        st.metric(
            "Attained",
            attained_count
        )

    with c4:
        st.metric(
            "Needs Revision",
            revision_count
        )

    if overall_score >= 80:
        st.success(
            "🏆 Overall assessment alignment has reached 80% or above."
        )
        st.balloons()

    elif overall_score >= 75:
        st.info(
            "The overall assessment has reached the attainment threshold."
        )

    else:
        st.warning(
            "Some questions require revision before the assessment "
            "reaches the desired alignment level."
        )

    # ========================================================
    # SCORE ANALYSIS
    # ========================================================

    st.subheader("6. Assessment Score Analysis")

    metric_data = []

    metric_names = [
        "CLO Match",
        "PLO Match",
        "Bloom",
        "Relevance",
        "Clarity",
        "Measurability"
    ]

    for metric in metric_names:

        value = round(
            sum(
                r[metric]
                for r in results
            ) / len(results)
        )

        metric_data.append({
            "Metric": metric,
            "Average Score": value
        })

    metric_df = pd.DataFrame(
        metric_data
    )

    st.dataframe(
        metric_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # REVISION LIST AT TOP
    # ========================================================

    st.subheader(
        "7. Questions Requiring Revision"
    )

    weak_results = [
        r for r in results
        if r["Number"] in st.session_state.revisions
    ]

    if not weak_results:

        st.success(
            "🎉 No question requires revision."
        )

    else:

        st.info(
            f"{len(weak_results)} question(s) require revision. "
            "The suggested revisions are generated automatically."
        )

        for result in weak_results:

            number = result["Number"]

            st.markdown(
                f"### Question {number} — "
                f"{result['Overall']}% — {result['Status']}"
            )

            st.write(
                "**Current Question:**"
            )

            st.info(
                result["Question"]
            )

            problems = identify_problems(
                result
            )

            st.write(
                "**Problem Identified:**"
            )

            for problem in problems:
                st.write(
                    f"• {problem}"
                )

            st.write(
                "**Why the Tool Flagged It:**"
            )

            st.write(
                f"CLO Match: {result['CLO Match']}%  |  "
                f"PLO Match: {result['PLO Match']}%  |  "
                f"Bloom: {result['Bloom']}%  |  "
                f"Relevance: {result['Relevance']}%  |  "
                f"Clarity: {result['Clarity']}%  |  "
                f"Measurability: {result['Measurability']}%"
            )

            st.write(
                "**Revision Focus:**"
            )

            st.write(
                revision_focus(result)
            )

            revised = st.session_state.revisions.get(
                number
            )

            if revised:

                st.write(
                    "**Practical Revision:**"
                )

                st.success(
                    revised
                )

                if st.button(
                    f"✅ Use This Revision — Question {number}",
                    key=f"use_revision_{number}",
                    use_container_width=True
                ):

                    # Replace original question
                    st.session_state.questions[
                        number - 1
                    ] = revised

                    # Rescore
                    new_result = evaluate(
                        revised,
                        clos,
                        plos,
                        target_bloom_from_input(
                            target_bloom
                        )
                    )

                    new_result["Number"] = number
                    new_result["Question"] = revised
                    new_result["Status"] = status(
                        new_result["Overall"]
                    )

                    # Replace result
                    for i, old in enumerate(
                        st.session_state.results
                    ):
                        if old["Number"] == number:
                            st.session_state.results[
                                i
                            ] = new_result
                            break

                    st.session_state.accepted[
                        number
                    ] = {
                        "before": result["Overall"],
                        "after": new_result["Overall"]
                    }

                    # Remove revision if attained
                    if new_result["Overall"] >= ATTAINMENT:
                        st.session_state.revisions.pop(
                            number,
                            None
                        )

                    st.rerun()

            st.divider()

    # ========================================================
    # ACCEPTED REVISIONS
    # ========================================================

    if st.session_state.accepted:

        st.subheader(
            "Accepted Revisions"
        )

        for number, values in st.session_state.accepted.items():

            st.success(
                f"Question {number}: "
                f"{values['before']}% → "
                f"{values['after']}%"
            )

            if values["after"] >= ATTAINMENT:
                st.write(
                    "🏆 Attained"
                )
                st.balloons()

    # ========================================================
    # ATTAINED QUESTIONS
    # ========================================================

    st.subheader(
        "8. Attained Questions"
    )

    attained = [
        r for r in st.session_state.results
        if r["Overall"] >= ATTAINMENT
    ]

    if attained:

        attained_df = pd.DataFrame([
            {
                "Question": r["Number"],
                "Score": f"{r['Overall']}%",
                "Status": status(
                    r["Overall"]
                ),
                "Type": r["Question Type"],
                "CLO": f"{r['CLO Match']}%",
                "PLO": f"{r['PLO Match']}%",
                "Bloom": f"{r['Bloom']}%"
            }
            for r in attained
        ])

        st.dataframe(
            attained_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "No questions have reached 75% yet."
        )

    # ========================================================
    # ONLY GRAPH
    # ========================================================

    st.subheader(
        "9. Alignment Overview"
    )

    graph_df = pd.DataFrame([
        {
            "Question": f"Q{r['Number']}",
            "Score": r["Overall"]
        }
        for r in st.session_state.results
    ])

    st.bar_chart(
        graph_df.set_index("Question")
    )

    # ========================================================
    # QUESTION OVERVIEW
    # ========================================================

    st.subheader(
        "10. Question Overview"
    )

    overview_df = pd.DataFrame([
        {
            "Question": r["Number"],
            "Type": r["Question Type"],
            "Score": f"{r['Overall']}%",
            "Status": r["Status"],
            "CLO": f"{r['CLO Match']}%",
            "PLO": f"{r['PLO Match']}%",
            "Bloom": f"{r['Bloom']}%",
            "Clarity": f"{r['Clarity']}%",
            "Measurability": f"{r['Measurability']}%"
        }
        for r in st.session_state.results
    ])

    st.dataframe(
        overview_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # DETAILED ANALYSIS
    # ========================================================

    st.subheader(
        "11. Detailed Question Analysis"
    )

    selected_number = st.selectbox(
        "Select Question",
        [
            r["Number"]
            for r in st.session_state.results
        ]
    )

    selected_result = next(
        r for r in st.session_state.results
        if r["Number"] == selected_number
    )

    st.markdown(
        f"### Question {selected_result['Number']}"
    )

    st.write(
        selected_result["Question"]
    )

    details = {
        "Overall": selected_result["Overall"],
        "Status": selected_result["Status"],
        "Question Type": selected_result["Question Type"],
        "Detected Bloom": selected_result["Detected Bloom"],
        "CLO Match": selected_result["CLO Match"],
        "PLO Match": selected_result["PLO Match"],
        "Bloom Score": selected_result["Bloom"],
        "Relevance": selected_result["Relevance"],
        "Clarity": selected_result["Clarity"],
        "Measurability": selected_result["Measurability"]
    }

    detail_df = pd.DataFrame(
        [
            {
                "Metric": key,
                "Value": (
                    f"{value}%"
                    if isinstance(value, (int, float))
                    and key not in [
                        "Overall"
                    ]
                    else value
                )
            }
            for key, value in details.items()
        ]
    )

    st.dataframe(
        detail_df,
        use_container_width=True,
        hide_index=True
    )

    if selected_result["Best CLO"]:
        st.write(
            "**Best Matching CLO:**"
        )
        st.info(
            selected_result["Best CLO"]
        )

    if selected_result["Best PLO"]:
        st.write(
            "**Best Matching PLO:**"
        )
        st.info(
            selected_result["Best PLO"]
        )

    # ========================================================
    # EXPORT
    # ========================================================

    st.subheader(
        "12. Export"
    )

    export_rows = []

    for r in st.session_state.results:

        export_rows.append({
            "Question No.": r["Number"],
            "Question": r["Question"],
            "Question Type": r["Question Type"],
            "Overall Score": r["Overall"],
            "Status": r["Status"],
            "CLO Match": r["CLO Match"],
            "PLO Match": r["PLO Match"],
            "Bloom": r["Bloom"],
            "Relevance": r["Relevance"],
            "Clarity": r["Clarity"],
            "Measurability": r["Measurability"],
            "Detected Bloom": r["Detected Bloom"],
            "Best CLO": r["Best CLO"],
            "Best PLO": r["Best PLO"],
            "Suggested Revision": st.session_state.revisions.get(
                r["Number"],
                ""
            )
        })

    export_df = pd.DataFrame(
        export_rows
    )

    csv_data = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Assessment Report",
        data=csv_data,
        file_name="obe_quiz_checker_report.csv",
        mime="text/csv",
        use_container_width=True
    )

# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "OBE Quiz Checker | Supports PDF, DOCX, PPTX, XLSX, CSV, TXT and image-based assessments."
)
