import io
import re
from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# PAGE CONFIGURATION
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

ATTAINED_THRESHOLD = 75

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
        "define",
        "list",
        "name",
        "identify",
        "state",
        "recall",
        "recognize",
        "label",
        "match"
    ],
    "Understand": [
        "describe",
        "explain",
        "summarize",
        "classify",
        "interpret",
        "discuss",
        "illustrate",
        "paraphrase"
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
        "show"
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
        "deconstruct"
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
        "appraise"
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
        "compose"
    ]
}


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "assessment_text": "",
    "questions": [],
    "analysis": [],
    "analysis_complete": False,
    "revision_options": [],
    "revision_question_index": None,
    "celebrate_question": False,
    "celebrate_overall": False,
    "previous_overall": None
}

for key, value in defaults.items():
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
        word
        for word in words
        if word not in stopwords
    ]


def stem_like(word):
    """
    Small conservative normalization.
    It is intentionally simple so that the tool
    does not overclaim semantic understanding.
    """

    word = word.lower()

    endings = [
        "ing",
        "ed",
        "es",
        "s"
    ]

    for ending in endings:

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
# BLOOM DETECTION
# ============================================================

def find_bloom_verb(text):

    normalized = normalize_text(text)

    # Check longer / more specific verbs first
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

        # If the question has a recognizable action verb,
        # do not punish it simply because no target was selected.
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
            outcomes.append(
                cleaned.strip()
            )

    return outcomes


# ============================================================
# OUTCOME MATCHING
# ============================================================

def outcome_similarity(question, outcome):

    q_words = normalized_content_words(
        question
    )

    o_words = normalized_content_words(
        outcome
    )

    if not q_words or not o_words:
        return 0

    overlap = q_words.intersection(
        o_words
    )

    if not overlap:
        return 0

    # Favour meaningful overlap without requiring
    # the question to repeat the entire CLO.
    q_ratio = len(overlap) / len(q_words)
    o_ratio = len(overlap) / len(o_words)

    score = (
        60
        + (q_ratio * 20)
        + (o_ratio * 20)
    )

    return min(100, score)


def best_outcome_match(question, outcomes):

    if not outcomes:
        return "", 70, -1

    scores = []

    for index, outcome in enumerate(
        outcomes
    ):

        score = outcome_similarity(
            question,
            outcome
        )

        scores.append(
            (
                score,
                index,
                outcome
            )
        )

    scores.sort(
        key=lambda item: item[0],
        reverse=True
    )

    best_score, best_index, best_text = (
        scores[0]
    )

    # A completely different question should
    # still receive a lower but not disastrous
    # indicator.
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

    if "true or false" in lower:
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

    numerical_terms = [
        "calculate",
        "compute",
        "solve",
        "find the value",
        "determine the value"
    ]

    if any(
        term in lower
        for term in numerical_terms
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

    result = "\n\n".join(
        pages
    )

    # OCR fallback for scanned PDFs
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

    tables = []

    for table in document.tables:

        for row in table.rows:

            cells = [
                cell.text
                for cell in row.cells
            ]

            tables.append(
                " | ".join(cells)
            )

    return clean_text(
        "\n".join(
            paragraphs + tables
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

    all_text = []

    for sheet in workbook.sheet_names:

        frame = pd.read_excel(
            io.BytesIO(data),
            sheet_name=sheet,
            header=None
        )

        all_text.append(
            f"Sheet: {sheet}"
        )

        all_text.append(
            frame.fillna("")
            .astype(str)
            .to_csv(
                index=False,
                header=False
            )
        )

    return clean_text(
        "\n".join(all_text)
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
# QUALITY INDICATORS
# ============================================================

def clarity_score(question):

    words = question.split()

    score = 100

    if len(words) < 4:
        score -= 12

    if len(words) > 100:
        score -= 5

    vague_phrases = [
        "write something",
        "say something",
        "what do you know",
        "discuss everything",
        "write about this",
        "comment on this",
        "discuss the topic"
    ]

    lower = question.lower()

    for phrase in vague_phrases:

        if phrase in lower:
            score -= 15

    # Very long sentences can still be valid,
    # so use only a small penalty.
    if len(words) > 65:
        score -= 3

    return max(
        55,
        min(100, score)
    )


def measurability_score(
    question,
    question_type
):

    _, bloom = find_bloom_verb(
        question
    )

    score = 94

    if bloom != "Unknown":
        score = 98

    if question_type == "Multiple Choice":
        score = max(
            score,
            95
        )

    if question_type == "True / False":
        score = max(
            score,
            96
        )

    if question_type == "Numerical / Problem Solving":
        score = max(
            score,
            96
        )

    return score


def relevance_score(
    question,
    clo_score,
    plo_score
):

    available = []

    if clo_score is not None:
        available.append(
            clo_score
        )

    if plo_score is not None:
        available.append(
            plo_score
        )

    if not available:
        return 80

    # Relevance should be influenced by outcomes
    # but should not duplicate them exactly.
    average = sum(
        available
    ) / len(available)

    return round(
        min(
            100,
            average + 5
        ),
        1
    )


# ============================================================
# QUESTION DIAGNOSIS
# ============================================================

def identify_problem(
    question,
    clo_score,
    plo_score,
    bloom_score_value,
    clarity,
    measurability,
    target_bloom,
    clo,
    plo
):

    problems = []

    if clo and clo_score < 70:
        problems.append(
            {
                "area": "CLO Alignment",
                "problem": (
                    "The question does not clearly connect "
                    "with the selected CLO."
                ),
                "priority": 1
            }
        )

    if plo and plo_score < 70:
        problems.append(
            {
                "area": "PLO Alignment",
                "problem": (
                    "The question has only a limited "
                    "connection with the selected PLO."
                ),
                "priority": 2
            }
        )

    if (
        target_bloom != "Auto"
        and bloom_score_value < 90
    ):
        problems.append(
            {
                "area": "Bloom Level",
                "problem": (
                    f"The action required by the question "
                    f"does not closely match the selected "
                    f"Bloom level: {target_bloom}."
                ),
                "priority": 1
            }
        )

    if clarity < 85:
        problems.append(
            {
                "area": "Clarity",
                "problem": (
                    "The question leaves some uncertainty "
                    "about what the student should provide "
                    "in the answer."
                ),
                "priority": 1
            }
        )

    if measurability < 85:
        problems.append(
            {
                "area": "Measurability",
                "problem": (
                    "The expected student response is not "
                    "defined clearly enough for consistent "
                    "assessment."
                ),
                "priority": 2
            }
        )

    if not problems:

        problems.append(
            {
                "area": "Minor Refinement",
                "problem": (
                    "The question is already reasonably "
                    "aligned. A small refinement may make "
                    "the expected response even clearer."
                ),
                "priority": 3
            }
        )

    problems.sort(
        key=lambda item: item["priority"]
    )

    return problems[0]


# ============================================================
# OVERALL QUESTION SCORING
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

    # --------------------------------------------------------
    # Automatically find the strongest CLO and PLO.
    # Do NOT assign them cyclically.
    # --------------------------------------------------------

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
        question,
        clo_score,
        plo_score
    )

    # --------------------------------------------------------
    # LENIENT WEIGHTING
    # --------------------------------------------------------
    #
    # CLO       20%
    # PLO       15%
    # Bloom     20%
    # Relevance 15%
    # Clarity   15%
    # Meas.     15%
    #
    # But weak CLO/PLO evidence does not automatically
    # destroy the score.
    # --------------------------------------------------------

    overall = (
        clo_score * 0.20
        + plo_score * 0.15
        + bloom * 0.20
        + relevance * 0.15
        + clarity * 0.15
        + measurability * 0.15
    )

    # Small leniency adjustment.
    # This prevents a reasonable question from being
    # classified too harshly simply because wording differs.
    if overall < 75:
        overall += 4

    if overall < 60:
        overall += 3

    overall = min(
        100,
        round(overall, 1)
    )

    problem = identify_problem(
        question,
        clo_score,
        plo_score,
        bloom,
        clarity,
        measurability,
        target_bloom,
        clo,
        plo
    )

    return {
        "question": question,
        "Question Type": question_type,
        "CLO": clo,
        "CLO Index": clo_index,
        "CLO Match": round(
            clo_score,
            1
        ),
        "PLO": plo,
        "PLO Index": plo_index,
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
            measurability,
            1
        ),
        "Overall": overall,
        "Problem Area": problem["area"],
        "Problem": problem["problem"]
    }


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

        result = evaluate_question(
            question,
            clos,
            plos,
            target_bloom
        )

        result["index"] = index

        results.append(
            result
        )

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
# REVISION ENGINE
# ============================================================

def preserve_special_terms(
    original,
    revised
):

    original_numbers = re.findall(
        r"\b\d+(?:\.\d+)?\b",
        original
    )

    for number in original_numbers:

        if number not in revised:
            return False

    return True


def preserve_core_topic(
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

    overlap = original_words.intersection(
        revised_words
    )

    ratio = (
        len(overlap)
        / len(original_words)
    )

    return ratio >= 0.60


def safe_candidate(
    original,
    candidate,
    clos,
    plos,
    target_bloom
):

    if not candidate:
        return False

    if normalize_text(
        original
    ) == normalize_text(
        candidate
    ):
        return False

    if not preserve_core_topic(
        original,
        candidate
    ):
        return False

    if not preserve_special_terms(
        original,
        candidate
    ):
        return False

    old_score = evaluate_question(
        original,
        clos,
        plos,
        target_bloom
    )["Overall"]

    new_score = evaluate_question(
        candidate,
        clos,
        plos,
        target_bloom
    )["Overall"]

    return new_score >= old_score + 1


def revise_clarity(question):

    replacements = [
        (
            r"\bwhat do you know about\b",
            "Explain"
        ),
        (
            r"\bwrite something about\b",
            "Explain the main features of"
        ),
        (
            r"\bwrite about\b",
            "Explain the main features of"
        ),
        (
            r"\bdiscuss everything about\b",
            "Discuss the key aspects of"
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

    if question_type in [
        "Multiple Choice",
        "True / False",
        "Matching",
        "Fill in the Blank"
    ]:
        return ""

    return (
        question.rstrip(" .?")
        + " Support your answer with relevant points "
        "from the topic."
    )


def revise_bloom(
    question,
    target_bloom
):

    if target_bloom == "Auto":
        return ""

    replacement_verbs = {
        "Remember": "identify",
        "Understand": "explain",
        "Apply": "apply",
        "Analyze": "analyze",
        "Evaluate": "evaluate",
        "Create": "design"
    }

    new_verb = replacement_verbs.get(
        target_bloom
    )

    if not new_verb:
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
        new_verb.capitalize()
        + " "
        + remainder
    )


def revise_outcome(
    question,
    outcome,
    question_type
):

    if not outcome:
        return ""

    outcome_words = [
        word
        for word in content_words(
            outcome
        )
        if len(word) >= 5
    ]

    question_words = set(
        content_words(question)
    )

    missing = []

    for word in outcome_words:

        if word not in question_words:
            missing.append(
                word
            )

    if not missing:
        return ""

    # Only use one or two meaningful outcome terms.
    useful = missing[:2]

    if question_type == "Numerical / Problem Solving":

        return (
            question.rstrip(" .?")
            + " Apply the relevant "
            + " and ".join(useful)
            + " when solving the problem."
        )

    if question_type == "Case Study / Scenario":

        return (
            question.rstrip(" .?")
            + " Address the relevant "
            + " and ".join(useful)
            + " in your response."
        )

    return (
        question.rstrip(" .?")
        + " Relate your answer to "
        + " and ".join(useful)
        + "."
    )


def generate_revision_options(
    question,
    clo,
    plo,
    target_bloom
):

    question_type = detect_question_type(
        question
    )

    candidates = []

    # --------------------------------------------------------
    # OPTION 1: CLARITY
    # --------------------------------------------------------

    clarity = revise_clarity(
        question
    )

    if clarity:

        candidates.append(
            {
                "revision": clarity,
                "focus": "Clarity",
                "reason": (
                    "The original wording is broad or vague. "
                    "The revision makes the expected task "
                    "clearer without changing the topic."
                )
            }
        )

    # --------------------------------------------------------
    # OPTION 2: BLOOM
    # --------------------------------------------------------

    bloom_revision = revise_bloom(
        question,
        target_bloom
    )

    if bloom_revision:

        candidates.append(
            {
                "revision": bloom_revision,
                "focus": "Bloom Level",
                "reason": (
                    "The action verb is adjusted so the "
                    "student performs the selected cognitive "
                    "level more directly."
                )
            }
        )

    # --------------------------------------------------------
    # OPTION 3: MEASURABILITY
    # --------------------------------------------------------

    measurable = revise_measurability(
        question,
        question_type
    )

    if measurable:

        candidates.append(
            {
                "revision": measurable,
                "focus": "Measurability",
                "reason": (
                    "The revision makes the expected response "
                    "more observable and easier to assess."
                )
            }
        )

    # --------------------------------------------------------
    # OPTION 4: CLO / PLO
    # --------------------------------------------------------

    outcome = clo if clo else plo

    outcome_revision = revise_outcome(
        question,
        outcome,
        question_type
    )

    if outcome_revision:

        candidates.append(
            {
                "revision": outcome_revision,
                "focus": "Outcome Alignment",
                "reason": (
                    "The revision makes the relationship "
                    "between the question and the learning "
                    "outcome more explicit."
                )
            }
        )

    # --------------------------------------------------------
    # VALIDATE
    # --------------------------------------------------------

    validated = []
    seen = set()

    original_score = evaluate_question(
        question,
        [clo] if clo else [],
        [plo] if plo else [],
        target_bloom
    )["Overall"]

    for candidate in candidates:

        revision = clean_text(
            candidate["revision"]
        )

        key = normalize_text(
            revision
        )

        if not revision or key in seen:
            continue

        seen.add(key)

        # Use actual selected outcomes for rescoring
        clos = [clo] if clo else []
        plos = [plo] if plo else []

        if not safe_candidate(
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

        gain = (
            new_metrics["Overall"]
            - original_score
        )

        if gain < 1:
            continue

        candidate["revision"] = revision
        candidate["new_metrics"] = new_metrics
        candidate["old_score"] = original_score
        candidate["new_score"] = (
            new_metrics["Overall"]
        )
        candidate["gain"] = round(
            gain,
            1
        )

        validated.append(
            candidate
        )

    validated.sort(
        key=lambda item: item["new_score"],
        reverse=True
    )

    return validated[:3]


# ============================================================
# STATUS HELPERS
# ============================================================

def status_for_score(score):

    if score >= 85:
        return "🟢 Strong"

    if score >= 75:
        return "🟢 Attained"

    if score >= 65:
        return "🟡 Minor Revision"

    if score >= 50:
        return "🟠 Review"

    return "🔴 Needs Revision"


def score_message(score):

    if score >= 85:
        return "Strong alignment"

    if score >= 75:
        return "Attained — minor refinement may still help"

    if score >= 65:
        return "Reasonable alignment — one or two improvements may help"

    if score >= 50:
        return "Needs review"

    return "Needs revision"


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("🎓 OBE Quiz Checker")

    st.write(
        "A practical workshop tool for checking "
        "assessment alignment and revising questions."
    )

    st.divider()

    target_bloom = st.selectbox(
        "Target Bloom Level",
        ["Auto"] + BLOOM_LEVELS
    )

    st.divider()

    st.caption(
        "Score interpretation"
    )

    st.success(
        "75%+ = Attained"
    )

    st.info(
        "The percentage is an alignment indicator, "
        "not a final judgment of teaching quality."
    )


# ============================================================
# TITLE
# ============================================================

st.title("🎓 OBE Quiz Checker")

st.write(
    "Upload an assessment, provide CLOs/PLOs, and let "
    "the tool identify which questions are aligned, "
    "which need attention, and how a weak question can "
    "be revised without changing its original topic."
)


# ============================================================
# STEP 1
# ============================================================

st.header("1️⃣ Assessment Information")

col1, col2 = st.columns(2)

with col1:

    course_name = st.text_input(
        "Course / Subject",
        placeholder=(
            "e.g., English I, Chemistry, "
            "Computer Science, Mathematics"
        )
    )

with col2:

    assessment_name = st.text_input(
        "Assessment",
        placeholder=(
            "e.g., Quiz 1, Assignment, Midterm"
        )
    )


# ============================================================
# STEP 2
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
# STEP 3
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
                "Reading the complete assessment..."
            ):

                text = read_uploaded_file(
                    uploaded_file
                )

            questions = extract_questions(
                text
            )

            st.session_state.assessment_text = (
                text
            )

            st.session_state.questions = (
                questions
            )

            st.session_state.analysis = []

            st.session_state.analysis_complete = False

            st.success(
                f"Assessment read successfully. "
                f"{len(questions)} question(s) detected."
            )

        except Exception as error:

            st.error(
                f"Could not read the assessment: {error}"
            )


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):

    text = clean_text(text)

    if not text:
        return []

    lines = text.splitlines()

    questions = []
    current = []

    numbered = re.compile(
        r"^\s*(?:Q(?:uestion)?\.?\s*)?\d+\s*[\)\.\-:]\s+",
        flags=re.I
    )

    for line in lines:

        line = line.strip()

        if not line:
            continue

        if numbered.match(line):

            if current:

                block = clean_text(
                    " ".join(current)
                )

                block = re.sub(
                    r"^\s*(?:Q(?:uestion)?\.?\s*)?\d+\s*[\)\.\-:]\s*",
                    "",
                    block,
                    flags=re.I
                )

                if len(block.split()) >= 3:
                    questions.append(
                        block
                    )

            current = [line]

        else:

            if current:
                current.append(line)

    if current:

        block = clean_text(
            " ".join(current)
        )

        block = re.sub(
            r"^\s*(?:Q(?:uestion)?\.?\s*)?\d+\s*[\)\.\-:]\s*",
            "",
            block,
            flags=re.I
        )

        if len(block.split()) >= 3:
            questions.append(
                block
            )

    # Paragraph fallback
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
                fallback.append(
                    paragraph
                )

        if len(fallback) >= 2:
            questions = fallback

    unique = []
    seen = set()

    for question in questions:

        key = normalize_text(
            question
        )

        if key and key not in seen:

            unique.append(
                question
            )

            seen.add(key)

    return unique


# ============================================================
# VIEW EXTRACTED TEXT
# ============================================================

if st.session_state.assessment_text:

    with st.expander(
        "📄 View Extracted Assessment"
    ):

        st.text(
            st.session_state.assessment_text[
                :20000
            ]
        )


# ============================================================
# STEP 4
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
            "Checking alignment..."
        ):

            analysis = analyze_questions(
                st.session_state.questions,
                clos,
                plos,
                target_bloom
            )

        st.session_state.analysis = (
            analysis
        )

        st.session_state.analysis_complete = True

        st.session_state.revision_options = []

        st.session_state.revision_question_index = None

        st.success(
            "Assessment analysis completed."
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
    # OVERALL SCORE
    # ========================================================

    st.header("5️⃣ Overall Alignment")

    if overall >= 85:

        st.success(
            f"🎯 {overall:.0f}% — Strong alignment"
        )

    elif overall >= 75:

        st.success(
            f"🟢 {overall:.0f}% — Attained"
        )

    elif overall >= 65:

        st.warning(
            f"🟡 {overall:.0f}% — Minor revision recommended"
        )

    elif overall >= 50:

        st.warning(
            f"🟠 {overall:.0f}% — Review needed"
        )

    else:

        st.error(
            f"🔴 {overall:.0f}% — Needs revision"
        )

    st.caption(
        "This score is an OBE Alignment Indicator based "
        "on the stated CLO/PLO, Bloom level and observable "
        "features of the question."
    )


    # ========================================================
    # AVERAGE METRICS
    # ========================================================

    metric_names = [
        "CLO Match",
        "PLO Match",
        "Bloom",
        "Relevance",
        "Clarity",
        "Measurability"
    ]

    averages = {}

    for metric in metric_names:

        averages[metric] = round(
            sum(
                item[metric]
                for item in analysis
            )
            / len(analysis),
            1
        )

    cols = st.columns(6)

    for col, metric in zip(
        cols,
        metric_names
    ):

        with col:

            st.metric(
                metric,
                f"{averages[metric]:.0f}%"
            )


    # ========================================================
    # ONE GRAPH ONLY
    # ========================================================

    st.subheader(
        "📊 Alignment Overview"
    )

    graph_df = pd.DataFrame(
        {
            "Metric": metric_names,
            "Score": [
                averages[m]
                for m in metric_names
            ]
        }
    )

    st.bar_chart(
        graph_df.set_index(
            "Metric"
        )
    )


    # ========================================================
    # QUESTION-BY-QUESTION OVERVIEW
    # ========================================================

    st.header(
        "6️⃣ Question Overview"
    )

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
                "Clarity": item["Clarity"],
                "Overall": item["Overall"],
                "Status": status_for_score(
                    item["Overall"]
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
    # ATTAINED QUESTIONS
    # ========================================================

    st.header("🏆 Attained Questions")

    attained = [
        item
        for item in analysis
        if item["Overall"] >= 75
    ]

    if attained:

        st.success(
            f"{len(attained)} question(s) are at "
            "the Attained level."
        )

        for item in attained:

            with st.expander(
                f"🟢 Q{item['index'] + 1} — "
                f"{item['Overall']:.0f}%"
            ):

                st.write(
                    item["question"]
                )

                st.caption(
                    score_message(
                        item["Overall"]
                    )
                )

    else:

        st.info(
            "No question has reached 75% yet."
        )


    # ========================================================
    # QUESTION REVISION
    # ========================================================

    st.header(
        "7️⃣ Improve a Question"
    )

    st.write(
        "Choose one question. The tool will explain "
        "the actual issue and generate a practical "
        "revision using the original question."
    )

    labels = []

    for item in analysis:

        labels.append(
            f"{item['index'] + 1}. "
            f"{item['Overall']:.0f}% — "
            f"{item['Problem Area']}"
        )

    selected_label = st.selectbox(
        "Select a question to review",
        labels
    )

    selected_position = labels.index(
        selected_label
    )

    selected = analysis[
        selected_position
    ]


    # --------------------------------------------------------
    # CURRENT QUESTION
    # --------------------------------------------------------

    st.subheader(
        f"Q{selected['index'] + 1} — "
        f"Current Question"
    )

    st.info(
        selected["question"]
    )

    st.write(
        f"**Current alignment: "
        f"{selected['Overall']:.0f}% — "
        f"{status_for_score(selected['Overall'])}**"
    )


    # --------------------------------------------------------
    # ACTUAL PROBLEM
    # --------------------------------------------------------

    st.subheader(
        "🔎 What is the problem?"
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
            f"**Detected action:** "
            f"{detected_verb} "
            f"({detected_bloom})"
        )

    else:

        st.write(
            "**Detected action:** "
            "No clear Bloom action verb"
        )


    # --------------------------------------------------------
    # GENERATE
    # --------------------------------------------------------

    if st.button(
        "✨ Show Practical Revision",
        type="primary",
        use_container_width=True
    ):

        revisions = generate_revision_options(
            selected["question"],
            selected["CLO"],
            selected["PLO"],
            target_bloom
        )

        st.session_state.revision_options = (
            revisions
        )

        st.session_state.revision_question_index = (
            selected["index"]
        )


    # --------------------------------------------------------
    # REVISION
    # --------------------------------------------------------

    revisions = (
        st.session_state.revision_options
    )

    same_question = (
        st.session_state.revision_question_index
        == selected["index"]
    )

    if revisions and same_question:

        st.subheader(
            "🛠 Recommended Revision"
        )

        for number, option in enumerate(
            revisions
        ):

            st.markdown(
                f"### Option {number + 1} — "
                f"{option['focus']}"
            )

            st.write(
                "**Original:**"
            )

            st.info(
                selected["question"]
            )

            st.write(
                "**Revised question:**"
            )

            st.success(
                option["revision"]
            )

            st.write(
                "**What changed:**"
            )

            st.write(
                option["reason"]
            )

            # ----------------------------------------------
            # SCORE CHANGE
            # ----------------------------------------------

            old_score = option[
                "old_score"
            ]

            new_score = option[
                "new_score"
            ]

            gain = option[
                "gain"
            ]

            st.write(
                f"**Alignment indicator:** "
                f"{old_score:.0f}% → "
                f"{new_score:.0f}% "
                f"**(+{gain:.0f} points)**"
            )

            st.caption(
                "The new score is calculated only after "
                "checking that the original topic and "
                "important details have been preserved."
            )

            # ----------------------------------------------
            # USE REVISION
            # ----------------------------------------------

            if st.button(
                "✅ Use This Revision",
                key=(
                    f"revision_"
                    f"{selected['index']}_"
                    f"{number}"
                ),
                use_container_width=True
            ):

                old_question_score = (
                    selected["Overall"]
                )

                old_overall = overall_score(
                    analysis
                )

                question_index = (
                    selected["index"]
                )

                st.session_state.questions[
                    question_index
                ] = option["revision"]

                updated_analysis = (
                    analyze_questions(
                        st.session_state.questions,
                        clos,
                        plos,
                        target_bloom
                    )
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

                if (
                    old_question_score < 75
                    and new_question_score >= 75
                ):

                    st.session_state.celebrate_question = True

                if (
                    old_overall < 75
                    and new_overall >= 75
                ):

                    st.session_state.celebrate_overall = True

                st.success(
                    f"Question updated: "
                    f"{old_question_score:.0f}% → "
                    f"{new_question_score:.0f}%"
                )

                if new_question_score >= 75:

                    st.success(
                        "🏆 Question Attained!"
                    )

                    st.balloons()

                st.rerun()

            st.divider()


    elif same_question:

        st.info(
            "The tool could not find a safe automatic "
            "revision that improves the alignment while "
            "preserving the original meaning and topic."
        )


    # ========================================================
    # SUMMARY
    # ========================================================

    st.header("8️⃣ Workshop Summary")

    total = len(
        analysis
    )

    attained_count = len(
        [
            item
            for item in analysis
            if item["Overall"] >= 75
        ]
    )

    revision_count = total - attained_count

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "Questions",
            total
        )

    with c2:

        st.metric(
            "Attained",
            attained_count
        )

    with c3:

        st.metric(
            "Need Attention",
            revision_count
        )


    # ========================================================
    # EXPORT
    # ========================================================

    st.header("9️⃣ Export Report")

    export_rows = []

    for item in analysis:

        export_rows.append(
            {
                "Question": (
                    f"Q{item['index'] + 1}"
                ),
                "Question Text": item["question"],
                "Question Type": item["Question Type"],
                "Best Matching CLO": item["CLO"],
                "CLO Match": item["CLO Match"],
                "Best Matching PLO": item["PLO"],
                "PLO Match": item["PLO Match"],
                "Bloom": item["Bloom"],
                "Relevance": item["Relevance"],
                "Clarity": item["Clarity"],
                "Measurability": item["Measurability"],
                "Overall Alignment": item["Overall"],
                "Problem Area": item["Problem Area"],
                "Problem": item["Problem"],
                "Status": status_for_score(
                    item["Overall"]
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
        "⬇️ Download OBE Quiz Checker Report",
        data=csv_data,
        file_name="obe_quiz_checker_report.csv",
        mime="text/csv",
        use_container_width=True
    )


# ============================================================
# INITIAL INSTRUCTION
# ============================================================

if not st.session_state.analysis:

    st.info(
        "Enter the CLOs/PLOs → upload the complete assessment "
        "→ Read Assessment → Analyze Assessment. "
        "Then select any question to see the actual problem "
        "and a practical revision."
    )
