import streamlit as st
import pandas as pd
import io
import os
import re

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

ACTION_VERBS = set(
    word
    for verbs in BLOOM_VERBS.values()
    for word in verbs
)

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on",
    "for", "with", "from", "by", "is", "are", "was", "were",
    "be", "been", "being", "this", "that", "these", "those",
    "as", "at", "it", "its", "into", "their", "there", "which",
    "what", "how", "why", "when", "where", "who", "whom",
    "can", "could", "should", "would", "will", "may", "might",
    "do", "does", "did", "you", "your", "we", "our", "they",
    "them", "he", "she", "his", "her", "than", "then",
    "also", "using", "use", "following", "given",
    "students", "student", "ability", "able", "demonstrate"
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
    "file_name": "",
    "overall_balloons_shown": False
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


def get_numbers(text):
    return re.findall(
        r"\b\d+(?:\.\d+)?\b",
        str(text)
    )


def safe_percentage(value):
    try:
        return max(
            0.0,
            min(100.0, float(value))
        )
    except Exception:
        return 0.0


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text):
    if not text:
        return []

    output = []

    for line in text.replace(
        "\r", "\n"
    ).split("\n"):

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
            output.append(line)

    return output


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(text):
    lower = str(text).lower()
    found = []

    for level, verbs in BLOOM_VERBS.items():
        for verb in verbs:
            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                lower
            ):
                found.append(
                    (level, verb)
                )

    if not found:
        return "understand", "unknown"

    found.sort(
        key=lambda item: BLOOM_LEVELS[item[0]],
        reverse=True
    )

    return found[0]


def bloom_distance_score(
    actual,
    target
):
    if actual not in BLOOM_LEVELS:
        return 78.0

    if target not in BLOOM_LEVELS:
        return 78.0

    difference = abs(
        BLOOM_LEVELS[actual]
        - BLOOM_LEVELS[target]
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


# ============================================================
# QUESTION TYPE
# ============================================================

def detect_question_type(question):
    text = normalize_text(question)
    lower = text.lower()

    options = extract_mcq_options(
        question
    )

    if len(options) >= 2:
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
    ) and re.search(r"\d", text):
        return "Numerical"

    if re.search(
        r"\b(design|develop|construct|implement|perform|demonstrate)\b",
        lower
    ):
        return "Practical/Application"

    if (
        len(text.split()) > 45
        or re.search(
            r"\b(essay|write an essay|write a detailed)\b",
            lower
        )
    ):
        return "Essay/Long Answer"

    return "Short Answer"


def extract_mcq_options(text):
    return re.findall(
        r"(?im)^\s*(?:[A-D][\.\)]|[1-4][\.\)])\s+(.+)$",
        str(text)
    )


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def split_question_blocks(text):
    lines = clean_text(text).split("\n")

    blocks = []
    current = []

    start_pattern = re.compile(
        r"^\s*(?:"
        r"Question\s*\d+"
        r"|Q\s*\d+"
        r"|\d+[\.\)]"
        r")",
        re.I
    )

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if current:
                current.append("")
            continue

        if (
            start_pattern.match(stripped)
            and current
        ):
            block = "\n".join(
                current
            ).strip()

            if len(block) >= 10:
                blocks.append(block)

            current = [stripped]

        else:
            current.append(stripped)

    if current:
        block = "\n".join(
            current
        ).strip()

        if len(block) >= 10:
            blocks.append(block)

    return blocks


def extract_questions(text):
    text = clean_text(text)

    if not text:
        return []

    questions = []

    blocks = split_question_blocks(
        text
    )

    for block in blocks:
        cleaned = re.sub(
            r"^\s*(?:Question\s*)?\d+[\.\):\-]?\s*",
            "",
            block,
            flags=re.I
        )

        cleaned = normalize_text(
            cleaned
        )

        if len(cleaned) >= 10:
            questions.append(
                cleaned
            )

    if len(questions) < 2:
        candidates = re.split(
            r"(?<=[?])\s+",
            text
        )

        for candidate in candidates:
            candidate = normalize_text(
                candidate
            )

            if len(candidate) < 15:
                continue

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
                    questions.append(
                        candidate
                    )

    filtered = []

    for question in questions:
        if len(question.split()) <= 2:
            continue

        if question not in filtered:
            filtered.append(question)

    return filtered


# ============================================================
# FILE READERS
# ============================================================

def read_pdf(uploaded_file):
    if fitz is None:
        return "", (
            "PyMuPDF is not installed. "
            "Add PyMuPDF to requirements.txt."
        )

    try:
        data = uploaded_file.read()

        document = fitz.open(
            stream=data,
            filetype="pdf"
        )

        pages = []

        for page in document:

            text = page.get_text(
                "text"
            )

            if text.strip():
                pages.append(text)

            elif (
                pytesseract is not None
                and Image is not None
            ):
                try:
                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(
                            2, 2
                        ),
                        alpha=False
                    )

                    image = Image.open(
                        io.BytesIO(
                            pix.tobytes("png")
                        )
                    )

                    ocr = pytesseract.image_to_string(
                        image
                    )

                    if ocr.strip():
                        pages.append(
                            ocr
                        )

                except Exception:
                    pass

        document.close()

        return clean_text(
            "\n\n".join(pages)
        ), None

    except Exception as exc:
        return "", (
            f"Could not read PDF: {exc}"
        )


def read_docx(uploaded_file):
    if Document is None:
        return "", (
            "python-docx is not installed."
        )

    try:
        data = uploaded_file.read()

        document = Document(
            io.BytesIO(data)
        )

        output = []

        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                output.append(
                    paragraph.text
                )

        for table in document.tables:
            for row in table.rows:
                output.append(
                    " | ".join(
                        cell.text
                        for cell in row.cells
                    )
                )

        return clean_text(
            "\n".join(output)
        ), None

    except Exception as exc:
        return "", (
            f"Could not read DOCX: {exc}"
        )


def read_pptx(uploaded_file):
    if Presentation is None:
        return "", (
            "python-pptx is not installed."
        )

    try:
        data = uploaded_file.read()

        presentation = Presentation(
            io.BytesIO(data)
        )

        slides = []

        for slide in presentation.slides:
            parts = []

            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    if shape.text.strip():
                        parts.append(
                            shape.text
                        )

            if parts:
                slides.append(
                    "\n".join(parts)
                )

        return clean_text(
            "\n\n".join(slides)
        ), None

    except Exception as exc:
        return "", (
            f"Could not read PPTX: {exc}"
        )


def read_excel(uploaded_file):
    try:
        data = uploaded_file.read()

        workbook = pd.ExcelFile(
            io.BytesIO(data)
        )

        output = []

        for sheet in workbook.sheet_names:

            df = pd.read_excel(
                io.BytesIO(data),
                sheet_name=sheet,
                header=None
            )

            output.append(
                f"Sheet: {sheet}\n"
                + df.fillna("")
                .astype(str)
                .to_string(
                    index=False,
                    header=False
                )
            )

        return clean_text(
            "\n\n".join(output)
        ), None

    except Exception as exc:
        return "", (
            f"Could not read spreadsheet: {exc}"
        )


def read_text_file(uploaded_file):
    try:
        return uploaded_file.read().decode(
            "utf-8",
            errors="ignore"
        ), None
    except Exception as exc:
        return "", (
            f"Could not read text file: {exc}"
        )


def read_image(uploaded_file):
    if Image is None:
        return "", "Pillow is not installed."

    if pytesseract is None:
        return "", "pytesseract is not installed."

    try:
        image = Image.open(
            uploaded_file
        )

        text = pytesseract.image_to_string(
            image
        )

        return clean_text(
            text
        ), None

    except Exception as exc:
        return "", (
            f"Could not read image: {exc}"
        )


def read_uploaded_file(uploaded_file):
    extension = os.path.splitext(
        uploaded_file.name
    )[1].lower()

    if extension == ".pdf":
        return read_pdf(
            uploaded_file
        )

    if extension == ".docx":
        return read_docx(
            uploaded_file
        )

    if extension == ".pptx":
        return read_pptx(
            uploaded_file
        )

    if extension in [
        ".xlsx",
        ".xls"
    ]:
        return read_excel(
            uploaded_file
        )

    if extension == ".csv":
        return read_text_file(
            uploaded_file
        )

    if extension in [
        ".txt",
        ".md"
    ]:
        return read_text_file(
            uploaded_file
        )

    if extension in [
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
        ".tiff"
    ]:
        return read_image(
            uploaded_file
        )

    return "", (
        "Unsupported file type."
    )


# ============================================================
# OUTCOME MATCHING
# ============================================================

def semantic_match(
    question,
    outcome
):
    q_words = word_set(
        question
    )

    o_words = word_set(
        outcome
    )

    if not q_words or not o_words:
        return 0.0

    intersection = q_words.intersection(
        o_words
    )

    outcome_coverage = (
        len(intersection)
        / max(1, len(o_words))
    )

    question_coverage = (
        len(intersection)
        / max(1, len(q_words))
    )

    return max(
        0.0,
        min(
            1.0,
            0.65 * outcome_coverage
            + 0.35 * question_coverage
        )
    )


def score_outcome_match(
    question,
    outcomes
):
    if not outcomes:
        return 80.0, "", 0.0

    matches = []

    for outcome in outcomes:
        matches.append(
            (
                semantic_match(
                    question,
                    outcome
                ),
                outcome
            )
        )

    matches.sort(
        key=lambda item: item[0],
        reverse=True
    )

    raw, best = matches[0]

    if raw >= 0.70:
        score = 95.0
    elif raw >= 0.50:
        score = 88.0
    elif raw >= 0.35:
        score = 78.0
    elif raw >= 0.20:
        score = 68.0
    elif raw > 0:
        score = 60.0
    else:
        score = 55.0

    return score, best, raw


# ============================================================
# OTHER SCORING
# ============================================================

def score_clarity(question):
    score = 98.0
    lower = question.lower()

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

    if len(question.split()) > 90:
        score -= 5

    if "??" in question:
        score -= 3

    return safe_percentage(
        score
    )


def score_measurability(question):
    lower = question.lower()

    score = 92.0

    has_action = any(
        re.search(
            r"\b" + re.escape(verb) + r"\b",
            lower
        )
        for verb in ACTION_VERBS
    )

    if has_action:
        score += 5

    if detect_question_type(
        question
    ) in [
        "MCQ",
        "True/False",
        "Numerical"
    ]:
        score += 2

    return safe_percentage(
        score
    )


def score_relevance(
    clo_score,
    plo_score
):
    values = []

    if clo_score is not None:
        values.append(
            clo_score
        )

    if plo_score is not None:
        values.append(
            plo_score
        )

    if not values:
        return 85.0

    return safe_percentage(
        70 + (
            sum(values)
            / len(values)
        ) * 0.30
    )


# ============================================================
# EVALUATION
# ============================================================

def evaluate_question(
    question,
    clos,
    plos
):
    question = normalize_text(
        question
    )

    q_type = detect_question_type(
        question
    )

    bloom_level, bloom_verb = detect_bloom(
        question
    )

    target_bloom = "understand"

    if clos:
        target_bloom, _ = detect_bloom(
            " ".join(clos)
        )

    bloom_score = bloom_distance_score(
        bloom_level,
        target_bloom
    )

    clo_score, best_clo, clo_raw = (
        score_outcome_match(
            question,
            clos
        )
    )

    plo_score, best_plo, plo_raw = (
        score_outcome_match(
            question,
            plos
        )
    )

    clarity = score_clarity(
        question
    )

    measurability = score_measurability(
        question
    )

    relevance = score_relevance(
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
        "CLO Match": round(
            clo_score,
            1
        ),
        "PLO Match": round(
            plo_score,
            1
        ),
        "Bloom Score": round(
            bloom_score,
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
        "Overall Alignment": round(
            safe_percentage(
                overall
            ),
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

    for number, question in enumerate(
        questions,
        start=1
    ):
        result = evaluate_question(
            question,
            clos,
            plos
        )

        result[
            "Question Number"
        ] = number

        results.append(
            result
        )

    return results


def calculate_overall_score(
    results
):
    if not results:
        return 0.0

    return round(
        sum(
            result[
                "Overall Alignment"
            ]
            for result in results
        )
        / len(results),
        1
    )


# ============================================================
# STATUS
# ============================================================

def score_status(score):
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
        "CLO Match": result["CLO Match"],
        "PLO Match": result["PLO Match"],
        "Bloom Score": result["Bloom Score"],
        "Relevance": result["Relevance"],
        "Clarity": result["Clarity"],
        "Measurability": result["Measurability"]
    }

    return min(
        dimensions,
        key=dimensions.get
    )


# ============================================================
# IMPORTANT:
# DIRECT CLO CONTENT EXTRACTION
#
# The CLO is NEVER printed inside a revised question.
# We extract its actual content and cognitive action.
# ============================================================

def clean_outcome_for_revision(
    outcome
):
    text = normalize_text(
        outcome
    )

    # Remove common outcome prefixes.
    text = re.sub(
        r"^(?:students?|learners?)\s+(?:will\s+)?",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"^(?:be able to|will be able to)\s+",
        "",
        text,
        flags=re.I
    )

    return text.strip()


def extract_action_and_content(
    outcome
):
    """
    Returns:

        action = Bloom cognitive action
        content = actual subject matter from the outcome

    Example:

        "Analyze the causes and effects of climate change."

        -> analyze
        -> "the causes and effects of climate change"
    """

    outcome = clean_outcome_for_revision(
        outcome
    )

    lower = outcome.lower()

    action = None
    action_level = "understand"

    ordered_levels = [
        "create",
        "evaluate",
        "analyze",
        "apply",
        "understand",
        "remember"
    ]

    for level in ordered_levels:
        for verb in BLOOM_VERBS[level]:
            pattern = (
                r"\b"
                + re.escape(verb)
                + r"\b"
            )

            match = re.search(
                pattern,
                lower
            )

            if match:
                action = verb
                action_level = level

                content = outcome[
                    match.end():
                ].strip()

                content = re.sub(
                    r"^[,:;\-]\s*",
                    "",
                    content
                )

                return (
                    action_level,
                    action,
                    content
                )

    return (
        "understand",
        "explain",
        outcome
    )


def remove_outcome_metadata(
    content
):
    content = normalize_text(
        content
    )

    # Remove common ability/outcome phrases.
    patterns = [
        r"\bto\s+enable\s+students\s+to\b",
        r"\bstudents?\s+will\s+be\s+able\s+to\b",
        r"\blearners?\s+will\s+be\s+able\s+to\b",
        r"\bwill\s+be\s+able\s+to\b",
        r"\bbe\s+able\s+to\b"
    ]

    for pattern in patterns:
        content = re.sub(
            pattern,
            "",
            content,
            flags=re.I
        )

    return normalize_text(
        content
    )


def content_phrases_from_outcome(
    outcome
):
    """
    Extract useful subject phrases from a CLO.

    The purpose is not to reproduce the CLO.
    The purpose is to identify the concepts that the
    assessment question should actually test.
    """

    _, _, content = extract_action_and_content(
        outcome
    )

    content = remove_outcome_metadata(
        content
    )

    content = content.rstrip(
        ".; "
    )

    if not content:
        return []

    # Split common coordinated outcome content.
    parts = re.split(
        r"\s+(?:and|as well as|along with)\s+",
        content,
        flags=re.I
    )

    cleaned = []

    for part in parts:
        part = normalize_text(
            part
        )

        part = re.sub(
            r"^(?:the|a|an)\s+",
            "",
            part,
            flags=re.I
        )

        if len(part.split()) >= 2:
            cleaned.append(
                part
            )

    if not cleaned:
        cleaned = [
            content
        ]

    return cleaned


# ============================================================
# DIRECT QUESTION BUILDERS
# ============================================================

def direct_action_sentence(
    action_level,
    content
):
    content = content.strip(
        " .?"
    )

    if action_level == "remember":
        return (
            "Identify "
            + content
            + "."
        )

    if action_level == "understand":
        return (
            "Explain "
            + content
            + "."
        )

    if action_level == "apply":
        return (
            "Apply the relevant principles to "
            + content
            + "."
        )

    if action_level == "analyze":
        return (
            "Analyze "
            + content
            + "."
        )

    if action_level == "evaluate":
        return (
            "Evaluate "
            + content
            + "."
        )

    if action_level == "create":
        return (
            "Design a solution involving "
            + content
            + "."
        )

    return (
        "Explain "
        + content
        + "."
    )


def make_direct_clo_question(
    clo
):
    """
    Converts the actual CLO content into a direct
    assessment question.

    Example:

    CLO:
    "Analyze the causes and effects of climate change."

    Result:
    "Analyze the causes and effects of climate change."
    """

    action_level, action, content = (
        extract_action_and_content(
            clo
        )
    )

    content = remove_outcome_metadata(
        content
    )

    return direct_action_sentence(
        action_level,
        content
    )


# ============================================================
# PRESERVE MCQ
# ============================================================

def get_mcq_stem(
    question
):
    options = extract_mcq_options(
        question
    )

    if not options:
        return normalize_text(
            question
        )

    parts = re.split(
        r"(?im)^\s*(?:[A-D][\.\)]|[1-4][\.\)])\s+",
        question
    )

    stem = parts[0]

    stem = re.sub(
        r"^\s*(?:Question\s*)?\d+[\.\):\-]?\s*",
        "",
        stem,
        flags=re.I
    )

    return normalize_text(
        stem
    )


def format_mcq(
    stem,
    options
):
    output = [
        stem.rstrip(".? ")
        + "?"
    ]

    letters = "ABCD"

    for index, option in enumerate(
        options
    ):
        prefix = (
            letters[index] + ". "
            if index < 4
            else str(index + 1) + ". "
        )

        output.append(
            prefix + option
        )

    return "\n".join(
        output
    )


# ============================================================
# CLO REVISION — QUESTION TYPE PRESERVED
# ============================================================

def revise_mcq(
    original,
    clo
):
    options = extract_mcq_options(
        original
    )

    if not options:
        return make_direct_clo_question(
            clo
        )

    action_level, action, content = (
        extract_action_and_content(
            clo
        )
    )

    old_stem = get_mcq_stem(
        original
    )

    old_stem = old_stem.rstrip(
        ".? "
    )

    # Direct MCQ stems.
    if action_level == "remember":
        stem = (
            "Which option correctly identifies "
            + content
            + "?"
        )

    elif action_level == "understand":
        stem = (
            "Which option best explains "
            + content
            + "?"
        )

    elif action_level == "apply":
        stem = (
            "Which option correctly applies the relevant "
            "principle to "
            + content
            + "?"
        )

    elif action_level == "analyze":
        stem = (
            "Which option best analyzes "
            + content
            + "?"
        )

    elif action_level == "evaluate":
        stem = (
            "Which option best evaluates "
            + content
            + "?"
        )

    elif action_level == "create":
        stem = (
            "Which option represents an appropriate solution "
            "involving "
            + content
            + "?"
        )

    else:
        stem = (
            "Which option best explains "
            + content
            + "?"
        )

    # If the new stem has no relationship to the original
    # topic, retain the original stem and sharpen it.
    if (
        len(
            word_set(old_stem)
            .intersection(
                word_set(content)
            )
        ) == 0
        and len(word_set(content)) > 1
    ):
        stem = (
            old_stem
            + " Which option best addresses "
            + content
            + "?"
        )

    return format_mcq(
        stem,
        options
    )


def revise_true_false(
    original,
    clo
):
    _, action, content = (
        extract_action_and_content(
            clo
        )
    )

    if action in [
        "identify",
        "define",
        "state"
    ]:
        statement = (
            content[:1].upper()
            + content[1:]
        )

        return (
            "Determine whether the following statement is correct: "
            + statement.rstrip(".")
            + ". (True/False)"
        )

    return (
        "Determine whether the following statement is correct: "
        + content[:1].upper()
        + content[1:].rstrip(".")
        + ". (True/False)"
    )


def revise_fill_blank(
    original,
    clo
):
    action_level, action, content = (
        extract_action_and_content(
            clo
        )
    )

    if action_level == "remember":
        return (
            "__________ is the term that describes "
            + content
            + "."
        )

    return (
        "Complete the following statement: "
        + content
        + " __________."
    )


def revise_numerical(
    original,
    clo
):
    """
    Numerical questions keep the original numerical
    information. Only the requested cognitive operation
    is sharpened.
    """

    action_level, action, content = (
        extract_action_and_content(
            clo
        )
    )

    numbers = get_numbers(
        original
    )

    base = normalize_text(
        original
    ).rstrip(".? ")

    if action_level == "apply":
        return (
            base
            + ". Apply the relevant principle to calculate "
            "the required result."
        )

    if action_level == "analyze":
        return (
            base
            + ". Analyze the given values and calculate "
            "the required result."
        )

    if action_level == "evaluate":
        return (
            base
            + ". Evaluate the result using the relevant "
            "principle and justify your answer."
        )

    # For a numerical CLO, retain the original direct
    # calculation rather than adding irrelevant wording.
    return (
        base
        + ". Show the calculation steps and state "
          "the final answer with the appropriate unit."
    )


def revise_case_study(
    original,
    clo
):
    action_level, action, content = (
        extract_action_and_content(
            clo
        )
    )

    base = normalize_text(
        original
    ).rstrip(".? ")

    if action_level == "analyze":
        return (
            base
            + ". Analyze the case by identifying "
              + content
              + "."
        )

    if action_level == "evaluate":
        return (
            base
            + ". Evaluate the case using "
              + content
              + " and support your judgment with evidence."
        )

    if action_level == "apply":
        return (
            base
            + ". Apply the relevant principles to "
              + content
              + " in the case."
        )

    return (
        base
        + ". Explain "
        + content
        + " using evidence from the case."
    )


def revise_essay(
    original,
    clo
):
    action_level, action, content = (
        extract_action_and_content(
            clo
        )
    )

    base = normalize_text(
        original
    ).rstrip(".? ")

    if action_level == "analyze":
        return (
            "Analyze "
            + content
            + " and support your analysis with relevant evidence."
        )

    if action_level == "evaluate":
        return (
            "Evaluate "
            + content
            + " and support your judgment with relevant reasons."
        )

    if action_level == "create":
        return (
            "Design a solution addressing "
            + content
            + " and explain your choices."
        )

    if action_level == "apply":
        return (
            "Apply the relevant principles to "
            + content
            + " and explain your answer."
        )

    return (
        direct_action_sentence(
            action_level,
            content
        )
    )


def revise_short_answer(
    original,
    clo
):
    action_level, action, content = (
        extract_action_and_content(
            clo
        )
    )

    base = normalize_text(
        original
    ).rstrip(".? ")

    # First preference: direct CLO content question.
    direct = direct_action_sentence(
        action_level,
        content
    )

    # If the original question already contains the main
    # subject, preserve it and sharpen the missing action.
    original_words = word_set(
        original
    )

    content_words = word_set(
        content
    )

    overlap = len(
        original_words.intersection(
            content_words
        )
    )

    if overlap >= 1:
        if action_level == "analyze":
            return (
                "Analyze "
                + base
                + " by addressing "
                + content
                + "."
            )

        if action_level == "evaluate":
            return (
                "Evaluate "
                + base
                + " with reference to "
                + content
                + "."
            )

        if action_level == "apply":
            return (
                "Apply the relevant principle to "
                + base
                + "."
            )

    return direct


# ============================================================
# MAIN CLO REVISION
# ============================================================

def generate_clo_revision(
    question,
    clo
):
    """
    Main rule:

    CLO/PLO is used as an internal reference.

    The words "CLO", "PLO", "learning outcome",
    "course learning outcome", etc. are NEVER placed
    in the student-facing question.
    """

    question = normalize_text(
        question
    )

    clo = normalize_text(
        clo
    )

    if not clo:
        return ""

    q_type = detect_question_type(
        question
    )

    if q_type == "MCQ":
        revision = revise_mcq(
            question,
            clo
        )

    elif q_type == "True/False":
        revision = revise_true_false(
            question,
            clo
        )

    elif q_type == "Fill in the Blank":
        revision = revise_fill_blank(
            question,
            clo
        )

    elif q_type == "Numerical":
        revision = revise_numerical(
            question,
            clo
        )

    elif q_type == "Case Study":
        revision = revise_case_study(
            question,
            clo
        )

    elif q_type == "Essay/Long Answer":
        revision = revise_essay(
            question,
            clo
        )

    else:
        revision = revise_short_answer(
            question,
            clo
        )

    revision = normalize_text(
        revision
    )

    return revision


# ============================================================
# REVISION VALIDATION
# ============================================================

def contains_forbidden_outcome_language(
    question
):
    lower = question.lower()

    forbidden = [
        "according to the clo",
        "according to clo",
        "according to the plo",
        "according to plo",
        "learning outcome",
        "course learning outcome",
        "program learning outcome",
        "clo",
        "plo",
        "learning outcomes"
    ]

    return any(
        phrase in lower
        for phrase in forbidden
    )


def preserve_numbers(
    original,
    revised
):
    return (
        get_numbers(original)
        == get_numbers(revised)
    )


def preserve_mcq_options(
    original,
    revised
):
    original_options = extract_mcq_options(
        original
    )

    if not original_options:
        return True

    revised_options = extract_mcq_options(
        revised
    )

    if len(
        original_options
    ) != len(
        revised_options
    ):
        return False

    original_clean = [
        normalize_text(option).lower()
        for option in original_options
    ]

    revised_clean = [
        normalize_text(option).lower()
        for option in revised_options
    ]

    return original_clean == revised_clean


def preserve_question_type(
    original,
    revised
):
    old_type = detect_question_type(
        original
    )

    new_type = detect_question_type(
        revised
    )

    if old_type == new_type:
        return True

    if old_type == "Numerical":
        return new_type == "Numerical"

    return False


def topic_preserved(
    original,
    revised
):
    old_words = word_set(
        original
    )

    new_words = word_set(
        revised
    )

    if not old_words:
        return True

    overlap = len(
        old_words.intersection(
            new_words
        )
    ) / max(
        1,
        len(old_words)
    )

    return overlap >= 0.15


def validate_revision(
    original,
    revised
):
    if not revised:
        return False

    if normalize_text(
        original
    ) == normalize_text(
        revised
    ):
        return False

    if contains_forbidden_outcome_language(
        revised
    ):
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

    if not preserve_question_type(
        original,
        revised
    ):
        return False

    if not topic_preserved(
        original,
        revised
    ):
        return False

    return True


# ============================================================
# DIRECT FALLBACK REVISION
# ============================================================

def fallback_direct_revision(
    question,
    clo
):
    """
    Strong fallback.

    Still does NOT mention CLO/PLO.
    """

    action_level, action, content = (
        extract_action_and_content(
            clo
        )
    )

    q_type = detect_question_type(
        question
    )

    if q_type == "MCQ":
        return revise_mcq(
            question,
            clo
        )

    if q_type == "Numerical":
        return revise_numerical(
            question,
            clo
        )

    if q_type == "Case Study":
        return revise_case_study(
            question,
            clo
        )

    if q_type == "Essay/Long Answer":
        return revise_essay(
            question,
            clo
        )

    return direct_action_sentence(
        action_level,
        content
    )


# ============================================================
# BLOOM REVISION
# ============================================================

def generate_bloom_revision(
    question,
    target_bloom
):
    q_type = detect_question_type(
        question
    )

    base = normalize_text(
        question
    ).rstrip(".? ")

    target = str(
        target_bloom
    ).lower()

    if q_type == "MCQ":
        options = extract_mcq_options(
            question
        )

        stem = get_mcq_stem(
            question
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
                "Which option correctly applies the "
                "relevant concept to "
                + stem
                + "?"
            )

        else:
            new_stem = (
                "Which option best explains "
                + stem
                + "?"
            )

        return format_mcq(
            new_stem,
            options
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
            + " that addresses the key requirements."
        )

    return (
        "Explain "
        + base
        + " clearly."
    )


# ============================================================
# GENERAL REVISION
# ============================================================

def generate_general_revision(
    question,
    result
):
    if result["CLO Match"] < ATTAINMENT_THRESHOLD:
        return generate_clo_revision(
            question,
            result["Best CLO"]
        )

    if result["PLO Match"] < ATTAINMENT_THRESHOLD:
        return generate_clo_revision(
            question,
            result["Best PLO"]
        )

    if result["Bloom Score"] < ATTAINMENT_THRESHOLD:
        return generate_bloom_revision(
            question,
            result["Target Bloom"]
        )

    if result["Clarity"] < ATTAINMENT_THRESHOLD:
        return (
            question.rstrip(".? ")
            + "."
        )

    if result["Measurability"] < ATTAINMENT_THRESHOLD:
        return (
            question.rstrip(".? ")
            + ". Support your answer with relevant evidence."
        )

    return generate_clo_revision(
        question,
        result["Best CLO"]
    )


# ============================================================
# PROBLEM EXPLANATION
# ============================================================

def explain_problem(
    result
):
    if result["CLO Match"] < ATTAINMENT_THRESHOLD:
        return (
            "The question does not sufficiently assess "
            "the concepts or skill expressed in the mapped CLO."
        )

    if result["PLO Match"] < ATTAINMENT_THRESHOLD:
        return (
            "The question provides limited evidence of "
            "the mapped program-level skill."
        )

    if result["Bloom Score"] < ATTAINMENT_THRESHOLD:
        return (
            "The cognitive action in the question does not "
            "closely match the required Bloom level."
        )

    if result["Clarity"] < ATTAINMENT_THRESHOLD:
        return (
            "The wording is not sufficiently precise."
        )

    if result["Measurability"] < ATTAINMENT_THRESHOLD:
        return (
            "The expected student response is not sufficiently "
            "observable or measurable."
        )

    return (
        "The question requires a small alignment improvement."
    )


def identify_revision_source(
    result
):
    if result["CLO Match"] < ATTAINMENT_THRESHOLD:
        return "CLO content"

    if result["PLO Match"] < ATTAINMENT_THRESHOLD:
        return "PLO content"

    if result["Bloom Score"] < ATTAINMENT_THRESHOLD:
        return "Bloom level"

    if result["Clarity"] < ATTAINMENT_THRESHOLD:
        return "Clarity"

    if result["Measurability"] < ATTAINMENT_THRESHOLD:
        return "Measurability"

    return "Alignment"


# ============================================================
# CREATE REVISION
# ============================================================

def create_revision(
    result
):
    question = result["Question"]

    # --------------------------------------------------------
    # CLO ALWAYS HAS PRIORITY
    # --------------------------------------------------------

    if (
        result["CLO Match"]
        < ATTAINMENT_THRESHOLD
    ):
        clo = result["Best CLO"]

        revision = generate_clo_revision(
            question,
            clo
        )

        if not validate_revision(
            question,
            revision
        ):
            revision = fallback_direct_revision(
                question,
                clo
            )

        return {
            "revision": revision,
            "source": "CLO content",
            "problem": (
                "CLO attainment is below 75%."
            ),
            "reason": explain_problem(
                result
            )
        }

    # --------------------------------------------------------
    # PLO
    # --------------------------------------------------------

    if (
        result["PLO Match"]
        < ATTAINMENT_THRESHOLD
    ):
        plo = result["Best PLO"]

        revision = generate_clo_revision(
            question,
            plo
        )

        if not validate_revision(
            question,
            revision
        ):
            revision = fallback_direct_revision(
                question,
                plo
            )

        return {
            "revision": revision,
            "source": "PLO content",
            "problem": (
                "PLO attainment is below 75%."
            ),
            "reason": explain_problem(
                result
            )
        }

    # --------------------------------------------------------
    # OTHER CRITERIA
    # --------------------------------------------------------

    revision = generate_general_revision(
        question,
        result
    )

    if not validate_revision(
        question,
        revision
    ):
        revision = question

    return {
        "revision": revision,
        "source": identify_revision_source(
            result
        ),
        "problem": (
            "The question requires alignment improvement."
        ),
        "reason": explain_problem(
            result
        )
    }


# ============================================================
# RESCORE
# ============================================================

def rescore_revision(
    original_result,
    revised_question,
    clos,
    plos
):
    revised = evaluate_question(
        revised_question,
        clos,
        plos
    )

    revised[
        "Question Number"
    ] = original_result[
        "Question Number"
    ]

    return revised


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>
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
        "Evaluate assessment questions for CLO, PLO, "
        "Bloom's Taxonomy, relevance, clarity, "
        "and measurability."
    )

    st.divider()

    st.caption(
        "Supported: PDF, DOCX, PPTX, XLSX, XLS, "
        "CSV, TXT, MD and image files."
    )

    st.caption(
        "Questions can be MCQs, True/False, "
        "fill-in-the-blank, numerical, case study, "
        "practical, short-answer or essay."
    )


# ============================================================
# HEADER
# ============================================================

st.title("🎓 OBE Quiz Checker")

st.write(
    "Evaluate assessment alignment and automatically "
    "improve questions that fall below the 75% threshold."
)


# ============================================================
# 1. ASSESSMENT INFORMATION
# ============================================================

st.header("1. Assessment Information")

col1, col2, col3 = st.columns(3)

with col1:
    course_name = st.text_input(
        "Course",
        placeholder="e.g., Chemistry"
    )

with col2:
    assessment_name = st.text_input(
        "Assessment",
        placeholder="e.g., Quiz 1"
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
            "Apply scientific principles to solve relevant problems."
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
# 3. UPLOAD
# ============================================================

st.header("3. Upload Complete Assessment")

uploaded_file = st.file_uploader(
    "Upload the complete assessment",
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
            "Reading assessment..."
        ):
            text, error = read_uploaded_file(
                uploaded_file
            )

        if error:
            st.error(error)

        elif not text.strip():
            st.error(
                "No readable text was found."
            )

        else:
            st.session_state.uploaded_text = text

            questions = extract_questions(
                text
            )

            st.session_state.questions = questions
            st.session_state.analysis = []
            st.session_state.revision_candidates = {}
            st.session_state.accepted_revisions = {}
            st.session_state.analyzed = False

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
# DETECTED QUESTIONS
# ============================================================

if st.session_state.questions:

    st.header("Detected Questions")

    for number, question in enumerate(
        st.session_state.questions,
        start=1
    ):
        st.write(
            f"**Question {number}:** {question}"
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
            "Analyzing assessment..."
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

        if overall >= OVERALL_BALLOON_THRESHOLD:
            st.balloons()

        st.success(
            "Assessment analysis completed."
        )


# ============================================================
# ANALYSIS RESULTS
# ============================================================

if (
    st.session_state.analyzed
    and st.session_state.analysis
):

    results = st.session_state.analysis

    # ========================================================
    # 5. OVERALL
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
        attained = sum(
            1
            for result in results
            if result[
                "Overall Alignment"
            ] >= ATTAINMENT_THRESHOLD
        )

        st.metric(
            "Questions Attained",
            f"{attained}/{len(results)}"
        )

    st.progress(
        overall_score / 100
    )

    st.write(
        f"**Status:** {score_status(overall_score)}"
    )

    # ========================================================
    # 6. SCORE ANALYSIS
    # ========================================================

    st.header("6. Assessment Score Analysis")

    metrics = [
        "CLO Match",
        "PLO Match",
        "Bloom Score",
        "Relevance",
        "Clarity",
        "Measurability"
    ]

    averages = {}

    for metric in metrics:
        averages[metric] = round(
            sum(
                result[metric]
                for result in results
            )
            / len(results),
            1
        )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Average CLO Match",
            f"{averages['CLO Match']:.1f}%"
        )

        st.metric(
            "Average PLO Match",
            f"{averages['PLO Match']:.1f}%"
        )

    with c2:
        st.metric(
            "Average Bloom",
            f"{averages['Bloom Score']:.1f}%"
        )

        st.metric(
            "Average Relevance",
            f"{averages['Relevance']:.1f}%"
        )

    with c3:
        st.metric(
            "Average Clarity",
            f"{averages['Clarity']:.1f}%"
        )

        st.metric(
            "Average Measurability",
            f"{averages['Measurability']:.1f}%"
        )

    # ========================================================
    # 7. REVISIONS AT TOP
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
            "🎉 All questions have reached the 75% threshold."
        )

    else:

        st.info(
            "Questions below 75% receive a direct revision. "
            "CLO/PLO problems are handled first."
        )

        for result in weak_results:

            number = result[
                "Question Number"
            ]

            if number not in (
                st.session_state.revision_candidates
            ):

                st.session_state.revision_candidates[
                    number
                ] = create_revision(
                    result
                )

            data = (
                st.session_state.revision_candidates[
                    number
                ]
            )

            revision = data[
                "revision"
            ]

            st.subheader(
                f"Question {number} — "
                f"{result['Overall Alignment']:.1f}%"
            )

            left, right = st.columns(
                2
            )

            with left:

                st.markdown(
                    "**Current Question**"
                )

                st.info(
                    result["Question"]
                )

                st.markdown(
                    "**Problem**"
                )

                st.write(
                    data["problem"]
                )

                st.markdown(
                    "**Why It Was Flagged**"
                )

                st.write(
                    data["reason"]
                )

                st.markdown(
                    "**Revision Focus**"
                )

                st.write(
                    data["source"]
                )

            with right:

                st.markdown(
                    "**Direct Revision**"
                )

                st.success(
                    revision
                )

                # Safety checks shown to user.
                checks = []

                if contains_forbidden_outcome_language(
                    revision
                ):
                    checks.append(
                        "The revision contains outcome terminology."
                    )

                if not preserve_numbers(
                    result["Question"],
                    revision
                ):
                    checks.append(
                        "A numerical value changed."
                    )

                if not preserve_mcq_options(
                    result["Question"],
                    revision
                ):
                    checks.append(
                        "MCQ options changed."
                    )

                if not preserve_question_type(
                    result["Question"],
                    revision
                ):
                    checks.append(
                        "Question type changed."
                    )

                if checks:
                    st.warning(
                        " / ".join(checks)
                    )
                else:
                    st.caption(
                        "✓ Direct question\n"
                        "✓ CLO/PLO wording not exposed\n"
                        "✓ Original question type preserved"
                    )

                if st.button(
                    "Use This Revision",
                    key=f"use_{number}",
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
                        number - 1
                    ] = revision

                    st.session_state.analysis[
                        number - 1
                    ] = revised_result

                    st.session_state.accepted_revisions[
                        number
                    ] = {
                        "original": result[
                            "Question"
                        ],
                        "revised": revision,
                        "old_score": old_score,
                        "new_score": revised_result[
                            "Overall Alignment"
                        ]
                    }

                    st.session_state.revision_candidates.pop(
                        number,
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
                        f"Revision applied: "
                        f"{old_score:.1f}% → "
                        f"{new_score:.1f}%"
                    )

                    st.rerun()

            st.divider()

    # ========================================================
    # ACCEPTED REVISIONS
    # ========================================================

    if st.session_state.accepted_revisions:

        st.subheader(
            "✅ Applied Revisions"
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
                f"Question {number}"
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
        if result[
            "Overall Alignment"
        ] >= ATTAINMENT_THRESHOLD
    ]

    if not attained_results:

        st.info(
            "No questions have reached 75% yet."
        )

    else:

        for result in attained_results:

            st.write(
                f"🏆 **Question "
                f"{result['Question Number']}** — "
                f"{result['Overall Alignment']:.1f}%"
            )

    # ========================================================
    # 9. ONLY GRAPH
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

    rows = []

    for result in st.session_state.analysis:

        rows.append(
            {
                "Question": (
                    f"Q{result['Question Number']}"
                ),
                "Type": result[
                    "Question Type"
                ],
                "CLO": (
                    f"{result['CLO Match']:.1f}%"
                ),
                "PLO": (
                    f"{result['PLO Match']:.1f}%"
                ),
                "Bloom": (
                    f"{result['Bloom Score']:.1f}%"
                ),
                "Relevance": (
                    f"{result['Relevance']:.1f}%"
                ),
                "Clarity": (
                    f"{result['Clarity']:.1f}%"
                ),
                "Measurability": (
                    f"{result['Measurability']:.1f}%"
                ),
                "Overall": (
                    f"{result['Overall Alignment']:.1f}%"
                ),
                "Status": score_status(
                    result[
                        "Overall Alignment"
                    ]
                )
            }
        )

    overview_df = pd.DataFrame(
        rows
    )

    st.dataframe(
        overview_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # 11. DETAILED ANALYSIS
    # ========================================================

    st.header("11. Detailed Question Analysis")

    labels = [
        (
            f"Question {result['Question Number']} — "
            f"{result['Overall Alignment']:.1f}%"
        )
        for result in st.session_state.analysis
    ]

    selected = st.selectbox(
        "Select a question",
        labels
    )

    selected_index = labels.index(
        selected
    )

    result = (
        st.session_state.analysis[
            selected_index
        ]
    )

    st.markdown(
        f"### Question {result['Question Number']}"
    )

    st.info(
        result["Question"]
    )

    st.write(
        f"**Question Type:** "
        f"{result['Question Type']}"
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "CLO Match",
            f"{result['CLO Match']:.1f}%"
        )

        st.metric(
            "PLO Match",
            f"{result['PLO Match']:.1f}%"
        )

    with c2:
        st.metric(
            "Bloom",
            f"{result['Bloom Score']:.1f}%"
        )

        st.metric(
            "Relevance",
            f"{result['Relevance']:.1f}%"
        )

    with c3:
        st.metric(
            "Clarity",
            f"{result['Clarity']:.1f}%"
        )

        st.metric(
            "Measurability",
            f"{result['Measurability']:.1f}%"
        )

    st.progress(
        result["Overall Alignment"]
        / 100
    )

    st.write(
        f"**Overall Alignment:** "
        f"{result['Overall Alignment']:.1f}% "
        f"{score_status(result['Overall Alignment'])}"
    )

    if result["Best CLO"]:
        st.markdown(
            "**Mapped CLO:**"
        )

        st.write(
            result["Best CLO"]
        )

    if result["Best PLO"]:
        st.markdown(
            "**Mapped PLO:**"
        )

        st.write(
            result["Best PLO"]
        )

    st.write(
        f"**Detected Bloom Level:** "
        f"{result['Bloom Level']}"
    )

    st.write(
        f"**Target Bloom Level:** "
        f"{result['Target Bloom']}"
    )

    if (
        result["Overall Alignment"]
        < ATTAINMENT_THRESHOLD
    ):

        st.warning(
            explain_problem(
                result
            )
        )

    else:

        st.success(
            "🏆 This question has reached the 75% threshold."
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
                "Mapped CLO": result[
                    "Best CLO"
                ],
                "Mapped PLO": result[
                    "Best PLO"
                ]
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
