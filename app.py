import io
import re
from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# OBE QUIZ CHECKER
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Checker",
    page_icon="🎓",
    layout="wide"
)


# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

try:
    import fitz
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

ATTAINED_THRESHOLD = 75.0

BLOOM_LEVELS = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create",
]

BLOOM_ORDER = {
    "remember": 1,
    "understand": 2,
    "apply": 3,
    "analyze": 4,
    "evaluate": 5,
    "create": 6,
}


# ============================================================
# SESSION STATE
# ============================================================

state_defaults = {
    "assessment_text": "",
    "questions": [],
    "analysis": [],
    "analysis_complete": False,
    "revision_options": [],
    "revision_question_index": None,
    "last_overall": None,
    "celebrate_question": False,
    "celebrate_overall": False,
}

for key, value in state_defaults.items():
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
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_text(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def content_words(text):
    stopwords = {
        "the", "a", "an", "and", "or", "of", "to", "in",
        "on", "for", "from", "with", "by", "is", "are",
        "was", "were", "be", "as", "at", "that", "this",
        "these", "those", "it", "its", "their", "there",
        "which", "who", "what", "how", "why", "when",
        "where", "into", "than", "then", "can", "could",
        "should", "would", "will", "may", "might", "using",
        "use", "used", "your", "you", "they", "them",
        "he", "she", "his", "her", "we", "our", "i", "me",
        "describe", "explain", "discuss", "write", "state",
        "identify", "give", "list", "answer"
    }

    words = re.findall(
        r"[A-Za-z][A-Za-z0-9\-]{2,}",
        str(text).lower()
    )

    return [
        word
        for word in words
        if word not in stopwords
    ]


def unique_preserved_terms(text):
    terms = []

    quoted = re.findall(
        r'"([^"]+)"|\'([^\']+)\'',
        text
    )

    for pair in quoted:
        for item in pair:
            if item:
                terms.append(item.strip())

    numbers = re.findall(
        r"\b\d+(?:\.\d+)?(?:\s*%|\s*(?:kg|g|mg|m|cm|km|s|min|h|Hz|V|A))?\b",
        text,
        flags=re.I
    )

    terms.extend(numbers)

    return list(dict.fromkeys(terms))


# ============================================================
# BLOOM TAXONOMY
# ============================================================

BLOOM_VERBS = {
    "Remember": [
        "define",
        "list",
        "name",
        "identify",
        "state",
        "recall",
        "recognize",
        "label",
        "match",
    ],
    "Understand": [
        "describe",
        "explain",
        "summarize",
        "classify",
        "interpret",
        "discuss",
        "illustrate",
        "paraphrase",
    ],
    "Apply": [
        "calculate",
        "solve",
        "apply",
        "demonstrate",
        "use",
        "implement",
        "execute",
        "compute",
        "perform",
        "show",
    ],
    "Analyze": [
        "analyze",
        "analyse",
        "compare",
        "contrast",
        "differentiate",
        "examine",
        "investigate",
        "categorize",
        "distinguish",
        "deconstruct",
    ],
    "Evaluate": [
        "evaluate",
        "assess",
        "justify",
        "critique",
        "judge",
        "defend",
        "argue",
        "recommend",
        "appraise",
    ],
    "Create": [
        "design",
        "create",
        "develop",
        "construct",
        "formulate",
        "produce",
        "propose",
        "generate",
        "plan",
        "compose",
    ],
}


def find_bloom_verb(text):
    normalized = normalize_text(text)

    for level in BLOOM_LEVELS:
        for verb in BLOOM_VERBS[level]:
            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                normalized
            ):
                return verb, level

    return "", "Unknown"


def bloom_score(question, target_level):
    _, detected = find_bloom_verb(question)

    if not target_level or target_level == "Auto":
        if detected == "Unknown":
            return 72.0

        return 88.0

    target = BLOOM_ORDER.get(
        target_level.lower()
    )

    if target is None:
        return 72.0

    actual = BLOOM_ORDER.get(
        detected.lower()
    )

    if actual is None:
        return 72.0

    distance = abs(target - actual)

    if distance == 0:
        return 100.0

    if distance == 1:
        return 88.0

    if distance == 2:
        return 75.0

    return 62.0


# ============================================================
# CLO / PLO PARSING
# ============================================================

def parse_outcomes(text):
    if not text:
        return []

    lines = text.splitlines()
    outcomes = []

    for line in lines:
        line = line.strip()

        if not line:
            continue

        line = re.sub(
            r"^\s*(?:CLO|PLO)?\s*\d+\s*[\.\):-]?\s*",
            "",
            line,
            flags=re.I
        )

        if len(line) >= 8:
            outcomes.append(line)

    return outcomes


def meaningful_overlap(question, outcome):
    q_words = set(content_words(question))
    o_words = set(content_words(outcome))

    if not q_words or not o_words:
        return 0.0

    overlap = q_words.intersection(o_words)

    q_ratio = len(overlap) / max(len(q_words), 1)
    o_ratio = len(overlap) / max(len(o_words), 1)

    score = 50 + (q_ratio * 25) + (o_ratio * 25)

    return max(
        0.0,
        min(100.0, score)
    )


def outcome_match_score(
    question,
    outcome,
    target_bloom=None
):
    if not outcome:
        return 70.0

    lexical = meaningful_overlap(
        question,
        outcome
    )

    _, question_bloom = find_bloom_verb(
        question
    )

    _, outcome_bloom = find_bloom_verb(
        outcome
    )

    bloom_bonus = 0

    if (
        question_bloom != "Unknown"
        and outcome_bloom != "Unknown"
    ):
        if question_bloom == outcome_bloom:
            bloom_bonus = 15
        elif abs(
            BLOOM_ORDER.get(question_bloom, 3)
            - BLOOM_ORDER.get(outcome_bloom, 3)
        ) == 1:
            bloom_bonus = 8

    score = lexical + bloom_bonus

    return max(
        0.0,
        min(100.0, score)
    )


# ============================================================
# QUESTION TYPE
# ============================================================

def detect_question_type(question):
    q = question.strip()
    lower = q.lower()

    if re.search(
        r"\btrue\s*(?:or|/)\s*false\b",
        lower
    ):
        return "True / False"

    if re.search(
        r"\btrue\s*false\b",
        lower
    ):
        return "True / False"

    if re.search(
        r"(?:^|\n)\s*(?:a|b|c|d|e)[\)\.\-]\s+",
        q,
        flags=re.I
    ):
        return "Multiple Choice"

    if "match the following" in lower:
        return "Matching"

    if (
        "fill in the blank" in lower
        or "________" in q
        or "____" in q
    ):
        return "Fill in the Blank"

    numerical_patterns = [
        r"\bcalculate\b",
        r"\bcompute\b",
        r"\bsolve\b",
        r"\bfind the value\b",
        r"\bdetermine the value\b",
        r"\bwhat is the value\b",
    ]

    if any(
        re.search(pattern, lower)
        for pattern in numerical_patterns
    ):
        return "Numerical / Problem Solving"

    if any(
        phrase in lower
        for phrase in [
            "case study",
            "scenario",
            "given case",
            "read the case",
            "situation",
        ]
    ):
        return "Case Study / Scenario"

    if any(
        word in lower
        for word in [
            "design",
            "develop",
            "construct",
            "implement",
            "perform",
            "demonstrate",
        ]
    ):
        return "Practical / Application"

    if any(
        word in lower
        for word in [
            "essay",
            "critically discuss",
            "critically analyze",
            "critically analyse",
        ]
    ):
        return "Essay"

    if len(q.split()) > 45:
        return "Long Answer"

    if any(
        word in lower
        for word in [
            "explain",
            "discuss",
            "analyze",
            "analyse",
            "evaluate",
            "compare",
            "justify",
            "assess",
        ]
    ):
        return "Short / Long Answer"

    return "Short Answer"


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def clean_question_block(text):
    text = clean_text(text)

    text = re.sub(
        r"^\s*(?:Q(?:uestion)?\.?\s*)?\d+\s*[\)\.\-:]\s*",
        "",
        text,
        flags=re.I
    )

    return text.strip()


def extract_questions(text):
    text = clean_text(text)

    if not text:
        return []

    lines = text.splitlines()
    questions = []
    current = []

    question_start = re.compile(
        r"^\s*(?:Q(?:uestion)?\.?\s*)?\d+\s*[\)\.\-:]\s+",
        flags=re.I
    )

    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue

        if question_start.match(stripped):

            if current:
                block = clean_question_block(
                    " ".join(current)
                )

                if len(block.split()) >= 3:
                    questions.append(block)

            current = [stripped]

        else:
            if current:
                current.append(stripped)

    if current:
        block = clean_question_block(
            " ".join(current)
        )

        if len(block.split()) >= 3:
            questions.append(block)

    # Fallback for assessments without numbering
    if len(questions) < 2:

        fallback = []

        paragraphs = re.split(
            r"\n\s*\n",
            text
        )

        for paragraph in paragraphs:
            paragraph = clean_text(
                paragraph
            )

            if len(paragraph.split()) >= 5:
                fallback.append(paragraph)

        if len(fallback) >= 2:
            questions = fallback

    # Final fallback
    if not questions:

        pieces = re.split(
            r"(?<=[\?\:])\s+(?=[A-Z])",
            text
        )

        for piece in pieces:
            piece = clean_text(piece)

            if len(piece.split()) >= 5:
                questions.append(piece)

    unique = []
    seen = set()

    for question in questions:
        key = normalize_text(question)

        if key and key not in seen:
            unique.append(question)
            seen.add(key)

    return unique


# ============================================================
# FILE READING
# ============================================================

def read_pdf(uploaded_file):
    if fitz is None:
        raise RuntimeError(
            "PyMuPDF is not installed. "
            "Add PyMuPDF to requirements.txt."
        )

    data = uploaded_file.read()

    document = fitz.open(
        stream=data,
        filetype="pdf"
    )

    pages = []

    for page in document:
        text = page.get_text("text")

        if text:
            pages.append(text)

    result = "\n\n".join(pages)

    # OCR fallback
    if (
        len(result.strip()) < 100
        and pytesseract is not None
        and Image is not None
    ):
        ocr_pages = []

        for page in document:

            pix = page.get_pixmap(
                matrix=fitz.Matrix(2, 2)
            )

            image = Image.frombytes(
                "RGB",
                [pix.width, pix.height],
                pix.samples
            )

            try:
                ocr_text = pytesseract.image_to_string(
                    image
                )

                if ocr_text:
                    ocr_pages.append(
                        ocr_text
                    )

            except Exception:
                pass

        if ocr_pages:
            result = "\n\n".join(
                ocr_pages
            )

    return clean_text(result)


def read_docx(uploaded_file):
    if Document is None:
        raise RuntimeError(
            "python-docx is not installed."
        )

    data = uploaded_file.read()

    document = Document(
        io.BytesIO(data)
    )

    paragraphs = [
        paragraph.text
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ]

    table_text = []

    for table in document.tables:

        for row in table.rows:

            cells = []

            for cell in row.cells:
                cells.append(
                    cell.text
                )

            table_text.append(
                " | ".join(cells)
            )

    return clean_text(
        "\n".join(
            paragraphs + table_text
        )
    )


def read_pptx(uploaded_file):
    if Presentation is None:
        raise RuntimeError(
            "python-pptx is not installed."
        )

    data = uploaded_file.read()

    presentation = Presentation(
        io.BytesIO(data)
    )

    slides = []

    for slide in presentation.slides:

        texts = []

        for shape in slide.shapes:

            if hasattr(shape, "text"):

                if shape.text.strip():
                    texts.append(
                        shape.text
                    )

        if texts:
            slides.append(
                "\n".join(texts)
            )

    return clean_text(
        "\n\n".join(slides)
    )


def read_excel(uploaded_file):
    data = uploaded_file.read()

    workbook = pd.ExcelFile(
        io.BytesIO(data)
    )

    sheets = []

    for sheet in workbook.sheet_names:

        frame = pd.read_excel(
            io.BytesIO(data),
            sheet_name=sheet,
            header=None
        )

        sheet_text = (
            f"Sheet: {sheet}\n"
            + frame.fillna("")
            .astype(str)
            .to_csv(
                index=False,
                header=False
            )
        )

        sheets.append(
            sheet_text
        )

    return clean_text(
        "\n".join(sheets)
    )


def read_csv(uploaded_file):
    data = uploaded_file.read()

    try:
        frame = pd.read_csv(
            io.BytesIO(data)
        )

    except Exception:
        frame = pd.read_csv(
            io.BytesIO(data),
            header=None
        )

    return clean_text(
        frame.fillna("")
        .astype(str)
        .to_csv(
            index=False
        )
    )


def read_text(uploaded_file):
    data = uploaded_file.read()

    return data.decode(
        "utf-8",
        errors="ignore"
    )


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
        uploaded_file
    )

    return clean_text(
        pytesseract.image_to_string(
            image
        )
    )


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

    if suffix in [".xlsx", ".xls"]:
        return read_excel(uploaded_file)

    if suffix == ".csv":
        return read_csv(uploaded_file)

    if suffix in [".txt", ".md"]:
        return read_text(uploaded_file)

    if suffix in [
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
        ".tiff",
    ]:
        return read_image(uploaded_file)

    if suffix == ".svg":

        data = uploaded_file.read().decode(
            "utf-8",
            errors="ignore"
        )

        return clean_text(
            re.sub(
                r"<[^>]+>",
                " ",
                data
            )
        )

    raise RuntimeError(
        f"Unsupported file type: {suffix}"
    )


# ============================================================
# SCORING
# ============================================================

def clarity_score(question):
    words = question.split()

    score = 94.0

    if len(words) < 4:
        score -= 18

    if len(words) > 80:
        score -= 8

    vague_phrases = [
        "discuss everything",
        "write something",
        "say something",
        "what do you know",
        "write about",
        "comment on this",
        "discuss the topic",
        "explain in detail",
    ]

    lower = question.lower()

    for phrase in vague_phrases:

        if phrase in lower:
            score -= 12

    return max(
        0.0,
        min(100.0, score)
    )


def measurability_score(question):
    _, level = find_bloom_verb(
        question
    )

    if level != "Unknown":
        return 96.0

    if "?" in question:
        return 85.0

    return 76.0


def relevance_score(
    question,
    clo,
    plo
):
    scores = []

    if clo:
        scores.append(
            meaningful_overlap(
                question,
                clo
            )
        )

    if plo:
        scores.append(
            meaningful_overlap(
                question,
                plo
            )
        )

    if not scores:
        return 75.0

    return sum(scores) / len(scores)


def evaluate_question(
    question,
    clo="",
    plo="",
    target_bloom="Auto",
    question_type=None,
):
    if question_type is None:
        question_type = detect_question_type(
            question
        )

    clo_score = outcome_match_score(
        question,
        clo,
        target_bloom
    )

    plo_score = outcome_match_score(
        question,
        plo,
        target_bloom
    )

    bloom = bloom_score(
        question,
        target_bloom
    )

    relevance = relevance_score(
        question,
        clo,
        plo
    )

    clarity = clarity_score(
        question
    )

    measurable = measurability_score(
        question
    )

    overall = (
        clo_score * 0.20
        + plo_score * 0.15
        + bloom * 0.20
        + relevance * 0.15
        + clarity * 0.15
        + measurable * 0.15
    )

    return {
        "CLO Match": round(
            clo_score,
            1
        ),
        "PLO Match": round(
            plo_score,
            1
        ),
        "Bloom": round(
            bloom,
            1
        ),
        "Relevance": round(
            relevance,
            1
        ),
        "Clarity": round(
            clarity,
            1
        ),
        "Measurability": round(
            measurable,
            1
        ),
        "Overall": round(
            overall,
            1
        ),
        "Question Type": question_type,
    }


# ============================================================
# PRACTICAL REVISION ENGINE
# ============================================================

def preservation_score(
    original,
    revised
):
    original_words = set(
        content_words(original)
    )

    revised_words = set(
        content_words(revised)
    )

    if not original_words:
        return 0.0

    retained = (
        original_words.intersection(
            revised_words
        )
    )

    word_retention = (
        len(retained)
        / len(original_words)
    )

    original_special = unique_preserved_terms(
        original
    )

    revised_special = unique_preserved_terms(
        revised
    )

    special_score = 0.0

    if original_special:

        retained_special = [
            term
            for term in original_special
            if term in revised_special
        ]

        special_score = (
            len(retained_special)
            / len(original_special)
        )

    score = (
        word_retention * 75
        + special_score * 25
    )

    return max(
        0.0,
        min(100.0, score)
    )


def topic_preserved(
    original,
    revised
):
    original_words = set(
        content_words(original)
    )

    revised_words = set(
        content_words(revised)
    )

    if not original_words:
        return False

    overlap = len(
        original_words.intersection(
            revised_words
        )
    )

    retention = (
        overlap
        / len(original_words)
    )

    if retention >= 0.55:
        return True

    original_special = unique_preserved_terms(
        original
    )

    if original_special:

        return all(
            term in revised
            for term in original_special
        )

    return False


def candidate_is_safe(
    original,
    candidate,
    clo,
    plo,
    target_bloom,
    question_type,
):
    if not candidate:
        return False

    if normalize_text(candidate) == normalize_text(
        original
    ):
        return False

    if not topic_preserved(
        original,
        candidate
    ):
        return False

    preservation = preservation_score(
        original,
        candidate
    )

    if preservation < 60:
        return False

    original_special = unique_preserved_terms(
        original
    )

    candidate_special = unique_preserved_terms(
        candidate
    )

    for term in original_special:

        if term not in candidate_special:
            return False

    candidate_type = detect_question_type(
        candidate
    )

    if candidate_type != question_type:

        compatible = {
            "Short Answer",
            "Long Answer",
            "Short / Long Answer",
            "Essay",
        }

        if not (
            question_type in compatible
            and candidate_type in compatible
        ):
            return False

    old_score = evaluate_question(
        original,
        clo,
        plo,
        target_bloom,
        question_type
    )["Overall"]

    new_score = evaluate_question(
        candidate,
        clo,
        plo,
        target_bloom,
        question_type
    )["Overall"]

    return new_score >= old_score + 1.0


def replace_leading_verb(
    question,
    new_verb
):
    verbs = []

    for level in BLOOM_LEVELS:
        verbs.extend(
            BLOOM_VERBS[level]
        )

    pattern = (
        r"^\s*(?:please\s+)?(?:"
        + "|".join(
            re.escape(verb)
            for verb in verbs
        )
        + r")\b"
    )

    match = re.search(
        pattern,
        question,
        flags=re.I
    )

    if match:

        remainder = question[
            match.end():
        ].lstrip()

        return (
            new_verb.capitalize()
            + " "
            + remainder
        )

    return (
        new_verb.capitalize()
        + " "
        + question
    )


def make_clarity_revision(
    question,
    question_type
):
    replacements = [
        (
            "discuss everything about",
            "Explain the key aspects of"
        ),
        (
            "write something about",
            "Explain the main features of"
        ),
        (
            "write about",
            "Explain the main features of"
        ),
        (
            "comment on",
            "Explain"
        ),
        (
            "what do you know about",
            "Explain"
        ),
    ]

    lower = question.lower()

    for old, new in replacements:

        if old in lower:

            return re.sub(
                re.escape(old),
                new,
                question,
                count=1,
                flags=re.I
            )

    verb, level = find_bloom_verb(
        question
    )

    if level != "Unknown":

        return (
            question.rstrip(" .?")
            + " Clearly address the specific "
            "requirement stated in the question."
        )

    return (
        question.rstrip(" .?")
        + " Clearly state the specific points "
        "required in your answer."
    )


def make_measurable_revision(
    question,
    question_type
):
    q = question.rstrip()

    lower = q.lower()

    if question_type == "Numerical / Problem Solving":

        if (
            "show" not in lower
            and "steps" not in lower
        ):

            return (
                q.rstrip(" .?")
                + " Show the steps used in your calculation."
            )

    if question_type == "Case Study / Scenario":

        if (
            "evidence" not in lower
            and "factors" not in lower
        ):

            return (
                q.rstrip(" .?")
                + " Identify two relevant factors "
                "and support your answer with evidence "
                "from the case."
            )

    if question_type in [
        "Multiple Choice",
        "True / False",
        "Matching",
    ]:
        return ""

    return (
        q.rstrip(" .?")
        + " Include at least two relevant points "
        "in your response."
    )


def make_bloom_revision(
    question,
    target_bloom
):
    if target_bloom == "Auto":
        return ""

    verb_map = {
        "remember": "identify",
        "understand": "explain",
        "apply": "apply",
        "analyze": "analyze",
        "evaluate": "evaluate",
        "create": "design",
    }

    new_verb = verb_map.get(
        target_bloom.lower()
    )

    if not new_verb:
        return ""

    return replace_leading_verb(
        question,
        new_verb
    )


def make_outcome_revision(
    question,
    clo,
    plo,
    question_type
):
    outcome = clo if clo else plo

    if not outcome:
        return ""

    outcome_words = content_words(
        outcome
    )

    question_words = set(
        content_words(question)
    )

    missing = [
        word
        for word in outcome_words
        if word not in question_words
    ]

    useful = [
        word
        for word in missing
        if len(word) >= 5
    ][:3]

    if not useful:
        return ""

    if question_type == "Case Study / Scenario":

        return (
            question.rstrip(" .?")
            + " Address the relevant "
            + ", ".join(useful)
            + " in your response."
        )

    if question_type == "Numerical / Problem Solving":

        return (
            question.rstrip(" .?")
            + " Apply the relevant "
            + ", ".join(useful)
            + " when solving the problem."
        )

    return (
        question.rstrip(" .?")
        + " In your answer, relate your response to "
        + ", ".join(useful)
        + "."
    )


def generate_practical_revisions(
    question,
    clo,
    plo,
    target_bloom,
    question_type
):
    candidates = []

    # --------------------------------------------------------
    # CLARITY
    # --------------------------------------------------------

    clarity = make_clarity_revision(
        question,
        question_type
    )

    if clarity:

        candidates.append(
            {
                "text": clarity,
                "reason": (
                    "Clarifies what the student is expected "
                    "to do while preserving the original "
                    "topic and task."
                ),
                "focus": "Clarity",
            }
        )

    # --------------------------------------------------------
    # MEASURABILITY
    # --------------------------------------------------------

    measurable = make_measurable_revision(
        question,
        question_type
    )

    if measurable:

        candidates.append(
            {
                "text": measurable,
                "reason": (
                    "Makes the expected student response "
                    "observable and easier to assess "
                    "consistently."
                ),
                "focus": "Measurability",
            }
        )

    # --------------------------------------------------------
    # BLOOM
    # --------------------------------------------------------

    bloom_revision = make_bloom_revision(
        question,
        target_bloom
    )

    if bloom_revision:

        candidates.append(
            {
                "text": bloom_revision,
                "reason": (
                    "Adjusts the action required from the "
                    "student to better match the selected "
                    "Bloom level."
                ),
                "focus": "Bloom",
            }
        )

    # --------------------------------------------------------
    # OUTCOME ALIGNMENT
    # --------------------------------------------------------

    outcome_revision = make_outcome_revision(
        question,
        clo,
        plo,
        question_type
    )

    if outcome_revision:

        candidates.append(
            {
                "text": outcome_revision,
                "reason": (
                    "Strengthens the connection with the "
                    "stated learning outcome without "
                    "changing the subject or core question."
                ),
                "focus": "CLO/PLO Alignment",
            }
        )

    # --------------------------------------------------------
    # VALIDATE
    # --------------------------------------------------------

    original_score = evaluate_question(
        question,
        clo,
        plo,
        target_bloom,
        question_type
    )["Overall"]

    valid = []
    seen = set()

    for candidate in candidates:

        text = clean_text(
            candidate["text"]
        )

        key = normalize_text(
            text
        )

        if not key or key in seen:
            continue

        seen.add(key)

        safe = candidate_is_safe(
            question,
            text,
            clo,
            plo,
            target_bloom,
            question_type
        )

        if not safe:
            continue

        new_metrics = evaluate_question(
            text,
            clo,
            plo,
            target_bloom,
            question_type
        )

        preservation = preservation_score(
            question,
            text
        )

        gain = (
            new_metrics["Overall"]
            - original_score
        )

        candidate["text"] = text
        candidate["score"] = new_metrics
        candidate["gain"] = round(
            gain,
            1
        )
        candidate["preservation"] = round(
            preservation,
            1
        )

        valid.append(
            candidate
        )

    valid.sort(
        key=lambda item: (
            item["score"]["Overall"],
            item["preservation"]
        ),
        reverse=True
    )

    return valid[:3]


# ============================================================
# ANALYSIS
# ============================================================

def analyze_questions(
    questions,
    clos,
    plos,
    target_bloom
):
    results = []

    for index, question in enumerate(
        questions
    ):

        clo = ""

        if clos:
            clo = clos[
                index % len(clos)
            ]

        plo = ""

        if plos:
            plo = plos[
                index % len(plos)
            ]

        question_type = detect_question_type(
            question
        )

        metrics = evaluate_question(
            question,
            clo,
            plo,
            target_bloom,
            question_type
        )

        results.append(
            {
                "index": index,
                "question": question,
                "clo": clo,
                "plo": plo,
                **metrics,
            }
        )

    return results


def overall_score(analysis):
    if not analysis:
        return 0.0

    return round(
        sum(
            item["Overall"]
            for item in analysis
        )
        / len(analysis),
        1
    )


def score_status(score):
    if score >= ATTAINED_THRESHOLD:
        return "Attained"

    if score >= 50:
        return "Review"

    return "Needs Revision"


def score_icon(score):
    if score >= ATTAINED_THRESHOLD:
        return "🟢"

    if score >= 50:
        return "🟡"

    return "🔴"


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("🎓 OBE Quiz Checker")

    st.write(
        "Check quiz and assessment questions for "
        "CLO, PLO, Bloom's Taxonomy, relevance, "
        "clarity and measurability."
    )

    st.divider()

    target_bloom = st.selectbox(
        "Target Bloom Level",
        ["Auto"] + BLOOM_LEVELS
    )

    st.divider()

    st.caption(
        "Attainment Threshold"
    )

    st.success(
        "75% or above = Attained"
    )


# ============================================================
# HEADER
# ============================================================

st.title("🎓 OBE Quiz Checker")

st.write(
    "Check your assessment questions and improve weak "
    "questions with practical, context-preserving revisions."
)


# ============================================================
# ASSESSMENT INFORMATION
# ============================================================

st.header("1️⃣ Assessment Information")

col1, col2 = st.columns(2)

with col1:

    course_name = st.text_input(
        "Course / Subject",
        placeholder=(
            "e.g., Chemistry, English I, "
            "Programming, Mathematics"
        )
    )

with col2:

    assessment_name = st.text_input(
        "Assessment Name",
        placeholder=(
            "e.g., Quiz 1, Midterm, Final Exam"
        )
    )


# ============================================================
# LEARNING OUTCOMES
# ============================================================

st.header("2️⃣ Learning Outcomes")

col1, col2 = st.columns(2)

with col1:

    clo_text = st.text_area(
        "CLOs",
        height=180,
        placeholder=(
            "CLO 1: Explain fundamental concepts...\n"
            "CLO 2: Apply relevant principles...\n"
            "CLO 3: Analyze..."
        )
    )

with col2:

    plo_text = st.text_area(
        "PLOs",
        height=180,
        placeholder=(
            "PLO 1: Knowledge...\n"
            "PLO 2: Problem Analysis...\n"
            "PLO 3: Design..."
        )
    )


clos = parse_outcomes(
    clo_text
)

plos = parse_outcomes(
    plo_text
)


# ============================================================
# FILE UPLOAD
# ============================================================

st.header("3️⃣ Upload Complete Quiz / Assessment")

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
        "svg",
        "png",
        "jpg",
        "jpeg",
        "webp",
        "bmp",
        "tiff",
    ]
)


# ============================================================
# READ ASSESSMENT
# ============================================================

if uploaded_file is not None:

    if st.button(
        "📖 Read Assessment",
        use_container_width=True
    ):

        try:

            with st.spinner(
                "Reading your assessment..."
            ):

                extracted_text = read_uploaded_file(
                    uploaded_file
                )

            questions = extract_questions(
                extracted_text
            )

            st.session_state.assessment_text = (
                extracted_text
            )

            st.session_state.questions = (
                questions
            )

            st.session_state.analysis = []

            st.session_state.analysis_complete = False

            st.session_state.revision_options = []

            st.success(
                "Assessment successfully read. "
                f"{len(questions)} question(s) detected."
            )

        except Exception as error:

            st.error(
                f"Could not read the assessment: {error}"
            )


# ============================================================
# EXTRACTED TEXT
# ============================================================

if st.session_state.assessment_text:

    with st.expander(
        "📄 View Extracted Assessment"
    ):

        st.text(
            st.session_state.assessment_text[
                :15000
            ]
        )


# ============================================================
# ANALYZE
# ============================================================

st.header("4️⃣ Analyze Quiz")

if st.button(
    "🔍 Analyze Quiz",
    type="primary",
    use_container_width=True
):

    if not st.session_state.questions:

        st.warning(
            "Please upload and read an assessment first."
        )

    elif not clos and not plos:

        st.warning(
            "Please enter at least one CLO or PLO."
        )

    else:

        with st.spinner(
            "Analyzing the quiz questions..."
        ):

            analysis = analyze_questions(
                st.session_state.questions,
                clos,
                plos,
                target_bloom
            )

        st.session_state.analysis = analysis
        st.session_state.analysis_complete = True
        st.session_state.last_overall = None

        st.success(
            "Quiz analysis completed."
        )


# ============================================================
# MAIN RESULTS
# ============================================================

if st.session_state.analysis:

    analysis = st.session_state.analysis

    current_overall = overall_score(
        analysis
    )

    # --------------------------------------------------------
    # CELEBRATION
    # --------------------------------------------------------

    if st.session_state.celebrate_question:

        st.balloons()

        st.success(
            "🎉 This question has reached the "
            "Attained level!"
        )

        st.session_state.celebrate_question = False

    if st.session_state.celebrate_overall:

        st.balloons()

        st.success(
            "🎉 The overall quiz has reached "
            "the Attained level!"
        )

        st.session_state.celebrate_overall = False


    # ========================================================
    # OVERALL SCORE
    # ========================================================

    st.header("5️⃣ Overall OBE Alignment")

    if current_overall >= ATTAINED_THRESHOLD:

        st.success(
            f"🏆 Overall Score: "
            f"{current_overall:.0f}% — Attained"
        )

    elif current_overall >= 50:

        st.warning(
            f"🟡 Overall Score: "
            f"{current_overall:.0f}% — Review"
        )

    else:

        st.error(
            f"🔴 Overall Score: "
            f"{current_overall:.0f}% — Needs Revision"
        )


    # ========================================================
    # SCORE CARDS
    # ========================================================

    metric_names = [
        "CLO Match",
        "PLO Match",
        "Bloom",
        "Relevance",
        "Clarity",
        "Measurability",
    ]

    average_metrics = {}

    for metric in metric_names:

        average_metrics[metric] = round(
            sum(
                item[metric]
                for item in analysis
            )
            / len(analysis),
            1
        )

    metric_columns = st.columns(6)

    for column, metric in zip(
        metric_columns,
        metric_names
    ):

        with column:

            st.metric(
                metric,
                f"{average_metrics[metric]:.0f}%"
            )


    # ========================================================
    # ONE GRAPH
    # ========================================================

    st.subheader(
        "📈 Alignment Overview"
    )

    chart_df = pd.DataFrame(
        {
            "Metric": metric_names,
            "Score": [
                average_metrics[metric]
                for metric in metric_names
            ],
        }
    )

    st.bar_chart(
        chart_df.set_index(
            "Metric"
        )
    )


    # ========================================================
    # ATTAINED SECTION
    # ========================================================

    st.header("🏆 Attained")

    attained_questions = [
        item
        for item in analysis
        if item["Overall"] >= ATTAINED_THRESHOLD
    ]

    if attained_questions:

        st.success(
            f"{len(attained_questions)} "
            "question(s) have reached 75% or above."
        )

        for item in attained_questions:

            with st.expander(
                f"🟢 Q{item['index'] + 1} — "
                f"{item['Overall']:.0f}% — Attained"
            ):

                st.write(
                    item["question"]
                )

                st.caption(
                    f"Type: {item['Question Type']}"
                )

                st.caption(
                    f"CLO: {item['clo'] or 'Not specified'}"
                )

                st.caption(
                    f"PLO: {item['plo'] or 'Not specified'}"
                )

    else:

        st.info(
            "No questions have reached the "
            "75% Attained threshold yet."
        )


    # ========================================================
    # QUESTION IMPROVEMENT
    # ========================================================

    st.header("6️⃣ Improve a Question")

    st.write(
        "Select a question below. OBE Quiz Checker will "
        "automatically identify a practical improvement "
        "and preserve the original subject, topic and task."
    )

    question_options = []

    for item in analysis:

        label = (
            f"{score_icon(item['Overall'])} "
            f"Q{item['index'] + 1} — "
            f"{item['Overall']:.0f}% — "
            f"{item['Question Type']}"
        )

        question_options.append(
            label
        )

    selected_label = st.selectbox(
        "Select a question",
        question_options
    )

    selected_position = (
        question_options.index(
            selected_label
        )
    )

    selected_item = analysis[
        selected_position
    ]

    st.subheader(
        f"Q{selected_item['index'] + 1}"
    )

    st.info(
        selected_item["question"]
    )


    # --------------------------------------------------------
    # QUESTION METRICS
    # --------------------------------------------------------

    question_metric_columns = st.columns(6)

    for column, metric in zip(
        question_metric_columns,
        metric_names
    ):

        with column:

            st.metric(
                metric,
                f"{selected_item[metric]:.0f}%"
            )


    st.write(
        f"**Question Type:** "
        f"{selected_item['Question Type']}"
    )

    st.write(
        f"**CLO:** "
        f"{selected_item['clo'] or 'Not specified'}"
    )

    st.write(
        f"**PLO:** "
        f"{selected_item['plo'] or 'Not specified'}"
    )

    detected_verb, detected_bloom = find_bloom_verb(
        selected_item["question"]
    )

    bloom_text = detected_bloom

    if detected_verb:
        bloom_text += (
            f" ({detected_verb})"
        )

    st.write(
        f"**Detected Bloom Level:** {bloom_text}"
    )


    # ========================================================
    # GENERATE PRACTICAL REVISIONS
    # ========================================================

    if st.button(
        "✨ Generate Practical Revision",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "Creating a practical revision from "
            "the actual question..."
        ):

            revisions = generate_practical_revisions(
                selected_item["question"],
                selected_item["clo"],
                selected_item["plo"],
                target_bloom,
                selected_item["Question Type"]
            )

        st.session_state.revision_options = (
            revisions
        )

        st.session_state.revision_question_index = (
            selected_item["index"]
        )

        if revisions:

            st.success(
                f"{len(revisions)} practical revision(s) "
                "found."
            )

        else:

            st.warning(
                "No safe automatic revision was found. "
                "The tool did not generate an unrelated "
                "question because preserving the original "
                "context is more important."
            )


    # ========================================================
    # REVISION OPTIONS
    # ========================================================

    revisions = (
        st.session_state.revision_options
    )

    same_question = (
        st.session_state.revision_question_index
        == selected_item["index"]
    )

    if revisions and same_question:

        st.subheader(
            "✨ Practical Revision"
        )

        for revision_number, suggestion in enumerate(
            revisions
        ):

            st.markdown(
                f"### Revision {revision_number + 1}"
            )

            st.write(
                suggestion["text"]
            )

            st.info(
                "💡 "
                + suggestion["reason"]
            )

            st.caption(
                f"Focus: {suggestion['focus']} | "
                f"Context preserved: "
                f"{suggestion['preservation']:.0f}%"
            )

            # ------------------------------------------------
            # USE REVISION
            # ------------------------------------------------

            if st.button(
                "✅ Use This Revision",
                key=(
                    f"use_revision_"
                    f"{selected_item['index']}_"
                    f"{revision_number}"
                ),
                use_container_width=True
            ):

                old_question_score = (
                    selected_item["Overall"]
                )

                old_overall = overall_score(
                    analysis
                )

                question_index = (
                    selected_item["index"]
                )

                revised_question = (
                    suggestion["text"]
                )

                # Replace the actual question
                st.session_state.questions[
                    question_index
                ] = revised_question

                # Re-analyze entire quiz
                updated_analysis = analyze_questions(
                    st.session_state.questions,
                    clos,
                    plos,
                    target_bloom
                )

                new_question_score = (
                    updated_analysis[
                        question_index
                    ]["Overall"]
                )

                new_overall = overall_score(
                    updated_analysis
                )

                st.session_state.analysis = (
                    updated_analysis
                )

                st.session_state.revision_options = []

                st.session_state.revision_question_index = None

                # ------------------------------------------------
                # ATTAINMENT TRANSITIONS
                # ------------------------------------------------

                if (
                    old_question_score
                    < ATTAINED_THRESHOLD
                    and new_question_score
                    >= ATTAINED_THRESHOLD
                ):

                    st.session_state.celebrate_question = True

                if (
                    old_overall
                    < ATTAINED_THRESHOLD
                    and new_overall
                    >= ATTAINED_THRESHOLD
                ):

                    st.session_state.celebrate_overall = True

                # Store latest overall
                st.session_state.last_overall = (
                    new_overall
                )

                # Show immediate score change
                st.success(
                    f"Question score changed from "
                    f"{old_question_score:.0f}% "
                    f"→ "
                    f"{new_question_score:.0f}%"
                )

                if (
                    new_question_score
                    >= ATTAINED_THRESHOLD
                ):

                    st.success(
                        "🟢 Attained 🎉"
                    )

                elif new_question_score >= 50:

                    st.warning(
                        "🟡 Review"
                    )

                else:

                    st.error(
                        "🔴 Needs Revision"
                    )

                st.rerun()

            st.divider()


    # ========================================================
    # ASSESSMENT OVERVIEW
    # ========================================================

    st.header("7️⃣ Assessment Overview")

    overview_rows = []

    for item in analysis:

        overview_rows.append(
            {
                "Question": (
                    f"Q{item['index'] + 1}"
                ),
                "Type": item["Question Type"],
                "CLO": item["CLO Match"],
                "PLO": item["PLO Match"],
                "Bloom": item["Bloom"],
                "Relevance": item["Relevance"],
                "Clarity": item["Clarity"],
                "Measurability": item["Measurability"],
                "Overall": item["Overall"],
                "Status": score_status(
                    item["Overall"]
                ),
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
    # QUESTIONS NEEDING REVISION
    # ========================================================

    questions_needing_revision = [
        item
        for item in analysis
        if item["Overall"] < ATTAINED_THRESHOLD
    ]

    if questions_needing_revision:

        st.subheader(
            "🛠 Questions Needing Attention"
        )

        sorted_questions = sorted(
            questions_needing_revision,
            key=lambda item: item["Overall"]
        )

        for item in sorted_questions[:10]:

            st.write(
                f"{score_icon(item['Overall'])} "
                f"**Q{item['index'] + 1} — "
                f"{item['Overall']:.0f}%**"
            )

            st.caption(
                item["question"]
            )


    # ========================================================
    # SUMMARY
    # ========================================================

    st.header("8️⃣ Summary")

    total_questions = len(
        analysis
    )

    attained_count = len(
        [
            item
            for item in analysis
            if item["Overall"]
            >= ATTAINED_THRESHOLD
        ]
    )

    revision_count = (
        total_questions
        - attained_count
    )

    summary_columns = st.columns(3)

    with summary_columns[0]:

        st.metric(
            "Total Questions",
            total_questions
        )

    with summary_columns[1]:

        st.metric(
            "Attained",
            attained_count
        )

    with summary_columns[2]:

        st.metric(
            "Need Revision",
            revision_count
        )


    # ========================================================
    # EXPORT
    # ========================================================

    st.header("9️⃣ Export")

    export_rows = []

    for item in analysis:

        export_rows.append(
            {
                "Question Number": (
                    item["index"] + 1
                ),
                "Question": item["question"],
                "Question Type": item["Question Type"],
                "CLO": item["clo"],
                "PLO": item["plo"],
                "CLO Match": item["CLO Match"],
                "PLO Match": item["PLO Match"],
                "Bloom": item["Bloom"],
                "Relevance": item["Relevance"],
                "Clarity": item["Clarity"],
                "Measurability": item["Measurability"],
                "Overall": item["Overall"],
                "Status": score_status(
                    item["Overall"]
                ),
            }
        )

    export_df = pd.DataFrame(
        export_rows
    )

    csv_data = export_df.to_csv(
        index=False
    ).encode(
        "utf-8"
    )

    st.download_button(
        "⬇️ Download OBE Quiz Report",
        data=csv_data,
        file_name="obe_quiz_checker_report.csv",
        mime="text/csv",
        use_container_width=True
    )


# ============================================================
# INITIAL MESSAGE
# ============================================================

if not st.session_state.analysis:

    st.info(
        "Start by entering your CLOs/PLOs, uploading the "
        "complete quiz or assessment, and clicking "
        "**Read Assessment** followed by **Analyze Quiz**."
    )
