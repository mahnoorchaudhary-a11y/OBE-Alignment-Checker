import io
import re
from pathlib import Path

import pandas as pd
import streamlit as st

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
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Checker",
    page_icon="🎓",
    layout="wide"
)


# ============================================================
# CONSTANTS
# ============================================================

BLOOM_LEVELS = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create"
]

BLOOM_ORDER = {
    "remember": 1,
    "understand": 2,
    "apply": 3,
    "analyze": 4,
    "evaluate": 5,
    "create": 6
}

BLOOM_VERBS = {
    "Remember": [
        "define", "list", "name", "identify",
        "state", "recall", "recognize", "label",
        "match"
    ],
    "Understand": [
        "describe", "explain", "summarize",
        "classify", "interpret", "discuss",
        "illustrate", "paraphrase"
    ],
    "Apply": [
        "calculate", "solve", "apply",
        "demonstrate", "use", "implement",
        "execute", "compute", "perform",
        "show"
    ],
    "Analyze": [
        "analyze", "analyse", "compare",
        "contrast", "differentiate",
        "examine", "investigate",
        "categorize", "distinguish"
    ],
    "Evaluate": [
        "evaluate", "assess", "justify",
        "critique", "judge", "defend",
        "argue", "recommend", "appraise"
    ],
    "Create": [
        "design", "create", "develop",
        "construct", "formulate",
        "produce", "propose",
        "generate", "plan", "compose"
    ]
}


# ============================================================
# SESSION STATE
# ============================================================

if "assessment_text" not in st.session_state:
    st.session_state.assessment_text = ""

if "questions" not in st.session_state:
    st.session_state.questions = []

if "analysis" not in st.session_state:
    st.session_state.analysis = []

if "revision_options" not in st.session_state:
    st.session_state.revision_options = []

if "revision_question_index" not in st.session_state:
    st.session_state.revision_question_index = None


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
        "the", "a", "an", "and", "or", "of", "to",
        "in", "on", "for", "from", "with", "by",
        "is", "are", "was", "were", "be", "as",
        "at", "that", "this", "these", "those",
        "it", "its", "their", "there", "which",
        "who", "what", "how", "why", "when",
        "where", "into", "than", "then",
        "can", "could", "should", "would",
        "will", "may", "might", "using",
        "use", "used", "your", "you", "they",
        "them", "he", "she", "his", "her",
        "we", "our", "i", "me",
        "please", "answer", "question"
    }

    words = re.findall(
        r"[A-Za-z][A-Za-z0-9\-]{2,}",
        str(text).lower()
    )

    return [
        word for word in words
        if word not in stopwords
    ]


def stem_like(word):
    word = word.lower()

    for ending in ["ing", "ed", "es", "s"]:
        if len(word) > len(ending) + 3:
            if word.endswith(ending):
                return word[:-len(ending)]

    return word


def normalized_content_words(text):
    return {
        stem_like(word)
        for word in content_words(text)
    }


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

        cleaned = re.sub(
            r"^\s*(?:CLO|PLO)?\s*\d+\s*[\.\):-]?\s*",
            "",
            line,
            flags=re.I
        )

        if len(cleaned.split()) >= 3:
            outcomes.append(cleaned.strip())

    return outcomes


# ============================================================
# BLOOM
# ============================================================

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


def bloom_score(question, target_bloom):

    _, detected = find_bloom_verb(question)

    if target_bloom == "Auto":

        if detected == "Unknown":
            return 82

        return 96

    target_number = BLOOM_ORDER.get(
        target_bloom.lower()
    )

    actual_number = BLOOM_ORDER.get(
        detected.lower()
    )

    if actual_number is None:
        return 78

    if target_number == actual_number:
        return 100

    distance = abs(
        target_number - actual_number
    )

    if distance == 1:
        return 90

    if distance == 2:
        return 82

    return 72


# ============================================================
# OUTCOME MATCHING
# ============================================================

def outcome_similarity(question, outcome):

    q_words = normalized_content_words(question)
    o_words = normalized_content_words(outcome)

    if not q_words or not o_words:
        return 0

    overlap = q_words.intersection(o_words)

    if not overlap:
        return 0

    q_ratio = len(overlap) / len(q_words)
    o_ratio = len(overlap) / len(o_words)

    score = (
        60
        + q_ratio * 20
        + o_ratio * 20
    )

    return min(100, score)


def best_outcome_match(question, outcomes):

    if not outcomes:
        return "", 70, -1

    scores = []

    for index, outcome in enumerate(outcomes):

        score = outcome_similarity(
            question,
            outcome
        )

        scores.append(
            (score, index, outcome)
        )

    scores.sort(
        key=lambda x: x[0],
        reverse=True
    )

    best_score, best_index, best_text = scores[0]

    if best_score == 0:
        best_score = 52

    return (
        best_text,
        round(best_score, 1),
        best_index
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
        or "_____" in q
    ):
        return "Fill in the Blank"

    if any(
        term in lower
        for term in [
            "calculate",
            "compute",
            "solve",
            "find the value",
            "determine the value"
        ]
    ):
        return "Numerical / Problem Solving"

    if any(
        term in lower
        for term in [
            "case study",
            "scenario",
            "given case",
            "read the case",
            "situation"
        ]
    ):
        return "Case Study / Scenario"

    if any(
        term in lower
        for term in [
            "design",
            "develop",
            "construct",
            "implement",
            "perform",
            "demonstrate"
        ]
    ):
        return "Practical / Application"

    if any(
        term in lower
        for term in [
            "essay",
            "critically discuss",
            "critically analyze",
            "critically analyse"
        ]
    ):
        return "Essay"

    if len(q.split()) > 45:
        return "Long Answer"

    if any(
        term in lower
        for term in [
            "explain",
            "discuss",
            "analyze",
            "analyse",
            "evaluate",
            "compare",
            "justify",
            "assess"
        ]
    ):
        return "Short / Long Answer"

    return "Short Answer"


# ============================================================
# QUESTION EXTRACTION
# IMPORTANT: DEFINED BEFORE IT IS USED
# ============================================================

def extract_questions(text):

    text = clean_text(text)

    if not text:
        return []

    lines = text.splitlines()

    questions = []
    current = []

    numbered_pattern = re.compile(
        r"^\s*(?:Q(?:uestion)?\.?\s*)?"
        r"\d+\s*[\)\.\-:]\s+",
        flags=re.I
    )

    question_word_pattern = re.compile(
        r"^\s*(?:Q(?:uestion)?\.?)\s*"
        r"\d+\s*[\)\.\-:]?\s*",
        flags=re.I
    )

    for line in lines:

        line = line.strip()

        if not line:
            continue

        is_new_question = (
            numbered_pattern.match(line)
            or question_word_pattern.match(line)
        )

        if is_new_question:

            if current:

                block = clean_text(
                    " ".join(current)
                )

                block = re.sub(
                    r"^\s*(?:Q(?:uestion)?\.?\s*)?"
                    r"\d+\s*[\)\.\-:]\s*",
                    "",
                    block,
                    flags=re.I
                )

                if len(block.split()) >= 3:
                    questions.append(block)

            current = [line]

        else:

            if current:
                current.append(line)

    if current:

        block = clean_text(
            " ".join(current)
        )

        block = re.sub(
            r"^\s*(?:Q(?:uestion)?\.?\s*)?"
            r"\d+\s*[\)\.\-:]\s*",
            "",
            block,
            flags=re.I
        )

        if len(block.split()) >= 3:
            questions.append(block)

    # --------------------------------------------------------
    # FALLBACK 1: numbered questions embedded in one paragraph
    # --------------------------------------------------------

    if len(questions) < 2:

        matches = re.split(
            r"(?=(?:Q(?:uestion)?\.?\s*)?\d+\s*[\)\.\-:]\s+)",
            text,
            flags=re.I
        )

        fallback = []

        for block in matches:

            block = clean_text(block)

            block = re.sub(
                r"^\s*(?:Q(?:uestion)?\.?\s*)?"
                r"\d+\s*[\)\.\-:]\s*",
                "",
                block,
                flags=re.I
            )

            if len(block.split()) >= 3:
                fallback.append(block)

        if len(fallback) >= 2:
            questions = fallback

    # --------------------------------------------------------
    # FALLBACK 2: paragraphs
    # --------------------------------------------------------

    if len(questions) < 2:

        paragraphs = re.split(
            r"\n\s*\n",
            text
        )

        fallback = []

        for paragraph in paragraphs:

            paragraph = clean_text(
                paragraph
            )

            if len(paragraph.split()) >= 5:

                if (
                    "clo" not in paragraph.lower()
                    and "plo" not in paragraph.lower()
                ):
                    fallback.append(
                        paragraph
                    )

        if len(fallback) >= 2:
            questions = fallback

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

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

                ocr_text = (
                    pytesseract.image_to_string(
                        image
                    )
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
        p.text
        for p in document.paragraphs
        if p.text.strip()
    ]

    table_text = []

    for table in document.tables:

        for row in table.rows:

            cells = [
                cell.text
                for cell in row.cells
            ]

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

    parts = []

    for sheet in workbook.sheet_names:

        frame = pd.read_excel(
            io.BytesIO(data),
            sheet_name=sheet,
            header=None
        )

        parts.append(
            f"Sheet: {sheet}"
        )

        parts.append(
            frame.fillna("")
            .astype(str)
            .to_csv(
                index=False,
                header=False
            )
        )

    return clean_text(
        "\n".join(parts)
    )


def read_csv(uploaded_file):

    data = uploaded_file.read()

    frame = pd.read_csv(
        io.BytesIO(data),
        header=None
    )

    return clean_text(
        frame.fillna("")
        .astype(str)
        .to_csv(
            index=False,
            header=False
        )
    )


def read_text(uploaded_file):

    return uploaded_file.read().decode(
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

    extension = Path(
        uploaded_file.name
    ).suffix.lower()

    if extension == ".pdf":
        return read_pdf(uploaded_file)

    if extension == ".docx":
        return read_docx(uploaded_file)

    if extension == ".pptx":
        return read_pptx(uploaded_file)

    if extension in [".xlsx", ".xls"]:
        return read_excel(uploaded_file)

    if extension == ".csv":
        return read_csv(uploaded_file)

    if extension in [".txt", ".md"]:
        return read_text(uploaded_file)

    if extension in [
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
        ".tiff"
    ]:
        return read_image(uploaded_file)

    if extension == ".svg":

        raw = uploaded_file.read().decode(
            "utf-8",
            errors="ignore"
        )

        return clean_text(
            re.sub(
                r"<[^>]+>",
                " ",
                raw
            )
        )

    raise RuntimeError(
        f"Unsupported file type: {extension}"
    )


# ============================================================
# QUALITY SCORING
# ============================================================

def clarity_score(question):

    words = question.split()

    score = 100

    if len(words) < 4:
        score -= 8

    if len(words) > 100:
        score -= 4

    vague_phrases = [
        "write something",
        "say something",
        "what do you know",
        "discuss everything",
        "write about this",
        "comment on this"
    ]

    lower = question.lower()

    for phrase in vague_phrases:

        if phrase in lower:
            score -= 12

    return max(
        65,
        min(100, score)
    )


def measurability_score(
    question,
    question_type
):

    _, bloom = find_bloom_verb(question)

    if bloom != "Unknown":
        score = 98
    else:
        score = 90

    if question_type == "Multiple Choice":
        score = 96

    elif question_type == "True / False":
        score = 96

    elif question_type == "Numerical / Problem Solving":
        score = 96

    return score


def relevance_score(
    clo_score,
    plo_score
):

    values = []

    if clo_score is not None:
        values.append(clo_score)

    if plo_score is not None:
        values.append(plo_score)

    if not values:
        return 80

    average = sum(values) / len(values)

    return round(
        min(100, average + 5),
        1
    )


# ============================================================
# QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question,
    clos,
    plos,
    target_bloom
):

    question_type = detect_question_type(
        question
    )

    clo, clo_score, clo_index = (
        best_outcome_match(
            question,
            clos
        )
    )

    plo, plo_score, plo_index = (
        best_outcome_match(
            question,
            plos
        )
    )

    bloom = bloom_score(
        question,
        target_bloom
    )

    clarity = clarity_score(
        question
    )

    measurability = measurability_score(
        question,
        question_type
    )

    relevance = relevance_score(
        clo_score,
        plo_score
    )

    overall = (
        clo_score * 0.20
        + plo_score * 0.15
        + bloom * 0.20
        + relevance * 0.15
        + clarity * 0.15
        + measurability * 0.15
    )

    # LENIENT ADJUSTMENT
    if overall < 75:
        overall += 4

    if overall < 60:
        overall += 3

    overall = min(
        100,
        round(overall, 1)
    )

    return {
        "question": question,
        "Question Type": question_type,
        "CLO": clo,
        "CLO Match": round(clo_score, 1),
        "CLO Index": clo_index,
        "PLO": plo,
        "PLO Match": round(plo_score, 1),
        "PLO Index": plo_index,
        "Bloom": round(bloom, 1),
        "Relevance": round(relevance, 1),
        "Clarity": round(clarity, 1),
        "Measurability": round(measurability, 1),
        "Overall": overall
    }


def identify_problem(item, target_bloom):

    if item["CLO Match"] < 70:
        return (
            "CLO Alignment",
            "The question has only a limited connection "
            "with the strongest matching CLO."
        )

    if item["PLO Match"] < 70:
        return (
            "PLO Alignment",
            "The question has only a limited connection "
            "with the strongest matching PLO."
        )

    if (
        target_bloom != "Auto"
        and item["Bloom"] < 90
    ):
        return (
            "Bloom Level",
            "The action required by the question does "
            "not closely match the selected Bloom level."
        )

    if item["Clarity"] < 85:
        return (
            "Clarity",
            "The wording does not make the expected "
            "student response sufficiently clear."
        )

    if item["Measurability"] < 85:
        return (
            "Measurability",
            "The expected response is not sufficiently "
            "observable for consistent assessment."
        )

    return (
        "Minor Refinement",
        "The question is already reasonably aligned. "
        "A small refinement may make the expected "
        "response even clearer."
    )


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

        item = evaluate_question(
            question,
            clos,
            plos,
            target_bloom
        )

        area, problem = identify_problem(
            item,
            target_bloom
        )

        item["index"] = index
        item["Problem Area"] = area
        item["Problem"] = problem

        results.append(item)

    return results


def overall_score(analysis):

    if not analysis:
        return 0

    return round(
        sum(
            item["Overall"]
            for item in analysis
        ) / len(analysis),
        1
    )


# ============================================================
# REVISION VALIDATION
# ============================================================

def preserve_numbers(
    original,
    revised
):

    numbers = re.findall(
        r"\b\d+(?:\.\d+)?\b",
        original
    )

    for number in numbers:

        if number not in revised:
            return False

    return True


def preserve_topic(
    original,
    revised
):

    original_words = normalized_content_words(
        original
    )

    revised_words = normalized_content_words(
        revised
    )

    if not original_words:
        return False

    overlap = (
        original_words
        .intersection(revised_words)
    )

    ratio = (
        len(overlap)
        / len(original_words)
    )

    return ratio >= 0.60


# ============================================================
# REVISION GENERATORS
# ============================================================

def revise_clarity(question):

    replacements = [
        (
            r"\bwhat do you know about\b",
            "Explain"
        ),
        (
            r"\bwrite something about\b",
            "Explain"
        ),
        (
            r"\bwrite about\b",
            "Explain"
        ),
        (
            r"\bcomment on\b",
            "Explain"
        )
    ]

    for pattern, replacement in replacements:

        if re.search(
            pattern,
            question,
            flags=re.I
        ):

            return re.sub(
                pattern,
                replacement,
                question,
                count=1,
                flags=re.I
            )

    return ""


def revise_measurability(
    question,
    question_type
):

    lower = question.lower()

    if question_type == "Numerical / Problem Solving":

        if (
            "show" not in lower
            and "steps" not in lower
        ):

            return (
                question.rstrip(" .?")
                + " Show the steps used in your calculation."
            )

    if question_type == "Case Study / Scenario":

        if (
            "evidence" not in lower
            and "support" not in lower
        ):

            return (
                question.rstrip(" .?")
                + " Support your answer with evidence "
                "from the case."
            )

    return ""


def revise_bloom(
    question,
    target_bloom
):

    if target_bloom == "Auto":
        return ""

    replacement = {
        "Remember": "Identify",
        "Understand": "Explain",
        "Apply": "Apply",
        "Analyze": "Analyze",
        "Evaluate": "Evaluate",
        "Create": "Design"
    }.get(target_bloom)

    if not replacement:
        return ""

    verbs = []

    for level in BLOOM_LEVELS:
        verbs.extend(
            BLOOM_VERBS[level]
        )

    pattern = (
        r"^\s*(?:please\s+)?(?:"
        + "|".join(
            re.escape(v)
            for v in verbs
        )
        + r")\b"
    )

    match = re.search(
        pattern,
        question,
        flags=re.I
    )

    if not match:
        return ""

    remainder = question[
        match.end():
    ].lstrip()

    return (
        replacement
        + " "
        + remainder
    )


def validate_revision(
    original,
    revised,
    clos,
    plos,
    target_bloom
):

    if not revised:
        return False

    if normalize_text(original) == normalize_text(revised):
        return False

    if not preserve_numbers(
        original,
        revised
    ):
        return False

    if not preserve_topic(
        original,
        revised
    ):
        return False

    old_score = evaluate_question(
        original,
        clos,
        plos,
        target_bloom
    )["Overall"]

    new_score = evaluate_question(
        revised,
        clos,
        plos,
        target_bloom
    )["Overall"]

    return new_score > old_score


def generate_revisions(
    question,
    clo,
    plo,
    target_bloom
):

    question_type = detect_question_type(
        question
    )

    candidates = []

    clarity = revise_clarity(
        question
    )

    if clarity:
        candidates.append(
            (
                "Clarity",
                "The wording is broad or vague. "
                "The revision makes the task clearer.",
                clarity
            )
        )

    measurable = revise_measurability(
        question,
        question_type
    )

    if measurable:
        candidates.append(
            (
                "Measurability",
                "The revision makes the expected "
                "response easier to observe and assess.",
                measurable
            )
        )

    bloom_revision = revise_bloom(
        question,
        target_bloom
    )

    if bloom_revision:
        candidates.append(
            (
                "Bloom Level",
                "The action verb is changed to better "
                "represent the selected cognitive level.",
                bloom_revision
            )
        )

    clos = [clo] if clo else []
    plos = [plo] if plo else []

    results = []
    seen = set()

    old_score = evaluate_question(
        question,
        clos,
        plos,
        target_bloom
    )["Overall"]

    for focus, reason, revision in candidates:

        key = normalize_text(
            revision
        )

        if key in seen:
            continue

        seen.add(key)

        if not validate_revision(
            question,
            revision,
            clos,
            plos,
            target_bloom
        ):
            continue

        new_metrics = evaluate_question(
            revision,
            clos,
            plos,
            target_bloom
        )

        results.append(
            {
                "focus": focus,
                "reason": reason,
                "revision": revision,
                "old_score": old_score,
                "new_score": new_metrics["Overall"],
                "gain": round(
                    new_metrics["Overall"]
                    - old_score,
                    1
                )
            }
        )

    results.sort(
        key=lambda x: x["new_score"],
        reverse=True
    )

    return results[:3]


# ============================================================
# STATUS
# ============================================================

def status_for_score(score):

    if score >= 85:
        return "🟢 Strong"

    if score >= 75:
        return "🏆 Attained"

    if score >= 65:
        return "🟡 Minor Revision"

    if score >= 50:
        return "🟠 Review"

    return "🔴 Needs Revision"


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("🎓 OBE Quiz Checker")

    st.write(
        "Check assessment alignment and improve "
        "weak questions with practical revisions."
    )

    st.divider()

    target_bloom = st.selectbox(
        "Target Bloom Level",
        ["Auto"] + BLOOM_LEVELS
    )

    st.divider()

    st.caption("Score interpretation")

    st.success(
        "75%+ = Attained"
    )

    st.caption(
        "The percentage is an alignment indicator, "
        "not an absolute judgment of assessment quality."
    )


# ============================================================
# MAIN TITLE
# ============================================================

st.title("🎓 OBE Quiz Checker")

st.write(
    "Upload an assessment, enter CLOs/PLOs, and let "
    "the tool identify alignment issues and generate "
    "practical revisions."
)


# ============================================================
# 1. ASSESSMENT INFORMATION
# ============================================================

st.header("1️⃣ Assessment Information")

col1, col2 = st.columns(2)

with col1:

    course_name = st.text_input(
        "Course / Subject",
        placeholder="e.g., English I, Chemistry, Mathematics"
    )

with col2:

    assessment_name = st.text_input(
        "Assessment",
        placeholder="e.g., Quiz 1, Assignment, Midterm"
    )


# ============================================================
# 2. CLO / PLO
# ============================================================

st.header("2️⃣ Learning Outcomes")

col1, col2 = st.columns(2)

with col1:

    clo_text = st.text_area(
        "Course Learning Outcomes (CLOs)",
        height=180,
        placeholder=(
            "CLO 1: Explain fundamental concepts...\n"
            "CLO 2: Apply relevant principles...\n"
            "CLO 3: Analyze..."
        )
    )

with col2:

    plo_text = st.text_area(
        "Program Learning Outcomes (PLOs)",
        height=180,
        placeholder=(
            "PLO 1: Demonstrate knowledge...\n"
            "PLO 2: Apply problem-solving skills...\n"
            "PLO 3: Design solutions..."
        )
    )

clos = parse_outcomes(clo_text)
plos = parse_outcomes(plo_text)


# ============================================================
# 3. UPLOAD
# ============================================================

st.header("3️⃣ Upload Complete Assessment")

uploaded_file = st.file_uploader(
    "Upload PDF, Word, PowerPoint, Excel, CSV, TXT or image",
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
        "tiff",
        "svg"
    ]
)


if uploaded_file:

    if st.button(
        "📖 Read Assessment",
        use_container_width=True
    ):

        try:

            with st.spinner(
                "Reading assessment..."
            ):

                text = read_uploaded_file(
                    uploaded_file
                )

            questions = extract_questions(
                text
            )

            st.session_state.assessment_text = text
            st.session_state.questions = questions
            st.session_state.analysis = []
            st.session_state.revision_options = []
            st.session_state.revision_question_index = None

            if not questions:

                st.warning(
                    "The file was readable, but no questions "
                    "could be detected automatically. "
                    "Make sure questions are numbered or "
                    "separated clearly."
                )

            else:

                st.success(
                    f"Assessment read successfully. "
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
            st.session_state.assessment_text[:20000]
        )


# ============================================================
# 4. ANALYZE
# ============================================================

st.header("4️⃣ Analyze Assessment")

if st.button(
    "🔍 Analyze Assessment",
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
            "Analyzing questions..."
        ):

            st.session_state.analysis = (
                analyze_questions(
                    st.session_state.questions,
                    clos,
                    plos,
                    target_bloom
                )
            )

        st.session_state.revision_options = []
        st.session_state.revision_question_index = None

        st.success(
            "Analysis completed."
        )


# ============================================================
# RESULTS
# ============================================================

if st.session_state.analysis:

    analysis = st.session_state.analysis

    overall = overall_score(
        analysis
    )

    # ========================================================
    # OVERALL
    # ========================================================

    st.header("5️⃣ Overall Alignment")

    if overall >= 85:

        st.success(
            f"🎯 {overall:.0f}% — Strong alignment"
        )

    elif overall >= 75:

        st.success(
            f"🏆 {overall:.0f}% — Attained"
        )

    elif overall >= 65:

        st.warning(
            f"🟡 {overall:.0f}% — Minor revision recommended"
        )

    else:

        st.warning(
            f"🟠 {overall:.0f}% — Review needed"
        )

    # ========================================================
    # METRICS
    # ========================================================

    metrics = [
        "CLO Match",
        "PLO Match",
        "Bloom",
        "Relevance",
        "Clarity",
        "Measurability"
    ]

    averages = {}

    for metric in metrics:

        averages[metric] = round(
            sum(
                item[metric]
                for item in analysis
            ) / len(analysis),
            1
        )

    cols = st.columns(6)

    for col, metric in zip(
        cols,
        metrics
    ):

        with col:

            st.metric(
                metric,
                f"{averages[metric]:.0f}%"
            )

    # ========================================================
    # ONE GRAPH
    # ========================================================

    st.subheader(
        "📊 Alignment Overview"
    )

    chart_df = pd.DataFrame(
        {
            "Metric": metrics,
            "Score": [
                averages[m]
                for m in metrics
            ]
        }
    )

    st.bar_chart(
        chart_df.set_index("Metric")
    )

    # ========================================================
    # QUESTION TABLE
    # ========================================================

    st.header("6️⃣ Question Overview")

    rows = []

    for item in analysis:

        rows.append(
            {
                "Question": f"Q{item['index'] + 1}",
                "Type": item["Question Type"],
                "CLO": item["CLO Match"],
                "PLO": item["PLO Match"],
                "Bloom": item["Bloom"],
                "Clarity": item["Clarity"],
                "Overall": item["Overall"],
                "Status": status_for_score(
                    item["Overall"]
                )
            }
        )

    table_df = pd.DataFrame(rows)

    st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # ATTAINED
    # ========================================================

    st.header("🏆 Attained Questions")

    attained = [
        item
        for item in analysis
        if item["Overall"] >= 75
    ]

    if attained:

        st.success(
            f"{len(attained)} question(s) have reached "
            "the Attained level."
        )

        for item in attained:

            with st.expander(
                f"🏆 Q{item['index'] + 1} — "
                f"{item['Overall']:.0f}%"
            ):

                st.write(
                    item["question"]
                )

                st.caption(
                    "This question has reached the 75% "
                    "Attained threshold."
                )

    else:

        st.info(
            "No questions have reached 75% yet."
        )

    # ========================================================
    # REVISION
    # ========================================================

    st.header("7️⃣ Improve a Question")

    labels = [
        f"{item['index'] + 1}. "
        f"{item['Overall']:.0f}% — "
        f"{item['Problem Area']}"
        for item in analysis
    ]

    selected_label = st.selectbox(
        "Select a question",
        labels
    )

    selected_position = labels.index(
        selected_label
    )

    selected = analysis[
        selected_position
    ]

    st.subheader(
        "Current Question"
    )

    st.info(
        selected["question"]
    )

    st.write(
        f"**Current score: "
        f"{selected['Overall']:.0f}% — "
        f"{status_for_score(selected['Overall'])}**"
    )

    st.subheader(
        "🔎 What needs attention?"
    )

    st.warning(
        selected["Problem"]
    )

    st.write(
        f"**Area:** {selected['Problem Area']}"
    )

    if selected["CLO"]:

        st.write(
            f"**Best matching CLO:** "
            f"{selected['CLO']}"
        )

    if selected["PLO"]:

        st.write(
            f"**Best matching PLO:** "
            f"{selected['PLO']}"
        )

    detected_verb, detected_bloom = (
        find_bloom_verb(
            selected["question"]
        )
    )

    if detected_verb:

        st.write(
            f"**Action detected:** "
            f"{detected_verb} "
            f"({detected_bloom})"
        )

    if st.button(
        "✨ Generate Practical Revision",
        type="primary",
        use_container_width=True
    ):

        st.session_state.revision_options = (
            generate_revisions(
                selected["question"],
                selected["CLO"],
                selected["PLO"],
                target_bloom
            )
        )

        st.session_state.revision_question_index = (
            selected["index"]
        )

    # ========================================================
    # REVISION OPTIONS
    # ========================================================

    if (
        st.session_state.revision_question_index
        == selected["index"]
    ):

        revisions = (
            st.session_state.revision_options
        )

        if revisions:

            st.subheader(
                "🛠 Practical Revision"
            )

            for number, option in enumerate(
                revisions
            ):

                st.markdown(
                    f"### Option {number + 1}: "
                    f"{option['focus']}"
                )

                st.write(
                    "**Original question**"
                )

                st.info(
                    selected["question"]
                )

                st.write(
                    "**Revised question**"
                )

                st.success(
                    option["revision"]
                )

                st.write(
                    "**Why this revision?**"
                )

                st.write(
                    option["reason"]
                )

                st.write(
                    f"**Alignment:** "
                    f"{option['old_score']:.0f}% → "
                    f"{option['new_score']:.0f}% "
                    f"(+{option['gain']:.0f})"
                )

                if st.button(
                    "✅ Use This Revision",
                    key=(
                        f"use_revision_"
                        f"{selected['index']}_"
                        f"{number}"
                    ),
                    use_container_width=True
                ):

                    old_score = selected["Overall"]

                    question_index = selected["index"]

                    st.session_state.questions[
                        question_index
                    ] = option["revision"]

                    new_analysis = analyze_questions(
                        st.session_state.questions,
                        clos,
                        plos,
                        target_bloom
                    )

                    st.session_state.analysis = (
                        new_analysis
                    )

                    new_score = new_analysis[
                        question_index
                    ]["Overall"]

                    st.session_state.revision_options = []
                    st.session_state.revision_question_index = None

                    st.success(
                        f"Revision applied successfully: "
                        f"{old_score:.0f}% → "
                        f"{new_score:.0f}%"
                    )

                    if (
                        old_score < 75
                        and new_score >= 75
                    ):

                        st.balloons()

                        st.success(
                            "🏆 Question Attained!"
                        )

                    st.rerun()

                st.divider()

        else:

            st.info(
                "The tool could not find a safe automatic "
                "revision that improves the alignment while "
                "preserving the original topic and meaning."
            )

    # ========================================================
    # SUMMARY
    # ========================================================

    st.header("8️⃣ Workshop Summary")

    total_questions = len(
        analysis
    )

    attained_count = len(
        [
            item
            for item in analysis
            if item["Overall"] >= 75
        ]
    )

    review_count = (
        total_questions
        - attained_count
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "Questions",
            total_questions
        )

    with c2:

        st.metric(
            "Attained",
            attained_count
        )

    with c3:

        st.metric(
            "Need Attention",
            review_count
        )

    # ========================================================
    # EXPORT
    # ========================================================

    st.header("9️⃣ Export Report")

    export_rows = []

    for item in analysis:

        export_rows.append(
            {
                "Question":
                    f"Q{item['index'] + 1}",

                "Question Text":
                    item["question"],

                "Question Type":
                    item["Question Type"],

                "Best Matching CLO":
                    item["CLO"],

                "CLO Match":
                    item["CLO Match"],

                "Best Matching PLO":
                    item["PLO"],

                "PLO Match":
                    item["PLO Match"],

                "Bloom":
                    item["Bloom"],

                "Relevance":
                    item["Relevance"],

                "Clarity":
                    item["Clarity"],

                "Measurability":
                    item["Measurability"],

                "Overall Alignment":
                    item["Overall"],

                "Problem Area":
                    item["Problem Area"],

                "Problem":
                    item["Problem"],

                "Status":
                    status_for_score(
                        item["Overall"]
                    )
            }
        )

    export_df = pd.DataFrame(
        export_rows
    )

    csv_data = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download OBE Quiz Checker Report",
        data=csv_data,
        file_name="obe_quiz_checker_report.csv",
        mime="text/csv",
        use_container_width=True
    )

else:

    st.info(
        "Enter CLOs/PLOs → upload the assessment → "
        "Read Assessment → Analyze Assessment."
    )
