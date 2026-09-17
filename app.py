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
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "questions": [],
    "analysis": [],
    "uploaded_text": "",
    "analyzed": False,
    "selected_question": None,
    "revision_candidates": {},
    "accepted_revisions": {},
    "last_overall_score": None,
    "balloons_shown": False,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# CONSTANTS
# ============================================================

BLOOM_LEVELS = {
    "Remember": 1,
    "Understand": 2,
    "Apply": 3,
    "Analyze": 4,
    "Evaluate": 5,
    "Create": 6,
}

BLOOM_VERBS = {
    "Remember": [
        "define", "identify", "list", "name", "state", "recall",
        "recognize", "mention", "select", "label", "match"
    ],
    "Understand": [
        "explain", "describe", "summarize", "interpret", "classify",
        "discuss", "compare", "paraphrase", "illustrate", "clarify"
    ],
    "Apply": [
        "calculate", "solve", "apply", "demonstrate", "use",
        "implement", "execute", "perform", "compute", "show"
    ],
    "Analyze": [
        "analyze", "analyse", "differentiate", "examine", "investigate",
        "distinguish", "organize", "deconstruct", "compare and contrast",
        "identify factors", "identify causes"
    ],
    "Evaluate": [
        "evaluate", "justify", "assess", "critique", "judge",
        "defend", "recommend", "argue", "appraise", "validate"
    ],
    "Create": [
        "design", "create", "develop", "construct", "formulate",
        "produce", "propose", "plan", "generate", "compose"
    ],
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "for", "with", "from",
    "into", "onto", "this", "that", "these", "those", "what",
    "which", "who", "when", "where", "why", "how", "are", "is",
    "was", "were", "be", "been", "being", "to", "of", "in", "on",
    "at", "by", "as", "it", "its", "their", "they", "them", "you",
    "your", "can", "may", "will", "would", "should", "does", "do",
    "did", "than", "then", "also", "about", "through", "using",
    "used", "use", "given", "following", "following"
}

GENERIC_VAGUE_PHRASES = [
    "discuss this",
    "discuss the topic",
    "discuss",
    "explain this",
    "explain the topic",
    "write about",
    "comment on",
    "give details",
    "describe this",
    "what do you think",
    "elaborate",
    "answer the question",
    "do the question",
    "solve it",
]

SECTION_WORDS = [
    "course learning outcomes",
    "learning outcomes",
    "course outcomes",
    "clos",
    "plo",
    "program learning outcomes",
    "program outcomes",
]


# ============================================================
# BASIC TEXT UTILITIES
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = str(text)
    text = text.replace("\x00", " ")
    text = text.replace("\u00a0", " ")
    text = text.replace("\r", "\n")

    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)

    return "\n".join(lines)


def normalize(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text):
    words = re.findall(r"[a-zA-Z0-9]+", normalize(text))
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def keyword_set(text):
    return set(tokenize(text))


def overlap_score(text_a, text_b):
    a = keyword_set(text_a)
    b = keyword_set(text_b)

    if not a or not b:
        return 0

    intersection = len(a.intersection(b))

    # Directional overlap plus Jaccard-style component
    recall = intersection / max(len(a), 1)
    precision = intersection / max(len(b), 1)
    jaccard = intersection / max(len(a.union(b)), 1)

    score = (
        0.45 * recall +
        0.30 * precision +
        0.25 * jaccard
    )

    return round(score * 100, 1)


def contains_any(text, phrases):
    text_n = normalize(text)
    return any(p in text_n for p in phrases)


def extract_numbers(text):
    return re.findall(
        r"\b\d+(?:\.\d+)?\b|"
        r"\b\d+(?:\.\d+)?\s*[%°]\b",
        str(text)
    )


def extract_technical_tokens(text):
    """
    Keeps numbers, abbreviations, formulas, units and capitalized terms.
    Used to make sure automatic revisions do not silently change the
    technical content.
    """
    tokens = []

    tokens.extend(extract_numbers(text))

    # Common units / mathematical symbols
    units = re.findall(
        r"\b(?:kg|g|mg|m|cm|mm|km|s|sec|min|hr|Hz|N|J|W|V|A|"
        r"Pa|mol|L|mL|cm2|m2|m3|°C|°F|%|km/h|m/s)\b",
        str(text),
        flags=re.I
    )
    tokens.extend(units)

    # Acronyms
    tokens.extend(re.findall(r"\b[A-Z]{2,}\b", str(text)))

    # Formula-like strings
    tokens.extend(
        re.findall(r"\b[A-Za-z]+\s*=\s*[^,\n.]+", str(text))
    )

    return [t.strip() for t in tokens if t.strip()]


# ============================================================
# LEARNING OUTCOME PARSING
# ============================================================

def parse_outcomes(text, prefix=None):
    if not text:
        return []

    raw = clean_text(text)

    outcomes = []

    patterns = [
        r"(?:^|\n)\s*(?:CLO|PLO|CO|PO)\s*[-:]?\s*\d+\s*[:.)-]?\s*(.+)",
        r"(?:^|\n)\s*\d+\s*[\.\):-]\s*(.+)",
        r"(?:^|\n)\s*[-•]\s*(.+)",
    ]

    found = []

    for pattern in patterns:
        matches = re.findall(pattern, raw, flags=re.I)
        if matches:
            found.extend(matches)

    if not found:
        paragraphs = [
            p.strip()
            for p in re.split(r"\n+", raw)
            if len(p.strip()) > 12
        ]
        found = paragraphs

    for item in found:
        item = clean_text(item)

        if len(item) < 8:
            continue

        low = item.lower()

        if any(
            heading in low
            for heading in [
                "learning outcomes",
                "course learning outcomes",
                "program learning outcomes",
                "clos:",
                "plos:"
            ]
        ):
            continue

        if item not in outcomes:
            outcomes.append(item)

    return outcomes[:30]


def outcome_match_score(question, outcomes):
    if not outcomes:
        return 80.0

    scores = [overlap_score(question, outcome) for outcome in outcomes]

    if not scores:
        return 80.0

    best = max(scores)

    # Lenient but meaningful scoring.
    if best >= 60:
        return min(100, round(70 + (best - 60) * 0.75, 1))

    if best >= 35:
        return round(62 + (best - 35) * 0.32, 1)

    if best >= 15:
        return round(57 + (best - 15) * 0.25, 1)

    return 55.0


def best_outcome(question, outcomes):
    if not outcomes:
        return ""

    scored = [
        (overlap_score(question, outcome), outcome)
        for outcome in outcomes
    ]

    scored.sort(reverse=True, key=lambda x: x[0])
    return scored[0][1] if scored else ""


# ============================================================
# BLOOM'S TAXONOMY
# ============================================================

def detect_bloom(question):
    q = normalize(question)

    matches = []

    for level, verbs in BLOOM_VERBS.items():
        for verb in verbs:
            if re.search(r"\b" + re.escape(verb) + r"\b", q):
                matches.append((BLOOM_LEVELS[level], level, verb))

    if not matches:
        return "Understand", ""

    matches.sort(reverse=True)
    _, level, verb = matches[0]

    return level, verb


def bloom_score(question, target_bloom):
    actual, _ = detect_bloom(question)

    if not target_bloom:
        return 88.0

    target = None

    for level in BLOOM_LEVELS:
        if normalize(target_bloom).startswith(normalize(level)):
            target = level
            break

    if target is None:
        return 88.0

    difference = abs(
        BLOOM_LEVELS[actual] - BLOOM_LEVELS[target]
    )

    if difference == 0:
        return 100.0
    if difference == 1:
        return 91.0
    if difference == 2:
        return 83.0
    if difference == 3:
        return 77.0

    return 72.0


# ============================================================
# QUESTION TYPE DETECTION
# ============================================================

def detect_question_type(question):
    q = normalize(question)

    if re.search(r"\btrue\s*/?\s*false\b", q):
        return "True/False"

    if re.search(r"\btrue or false\b", q):
        return "True/False"

    # MCQ options
    option_patterns = [
        r"\b[A-D]\s*[\.\):]",
        r"\([A-D]\)",
        r"\boption\s+[A-D]\b",
    ]

    option_hits = sum(
        len(re.findall(pattern, question, flags=re.I))
        for pattern in option_patterns
    )

    if option_hits >= 2:
        return "MCQ"

    if re.search(r"\bfill\s+in\s+the\s+blank\b", q):
        return "Fill in the Blank"

    if "____" in question or "……" in question:
        return "Fill in the Blank"

    if "match the following" in q or "matching" in q:
        return "Matching"

    if any(
        word in q
        for word in [
            "case study",
            "case scenario",
            "read the case",
            "case and"
        ]
    ):
        return "Case Study"

    if any(
        word in q
        for word in [
            "calculate",
            "compute",
            "find the value",
            "solve for",
            "determine the value"
        ]
    ) and extract_numbers(question):
        return "Numerical"

    if any(
        word in q
        for word in [
            "perform",
            "demonstrate",
            "implement",
            "conduct",
            "carry out",
            "design an experiment",
            "practical"
        ]
    ):
        return "Practical/Application"

    word_count = len(question.split())

    if any(
        word in q
        for word in [
            "essay",
            "critically discuss",
            "write an essay",
            "write a detailed"
        ]
    ) or word_count > 55:
        return "Essay/Long Answer"

    if any(
        word in q
        for word in [
            "explain",
            "describe",
            "analyze",
            "analyse",
            "evaluate",
            "compare",
            "justify"
        ]
    ):
        return "Short/Constructed Response"

    return "Short Answer"


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def split_numbered_questions(text):
    text = clean_text(text)

    pattern = re.compile(
        r"(?:^|\n)\s*"
        r"(?:Q(?:uestion)?\s*)?"
        r"(\d{1,3})"
        r"\s*[\.\):\-]\s*",
        flags=re.I
    )

    matches = list(pattern.finditer(text))

    questions = []

    if matches:
        for i, match in enumerate(matches):
            start = match.end()

            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(text)

            content = text[start:end].strip()

            if len(content) >= 10:
                questions.append(content)

    return questions


def remove_instructional_noise(text):
    lines = text.splitlines()
    cleaned = []

    noise_patterns = [
        r"^\s*instructions?\s*:?",
        r"^\s*time\s*:",
        r"^\s*marks?\s*:",
        r"^\s*total\s+marks",
        r"^\s*section\s+[a-z]\s*$",
        r"^\s*name\s*:",
        r"^\s*roll\s*(no|number)?\s*:",
        r"^\s*date\s*:",
        r"^\s*course\s*:",
    ]

    for line in lines:
        skip = any(
            re.search(pattern, line, flags=re.I)
            for pattern in noise_patterns
        )

        if not skip:
            cleaned.append(line)

    return "\n".join(cleaned)


def extract_questions(text):
    text = clean_text(text)
    text = remove_instructional_noise(text)

    if not text:
        return []

    numbered = split_numbered_questions(text)

    if numbered:
        raw_questions = numbered
    else:
        paragraphs = [
            p.strip()
            for p in re.split(r"\n\s*\n+", text)
            if len(p.strip()) >= 12
        ]

        if paragraphs:
            raw_questions = paragraphs
        else:
            lines = [
                line.strip()
                for line in text.splitlines()
                if len(line.strip()) >= 15
            ]

            raw_questions = lines

    questions = []

    for q in raw_questions:
        q = clean_text(q)

        # Remove obvious headers
        if len(q) < 10:
            continue

        if q.lower() in {
            "answer all questions",
            "attempt all questions",
            "section a",
            "section b",
            "objective",
            "subjective",
        }:
            continue

        # Keep option content with MCQs.
        q = re.sub(r"\n{2,}", "\n", q)

        if q not in questions:
            questions.append(q)

    return questions[:100]


# ============================================================
# FILE READERS
# ============================================================

def read_pdf(uploaded_file):
    if fitz is None:
        return (
            "",
            "PyMuPDF is not installed. Add 'PyMuPDF' to requirements.txt."
        )

    try:
        data = uploaded_file.getvalue()
        document = fitz.open(stream=data, filetype="pdf")

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

        result = clean_text("\n".join(pages))

        if not result:
            return "", "The PDF was opened but no readable text was found."

        return result, ""

    except Exception as exc:
        return "", "Could not read PDF: " + str(exc)


def read_docx(uploaded_file):
    if Document is None:
        return "", "python-docx is not installed."

    try:
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

        return clean_text("\n".join(parts)), ""

    except Exception as exc:
        return "", "Could not read DOCX: " + str(exc)


def read_pptx(uploaded_file):
    if Presentation is None:
        return "", "python-pptx is not installed."

    try:
        presentation = Presentation(
            io.BytesIO(uploaded_file.getvalue())
        )

        parts = []

        for slide in presentation.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    if shape.text.strip():
                        parts.append(shape.text)

        return clean_text("\n".join(parts)), ""

    except Exception as exc:
        return "", "Could not read PPTX: " + str(exc)


def read_excel(uploaded_file):
    try:
        excel = pd.ExcelFile(
            io.BytesIO(uploaded_file.getvalue())
        )

        parts = []

        for sheet in excel.sheet_names:
            df = pd.read_excel(
                excel,
                sheet_name=sheet,
                header=None
            )

            parts.append("SHEET: " + str(sheet))

            for row in df.fillna("").astype(str).values:
                row_text = " | ".join(
                    cell.strip()
                    for cell in row
                    if cell.strip()
                )

                if row_text:
                    parts.append(row_text)

        return clean_text("\n".join(parts)), ""

    except Exception as exc:
        return "", "Could not read Excel file: " + str(exc)


def read_csv(uploaded_file):
    try:
        data = uploaded_file.getvalue()

        try:
            df = pd.read_csv(
                io.BytesIO(data),
                encoding="utf-8"
            )
        except Exception:
            df = pd.read_csv(
                io.BytesIO(data),
                encoding="latin1"
            )

        return clean_text(
            df.fillna("").astype(str).to_csv(
                index=False
            )
        ), ""

    except Exception as exc:
        return "", "Could not read CSV: " + str(exc)


def read_text_file(uploaded_file):
    try:
        data = uploaded_file.getvalue()

        try:
            text = data.decode("utf-8")
        except Exception:
            text = data.decode("latin1", errors="ignore")

        return clean_text(text), ""

    except Exception as exc:
        return "", "Could not read text file: " + str(exc)


def read_image(uploaded_file):
    if Image is None:
        return "", "Pillow is not installed."

    if pytesseract is None:
        return "", (
            "OCR is not available. Add 'pytesseract' to "
            "requirements.txt and make sure Tesseract is available."
        )

    try:
        image = Image.open(
            io.BytesIO(uploaded_file.getvalue())
        )

        text = pytesseract.image_to_string(image)

        return clean_text(text), ""

    except Exception as exc:
        return "", "Could not read image: " + str(exc)


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
        (".txt", ".md", ".text")
    ):
        return read_text_file(uploaded_file)

    if name.endswith(
        (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")
    ):
        return read_image(uploaded_file)

    return "", (
        "Unsupported file type. Use PDF, DOCX, PPTX, "
        "XLSX, XLS, CSV, TXT, MD, or an image."
    )


# ============================================================
# QUESTION QUALITY METRICS
# ============================================================

def clarity_score(question):
    q = normalize(question)

    score = 98.0

    for phrase in GENERIC_VAGUE_PHRASES:
        if phrase in q:
            score -= 10

    if "??" in question:
        score -= 3

    if len(question.split()) > 100:
        score -= 5

    if len(question.split()) < 4:
        score -= 2

    # Double negatives
    negative_hits = len(
        re.findall(
            r"\bnot\b|\bnever\b|\bno\b",
            q
        )
    )

    if negative_hits >= 2:
        score -= 6

    # Extremely fragmented text
    if question.count("...") >= 2:
        score -= 5

    return max(45.0, min(100.0, round(score, 1)))


def measurability_score(question, question_type):
    q = normalize(question)

    if question_type in {
        "MCQ",
        "True/False",
        "Fill in the Blank",
        "Matching",
        "Numerical"
    }:
        score = 96.0
    else:
        score = 92.0

    if any(
        phrase in q
        for phrase in GENERIC_VAGUE_PHRASES
    ):
        score -= 12

    if question_type in {
        "Essay/Long Answer",
        "Short/Constructed Response"
    }:
        if any(
            word in q
            for word in [
                "explain",
                "analyze",
                "analyse",
                "evaluate",
                "compare",
                "justify",
                "describe",
                "discuss"
            ]
        ):
            score += 3

    return max(50.0, min(100.0, round(score, 1)))


def relevance_score(
    question,
    clo_score,
    plo_score,
    outcomes
):
    if not outcomes:
        return 88.0

    average = (
        0.60 * clo_score +
        0.40 * plo_score
    )

    return round(
        max(60.0, min(100.0, average)),
        1
    )


# ============================================================
# EVALUATE ONE QUESTION
# ============================================================

def evaluate_question(
    question,
    clos,
    plos,
    target_bloom=""
):
    q_type = detect_question_type(question)

    actual_bloom, bloom_verb = detect_bloom(question)

    clo_score = outcome_match_score(
        question,
        clos
    )

    plo_score = outcome_match_score(
        question,
        plos
    )

    b_score = bloom_score(
        question,
        target_bloom
    )

    c_score = clarity_score(question)

    m_score = measurability_score(
        question,
        q_type
    )

    r_score = relevance_score(
        question,
        clo_score,
        plo_score,
        clos + plos
    )

    overall = (
        0.20 * clo_score +
        0.15 * plo_score +
        0.20 * b_score +
        0.15 * r_score +
        0.15 * c_score +
        0.15 * m_score
    )

    overall = round(
        max(0.0, min(100.0, overall)),
        1
    )

    return {
        "question": question,
        "type": q_type,
        "clo": clo_score,
        "plo": plo_score,
        "bloom": b_score,
        "relevance": r_score,
        "clarity": c_score,
        "measurability": m_score,
        "overall": overall,
        "actual_bloom": actual_bloom,
        "bloom_verb": bloom_verb,
        "best_clo": best_outcome(question, clos),
        "best_plo": best_outcome(question, plos),
    }


def analyze_questions(
    questions,
    clos,
    plos,
    target_bloom=""
):
    results = []

    for index, question in enumerate(questions):
        result = evaluate_question(
            question,
            clos,
            plos,
            target_bloom
        )

        result["index"] = index
        results.append(result)

    return results


def calculate_overall_score(analysis):
    if not analysis:
        return 0.0

    scores = [
        item["overall"]
        for item in analysis
        if isinstance(item.get("overall"), (int, float))
    ]

    if not scores:
        return 0.0

    return round(
        sum(scores) / len(scores),
        1
    )


# ============================================================
# SCORE STATUS
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
# REVISION ENGINE
# ============================================================

def strongest_problem(result):
    metrics = {
        "CLO alignment": result["clo"],
        "PLO alignment": result["plo"],
        "Bloom's level": result["bloom"],
        "Relevance": result["relevance"],
        "Clarity": result["clarity"],
        "Measurability": result["measurability"],
    }

    weakest = min(
        metrics,
        key=metrics.get
    )

    return weakest, metrics[weakest]


def explain_problem(
    result,
    question,
    target_bloom
):
    problem, score = strongest_problem(result)

    actual = result["actual_bloom"]

    if problem == "CLO alignment":
        if result["best_clo"]:
            return (
                "CLO alignment",
                "The question only partially addresses the stated "
                "course learning outcome. The revision should make "
                "the task explicitly demonstrate the skill or content "
                "required by the CLO."
            )

        return (
            "CLO alignment",
            "The question does not contain enough evidence of the "
            "stated course learning outcome. The revision should "
            "connect the existing task more directly to the outcome."
        )

    if problem == "PLO alignment":
        return (
            "PLO alignment",
            "The question provides limited evidence of the selected "
            "program learning outcome. The revision should strengthen "
            "the observable skill without changing the subject."
        )

    if problem == "Bloom's level":
        return (
            "Bloom's level",
            "The question currently asks students to perform a "
            f"{actual.lower()}-level task, while the intended Bloom's "
            f"level is {target_bloom or 'higher-order'}."
        )

    if problem == "Clarity":
        return (
            "Clarity",
            "The wording is vague, overly broad, fragmented, or "
            "contains wording that makes the expected response "
            "unclear."
        )

    if problem == "Measurability":
        return (
            "Measurability",
            "The question does not make the expected student "
            "performance sufficiently observable or assessable."
        )

    return (
        "Relevance",
        "The connection between the question and the stated "
        "learning outcomes is weaker than the rest of the assessment."
    )


def preserve_options(question):
    options = re.findall(
        r"(?im)^\s*(?:\(?[A-Da-d]\)?)[\.\):\-]\s*.+$",
        question
    )

    return options


def remove_options_from_stem(question):
    lines = question.splitlines()

    kept = []

    for line in lines:
        if re.match(
            r"^\s*(?:\(?[A-Da-d]\)?)[\.\):\-]\s*.+$",
            line
        ):
            continue

        kept.append(line)

    return "\n".join(kept).strip()


def preserve_technical_content(original, revised):
    original_tokens = extract_technical_tokens(original)
    revised_text = revised

    missing = []

    for token in original_tokens:
        if token.lower() not in revised_text.lower():
            missing.append(token)

    if missing:
        return False

    return True


def preserve_mcq_options(original, revised):
    original_options = preserve_options(original)

    if not original_options:
        return True

    for option in original_options:
        option_content = re.sub(
            r"^\s*(?:\(?[A-Da-d]\)?)[\.\):\-]\s*",
            "",
            option
        ).strip()

        if option_content.lower() not in revised.lower():
            return False

    return True


def safe_add_sentence(question, sentence):
    question = question.strip()

    if question.endswith("."):
        return question + " " + sentence

    return question + ". " + sentence


# ------------------------------------------------------------
# Revision generators
# ------------------------------------------------------------

def revise_clo(
    question,
    result,
    clo,
    question_type
):
    if not clo:
        return None

    clo_norm = normalize(clo)
    q_norm = normalize(question)

    missing_keywords = [
        word
        for word in tokenize(clo)
        if word not in keyword_set(question)
    ]

    if not missing_keywords:
        return None

    if question_type == "Numerical":
        revised = safe_add_sentence(
            question,
            "Show the calculation steps and explain what the result "
            "means in the context of the problem"
        )
        return revised

    if question_type == "MCQ":
        stem = remove_options_from_stem(question)

        # Only modify the stem. Options remain unchanged.
        if "what is" in q_norm:
            stem = re.sub(
                r"\bwhat\s+is\b",
                "Which statement best explains",
                stem,
                flags=re.I
            )

        revised = stem.strip()

        return revised + "\n" + "\n".join(
            preserve_options(question)
        )

    if question_type == "True/False":
        return question

    if question_type == "Fill in the Blank":
        return question

    # Use wording from the CLO only when it can be connected naturally.
    if any(
        word in clo_norm
        for word in [
            "importance",
            "significance",
            "effects",
            "impact",
            "causes",
            "factors",
            "applications"
        ]
    ):
        clause_words = []

        for phrase in [
            "importance",
            "significance",
            "effects",
            "impact",
            "causes",
            "factors",
            "applications"
        ]:
            if phrase in clo_norm:
                clause_words.append(phrase)

        if clause_words:
            phrase = clause_words[0]

            return (
                question.rstrip("?.!") +
                f" and explain the {phrase} identified in the "
                "course learning outcome."
            )

    # Safer general revision: make existing content explicitly connect
    # to the CLO without inventing technical facts.
    return (
        question.rstrip("?.!") +
        ", explaining how it relates to the stated course learning outcome."
    )


def revise_bloom(
    question,
    result,
    target_bloom,
    question_type
):
    if not target_bloom:
        return None

    actual = result["actual_bloom"]

    target_level = None

    for level in BLOOM_LEVELS:
        if normalize(target_bloom).startswith(
            normalize(level)
        ):
            target_level = level
            break

    if not target_level:
        return None

    if BLOOM_LEVELS[actual] >= BLOOM_LEVELS[target_level]:
        return None

    # Numerical
    if question_type == "Numerical":
        return safe_add_sentence(
            question,
            "show the calculation steps and explain the meaning "
            "of the final result"
        )

    # MCQ
    if question_type == "MCQ":
        stem = remove_options_from_stem(question)

        if target_level == "Analyze":
            stem = (
                "Which option best explains the result or relationship "
                "described in the question?\n" + stem
            )

        elif target_level == "Evaluate":
            stem = (
                "Which option provides the best-supported judgment "
                "based on the information given?\n" + stem
            )

        else:
            stem = stem.rstrip("?.!") + (
                " and explain the reason for your answer"
            )

        return stem + "\n" + "\n".join(
            preserve_options(question)
        )

    # True/False
    if question_type == "True/False":
        return (
            question.rstrip("?.!") +
            " and justify your answer with one relevant reason."
        )

    # Essay
    if question_type == "Essay/Long Answer":
        if target_level == "Evaluate":
            return (
                question.rstrip("?.!") +
                ", evaluate the issue using relevant evidence and "
                "justify your conclusion."
            )

        if target_level == "Analyze":
            return (
                question.rstrip("?.!") +
                ", analyze the main factors or relationships involved "
                "and explain how they contribute to the issue."
            )

    # Short answer
    if target_level == "Analyze":
        return (
            question.rstrip("?.!") +
            ", analyze the relevant factors or relationships involved."
        )

    if target_level == "Evaluate":
        return (
            question.rstrip("?.!") +
            ", evaluate the issue and justify your conclusion."
        )

    if target_level == "Create":
        return (
            question.rstrip("?.!") +
            " and propose an appropriate solution or approach."
        )

    if target_level == "Apply":
        return (
            question.rstrip("?.!") +
            " and demonstrate how the concept would be applied "
            "to the situation described."
        )

    return None


def revise_clarity(
    question,
    result,
    question_type
):
    q = question.strip()

    # Don't make good questions longer.
    if result["clarity"] >= 85:
        return None

    if question_type == "Numerical":
        return safe_add_sentence(
            q,
            "show the calculation steps and state the final answer "
            "with the appropriate unit"
        )

    if question_type == "True/False":
        q = re.sub(
            r"\bnot\s+untrue\b",
            "true",
            q,
            flags=re.I
        )

        q = re.sub(
            r"\bnot\s+unlikely\b",
            "likely",
            q,
            flags=re.I
        )

        return q

    # Replace broad phrases with a more measurable task.
    replacements = [
        (
            r"\bdiscuss\s+this\b",
            "Explain the main points of the issue"
        ),
        (
            r"\bdiscuss\s+the\s+topic\b",
            "Explain the main aspects of the topic"
        ),
        (
            r"\bwrite\s+about\b",
            "Explain"
        ),
        (
            r"\bcomment\s+on\b",
            "Explain and evaluate"
        ),
        (
            r"\bgive\s+details\s+about\b",
            "Describe the main features of"
        ),
        (
            r"\belaborate\s+on\b",
            "Explain"
        ),
    ]

    revised = q

    for pattern, replacement in replacements:
        revised = re.sub(
            pattern,
            replacement,
            revised,
            flags=re.I
        )

    if revised != q:
        return revised

    return (
        q.rstrip("?.!") +
        " Clearly state the main point and support your response "
        "with relevant evidence or explanation."
    )


def revise_measurability(
    question,
    result,
    question_type
):
    if result["measurability"] >= 85:
        return None

    if question_type == "Numerical":
        return safe_add_sentence(
            question,
            "show the calculation steps and state the final answer "
            "with the appropriate unit"
        )

    if question_type == "Essay/Long Answer":
        return (
            question.rstrip("?.!") +
            " Support your response with relevant evidence and "
            "a clear conclusion."
        )

    if question_type == "Short/Constructed Response":
        return (
            question.rstrip("?.!") +
            " Support your answer with relevant evidence or explanation."
        )

    if question_type == "Practical/Application":
        return (
            question.rstrip("?.!") +
            " Clearly state the procedure followed and the expected result."
        )

    return None


def validate_revision(
    original,
    revised,
    question_type
):
    if not revised:
        return False

    revised = revised.strip()

    if len(revised) < 10:
        return False

    # Must retain original technical information.
    if not preserve_technical_content(
        original,
        revised
    ):
        return False

    # MCQ options must survive unchanged.
    if question_type == "MCQ":
        if not preserve_mcq_options(
            original,
            revised
        ):
            return False

    # Don't accept a revision that is effectively identical.
    if normalize(original) == normalize(revised):
        return False

    return True


def score_revision(
    revised,
    original_result,
    clos,
    plos,
    target_bloom
):
    return evaluate_question(
        revised,
        clos,
        plos,
        target_bloom
    )


def generate_revision(
    question,
    result,
    clos,
    plos,
    target_bloom
):
    question_type = result["type"]

    problem, problem_score = strongest_problem(result)

    best_clo = result.get("best_clo", "")

    candidates = []

    # --------------------------------------------------------
    # Candidate 1: CLO
    # --------------------------------------------------------
    if problem == "CLO alignment":
        candidate = revise_clo(
            question,
            result,
            best_clo,
            question_type
        )

        if candidate:
            candidates.append(
                (
                    candidate,
                    "CLO alignment",
                    "The revision connects the existing question "
                    "more directly to the stated CLO."
                )
            )

    # --------------------------------------------------------
    # Candidate 2: Bloom
    # --------------------------------------------------------
    if problem == "Bloom's level":
        candidate = revise_bloom(
            question,
            result,
            target_bloom,
            question_type
        )

        if candidate:
            candidates.append(
                (
                    candidate,
                    "Bloom's level",
                    "The revision changes the cognitive task while "
                    "keeping the original subject and content."
                )
            )

    # --------------------------------------------------------
    # Candidate 3: clarity
    # --------------------------------------------------------
    if problem == "Clarity":
        candidate = revise_clarity(
            question,
            result,
            question_type
        )

        if candidate:
            candidates.append(
                (
                    candidate,
                    "Clarity",
                    "The revision makes the expected response "
                    "more explicit without changing the topic."
                )
            )

    # --------------------------------------------------------
    # Candidate 4: measurability
    # --------------------------------------------------------
    if problem == "Measurability":
        candidate = revise_measurability(
            question,
            result,
            question_type
        )

        if candidate:
            candidates.append(
                (
                    candidate,
                    "Measurability",
                    "The revision makes the student's expected "
                    "performance more observable and assessable."
                )
            )

    # --------------------------------------------------------
    # If primary problem didn't create a candidate, try all.
    # --------------------------------------------------------
    if not candidates:
        candidate_generators = [
            (
                revise_clo,
                "CLO alignment"
            ),
            (
                revise_bloom,
                "Bloom's level"
            ),
            (
                revise_clarity,
                "Clarity"
            ),
            (
                revise_measurability,
                "Measurability"
            ),
        ]

        for generator, label in candidate_generators:
            if label == "CLO alignment":
                candidate = generator(
                    question,
                    result,
                    best_clo,
                    question_type
                )
            elif label == "Bloom's level":
                candidate = generator(
                    question,
                    result,
                    target_bloom,
                    question_type
                )
            else:
                candidate = generator(
                    question,
                    result,
                    question_type
                )

            if candidate:
                candidates.append(
                    (
                        candidate,
                        label,
                        "The revision addresses a specific "
                        "alignment weakness identified by the tool."
                    )
                )

    valid_candidates = []

    for candidate, area, explanation in candidates:
        if not validate_revision(
            question,
            candidate,
            question_type
        ):
            continue

        revised_result = score_revision(
            candidate,
            result,
            clos,
            plos,
            target_bloom
        )

        improvement = (
            revised_result["overall"] -
            result["overall"]
        )

        # Accept only logical improvements.
        if improvement >= 2:
            valid_candidates.append(
                {
                    "revision": candidate,
                    "area": area,
                    "why": explanation,
                    "before": result["overall"],
                    "after": revised_result["overall"],
                    "improvement": round(improvement, 1),
                    "analysis": revised_result,
                }
            )

    if not valid_candidates:
        return {
            "available": False,
            "area": problem,
            "why": (
                "The tool did not identify a safe wording change "
                "that would improve the score while preserving the "
                "original subject and technical content."
            ),
            "original": question,
        }

    valid_candidates.sort(
        key=lambda x: x["improvement"],
        reverse=True
    )

    return {
        "available": True,
        "candidates": valid_candidates[:3],
        "original": question,
    }


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.4rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
    }

    .subtle {
        color: #666;
        font-size: 1rem;
    }

    .revision-box {
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid #d9d9d9;
        margin-bottom: 1rem;
        background: #fafafa;
    }

    .question-number {
        font-size: 1.15rem;
        font-weight: 750;
    }

    .revision-label {
        font-weight: 700;
        margin-top: 0.5rem;
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
        "Check assessment questions for CLO, PLO, Bloom's Taxonomy, "
        "clarity, relevance, and measurability."
    )

    st.divider()

    st.subheader("Assessment Settings")

    target_bloom = st.selectbox(
        "Target Bloom's Level",
        [
            "Not specified",
            "Remember",
            "Understand",
            "Apply",
            "Analyze",
            "Evaluate",
            "Create",
        ]
    )

    if target_bloom == "Not specified":
        target_bloom = ""

    st.divider()

    st.caption(
        "The checker is subject-independent and can evaluate "
        "different assessment formats."
    )


# ============================================================
# MAIN HEADER
# ============================================================

st.title("🎓 OBE Quiz Checker")

st.write(
    "Check your assessment questions for CLO, PLO, Bloom's Taxonomy, "
    "clarity, relevance, and measurability — and improve weak "
    "questions with practical, context-preserving revisions."
)


# ============================================================
# 1. ASSESSMENT INFORMATION
# ============================================================

st.header("1. 📋 Assessment Information")

col1, col2 = st.columns(2)

with col1:
    course_name = st.text_input(
        "Course Name",
        placeholder="e.g., Biology, Programming Fundamentals, English I"
    )

with col2:
    assessment_name = st.text_input(
        "Assessment Name",
        placeholder="e.g., Quiz 1, Midterm, Assignment 2"
    )


# ============================================================
# 2. LEARNING OUTCOMES
# ============================================================

st.header("2. 🎯 Learning Outcomes")

clo_text = st.text_area(
    "Course Learning Outcomes (CLOs)",
    placeholder=(
        "Enter one or more CLOs.\n\n"
        "CLO1: Explain the major concepts of the subject.\n"
        "CLO2: Apply relevant concepts to practical situations."
    ),
    height=150
)

plo_text = st.text_area(
    "Program Learning Outcomes (PLOs)",
    placeholder=(
        "Enter one or more PLOs.\n\n"
        "PLO1: Apply knowledge to solve problems.\n"
        "PLO2: Communicate effectively."
    ),
    height=150
)

clos = parse_outcomes(clo_text)
plos = parse_outcomes(plo_text)

if clos:
    st.success(
        f"Detected {len(clos)} CLO(s)."
    )

if plos:
    st.success(
        f"Detected {len(plos)} PLO(s)."
    )


# ============================================================
# 3. UPLOAD
# ============================================================

st.header("3. 📄 Upload Complete Assessment")

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
        "tiff",
    ]
)

if uploaded_file is not None:
    if st.button(
        "📖 Read Assessment",
        use_container_width=True
    ):
        with st.spinner("Reading assessment..."):
            text, error = read_uploaded_file(
                uploaded_file
            )

        if error:
            st.error(error)
        else:
            questions = extract_questions(text)

            st.session_state.uploaded_text = text
            st.session_state.questions = questions
            st.session_state.analysis = []
            st.session_state.analyzed = False
            st.session_state.selected_question = None
            st.session_state.revision_candidates = {}
            st.session_state.accepted_revisions = {}
            st.session_state.last_overall_score = None
            st.session_state.balloons_shown = False

            if questions:
                st.success(
                    f"Assessment read successfully. "
                    f"{len(questions)} question(s) detected."
                )
            else:
                st.warning(
                    "The file was read, but no questions could be "
                    "identified automatically."
                )


# ============================================================
# SHOW EXTRACTED QUESTIONS
# ============================================================

if st.session_state.questions:
    with st.expander(
        "👁️ View Extracted Questions",
        expanded=False
    ):
        for i, question in enumerate(
            st.session_state.questions,
            start=1
        ):
            st.markdown(
                f"**Question {i}**"
            )
            st.write(question)
            st.divider()


# ============================================================
# 4. ANALYZE
# ============================================================

st.header("4. 🔍 Analyze Assessment")

if st.session_state.questions:

    if st.button(
        "🚀 Analyze Assessment",
        type="primary",
        use_container_width=True
    ):
        with st.spinner(
            "Evaluating every question independently..."
        ):
            st.session_state.analysis = analyze_questions(
                st.session_state.questions,
                clos,
                plos,
                target_bloom
            )

        st.session_state.analyzed = True
        st.session_state.selected_question = None
        st.session_state.revision_candidates = {}

        calculated_score = calculate_overall_score(
            st.session_state.analysis
        )

        st.session_state.last_overall_score = calculated_score
        st.session_state.balloons_shown = False

        st.success(
            "Assessment analysis completed."
        )

else:
    st.info(
        "Upload and read an assessment before analyzing it."
    )


# ============================================================
# ANALYSIS START
# ============================================================

if st.session_state.analyzed and st.session_state.analysis:

    analysis = st.session_state.analysis

    calculated_score = calculate_overall_score(
        analysis
    )

    # ========================================================
    # 5. OVERALL ALIGNMENT
    # ========================================================

    st.header("5. 📊 Overall Alignment")

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric(
        "Overall Score",
        f"{calculated_score:.1f}%"
    )

    strong_count = sum(
        1
        for item in analysis
        if item["overall"] >= 85
    )

    attained_count = sum(
        1
        for item in analysis
        if 75 <= item["overall"] < 85
    )

    revision_count = sum(
        1
        for item in analysis
        if item["overall"] < 75
    )

    metric2.metric(
        "🟢 Strong",
        strong_count
    )

    metric3.metric(
        "🏆 Attained",
        attained_count
    )

    metric4.metric(
        "🔧 Needs Revision",
        revision_count
    )


    # ========================================================
    # 6. SCORE ANALYSIS
    # ========================================================

    st.header("6. 🎯 Assessment Score Analysis")

    st.metric(
        "Actual Calculated Assessment Score",
        f"{calculated_score:.1f}%"
    )

    if calculated_score >= 80:
        if not st.session_state.balloons_shown:
            st.balloons()
            st.session_state.balloons_shown = True

        st.success(
            f"🎉 Congratulations! Your assessment achieved "
            f"{calculated_score:.1f}%, which is 80% or above."
        )

        st.write(
            "The assessment demonstrates strong overall alignment "
            "across learning outcomes, cognitive level, relevance, "
            "clarity, and measurability."
        )

    elif calculated_score >= 75:
        st.success(
            f"🏆 Your assessment achieved {calculated_score:.1f}%."
        )

        st.write(
            "The assessment has reached the attainment level. "
            "Targeted revisions can further strengthen weaker questions."
        )

    elif calculated_score >= 65:
        st.warning(
            f"🔧 Your assessment achieved {calculated_score:.1f}%."
        )

        st.write(
            "The assessment shows reasonable alignment, but some "
            "questions should be strengthened."
        )

    else:
        st.error(
            f"🛠️ Your assessment achieved {calculated_score:.1f}%."
        )

        st.write(
            "Several questions require improvement. Start with "
            "the questions listed in the revision section below."
        )


    # ========================================================
    # 7. REVISION LIST AT TOP
    # ========================================================

    st.header("7. 🔧 Questions Requiring Revision")

    revision_items = [
        (i, item)
        for i, item in enumerate(analysis)
        if item["overall"] < 75
    ]

    if not revision_items:
        st.success(
            "🎉 No questions currently require revision. "
            "All questions have reached 75% or above."
        )

    else:

        st.info(
            "The tool automatically identifies the specific weakness "
            "and writes a practical revision. You do not need to "
            "rewrite the question yourself."
        )

        for i, item in revision_items:

            st.markdown(
                f"### Question {i + 1} — {item['overall']:.1f}%"
            )

            status = status_for_score(
                item["overall"]
            )

            st.caption(
                f"{status}  •  {item['type']}  •  "
                f"Detected Bloom's level: {item['actual_bloom']}"
            )

            problem, problem_score = strongest_problem(item)

            problem_title, problem_explanation = explain_problem(
                item,
                item["question"],
                target_bloom
            )

            st.markdown(
                f"**Problem Identified:** {problem_title}"
            )

            st.write(
                problem_explanation
            )

            st.markdown("**Original Question**")

            st.info(
                item["question"]
            )

            revision_key = f"revision_{i}"

            if revision_key not in st.session_state.revision_candidates:

                revision = generate_revision(
                    item["question"],
                    item,
                    clos,
                    plos,
                    target_bloom
                )

                st.session_state.revision_candidates[
                    revision_key
                ] = revision

            revision = st.session_state.revision_candidates[
                revision_key
            ]

            if revision.get("available"):

                candidates = revision["candidates"]

                for candidate_index, candidate in enumerate(
                    candidates
                ):

                    st.markdown(
                        f"**Practical Revision "
                        f"{candidate_index + 1}**"
                    )

                    st.success(
                        candidate["revision"]
                    )

                    st.markdown(
                        "**Why this revision?**"
                    )

                    st.write(
                        candidate["why"]
                    )

                    before_score = candidate["before"]
                    after_score = candidate["after"]
                    improvement = candidate["improvement"]

                    st.write(
                        f"**Score:** "
                        f"{before_score:.1f}% → "
                        f"**{after_score:.1f}%** "
                        f"(+{improvement:.1f})"
                    )

                    button_key = (
                        f"use_revision_{i}_{candidate_index}"
                    )

                    if st.button(
                        "✅ Use This Revision",
                        key=button_key,
                        use_container_width=True
                    ):
                        old_question = item["question"]

                        new_question = candidate[
                            "revision"
                        ]

                        st.session_state.questions[
                            i
                        ] = new_question

                        # Recalculate the complete assessment.
                        new_analysis = analyze_questions(
                            st.session_state.questions,
                            clos,
                            plos,
                            target_bloom
                        )

                        st.session_state.analysis = new_analysis

                        new_overall = calculate_overall_score(
                            new_analysis
                        )

                        st.session_state.last_overall_score = (
                            new_overall
                        )

                        st.session_state.accepted_revisions[
                            i
                        ] = {
                            "old": old_question,
                            "new": new_question,
                            "old_score": item["overall"],
                            "new_score": new_analysis[i]["overall"],
                        }

                        # Clear stale revision candidates.
                        st.session_state.revision_candidates = {}

                        st.success(
                            f"Revision applied successfully: "
                            f"{item['overall']:.1f}% → "
                            f"{new_analysis[i]['overall']:.1f}%"
                        )

                        if new_analysis[i]["overall"] >= 75:
                            st.balloons()

                        st.rerun()

                    st.divider()

            else:
                st.warning(
                    "Keep Current Question — the tool did not find "
                    "a safe automatic wording change that would "
                    "improve the score without changing the original "
                    "subject or technical content."
                )

            st.divider()


    # ========================================================
    # 8. ATTAINED QUESTIONS
    # ========================================================

    st.header("8. 🏆 Attained Questions")

    attained = [
        (i, item)
        for i, item in enumerate(analysis)
        if item["overall"] >= 75
    ]

    if attained:

        for i, item in attained:
            st.success(
                f"Question {i + 1} — "
                f"{item['overall']:.1f}% — 🏆 Attained"
            )

            with st.expander(
                f"View Question {i + 1}"
            ):
                st.write(
                    item["question"]
                )

                cols = st.columns(6)

                cols[0].metric(
                    "CLO",
                    f"{item['clo']:.0f}%"
                )

                cols[1].metric(
                    "PLO",
                    f"{item['plo']:.0f}%"
                )

                cols[2].metric(
                    "Bloom",
                    f"{item['bloom']:.0f}%"
                )

                cols[3].metric(
                    "Relevance",
                    f"{item['relevance']:.0f}%"
                )

                cols[4].metric(
                    "Clarity",
                    f"{item['clarity']:.0f}%"
                )

                cols[5].metric(
                    "Measurability",
                    f"{item['measurability']:.0f}%"
                )

    else:
        st.info(
            "No questions have reached 75% yet."
        )


    # ========================================================
    # 9. ALIGNMENT OVERVIEW — ONLY GRAPH
    # ========================================================

    st.header("9. 📈 Alignment Overview")

    chart_data = pd.DataFrame(
        {
            "Question": [
                f"Q{i + 1}"
                for i in range(len(analysis))
            ],
            "Overall Alignment": [
                item["overall"]
                for item in analysis
            ],
        }
    )

    st.bar_chart(
        chart_data.set_index("Question")
    )


    # ========================================================
    # 10. QUESTION OVERVIEW
    # ========================================================

    st.header("10. 📋 Question Overview")

    overview_rows = []

    for i, item in enumerate(analysis):
        overview_rows.append(
            {
                "Question": f"Q{i + 1}",
                "Type": item["type"],
                "CLO Match": round(item["clo"], 1),
                "PLO Match": round(item["plo"], 1),
                "Bloom": round(item["bloom"], 1),
                "Relevance": round(item["relevance"], 1),
                "Clarity": round(item["clarity"], 1),
                "Measurability": round(item["measurability"], 1),
                "Overall": round(item["overall"], 1),
                "Status": status_for_score(
                    item["overall"]
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
    # 11. DETAILED QUESTION INSPECTION
    # ========================================================

    st.header("11. 🔎 Detailed Question Analysis")

    question_options = [
        f"Question {i + 1}"
        for i in range(len(analysis))
    ]

    selected_label = st.selectbox(
        "Select a question to inspect",
        question_options
    )

    selected_index = (
        question_options.index(
            selected_label
        )
    )

    selected = analysis[selected_index]

    st.subheader(
        f"{selected_label} — "
        f"{selected['overall']:.1f}%"
    )

    st.write(
        selected["question"]
    )

    detail_cols = st.columns(6)

    detail_cols[0].metric(
        "CLO",
        f"{selected['clo']:.1f}%"
    )

    detail_cols[1].metric(
        "PLO",
        f"{selected['plo']:.1f}%"
    )

    detail_cols[2].metric(
        "Bloom",
        f"{selected['bloom']:.1f}%"
    )

    detail_cols[3].metric(
        "Relevance",
        f"{selected['relevance']:.1f}%"
    )

    detail_cols[4].metric(
        "Clarity",
        f"{selected['clarity']:.1f}%"
    )

    detail_cols[5].metric(
        "Measurability",
        f"{selected['measurability']:.1f}%"
    )

    st.write(
        f"**Question Type:** {selected['type']}"
    )

    st.write(
        f"**Detected Bloom's Level:** "
        f"{selected['actual_bloom']}"
    )

    if selected["bloom_verb"]:
        st.write(
            f"**Detected Action Verb:** "
            f"{selected['bloom_verb']}"
        )

    if selected["best_clo"]:
        st.write(
            f"**Closest CLO:** {selected['best_clo']}"
        )

    if selected["best_plo"]:
        st.write(
            f"**Closest PLO:** {selected['best_plo']}"
        )


    # ========================================================
    # 12. WORKSHOP SUMMARY
    # ========================================================

    st.header("12. 🧑‍🏫 Workshop Summary")

    summary_cols = st.columns(4)

    summary_cols[0].metric(
        "Questions",
        len(analysis)
    )

    summary_cols[1].metric(
        "Overall Score",
        f"{calculated_score:.1f}%"
    )

    summary_cols[2].metric(
        "Attained",
        attained_count
    )

    summary_cols[3].metric(
        "Revisions Needed",
        revision_count
    )

    st.write(
        "Use the revision list at the top to identify weak questions. "
        "Each revision is generated from the actual wording, learning "
        "outcomes, question type, and detected cognitive level."
    )


    # ========================================================
    # 13. EXPORT
    # ========================================================

    st.header("13. 📥 Export Results")

    export_rows = []

    for i, item in enumerate(
        st.session_state.analysis
    ):
        accepted = st.session_state.accepted_revisions.get(
            i
        )

        export_rows.append(
            {
                "Question Number": i + 1,
                "Question Type": item["type"],
                "Current Question": item["question"],
                "CLO Match": item["clo"],
                "PLO Match": item["plo"],
                "Bloom Score": item["bloom"],
                "Relevance": item["relevance"],
                "Clarity": item["clarity"],
                "Measurability": item["measurability"],
                "Overall Score": item["overall"],
                "Status": status_for_score(
                    item["overall"]
                ),
                "Detected Bloom": item["actual_bloom"],
                "Accepted Revision": (
                    accepted["new"]
                    if accepted
                    else ""
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
        "📥 Download OBE Quiz Checker Report",
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
    "OBE Quiz Checker • Subject-independent assessment analysis "
    "and practical question revision"
)
