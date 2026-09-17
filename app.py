import streamlit as st
import pandas as pd
import re
import io
import random
import time
import hashlib

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
    layout="wide",
    initial_sidebar_state="expanded"
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

BLOOM_VERBS = {
    "Remember": [
        "define", "identify", "list", "name", "state",
        "recall", "recognize", "select", "mention"
    ],
    "Understand": [
        "describe", "explain", "summarize", "interpret",
        "classify", "discuss", "illustrate", "outline"
    ],
    "Apply": [
        "calculate", "apply", "demonstrate", "use",
        "solve", "implement", "execute", "show"
    ],
    "Analyze": [
        "analyze", "analyse", "compare", "differentiate",
        "examine", "contrast", "investigate", "categorize"
    ],
    "Evaluate": [
        "evaluate", "assess", "justify", "critique",
        "defend", "judge", "appraise", "argue"
    ],
    "Create": [
        "create", "design", "develop", "construct",
        "formulate", "propose", "produce", "develop"
    ]
}

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then",
    "than", "that", "this", "these", "those", "with",
    "from", "into", "onto", "for", "of", "to", "in",
    "on", "at", "by", "as", "is", "are", "was", "were",
    "be", "been", "being", "do", "does", "did", "can",
    "could", "should", "would", "will", "may", "might",
    "what", "which", "who", "whom", "when", "where",
    "why", "how", "your", "their", "his", "her", "its",
    "our", "you", "we", "they", "it", "students",
    "student"
}


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "questions": [],
    "analysis": [],
    "uploaded_text": "",
    "analyzed": False,
    "selected_question": 0,
    "wheel_score": None,
    "wheel_spun": False,
    "wheel_running": False,
    "revision_message": "",
    "revision_old_score": None,
    "revision_new_score": None
}

for key, value in defaults.items():
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
    text = text.replace("\u2018", "'")
    text = text.replace("\u2019", "'")
    text = text.replace("\u201c", '"')
    text = text.replace("\u201d", '"')
    text = text.replace("\u2013", "-")
    text = text.replace("\u2014", "-")
    text = text.replace("\u00a0", " ")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


def normalize_text(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def content_words(text):
    words = normalize_text(text).split()

    result = []

    for word in words:
        if word in STOP_WORDS:
            continue

        if len(word) < 3:
            continue

        result.append(word)

    return result


def stem_like(word):
    word = word.lower().strip()

    endings = [
        "ization",
        "ations",
        "ation",
        "ments",
        "ment",
        "ingly",
        "edly",
        "ing",
        "ers",
        "ies",
        "es",
        "ed",
        "s"
    ]

    for ending in endings:
        if word.endswith(ending) and len(word) > len(ending) + 3:
            return word[:-len(ending)]

    return word


def normalized_content_words(text):
    return [stem_like(w) for w in content_words(text)]


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text):
    if not text:
        return []

    lines = text.splitlines()
    outcomes = []

    for line in lines:
        line = clean_text(line)

        if not line:
            continue

        line = re.sub(
            r"^(CLO|PLO)\s*[-:]?\s*\d+\s*[:.)-]?\s*",
            "",
            line,
            flags=re.IGNORECASE
        )

        line = re.sub(
            r"^\d+\s*[\).:-]\s*",
            "",
            line
        )

        line = re.sub(
            r"^[-•*]\s*",
            "",
            line
        )

        if len(line.split()) >= 3:
            outcomes.append(line)

    return outcomes


# ============================================================
# BLOOM DETECTION
# ============================================================

def find_bloom_verb(question):
    q = normalize_text(question)

    for level, verbs in BLOOM_VERBS.items():
        for verb in verbs:
            pattern = r"\b" + re.escape(verb) + r"\b"

            if re.search(pattern, q):
                return level, verb

    return "Unknown", ""


def bloom_distance(current, target):
    if current == "Unknown" or target == "Unknown":
        return 0

    try:
        a = BLOOM_LEVELS.index(current)
        b = BLOOM_LEVELS.index(target)
        return abs(a - b)
    except Exception:
        return 0


def bloom_score(question, target_bloom=""):
    current, verb = find_bloom_verb(question)

    if not target_bloom:
        if current == "Unknown":
            return 82.0
        return 92.0

    if current == "Unknown":
        return 78.0

    distance = bloom_distance(current, target_bloom)

    if distance == 0:
        return 100.0

    if distance == 1:
        return 91.0

    if distance == 2:
        return 83.0

    if distance == 3:
        return 76.0

    return 70.0


# ============================================================
# QUESTION TYPE DETECTION
# ============================================================

def detect_question_type(question):
    q = question.lower()

    if re.search(r"\btrue\s*(or|/)?\s*false\b", q):
        return "True / False"

    if re.search(r"\b(a\)|b\)|c\)|d\))", q):
        return "MCQ"

    if re.search(r"\bchoose the correct\b", q):
        return "MCQ"

    if re.search(r"\bselect the correct\b", q):
        return "MCQ"

    if "match the following" in q:
        return "Matching"

    if "fill in the blank" in q or "fill in the blanks" in q:
        return "Fill in the Blank"

    if any(x in q for x in [
        "calculate",
        "compute",
        "find the value",
        "solve for",
        "determine the value"
    ]):
        return "Numerical / Calculation"

    if any(x in q for x in [
        "case study",
        "read the case",
        "scenario",
        "case"
    ]):
        return "Case Study"

    if any(x in q for x in [
        "design",
        "develop",
        "construct",
        "implement",
        "perform",
        "demonstrate"
    ]):
        return "Practical / Application"

    if any(x in q for x in [
        "essay",
        "discuss in detail",
        "write an essay",
        "critically discuss"
    ]):
        return "Essay / Long Answer"

    words = len(q.split())

    if words > 35:
        return "Essay / Long Answer"

    return "Short Answer"


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def extract_questions(text):
    """
    Extract questions from uploaded assessment text.
    This function is intentionally defined before it is called.
    """

    text = clean_text(text)

    if not text:
        return []

    lines = [
        clean_text(x)
        for x in text.splitlines()
        if clean_text(x)
    ]

    questions = []

    # --------------------------------------------------------
    # Numbered questions
    # --------------------------------------------------------

    current = ""

    for line in lines:

        is_question_start = bool(
            re.match(
                r"^(?:Q(?:uestion)?\s*)?\d+\s*[\).:-]\s+",
                line,
                flags=re.IGNORECASE
            )
        )

        if is_question_start:

            if current:
                questions.append(current.strip())

            current = re.sub(
                r"^(?:Q(?:uestion)?\s*)?\d+\s*[\).:-]\s*",
                "",
                line,
                flags=re.IGNORECASE
            ).strip()

        else:

            if current:
                current += " " + line

    if current:
        questions.append(current.strip())

    # --------------------------------------------------------
    # Fallback: paragraphs
    # --------------------------------------------------------

    if len(questions) < 2:

        paragraphs = re.split(r"\n\s*\n", text)

        candidate_paragraphs = []

        for p in paragraphs:
            p = clean_text(p)

            if len(p.split()) >= 5:
                candidate_paragraphs.append(p)

        if len(candidate_paragraphs) >= 2:
            questions = candidate_paragraphs

    # --------------------------------------------------------
    # Fallback: lines that look like questions
    # --------------------------------------------------------

    if not questions:

        for line in lines:

            if (
                "?" in line
                or re.match(
                    r"^(explain|describe|define|identify|calculate|"
                    r"compare|analyze|analyse|evaluate|discuss|"
                    r"state|list|design|develop|what|why|how|which)\b",
                    line,
                    flags=re.IGNORECASE
                )
            ):

                if len(line.split()) >= 4:
                    questions.append(line)

    # --------------------------------------------------------
    # Clean and deduplicate
    # --------------------------------------------------------

    final_questions = []
    seen = set()

    for q in questions:

        q = clean_text(q)

        if len(q.split()) < 3:
            continue

        key = normalize_text(q)

        if key in seen:
            continue

        seen.add(key)
        final_questions.append(q)

    return final_questions


# ============================================================
# FILE READERS
# ============================================================

def read_pdf(uploaded_file):

    if fitz is None:
        raise RuntimeError(
            "PyMuPDF is not installed. Add PyMuPDF to requirements.txt."
        )

    data = uploaded_file.read()
    doc = fitz.open(stream=data, filetype="pdf")

    pages = []

    for page in doc:
        text = page.get_text("text")

        if text and text.strip():
            pages.append(text)

        elif pytesseract
