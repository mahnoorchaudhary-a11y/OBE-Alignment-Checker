import io
import re
import textwrap
from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

try:
    import pypdf
except Exception:
    pypdf = None

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    from docx import Document
except Exception:
    Document = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from pdf2image import convert_from_bytes
except Exception:
    convert_from_bytes = None


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Quality & Alignment Checker",
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

BLOOM_RANK = {
    "Remember": 1,
    "Understand": 2,
    "Apply": 3,
    "Analyze": 4,
    "Evaluate": 5,
    "Create": 6
}

BLOOM_VERBS = {
    "Remember": [
        "define", "list", "name", "identify", "state", "recall",
        "recognize", "label", "select", "match", "mention"
    ],
    "Understand": [
        "explain", "describe", "summarize", "interpret", "classify",
        "discuss", "illustrate", "paraphrase", "translate", "compare"
    ],
    "Apply": [
        "apply", "calculate", "solve", "use", "demonstrate",
        "implement", "execute", "determine", "show", "compute"
    ],
    "Analyze": [
        "analyze", "analyse", "differentiate", "distinguish",
        "examine", "organize", "compare", "contrast", "categorize",
        "investigate", "break down", "infer"
    ],
    "Evaluate": [
        "evaluate", "assess", "judge", "justify", "critique",
        "defend", "argue", "validate", "appraise", "recommend"
    ],
    "Create": [
        "create", "design", "develop", "construct", "formulate",
        "produce", "generate", "plan", "propose", "compose"
    ]
}

STOP_WORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on",
    "for", "with", "by", "from", "at", "is", "are", "was",
    "were", "be", "been", "being", "as", "that", "this",
    "these", "those", "it", "its", "their", "they", "them",
    "he", "she", "his", "her", "you", "your", "we", "our",
    "what", "which", "who", "whom", "when", "where", "why",
    "how", "does", "do", "did", "can", "could", "should",
    "would", "will", "may", "might", "than", "into", "about",
    "through", "during", "using", "used", "use", "following",
    "given", "based", "question", "questions"
}

QUESTION_STARTERS = [
    "identify", "define", "state", "list", "name", "explain",
    "describe", "summarize", "discuss", "analyze", "analyse",
    "compare", "contrast", "differentiate", "distinguish",
    "evaluate", "assess", "justify", "examine", "interpret",
    "apply", "calculate", "determine", "solve", "demonstrate",
    "illustrate", "classify", "select", "choose", "write",
    "rewrite", "paraphrase", "develop", "design", "create",
    "formulate", "construct", "produce", "generate", "propose",
    "what", "which", "why", "how", "when", "where", "who",
    "whose", "is", "are", "was", "were"
]


# ============================================================
# GENERAL TEXT UTILITIES
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\x00", " ")
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_text(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def tokenize(text):
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]*", str(text).lower())

    return [
        w for w in words
        if w not in STOP_WORDS and len(w) > 2
    ]


def similarity_score(text_a, text_b):
    """
    Simple transparent lexical similarity.
    It is used as an alignment indicator, not as a semantic proof.
    """

    a = set(tokenize(text_a))
    b = set(tokenize(text_b))

    if not a or not b:
        return 0.0

    intersection = len(a.intersection(b))
    union = len(a.union(b))

    if union == 0:
        return 0.0

    jaccard = intersection / union

    # Also consider coverage of the learning outcome.
    coverage = intersection / max(len(b), 1)

    score = (jaccard * 0.45) + (coverage * 0.55)

    return round(min(score * 100, 100), 1)


def extract_keywords(text, max_words=12):
    words = tokenize(text)

    frequencies = {}

    for word in words:
        frequencies[word] = frequencies.get(word, 0) + 1

    ordered = sorted(
        frequencies.items(),
        key=lambda x: (-x[1], x[0])
    )

    return [word for word, _ in ordered[:max_words]]


# ============================================================
# LEARNING OUTCOME PARSING
# ============================================================

def parse_learning_outcomes(text, outcome_type="CLO"):
    """
    Detects several common formats.

    Examples:
        CLO1: Identify the main idea.
        CLO 1: Identify the main idea.
        CLO-1: Identify the main idea.
        CLO_1: Identify the main idea.
        CLO1 - Identify the main idea.
        CLO1) Identify the main idea.

    Also detects:
        Course Learning Outcome 1:
        Course Learning Outcome 1 -
        Learning Outcome 1:
        LO1:
        PLO1:
        Program Learning Outcome 1:
        PO1:
    """

    text = clean_text(text)

    if not text:
        return []

    if outcome_type.upper() == "CLO":
        patterns = [
            r"(?im)^\s*(CLO\s*[-_ ]?\s*\d+)\s*[\:\-\)\.]?\s*(.+)$",
            r"(?im)^\s*(Course\s+Learning\s+Outcome\s*\d+)\s*[\:\-\)\.]?\s*(.+)$",
            r"(?im)^\s*(Learning\s+Outcome\s*\d+)\s*[\:\-\)\.]?\s*(.+)$",
            r"(?im)^\s*(LO\s*[-_ ]?\s*\d+)\s*[\:\-\)\.]?\s*(.+)$"
        ]
    else:
        patterns = [
            r"(?im)^\s*(PLO\s*[-_ ]?\s*\d+)\s*[\:\-\)\.]?\s*(.+)$",
            r"(?im)^\s*(Program\s+Learning\s+Outcome\s*\d+)\s*[\:\-\)\.]?\s*(.+)$",
            r"(?im)^\s*(PO\s*[-_ ]?\s*\d+)\s*[\:\-\)\.]?\s*(.+)$"
        ]

    found = []

    for pattern in patterns:
        matches = re.findall(pattern, text)

        for label, description in matches:
            label = re.sub(r"\s+", "", label.upper())
            description = clean_text(description)

            if description:
                found.append({
                    "label": label,
                    "description": description
                })

    # Remove duplicates while maintaining order.
    unique = []
    seen = set()

    for item in found:
        key = (
            item["label"].lower(),
            item["description"].lower()
        )

        if key not in seen:
            unique.append(item)
            seen.add(key)

    if unique:
        return unique

    # --------------------------------------------------------
    # Heading-based fallback
    # --------------------------------------------------------

    lines = [
        clean_text(line)
        for line in text.split("\n")
        if clean_text(line)
    ]

    if outcome_type.upper() == "CLO":
        heading_terms = [
            "course learning outcomes",
            "course learning outcome",
            "learning outcomes",
            "learning outcome"
        ]
    else:
        heading_terms = [
            "program learning outcomes",
            "program learning outcome",
            "programme learning outcomes",
            "programme learning outcome"
        ]

    start_index = None

    for i, line in enumerate(lines):
        lower = line.lower()

        if any(term in lower for term in heading_terms):
            start_index = i + 1
            break

    if start_index is not None:
        counter = 1

        for line in lines[start_index:]:
            lower = line.lower()

            # Stop if another major heading begins.
            if (
                len(line) < 80
                and (
                    lower.endswith(":")
                    or lower in [
                        "questions",
                        "quiz",
                        "assessment",
                        "program learning outcomes",
                        "course learning outcomes"
                    ]
                )
            ):
                if counter > 1:
                    break

            candidate = re.sub(
                r"^\s*(?:[-•●▪◦]|\(?\d+\)?[\.\):\-]?)\s*",
                "",
                line
            )

            candidate = clean_text(candidate)

            if len(candidate.split()) >= 4:
                label = (
                    f"CLO{counter}"
                    if outcome_type.upper() == "CLO"
                    else f"PLO{counter}"
                )

                unique.append({
                    "label": label,
                    "description": candidate
                })

                counter += 1

            if counter > 20:
                break

    return unique


# ============================================================
# FILE EXTRACTION
# ============================================================

def extract_pdf_pypdf(data):
    if pypdf is None:
        return ""

    try:
        reader = pypdf.PdfReader(io.BytesIO(data))

        pages = []

        for page in reader.pages:
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""

            if page_text:
                pages.append(page_text)

        return clean_text("\n".join(pages))

    except Exception:
        return ""


def extract_pdf_pymupdf(data):
    if fitz is None:
        return ""

    try:
        document = fitz.open(
            stream=data,
            filetype="pdf"
        )

        pages = []

        for page in document:
            try:
                page_text = page.get_text("text")
            except Exception:
                page_text = ""

            if page_text:
                pages.append(page_text)

        document.close()

        return clean_text("\n".join(pages))

    except Exception:
        return ""


def extract_pdf_ocr(data):
    if pytesseract is None or convert_from_bytes is None:
        return ""

    try:
        images = convert_from_bytes(
            data,
            dpi=200
        )

        pages = []

        for image in images:
            try:
                text = pytesseract.image_to_string(image)
            except Exception:
                text = ""

            if text:
                pages.append(text)

        return clean_text("\n".join(pages))

    except Exception:
        return ""


def extract_pdf_text(data):
    candidates = []

    text = extract_pdf_pymupdf(data)

    if text:
        candidates.append(
            (text, "PyMuPDF text extraction")
        )

    text = extract_pdf_pypdf(data)

    if text:
        candidates.append(
            (text, "pypdf text extraction")
        )

    text = extract_pdf_ocr(data)

    if text:
        candidates.append(
            (text, "OCR extraction")
        )

    if not candidates:
        return "", "No PDF text could be extracted"

    candidates.sort(
        key=lambda x: len(x[0]),
        reverse=True
    )

    return candidates[0]


def extract_docx_text(data):
    if Document is None:
        return ""

    try:
        document = Document(io.BytesIO(data))

        parts = []

        for paragraph in document.paragraphs:
            text = clean_text(paragraph.text)

            if text:
                parts.append(text)

        for table in document.tables:
            for row in table.rows:
                row_values = []

                for cell in row.cells:
                    value = clean_text(cell.text)

                    if value:
                        row_values.append(value)

                if row_values:
                    parts.append(" | ".join(row_values))

        return clean_text("\n".join(parts))

    except Exception:
        return ""


def extract_excel_text(data):
    try:
        workbook = pd.ExcelFile(
            io.BytesIO(data)
        )

        parts = []

        for sheet_name in workbook.sheet_names:
            try:
                df = pd.read_excel(
                    io.BytesIO(data),
                    sheet_name=sheet_name,
                    header=None
                )

                parts.append(
                    f"Sheet: {sheet_name}"
                )

                for row in df.fillna("").astype(str).values.tolist():
                    row_text = " | ".join(
                        value.strip()
                        for value in row
                        if value.strip()
                    )

                    if row_text:
                        parts.append(row_text)

            except Exception:
                continue

        return clean_text("\n".join(parts))

    except Exception:
        return ""


def extract_csv_text(data):
    try:
        text = data.decode(
            "utf-8",
            errors="ignore"
        )

        return clean_text(text)

    except Exception:
        return ""


def extract_plain_text(data):
    try:
        return clean_text(
            data.decode(
                "utf-8",
                errors="ignore"
            )
        )

    except Exception:
        return ""


def extract_uploaded_file(uploaded_file):
    """
    Returns:
        text,
        extraction_method
    """

    data = uploaded_file.getvalue()

    extension = Path(
        uploaded_file.name
    ).suffix.lower()

    if extension == ".pdf":
        return extract_pdf_text(data)

    if extension == ".docx":
        text = extract_docx_text(data)

        return (
            text,
            "DOCX extraction"
            if text
            else "DOCX extraction failed"
        )

    if extension in [".xlsx", ".xls"]:
        text = extract_excel_text(data)

        return (
            text,
            "Excel extraction"
            if text
            else "Excel extraction failed"
        )

    if extension == ".csv":
        text = extract_csv_text(data)

        return (
            text,
            "CSV extraction"
            if text
            else "CSV extraction failed"
        )

    if extension in [
        ".txt",
        ".md",
        ".text"
    ]:
        text = extract_plain_text(data)

        return (
            text,
            "Text extraction"
            if text
            else "Text extraction failed"
        )

    return (
        "",
        "Unsupported file type"
    )


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def looks_like_question_start(text):
    text = clean_text(text)

    if not text:
        return False

    lower = text.lower()

    for starter in QUESTION_STARTERS:
        if re.match(
            rf"^{re.escape(starter)}\b",
            lower
        ):
            return True

    return False


def parse_options(lines):
    """
    Detect MCQ options A-H.
    """

    options = []

    option_pattern = re.compile(
        r"^\s*[\(\[]?([A-Ha-h])[\)\].:\-]\s*(.+)$"
    )

    for line in lines:
        line = clean_text(line)

        match = option_pattern.match(line)

        if match:
            label = match.group(1).upper()
            value = clean_text(match.group(2))

            if value:
                options.append({
                    "label": label,
                    "text": value
                })

    return options


def clean_question_text(text):
    text = clean_text(text)

    # Remove answer-key style text if accidentally captured.
    text = re.sub(
        r"\b(?:answer|correct answer|key)\s*[:\-]\s*[A-H]\b",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def extract_questions(text):
    """
    Robust extraction for common quiz formats.

    Supports:
        Q1. Question
        Q1: Question
        Q1) Question
        Question 1: Question
        1. Question
        1) Question
        1: Question

    Also detects question-mark sentences and command-style questions.
    """

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
    # First pass: explicitly numbered questions
    # --------------------------------------------------------

    question_pattern = re.compile(
        r"^\s*(?:"
        r"Q(?:uestion)?\s*)?"
        r"(\d{1,3})"
        r"\s*[\.\):\-]\s*(.+)$",
        flags=re.IGNORECASE
    )

    current = None

    for line in lines:

        match = question_pattern.match(line)

        if match:
            if current is not None:
                questions.append(current)

            number = int(match.group(1))
            content = clean_text(match.group(2))

            current = {
                "number": number,
                "lines": [content]
            }

            continue

        if current is not None:
            # Stop obvious answer-key lines.
            lower = line.lower()

            if lower.startswith(
                (
                    "answer key",
                    "answers:",
                    "correct answers",
                    "key:"
                )
            ):
                break

            current["lines"].append(line)

    if current is not None:
        questions.append(current)

    # --------------------------------------------------------
    # If numbered questions were not found, use question
    # sentences / command-style questions.
    # --------------------------------------------------------

    if not questions:

        paragraphs = re.split(
            r"\n\s*\n",
            text
        )

        counter = 1

        for paragraph in paragraphs:
            paragraph = clean_text(paragraph)

            if not paragraph:
                continue

            if "?" in paragraph:
                parts = re.split(
                    r"(?<=[?])\s+",
                    paragraph
                )

                for part in parts:
                    part = clean_text(part)

                    if "?" in part and len(part.split()) >= 4:
                        questions.append({
                            "number": counter,
                            "lines": [part]
                        })

                        counter += 1

            elif looks_like_question_start(paragraph):
                questions.append({
                    "number": counter,
                    "lines": [paragraph]
                })

                counter += 1

    # --------------------------------------------------------
    # Build final question objects
    # --------------------------------------------------------

    final_questions = []

    for item in questions:

        raw_lines = [
            clean_text(line)
            for line in item["lines"]
            if clean_text(line)
        ]

        if not raw_lines:
            continue

        options = parse_options(raw_lines)

        non_option_lines = []

        option_pattern = re.compile(
            r"^\s*[\(\[]?[A-Ha-h][\)\].:\-]\s*(.+)$"
        )

        for line in raw_lines:
            if not option_pattern.match(line):
                non_option_lines.append(line)

        question_text = clean_question_text(
            " ".join(non_option_lines)
        )

        # Remove accidental instructions at the end.
        question_text = re.sub(
            r"\b(?:marks?|points?)\s*[:\-]?\s*\d+\s*$",
            "",
            question_text,
            flags=re.IGNORECASE
        ).strip()

        if len(question_text.split()) < 3:
            continue

        final_questions.append({
            "number": item["number"],
            "question": question_text,
            "options": options,
            "raw_lines": raw_lines
        })

    # Remove duplicate question numbers/content.
    unique = []
    seen = set()

    for question in final_questions:

        key = (
            question["number"],
            normalize_text(question["question"])
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(question)

    return unique


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):
    text = normalize_text(question)

    scores = {}

    for level, verbs in BLOOM_VERBS.items():
        score = 0

        for verb in verbs:
            if re.search(
                rf"\b{re.escape(verb)}\b",
                text
            ):
                score += 1

        scores[level] = score

    best_level = max(
        scores,
        key=scores.get
    )

    if scores[best_level] == 0:
        return "Needs Review"

    return best_level


def bloom_alignment_score(
    detected,
    intended
):
    if detected == "Needs Review":
        return 40.0

    distance = abs(
        BLOOM_RANK[detected]
        - BLOOM_RANK[intended]
    )

    if distance == 0:
        return 100.0

    if distance == 1:
        return 70.0

    if distance == 2:
        return 50.0

    return 30.0


# ============================================================
# MCQ QUALITY
# ============================================================

def evaluate_mcq_options(options):
    if not options:
        return {
            "score": 50.0,
            "status": "Not an MCQ"
        }

    score = 100.0
    problems = []

    count = len(options)

    if count < 3:
        score -= 30
        problems.append(
            "Fewer than three options were detected."
        )

    if count > 6:
        score -= 10
        problems.append(
            "More than six options may reduce readability."
        )

    labels = [
        option["label"]
        for option in options
    ]

    if len(labels) != len(set(labels)):
        score -= 30
        problems.append(
            "Duplicate option labels were detected."
        )

    lengths = [
        len(option["text"].split())
        for option in options
    ]

    if lengths:
        if max(lengths) > min(lengths) * 4:
            score -= 10
            problems.append(
                "Option lengths are highly uneven."
            )

    empty_options = [
        option
        for option in options
        if not option["text"].strip()
    ]

    if empty_options:
        score -= 20
        problems.append(
            "One or more options appear empty."
        )

    return {
        "score": max(0.0, min(100.0, score)),
        "status": (
            "Good"
            if not problems
            else "; ".join(problems)
        )
    }


# ============================================================
# QUESTION QUALITY DIMENSIONS
# ============================================================

def clarity_score(question):
    words = question.split()

    score = 100.0

    if len(words) < 5:
        score -= 20

    if len(words) > 60:
        score -= 20

    if "??" in question:
        score -= 10

    if "..." in question:
        score -= 5

    if re.search(
        r"\b(etc|and so on|something|somehow)\b",
        question,
        flags=re.IGNORECASE
    ):
        score -= 15

    return max(0.0, min(100.0, score))


def specificity_score(question):
    score = 100.0

    vague_terms = [
        "discuss something",
        "explain something",
        "tell about",
        "write about",
        "what do you know",
        "say something about"
    ]

    lower = question.lower()

    for phrase in vague_terms:
        if phrase in lower:
            score -= 25

    if len(question.split()) < 6:
        score -= 10

    return max(0.0, min(100.0, score))


def measurability_score(question):
    text = normalize_text(question)

    measurable = False

    for level, verbs in BLOOM_VERBS.items():
        for verb in verbs:
            if re.search(
                rf"\b{re.escape(verb)}\b",
                text
            ):
                measurable = True
                break

        if measurable:
            break

    if measurable:
        return 100.0

    if "?" in question:
        return 65.0

    return 45.0


def relevance_score(
    question,
    clo_text,
    plo_text
):
    clo = similarity_score(
        question,
        clo_text
    )

    plo = similarity_score(
        question,
        plo_text
    )

    if not clo_text and not plo_text:
        return 50.0

    if clo_text and plo_text:
        return round(
            (clo * 0.6) + (plo * 0.4),
            1
        )

    return max(clo, plo)


# ============================================================
# QUESTION EVALUATION
# ============================================================

def best_learning_outcome(
    question,
    outcomes
):
    if not outcomes:
        return None, 0.0

    scored = []

    for outcome in outcomes:
        score = similarity_score(
            question,
            outcome["description"]
        )

        scored.append(
            (
                outcome,
                score
            )
        )

    scored.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return scored[0]


def quality_label(score):
    if score >= 85:
        return "Strong"
    if score >= 70:
        return "Good"
    if score >= 55:
        return "Needs Improvement"

    return "Weak"


def evaluate_question(
    question_obj,
    clos,
    plos,
    intended_bloom
):
    question = question_obj["question"]

    best_clo, clo_score = best_learning_outcome(
        question,
        clos
    )

    best_plo, plo_score = best_learning_outcome(
        question,
        plos
    )

    detected_bloom = detect_bloom(
        question
    )

    bloom_score = bloom_alignment_score(
        detected_bloom,
        intended_bloom
    )

    clarity = clarity_score(
        question
    )

    specificity = specificity_score(
        question
    )

    measurability = measurability_score(
        question
    )

    relevance = relevance_score(
        question,
        best_clo["description"]
        if best_clo
        else "",
        best_plo["description"]
        if best_plo
        else ""
    )

    mcq = evaluate_mcq_options(
        question_obj["options"]
    )

    # Overall quality
    overall = (
        clo_score * 0.20
        + plo_score * 0.15
        + bloom_score * 0.20
        + clarity * 0.10
        + specificity * 0.10
        + measurability * 0.10
        + relevance * 0.05
        + mcq["score"] * 0.10
    )

    overall = round(
        max(0.0, min(100.0, overall)),
        1
    )

    issues = []

    if clo_score < 60:
        issues.append(
            "Weak alignment with the selected course learning outcome."
        )

    if plo_score < 60:
        issues.append(
            "Weak alignment with the selected program learning outcome."
        )

    if bloom_score < 70:
        issues.append(
            f"Detected cognitive level: {detected_bloom}; "
            f"intended level: {intended_bloom}."
        )

    if clarity < 70:
        issues.append(
            "The wording may be unclear or unnecessarily complex."
        )

    if specificity < 70:
        issues.append(
            "The question may be too broad or vague."
        )

    if measurability < 70:
        issues.append(
            "The expected student action is not sufficiently measurable."
        )

    if mcq["score"] < 70:
        issues.append(
            f"MCQ option issue: {mcq['status']}"
        )

    if not issues:
        issues.append(
            "No major quality issue was detected under the defined rubric."
        )

    return {
        "number": question_obj["number"],
        "question": question,
        "options": question_obj["options"],
        "clo": (
            best_clo["label"]
            if best_clo
            else "Not detected"
        ),
        "clo_description": (
            best_clo["description"]
            if best_clo
            else ""
        ),
        "clo_score": round(clo_score, 1),
        "plo": (
            best_plo["label"]
            if best_plo
            else "Not detected"
        ),
        "plo_description": (
            best_plo["description"]
            if best_plo
            else ""
        ),
        "plo_score": round(plo_score, 1),
        "detected_bloom": detected_bloom,
        "bloom_score": round(bloom_score, 1),
        "clarity": round(clarity, 1),
        "specificity": round(specificity, 1),
        "measurability": round(measurability, 1),
        "relevance": round(relevance, 1),
        "mcq_score": round(mcq["score"], 1),
        "mcq_status": mcq["status"],
        "overall": overall,
        "quality": quality_label(overall),
        "issues": issues
    }


# ============================================================
# SUGGESTION GENERATION
# ============================================================

def remove_outcome_labels(text):
    text = re.sub(
        r"\bCLO\s*[-_]?\s*\d+\b",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\bPLO\s*[-_]?\s*\d+\b",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\bLO\s*[-_]?\s*\d+\b",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\bPO\s*[-_]?\s*\d+\b",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def topic_phrase(outcome):
    keywords = extract_keywords(
        outcome,
        max_words=7
    )

    if not keywords:
        return "the key concepts covered in the learning outcome"

    return " ".join(keywords)


def generate_suggestions(
    original_question,
    clo_text,
    plo_text,
    bloom_level
):
    """
    Generates three alternatives based on the actual learning
    outcome content and intended Bloom level.

    The terms CLO/PLO are deliberately excluded from the
    generated questions.
    """

    main_outcome = clo_text or plo_text

    topic = topic_phrase(
        main_outcome
    )

    clean_outcome = remove_outcome_labels(
        main_outcome
    )

    if bloom_level == "Remember":

        suggestions = [
            f"Which statement correctly identifies a key concept related to {topic}?",
            f"Which of the following correctly defines the main concept described by {topic}?",
            f"Which option accurately identifies the essential element associated with {topic}?"
        ]

    elif bloom_level == "Understand":

        suggestions = [
            f"Which statement best explains the relationship among the main ideas involved in {topic}?",
            f"How would you describe the central concept represented by {topic}?",
            f"Which explanation best summarizes the key idea represented by {topic}?"
        ]

    elif bloom_level == "Apply":

        suggestions = [
            f"A new situation involves {topic}. Which action would apply the relevant concept correctly?",
            f"Given a practical situation involving {topic}, which approach should be used to address the situation?",
            f"How would you apply the principles related to {topic} to solve the given situation?"
        ]

    elif bloom_level == "Analyze":

        suggestions = [
            f"Given information related to {topic}, which conclusion is best supported by the evidence?",
            f"Which analysis best distinguishes the important elements involved in {topic}?",
            f"Examine the situation involving {topic}. Which relationship or pattern can be identified from the information provided?"
        ]

    elif bloom_level == "Evaluate":

        suggestions = [
            f"Which judgment about {topic} is best supported by the available evidence?",
            f"Which option provides the strongest justification for the approach used in {topic}?",
            f"Which conclusion about {topic} is most defensible based on the stated evidence?"
        ]

    else:

        suggestions = [
            f"Which proposed solution would most effectively address a new problem involving {topic}?",
            f"Which plan could be developed to address the key requirements associated with {topic}?",
            f"Which proposed approach best integrates the main requirements of {topic} in a new situation?"
        ]

    # Remove any accidental outcome labels.
    suggestions = [
        remove_outcome_labels(
            suggestion
        )
        for suggestion in suggestions
    ]

    return suggestions


# ============================================================
# RE-EVALUATE SUGGESTED QUESTIONS
# ============================================================

def evaluate_suggested_question(
    question,
    clo,
    plo,
    bloom
):
    obj = {
        "number": 1,
        "question": question,
        "options": []
    }

    result = evaluate_question(
        obj,
        [clo] if clo else [],
        [plo] if plo else [],
        bloom
    )

    # Suggested questions are not MCQs.
    result["overall"] = round(
        (
            result["clo_score"] * 0.30
            + result["plo_score"] * 0.20
            + result["bloom_score"] * 0.30
            + result["clarity"] * 0.08
            + result["specificity"] * 0.06
            + result["measurability"] * 0.06
        ),
        1
    )

    result["quality"] = quality_label(
        result["overall"]
    )

    return result


# ============================================================
# SESSION STATE
# ============================================================

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = []

if "suggestion_results" not in st.session_state:
    st.session_state.suggestion_results = {}

if "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""

if "extraction_method" not in st.session_state:
    st.session_state.extraction_method = ""


# ============================================================
# TITLE
# ============================================================

st.title(
    "🎓 OBE Quiz Quality & Alignment Checker"
)

st.write(
    "Evaluate quiz questions for learning-outcome alignment, "
    "Bloom's cognitive level, clarity, measurability, relevance, "
    "and overall question quality."
)


# ============================================================
# 1. ASSESSMENT INFORMATION
# ============================================================

st.header("1. Assessment Information")

col1, col2, col3 = st.columns(3)

with col1:
    course_name = st.text_input(
        "Course / Subject",
        placeholder="e.g., Chemistry, English, Mathematics, Computer Science"
    )

with col2:
    assessment_name = st.text_input(
        "Assessment",
        placeholder="e.g., Quiz 1"
    )

with col3:
    intended_bloom = st.selectbox(
        "Intended Bloom's Level",
        BLOOM_LEVELS
    )


# ============================================================
# 2. CLO INPUT
# ============================================================

st.header("2. Course Learning Outcomes")

st.caption(
    "Enter one outcome per line. Example: CLO1: Identify the main idea."
)

clo_text_input = st.text_area(
    "Course Learning Outcomes",
    height=160,
    placeholder=(
        "CLO1: Identify the main concepts of the subject.\n"
        "CLO2: Apply relevant principles to practical situations.\n"
        "CLO3: Analyze information and draw appropriate conclusions."
    )
)

manual_clos = parse_learning_outcomes(
    clo_text_input,
    "CLO"
)

if manual_clos:
    st.success(
        f"{len(manual_clos)} course learning outcome(s) detected."
    )

    clo_df = pd.DataFrame(
        manual_clos
    )

    st.dataframe(
        clo_df,
        use_container_width=True,
        hide_index=True
    )
else:
    if clo_text_input.strip():
        st.warning(
            "No CLOs could be detected. Use formats such as "
            "'CLO1: Identify the main idea.'"
        )


# ============================================================
# 3. PLO INPUT
# ============================================================

st.header("3. Program Learning Outcomes")

st.caption(
    "Enter one outcome per line. Example: PLO1: Apply knowledge of the discipline."
)

plo_text_input = st.text_area(
    "Program Learning Outcomes",
    height=160,
    placeholder=(
        "PLO1: Apply knowledge of the discipline.\n"
        "PLO2: Analyze information critically.\n"
        "PLO3: Communicate ideas effectively."
    )
)

manual_plos = parse_learning_outcomes(
    plo_text_input,
    "PLO"
)

if manual_plos:
    st.success(
        f"{len(manual_plos)} program learning outcome(s) detected."
    )

    plo_df = pd.DataFrame(
        manual_plos
    )

    st.dataframe(
        plo_df,
        use_container_width=True,
        hide_index=True
    )
else:
    if plo_text_input.strip():
        st.warning(
            "No PLOs could be detected. Use formats such as "
            "'PLO1: Apply knowledge of the discipline.'"
        )


# ============================================================
# 4. UPLOAD QUIZ / COURSE DOCUMENT
# ============================================================

st.header("4. Upload Complete Quiz / Assessment File")

uploaded_file = st.file_uploader(
    "Upload PDF, DOCX, XLSX, XLS, CSV, TXT, or Markdown file",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "csv",
        "txt",
        "md"
    ]
)

if uploaded_file is not None:

    if st.button(
        "📖 Read Uploaded File",
        use_container_width=True
    ):

        with st.spinner(
            "Reading and extracting the file..."
        ):

            extracted_text, extraction_method = (
                extract_uploaded_file(
                    uploaded_file
                )
            )

        st.session_state.extracted_text = (
            extracted_text
        )

        st.session_state.extraction_method = (
            extraction_method
        )

        if extracted_text:

            st.success(
                f"File read successfully using {extraction_method}."
            )

            st.info(
                f"Extracted {len(extracted_text.split())} words."
            )

        else:

            st.error(
                "The file could not be read. "
                "If it is a scanned PDF, make sure OCR dependencies "
                "are installed."
            )


# ============================================================
# SHOW EXTRACTED TEXT
# ============================================================

if st.session_state.extracted_text:

    with st.expander(
        "🔎 Preview Extracted File Text",
        expanded=False
    ):

        st.text_area(
            "Extracted text",
            st.session_state.extracted_text,
            height=300
        )


# ============================================================
# 5. ANALYZE FILE
# ============================================================

if st.session_state.extracted_text:

    st.header("5. Perform Complete Quiz Evaluation")

    if st.button(
        "🔍 Analyze Complete Quiz",
        type="primary",
        use_container_width=True
    ):

        document_text = (
            st.session_state.extracted_text
        )

        # ----------------------------------------------------
        # Try extracting CLO/PLO from uploaded file as well.
        # ----------------------------------------------------

        file_clos = parse_learning_outcomes(
            document_text,
            "CLO"
        )

        file_plos = parse_learning_outcomes(
            document_text,
            "PLO"
        )

        # Use manually entered outcomes if available.
        final_clos = (
            manual_clos
            if manual_clos
            else file_clos
        )

        final_plos = (
            manual_plos
            if manual_plos
            else file_plos
        )

        if not final_clos:
            st.error(
                "No CLOs were detected. Please enter CLOs manually "
                "or make sure the uploaded file contains identifiable "
                "course learning outcomes."
            )

            st.stop()

        if not final_plos:
            st.error(
                "No PLOs were detected. Please enter PLOs manually "
                "or make sure the uploaded file contains identifiable "
                "program learning outcomes."
            )

            st.stop()

        questions = extract_questions(
            document_text
        )

        if not questions:

            st.error(
                "No quiz questions could be detected. "
                "Make sure the file contains numbered questions, "
                "question marks, or clearly written question statements."
            )

            st.stop()

        results = []

        progress = st.progress(0)

        for i, question in enumerate(questions):

            result = evaluate_question(
                question,
                final_clos,
                final_plos,
                intended_bloom
            )

            results.append(result)

            progress.progress(
                (i + 1) / len(questions)
            )

        st.session_state.analysis_results = (
            results
        )

        st.session_state.final_clos = final_clos
        st.session_state.final_plos = final_plos

        st.success(
            f"Evaluation completed for {len(results)} question(s)."
        )


# ============================================================
# RESULTS
# ============================================================

results = st.session_state.analysis_results

if results:

    st.divider()

    st.header("6. Overall Evaluation")

    results_df = pd.DataFrame(
        results
    )

    # --------------------------------------------------------
    # Average values
    # --------------------------------------------------------

    clo_avg = round(
        results_df["clo_score"].mean(),
        1
    )

    plo_avg = round(
        results_df["plo_score"].mean(),
        1
    )

    bloom_avg = round(
        results_df["bloom_score"].mean(),
        1
    )

    clarity_avg = round(
        results_df["clarity"].mean(),
        1
    )

    specificity_avg = round(
        results_df["specificity"].mean(),
        1
    )

    measurability_avg = round(
        results_df["measurability"].mean(),
        1
    )

    mcq_avg = round(
        results_df["mcq_score"].mean(),
        1
    )

    overall = round(
        results_df["overall"].mean(),
        1
    )

    # --------------------------------------------------------
    # TOP GRAPH
    # --------------------------------------------------------

    st.subheader(
        "📊 Overall Quality & Alignment Graph"
    )

    graph_df = pd.DataFrame(
        {
            "Evaluation Area": [
                "CLO Alignment",
                "PLO Alignment",
                "Bloom Alignment",
                "Clarity",
                "Specificity",
                "Measurability",
                "MCQ Quality",
                "Overall Quality"
            ],
            "Score": [
                clo_avg,
                plo_avg,
                bloom_avg,
                clarity_avg,
                specificity_avg,
                measurability_avg,
                mcq_avg,
                overall
            ]
        }
    )

    st.bar_chart(
        graph_df.set_index(
            "Evaluation Area"
        )["Score"],
        use_container_width=True
    )

    st.caption(
        "These percentages evaluate assessment-question quality "
        "and alignment. They are not student attainment percentages. "
        "Student attainment requires student marks."
    )

    # --------------------------------------------------------
    # SUMMARY METRICS
    # --------------------------------------------------------

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric(
            "CLO Alignment",
            f"{clo_avg}%"
        )

    with m2:
        st.metric(
            "PLO Alignment",
            f"{plo_avg}%"
        )

    with m3:
        st.metric(
            "Bloom Alignment",
            f"{bloom_avg}%"
        )

    with m4:
        st.metric(
            "Overall Quality",
            f"{overall}%"
        )


    # ========================================================
    # CLO ANALYSIS
    # ========================================================

    st.divider()

    st.header(
        "7. CLO Analysis"
    )

    clos_for_results = st.session_state.get(
        "final_clos",
        manual_clos
    )

    if clos_for_results:

        clo_labels = [
            item["label"]
            for item in clos_for_results
        ]

        selected_clo_label = st.selectbox(
            "Select ONE CLO to review",
            clo_labels
        )

        selected_clo = next(
            item
            for item in clos_for_results
            if item["label"] == selected_clo_label
        )

        st.info(
            f"{selected_clo['label']}: "
            f"{selected_clo['description']}"
        )

        clo_questions = [
            r for r in results
            if r["clo"] == selected_clo_label
        ]

        if clo_questions:

            selected_clo_score = round(
                sum(
                    r["clo_score"]
                    for r in clo_questions
                ) / len(clo_questions),
                1
            )

            st.metric(
                f"{selected_clo_label} Alignment",
                f"{selected_clo_score}%"
            )

            clo_review_df = pd.DataFrame(
                [
                    {
                        "Question": f"Q{r['number']}",
                        "Alignment": f"{r['clo_score']}%",
                        "Quality": r["quality"],
                        "Bloom": r["detected_bloom"]
                    }
                    for r in clo_questions
                ]
            )

            st.dataframe(
                clo_review_df,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.warning(
                "No question was strongly mapped to this selected CLO."
            )


    # ========================================================
    # PLO ANALYSIS
    # ========================================================

    st.divider()

    st.header(
        "8. PLO Analysis"
    )

    plos_for_results = st.session_state.get(
        "final_plos",
        manual_plos
    )

    if plos_for_results:

        plo_labels = [
            item["label"]
            for item in plos_for_results
        ]

        selected_plo_label = st.selectbox(
            "Select ONE PLO to review",
            plo_labels
        )

        selected_plo = next(
            item
            for item in plos_for_results
            if item["label"] == selected_plo_label
        )

        st.info(
            f"{selected_plo['label']}: "
            f"{selected_plo['description']}"
        )

        plo_questions = [
            r for r in results
            if r["plo"] == selected_plo_label
        ]

        if plo_questions:

            selected_plo_score = round(
                sum(
                    r["plo_score"]
                    for r in plo_questions
                ) / len(plo_questions),
                1
            )

            st.metric(
                f"{selected_plo_label} Alignment",
                f"{selected_plo_score}%"
            )

            plo_review_df = pd.DataFrame(
                [
                    {
                        "Question": f"Q{r['number']}",
                        "Alignment": f"{r['plo_score']}%",
                        "Quality": r["quality"],
                        "Bloom": r["detected_bloom"]
                    }
                    for r in plo_questions
                ]
            )

            st.dataframe(
                plo_review_df,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.warning(
                "No question was strongly mapped to this selected PLO."
            )


    # ========================================================
    # BLOOM ANALYSIS
    # ========================================================

    st.divider()

    st.header(
        "9. Bloom's Taxonomy Analysis"
    )

    bloom_counts = (
        results_df["detected_bloom"]
        .value_counts()
        .to_dict()
    )

    bloom_rows = []

    for level in BLOOM_LEVELS:

        count = bloom_counts.get(
            level,
            0
        )

        percentage = round(
            count / len(results) * 100,
            1
        )

        bloom_rows.append(
            {
                "Bloom Level": level,
                "Questions": count,
                "Percentage": f"{percentage}%",
                "Intended Level": (
                    "Yes"
                    if level == intended_bloom
                    else ""
                )
            }
        )

    if "Needs Review" in bloom_counts:

        count = bloom_counts["Needs Review"]

        bloom_rows.append(
            {
                "Bloom Level": "Needs Review",
                "Questions": count,
                "Percentage": (
                    f"{round(count / len(results) * 100, 1)}%"
                ),
                "Intended Level": ""
            }
        )

    bloom_df = pd.DataFrame(
        bloom_rows
    )

    st.dataframe(
        bloom_df,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # QUESTION-BY-QUESTION
    # ========================================================

    st.divider()

    st.header(
        "10. Question-by-Question Quality Evaluation"
    )

    table_rows = []

    for r in results:

        table_rows.append(
            {
                "Question": f"Q{r['number']}",
                "CLO": r["clo"],
                "CLO Alignment": f"{r['clo_score']}%",
                "PLO": r["plo"],
                "PLO Alignment": f"{r['plo_score']}%",
                "Bloom": r["detected_bloom"],
                "Bloom Alignment": f"{r['bloom_score']}%",
                "Clarity": f"{r['clarity']}%",
                "Specificity": f"{r['specificity']}%",
                "Measurability": f"{r['measurability']}%",
                "MCQ Quality": f"{r['mcq_score']}%",
                "Overall": f"{r['overall']}%",
                "Status": r["quality"]
            }
        )

    evaluation_table = pd.DataFrame(
        table_rows
    )

    st.dataframe(
        evaluation_table,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # INDIVIDUAL QUESTION REVIEW
    # ========================================================

    st.divider()

    st.header(
        "11. Detailed Question Review"
    )

    question_labels = [
        f"Q{r['number']}: {textwrap.shorten(r['question'], width=100)}"
        for r in results
    ]

    selected_question_label = st.selectbox(
        "Select ONE question",
        question_labels
    )

    selected_index = question_labels.index(
        selected_question_label
    )

    selected_result = results[
        selected_index
    ]

    st.subheader(
        f"Question {selected_result['number']}"
    )

    st.write(
        selected_result["question"]
    )

    if selected_result["options"]:

        st.markdown(
            "**Options:**"
        )

        for option in selected_result["options"]:

            st.write(
                f"{option['label']}. "
                f"{option['text']}"
            )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "CLO Alignment",
            f"{selected_result['clo_score']}%"
        )

    with col2:
        st.metric(
            "PLO Alignment",
            f"{selected_result['plo_score']}%"
        )

    with col3:
        st.metric(
            "Overall Quality",
            f"{selected_result['overall']}%"
        )

    st.write(
        f"**Mapped CLO:** {selected_result['clo']}"
    )

    if selected_result["clo_description"]:
        st.caption(
            selected_result["clo_description"]
        )

    st.write(
        f"**Mapped PLO:** {selected_result['plo']}"
    )

    if selected_result["plo_description"]:
        st.caption(
            selected_result["plo_description"]
        )

    st.write(
        f"**Detected Bloom Level:** "
        f"{selected_result['detected_bloom']}"
    )

    st.write(
        f"**Intended Bloom Level:** "
        f"{intended_bloom}"
    )

    st.write(
        f"**Clarity:** {selected_result['clarity']}%"
    )

    st.write(
        f"**Specificity:** "
        f"{selected_result['specificity']}%"
    )

    st.write(
        f"**Measurability:** "
        f"{selected_result['measurability']}%"
    )

    st.write(
        f"**Relevance:** "
        f"{selected_result['relevance']}%"
    )

    st.write(
        f"**MCQ Quality:** "
        f"{selected_result['mcq_score']}%"
    )

    st.write(
        f"**Quality Status:** "
        f"**{selected_result['quality']}**"
    )


    # ========================================================
    # FEEDBACK
    # ========================================================

    st.subheader(
        "Detailed Feedback"
    )

    for issue in selected_result["issues"]:

        if (
            "No major quality issue"
            in issue
        ):
            st.success(
                issue
            )
        else:
            st.warning(
                issue
            )


    # ========================================================
    # SUGGEST THREE ALTERNATIVES
    # ========================================================

    if (
        selected_result["overall"] < 85
        or selected_result["clo_score"] < 70
        or selected_result["plo_score"] < 70
        or selected_result["bloom_score"] < 70
    ):

        st.divider()

        st.header(
            "12. Three Improved Question Alternatives"
        )

        selected_clo = next(
            (
                c
                for c in clos_for_results
                if c["label"]
                == selected_result["clo"]
            ),
            None
        )

        selected_plo = next(
            (
                p
                for p in plos_for_results
                if p["label"]
                == selected_result["plo"]
            ),
            None
        )

        if selected_clo is None:
            selected_clo = {
                "label": "",
                "description": ""
            }

        if selected_plo is None:
            selected_plo = {
                "label": "",
                "description": ""
            }

        suggestions = generate_suggestions(
            selected_result["question"],
            selected_clo["description"],
            selected_plo["description"],
            intended_bloom
        )

        for i, suggestion in enumerate(
            suggestions,
            start=1
        ):

            st.markdown(
                f"### Alternative {i}"
            )

            st.write(
                suggestion
            )

            reevaluated = evaluate_suggested_question(
                suggestion,
                selected_clo,
                selected_plo,
                intended_bloom
            )

            st.write(
                f"**CLO alignment:** "
                f"{reevaluated['clo_score']}%"
            )

            st.write(
                f"**PLO alignment:** "
                f"{reevaluated['plo_score']}%"
            )

            st.write(
                f"**Bloom alignment:** "
                f"{reevaluated['bloom_score']}%"
            )

            st.write(
                f"**Clarity:** "
                f"{reevaluated['clarity']}%"
            )

            st.write(
                f"**Specificity:** "
                f"{reevaluated['specificity']}%"
            )

            st.write(
                f"**Measurability:** "
                f"{reevaluated['measurability']}%"
            )

            st.write(
                f"**Overall rubric score:** "
                f"{reevaluated['overall']}%"
            )

            if reevaluated["overall"] >= 85:

                st.success(
                    "This alternative satisfies the defined "
                    "target thresholds for the selected learning "
                    "outcomes and Bloom level."
                )

            else:

                st.info(
                    "This alternative is a stronger candidate "
                    "but may still require expert review."
                )


    # ========================================================
    # WEAK QUESTIONS
    # ========================================================

    st.divider()

    st.header(
        "13. Questions Requiring Revision"
    )

    weak_questions = [
        r for r in results
        if r["overall"] < 70
    ]

    if weak_questions:

        weak_rows = []

        for r in weak_questions:

            weak_rows.append(
                {
                    "Question": f"Q{r['number']}",
                    "Overall": f"{r['overall']}%",
                    "CLO Alignment": f"{r['clo_score']}%",
                    "PLO Alignment": f"{r['plo_score']}%",
                    "Bloom": r["detected_bloom"],
                    "Main Issue": r["issues"][0]
                }
            )

        weak_df = pd.DataFrame(
            weak_rows
        )

        st.dataframe(
            weak_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.success(
            "No questions fall below the 70% revision threshold."
        )


    # ========================================================
    # EXPORT
    # ========================================================

    st.divider()

    st.header(
        "14. Export Evaluation"
    )

    export_df = results_df[
        [
            "number",
            "question",
            "clo",
            "clo_score",
            "plo",
            "plo_score",
            "detected_bloom",
            "bloom_score",
            "clarity",
            "specificity",
            "measurability",
            "relevance",
            "mcq_score",
            "overall",
            "quality"
        ]
    ].copy()

    export_df.columns = [
        "Question Number",
        "Question",
        "CLO",
        "CLO Alignment",
        "PLO",
        "PLO Alignment",
        "Detected Bloom",
        "Bloom Alignment",
        "Clarity",
        "Specificity",
        "Measurability",
        "Relevance",
        "MCQ Quality",
        "Overall Quality",
        "Status"
    ]

    csv_data = export_df.to_csv(
        index=False
    ).encode(
        "utf-8"
    )

    st.download_button(
        "⬇️ Download Evaluation CSV",
        data=csv_data,
        file_name="obe_quiz_evaluation.csv",
        mime="text/csv",
        use_container_width=True
    )


    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    st.divider()

    st.header(
        "15. Final Evaluation Summary"
    )

    strong_count = sum(
        1
        for r in results
        if r["quality"] == "Strong"
    )

    good_count = sum(
        1
        for r in results
        if r["quality"] == "Good"
    )

    improvement_count = sum(
        1
        for r in results
        if r["quality"] == "Needs Improvement"
    )

    weak_count = sum(
        1
        for r in results
        if r["quality"] == "Weak"
    )

    st.write(
        f"**Total questions evaluated:** "
        f"{len(results)}"
    )

    st.write(
        f"**Strong questions:** "
        f"{strong_count}"
    )

    st.write(
        f"**Good questions:** "
        f"{good_count}"
    )

    st.write(
        f"**Questions needing improvement:** "
        f"{improvement_count}"
    )

    st.write(
        f"**Weak questions:** "
        f"{weak_count}"
    )

    st.write(
        f"**Average CLO alignment:** "
        f"{clo_avg}%"
    )

    st.write(
        f"**Average PLO alignment:** "
        f"{plo_avg}%"
    )

    st.write(
        f"**Average Bloom alignment:** "
        f"{bloom_avg}%"
    )

    st.write(
        f"**Overall question-quality score:** "
        f"{overall}%"
    )

    st.info(
        "The evaluation is a rubric-based quality and alignment "
        "analysis. It should be reviewed by the instructor or "
        "OBE expert before final assessment approval."
    )


# ============================================================
# NO RESULTS MESSAGE
# ============================================================

else:

    if not uploaded_file:

        st.info(
            "Enter the learning outcomes, select the intended "
            "Bloom level, upload the complete quiz, and then "
            "run the analysis."
        )
