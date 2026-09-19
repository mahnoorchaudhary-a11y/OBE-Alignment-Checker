import io
import re
import math
import textwrap
from collections import Counter

import streamlit as st
import pandas as pd


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Checker",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
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
    "understand": 2,
    "apply": 3,
    "analyze": 4,
    "analyse": 4,
    "evaluate": 5,
    "create": 6,
}

BLOOM_NAMES = {
    1: "Remember",
    2: "Understand",
    3: "Apply",
    4: "Analyze",
    5: "Evaluate",
    6: "Create",
}

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "than",
    "of", "to", "in", "on", "for", "from", "with", "by", "at",
    "as", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "it", "its", "their",
    "they", "them", "he", "she", "we", "you", "your", "our",
    "students", "student", "will", "can", "may", "should",
    "must", "able", "ability", "knowledge", "understanding",
    "demonstrate", "demonstrates", "demonstrating",
    "learn", "learning", "course", "program", "outcome",
    "learning", "use", "using", "used", "given", "appropriate",
    "relevant", "different", "various", "following",
}

ACTION_FAMILIES = {
    "remember": {
        "define", "identify", "list", "name", "state", "recall",
        "recognize", "recognise", "label", "select"
    },
    "understand": {
        "explain", "describe", "summarize", "summarise",
        "interpret", "classify", "discuss", "illustrate"
    },
    "apply": {
        "apply", "calculate", "solve", "use", "demonstrate",
        "execute", "implement", "compute", "perform"
    },
    "analyze": {
        "analyze", "analyse", "compare", "contrast", "differentiate",
        "examine", "investigate", "categorize", "categorise",
        "distinguish", "break", "deconstruct"
    },
    "evaluate": {
        "evaluate", "assess", "judge", "justify", "critique",
        "defend", "recommend", "select", "appraise"
    },
    "create": {
        "create", "design", "develop", "construct", "formulate",
        "produce", "propose", "plan", "build", "generate"
    },
}

VERB_TO_LEVEL = {}
for level_name, verbs in ACTION_FAMILIES.items():
    for verb in verbs:
        VERB_TO_LEVEL[verb] = BLOOM_LEVELS[level_name]


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "assessment_text": "",
    "assessment_source": "",
    "questions": [],
    "analysis": [],
    "analyzed": False,
    "selected_question": None,
    "accepted_revisions": {},
    "assessment_title": "",
    "subject": "",
    "course": "",
    "clo": "",
    "plo": "",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# BASIC TEXT UTILITIES
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\x00", " ")
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize(text):
    text = clean_text(text).lower()
    text = text.replace("analyse", "analyze")
    text = text.replace("categorise", "categorize")
    text = text.replace("summarise", "summarize")
    return text


def tokens(text):
    text = normalize(text)
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]*", text)

    result = []
    for word in words:
        word = word.lower().strip("'")
        if len(word) <= 2:
            continue
        if word in STOPWORDS:
            continue
        result.append(word)

    return result


def unique_preserve(items):
    result = []
    seen = set()

    for item in items:
        value = item.strip()
        key = value.lower()

        if value and key not in seen:
            seen.add(key)
            result.append(value)

    return result


def sentence_case(text):
    text = clean_text(text)
    if not text:
        return ""

    text = text[0].upper() + text[1:]

    if text.endswith("."):
        return text

    if text.endswith("?") or text.endswith(":"):
        return text

    return text


def ensure_question_mark(text):
    text = clean_text(text)

    if not text:
        return ""

    if text.endswith("?"):
        return text

    if text.endswith("."):
        text = text[:-1]

    return text + "?"


# ============================================================
# BLOOM DETECTION
# ============================================================

def extract_action_verbs(text):
    normalized = normalize(text)
    found = []

    for verb in VERB_TO_LEVEL:
        pattern = r"\b" + re.escape(verb) + r"\b"
        if re.search(pattern, normalized):
            found.append(verb)

    return found


def detect_bloom_level(question):
    normalized = normalize(question)

    # Strong task patterns get priority.
    if any(
        phrase in normalized
        for phrase in [
            "design a",
            "design an",
            "develop a",
            "develop an",
            "create a",
            "create an",
            "construct a",
            "formulate a",
            "propose a",
            "build a",
        ]
    ):
        return 6

    if any(
        phrase in normalized
        for phrase in [
            "justify",
            "defend your",
            "recommend",
            "evaluate",
            "critique",
            "assess which",
            "which option is better",
        ]
    ):
        return 5

    if any(
        phrase in normalized
        for phrase in [
            "analyze",
            "analyse",
            "compare",
            "contrast",
            "differentiate",
            "examine the relationship",
            "investigate",
            "distinguish",
            "causes and effects",
        ]
    ):
        return 4

    if any(
        phrase in normalized
        for phrase in [
            "calculate",
            "solve",
            "compute",
            "determine",
            "apply",
            "use the formula",
            "show your working",
            "demonstrate how",
        ]
    ):
        return 3

    if any(
        phrase in normalized
        for phrase in [
            "explain",
            "describe",
            "summarize",
            "summarise",
            "interpret",
            "why is",
            "how does",
            "how do",
        ]
    ):
        return 2

    if any(
        phrase in normalized
        for phrase in [
            "what is",
            "what are",
            "who is",
            "who was",
            "define",
            "list",
            "name",
            "identify",
            "state",
        ]
    ):
        return 1

    verbs = extract_action_verbs(question)

    if verbs:
        return max(VERB_TO_LEVEL[v] for v in verbs)

    return 1


def target_bloom(clo, plo):
    clo_levels = [
        VERB_TO_LEVEL[v]
        for v in extract_action_verbs(clo)
        if v in VERB_TO_LEVEL
    ]

    plo_levels = [
        VERB_TO_LEVEL[v]
        for v in extract_action_verbs(plo)
        if v in VERB_TO_LEVEL
    ]

    # CLO is the primary course-level target.
    if clo_levels:
        clo_target = max(clo_levels)

        if plo_levels:
            plo_target = max(plo_levels)

            # When PLO asks for substantially higher cognition,
            # use the higher target.
            return max(clo_target, plo_target)

        return clo_target

    if plo_levels:
        return max(plo_levels)

    return None


# ============================================================
# CONCEPT EXTRACTION
# ============================================================

def remove_action_phrases(text):
    result = normalize(text)

    all_verbs = sorted(
        VERB_TO_LEVEL.keys(),
        key=len,
        reverse=True
    )

    for verb in all_verbs:
        result = re.sub(
            r"\b" + re.escape(verb) + r"\b",
            " ",
            result
        )

    result = re.sub(
        r"\b(students?|learners?|ability|knowledge|understanding)\b",
        " ",
        result
    )

    return clean_text(result)


def meaningful_phrases(text):
    text = remove_action_phrases(text)

    clauses = re.split(
        r"\b(?:and|or|while|through|using|by|for|to)\b|[,;:.]",
        text,
        flags=re.IGNORECASE
    )

    phrases = []

    for clause in clauses:
        clause = clean_text(clause)

        if not clause:
            continue

        words = tokens(clause)

        if not words:
            continue

        if len(words) >= 2:
            phrases.append(" ".join(words[:7]))
        else:
            phrases.append(words[0])

    return unique_preserve(phrases)


def extract_key_concepts(clo, plo, question=""):
    sources = []

    if clo:
        sources.extend(meaningful_phrases(clo))

    if plo:
        sources.extend(meaningful_phrases(plo))

    if question:
        sources.extend(meaningful_phrases(question))

    sources = unique_preserve(sources)

    # Prefer longer concepts because they carry more meaning.
    sources.sort(
        key=lambda x: (len(x.split()), len(x)),
        reverse=True
    )

    return sources[:8]


def concept_words(text):
    words = tokens(text)

    # Light stemming to handle common variations.
    normalized_words = []

    for word in words:
        value = word

        for suffix in [
            "ing", "ed", "es", "s"
        ]:
            if value.endswith(suffix) and len(value) > len(suffix) + 3:
                value = value[:-len(suffix)]
                break

        normalized_words.append(value)

    return set(normalized_words)


def concept_overlap(question, outcome):
    q_words = concept_words(question)
    o_words = concept_words(remove_action_phrases(outcome))

    if not o_words:
        return 0

    return round(
        100 * len(q_words.intersection(o_words)) / len(o_words),
        1
    )


# ============================================================
# SUBJECT / COURSE RELEVANCE
# ============================================================

def subject_relevance(question, subject, clo, plo):
    q_words = concept_words(question)

    reference = " ".join(
        [
            subject or "",
            clo or "",
            plo or "",
        ]
    )

    ref_words = concept_words(reference)

    if not ref_words:
        return 75, "The question was checked for general assessment relevance."

    overlap = len(q_words.intersection(ref_words)) / max(1, len(ref_words))

    if overlap >= 0.35:
        score = 95
    elif overlap >= 0.22:
        score = 88
    elif overlap >= 0.12:
        score = 78
    elif overlap >= 0.05:
        score = 65
    else:
        score = 45

    feedback = (
        "The question is clearly connected to the supplied course and "
        "learning-outcome content."
        if score >= 85
        else
        "The question has some connection to the supplied content, "
        "but its subject relevance could be made more explicit."
        if score >= 70
        else
        "The question has limited evidence of connection to the supplied "
        "course content."
    )

    return score, feedback


# ============================================================
# CLO EVALUATION
# ============================================================

def score_clo(question, clo):
    if not clo:
        return None, "No CLO was provided."

    overlap = concept_overlap(question, clo)

    clo_verbs = extract_action_verbs(clo)
    question_level = detect_bloom_level(question)
    clo_target = max(
        [VERB_TO_LEVEL[v] for v in clo_verbs],
        default=None
    )

    score = 0

    # Specific content alignment.
    if overlap >= 65:
        score += 55
    elif overlap >= 45:
        score += 45
    elif overlap >= 30:
        score += 35
    elif overlap >= 15:
        score += 22
    elif overlap > 0:
        score += 12
    else:
        score += 3

    # Cognitive/action alignment.
    if clo_target is not None:
        difference = abs(question_level - clo_target)

        if difference == 0:
            score += 35
        elif difference == 1:
            score += 25
        elif difference == 2:
            score += 12
        else:
            score += 5
    else:
        score += 25

    # Task completeness.
    q_normal = normalize(question)

    if question_level >= 4:
        if any(
            phrase in q_normal
            for phrase in [
                "because",
                "evidence",
                "effect",
                "impact",
                "compare",
                "justify",
                "recommend",
                "design",
                "develop",
                "calculate",
                "solve",
            ]
        ):
            score += 10
        else:
            score += 3
    else:
        score += 8

    score = min(100, round(score))

    if score >= 85:
        feedback = (
            "The question directly measures the specific knowledge or "
            "skill represented by the CLO and uses an appropriate task."
        )
    elif score >= 70:
        feedback = (
            "The question addresses important CLO content, but some of "
            "the required content or cognitive action is missing."
        )
    elif score >= 50:
        feedback = (
            "The question is related to the CLO topic, but it does not "
            "fully assess the required course-level skill."
        )
    else:
        feedback = (
            "The question does not adequately measure the specific "
            "knowledge or skill required by the CLO."
        )

    return score, feedback


# ============================================================
# PLO EVALUATION
# ============================================================

def score_plo(question, plo):
    if not plo:
        return None, "No PLO was provided."

    q_words = concept_words(question)
    plo_words = concept_words(remove_action_phrases(plo))

    overlap = (
        len(q_words.intersection(plo_words))
        / max(1, len(plo_words))
    ) * 100

    question_level = detect_bloom_level(question)

    plo_verbs = extract_action_verbs(plo)
    plo_target = max(
        [VERB_TO_LEVEL[v] for v in plo_verbs],
        default=None
    )

    score = 0

    # Broader capability evidence.
    if overlap >= 45:
        score += 45
    elif overlap >= 30:
        score += 36
    elif overlap >= 18:
        score += 27
    elif overlap >= 8:
        score += 18
    elif overlap > 0:
        score += 10
    else:
        score += 4

    # Evidence of broader capability.
    capability_phrases = [
        "analyze", "analyse", "compare", "evaluate",
        "justify", "recommend", "solve", "design",
        "develop", "interpret", "apply", "decision",
        "evidence", "problem", "case", "situation",
    ]

    capability_count = sum(
        1 for phrase in capability_phrases
        if phrase in normalize(question)
    )

    if capability_count >= 2:
        score += 35
    elif capability_count == 1:
        score += 22
    else:
        score += 7

    # Cognitive evidence for the broader program capability.
    if plo_target is not None:
        difference = abs(question_level - plo_target)

        if difference == 0:
            score += 20
        elif difference == 1:
            score += 13
        elif difference == 2:
            score += 7
        else:
            score += 3
    else:
        score += 12

    score = min(100, round(score))

    if score >= 85:
        feedback = (
            "The question provides clear evidence of the broader "
            "program-level capability represented by the PLO."
        )
    elif score >= 70:
        feedback = (
            "The question demonstrates some broader capability, but "
            "stronger evidence of the PLO is needed."
        )
    elif score >= 50:
        feedback = (
            "The question has limited evidence of the broader program "
            "capability and mainly focuses on the immediate topic."
        )
    else:
        feedback = (
            "The question mainly tests isolated knowledge and provides "
            "little evidence of the broader PLO capability."
        )

    return score, feedback


# ============================================================
# BLOOM EVALUATION
# ============================================================

def bloom_analysis(question, clo, plo):
    actual_level = detect_bloom_level(question)
    target_level = target_bloom(clo, plo)

    if target_level is None:
        target_level = actual_level

    difference = abs(actual_level - target_level)

    if difference == 0:
        score = 100
    elif difference == 1:
        score = 88
    elif difference == 2:
        score = 72
    elif difference == 3:
        score = 55
    else:
        score = 40

    actual_name = BLOOM_NAMES[actual_level]
    target_name = BLOOM_NAMES[target_level]

    if actual_level == target_level:
        feedback = (
            f"The question operates at {actual_name}, which matches "
            f"the intended {target_name} cognitive level."
        )
    elif actual_level < target_level:
        feedback = (
            f"The question operates at {actual_name}, below the intended "
            f"{target_name} level. Students need a more demanding task."
        )
    else:
        feedback = (
            f"The question operates at {actual_name}, above the intended "
            f"{target_name} level. The cognitive demand may be higher "
            f"than required."
        )

    return score, feedback, actual_name, target_name


# ============================================================
# CLARITY
# ============================================================

def clarity_score(question):
    q = clean_text(question)
    words = q.split()

    score = 100

    if len(words) < 5:
        score -= 20

    if len(words) > 60:
        score -= 12

    if q.count("?") > 1:
        score -= 8

    if "??" in q:
        score -= 10

    if re.search(r"\b(what,|explain,|why,|how,)\b", q.lower()):
        score -= 10

    if re.search(r"\s{2,}", q):
        score -= 3

    return max(40, min(100, score))


def clarity_feedback(score):
    if score >= 90:
        return "The wording is clear, focused, and easy to interpret."
    if score >= 80:
        return "The wording is generally clear with only minor room for improvement."
    if score >= 65:
        return "The question is understandable but could be more precise."
    return "The wording is unclear or overly broad and should be simplified."


# ============================================================
# MEASURABILITY
# ============================================================

def measurability_score(question):
    q = normalize(question)
    score = 65

    measurable_patterns = [
        "calculate",
        "solve",
        "identify",
        "explain",
        "describe",
        "compare",
        "analyze",
        "analyse",
        "evaluate",
        "justify",
        "recommend",
        "design",
        "develop",
        "list",
        "state",
        "determine",
        "show",
        "interpret",
    ]

    count = sum(
        1 for pattern in measurable_patterns
        if re.search(r"\b" + re.escape(pattern) + r"\b", q)
    )

    score += min(25, count * 7)

    if "appropriate" in q or "suitable" in q:
        score += 4

    if "why" in q or "because" in q:
        score += 5

    if "evidence" in q:
        score += 5

    return max(45, min(100, score))


def measurability_feedback(score):
    if score >= 90:
        return "The expected student response is clearly observable and assessable."
    if score >= 80:
        return "The question is measurable and can be assessed with reasonable consistency."
    if score >= 65:
        return "The expected response is partly measurable but could be made more specific."
    return "The question needs a clearer, observable task."


# ============================================================
# OVERALL SCORE
# ============================================================

def calculate_overall(
    clo_score,
    plo_score,
    bloom_score,
    relevance_score,
    clarity,
    measurability,
):
    clo_value = clo_score if clo_score is not None else 0
    plo_value = plo_score if plo_score is not None else 0

    weighted = (
        clo_value * 0.30
        + plo_value * 0.20
        + bloom_score * 0.20
        + relevance_score * 0.10
        + clarity * 0.10
        + measurability * 0.10
    )

    return round(weighted)


def attainment_label(score):
    if score >= 85:
        return "🟢 Strong Alignment"
    if score >= ATTAINMENT:
        return "🟢 Alignment Attained"
    if score >= 60:
        return "🟡 Needs Improvement"
    if score >= 40:
        return "🟠 Needs Revision"
    return "🔴 Weak Alignment"


# ============================================================
# QUESTION TYPE DETECTION
# ============================================================

def detect_question_type(question):
    q = normalize(question)

    if re.search(r"\btrue\s*/?\s*false\b", q):
        return "True/False"

    if re.search(r"\b(a|b|c|d)\)", q) or "options:" in q:
        return "MCQ"

    if "fill in the blank" in q or "_____ " in q or "____" in q:
        return "Fill in the Blank"

    if "match the following" in q or "matching" in q:
        return "Matching"

    if any(
        phrase in q
        for phrase in [
            "case study",
            "case:",
            "read the case",
            "scenario",
            "situation",
        ]
    ):
        return "Case / Scenario"

    if any(
        word in q
        for word in [
            "calculate",
            "compute",
            "solve",
            "equation",
            "formula",
            "numerical",
        ]
    ):
        return "Numerical / Problem"

    if any(
        word in q
        for word in [
            "design",
            "develop",
            "construct",
            "program",
            "code",
            "implement",
        ]
    ):
        return "Practical / Application"

    if any(
        word in q
        for word in [
            "essay",
            "discuss in detail",
            "long answer",
        ]
    ):
        return "Essay / Long Answer"

    return "Short Answer"


# ============================================================
# ASSESSMENT FILE READERS
# ============================================================

def read_pdf(uploaded_file):
    raw = uploaded_file.getvalue()

    if not raw:
        return "", "The uploaded PDF is empty."

    # PyMuPDF
    try:
        import fitz

        pdf = fitz.open(stream=raw, filetype="pdf")
        pages = []

        for page_number in range(len(pdf)):
            try:
                page = pdf.load_page(page_number)
                text = page.get_text("text", sort=True)

                if text:
                    pages.append(text)
            except Exception:
                continue

        pdf.close()

        combined = clean_text("\n".join(pages))

        if len(combined) >= 20:
            return combined, "PyMuPDF text extraction"

    except Exception:
        pass

    # pypdf
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        pages = []

        for page in reader.pages:
            try:
                text = page.extract_text()

                if text:
                    pages.append(text)
            except Exception:
                continue

        combined = clean_text("\n".join(pages))

        if len(combined) >= 20:
            return combined, "pypdf text extraction"

    except Exception:
        pass

    # pdfplumber
    try:
        import pdfplumber

        pages = []

        with pdfplumber.open(io.BytesIO(raw)) as pdf:
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

        combined = clean_text("\n".join(pages))

        if len(combined) >= 20:
            return combined, "pdfplumber text extraction"

    except Exception:
        pass

    # OCR
    try:
        import fitz
        from PIL import Image
        import pytesseract

        pdf = fitz.open(stream=raw, filetype="pdf")
        pages = []

        for page_number in range(len(pdf)):
            try:
                page = pdf.load_page(page_number)

                pix = page.get_pixmap(
                    matrix=fitz.Matrix(2.0, 2.0),
                    alpha=False
                )

                image_bytes = pix.tobytes("png")
                image = Image.open(io.BytesIO(image_bytes))

                text = pytesseract.image_to_string(
                    image,
                    config="--psm 6"
                )

                if text:
                    pages.append(text)

            except Exception:
                continue

        pdf.close()

        combined = clean_text("\n".join(pages))

        if len(combined) >= 20:
            return combined, "OCR"

    except Exception:
        pass

    return "", (
        "No readable text was extracted from the PDF. "
        "If this is a scanned PDF, install Tesseract OCR."
    )


def read_docx(uploaded_file):
    try:
        from docx import Document

        document = Document(
            io.BytesIO(uploaded_file.getvalue())
        )

        parts = []

        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                parts.append(paragraph.text)

        for table in document.tables:
            for row in table.rows:
                cells = [
                    cell.text.strip()
                    for cell in row.cells
                ]

                if any(cells):
                    parts.append(" | ".join(cells))

        return clean_text("\n".join(parts)), "DOCX"

    except Exception as exc:
        return "", f"DOCX reading failed: {exc}"


def read_pptx(uploaded_file):
    try:
        from pptx import Presentation

        presentation = Presentation(
            io.BytesIO(uploaded_file.getvalue())
        )

        parts = []

        for slide in presentation.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    if shape.text.strip():
                        parts.append(shape.text)

        return clean_text("\n".join(parts)), "PPTX"

    except Exception as exc:
        return "", f"PPTX reading failed: {exc}"


def read_excel(uploaded_file):
    try:
        excel = pd.ExcelFile(
            io.BytesIO(uploaded_file.getvalue())
        )

        parts = []

        for sheet in excel.sheet_names:
            try:
                frame = pd.read_excel(
                    excel,
                    sheet_name=sheet,
                    header=None
                )

                parts.append(
                    f"Sheet: {sheet}"
                )

                for row in frame.fillna("").values.tolist():
                    values = [
                        str(value).strip()
                        for value in row
                        if str(value).strip()
                    ]

                    if values:
                        parts.append(" | ".join(values))

            except Exception:
                continue

        return clean_text("\n".join(parts)), "Excel"

    except Exception as exc:
        return "", f"Excel reading failed: {exc}"


def read_csv(uploaded_file):
    try:
        frame = pd.read_csv(
            io.BytesIO(uploaded_file.getvalue()),
            header=None,
            encoding_errors="ignore"
        )

        parts = []

        for row in frame.fillna("").values.tolist():
            values = [
                str(value).strip()
                for value in row
                if str(value).strip()
            ]

            if values:
                parts.append(" | ".join(values))

        return clean_text("\n".join(parts)), "CSV"

    except Exception as exc:
        return "", f"CSV reading failed: {exc}"


def read_text_file(uploaded_file):
    try:
        raw = uploaded_file.getvalue()

        for encoding in [
            "utf-8",
            "utf-16",
            "latin-1",
            "cp1252",
        ]:
            try:
                return (
                    clean_text(raw.decode(encoding)),
                    "Text file"
                )
            except Exception:
                continue

        return "", "The text encoding could not be read."

    except Exception as exc:
        return "", f"Text reading failed: {exc}"


def read_image(uploaded_file):
    try:
        from PIL import Image
        import pytesseract

        image = Image.open(
            io.BytesIO(uploaded_file.getvalue())
        )

        text = pytesseract.image_to_string(
            image,
            config="--psm 6"
        )

        text = clean_text(text)

        if len(text) >= 10:
            return text, "OCR"

        return "", "No readable text was found in the image."

    except Exception as exc:
        return "", f"Image OCR failed: {exc}"


def read_uploaded_file(uploaded_file):
    extension = uploaded_file.name.lower().split(".")[-1]

    if extension == "pdf":
        return read_pdf(uploaded_file)

    if extension == "docx":
        return read_docx(uploaded_file)

    if extension == "pptx":
        return read_pptx(uploaded_file)

    if extension in ["xlsx", "xls", "xlsm"]:
        return read_excel(uploaded_file)

    if extension == "csv":
        return read_csv(uploaded_file)

    if extension in ["txt", "md", "rtf"]:
        return read_text_file(uploaded_file)

    if extension in [
        "png",
        "jpg",
        "jpeg",
        "webp",
        "bmp",
        "tiff",
    ]:
        return read_image(uploaded_file)

    return "", (
        "Unsupported file type. "
        "Please upload PDF, DOCX, PPTX, XLSX, CSV, TXT, "
        "RTF, MD, or an image."
    )


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def clean_question_candidate(text):
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

    text = re.sub(
        r"^(mcq|mcqs)\s*[\.\):\-]?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    return clean_text(text)


def looks_like_question(text):
    value = clean_text(text)

    if len(value) < 8:
        return False

    normalized = normalize(value)

    if any(
        marker in normalized
        for marker in [
            "student name",
            "registration",
            "roll number",
            "date:",
            "time:",
            "total marks",
            "instructions:",
            "department:",
            "semester:",
            "section:",
        ]
    ):
        return False

    if value.endswith("?"):
        return True

    question_verbs = [
        "what",
        "why",
        "how",
        "which",
        "where",
        "when",
        "define",
        "explain",
        "describe",
        "calculate",
        "solve",
        "analyze",
        "analyse",
        "compare",
        "evaluate",
        "justify",
        "design",
        "develop",
        "identify",
        "discuss",
        "state",
        "list",
        "determine",
        "interpret",
        "recommend",
    ]

    first_words = normalized.split()[:4]

    if any(
        word in question_verbs
        for word in first_words
    ):
        return True

    return False


def extract_questions(text):
    text = clean_text(text)

    if not text:
        return []

    lines = [
        clean_text(line)
        for line in text.split("\n")
        if clean_text(line)
    ]

    questions = []

    # --------------------------------------------------------
    # Strategy 1: Numbered questions
    # --------------------------------------------------------

    current = []

    for line in lines:
        is_new = bool(
            re.match(
                r"^(?:question\s*)?\d+\s*[\.\):\-]\s+",
                line,
                flags=re.IGNORECASE
            )
        ) or bool(
            re.match(
                r"^q\s*\d+\s*[\.\):\-]\s+",
                line,
                flags=re.IGNORECASE
            )
        )

        if is_new:
            if current:
                candidate = clean_question_candidate(
                    " ".join(current)
                )

                if len(candidate) >= 8:
                    questions.append(candidate)

            current = [line]

        else:
            if current:
                current.append(line)

    if current:
        candidate = clean_question_candidate(
            " ".join(current)
        )

        if len(candidate) >= 8:
            questions.append(candidate)

    # --------------------------------------------------------
    # Strategy 2: Question marks
    # --------------------------------------------------------

    if len(questions) < 2:
        question_chunks = re.findall(
            r"[^?]{5,}\?",
            text,
            flags=re.DOTALL
        )

        for chunk in question_chunks:
            candidate = clean_question_candidate(chunk)

            if len(candidate) >= 8:
                questions.append(candidate)

    # --------------------------------------------------------
    # Strategy 3: Question-number patterns in a single line
    # --------------------------------------------------------

    if len(questions) < 2:
        chunks = re.split(
            r"(?=(?:Q(?:uestion)?\s*)?\d+\s*[\.\):\-])",
            text,
            flags=re.IGNORECASE
        )

        for chunk in chunks:
            candidate = clean_question_candidate(chunk)

            if looks_like_question(candidate):
                questions.append(candidate)

    # --------------------------------------------------------
    # Strategy 4: Meaningful lines
    # --------------------------------------------------------

    if len(questions) < 2:
        for line in lines:
            candidate = clean_question_candidate(line)

            if looks_like_question(candidate):
                questions.append(candidate)

    # --------------------------------------------------------
    # Last resort
    # --------------------------------------------------------

    if not questions:
        paragraphs = re.split(
            r"\n\s*\n",
            text
        )

        for paragraph in paragraphs:
            candidate = clean_question_candidate(
                paragraph
            )

            if len(candidate) >= 15:
                questions.append(candidate)

    # Remove obvious duplicates.
    final_questions = []
    seen = set()

    for question in questions:
        question = clean_question_candidate(question)

        key = re.sub(
            r"\W+",
            " ",
            question.lower()
        ).strip()

        if key in seen:
            continue

        seen.add(key)

        if len(question) >= 8:
            final_questions.append(question)

    return final_questions[:100]


# ============================================================
# REVISION ENGINE
# ============================================================

def remove_question_instruction_words(text):
    value = normalize(text)

    # Remove generic introductory wording while preserving
    # subject concepts.
    patterns = [
        r"\baccording to\b",
        r"\bbased on\b",
        r"\bwith reference to\b",
        r"\bin relation to\b",
        r"\bstudents should\b",
        r"\bstudents will\b",
        r"\blearners should\b",
    ]

    for pattern in patterns:
        value = re.sub(pattern, " ", value)

    return clean_text(value)


def get_core_topic(clo, plo, question):
    concepts = extract_key_concepts(
        clo,
        plo,
        question
    )

    # Prefer CLO-derived concepts.
    clo_concepts = meaningful_phrases(clo)

    if clo_concepts:
        clo_concepts.sort(
            key=lambda x: (len(x.split()), len(x)),
            reverse=True
        )

        return clo_concepts[0]

    if concepts:
        return concepts[0]

    question_concepts = meaningful_phrases(question)

    if question_concepts:
        return question_concepts[0]

    return "the topic"


def get_secondary_topic(clo, plo, question):
    candidates = []

    candidates.extend(meaningful_phrases(clo))
    candidates.extend(meaningful_phrases(plo))
    candidates.extend(meaningful_phrases(question))

    candidates = unique_preserve(candidates)

    candidates.sort(
        key=lambda x: (len(x.split()), len(x)),
        reverse=True
    )

    if len(candidates) > 1:
        return candidates[1]

    return ""


def clean_topic_phrase(text):
    text = clean_text(text)

    replacements = [
        (" students ", " "),
        (" learners ", " "),
        (" ability to ", " "),
        (" knowledge of ", " "),
        (" understanding of ", " "),
    ]

    lower = " " + text.lower() + " "

    for old, new in replacements:
        lower = lower.replace(old, new)

    return clean_text(lower)


def preserve_numerical_context(original):
    numbers = re.findall(
        r"\b\d+(?:\.\d+)?\b",
        original
    )

    units = re.findall(
        r"\b(?:m/s|km/h|kg|g|N|J|W|Pa|mol|m|cm|mm|s|min|h|Hz|V|A|ohm)\b",
        original,
        flags=re.IGNORECASE
    )

    if numbers:
        number_text = ", ".join(numbers[:5])

        if units:
            return (
                f"The problem provides the values "
                f"{number_text} {', '.join(unique_preserve(units[:3]))}."
            )

        return f"The problem provides the values {number_text}."

    return ""


def build_revision_candidates(
    original,
    clo,
    plo,
    question_type,
):
    target = target_bloom(clo, plo)

    if target is None:
        target = detect_bloom_level(original)

    topic = clean_topic_phrase(
        get_core_topic(clo, plo, original)
    )

    secondary = clean_topic_phrase(
        get_secondary_topic(clo, plo, original)
    )

    if not topic:
        topic = "the main concept"

    candidates = []

    # --------------------------------------------------------
    # REMEMBER
    # --------------------------------------------------------

    if target == 1:
        candidates.extend([
            f"What is {topic}?",
            f"Define {topic} and state its main purpose.",
            f"Identify the main features of {topic}.",
            f"List the key components of {topic}.",
        ])

    # --------------------------------------------------------
    # UNDERSTAND
    # --------------------------------------------------------

    elif target == 2:
        candidates.extend([
            f"How does {topic} work, and why is it important?",
            f"Explain how {topic} works in a clear and simple way.",
            f"Describe the main features of {topic} and explain their importance.",
            f"How would you explain {topic} to someone who is new to the subject?",
        ])

        if secondary:
            candidates.append(
                f"Explain how {topic} is related to {secondary}."
            )

    # --------------------------------------------------------
    # APPLY
    # --------------------------------------------------------

    elif target == 3:
        candidates.extend([
            f"How would you use {topic} to solve a practical problem?",
            f"Apply the principles of {topic} to the situation described in the question.",
            f"Use your knowledge of {topic} to solve the given problem and show the main steps.",
            f"Demonstrate how {topic} can be applied in a practical situation.",
        ])

        if question_type == "Numerical / Problem":
            context = preserve_numerical_context(original)

            if context:
                candidates.insert(
                    0,
                    f"{original.rstrip('.?')} "
                    f"Calculate the required result and show your working."
                )
            else:
                candidates.insert(
                    0,
                    f"Solve the problem using the principles of {topic} and show your working."
                )

    # --------------------------------------------------------
    # ANALYZE
    # --------------------------------------------------------

    elif target == 4:
        candidates.extend([
            f"What are the main causes or factors related to {topic}, and how do they affect the outcome?",
            f"Compare the main factors involved in {topic} and explain how they influence the result.",
            f"Analyze the relationship between {topic} and {secondary or 'its effects'}.",
            f"Examine {topic} and explain the main factors that contribute to it.",
            f"How do the different factors involved in {topic} interact with one another?",
        ])

        if question_type == "Case / Scenario":
            candidates.insert(
                0,
                f"Analyze the main problem in the case and explain the factors that contributed to it."
            )

    # --------------------------------------------------------
    # EVALUATE
    # --------------------------------------------------------

    elif target == 5:
        candidates.extend([
            f"Evaluate the main options for addressing {topic} and justify the most appropriate option.",
            f"Compare the possible approaches to {topic} and justify which approach is most suitable.",
            f"Which approach to {topic} would be most appropriate in this situation? Justify your answer with reasons.",
            f"Assess the available options related to {topic} and recommend the most suitable one.",
        ])

        if question_type == "Case / Scenario":
            candidates.insert(
                0,
                f"Evaluate the possible solutions to the problem in the case and recommend the most appropriate solution. Justify your recommendation."
            )

    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------

    elif target == 6:
        candidates.extend([
            f"Design a suitable solution for a practical problem involving {topic}.",
            f"Develop a practical plan for addressing a problem involving {topic}.",
            f"Propose a suitable approach for applying {topic} to a real-world situation.",
            f"Construct a solution that uses the key principles of {topic}.",
        ])

        if question_type == "Practical / Application":
            candidates.insert(
                0,
                f"Design a practical solution that addresses the problem described in the question using {topic}."
            )

    # --------------------------------------------------------
    # PRESERVE CASE STUDY CONTEXT
    # --------------------------------------------------------

    if question_type == "Case / Scenario":
        candidates.extend([
            f"Analyze the situation presented in the case and explain the main issue related to {topic}.",
            f"Using the information in the case, identify the main issue and explain how {topic} affects the situation.",
        ])

    # --------------------------------------------------------
    # REMOVE DUPLICATES
    # --------------------------------------------------------

    cleaned = []

    for candidate in candidates:
        candidate = clean_text(candidate)

        # Never expose outcome terminology.
        forbidden = [
            "according to the clo",
            "according to the plo",
            "learning outcome",
            "course learning outcome",
            "program learning outcome",
            "as stated in the clo",
            "as stated in the plo",
        ]

        if any(
            phrase in normalize(candidate)
            for phrase in forbidden
        ):
            continue

        candidate = sentence_case(
            candidate
        )

        candidate = ensure_question_mark(
            candidate
        )

        if candidate.lower() == clean_text(original).lower():
            continue

        cleaned.append(candidate)

    return unique_preserve(cleaned)


def strengthen_candidate(
    candidate,
    target_level,
    question_type,
    topic,
):
    candidate = clean_text(candidate)

    if target_level == 1:
        return candidate

    if target_level == 2:
        if "why" not in normalize(candidate) and "explain" not in normalize(candidate):
            candidate = candidate.rstrip("?") + " and explain why it is important?"
        return candidate

    if target_level == 3:
        if "show" not in normalize(candidate):
            candidate = candidate.rstrip("?") + " and show the main steps."
        return ensure_question_mark(candidate)

    if target_level == 4:
        if "how" not in normalize(candidate):
            candidate = (
                candidate.rstrip("?")
                + " and explain how the main factors are related."
            )
        return ensure_question_mark(candidate)

    if target_level == 5:
        if "justify" not in normalize(candidate):
            candidate = (
                candidate.rstrip("?")
                + " Justify your answer with clear reasons."
            )
        return ensure_question_mark(candidate)

    if target_level == 6:
        if not any(
            word in normalize(candidate)
            for word in [
                "design",
                "develop",
                "construct",
                "propose",
            ]
        ):
            candidate = (
                f"Design a practical solution involving {topic} "
                f"for the situation described."
            )

        return ensure_question_mark(candidate)

    return candidate


def evaluate_question(question, clo, plo, subject):
    clo_score, clo_feedback = score_clo(
        question,
        clo
    )

    plo_score, plo_feedback = score_plo(
        question,
        plo
    )

    bloom_score, bloom_feedback, actual_bloom, target_bloom_name = (
        bloom_analysis(
            question,
            clo,
            plo
        )
    )

    relevance_score, relevance_feedback = subject_relevance(
        question,
        subject,
        clo,
        plo
    )

    clarity = clarity_score(question)
    clarity_text = clarity_feedback(clarity)

    measurability = measurability_score(question)
    measurability_text = measurability_feedback(
        measurability
    )

    overall = calculate_overall(
        clo_score,
        plo_score,
        bloom_score,
        relevance_score,
        clarity,
        measurability,
    )

    return {
        "question": question,
        "clo": clo_score,
        "clo_feedback": clo_feedback,
        "plo": plo_score,
        "plo_feedback": plo_feedback,
        "bloom": bloom_score,
        "bloom_feedback": bloom_feedback,
        "actual_bloom": actual_bloom,
        "target_bloom": target_bloom_name,
        "relevance": relevance_score,
        "relevance_feedback": relevance_feedback,
        "clarity": clarity,
        "clarity_feedback": clarity_text,
        "measurability": measurability,
        "measurability_feedback": measurability_text,
        "overall": overall,
        "status": attainment_label(overall),
    }


def generate_best_revision(
    original,
    clo,
    plo,
    subject,
):
    question_type = detect_question_type(original)

    target_level = target_bloom(clo, plo)

    if target_level is None:
        target_level = detect_bloom_level(original)

    candidates = build_revision_candidates(
        original,
        clo,
        plo,
        question_type,
    )

    evaluated = []

    # First generation.
    for candidate in candidates:
        metrics = evaluate_question(
            candidate,
            clo,
            plo,
            subject,
        )

        evaluated.append(metrics)

    # Strengthen candidates that do not attain.
    strengthened = []

    topic = clean_topic_phrase(
        get_core_topic(clo, plo, original)
    )

    for item in evaluated:
        if item["overall"] < ATTAINMENT:
            stronger = strengthen_candidate(
                item["question"],
                target_level,
                question_type,
                topic,
            )

            if stronger != item["question"]:
                stronger_metrics = evaluate_question(
                    stronger,
                    clo,
                    plo,
                    subject,
                )

                strengthened.append(
                    stronger_metrics
                )

    evaluated.extend(strengthened)

    # --------------------------------------------------------
    # Targeted candidates designed to satisfy each dimension.
    # These remain natural assessment questions.
    # --------------------------------------------------------

    if target_level == 2:
        targeted = [
            f"Explain how {topic} works and why it is important.",
            f"Describe {topic} and explain how it affects the relevant process or outcome.",
        ]

    elif target_level == 3:
        targeted = [
            f"Use the principles of {topic} to solve the given problem and show your working.",
            f"How can {topic} be applied to the situation described? Demonstrate the steps you would use.",
        ]

    elif target_level == 4:
        targeted = [
            f"Analyze the main factors related to {topic} and explain how they influence the outcome.",
            f"Compare the key factors involved in {topic} and explain the relationship between them.",
        ]

    elif target_level == 5:
        targeted = [
            f"Evaluate the possible approaches to {topic} and justify the most appropriate one.",
            f"Which approach to {topic} is most suitable for the situation? Justify your choice with reasons.",
        ]

    elif target_level == 6:
        targeted = [
            f"Design a practical solution to a problem involving {topic}.",
            f"Develop a suitable plan for addressing a practical problem involving {topic}.",
        ]

    else:
        targeted = [
            f"Identify the main features of {topic}.",
            f"Define {topic} and state its main purpose.",
        ]

    for candidate in targeted:
        candidate = ensure_question_mark(
            sentence_case(candidate)
        )

        metrics = evaluate_question(
            candidate,
            clo,
            plo,
            subject,
        )

        evaluated.append(metrics)

    # --------------------------------------------------------
    # Rank by actual recalculated score.
    # Do NOT artificially modify scores.
    # --------------------------------------------------------

    evaluated = sorted(
        evaluated,
        key=lambda item: (
            item["overall"],
            item["clo"] or 0,
            item["plo"] or 0,
            item["bloom"],
        ),
        reverse=True,
    )

    if evaluated:
        return evaluated[0]

    return None


# ============================================================
# ANALYSIS OF COMPLETE ASSESSMENT
# ============================================================

def analyze_assessment(
    questions,
    clo,
    plo,
    subject,
):
    results = []

    for index, question in enumerate(
        questions,
        start=1
    ):
        metrics = evaluate_question(
            question,
            clo,
            plo,
            subject,
        )

        metrics["number"] = index
        metrics["question_type"] = detect_question_type(
            question
        )

        results.append(metrics)

    return results


# ============================================================
# CSS
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
    color: #666666;
    font-size: 16px;
    margin-bottom: 20px;
}

.score-box {
    border: 1px solid #dddddd;
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    background: #fafafa;
}

.small-label {
    color: #666666;
    font-size: 13px;
}

.big-score {
    font-size: 30px;
    font-weight: 800;
}

.revision-card {
    border: 1px solid #dddddd;
    border-radius: 12px;
    padding: 18px;
    margin-bottom: 16px;
    background: white;
}

.feedback {
    font-size: 14px;
    line-height: 1.5;
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🎓 OBE Quiz Checker</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    "Analyze assessment questions, identify alignment gaps, "
    "and generate simple Bloom-appropriate revisions."
    "</div>",
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header("Assessment Information")

    st.session_state.assessment_title = st.text_input(
        "Assessment Title",
        value=st.session_state.assessment_title,
        placeholder="e.g., Midterm Quiz"
    )

    st.session_state.subject = st.text_input(
        "Subject / Course",
        value=st.session_state.subject,
        placeholder="e.g., Chemistry, Programming, Marketing"
    )

    st.session_state.course = st.text_input(
        "Course Code",
        value=st.session_state.course,
        placeholder="e.g., CHEM-101"
    )

    st.divider()

    st.caption(
        "Alignment is calculated only after the CLO, PLO, "
        "and assessment questions are provided."
    )


# ============================================================
# LEARNING OUTCOMES
# ============================================================

st.header("1. Learning Outcomes")

col1, col2 = st.columns(2)

with col1:
    st.session_state.clo = st.text_area(
        "Course Learning Outcome (CLO)",
        value=st.session_state.clo,
        height=150,
        placeholder=(
            "Example: Explain the process of photosynthesis "
            "and its importance to plant growth."
        ),
    )

with col2:
    st.session_state.plo = st.text_area(
        "Program Learning Outcome (PLO)",
        value=st.session_state.plo,
        height=150,
        placeholder=(
            "Example: Apply scientific knowledge to solve "
            "practical problems."
        ),
    )

clo_ready = bool(
    clean_text(st.session_state.clo)
)

plo_ready = bool(
    clean_text(st.session_state.plo)
)

if not clo_ready or not plo_ready:
    st.info(
        "⏳ Awaiting Learning Outcomes — enter both CLO and PLO "
        "before alignment can be calculated."
    )
else:
    target = target_bloom(
        st.session_state.clo,
        st.session_state.plo
    )

    if target:
        st.success(
            f"Learning outcomes received. Intended cognitive level: "
            f"**{BLOOM_NAMES[target]}**."
        )
    else:
        st.info(
            "Learning outcomes received. No explicit Bloom action "
            "verb was detected, so the question's cognitive level "
            "will be evaluated independently."
        )


# ============================================================
# FILE UPLOAD
# ============================================================

st.header("2. Upload Complete Assessment")

uploaded_file = st.file_uploader(
    "Upload your complete assessment",
    type=[
        "pdf",
        "docx",
        "pptx",
        "xlsx",
        "xls",
        "xlsm",
        "csv",
        "txt",
        "md",
        "rtf",
        "png",
        "jpg",
        "jpeg",
        "webp",
        "bmp",
        "tiff",
    ],
    help=(
        "The tool accepts MCQs, True/False, fill-in-the-blank, "
        "matching, case studies, numerical problems, practical "
        "questions, short answers, and essays."
    ),
)

if uploaded_file is not None:

    file_key = (
        uploaded_file.name,
        len(uploaded_file.getvalue())
    )

    if st.session_state.get("uploaded_file_key") != file_key:
        text, source = read_uploaded_file(
            uploaded_file
        )

        st.session_state.assessment_text = text
        st.session_state.assessment_source = source
        st.session_state.questions = extract_questions(text)
        st.session_state.analysis = []
        st.session_state.analyzed = False
        st.session_state.accepted_revisions = {}
        st.session_state.uploaded_file_key = file_key

    if st.session_state.assessment_text:
        st.success(
            f"File read successfully using "
            f"**{st.session_state.assessment_source}**."
        )

        st.write(
            f"Detected **{len(st.session_state.questions)} "
            f"potential assessment question(s)**."
        )

        if len(st.session_state.questions) == 0:
            st.warning(
                "No structured questions were detected. "
                "The file was readable, but the question format "
                "could not be identified."
            )

            with st.expander("View extracted text"):
                st.text(
                    st.session_state.assessment_text[:12000]
                )
    else:
        st.error(
            st.session_state.assessment_source
        )


# ============================================================
# ANALYZE BUTTON
# ============================================================

st.header("3. Analyze Assessment")

ready_to_analyze = (
    clo_ready
    and plo_ready
    and bool(st.session_state.questions)
)

if not clo_ready or not plo_ready:
    st.warning(
        "⏳ Ready for Analysis only after both CLO and PLO "
        "are entered."
    )

if not st.session_state.questions:
    st.warning(
        "⏳ Upload an assessment containing readable questions."
    )

if st.button(
    "🔍 Analyze Assessment",
    type="primary",
    disabled=not ready_to_analyze,
    use_container_width=True,
):

    st.session_state.analysis = analyze_assessment(
        st.session_state.questions,
        st.session_state.clo,
        st.session_state.plo,
        st.session_state.subject,
    )

    st.session_state.analyzed = True
    st.session_state.accepted_revisions = {}

    st.success(
        "Assessment analysis completed."
    )


# ============================================================
# DO NOT SHOW ALIGNMENT BEFORE ANALYSIS
# ============================================================

if not st.session_state.analyzed:
    st.info(
        "⏳ Alignment status will appear here after the assessment "
        "has been analyzed."
    )

    st.stop()


# ============================================================
# OVERALL ASSESSMENT SCORE
# ============================================================

results = st.session_state.analysis

if not results:
    st.error(
        "No assessment questions were available for analysis."
    )
    st.stop()


# Apply accepted revisions.
display_results = []

for result in results:
    q_number = result["number"]

    if q_number in st.session_state.accepted_revisions:
        display_results.append(
            st.session_state.accepted_revisions[q_number]
        )
    else:
        display_results.append(result)


overall_score = round(
    sum(
        item["overall"]
        for item in display_results
    ) / len(display_results)
)

attained_count = sum(
    1
    for item in display_results
    if item["overall"] >= ATTAINMENT
)

revision_count = len(display_results) - attained_count


st.header("4. Overall Alignment")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Overall Score",
        f"{overall_score}%"
    )

with col2:
    st.metric(
        "Questions",
        len(display_results)
    )

with col3:
    st.metric(
        "Attained",
        attained_count
    )

with col4:
    st.metric(
        "Requiring Revision",
        revision_count
    )


if overall_score >= ATTAINMENT:
    st.success(
        f"🟢 Alignment Attained — Overall assessment score "
        f"is **{overall_score}%**."
    )

    if overall_score >= 80:
        st.balloons()

else:
    st.warning(
        f"🟠 Revision Required — Overall assessment score "
        f"is **{overall_score}%**."
    )


# ============================================================
# QUESTIONS REQUIRING REVISION
# ============================================================

weak_questions = [
    item
    for item in display_results
    if item["overall"] < ATTAINMENT
]


st.header("5. Questions Requiring Revision")

if not weak_questions:
    st.success(
        "🟢 All analyzed questions have attained 80% or higher."
    )

else:
    st.write(
        "The tool automatically identifies weak questions and "
        "generates a simpler question appropriate to the required "
        "Bloom level."
    )

    for item in weak_questions:

        number = item["number"]

        st.markdown(
            f"### Question {number} — {item['overall']}%"
        )

        st.caption(
            f"Question type: {item['question_type']} | "
            f"Current level: {item['actual_bloom']} | "
            f"Target level: {item['target_bloom']}"
        )

        st.markdown("**Current Question**")
        st.info(item["question"])

        st.markdown("**Why does this question need revision?**")

        diagnosis_parts = []

        if item["clo"] < ATTAINMENT:
            diagnosis_parts.append(
                "The question does not fully measure the specific "
                "course-level skill required."
            )

        if item["plo"] < ATTAINMENT:
            diagnosis_parts.append(
                "The question provides limited evidence of the "
                "broader program capability."
            )

        if item["bloom"] < ATTAINMENT:
            diagnosis_parts.append(
                f"The question operates at {item['actual_bloom']}, "
                f"while the intended level is {item['target_bloom']}."
            )

        if item["clarity"] < ATTAINMENT:
            diagnosis_parts.append(
                "The wording can be made clearer or more focused."
            )

        if item["measurability"] < ATTAINMENT:
            diagnosis_parts.append(
                "The expected student response should be more "
                "observable and measurable."
            )

        if diagnosis_parts:
            for diagnosis in diagnosis_parts:
                st.write("• " + diagnosis)
        else:
            st.write(
                "The combined score is below the attainment threshold."
            )

        # ----------------------------------------------------
        # Separate evaluations
        # ----------------------------------------------------

        with st.expander(
            "View Detailed Analysis",
            expanded=True
        ):

            metric_col1, metric_col2, metric_col3 = st.columns(3)

            with metric_col1:
                st.metric(
                    "CLO Alignment",
                    f"{item['clo']}%"
                )
                st.write(
                    item["clo_feedback"]
                )

            with metric_col2:
                st.metric(
                    "PLO Alignment",
                    f"{item['plo']}%"
                )
                st.write(
                    item["plo_feedback"]
                )

            with metric_col3:
                st.metric(
                    "Bloom Alignment",
                    f"{item['bloom']}%"
                )
                st.write(
                    item["bloom_feedback"]
                )

            st.divider()

            other_col1, other_col2, other_col3 = st.columns(3)

            with other_col1:
                st.metric(
                    "Subject Relevance",
                    f"{item['relevance']}%"
                )
                st.write(
                    item["relevance_feedback"]
                )

            with other_col2:
                st.metric(
                    "Clarity",
                    f"{item['clarity']}%"
                )
                st.write(
                    item["clarity_feedback"]
                )

            with other_col3:
                st.metric(
                    "Measurability",
                    f"{item['measurability']}%"
                )
                st.write(
                    item["measurability_feedback"]
                )

        # ----------------------------------------------------
        # Generate revision
        # ----------------------------------------------------

        revision_key = f"revision_{number}"

        if revision_key not in st.session_state:
            st.session_state[revision_key] = (
                generate_best_revision(
                    item["question"],
                    st.session_state.clo,
                    st.session_state.plo,
                    st.session_state.subject,
                )
            )

        revision = st.session_state[revision_key]

        if revision:

            st.markdown("### 💡 Suggested Question")

            st.success(
                revision["question"]
            )

            st.caption(
                "The CLO/PLO were used internally to guide the "
                "revision. They are not inserted into the student-facing question."
            )

            st.write(
                f"**Suggested Bloom Level:** "
                f"{revision['actual_bloom']}"
            )

            if revision["actual_bloom"] == revision["target_bloom"]:
                st.write(
                    "✅ The suggested question uses the intended "
                    "cognitive level."
                )
            else:
                st.write(
                    f"⚠️ The suggested question operates at "
                    f"{revision['actual_bloom']} rather than the "
                    f"target {revision['target_bloom']}."
                )

            st.markdown("**Why this revision works**")

            revision_reasons = []

            if revision["clo"] >= ATTAINMENT:
                revision_reasons.append(
                    "It directly measures the required course-level skill."
                )

            if revision["plo"] >= ATTAINMENT:
                revision_reasons.append(
                    "It provides evidence of the broader program capability."
                )

            if revision["bloom"] >= ATTAINMENT:
                revision_reasons.append(
                    "Its cognitive demand matches the intended Bloom level."
                )

            if revision["clarity"] >= ATTAINMENT:
                revision_reasons.append(
                    "Its wording is clear and focused."
                )

            if revision["measurability"] >= ATTAINMENT:
                revision_reasons.append(
                    "The expected response is observable and assessable."
                )

            for reason in revision_reasons:
                st.write("• " + reason)

            st.markdown("### Suggested Question Score")

            score_cols = st.columns(6)

            score_data = [
                ("CLO", revision["clo"]),
                ("PLO", revision["plo"]),
                ("Bloom", revision["bloom"]),
                ("Relevance", revision["relevance"]),
                ("Clarity", revision["clarity"]),
                ("Measurability", revision["measurability"]),
            ]

            for column, (label, value) in zip(
                score_cols,
                score_data
            ):
                with column:
                    st.metric(
                        label,
                        f"{value}%"
                    )

            st.markdown(
                f"### Before Revision: "
                f"**{item['overall']}%**"
            )

            st.markdown(
                f"### After Revision: "
                f"**{revision['overall']}%**"
            )

            if revision["overall"] >= ATTAINMENT:
                st.success(
                    f"🟢 Alignment Attained — "
                    f"{revision['overall']}%"
                )

            else:
                st.warning(
                    f"🟠 Suggested revision score: "
                    f"{revision['overall']}%. "
                    f"The tool will continue using the strongest "
                    f"recalculated candidate available."
                )

            if st.button(
                "✅ Use This Suggested Question",
                key=f"use_revision_{number}",
                use_container_width=True,
            ):

                accepted = dict(revision)
                accepted["number"] = number
                accepted["question_type"] = detect_question_type(
                    revision["question"]
                )

                st.session_state.accepted_revisions[
                    number
                ] = accepted

                st.rerun()

        st.divider()


# ============================================================
# ATTAINED QUESTIONS
# ============================================================

st.header("6. Attained Questions")

attained_questions = [
    item
    for item in display_results
    if item["overall"] >= ATTAINMENT
]

if attained_questions:

    for item in attained_questions:

        with st.expander(
            f"Question {item['number']} — "
            f"{item['overall']}% — 🟢 Attained"
        ):

            st.write(
                f"**Question:** {item['question']}"
            )

            cols = st.columns(4)

            with cols[0]:
                st.metric(
                    "CLO",
                    f"{item['clo']}%"
                )

            with cols[1]:
                st.metric(
                    "PLO",
                    f"{item['plo']}%"
                )

            with cols[2]:
                st.metric(
                    "Bloom",
                    f"{item['bloom']}%"
                )

            with cols[3]:
                st.metric(
                    "Overall",
                    f"{item['overall']}%"
                )

            st.success(
                "🟢 Alignment Attained"
            )

else:
    st.info(
        "No questions have reached the 80% attainment threshold yet."
    )


# ============================================================
# ALIGNMENT OVERVIEW — ONLY GRAPH
# ============================================================

st.header("7. Alignment Overview")

chart_rows = []

for item in display_results:
    chart_rows.append(
        {
            "Question": f"Q{item['number']}",
            "CLO": item["clo"] or 0,
            "PLO": item["plo"] or 0,
            "Bloom": item["bloom"],
            "Overall": item["overall"],
        }
    )

chart_df = pd.DataFrame(chart_rows)

if not chart_df.empty:
    chart_df = chart_df.set_index("Question")

    st.bar_chart(
        chart_df[
            [
                "CLO",
                "PLO",
                "Bloom",
                "Overall",
            ]
        ]
    )


# ============================================================
# QUESTION OVERVIEW
# ============================================================

st.header("8. Question Overview")

overview_rows = []

for item in display_results:
    overview_rows.append(
        {
            "Question": f"Q{item['number']}",
            "Type": item["question_type"],
            "CLO": item["clo"],
            "PLO": item["plo"],
            "Bloom": item["bloom"],
            "Actual Bloom": item["actual_bloom"],
            "Target Bloom": item["target_bloom"],
            "Relevance": item["relevance"],
            "Clarity": item["clarity"],
            "Measurability": item["measurability"],
            "Overall": item["overall"],
            "Status": (
                "Attained"
                if item["overall"] >= ATTAINMENT
                else "Needs Revision"
            ),
        }
    )

overview_df = pd.DataFrame(
    overview_rows
)

st.dataframe(
    overview_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# DETAILED QUESTION ANALYSIS
# ============================================================

st.header("9. Detailed Question Analysis")

selected_number = st.selectbox(
    "Select a question",
    options=[
        item["number"]
        for item in display_results
    ],
    format_func=lambda number: f"Question {number}",
)

selected_item = next(
    (
        item
        for item in display_results
        if item["number"] == selected_number
    ),
    None
)

if selected_item:

    st.subheader(
        f"Question {selected_number}"
    )

    st.info(
        selected_item["question"]
    )

    st.write(
        f"**Overall Score:** "
        f"{selected_item['overall']}% "
        f"— {selected_item['status']}"
    )

    detail_rows = [
        {
            "Area": "CLO Alignment",
            "Score": f"{selected_item['clo']}%",
            "Evaluation": selected_item["clo_feedback"],
        },
        {
            "Area": "PLO Alignment",
            "Score": f"{selected_item['plo']}%",
            "Evaluation": selected_item["plo_feedback"],
        },
        {
            "Area": "Bloom Alignment",
            "Score": f"{selected_item['bloom']}%",
            "Evaluation": selected_item["bloom_feedback"],
        },
        {
            "Area": "Subject Relevance",
            "Score": f"{selected_item['relevance']}%",
            "Evaluation": selected_item["relevance_feedback"],
        },
        {
            "Area": "Clarity",
            "Score": f"{selected_item['clarity']}%",
            "Evaluation": selected_item["clarity_feedback"],
        },
        {
            "Area": "Measurability",
            "Score": f"{selected_item['measurability']}%",
            "Evaluation": selected_item["measurability_feedback"],
        },
    ]

    st.dataframe(
        pd.DataFrame(detail_rows),
        use_container_width=True,
        hide_index=True,
    )

    if selected_item["overall"] < ATTAINMENT:

        st.warning(
            "This question should be revised before being treated "
            "as fully aligned."
        )

        selected_revision = generate_best_revision(
            selected_item["question"],
            st.session_state.clo,
            st.session_state.plo,
            st.session_state.subject,
        )

        if selected_revision:

            st.markdown("### Recommended Revision")

            st.success(
                selected_revision["question"]
            )

            st.write(
                f"**Revised Score:** "
                f"{selected_revision['overall']}%"
            )

            if selected_revision["overall"] >= ATTAINMENT:
                st.success(
                    "🟢 Alignment Attained"
                )


# ============================================================
# EXPORT
# ============================================================

st.header("10. Export Results")

export_rows = []

for item in display_results:

    export_rows.append(
        {
            "Question Number": item["number"],
            "Original / Current Question": item["question"],
            "Question Type": item["question_type"],
            "CLO Alignment": item["clo"],
            "CLO Feedback": item["clo_feedback"],
            "PLO Alignment": item["plo"],
            "PLO Feedback": item["plo_feedback"],
            "Bloom Alignment": item["bloom"],
            "Actual Bloom": item["actual_bloom"],
            "Target Bloom": item["target_bloom"],
            "Bloom Feedback": item["bloom_feedback"],
            "Subject Relevance": item["relevance"],
            "Clarity": item["clarity"],
            "Measurability": item["measurability"],
            "Overall Score": item["overall"],
            "Status": (
                "Alignment Attained"
                if item["overall"] >= ATTAINMENT
                else "Needs Revision"
            ),
        }
    )

export_df = pd.DataFrame(
    export_rows
)

csv_data = export_df.to_csv(
    index=False
).encode("utf-8")

st.download_button(
    "⬇️ Download Analysis CSV",
    data=csv_data,
    file_name="OBE_Quiz_Checker_Analysis.csv",
    mime="text/csv",
    use_container_width=True,
)


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "OBE Quiz Checker evaluates CLO alignment, PLO alignment, "
    "Bloom level, subject relevance, clarity, and measurability "
    "as separate dimensions. Suggested questions are generated "
    "from the required learning skill rather than copying the CLO."
)
