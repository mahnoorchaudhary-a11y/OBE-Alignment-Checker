import streamlit as st
import pandas as pd
import re
import io
import os
import math
from collections import Counter

# ============================================================
# OPTIONAL LIBRARIES
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
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Checker",
    page_icon="🎓",
    layout="wide"
)


# ============================================================
# CONSTANTS
# ============================================================

ATTAINMENT_THRESHOLD = 75
OVERALL_BALLOON_THRESHOLD = 80

BLOOM_LEVELS = {
    "remember": 1,
    "understand": 2,
    "apply": 3,
    "analyze": 4,
    "evaluate": 5,
    "create": 6
}

BLOOM_VERBS = {
    "remember": [
        "define", "identify", "list", "name", "state",
        "recall", "recognize", "mention", "select"
    ],
    "understand": [
        "describe", "explain", "summarize", "summarise",
        "discuss", "interpret", "classify", "illustrate"
    ],
    "apply": [
        "apply", "calculate", "solve", "demonstrate",
        "use", "implement", "execute", "compute"
    ],
    "analyze": [
        "analyze", "analyse", "examine", "differentiate",
        "compare", "contrast", "investigate", "break down"
    ],
    "evaluate": [
        "evaluate", "assess", "judge", "critique",
        "justify", "defend", "appraise", "recommend"
    ],
    "create": [
        "create", "design", "develop", "construct",
        "formulate", "produce", "propose", "generate"
    ]
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on",
    "for", "with", "from", "by", "is", "are", "was", "were",
    "be", "been", "being", "this", "that", "these", "those",
    "as", "at", "it", "its", "into", "their", "there", "which",
    "what", "how", "why", "when", "where", "who", "whom",
    "can", "could", "should", "would", "will", "may", "might",
    "do", "does", "did", "you", "your", "we", "our", "they",
    "them", "he", "she", "his", "her", "than", "then",
    "also", "using", "use", "following", "given"
}

ACTION_VERBS = {
    "define", "identify", "list", "name", "state", "recall",
    "recognize", "describe", "explain", "summarize", "summarise",
    "discuss", "interpret", "classify", "illustrate", "apply",
    "calculate", "solve", "demonstrate", "implement", "execute",
    "compute", "analyze", "analyse", "examine", "differentiate",
    "compare", "contrast", "investigate", "evaluate", "assess",
    "judge", "critique", "justify", "defend", "appraise",
    "recommend", "create", "design", "develop", "construct",
    "formulate", "produce", "propose", "generate"
}


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "questions": [],
    "analysis": [],
    "uploaded_text": "",
    "analyzed": False,
    "revision_candidates": {},
    "accepted_revisions": {},
    "last_overall_score": None,
    "balloons_question_keys": set(),
    "overall_balloons_shown": False,
    "file_name": ""
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# GENERAL TEXT UTILITIES
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\x00", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_text(text):
    text = clean_text(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def meaningful_words(text):
    words = re.findall(
        r"[A-Za-z][A-Za-z0-9'-]+",
        str(text).lower()
    )

    return [
        word for word in words
        if word not in STOPWORDS and len(word) > 2
    ]


def word_set(text):
    return set(meaningful_words(text))


def sentence_count(text):
    parts = re.split(r"[.!?]+", str(text))
    return len([p for p in parts if p.strip()])


def get_numbers(text):
    return re.findall(
        r"\b\d+(?:\.\d+)?\b",
        str(text)
    )


def safe_percentage(value):
    try:
        return max(0.0, min(100.0, float(value)))
    except Exception:
        return 0.0


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text):
    if not text:
        return []

    text = text.replace("\r", "\n")

    lines = []

    for line in text.split("\n"):
        line = normalize_text(line)

        if not line:
            continue

        line = re.sub(
            r"^(?:[-•*]|\d+[\.\)]|CLO\s*\d*[:\-]?|PLO\s*\d*[:\-]?)\s*",
            "",
            line,
            flags=re.I
        )

        if len(line) >= 5:
            lines.append(line)

    if not lines:
        return [normalize_text(text)]

    return lines


# ============================================================
# BLOOM TAXONOMY
# ============================================================

def detect_bloom(text):
    text_lower = str(text).lower()

    found = []

    for level, verbs in BLOOM_VERBS.items():
        for verb in verbs:
            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                text_lower
            ):
                found.append((level, verb))

    if not found:
        return "understand", "unknown"

    priority = {
        "remember": 1,
        "understand": 2,
        "apply": 3,
        "analyze": 4,
        "evaluate": 5,
        "create": 6
    }

    found.sort(
        key=lambda item: priority[item[0]],
        reverse=True
    )

    return found[0]


def bloom_distance_score(actual, target):
    if not actual or not target:
        return 78.0

    if actual not in BLOOM_LEVELS or target not in BLOOM_LEVELS:
        return 78.0

    difference = abs(
        BLOOM_LEVELS[actual] -
        BLOOM_LEVELS[target]
    )

    if difference == 0:
        return 100.0

    if difference == 1:
        return 92.0

    if difference == 2:
        return 84.0

    if difference == 3:
        return 78.0

    return 72.0


def extract_target_bloom(outcomes):
    if not outcomes:
        return "understand"

    combined = " ".join(outcomes)
    level, _ = detect_bloom(combined)

    return level


# ============================================================
# QUESTION TYPE DETECTION
# ============================================================

def detect_question_type(question):
    text = normalize_text(question)
    lower = text.lower()

    option_pattern = re.findall(
        r"(?im)^\s*(?:[A-D][\.\)]|[1-4][\.\)])\s+.+$",
        str(question)
    )

    if len(option_pattern) >= 2:
        return "MCQ"

    if re.search(
        r"\b(true\s*/\s*false|true or false)\b",
        lower
    ):
        return "True/False"

    if (
        "_" in text
        or "fill in the blank" in lower
        or "fill the blank" in lower
    ):
        return "Fill in the Blank"

    if (
        "case study" in lower
        or "read the case" in lower
        or "scenario" in lower
        or "case:" in lower
    ):
        return "Case Study"

    if re.search(
        r"\b(calculate|compute|solve|find|determine)\b",
        lower
    ):
        if (
            re.search(r"\d", text)
            or re.search(
                r"\b(equation|formula|velocity|speed|force|mass|"
                r"distance|time|probability|percentage|mean|average)\b",
                lower
            )
        ):
            return "Numerical"

    if re.search(
        r"\b(design|develop|construct|implement|perform|demonstrate)\b",
        lower
    ):
        return "Practical/Application"

    if len(text.split()) > 45:
        return "Essay/Long Answer"

    if re.search(
        r"\b(essay|write an essay|write a detailed|in detail)\b",
        lower
    ):
        return "Essay/Long Answer"

    return "Short Answer"


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def split_question_blocks(text):
    text = clean_text(text)

    if not text:
        return []

    lines = text.split("\n")

    blocks = []
    current = []

    question_start = re.compile(
        r"^\s*(?:"
        r"Q(?:uestion)?\s*\d+"
        r"|Question\s+\d+"
        r"|\d+[\.\)]"
        r"|[A-Z][\.\)]"
        r")\s*",
        re.I
    )

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if current:
                current.append("")
            continue

        if question_start.match(stripped) and current:
            block = "\n".join(current).strip()

            if len(block) > 15:
                blocks.append(block)

            current = [stripped]
        else:
            current.append(stripped)

    if current:
        block = "\n".join(current).strip()

        if len(block) > 15:
            blocks.append(block)

    return blocks


def extract_questions(text):
    text = clean_text(text)

    if not text:
        return []

    questions = []

    blocks = split_question_blocks(text)

    # --------------------------------------------------------
    # First method: explicit numbered questions
    # --------------------------------------------------------

    if blocks:
        for block in blocks:
            cleaned = re.sub(
                r"^\s*(?:Question\s*)?\d+[\.\):\-]?\s*",
                "",
                block,
                flags=re.I
            )

            if len(normalize_text(cleaned)) >= 10:
                questions.append(normalize_text(cleaned))

    # --------------------------------------------------------
    # Second method: question marks
    # --------------------------------------------------------

    if len(questions) < 2:
        candidates = re.split(
            r"(?<=[?])\s+",
            text
        )

        for candidate in candidates:
            candidate = normalize_text(candidate)

            if len(candidate) >= 15:
                if (
                    "?" in candidate
                    or re.match(
                        r"(?i)^(define|explain|describe|discuss|"
                        r"calculate|analyze|analyse|evaluate|"
                        r"compare|identify|what|why|how|which|"
                        r"determine|state)\b",
                        candidate
                    )
                ):
                    if candidate not in questions:
                        questions.append(candidate)

    # --------------------------------------------------------
    # Third method: line-based fallback
    # --------------------------------------------------------

    if not questions:
        for line in text.splitlines():
            line = normalize_text(line)

            if len(line) < 15:
                continue

            if re.match(
                r"(?i)^(define|explain|describe|discuss|"
                r"calculate|analyze|analyse|evaluate|compare|"
                r"identify|what|why|how|which|determine|state)\b",
                line
            ):
                questions.append(line)

    # --------------------------------------------------------
    # Remove obvious non-question headings
    # --------------------------------------------------------

    filtered = []

    heading_words = {
        "quiz", "assessment", "examination", "exam",
        "instructions", "section", "course", "name",
        "date", "semester", "marks", "total marks"
    }

    for question in questions:
        lower = question.lower()

        if len(question.split()) <= 2:
            continue

        if lower in heading_words:
            continue

        filtered.append(question)

    # Deduplicate while preserving order.
    unique = []

    for question in filtered:
        if question not in unique:
            unique.append(question)

    return unique


# ============================================================
# FILE READERS
# ============================================================

def read_pdf(uploaded_file):
    if fitz is None:
        return (
            "",
            "PyMuPDF is not installed. Add PyMuPDF to requirements.txt."
        )

    try:
        data = uploaded_file.read()
        document = fitz.open(
            stream=data,
            filetype="pdf"
        )

        pages = []

        for page in document:
            page_text = page.get_text("text")

            if page_text and page_text.strip():
                pages.append(page_text)
            else:
                if pytesseract is not None and Image is not None:
                    try:
                        pix = page.get_pixmap(
                            matrix=fitz.Matrix(2, 2),
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

                        if ocr_text.strip():
                            pages.append(ocr_text)

                    except Exception:
                        pass

        document.close()

        return clean_text("\n\n".join(pages)), None

    except Exception as exc:
        return "", f"Could not read PDF: {exc}"


def read_docx(uploaded_file):
    if Document is None:
        return (
            "",
            "python-docx is not installed."
        )

    try:
        data = uploaded_file.read()
        document = Document(
            io.BytesIO(data)
        )

        paragraphs = []

        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                paragraphs.append(paragraph.text)

        for table in document.tables:
            for row in table.rows:
                values = []

                for cell in row.cells:
                    values.append(cell.text)

                paragraphs.append(" | ".join(values))

        return clean_text("\n".join(paragraphs)), None

    except Exception as exc:
        return "", f"Could not read DOCX: {exc}"


def read_pptx(uploaded_file):
    if Presentation is None:
        return (
            "",
            "python-pptx is not installed."
        )

    try:
        data = uploaded_file.read()

        presentation = Presentation(
            io.BytesIO(data)
        )

        slides = []

        for slide in presentation.slides:
            slide_text = []

            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    if shape.text.strip():
                        slide_text.append(shape.text)

            if slide_text:
                slides.append("\n".join(slide_text))

        return clean_text("\n\n".join(slides)), None

    except Exception as exc:
        return "", f"Could not read PPTX: {exc}"


def read_excel(uploaded_file):
    try:
        data = uploaded_file.read()

        workbook = pd.ExcelFile(
            io.BytesIO(data)
        )

        sections = []

        for sheet in workbook.sheet_names:
            dataframe = pd.read_excel(
                io.BytesIO(data),
                sheet_name=sheet,
                header=None
            )

            sections.append(
                f"Sheet: {sheet}\n"
                + dataframe.fillna("").astype(str).to_string(
                    index=False,
                    header=False
                )
            )

        return clean_text(
            "\n\n".join(sections)
        ), None

    except Exception as exc:
        return "", f"Could not read spreadsheet: {exc}"


def read_text_file(uploaded_file):
    try:
        data = uploaded_file.read()

        return data.decode(
            "utf-8",
            errors="ignore"
        ), None

    except Exception as exc:
        return "", f"Could not read text file: {exc}"


def read_image(uploaded_file):
    if Image is None:
        return (
            "",
            "Pillow is not installed."
        )

    if pytesseract is None:
        return (
            "",
            "pytesseract is not installed."
        )

    try:
        image = Image.open(
            uploaded_file
        )

        text = pytesseract.image_to_string(
            image
        )

        return clean_text(text), None

    except Exception as exc:
        return "", f"Could not read image: {exc}"


def read_uploaded_file(uploaded_file):
    extension = os.path.splitext(
        uploaded_file.name
    )[1].lower()

    if extension == ".pdf":
        return read_pdf(uploaded_file)

    if extension == ".docx":
        return read_docx(uploaded_file)

    if extension == ".pptx":
        return read_pptx(uploaded_file)

    if extension in [".xlsx", ".xls", ".csv"]:
        if extension == ".csv":
            return read_text_file(uploaded_file)

        return read_excel(uploaded_file)

    if extension in [
        ".txt",
        ".md"
    ]:
        return read_text_file(uploaded_file)

    if extension in [
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
        ".tiff"
    ]:
        return read_image(uploaded_file)

    return "", "Unsupported file type."


# ============================================================
# OUTCOME MATCHING
# ============================================================

def semantic_match(question, outcome):
    q_words = word_set(question)
    o_words = word_set(outcome)

    if not q_words or not o_words:
        return 0.0

    intersection = q_words.intersection(o_words)

    # Recall from the outcome perspective.
    outcome_coverage = (
        len(intersection) /
        max(1, len(o_words))
    )

    # Precision from question perspective.
    question_coverage = (
        len(intersection) /
        max(1, len(q_words))
    )

    score = (
        0.65 * outcome_coverage
        + 0.35 * question_coverage
    )

    return max(
        0.0,
        min(1.0, score)
    )


def score_outcome_match(question, outcomes):
    if not outcomes:
        return 80.0, "", ""

    scores = []

    for outcome in outcomes:
        match = semantic_match(
            question,
            outcome
        )

        scores.append(
            (match, outcome)
        )

    scores.sort(
        key=lambda item: item[0],
        reverse=True
    )

    best_match, best_outcome = scores[0]

    if best_match >= 0.70:
        score = 95.0
    elif best_match >= 0.50:
        score = 88.0
    elif best_match >= 0.35:
        score = 78.0
    elif best_match >= 0.20:
        score = 68.0
    elif best_match > 0:
        score = 60.0
    else:
        score = 55.0

    return score, best_outcome, best_match


# ============================================================
# CLARITY
# ============================================================

def score_clarity(question):
    text = normalize_text(question)

    if not text:
        return 0.0

    score = 98.0
    lower = text.lower()

    vague_phrases = [
        "discuss this",
        "explain this",
        "write something",
        "say something",
        "comment on it",
        "do the needful",
        "what do you think about this"
    ]

    for phrase in vague_phrases:
        if phrase in lower:
            score -= 8

    if len(text.split()) > 90:
        score -= 5

    if "??" in text:
        score -= 3

    if re.search(
        r"\b(etc|and so on)\b",
        lower
    ):
        score -= 3

    if re.search(
        r"\b(as discussed above|as mentioned earlier)\b",
        lower
    ):
        score -= 2

    return safe_percentage(score)


# ============================================================
# MEASURABILITY
# ============================================================

def score_measurability(question):
    text = normalize_text(question)
    lower = text.lower()

    if not text:
        return 0.0

    q_type = detect_question_type(text)

    clear_verbs = []

    for level_verbs in BLOOM_VERBS.values():
        clear_verbs.extend(level_verbs)

    has_action = any(
        re.search(
            r"\b" + re.escape(verb) + r"\b",
            lower
        )
        for verb in clear_verbs
    )

    score = 92.0

    if has_action:
        score += 5

    if q_type in [
        "MCQ",
        "True/False",
        "Numerical"
    ]:
        score += 2

    if re.search(
        r"(?i)\b(show|state|identify|calculate|"
        r"compare|justify|support|explain)\b",
        lower
    ):
        score += 1

    return safe_percentage(score)


# ============================================================
# RELEVANCE
# ============================================================

def score_relevance(question, clo_score, plo_score):
    if clo_score is None and plo_score is None:
        return 85.0

    values = []

    if clo_score is not None:
        values.append(clo_score)

    if plo_score is not None:
        values.append(plo_score)

    if not values:
        return 85.0

    base = sum(values) / len(values)

    # Keep relevance lenient.
    return safe_percentage(
        70 + (base * 0.30)
    )


# ============================================================
# QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question,
    clos,
    plos
):
    question = normalize_text(question)

    q_type = detect_question_type(
        question
    )

    bloom_level, bloom_verb = detect_bloom(
        question
    )

    target_bloom = extract_target_bloom(
        clos
    )

    bloom_score = bloom_distance_score(
        bloom_level,
        target_bloom
    )

    clo_score, best_clo, clo_raw = score_outcome_match(
        question,
        clos
    )

    plo_score, best_plo, plo_raw = score_outcome_match(
        question,
        plos
    )

    clarity = score_clarity(
        question
    )

    measurability = score_measurability(
        question
    )

    relevance = score_relevance(
        question,
        clo_score,
        plo_score
    )

    overall = (
        clo_score * 0.20
        + plo_score * 0.15
        + bloom_score * 0.20
        + relevance * 0.15
        + clarity * 0.15
        + measurability * 0.15
    )

    return {
        "Question": question,
        "Question Type": q_type,
        "Bloom Level": bloom_level.title(),
        "Bloom Verb": bloom_verb,
        "Target Bloom": target_bloom.title(),
        "CLO Match": round(clo_score, 1),
        "PLO Match": round(plo_score, 1),
        "Bloom Score": round(bloom_score, 1),
        "Relevance": round(relevance, 1),
        "Clarity": round(clarity, 1),
        "Measurability": round(measurability, 1),
        "Overall Alignment": round(
            safe_percentage(overall),
            1
        ),
        "Best CLO": best_clo,
        "Best PLO": best_plo,
        "CLO Raw Match": clo_raw,
        "PLO Raw Match": plo_raw
    }


def analyze_questions(
    questions,
    clos,
    plos
):
    results = []

    for index, question in enumerate(
        questions,
        start=1
    ):
        result = evaluate_question(
            question,
            clos,
            plos
        )

        result["Question Number"] = index

        results.append(result)

    return results


def calculate_overall_score(results):
    if not results:
        return 0.0

    scores = [
        safe_percentage(
            result.get(
                "Overall Alignment",
                0
            )
        )
        for result in results
    ]

    return round(
        sum(scores) / len(scores),
        1
    )


# ============================================================
# STATUS
# ============================================================

def score_status(score):
    score = safe_percentage(score)

    if score >= 85:
        return "🟢 Strong"

    if score >= 75:
        return "🏆 Attained"

    if score >= 65:
        return "🟡 Minor Revision"

    if score >= 50:
        return "🟠 Review"

    return "🔴 Needs Revision"


def weakest_dimension(result):
    dimensions = {
        "CLO Match": result.get("CLO Match", 100),
        "PLO Match": result.get("PLO Match", 100),
        "Bloom Score": result.get("Bloom Score", 100),
        "Relevance": result.get("Relevance", 100),
        "Clarity": result.get("Clarity", 100),
        "Measurability": result.get("Measurability", 100)
    }

    return min(
        dimensions,
        key=dimensions.get
    )


# ============================================================
# REVISION ENGINE
# ============================================================

def extract_clo_concepts(clo):
    words = meaningful_words(clo)

    return [
        word
        for word in words
        if word not in ACTION_VERBS
    ]


def extract_clo_action(clo):
    text = str(clo).lower()

    ordered_actions = [
        (
            "create",
            [
                "create",
                "design",
                "develop",
                "construct",
                "formulate"
            ]
        ),
        (
            "evaluate",
            [
                "evaluate",
                "assess",
                "critique",
                "judge",
                "justify"
            ]
        ),
        (
            "analyze",
            [
                "analyze",
                "analyse",
                "examine",
                "differentiate"
            ]
        ),
        (
            "apply",
            [
                "apply",
                "demonstrate",
                "use",
                "solve",
                "calculate"
            ]
        ),
        (
            "understand",
            [
                "explain",
                "describe",
                "summarize",
                "summarise"
            ]
        ),
        (
            "remember",
            [
                "define",
                "identify",
                "list",
                "state",
                "name"
            ]
        )
    ]

    for level, verbs in ordered_actions:
        for verb in verbs:
            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                text
            ):
                return level, verb

    return "understand", "explain"


def preserve_numbers(original, revised):
    original_numbers = get_numbers(
        original
    )

    revised_numbers = get_numbers(
        revised
    )

    return original_numbers == revised_numbers


def extract_mcq_options(text):
    return re.findall(
        r"(?im)^\s*(?:[A-D][\.\)]|[1-4][\.\)])\s+(.+)$",
        str(text)
    )


def preserve_mcq_options(original, revised):
    original_options = extract_mcq_options(
        original
    )

    if not original_options:
        return True

    revised_options = extract_mcq_options(
        revised
    )

    if len(revised_options) != len(
        original_options
    ):
        return False

    for original_option in original_options:
        if normalize_text(
            original_option
        ).lower() not in normalize_text(
            revised
        ).lower():
            return False

    return True


def validate_topic_preservation(
    original,
    revised
):
    original_words = word_set(
        original
    )

    revised_words = word_set(
        revised
    )

    if not original_words:
        return True

    overlap = len(
        original_words.intersection(
            revised_words
        )
    ) / max(
        1,
        len(original_words)
    )

    return overlap >= 0.20


def validate_question_type(
    original,
    revised
):
    original_type = detect_question_type(
        original
    )

    revised_type = detect_question_type(
        revised
    )

    # Numerical and short-answer transformations can sometimes
    # be classified differently after wording changes.
    if original_type == revised_type:
        return True

    if original_type == "Numerical":
        return revised_type in [
            "Numerical",
            "Short Answer"
        ]

    if original_type == "Short Answer":
        return revised_type in [
            "Short Answer",
            "Essay/Long Answer"
        ]

    return False


def validate_revision(
    original,
    revised
):
    if not revised:
        return False

    original = normalize_text(
        original
    )

    revised = normalize_text(
        revised
    )

    if original == revised:
        return False

    if not preserve_numbers(
        original,
        revised
    ):
        return False

    if not preserve_mcq_options(
        original,
        revised
    ):
        return False

    if not validate_topic_preservation(
        original,
        revised
    ):
        return False

    if not validate_question_type(
        original,
        revised
    ):
        return False

    return True


# ============================================================
# CLO-DRIVEN REVISION
# ============================================================

def build_clo_revision(
    question,
    clo,
    q_type
):
    question = normalize_text(
        question
    )

    clo = normalize_text(
        clo
    )

    if not clo:
        return ""

    action_level, action = extract_clo_action(
        clo
    )

    concepts = extract_clo_concepts(
        clo
    )

    # --------------------------------------------------------
    # MCQ
    # --------------------------------------------------------

    if q_type == "MCQ":
        options = extract_mcq_options(
            question
        )

        stem = re.split(
            r"(?im)^\s*(?:[A-D][\.\)]|[1-4][\.\)])\s+",
            question
        )[0].strip()

        stem = re.sub(
            r"^\s*(?:Question\s*)?\d+[\.\):\-]?\s*",
            "",
            stem,
            flags=re.I
        )

        stem = stem.rstrip(
            ".? "
        )

        if action_level == "analyze":
            new_stem = (
                "Which option best analyzes "
                + stem
                + "?"
            )

        elif action_level == "evaluate":
            new_stem = (
                "Which option best evaluates "
                + stem
                + "?"
            )

        elif action_level == "apply":
            new_stem = (
                "Which option best applies the relevant "
                "concept to "
                + stem
                + "?"
            )

        else:
            new_stem = (
                action.capitalize()
                + " "
                + stem
                + "."
            )

        if options:
            letters = "ABCD"

            formatted = [
                new_stem
            ]

            for index, option in enumerate(
                options
            ):
                if index < 4:
                    formatted.append(
                        letters[index]
                        + ". "
                        + option
                    )
                else:
                    formatted.append(
                        str(index + 1)
                        + ". "
                        + option
                    )

            return "\n".join(
                formatted
            )

        return new_stem

    # --------------------------------------------------------
    # TRUE / FALSE
    # --------------------------------------------------------

    if q_type == "True/False":
        body = re.sub(
            r"(?i)\b(true\s*/\s*false|true or false)\b",
            "",
            question
        ).strip()

        body = body.rstrip(
            ".? "
        )

        return (
            "Determine whether the following statement is correct: "
            + body
            + ". (True/False)"
        )

    # --------------------------------------------------------
    # FILL IN THE BLANK
    # --------------------------------------------------------

    if q_type == "Fill in the Blank":
        if "_" in question:
            return question

        return (
            question.rstrip(".? ")
            + ": __________"
        )

    # --------------------------------------------------------
    # NUMERICAL
    # --------------------------------------------------------

    if q_type == "Numerical":
        lower = question.lower()

        if (
            "show" in lower
            and "step" in lower
            and "unit" in lower
        ):
            return question

        return (
            question.rstrip(".? ")
            + ". Show the calculation steps and state "
              "the final answer with the appropriate unit."
        )

    # --------------------------------------------------------
    # CASE STUDY
    # --------------------------------------------------------

    if q_type == "Case Study":
        base = question.rstrip(
            ".? "
        )

        if action_level == "analyze":
            return (
                base
                + ". Analyze the case by identifying the key "
                  "factors involved and support your answer "
                  "with evidence from the case."
            )

        if action_level == "evaluate":
            return (
                base
                + ". Evaluate the situation using the relevant "
                  "concepts and support your judgment with "
                  "evidence from the case."
            )

        if action_level == "apply":
            return (
                base
                + ". Apply the relevant concept to the case "
                  "and explain your answer."
            )

        return (
            base
            + ". Explain your answer using the relevant "
              "concepts identified in the learning outcome."
        )

    # --------------------------------------------------------
    # ESSAY
    # --------------------------------------------------------

    if q_type == "Essay/Long Answer":

        if action_level == "evaluate":
            return (
                "Evaluate "
                + question.rstrip(".? ")
                + " and support your evaluation with relevant reasons."
            )

        if action_level == "analyze":
            return (
                "Analyze "
                + question.rstrip(".? ")
                + " by examining the key concepts involved."
            )

        if action_level == "apply":
            return (
                "Apply the relevant concepts to "
                + question.rstrip(".? ")
                + " and explain your application."
            )

        if action_level == "create":
            return (
                "Develop a response to "
                + question.rstrip(".? ")
                + " that addresses the key concepts required "
                  "by the learning outcome."
            )

        return (
            action.capitalize()
            + " "
            + question.rstrip(".? ")
            + " with reference to the key concepts "
              "required by the learning outcome."
        )

    # --------------------------------------------------------
    # SHORT ANSWER
    # --------------------------------------------------------

    base = question.rstrip(
        ".? "
    )

    if action_level == "evaluate":
        return (
            "Evaluate "
            + base
            + " and support your evaluation with relevant reasons."
        )

    if action_level == "analyze":
        return (
            "Analyze "
            + base
            + " by identifying the key factors involved."
        )

    if action_level == "apply":
        return (
            "Apply the relevant concept to "
            + base
            + " and explain your answer."
        )

    if action_level == "create":
        return (
            "Develop a response to "
            + base
            + " using the relevant concepts from the course."
        )

    # Directly use the CLO as a question.
    # This avoids generic "relate your answer to CLO" wording.
    return clo.rstrip(
        ".? "
    ) + "."


def generate_clo_revision(
    question,
    clo
):
    """
    This is the mandatory CLO revision route.

    When CLO is below 75%, the tool does not return None.
    It tries several practical candidates and always has a
    context-preserving fallback.
    """

    q_type = detect_question_type(
        question
    )

    candidates = []

    primary = build_clo_revision(
        question,
        clo,
        q_type
    )

    candidates.append(
        primary
    )

    action_level, action = extract_clo_action(
        clo
    )

    base = normalize_text(
        question
    ).rstrip(".? ")

    if q_type not in [
        "MCQ",
        "True/False",
        "Fill in the Blank"
    ]:

        if action_level == "understand":
            candidates.append(
                "Explain "
                + base
                + " and address the key concept specified "
                  "in the course learning outcome."
            )

        elif action_level == "apply":
            candidates.append(
                "Apply the relevant concept to "
                + base
                + " and explain your answer."
            )

        elif action_level == "analyze":
            candidates.append(
                "Analyze "
                + base
                + " by identifying the key factors and "
                  "relationships involved."
            )

        elif action_level == "evaluate":
            candidates.append(
                "Evaluate "
                + base
                + " and support your judgment with relevant reasons."
            )

        elif action_level == "create":
            candidates.append(
                "Develop a response to "
                + base
                + " that addresses the required learning outcome."
            )

    for candidate in candidates:
        candidate = normalize_text(
            candidate
        )

        if validate_revision(
            question,
            candidate
        ):
            return candidate

    # --------------------------------------------------------
    # MANDATORY FALLBACK
    # --------------------------------------------------------

    fallback = (
        base
        + ". Explain the answer using the concepts and skills "
          "required by the course learning outcome."
    )

    return fallback


# ============================================================
# OTHER REVISION ROUTES
# ============================================================

def generate_bloom_revision(
    question,
    target_bloom
):
    question = normalize_text(
        question
    )

    q_type = detect_question_type(
        question
    )

    base = question.rstrip(
        ".? "
    )

    target = str(
        target_bloom
    ).lower()

    if q_type == "MCQ":
        options = extract_mcq_options(
            question
        )

        stem = re.split(
            r"(?im)^\s*(?:[A-D][\.\)]|[1-4][\.\)])\s+",
            question
        )[0].strip()

        stem = stem.rstrip(
            ".? "
        )

        if target == "analyze":
            new_stem = (
                "Which option best analyzes "
                + stem
                + "?"
            )
        elif target == "evaluate":
            new_stem = (
                "Which option best evaluates "
                + stem
                + "?"
            )
        elif target == "apply":
            new_stem = (
                "Which option best applies the relevant "
                "concept to "
                + stem
                + "?"
            )
        else:
            new_stem = (
                "Which option best explains "
                + stem
                + "?"
            )

        if options:
            letters = "ABCD"
            output = [new_stem]

            for i, option in enumerate(options):
                if i < 4:
                    output.append(
                        letters[i]
                        + ". "
                        + option
                    )
                else:
                    output.append(
                        str(i + 1)
                        + ". "
                        + option
                    )

            return "\n".join(output)

        return new_stem

    if target == "understand":
        return (
            "Explain "
            + base
            + " and describe the key idea involved."
        )

    if target == "apply":
        return (
            "Apply the relevant concept to "
            + base
            + " and explain your answer."
        )

    if target == "analyze":
        return (
            "Analyze "
            + base
            + " by identifying the key factors involved."
        )

    if target == "evaluate":
        return (
            "Evaluate "
            + base
            + " and support your judgment with relevant reasons."
        )

    if target == "create":
        return (
            "Develop a response to "
            + base
            + " using the relevant concepts."
        )

    return (
        "Explain "
        + base
        + " clearly."
    )


def generate_clarity_revision(
    question
):
    question = normalize_text(
        question
    )

    replacements = {
        "Discuss this.": "Explain the main concept involved.",
        "Explain this.": "Explain the concept clearly.",
        "Write something about": "Explain",
        "Say something about": "Explain",
        "What do you think about": "Evaluate",
        "Tell me about": "Describe"
    }

    revised = question

    for old, new in replacements.items():
        if old.lower() in revised.lower():
            revised = re.sub(
                re.escape(old),
                new,
                revised,
                flags=re.I
            )

    return revised


def generate_measurability_revision(
    question
):
    question = normalize_text(
        question
    )

    q_type = detect_question_type(
        question
    )

    if q_type == "Numerical":
        return (
            question.rstrip(".? ")
            + ". Show the calculation steps and state "
              "the final answer with the appropriate unit."
        )

    if q_type == "Short Answer":
        return (
            question.rstrip(".? ")
            + ". Support your answer with the relevant "
              "concept or evidence."
        )

    if q_type == "Essay/Long Answer":
        return (
            question.rstrip(".? ")
            + ". Support your response with relevant reasons "
              "or evidence."
        )

    return question


def generate_general_revision(
    question,
    result
):
    weakest = weakest_dimension(
        result
    )

    if weakest == "CLO Match":
        clo = result.get(
            "Best CLO",
            ""
        )

        if clo:
            return generate_clo_revision(
                question,
                clo
            )

    if weakest == "PLO Match":
        plo = result.get(
            "Best PLO",
            ""
        )

        if plo:
            return generate_clo_revision(
                question,
                plo
            )

    if weakest == "Bloom Score":
        return generate_bloom_revision(
            question,
            result.get(
                "Target Bloom",
                "understand"
            )
        )

    if weakest == "Clarity":
        return generate_clarity_revision(
            question
        )

    if weakest == "Measurability":
        return generate_measurability_revision(
            question
        )

    return generate_clo_revision(
        question,
        result.get(
            "Best CLO",
            ""
        )
    )


# ============================================================
# REVISION EXPLANATIONS
# ============================================================

def explain_problem(
    result
):
    clo = result.get(
        "CLO Match",
        100
    )

    plo = result.get(
        "PLO Match",
        100
    )

    bloom = result.get(
        "Bloom Score",
        100
    )

    clarity = result.get(
        "Clarity",
        100
    )

    measurability = result.get(
        "Measurability",
        100
    )

    if clo < ATTAINMENT_THRESHOLD:
        return (
            "CLO alignment is below 75%. The question needs to "
            "assess the concept or skill expressed in the selected CLO."
        )

    if plo < ATTAINMENT_THRESHOLD:
        return (
            "PLO alignment is below 75%. The question needs to "
            "provide clearer evidence of the selected program outcome."
        )

    if bloom < ATTAINMENT_THRESHOLD:
        return (
            "The cognitive demand of the question does not sufficiently "
            "match the target Bloom level."
        )

    if clarity < ATTAINMENT_THRESHOLD:
        return (
            "The wording contains a clarity issue that may make the "
            "expected response less precise."
        )

    if measurability < ATTAINMENT_THRESHOLD:
        return (
            "The expected student response is not sufficiently observable "
            "or measurable."
        )

    return (
        "The question has an alignment issue that can be improved "
        "without changing its subject or technical content."
    )


def identify_revision_source(result):
    if result.get(
        "CLO Match",
        100
    ) < ATTAINMENT_THRESHOLD:
        return "CLO"

    if result.get(
        "PLO Match",
        100
    ) < ATTAINMENT_THRESHOLD:
        return "PLO"

    if result.get(
        "Bloom Score",
        100
    ) < ATTAINMENT_THRESHOLD:
        return "Bloom's Taxonomy"

    if result.get(
        "Clarity",
        100
    ) < ATTAINMENT_THRESHOLD:
        return "Clarity"

    if result.get(
        "Measurability",
        100
    ) < ATTAINMENT_THRESHOLD:
        return "Measurability"

    return "Alignment"


def create_revision(
    result
):
    question = result.get(
        "Question",
        ""
    )

    clo_score = result.get(
        "CLO Match",
        100
    )

    plo_score = result.get(
        "PLO Match",
        100
    )

    # --------------------------------------------------------
    # PRIORITY 1 — CLO
    # --------------------------------------------------------

    if clo_score < ATTAINMENT_THRESHOLD:
        clo = result.get(
            "Best CLO",
            ""
        )

        if clo:
            revision = generate_clo_revision(
                question,
                clo
            )

            return {
                "revision": revision,
                "source": "CLO",
                "problem": "CLO attainment is below 75%.",
                "reason": explain_problem(result)
            }

    # --------------------------------------------------------
    # PRIORITY 2 — PLO
    # --------------------------------------------------------

    if plo_score < ATTAINMENT_THRESHOLD:
        plo = result.get(
            "Best PLO",
            ""
        )

        if plo:
            revision = generate_clo_revision(
                question,
                plo
            )

            return {
                "revision": revision,
                "source": "PLO",
                "problem": "PLO attainment is below 75%.",
                "reason": explain_problem(result)
            }

    # --------------------------------------------------------
    # OTHER PROBLEMS
    # --------------------------------------------------------

    revision = generate_general_revision(
        question,
        result
    )

    return {
        "revision": revision,
        "source": identify_revision_source(result),
        "problem": "The question requires alignment improvement.",
        "reason": explain_problem(result)
    }


# ============================================================
# RESCORING
# ============================================================

def rescore_revision(
    original_result,
    revised_question,
    clos,
    plos
):
    revised_result = evaluate_question(
        revised_question,
        clos,
        plos
    )

    revised_result[
        "Question Number"
    ] = original_result[
        "Question Number"
    ]

    return revised_result


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>
    .main {
        padding-top: 1rem;
    }

    .block-container {
        max-width: 1200px;
        padding-top: 1rem;
    }

    h1 {
        font-weight: 800;
    }

    h2, h3 {
        font-weight: 700;
    }

    .revision-box {
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid #d9d9d9;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.title("🎓 OBE Quiz Checker")

    st.write(
        "Check assessment questions for CLO, PLO, "
        "Bloom's Taxonomy, relevance, clarity, "
        "and measurability."
    )

    st.divider()

    st.caption(
        "Supported formats: PDF, DOCX, PPTX, XLSX, "
        "XLS, CSV, TXT, MD and images."
    )

    st.caption(
        "Question types can include MCQs, True/False, "
        "fill-in-the-blank, matching, case studies, "
        "numerical questions, practical tasks, "
        "short answers and essays."
    )


# ============================================================
# MAIN HEADER
# ============================================================

st.title("🎓 OBE Quiz Checker")

st.write(
    "Check your assessment questions for CLO, PLO, "
    "Bloom's Taxonomy, clarity, relevance, and measurability "
    "— and improve weak questions with practical, "
    "context-preserving revisions."
)


# ============================================================
# 1. ASSESSMENT INFORMATION
# ============================================================

st.header("1. Assessment Information")

col1, col2, col3 = st.columns(3)

with col1:
    course_name = st.text_input(
        "Course",
        placeholder="e.g., Chemistry, English I, Physics"
    )

with col2:
    assessment_name = st.text_input(
        "Assessment",
        placeholder="e.g., Quiz 1, Midterm, Assignment"
    )

with col3:
    total_marks = st.number_input(
        "Total Marks",
        min_value=0.0,
        value=10.0,
        step=1.0
    )


# ============================================================
# 2. LEARNING OUTCOMES
# ============================================================

st.header("2. Learning Outcomes")

col1, col2 = st.columns(2)

with col1:
    clo_text = st.text_area(
        "Course Learning Outcomes (CLOs)",
        height=180,
        placeholder=(
            "Enter one CLO per line.\n\n"
            "Example:\n"
            "Explain the process of photosynthesis and its importance to plant growth.\n"
            "Apply scientific concepts to solve relevant problems."
        )
    )

with col2:
    plo_text = st.text_area(
        "Program Learning Outcomes (PLOs)",
        height=180,
        placeholder=(
            "Enter one PLO per line.\n\n"
            "Example:\n"
            "Apply knowledge of science and mathematics to solve problems.\n"
            "Communicate ideas effectively."
        )
    )

clos = parse_outcomes(
    clo_text
)

plos = parse_outcomes(
    plo_text
)

if clos:
    st.success(
        f"{len(clos)} CLO(s) loaded."
    )

if plos:
    st.success(
        f"{len(plos)} PLO(s) loaded."
    )


# ============================================================
# 3. UPLOAD ASSESSMENT
# ============================================================

st.header("3. Upload Complete Assessment")

uploaded_file = st.file_uploader(
    "Upload the complete quiz or assessment file",
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
        "tiff"
    ]
)

if uploaded_file is not None:
    if (
        st.session_state.file_name
        != uploaded_file.name
    ):
        st.session_state.questions = []
        st.session_state.analysis = []
        st.session_state.revision_candidates = {}
        st.session_state.accepted_revisions = {}
        st.session_state.analyzed = False
        st.session_state.overall_balloons_shown = False

    st.session_state.file_name = (
        uploaded_file.name
    )

    if st.button(
        "📖 Read Assessment",
        use_container_width=True
    ):
        with st.spinner(
            "Reading the assessment..."
        ):
            text, error = read_uploaded_file(
                uploaded_file
            )

        if error:
            st.error(error)
        elif not text.strip():
            st.error(
                "No readable text was found in the file."
            )
        else:
            st.session_state.uploaded_text = text

            questions = extract_questions(
                text
            )

            st.session_state.questions = questions
            st.session_state.analysis = []
            st.session_state.analyzed = False
            st.session_state.revision_candidates = {}

            st.success(
                f"Assessment read successfully. "
                f"{len(questions)} question(s) detected."
            )

            with st.expander(
                "Preview extracted text"
            ):
                st.text(
                    text[:8000]
                )


# ============================================================
# EXTRACTED QUESTIONS
# ============================================================

if st.session_state.questions:
    st.header("Detected Questions")

    for index, question in enumerate(
        st.session_state.questions,
        start=1
    ):
        st.write(
            f"**Question {index}:** {question}"
        )


# ============================================================
# 4. ANALYZE
# ============================================================

st.header("4. Analyze Assessment")

if not st.session_state.questions:
    st.info(
        "Upload and read an assessment first."
    )

elif not clos:
    st.warning(
        "Enter at least one CLO before analysis."
    )

else:
    if st.button(
        "🔍 Analyze Assessment",
        type="primary",
        use_container_width=True
    ):
        with st.spinner(
            "Analyzing questions and learning-outcome alignment..."
        ):
            results = analyze_questions(
                st.session_state.questions,
                clos,
                plos
            )

        st.session_state.analysis = results
        st.session_state.analyzed = True
        st.session_state.revision_candidates = {}

        overall = calculate_overall_score(
            results
        )

        st.session_state.last_overall_score = (
            overall
        )

        if overall >= OVERALL_BALLOON_THRESHOLD:
            st.balloons()
            st.session_state.overall_balloons_shown = True

        st.success(
            "Assessment analysis completed."
        )


# ============================================================
# ANALYSIS OUTPUT
# ============================================================

if st.session_state.analyzed and st.session_state.analysis:

    results = st.session_state.analysis

    # ========================================================
    # 5. OVERALL ALIGNMENT
    # ========================================================

    st.header("5. Overall Alignment")

    overall_score = calculate_overall_score(
        results
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Overall Alignment",
            f"{overall_score:.1f}%"
        )

    with col2:
        st.metric(
            "Questions",
            len(results)
        )

    with col3:
        attained_count = sum(
            1
            for result in results
            if result["Overall Alignment"]
            >= ATTAINMENT_THRESHOLD
        )

        st.metric(
            "Questions Attained",
            f"{attained_count}/{len(results)}"
        )

    st.progress(
        overall_score / 100
    )

    st.write(
        f"**Status:** {score_status(overall_score)}"
    )

    if overall_score >= OVERALL_BALLOON_THRESHOLD:
        st.success(
            "🎉 Overall assessment alignment has reached 80% or above."
        )

    # ========================================================
    # 6. ASSESSMENT SCORE ANALYSIS
    # ========================================================

    st.header("6. Assessment Score Analysis")

    metric_columns = [
        "CLO Match",
        "PLO Match",
        "Bloom Score",
        "Relevance",
        "Clarity",
        "Measurability"
    ]

    metric_values = {}

    for column in metric_columns:
        metric_values[column] = round(
            sum(
                float(result[column])
                for result in results
            )
            / len(results),
            1
        )

    score_col1, score_col2, score_col3 = st.columns(3)

    with score_col1:
        st.metric(
            "Average CLO Match",
            f"{metric_values['CLO Match']:.1f}%"
        )

        st.metric(
            "Average PLO Match",
            f"{metric_values['PLO Match']:.1f}%"
        )

    with score_col2:
        st.metric(
            "Average Bloom",
            f"{metric_values['Bloom Score']:.1f}%"
        )

        st.metric(
            "Average Relevance",
            f"{metric_values['Relevance']:.1f}%"
        )

    with score_col3:
        st.metric(
            "Average Clarity",
            f"{metric_values['Clarity']:.1f}%"
        )

        st.metric(
            "Average Measurability",
            f"{metric_values['Measurability']:.1f}%"
        )

    # ========================================================
    # 7. QUESTIONS REQUIRING REVISION
    # ========================================================

    st.header("7. 🔧 Questions Requiring Revision")

    weak_results = [
        result
        for result in results
        if (
            result["Overall Alignment"]
            < ATTAINMENT_THRESHOLD
            or result["CLO Match"]
            < ATTAINMENT_THRESHOLD
            or result["PLO Match"]
            < ATTAINMENT_THRESHOLD
        )
    ]

    if not weak_results:
        st.success(
            "🎉 All questions have reached the 75% attainment threshold."
        )

    else:
        st.info(
            "The tool automatically generates practical revisions "
            "for questions below the attainment threshold. "
            "CLO/PLO alignment problems are handled first."
        )

        # ----------------------------------------------------
        # Revision list at top
        # ----------------------------------------------------

        for result in weak_results:

            question_number = result[
                "Question Number"
            ]

            if question_number not in (
                st.session_state.revision_candidates
            ):
                st.session_state.revision_candidates[
                    question_number
                ] = create_revision(
                    result
                )

            revision_data = (
                st.session_state.revision_candidates[
                    question_number
                ]
            )

            revision = revision_data.get(
                "revision",
                ""
            )

            if not revision:
                # Absolute fallback.
                revision = (
                    result["Question"].rstrip(".? ")
                    + ". Explain your answer clearly."
                )

                st.session_state.revision_candidates[
                    question_number
                ]["revision"] = revision

            st.subheader(
                f"Question {question_number} — "
                f"{result['Overall Alignment']:.1f}% "
                f"{score_status(result['Overall Alignment'])}"
            )

            col1, col2 = st.columns(
                [1, 1]
            )

            with col1:
                st.markdown(
                    "**Current Question**"
                )

                st.info(
                    result["Question"]
                )

                st.markdown(
                    "**Problem Identified**"
                )

                st.write(
                    revision_data.get(
                        "problem",
                        "Alignment issue detected."
                    )
                )

                st.markdown(
                    "**Why the Tool Flagged It**"
                )

                st.write(
                    revision_data.get(
                        "reason",
                        explain_problem(result)
                    )
                )

                st.markdown(
                    "**Revision Focus**"
                )

                st.write(
                    revision_data.get(
                        "source",
                        "Alignment"
                    )
                )

            with col2:
                st.markdown(
                    "**Practical Revision**"
                )

                st.success(
                    revision
                )

                st.caption(
                    "The revision preserves the original "
                    "subject and assessment context."
                )

                if result["Question Type"] == "MCQ":
                    st.caption(
                        "MCQ options are preserved."
                    )

                if get_numbers(
                    result["Question"]
                ):
                    st.caption(
                        "Original numerical values are preserved."
                    )

                if st.button(
                    "Use This Revision",
                    key=f"use_revision_{question_number}",
                    use_container_width=True
                ):
                    old_score = float(
                        result[
                            "Overall Alignment"
                        ]
                    )

                    revised_result = rescore_revision(
                        result,
                        revision,
                        clos,
                        plos
                    )

                    revised_result[
                        "Question"
                    ] = revision

                    st.session_state.questions[
                        question_number - 1
                    ] = revision

                    st.session_state.analysis[
                        question_number - 1
                    ] = revised_result

                    st.session_state.accepted_revisions[
                        question_number
                    ] = {
                        "original": result["Question"],
                        "revised": revision,
                        "old_score": old_score,
                        "new_score": revised_result[
                            "Overall Alignment"
                        ]
                    }

                    st.session_state.revision_candidates.pop(
                        question_number,
                        None
                    )

                    new_score = float(
                        revised_result[
                            "Overall Alignment"
                        ]
                    )

                    if new_score >= ATTAINMENT_THRESHOLD:
                        st.balloons()

                    st.success(
                        f"Revision applied. "
                        f"Before: {old_score:.1f}% → "
                        f"After: {new_score:.1f}%"
                    )

                    st.rerun()

            st.divider()

    # ========================================================
    # ACCEPTED REVISION HISTORY
    # ========================================================

    if st.session_state.accepted_revisions:

        st.subheader(
            "✅ Revised Questions"
        )

        for number, data in (
            st.session_state.accepted_revisions.items()
        ):
            st.write(
                f"**Question {number}:** "
                f"{data['old_score']:.1f}% → "
                f"{data['new_score']:.1f}%"
            )

            with st.expander(
                f"View Question {number} Revision"
            ):
                st.markdown(
                    "**Original:**"
                )

                st.write(
                    data["original"]
                )

                st.markdown(
                    "**Revised:**"
                )

                st.success(
                    data["revised"]
                )

    # ========================================================
    # 8. ATTAINED QUESTIONS
    # ========================================================

    st.header("8. 🏆 Attained Questions")

    attained_results = [
        result
        for result in st.session_state.analysis
        if result["Overall Alignment"]
        >= ATTAINMENT_THRESHOLD
    ]

    if not attained_results:
        st.info(
            "No questions have reached 75% yet."
        )

    else:
        for result in attained_results:
            st.write(
                f"🏆 **Question {result['Question Number']}** — "
                f"{result['Overall Alignment']:.1f}%"
            )

    # ========================================================
    # 9. ALIGNMENT OVERVIEW — ONLY GRAPH
    # ========================================================

    st.header("9. Alignment Overview")

    graph_data = pd.DataFrame(
        [
            {
                "Question": (
                    f"Q{result['Question Number']}"
                ),
                "CLO": result["CLO Match"],
                "PLO": result["PLO Match"],
                "Bloom": result["Bloom Score"],
                "Relevance": result["Relevance"],
                "Clarity": result["Clarity"],
                "Measurability": result["Measurability"],
                "Overall": result["Overall Alignment"]
            }
            for result in st.session_state.analysis
        ]
    )

    if not graph_data.empty:
        graph_data = graph_data.set_index(
            "Question"
        )

        st.line_chart(
            graph_data
        )

    # ========================================================
    # 10. QUESTION OVERVIEW
    # ========================================================

    st.header("10. Question Overview")

    overview_rows = []

    for result in st.session_state.analysis:
        overview_rows.append(
            {
                "Question": (
                    f"Q{result['Question Number']}"
                ),
                "Type": result["Question Type"],
                "CLO": f"{result['CLO Match']:.1f}%",
                "PLO": f"{result['PLO Match']:.1f}%",
                "Bloom": f"{result['Bloom Score']:.1f}%",
                "Relevance": f"{result['Relevance']:.1f}%",
                "Clarity": f"{result['Clarity']:.1f}%",
                "Measurability": (
                    f"{result['Measurability']:.1f}%"
                ),
                "Overall": (
                    f"{result['Overall Alignment']:.1f}%"
                ),
                "Status": score_status(
                    result["Overall Alignment"]
                )
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
    # 11. DETAILED QUESTION ANALYSIS
    # ========================================================

    st.header("11. Detailed Question Analysis")

    question_labels = [
        (
            f"Question {result['Question Number']} — "
            f"{result['Overall Alignment']:.1f}%"
        )
        for result in st.session_state.analysis
    ]

    selected_label = st.selectbox(
        "Select a question",
        question_labels
    )

    selected_index = question_labels.index(
        selected_label
    )

    selected_result = (
        st.session_state.analysis[
            selected_index
        ]
    )

    st.markdown(
        f"### Question {selected_result['Question Number']}"
    )

    st.info(
        selected_result["Question"]
    )

    st.write(
        f"**Question Type:** "
        f"{selected_result['Question Type']}"
    )

    metric_col1, metric_col2, metric_col3 = st.columns(3)

    with metric_col1:
        st.metric(
            "CLO Match",
            f"{selected_result['CLO Match']:.1f}%"
        )

        st.metric(
            "PLO Match",
            f"{selected_result['PLO Match']:.1f}%"
        )

    with metric_col2:
        st.metric(
            "Bloom",
            f"{selected_result['Bloom Score']:.1f}%"
        )

        st.metric(
            "Relevance",
            f"{selected_result['Relevance']:.1f}%"
        )

    with metric_col3:
        st.metric(
            "Clarity",
            f"{selected_result['Clarity']:.1f}%"
        )

        st.metric(
            "Measurability",
            f"{selected_result['Measurability']:.1f}%"
        )

    st.progress(
        selected_result["Overall Alignment"]
        / 100
    )

    st.write(
        f"**Overall Alignment:** "
        f"{selected_result['Overall Alignment']:.1f}% "
        f"{score_status(selected_result['Overall Alignment'])}"
    )

    if selected_result.get(
        "Best CLO"
    ):
        st.markdown(
            "**Mapped CLO**"
        )

        st.write(
            selected_result["Best CLO"]
        )

    if selected_result.get(
        "Best PLO"
    ):
        st.markdown(
            "**Mapped PLO**"
        )

        st.write(
            selected_result["Best PLO"]
        )

    st.write(
        f"**Detected Bloom Level:** "
        f"{selected_result['Bloom Level']}"
    )

    st.write(
        f"**Target Bloom Level:** "
        f"{selected_result['Target Bloom']}"
    )

    # ========================================================
    # DETAILED PROBLEM INFORMATION
    # ========================================================

    if selected_result[
        "Overall Alignment"
    ] < ATTAINMENT_THRESHOLD:

        st.markdown(
            "### 🔧 Recommended Improvement"
        )

        problem = explain_problem(
            selected_result
        )

        st.warning(
            problem
        )

        source = identify_revision_source(
            selected_result
        )

        st.write(
            f"**Revision focus:** {source}"
        )

        if selected_result[
            "CLO Match"
        ] < ATTAINMENT_THRESHOLD:

            st.write(
                "The CLO is below the 75% attainment threshold, "
                "so the revision should directly address the "
                "actual CLO."
            )

        elif selected_result[
            "PLO Match"
        ] < ATTAINMENT_THRESHOLD:

            st.write(
                "The PLO is below the 75% attainment threshold, "
                "so the revision should directly address the "
                "actual PLO."
            )

    else:
        st.success(
            "🏆 This question has reached the 75% attainment threshold."
        )

    # ========================================================
    # 12. EXPORT
    # ========================================================

    st.header("12. Export")

    export_rows = []

    for result in st.session_state.analysis:
        export_rows.append(
            {
                "Question Number": result[
                    "Question Number"
                ],
                "Question": result[
                    "Question"
                ],
                "Question Type": result[
                    "Question Type"
                ],
                "Bloom Level": result[
                    "Bloom Level"
                ],
                "Target Bloom": result[
                    "Target Bloom"
                ],
                "CLO Match": result[
                    "CLO Match"
                ],
                "PLO Match": result[
                    "PLO Match"
                ],
                "Bloom Score": result[
                    "Bloom Score"
                ],
                "Relevance": result[
                    "Relevance"
                ],
                "Clarity": result[
                    "Clarity"
                ],
                "Measurability": result[
                    "Measurability"
                ],
                "Overall Alignment": result[
                    "Overall Alignment"
                ],
                "Status": score_status(
                    result[
                        "Overall Alignment"
                    ]
                ),
                "Mapped CLO": result.get(
                    "Best CLO",
                    ""
                ),
                "Mapped PLO": result.get(
                    "Best PLO",
                    ""
                )
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
        "⬇️ Download Analysis Report",
        data=csv_data,
        file_name="obe_quiz_checker_report.csv",
        mime="text/csv",
        use_container_width=True
    )
