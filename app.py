import streamlit as st
import pandas as pd
import re
import io
import os
import math

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

BLOOM_LEVELS = {
    "Remember": 1,
    "Understand": 2,
    "Apply": 3,
    "Analyze": 4,
    "Evaluate": 5,
    "Create": 6
}

BLOOM_VERBS = {
    "Remember": [
        "define", "identify", "list", "name", "state",
        "recall", "recognize", "select"
    ],
    "Understand": [
        "describe", "explain", "summarize", "summarise",
        "interpret", "classify", "discuss"
    ],
    "Apply": [
        "apply", "calculate", "solve", "demonstrate",
        "use", "compute", "implement"
    ],
    "Analyze": [
        "analyze", "analyse", "differentiate", "compare",
        "contrast", "examine", "investigate"
    ],
    "Evaluate": [
        "evaluate", "assess", "judge", "critique",
        "justify", "defend", "recommend"
    ],
    "Create": [
        "create", "design", "develop", "construct",
        "formulate", "produce", "propose"
    ]
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on",
    "for", "with", "from", "by", "is", "are", "was", "were",
    "be", "been", "being", "this", "that", "these", "those",
    "as", "at", "it", "its", "into", "their", "there", "which",
    "what", "how", "why", "when", "where", "who", "can", "could",
    "should", "would", "will", "may", "might", "do", "does",
    "did", "you", "your", "we", "our", "they", "them", "using",
    "use", "given", "following", "following", "based"
}


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "uploaded_text": "",
    "questions": [],
    "analysis": [],
    "file_name": "",
    "analyzed": False,
    "revisions": {},
    "accepted_revisions": {},
    "overall_balloons": False
}

for key, value in DEFAULT_STATE.items():
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
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_text(text):
    text = clean_text(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text):
    tokens = re.findall(
        r"[A-Za-z][A-Za-z0-9'-]+",
        str(text).lower()
    )

    return {
        t for t in tokens
        if t not in STOPWORDS and len(t) > 2
    }


def extract_numbers(text):
    return re.findall(
        r"\b\d+(?:\.\d+)?\b",
        str(text)
    )


# ============================================================
# LEARNING OUTCOME PARSER
# ============================================================

def parse_outcomes(text):
    text = clean_text(text)

    if not text:
        return []

    outcomes = []

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        line = re.sub(
            r"^\s*(?:[-•*]|\d+[\.\)]|CLO\s*\d*\s*[:\-]?|PLO\s*\d*\s*[:\-]?)\s*",
            "",
            line,
            flags=re.IGNORECASE
        )

        line = normalize_text(line)

        if len(line) >= 5:
            outcomes.append(line)

    return list(dict.fromkeys(outcomes))


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(text):

    low = str(text).lower()

    detected = []

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                low
            ):
                detected.append(
                    (
                        BLOOM_LEVELS[level],
                        level,
                        verb
                    )
                )

    if not detected:
        return "Understand", "unknown"

    detected.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return detected[0][1], detected[0][2]


# ============================================================
# QUESTION TYPE DETECTION
# ============================================================

def detect_question_type(question):

    q = normalize_text(question)
    low = q.lower()

    options = re.findall(
        r"(?im)^\s*(?:[A-D][\.\)]|[1-4][\.\)])\s+.+$",
        question
    )

    if len(options) >= 2:
        return "MCQ"

    if re.search(
        r"\btrue\s*/\s*false\b|\btrue\s+or\s+false\b",
        low
    ):
        return "True/False"

    if "_" in question:
        return "Fill in the Blank"

    if "fill in the blank" in low:
        return "Fill in the Blank"

    if (
        "case study" in low
        or "read the case" in low
        or "scenario" in low
        or "case:" in low
    ):
        return "Case Study"

    numerical_words = [
        "calculate",
        "compute",
        "solve",
        "determine"
    ]

    numerical_context = [
        "velocity",
        "speed",
        "distance",
        "time",
        "mass",
        "force",
        "energy",
        "probability",
        "percentage",
        "equation",
        "formula"
    ]

    if (
        any(
            re.search(
                r"\b" + re.escape(v) + r"\b",
                low
            )
            for v in numerical_words
        )
        and (
            bool(re.search(r"\d", question))
            or any(x in low for x in numerical_context)
        )
    ):
        return "Numerical"

    if any(
        re.search(
            r"\b" + re.escape(v) + r"\b",
            low
        )
        for v in [
            "design",
            "develop",
            "construct",
            "implement",
            "perform",
            "demonstrate"
        ]
    ):
        return "Practical/Application"

    if (
        len(q.split()) > 45
        or "essay" in low
        or "write a detailed" in low
    ):
        return "Essay/Long Answer"

    return "Short Answer"


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):

    text = clean_text(text)

    if not text:
        return []

    questions = []

    # --------------------------------------------------------
    # METHOD 1:
    # Questions explicitly numbered Q1, Q2, 1., 2), etc.
    # --------------------------------------------------------

    lines = text.splitlines()

    current = []

    question_start_pattern = re.compile(
        r"^\s*(?:"
        r"Q(?:uestion)?\s*\d+"
        r"|"
        r"\d+\s*[\.\):\-]"
        r")\s*",
        re.IGNORECASE
    )

    for line in lines:

        line = line.strip()

        if not line:
            continue

        if question_start_pattern.match(line):

            if current:

                block = "\n".join(current).strip()

                if len(block) >= 10:
                    questions.append(block)

            current = [line]

        else:

            if current:
                current.append(line)

    if current:

        block = "\n".join(current).strip()

        if len(block) >= 10:
            questions.append(block)

    # --------------------------------------------------------
    # Remove question numbers
    # --------------------------------------------------------

    cleaned_questions = []

    for q in questions:

        q = re.sub(
            r"^\s*(?:Question\s*)?\d+\s*[\.\):\-]?\s*",
            "",
            q,
            flags=re.IGNORECASE
        )

        q = normalize_text(q)

        if len(q) >= 10:
            cleaned_questions.append(q)

    questions = cleaned_questions

    # --------------------------------------------------------
    # METHOD 2:
    # Split on question marks if numbering was not detected.
    # --------------------------------------------------------

    if len(questions) < 2:

        candidates = re.split(
            r"(?<=\?)\s+",
            text
        )

        for candidate in candidates:

            candidate = normalize_text(candidate)

            if len(candidate) < 15:
                continue

            if "?" in candidate:

                if candidate not in questions:
                    questions.append(candidate)

    # --------------------------------------------------------
    # METHOD 3:
    # Detect common question-opening verbs.
    # --------------------------------------------------------

    if len(questions) < 2:

        for line in text.splitlines():

            line = normalize_text(line)

            if len(line) < 15:
                continue

            if re.match(
                r"(?i)^(define|explain|describe|discuss|"
                r"calculate|compute|solve|analyze|analyse|"
                r"evaluate|compare|contrast|identify|"
                r"what|why|how|which|determine|state|"
                r"list|write|design|develop|apply)\b",
                line
            ):

                if line not in questions:
                    questions.append(line)

    # --------------------------------------------------------
    # Remove obvious non-question headings
    # --------------------------------------------------------

    final_questions = []

    bad_starts = [
        "instructions",
        "section a",
        "section b",
        "section c",
        "quiz",
        "assessment",
        "answer key",
        "total marks",
        "name:",
        "roll no:",
        "date:"
    ]

    for q in questions:

        low = q.lower().strip()

        if any(
            low.startswith(x)
            for x in bad_starts
        ):
            continue

        if len(q.split()) < 3:
            continue

        final_questions.append(q)

    return list(dict.fromkeys(final_questions))


# ============================================================
# FILE READING
# ============================================================

def read_uploaded_file(uploaded_file):

    extension = os.path.splitext(
        uploaded_file.name
    )[1].lower()

    try:

        file_bytes = uploaded_file.getvalue()

        # ----------------------------------------------------
        # PDF
        # ----------------------------------------------------

        if extension == ".pdf":

            if fitz is None:

                return "", (
                    "PyMuPDF is not installed. "
                    "Add PyMuPDF to requirements.txt."
                )

            document = fitz.open(
                stream=file_bytes,
                filetype="pdf"
            )

            pages = []

            for page in document:

                page_text = page.get_text("text")

                if page_text and page_text.strip():

                    pages.append(page_text)

                else:

                    if (
                        pytesseract is not None
                        and Image is not None
                    ):

                        try:

                            pix = page.get_pixmap(
                                matrix=fitz.Matrix(2, 2),
                                alpha=False
                            )

                            image_bytes = pix.tobytes(
                                "png"
                            )

                            image = Image.open(
                                io.BytesIO(image_bytes)
                            )

                            ocr_text = pytesseract.image_to_string(
                                image
                            )

                            if ocr_text.strip():
                                pages.append(ocr_text)

                        except Exception:
                            pass

            document.close()

            return clean_text(
                "\n\n".join(pages)
            ), ""

        # ----------------------------------------------------
        # DOCX
        # ----------------------------------------------------

        if extension == ".docx":

            if Document is None:

                return "", (
                    "python-docx is not installed."
                )

            document = Document(
                io.BytesIO(file_bytes)
            )

            parts = []

            for paragraph in document.paragraphs:

                if paragraph.text.strip():
                    parts.append(paragraph.text)

            for table in document.tables:

                for row in table.rows:

                    row_text = []

                    for cell in row.cells:
                        row_text.append(cell.text)

                    parts.append(
                        " | ".join(row_text)
                    )

            return clean_text(
                "\n".join(parts)
            ), ""

        # ----------------------------------------------------
        # PPTX
        # ----------------------------------------------------

        if extension == ".pptx":

            if Presentation is None:

                return "", (
                    "python-pptx is not installed."
                )

            presentation = Presentation(
                io.BytesIO(file_bytes)
            )

            parts = []

            for slide in presentation.slides:

                for shape in slide.shapes:

                    if hasattr(shape, "text"):

                        if shape.text.strip():
                            parts.append(shape.text)

            return clean_text(
                "\n".join(parts)
            ), ""

        # ----------------------------------------------------
        # XLSX / XLS
        # ----------------------------------------------------

        if extension in [".xlsx", ".xls"]:

            excel = pd.ExcelFile(
                io.BytesIO(file_bytes)
            )

            parts = []

            for sheet in excel.sheet_names:

                dataframe = pd.read_excel(
                    io.BytesIO(file_bytes),
                    sheet_name=sheet,
                    header=None
                )

                dataframe = dataframe.fillna("")

                parts.append(
                    "Sheet: "
                    + str(sheet)
                    + "\n"
                    + dataframe.astype(str).to_string(
                        index=False,
                        header=False
                    )
                )

            return clean_text(
                "\n\n".join(parts)
            ), ""

        # ----------------------------------------------------
        # CSV
        # ----------------------------------------------------

        if extension == ".csv":

            text = file_bytes.decode(
                "utf-8",
                errors="ignore"
            )

            return clean_text(text), ""

        # ----------------------------------------------------
        # TXT / MD
        # ----------------------------------------------------

        if extension in [".txt", ".md"]:

            text = file_bytes.decode(
                "utf-8",
                errors="ignore"
            )

            return clean_text(text), ""

        # ----------------------------------------------------
        # IMAGE
        # ----------------------------------------------------

        if extension in [
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".bmp",
            ".tiff"
        ]:

            if Image is None:
                return "", "Pillow is not installed."

            if pytesseract is None:
                return "", "pytesseract is not installed."

            image = Image.open(
                io.BytesIO(file_bytes)
            )

            text = pytesseract.image_to_string(
                image
            )

            return clean_text(text), ""

        return "", (
            "Unsupported file format. "
            "Please upload PDF, DOCX, PPTX, XLSX, CSV, TXT, "
            "MD, PNG, JPG, JPEG, WEBP, BMP or TIFF."
        )

    except Exception as error:

        return "", (
            "Could not read the uploaded file: "
            + str(error)
        )


# ============================================================
# MATCHING
# ============================================================

def semantic_match(question, outcome):

    question_words = tokenize(question)
    outcome_words = tokenize(outcome)

    if not question_words or not outcome_words:
        return 0.0

    common = question_words.intersection(
        outcome_words
    )

    question_ratio = (
        len(common) /
        max(1, len(question_words))
    )

    outcome_ratio = (
        len(common) /
        max(1, len(outcome_words))
    )

    return (
        0.65 * outcome_ratio
        + 0.35 * question_ratio
    )


def calculate_outcome_score(
    question,
    outcomes
):

    if not outcomes:

        return 80.0, "", 0.0

    matches = []

    for outcome in outcomes:

        score = semantic_match(
            question,
            outcome
        )

        matches.append(
            (score, outcome)
        )

    matches.sort(
        key=lambda x: x[0],
        reverse=True
    )

    raw_score, best_outcome = matches[0]

    if raw_score >= 0.70:
        score = 95

    elif raw_score >= 0.50:
        score = 88

    elif raw_score >= 0.35:
        score = 78

    elif raw_score >= 0.20:
        score = 68

    elif raw_score > 0:
        score = 60

    else:
        score = 55

    return (
        float(score),
        best_outcome,
        raw_score
    )


# ============================================================
# QUALITY METRICS
# ============================================================

def calculate_clarity(question):

    score = 98.0

    low = question.lower()

    vague_phrases = [
        "discuss this",
        "explain this",
        "write something",
        "say something",
        "comment on it",
        "do the needful"
    ]

    for phrase in vague_phrases:

        if phrase in low:
            score -= 8

    if len(question.split()) > 90:
        score -= 5

    if "??" in question:
        score -= 3

    if "etc." in low:
        score -= 3

    if "and so on" in low:
        score -= 3

    return max(
        0,
        min(100, score)
    )


def calculate_measurability(question):

    score = 92.0

    low = question.lower()

    all_verbs = []

    for verbs in BLOOM_VERBS.values():
        all_verbs.extend(verbs)

    if any(
        re.search(
            r"\b" + re.escape(verb) + r"\b",
            low
        )
        for verb in all_verbs
    ):
        score += 5

    if detect_question_type(question) in [
        "MCQ",
        "True/False",
        "Numerical"
    ]:
        score += 2

    return min(
        100,
        score
    )


def calculate_bloom_score(
    question,
    clos
):

    question_level, question_verb = detect_bloom(
        question
    )

    if not clos:

        target_level = "Understand"

    else:

        detected = []

        for clo in clos:

            level, _ = detect_bloom(clo)

            detected.append(
                BLOOM_LEVELS.get(
                    level,
                    2
                )
            )

        target_number = max(detected)

        target_level = next(
            (
                name
                for name, number
                in BLOOM_LEVELS.items()
                if number == target_number
            ),
            "Understand"
        )

    question_number = BLOOM_LEVELS.get(
        question_level,
        2
    )

    target_number = BLOOM_LEVELS.get(
        target_level,
        2
    )

    difference = abs(
        question_number - target_number
    )

    if difference == 0:
        score = 100

    elif difference == 1:
        score = 92

    elif difference == 2:
        score = 84

    elif difference == 3:
        score = 78

    else:
        score = 72

    return (
        score,
        question_level,
        question_verb,
        target_level
    )


# ============================================================
# COMPLETE EVALUATION
# ============================================================

def evaluate_question(
    question,
    clos,
    plos
):

    clo_score, best_clo, clo_raw = calculate_outcome_score(
        question,
        clos
    )

    plo_score, best_plo, plo_raw = calculate_outcome_score(
        question,
        plos
    )

    (
        bloom_score,
        bloom_level,
        bloom_verb,
        target_bloom
    ) = calculate_bloom_score(
        question,
        clos
    )

    clarity = calculate_clarity(
        question
    )

    measurability = calculate_measurability(
        question
    )

    relevance = (
        70
        + (
            (clo_score + plo_score) / 2
        ) * 0.30
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
        "Question Type": detect_question_type(question),
        "Bloom Level": bloom_level,
        "Bloom Verb": bloom_verb,
        "Target Bloom": target_bloom,
        "CLO Match": round(clo_score, 1),
        "PLO Match": round(plo_score, 1),
        "Bloom Score": round(bloom_score, 1),
        "Relevance": round(relevance, 1),
        "Clarity": round(clarity, 1),
        "Measurability": round(measurability, 1),
        "Overall Alignment": round(overall, 1),
        "Best CLO": best_clo,
        "Best PLO": best_plo,
        "CLO Raw": clo_raw,
        "PLO Raw": plo_raw
    }


# ============================================================
# STATUS
# ============================================================

def get_status(score):

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
# REVISION HELPERS
# ============================================================

def get_outcome_action_and_content(outcome):

    outcome = normalize_text(
        outcome
    ).rstrip(".?")

    if not outcome:
        return (
            "Understand",
            "explain",
            ""
        )

    level, verb = detect_bloom(
        outcome
    )

    content = re.sub(
        r"^\s*"
        + re.escape(verb)
        + r"\s+",
        "",
        outcome,
        flags=re.IGNORECASE
    )

    content = re.sub(
        r"^\s*(students?\s+will\s+)",
        "",
        content,
        flags=re.IGNORECASE
    )

    return (
        level,
        verb,
        normalize_text(content)
    )


def get_mcq_options(question):

    return re.findall(
        r"(?im)^\s*(?:[A-D][\.\)]|[1-4][\.\)])\s+(.+)$",
        question
    )


def get_mcq_stem(question):

    parts = re.split(
        r"(?im)^\s*(?:[A-D][\.\)]|[1-4][\.\)])\s+",
        question
    )

    return normalize_text(
        parts[0]
    ).rstrip(".? ")


def content_overlap(a, b):

    wa = tokenize(a)
    wb = tokenize(b)

    if not wa:
        return 0

    return len(
        wa.intersection(wb)
    ) / len(wa)


# ============================================================
# DIRECT CLO-BASED REVISION
# ============================================================

def create_direct_outcome_revision(
    question,
    outcome
):

    question = normalize_text(
        question
    )

    (
        level,
        verb,
        content
    ) = get_outcome_action_and_content(
        outcome
    )

    if not content:
        return ""

    qtype = detect_question_type(
        question
    )

    # --------------------------------------------------------
    # MCQ
    # --------------------------------------------------------

    if qtype == "MCQ":

        options = get_mcq_options(
            question
        )

        stem = get_mcq_stem(
            question
        )

        if level == "Analyze":

            new_stem = (
                "Which option best analyzes "
                + stem.rstrip(".? ")
                + "?"
            )

        elif level == "Evaluate":

            new_stem = (
                "Which option best evaluates "
                + stem.rstrip(".? ")
                + "?"
            )

        elif level == "Understand":

            new_stem = (
                "Which statement best explains "
                + content.rstrip(".? ")
                + "?"
            )

        elif level == "Apply":

            new_stem = (
                "Which option correctly applies "
                + content.rstrip(".? ")
                + "?"
            )

        elif level == "Create":

            new_stem = (
                "Which option best proposes a solution "
                + "for "
                + content.rstrip(".? ")
                + "?"
            )

        else:

            new_stem = (
                "Which statement correctly identifies "
                + content.rstrip(".? ")
                + "?"
            )

        if options:

            option_text = []

            labels = [
                "A",
                "B",
                "C",
                "D"
            ]

            for i, option in enumerate(options):

                if i < 4:

                    option_text.append(
                        labels[i]
                        + ". "
                        + option
                    )

            return (
                new_stem
                + "\n"
                + "\n".join(option_text)
            )

        return new_stem

    # --------------------------------------------------------
    # NUMERICAL
    # --------------------------------------------------------

    if qtype == "Numerical":

        if (
            "show the calculation" in question.lower()
            or "show your calculation" in question.lower()
        ):

            return question

        return (
            question.rstrip(".? ")
            + ". Show the calculation steps and state "
            + "the final answer with the appropriate unit."
        )

    # --------------------------------------------------------
    # TRUE / FALSE
    # --------------------------------------------------------

    if qtype == "True/False":

        statement = re.sub(
            r"(?i)\btrue\s*/\s*false\b",
            "",
            question
        )

        statement = re.sub(
            r"(?i)\btrue\s+or\s+false\b",
            "",
            statement
        )

        statement = statement.strip().rstrip(
            ".? "
        )

        return (
            "Determine whether the following statement "
            "is correct: "
            + statement
            + ". (True/False)"
        )

    # --------------------------------------------------------
    # FILL IN THE BLANK
    # --------------------------------------------------------

    if qtype == "Fill in the Blank":

        if "_" in question:
            return question

        return (
            question.rstrip(".? ")
            + ": __________"
        )

    # --------------------------------------------------------
    # UNDERSTAND
    # --------------------------------------------------------

    if level == "Understand":

        return (
            "Explain "
            + content.rstrip(".? ")
            + "."
        )

    # --------------------------------------------------------
    # APPLY
    # --------------------------------------------------------

    if level == "Apply":

        original_without_question = (
            question.rstrip(".? ")
        )

        if content_overlap(
            original_without_question,
            content
        ) > 0.20:

            return (
                "Apply "
                + content.rstrip(".? ")
                + "."
            )

        return (
            "Apply "
            + content.rstrip(".? ")
            + " to "
            + original_without_question
            + "."
        )

    # --------------------------------------------------------
    # ANALYZE
    # --------------------------------------------------------

    if level == "Analyze":

        if " and " in content.lower():

            return (
                "Analyze "
                + content.rstrip(".? ")
                + "."
            )

        return (
            "Analyze "
            + content.rstrip(".? ")
            + "."
        )

    # --------------------------------------------------------
    # EVALUATE
    # --------------------------------------------------------

    if level == "Evaluate":

        return (
            "Evaluate "
            + content.rstrip(".? ")
            + "."
        )

    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------

    if level == "Create":

        return (
            "Develop a solution that addresses "
            + content.rstrip(".? ")
            + "."
        )

    return (
        verb.capitalize()
        + " "
        + content.rstrip(".? ")
        + "."
    )


# ============================================================
# VALIDATION
# ============================================================

def validate_revision(
    original,
    revised
):

    if not revised:
        return False

    if normalize_text(original) == normalize_text(revised):
        return False

    # Never allow meta learning-outcome language.
    forbidden = [
        "clo",
        "plo",
        "learning outcome",
        "course learning outcome",
        "program learning outcome",
        "according to the clo",
        "according to the plo",
        "according to the learning outcome",
        "as stated in the clo",
        "as stated in the plo",
        "using the learning outcome",
        "using the clo",
        "using the plo"
    ]

    low = revised.lower()

    for phrase in forbidden:

        if phrase in low:
            return False

    # Preserve numbers.
    if extract_numbers(original) != extract_numbers(revised):
        return False

    # Preserve MCQ options.
    if detect_question_type(original) == "MCQ":

        old_options = get_mcq_options(
            original
        )

        new_options = get_mcq_options(
            revised
        )

        if old_options != new_options:
            return False

    # Preserve topic.
    if content_overlap(
        original,
        revised
    ) < 0.10:

        return False

    return True


# ============================================================
# GENERAL REVISION
# ============================================================

def create_revision(result):

    question = result["Question"]

    # --------------------------------------------------------
    # CLO HAS PRIORITY
    # --------------------------------------------------------

    if (
        result["CLO Match"] < ATTAINMENT_THRESHOLD
        and result["Best CLO"]
    ):

        revision = create_direct_outcome_revision(
            question,
            result["Best CLO"]
        )

        if validate_revision(
            question,
            revision
        ):

            return {
                "revision": revision,
                "focus": "CLO alignment",
                "reason": (
                    "The question does not sufficiently assess "
                    "the required course content or skill."
                )
            }

    # --------------------------------------------------------
    # PLO
    # --------------------------------------------------------

    if (
        result["PLO Match"] < ATTAINMENT_THRESHOLD
        and result["Best PLO"]
    ):

        revision = create_direct_outcome_revision(
            question,
            result["Best PLO"]
        )

        if validate_revision(
            question,
            revision
        ):

            return {
                "revision": revision,
                "focus": "PLO alignment",
                "reason": (
                    "The question does not sufficiently assess "
                    "the required program-level content or skill."
                )
            }

    # --------------------------------------------------------
    # BLOOM
    # --------------------------------------------------------

    if result["Bloom Score"] < ATTAINMENT_THRESHOLD:

        target = result["Target Bloom"]

        base = question.rstrip(".? ")

        if target == "Analyze":

            revision = (
                "Analyze "
                + base
                + " by identifying the key factors involved."
            )

        elif target == "Evaluate":

            revision = (
                "Evaluate "
                + base
                + " and support your judgment with relevant reasons."
            )

        elif target == "Apply":

            revision = (
                "Apply the relevant concept to "
                + base
                + " and show how it is used."
            )

        elif target == "Create":

            revision = (
                "Develop a solution for "
                + base
                + "."
            )

        else:

            revision = (
                "Explain "
                + base
                + " clearly."
            )

        if validate_revision(
            question,
            revision
        ):

            return {
                "revision": revision,
                "focus": "Bloom's Taxonomy",
                "reason": (
                    "The cognitive demand of the question "
                    "is below the required level."
                )
            }

    # --------------------------------------------------------
    # CLARITY
    # --------------------------------------------------------

    if result["Clarity"] < ATTAINMENT_THRESHOLD:

        revision = question

        revision = re.sub(
            r"(?i)^discuss this$",
            "Explain the main concept.",
            revision
        )

        revision = re.sub(
            r"(?i)^explain this$",
            "Explain the main concept.",
            revision
        )

        if validate_revision(
            question,
            revision
        ):

            return {
                "revision": revision,
                "focus": "Clarity",
                "reason": (
                    "The question contains vague wording "
                    "that should be made more precise."
                )
            }

    # --------------------------------------------------------
    # MEASURABILITY
    # --------------------------------------------------------

    if result["Measurability"] < ATTAINMENT_THRESHOLD:

        revision = (
            question.rstrip(".? ")
            + ". Support your answer with relevant evidence."
        )

        if validate_revision(
            question,
            revision
        ):

            return {
                "revision": revision,
                "focus": "Measurability",
                "reason": (
                    "The expected response is not sufficiently "
                    "observable or measurable."
                )
            }

    # --------------------------------------------------------
    # FINAL DIRECT OUTCOME FALLBACK
    # --------------------------------------------------------

    if result["Best CLO"]:

        revision = create_direct_outcome_revision(
            question,
            result["Best CLO"]
        )

        if revision:

            return {
                "revision": revision,
                "focus": "CLO alignment",
                "reason": (
                    "The question can be made more directly "
                    "aligned with the assessed content."
                )
            }

    return {
        "revision": (
            question.rstrip(".? ")
            + "?"
        ),
        "focus": "Question wording",
        "reason": (
            "The question needs a clearer and more direct formulation."
        )
    }


# ============================================================
# HEADER
# ============================================================

st.title("🎓 OBE Quiz Checker")

st.write(
    "Check assessment questions for CLO, PLO, Bloom's Taxonomy, "
    "relevance, clarity, and measurability — and automatically "
    "improve weak questions with direct, practical revisions."
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("🎓 OBE Quiz Checker")

    st.caption(
        "Subject-independent assessment alignment tool."
    )

    st.divider()

    st.write(
        "Supports:"
    )

    st.write(
        "• PDF\n"
        "• DOCX\n"
        "• PPTX\n"
        "• XLSX / XLS\n"
        "• CSV\n"
        "• TXT / MD\n"
        "• Images"
    )


# ============================================================
# 1. ASSESSMENT INFORMATION
# ============================================================

st.header("1. Assessment Information")

col1, col2, col3 = st.columns(3)

with col1:

    course_name = st.text_input(
        "Course",
        placeholder="e.g. Chemistry, English I, Physics"
    )

with col2:

    assessment_name = st.text_input(
        "Assessment",
        placeholder="e.g. Quiz 1"
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

    clo_input = st.text_area(
        "Course Learning Outcomes (CLOs)",
        height=180,
        placeholder=(
            "Enter one CLO per line.\n\n"
            "Example:\n"
            "Explain the process of photosynthesis and its importance to plant growth."
        )
    )

with col2:

    plo_input = st.text_area(
        "Program Learning Outcomes (PLOs)",
        height=180,
        placeholder=(
            "Enter one PLO per line.\n\n"
            "Example:\n"
            "Apply scientific knowledge to solve problems."
        )
    )


clos = parse_outcomes(
    clo_input
)

plos = parse_outcomes(
    plo_input
)


# ============================================================
# 3. UPLOAD
# ============================================================

st.header("3. Upload Complete Assessment")

uploaded_file = st.file_uploader(
    "Upload your complete assessment file",
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
    ],
    key="assessment_uploader"
)


if uploaded_file is not None:

    if (
        st.session_state.file_name
        != uploaded_file.name
    ):

        st.session_state.file_name = (
            uploaded_file.name
        )

        st.session_state.uploaded_text = ""
        st.session_state.questions = []
        st.session_state.analysis = []
        st.session_state.revisions = {}
        st.session_state.accepted_revisions = {}
        st.session_state.analyzed = False

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
                "No readable text was found in the uploaded file."
            )

            st.info(
                "If this is a scanned PDF, make sure OCR/PyMuPDF "
                "are included in requirements.txt."
            )

        else:

            questions = extract_questions(
                text
            )

            st.session_state.uploaded_text = text
            st.session_state.questions = questions
            st.session_state.analysis = []
            st.session_state.revisions = {}
            st.session_state.accepted_revisions = {}
            st.session_state.analyzed = False

            if questions:

                st.success(
                    f"Successfully detected {len(questions)} question(s)."
                )

            else:

                st.warning(
                    "The file was read successfully, but no questions "
                    "could be detected automatically."
                )

                st.info(
                    "Make sure questions are numbered, separated clearly, "
                    "or written as complete question sentences."
                )

            with st.expander(
                "Preview Extracted Assessment Text"
            ):

                st.text(
                    text[:12000]
                )


# ============================================================
# DETECTED QUESTIONS
# ============================================================

if st.session_state.questions:

    with st.expander(
        f"Detected Questions ({len(st.session_state.questions)})",
        expanded=False
    ):

        for index, question in enumerate(
            st.session_state.questions,
            start=1
        ):

            st.write(
                f"**Q{index}.** {question}"
            )


# ============================================================
# 4. ANALYZE
# ============================================================

st.header("4. Analyze Assessment")

if st.session_state.questions:

    if st.button(
        "🔍 Analyze Assessment",
        type="primary",
        use_container_width=True
    ):

        if not clos:

            st.error(
                "Please enter at least one CLO before analysis."
            )

        else:

            analysis_results = []

            for index, question in enumerate(
                st.session_state.questions,
                start=1
            ):

                result = evaluate_question(
                    question,
                    clos,
                    plos
                )

                result["Question Number"] = index

                analysis_results.append(
                    result
                )

            st.session_state.analysis = (
                analysis_results
            )

            st.session_state.revisions = {}
            st.session_state.accepted_revisions = {}
            st.session_state.analyzed = True
            st.session_state.overall_balloons = False

            st.success(
                "Assessment analysis completed successfully."
            )

else:

    st.info(
        "Upload and read your assessment first."
    )


# ============================================================
# RESULTS
# ============================================================

if (
    st.session_state.analyzed
    and st.session_state.analysis
):

    results = st.session_state.analysis

    overall_score = round(
        sum(
            r["Overall Alignment"]
            for r in results
        )
        / len(results),
        1
    )

    # ========================================================
    # 5. OVERALL ALIGNMENT
    # ========================================================

    st.header("5. Overall Alignment")

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Overall Alignment",
            f"{overall_score:.1f}%"
        )

    with col2:

        st.metric(
            "Total Questions",
            len(results)
        )

    with col3:

        attained_count = sum(
            r["Overall Alignment"]
            >= ATTAINMENT_THRESHOLD
            for r in results
        )

        st.metric(
            "Attained Questions",
            f"{attained_count}/{len(results)}"
        )

    st.progress(
        min(1.0, overall_score / 100)
    )

    if overall_score >= 80:

        st.success(
            "🎉 Overall assessment alignment is attained."
        )

        if not st.session_state.overall_balloons:

            st.balloons()

            st.session_state.overall_balloons = True

    elif overall_score >= 75:

        st.success(
            "🏆 Overall assessment has reached the 75% attainment threshold."
        )

    else:

        st.warning(
            "Some questions require revision to strengthen alignment."
        )


    # ========================================================
    # 6. SCORE ANALYSIS
    # ========================================================

    st.header("6. Assessment Score Analysis")

    metric_names = [
        "CLO Match",
        "PLO Match",
        "Bloom Score",
        "Relevance",
        "Clarity",
        "Measurability"
    ]

    averages = {}

    for metric in metric_names:

        averages[metric] = round(
            sum(
                r[metric]
                for r in results
            )
            / len(results),
            1
        )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "Average CLO Match",
            f"{averages['CLO Match']}%"
        )

        st.metric(
            "Average PLO Match",
            f"{averages['PLO Match']}%"
        )

    with c2:

        st.metric(
            "Average Bloom",
            f"{averages['Bloom Score']}%"
        )

        st.metric(
            "Average Relevance",
            f"{averages['Relevance']}%"
        )

    with c3:

        st.metric(
            "Average Clarity",
            f"{averages['Clarity']}%"
        )

        st.metric(
            "Average Measurability",
            f"{averages['Measurability']}%"
        )


    # ========================================================
    # 7. QUESTIONS REQUIRING REVISION
    # ========================================================

    st.header(
        "7. 🔧 Questions Requiring Revision"
    )

    weak_questions = []

    for result in results:

        if (
            result["Overall Alignment"]
            < ATTAINMENT_THRESHOLD
            or result["CLO Match"]
            < ATTAINMENT_THRESHOLD
            or result["PLO Match"]
            < ATTAINMENT_THRESHOLD
        ):

            weak_questions.append(
                result
            )

    if not weak_questions:

        st.success(
            "🎉 All questions have attained the 75% threshold."
        )

    else:

        st.info(
            f"{len(weak_questions)} question(s) require revision."
        )

    # --------------------------------------------------------
    # Revision list at top
    # --------------------------------------------------------

    for result in weak_questions:

        question_number = result[
            "Question Number"
        ]

        if (
            question_number
            not in st.session_state.revisions
        ):

            st.session_state.revisions[
                question_number
            ] = create_revision(
                result
            )

        revision_data = (
            st.session_state.revisions[
                question_number
            ]
        )

        st.subheader(
            f"Question {question_number} "
            f"— {result['Overall Alignment']:.1f}%"
        )

        left, right = st.columns(2)

        with left:

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
                revision_data["reason"]
            )

            st.markdown(
                "**Revision Focus**"
            )

            st.write(
                revision_data["focus"]
            )

        with right:

            st.markdown(
                "**Practical Revision**"
            )

            st.success(
                revision_data["revision"]
            )

            st.caption(
                "The learning outcomes guide the revision internally; "
                "they are not inserted into the student question."
            )

            if st.button(
                "✅ Use This Revision",
                key=f"use_revision_{question_number}",
                use_container_width=True
            ):

                original_score = (
                    result["Overall Alignment"]
                )

                revised_question = (
                    revision_data["revision"]
                )

                revised_result = evaluate_question(
                    revised_question,
                    clos,
                    plos
                )

                revised_result[
                    "Question Number"
                ] = question_number

                st.session_state.questions[
                    question_number - 1
                ] = revised_question

                st.session_state.analysis[
                    question_number - 1
                ] = revised_result

                st.session_state.accepted_revisions[
                    question_number
                ] = {
                    "original": result["Question"],
                    "revised": revised_question,
                    "before": original_score,
                    "after": revised_result[
                        "Overall Alignment"
                    ]
                }

                del st.session_state.revisions[
                    question_number
                ]

                if (
                    revised_result[
                        "Overall Alignment"
                    ]
                    >= ATTAINMENT_THRESHOLD
                ):

                    st.balloons()

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

            before = data["before"]
            after = data["after"]

            if after >= ATTAINMENT_THRESHOLD:

                st.success(
                    f"Q{number}: "
                    f"{before:.1f}% → {after:.1f}% "
                    f"🏆 Attained"
                )

            else:

                st.warning(
                    f"Q{number}: "
                    f"{before:.1f}% → {after:.1f}%"
                )

            with st.expander(
                f"View revised Q{number}"
            ):

                st.write(
                    "**Original Question:**"
                )

                st.write(
                    data["original"]
                )

                st.write(
                    "**Revised Question:**"
                )

                st.success(
                    data["revised"]
                )


    # ========================================================
    # 8. ATTAINED QUESTIONS
    # ========================================================

    st.header(
        "8. 🏆 Attained Questions"
    )

    attained_questions = [
        r
        for r in st.session_state.analysis
        if r["Overall Alignment"]
        >= ATTAINMENT_THRESHOLD
    ]

    if attained_questions:

        for result in attained_questions:

            st.write(
                f"🏆 **Q{result['Question Number']}** "
                f"— {result['Overall Alignment']:.1f}%"
            )

    else:

        st.info(
            "No questions have reached 75% yet."
        )


    # ========================================================
    # 9. ONLY GRAPH
    # ========================================================

    st.header(
        "9. Alignment Overview"
    )

    chart_data = pd.DataFrame(
        [
            {
                "Question":
                    f"Q{r['Question Number']}",
                "CLO":
                    r["CLO Match"],
                "PLO":
                    r["PLO Match"],
                "Bloom":
                    r["Bloom Score"],
                "Overall":
                    r["Overall Alignment"]
            }
            for r in st.session_state.analysis
        ]
    )

    if not chart_data.empty:

        chart_data = chart_data.set_index(
            "Question"
        )

        st.line_chart(
            chart_data
        )


    # ========================================================
    # 10. QUESTION OVERVIEW
    # ========================================================

    st.header(
        "10. Question Overview"
    )

    overview_data = []

    for result in st.session_state.analysis:

        overview_data.append(
            {
                "Question":
                    f"Q{result['Question Number']}",
                "Type":
                    result["Question Type"],
                "CLO":
                    f"{result['CLO Match']}%",
                "PLO":
                    f"{result['PLO Match']}%",
                "Bloom":
                    f"{result['Bloom Score']}%",
                "Clarity":
                    f"{result['Clarity']}%",
                "Measurability":
                    f"{result['Measurability']}%",
                "Overall":
                    f"{result['Overall Alignment']}%",
                "Status":
                    get_status(
                        result["Overall Alignment"]
                    )
            }
        )

    overview_df = pd.DataFrame(
        overview_data
    )

    st.dataframe(
        overview_df,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # 11. DETAILED QUESTION ANALYSIS
    # ========================================================

    st.header(
        "11. Detailed Question Analysis"
    )

    question_labels = [
        (
            f"Q{r['Question Number']} "
            f"— {r['Overall Alignment']:.1f}%"
        )
        for r in st.session_state.analysis
    ]

    selected_label = st.selectbox(
        "Select a question",
        question_labels
    )

    selected_index = (
        question_labels.index(
            selected_label
        )
    )

    selected_result = (
        st.session_state.analysis[
            selected_index
        ]
    )

    st.info(
        selected_result["Question"]
    )

    d1, d2, d3 = st.columns(3)

    with d1:

        st.metric(
            "CLO Match",
            f"{selected_result['CLO Match']}%"
        )

        st.metric(
            "PLO Match",
            f"{selected_result['PLO Match']}%"
        )

    with d2:

        st.metric(
            "Bloom Score",
            f"{selected_result['Bloom Score']}%"
        )

        st.metric(
            "Clarity",
            f"{selected_result['Clarity']}%"
        )

    with d3:

        st.metric(
            "Relevance",
            f"{selected_result['Relevance']}%"
        )

        st.metric(
            "Measurability",
            f"{selected_result['Measurability']}%"
        )

    st.progress(
        min(
            1.0,
            selected_result["Overall Alignment"] / 100
        )
    )

    st.write(
        f"**Overall Alignment:** "
        f"{selected_result['Overall Alignment']:.1f}% "
        f"{get_status(selected_result['Overall Alignment'])}"
    )

    st.write(
        f"**Question Type:** "
        f"{selected_result['Question Type']}"
    )

    st.write(
        f"**Bloom Level:** "
        f"{selected_result['Bloom Level']}"
    )

    st.write(
        f"**Target Bloom Level:** "
        f"{selected_result['Target Bloom']}"
    )

    if selected_result["Best CLO"]:

        st.write(
            "**Mapped CLO:** "
            + selected_result["Best CLO"]
        )

    if selected_result["Best PLO"]:

        st.write(
            "**Mapped PLO:** "
            + selected_result["Best PLO"]
        )


    # ========================================================
    # 12. EXPORT
    # ========================================================

    st.header(
        "12. Export"
    )

    export_rows = []

    for result in st.session_state.analysis:

        export_rows.append(
            {
                "Question Number":
                    result["Question Number"],
                "Question":
                    result["Question"],
                "Question Type":
                    result["Question Type"],
                "Bloom Level":
                    result["Bloom Level"],
                "Target Bloom":
                    result["Target Bloom"],
                "CLO Match":
                    result["CLO Match"],
                "PLO Match":
                    result["PLO Match"],
                "Bloom Score":
                    result["Bloom Score"],
                "Relevance":
                    result["Relevance"],
                "Clarity":
                    result["Clarity"],
                "Measurability":
                    result["Measurability"],
                "Overall Alignment":
                    result["Overall Alignment"],
                "Status":
                    get_status(
                        result["Overall Alignment"]
                    ),
                "Mapped CLO":
                    result["Best CLO"],
                "Mapped PLO":
                    result["Best PLO"]
            }
        )

    export_df = pd.DataFrame(
        export_rows
    )

    csv_data = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Analysis Report",
        data=csv_data,
        file_name="obe_quiz_checker_report.csv",
        mime="text/csv",
        use_container_width=True
    )
