import io
import re
from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    import pypdf
except Exception:
    pypdf = None

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
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="OBE Assessment Alignment Checker",
    page_icon="🎓",
    layout="wide"
)


# ============================================================
# BLOOM TAXONOMY
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
        "define",
        "identify",
        "list",
        "name",
        "state",
        "recall",
        "recognize",
        "label",
        "select",
        "match",
        "mention"
    ],
    "Understand": [
        "explain",
        "describe",
        "summarize",
        "interpret",
        "classify",
        "discuss",
        "illustrate",
        "paraphrase",
        "translate",
        "compare"
    ],
    "Apply": [
        "apply",
        "calculate",
        "solve",
        "use",
        "demonstrate",
        "implement",
        "execute",
        "determine",
        "compute",
        "show"
    ],
    "Analyze": [
        "analyze",
        "analyse",
        "differentiate",
        "distinguish",
        "examine",
        "organize",
        "compare",
        "contrast",
        "categorize",
        "investigate",
        "infer"
    ],
    "Evaluate": [
        "evaluate",
        "assess",
        "judge",
        "justify",
        "critique",
        "defend",
        "argue",
        "validate",
        "appraise",
        "recommend"
    ],
    "Create": [
        "create",
        "design",
        "develop",
        "construct",
        "formulate",
        "produce",
        "generate",
        "plan",
        "propose",
        "compose"
    ]
}


# ============================================================
# QUESTION TYPES
# ============================================================

QUESTION_TYPES = [
    "MCQ",
    "True/False",
    "Short Answer",
    "Long Answer",
    "Essay",
    "Numerical / Problem Solving",
    "Fill in the Blank",
    "Matching",
    "Case Study / Scenario",
    "Practical / Application",
    "Other"
]


# ============================================================
# TEXT UTILITIES
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


STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "by",
    "from",
    "at",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "as",
    "that",
    "this",
    "these",
    "those",
    "it",
    "its",
    "their",
    "they",
    "them",
    "he",
    "she",
    "his",
    "her",
    "you",
    "your",
    "we",
    "our",
    "what",
    "which",
    "who",
    "whom",
    "when",
    "where",
    "why",
    "how",
    "does",
    "do",
    "did",
    "can",
    "could",
    "should",
    "would",
    "will",
    "may",
    "might",
    "than",
    "into",
    "about",
    "through",
    "during",
    "using",
    "used",
    "use",
    "following",
    "given",
    "based",
    "question",
    "questions"
}


def tokenize(text):
    words = re.findall(
        r"[A-Za-z][A-Za-z0-9_-]*",
        str(text).lower()
    )

    return [
        word
        for word in words
        if word not in STOP_WORDS
        and len(word) > 2
    ]


def keyword_similarity(text_a, text_b):
    a = set(tokenize(text_a))
    b = set(tokenize(text_b))

    if not a or not b:
        return 0.0

    intersection = len(a.intersection(b))
    union = len(a.union(b))

    if union == 0:
        return 0.0

    jaccard = intersection / union
    coverage = intersection / max(len(b), 1)

    score = (
        jaccard * 0.40
        + coverage * 0.60
    )

    return round(
        min(score * 100, 100),
        1
    )


def extract_keywords(text, limit=8):
    words = tokenize(text)

    counts = {}

    for word in words:
        counts[word] = counts.get(word, 0) + 1

    ordered = sorted(
        counts.items(),
        key=lambda x: (-x[1], x[0])
    )

    return [
        word
        for word, _ in ordered[:limit]
    ]


# ============================================================
# FILE EXTRACTION
# ============================================================

def extract_pdf_with_pymupdf(data):
    if fitz is None:
        return ""

    try:
        document = fitz.open(
            stream=data,
            filetype="pdf"
        )

        pages = []

        for page in document:
            text = page.get_text("text")

            if text:
                pages.append(text)

        document.close()

        return clean_text(
            "\n".join(pages)
        )

    except Exception:
        return ""


def extract_pdf_with_pypdf(data):
    if pypdf is None:
        return ""

    try:
        reader = pypdf.PdfReader(
            io.BytesIO(data)
        )

        pages = []

        for page in reader.pages:
            try:
                text = page.extract_text()
            except Exception:
                text = ""

            if text:
                pages.append(text)

        return clean_text(
            "\n".join(pages)
        )

    except Exception:
        return ""


def extract_pdf_with_ocr(data):
    if pytesseract is None:
        return ""

    if convert_from_bytes is None:
        return ""

    try:
        images = convert_from_bytes(
            data,
            dpi=200
        )

        pages = []

        for image in images:
            try:
                text = pytesseract.image_to_string(
                    image
                )
            except Exception:
                text = ""

            if text:
                pages.append(text)

        return clean_text(
            "\n".join(pages)
        )

    except Exception:
        return ""


def extract_pdf(data):
    candidates = []

    text = extract_pdf_with_pymupdf(data)

    if text:
        candidates.append(
            (
                text,
                "PyMuPDF"
            )
        )

    text = extract_pdf_with_pypdf(data)

    if text:
        candidates.append(
            (
                text,
                "pypdf"
            )
        )

    text = extract_pdf_with_ocr(data)

    if text:
        candidates.append(
            (
                text,
                "OCR"
            )
        )

    if not candidates:
        return (
            "",
            "PDF could not be read"
        )

    candidates.sort(
        key=lambda x: len(x[0]),
        reverse=True
    )

    return candidates[0]


def extract_docx(data):
    if Document is None:
        return (
            "",
            "python-docx is not installed"
        )

    try:
        document = Document(
            io.BytesIO(data)
        )

        parts = []

        for paragraph in document.paragraphs:
            text = clean_text(
                paragraph.text
            )

            if text:
                parts.append(text)

        for table in document.tables:

            for row in table.rows:

                values = []

                for cell in row.cells:

                    value = clean_text(
                        cell.text
                    )

                    if value:
                        values.append(value)

                if values:
                    parts.append(
                        " | ".join(values)
                    )

        return (
            clean_text("\n".join(parts)),
            "DOCX"
        )

    except Exception as exc:
        return (
            "",
            f"DOCX error: {exc}"
        )


def extract_excel(data):
    try:
        excel = pd.ExcelFile(
            io.BytesIO(data)
        )

        parts = []

        for sheet in excel.sheet_names:

            parts.append(
                f"Sheet: {sheet}"
            )

            df = pd.read_excel(
                io.BytesIO(data),
                sheet_name=sheet,
                header=None
            )

            for row in df.fillna("").astype(str).values:

                values = [
                    value.strip()
                    for value in row
                    if value.strip()
                ]

                if values:
                    parts.append(
                        " | ".join(values)
                    )

        return (
            clean_text("\n".join(parts)),
            "Excel"
        )

    except Exception as exc:
        return (
            "",
            f"Excel error: {exc}"
        )


def extract_csv(data):
    try:
        text = data.decode(
            "utf-8",
            errors="ignore"
        )

        return (
            clean_text(text),
            "CSV"
        )

    except Exception as exc:
        return (
            "",
            f"CSV error: {exc}"
        )


def extract_text_file(data):
    try:
        text = data.decode(
            "utf-8",
            errors="ignore"
        )

        return (
            clean_text(text),
            "Text"
        )

    except Exception as exc:
        return (
            "",
            f"Text error: {exc}"
        )


def extract_uploaded_file(uploaded_file):

    data = uploaded_file.getvalue()

    extension = Path(
        uploaded_file.name
    ).suffix.lower()

    if extension == ".pdf":
        return extract_pdf(data)

    if extension == ".docx":
        return extract_docx(data)

    if extension in [".xlsx", ".xls"]:
        return extract_excel(data)

    if extension == ".csv":
        return extract_csv(data)

    if extension in [".txt", ".md"]:
        return extract_text_file(data)

    return (
        "",
        "Unsupported file format"
    )


# ============================================================
# CLO / PLO DETECTION
# ============================================================

def parse_outcomes(text, outcome_type):
    text = clean_text(text)

    if not text:
        return []

    if outcome_type == "CLO":

        patterns = [
            r"(?im)^\s*(CLO\s*[-_ ]?\s*\d+)\s*[\:\-\.\)]\s*(.+)$",
            r"(?im)^\s*(Course\s+Learning\s+Outcome\s*\d+)\s*[\:\-\.\)]\s*(.+)$",
            r"(?im)^\s*(Learning\s+Outcome\s*\d+)\s*[\:\-\.\)]\s*(.+)$",
            r"(?im)^\s*(LO\s*[-_ ]?\s*\d+)\s*[\:\-\.\)]\s*(.+)$"
        ]

    else:

        patterns = [
            r"(?im)^\s*(PLO\s*[-_ ]?\s*\d+)\s*[\:\-\.\)]\s*(.+)$",
            r"(?im)^\s*(Program\s+Learning\s+Outcome\s*\d+)\s*[\:\-\.\)]\s*(.+)$",
            r"(?im)^\s*(Programme\s+Learning\s+Outcome\s*\d+)\s*[\:\-\.\)]\s*(.+)$",
            r"(?im)^\s*(PO\s*[-_ ]?\s*\d+)\s*[\:\-\.\)]\s*(.+)$"
        ]

    outcomes = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text
        )

        for label, description in matches:

            label = re.sub(
                r"\s+",
                "",
                label.upper()
            )

            description = clean_text(
                description
            )

            if description:
                outcomes.append(
                    {
                        "label": label,
                        "description": description
                    }
                )

    unique = []
    seen = set()

    for item in outcomes:

        key = (
            item["label"],
            normalize_text(
                item["description"]
            )
        )

        if key not in seen:

            unique.append(item)
            seen.add(key)

    return unique


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def question_number_pattern():

    return re.compile(
        r"^\s*"
        r"(?:Q(?:uestion)?\s*)?"
        r"(\d{1,3})"
        r"\s*[\.\)\:\-]\s*"
        r"(.+)$",
        re.IGNORECASE
    )


def is_option_line(line):
    return bool(
        re.match(
            r"^\s*[\(\[]?[A-Ha-h][\)\].:\-]\s+.+",
            line
        )
    )


def detect_question_type(question, options):
    text = question.lower().strip()

    if options and len(options) >= 2:
        return "MCQ"

    if re.search(
        r"\btrue\s*(or|/)\s*false\b",
        text
    ):
        return "True/False"

    if re.search(
        r"\b(true|false)\b",
        text
    ) and len(text.split()) < 35:
        return "True/False"

    if re.search(
        r"\b(fill|blank|blanks)\b",
        text
    ):
        return "Fill in the Blank"

    if re.search(
        r"\bmatch\b.*\b(column|following)\b",
        text
    ):
        return "Matching"

    if re.search(
        r"\b(case study|scenario|situation|given case)\b",
        text
    ):
        return "Case Study / Scenario"

    if re.search(
        r"\b(calculate|compute|solve|find the value|equation|"
        r"numerical|calculate the|determine the value)\b",
        text
    ):
        return "Numerical / Problem Solving"

    if re.search(
        r"\b(design|develop|construct|build|implement|create|"
        r"perform|demonstrate|conduct|carry out|experiment)\b",
        text
    ):
        return "Practical / Application"

    word_count = len(text.split())

    if word_count >= 45:
        return "Essay"

    if re.search(
        r"\b(critically discuss|critically analyze|"
        r"write an essay|essay)\b",
        text
    ):
        return "Essay"

    if re.search(
        r"\b(explain|discuss|analyze|analyse|evaluate|"
        r"compare|contrast|justify|describe)\b",
        text
    ):
        if word_count >= 20:
            return "Long Answer"

    if word_count <= 18:
        return "Short Answer"

    return "Long Answer"


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

    current = None

    pattern = question_number_pattern()

    for line in lines:

        match = pattern.match(line)

        if match:

            if current is not None:
                questions.append(
                    current
                )

            current = {
                "number": int(
                    match.group(1)
                ),
                "lines": [
                    match.group(2)
                ]
            }

        else:

            if current is not None:

                if line.lower().startswith(
                    (
                        "answer key",
                        "answers:",
                        "answer:",
                        "correct answers"
                    )
                ):
                    continue

                current["lines"].append(
                    line
                )

    if current is not None:
        questions.append(
            current
        )

    # --------------------------------------------------------
    # Fallback if no numbered questions were found
    # --------------------------------------------------------

    if not questions:

        sentences = re.split(
            r"(?<=[\?])\s+",
            text
        )

        number = 1

        for sentence in sentences:

            sentence = clean_text(
                sentence
            )

            if len(sentence.split()) >= 4:

                if (
                    "?" in sentence
                    or re.match(
                        r"^(define|identify|explain|describe|"
                        r"analyze|analyse|evaluate|compare|"
                        r"discuss|calculate|solve|determine|"
                        r"design|develop|create|justify)\b",
                        sentence,
                        re.IGNORECASE
                    )
                ):

                    questions.append(
                        {
                            "number": number,
                            "lines": [sentence]
                        }
                    )

                    number += 1

    final_questions = []

    for item in questions:

        lines_for_question = [
            clean_text(line)
            for line in item["lines"]
            if clean_text(line)
        ]

        options = []

        question_lines = []

        for line in lines_for_question:

            if is_option_line(line):

                match = re.match(
                    r"^\s*[\(\[]?([A-Ha-h])[\)\].:\-]\s+(.+)",
                    line
                )

                if match:

                    options.append(
                        {
                            "label": match.group(1).upper(),
                            "text": clean_text(
                                match.group(2)
                            )
                        }
                    )

            else:

                question_lines.append(
                    line
                )

        question_text = clean_text(
            " ".join(question_lines)
        )

        if not question_text:
            continue

        if len(question_text.split()) < 3:
            continue

        question_type = detect_question_type(
            question_text,
            options
        )

        final_questions.append(
            {
                "number": item["number"],
                "question": question_text,
                "options": options,
                "type": question_type
            }
        )

    return final_questions


# ============================================================
# BLOOM ANALYSIS
# ============================================================

def detect_bloom(question):

    text = normalize_text(
        question
    )

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

    best = max(
        scores,
        key=scores.get
    )

    if scores[best] == 0:

        # Heuristic based on question structure.
        if re.search(
            r"\bwhy\b",
            text
        ):
            return "Understand"

        if re.search(
            r"\bhow\b",
            text
        ):
            return "Apply"

        return "Needs Review"

    return best


def bloom_score(
    detected,
    intended
):

    if detected == "Needs Review":
        return 40.0

    difference = abs(
        BLOOM_RANK[detected]
        - BLOOM_RANK[intended]
    )

    if difference == 0:
        return 100.0

    if difference == 1:
        return 75.0

    if difference == 2:
        return 55.0

    return 35.0


# ============================================================
# QUALITY DIMENSIONS
# ============================================================

def clarity_score(question):

    words = question.split()

    score = 100.0

    if len(words) < 4:
        score -= 25

    if len(words) > 80:
        score -= 20

    if "??" in question:
        score -= 10

    if "..." in question:
        score -= 5

    vague = [
        "something",
        "somehow",
        "etc.",
        "and so on",
        "tell me about",
        "what do you know"
    ]

    lower = question.lower()

    for term in vague:

        if term in lower:
            score -= 10

    return max(
        0.0,
        min(100.0, score)
    )


def specificity_score(question):

    score = 100.0

    lower = question.lower()

    vague_phrases = [
        "discuss something",
        "explain something",
        "write about",
        "tell about",
        "what do you know",
        "say something about"
    ]

    for phrase in vague_phrases:

        if phrase in lower:
            score -= 25

    if len(question.split()) < 5:
        score -= 15

    return max(
        0.0,
        min(100.0, score)
    )


def measurability_score(question):

    text = normalize_text(
        question
    )

    for verbs in BLOOM_VERBS.values():

        for verb in verbs:

            if re.search(
                rf"\b{re.escape(verb)}\b",
                text
            ):
                return 100.0

    if "?" in question:
        return 65.0

    return 50.0


def cognitive_demand_score(
    question,
    detected_bloom
):

    if detected_bloom == "Needs Review":
        return 50.0

    text = normalize_text(
        question
    )

    score = 70.0

    if detected_bloom in [
        "Analyze",
        "Evaluate",
        "Create"
    ]:
        score += 20

    if re.search(
        r"\b(evidence|justify|reason|"
        r"compare|contrast|interpret|"
        r"critique|design|develop)\b",
        text
    ):
        score += 10

    return min(
        score,
        100.0
    )


# ============================================================
# ALIGNMENT
# ============================================================

def find_best_outcome(
    question,
    outcomes
):

    if not outcomes:
        return None, 0.0

    scored = []

    for outcome in outcomes:

        score = keyword_similarity(
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


def relevance_score(
    question,
    clo,
    plo
):

    clo_score = keyword_similarity(
        question,
        clo
    )

    plo_score = keyword_similarity(
        question,
        plo
    )

    if clo and plo:

        return round(
            clo_score * 0.60
            + plo_score * 0.40,
            1
        )

    if clo:
        return clo_score

    if plo:
        return plo_score

    return 50.0


# ============================================================
# ASSESSMENT TYPE APPROPRIATENESS
# ============================================================

def format_appropriateness(
    question,
    question_type,
    bloom_level
):

    text = question.lower()

    score = 90.0

    if question_type == "MCQ":

        if bloom_level == "Create":
            score -= 15

        if bloom_level == "Evaluate":
            score -= 5

    elif question_type == "True/False":

        if bloom_level in [
            "Analyze",
            "Evaluate",
            "Create"
        ]:
            score -= 20

    elif question_type == "Fill in the Blank":

        if bloom_level in [
            "Analyze",
            "Evaluate",
            "Create"
        ]:
            score -= 20

    elif question_type == "Essay":

        if bloom_level in [
            "Analyze",
            "Evaluate",
            "Create"
        ]:
            score += 5

    elif question_type == "Numerical / Problem Solving":

        if bloom_level in [
            "Apply",
            "Analyze"
        ]:
            score += 5

    elif question_type == "Practical / Application":

        if bloom_level in [
            "Apply",
            "Analyze",
            "Create"
        ]:
            score += 5

    elif question_type == "Case Study / Scenario":

        if bloom_level in [
            "Apply",
            "Analyze",
            "Evaluate"
        ]:
            score += 5

    return max(
        0.0,
        min(100.0, score)
    )


# ============================================================
# QUESTION EVALUATION
# ============================================================

def evaluate_question(
    question,
    clos,
    plos,
    intended_bloom
):

    text = question["question"]

    best_clo, clo_alignment = find_best_outcome(
        text,
        clos
    )

    best_plo, plo_alignment = find_best_outcome(
        text,
        plos
    )

    detected = detect_bloom(
        text
    )

    bloom_alignment = bloom_score(
        detected,
        intended_bloom
    )

    clarity = clarity_score(
        text
    )

    specificity = specificity_score(
        text
    )

    measurability = measurability_score(
        text
    )

    relevance = relevance_score(
        text,
        best_clo["description"]
        if best_clo
        else "",
        best_plo["description"]
        if best_plo
        else ""
    )

    cognitive = cognitive_demand_score(
        text,
        detected
    )

    format_score = format_appropriateness(
        text,
        question["type"],
        detected
    )

    # --------------------------------------------------------
    # OVERALL SCORE
    #
    # No MCQ quality.
    # No assumption that assessment is MCQ.
    # --------------------------------------------------------

    overall = (
        clo_alignment * 0.20
        + plo_alignment * 0.15
        + bloom_alignment * 0.20
        + relevance * 0.10
        + clarity * 0.10
        + specificity * 0.10
        + measurability * 0.05
        + cognitive * 0.05
        + format_score * 0.05
    )

    overall = round(
        max(
            0.0,
            min(
                100.0,
                overall
            )
        ),
        1
    )

    issues = []

    if clo_alignment < 60:
        issues.append(
            "The question has weak apparent alignment with the mapped CLO."
        )

    if plo_alignment < 60:
        issues.append(
            "The question has weak apparent alignment with the mapped PLO."
        )

    if bloom_alignment < 70:
        issues.append(
            "The detected cognitive level does not closely match the intended Bloom level."
        )

    if clarity < 70:
        issues.append(
            "The wording may need improvement for clarity."
        )

    if specificity < 70:
        issues.append(
            "The question may be too broad or vague."
        )

    if measurability < 70:
        issues.append(
            "The expected student action may not be sufficiently measurable."
        )

    if relevance < 60:
        issues.append(
            "The question has limited apparent relevance to the selected outcomes."
        )

    if not issues:
        issues.append(
            "No major issue was detected by the automated rubric."
        )

    if overall >= 85:
        status = "Strong"
    elif overall >= 70:
        status = "Good"
    elif overall >= 55:
        status = "Needs Improvement"
    else:
        status = "Weak"

    return {
        "number": question["number"],
        "question": text,
        "type": question["type"],
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
        "clo_alignment": round(
            clo_alignment,
            1
        ),
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
        "plo_alignment": round(
            plo_alignment,
            1
        ),
        "detected_bloom": detected,
        "bloom_alignment": round(
            bloom_alignment,
            1
        ),
        "relevance": round(
            relevance,
            1
        ),
        "clarity": round(
            clarity,
            1
        ),
        "specificity": round(
            specificity,
            1
        ),
        "measurability": round(
            measurability,
            1
        ),
        "cognitive_demand": round(
            cognitive,
            1
        ),
        "format_appropriateness": round(
            format_score,
            1
        ),
        "overall": overall,
        "status": status,
        "issues": issues
    }


# ============================================================
# ALTERNATIVE QUESTION GENERATOR
# ============================================================

def outcome_topic(outcome_text):

    keywords = extract_keywords(
        outcome_text,
        limit=7
    )

    if not keywords:
        return "the concepts addressed in the learning outcome"

    return " ".join(
        keywords
    )


def generate_alternatives(
    original_question,
    clo_text,
    plo_text,
    bloom_level,
    question_type
):

    outcome = clo_text or plo_text

    topic = outcome_topic(
        outcome
    )

    if question_type == "MCQ":

        if bloom_level == "Remember":

            return [
                f"Which statement correctly identifies a key concept related to {topic}?",
                f"Which option correctly defines the central concept associated with {topic}?",
                f"Which of the following accurately identifies an important element of {topic}?"
            ]

        if bloom_level == "Understand":

            return [
                f"Which statement best explains the main idea associated with {topic}?",
                f"Which option best describes the relationship between the key concepts in {topic}?",
                f"Which explanation best represents the central idea of {topic}?"
            ]

        if bloom_level == "Apply":

            return [
                f"A practical situation involves {topic}. Which approach should be used?",
                f"Given a problem involving {topic}, which method would be most appropriate?",
                f"Which action correctly applies the relevant principles of {topic}?"
            ]

        if bloom_level == "Analyze":

            return [
                f"Given information about {topic}, which conclusion is best supported by the evidence?",
                f"Which analysis best distinguishes the important elements of {topic}?",
                f"Which relationship can be identified by analyzing the situation involving {topic}?"
            ]

        if bloom_level == "Evaluate":

            return [
                f"Which judgment about {topic} is best supported by the available evidence?",
                f"Which approach to {topic} is most defensible, and why?",
                f"Which conclusion about {topic} has the strongest justification?"
            ]

        return [
            f"Which proposed solution would best address a new problem involving {topic}?",
            f"Which plan could be developed to address the requirements associated with {topic}?",
            f"Which proposed approach best integrates the major requirements of {topic}?"
        ]

    if question_type == "True/False":

        return [
            f"True or False: {topic} involves the principle described in the learning outcome.",
            f"True or False: The stated principle of {topic} can be applied in the described context.",
            f"True or False: The relationship represented by {topic} is correctly described by the statement."
        ]

    if question_type == "Fill in the Blank":

        return [
            f"Complete the statement: The key concept associated with {topic} is ________.",
            f"Complete the statement: The process involving {topic} requires ________.",
            f"Complete the statement: An important characteristic of {topic} is ________."
        ]

    if question_type == "Numerical / Problem Solving":

        return [
            f"Apply the relevant principles of {topic} to solve the following problem and show your working.",
            f"Using the appropriate method related to {topic}, calculate the required result and explain the main steps.",
            f"Given a practical problem involving {topic}, determine the solution using the relevant principles."
        ]

    if question_type == "Case Study / Scenario":

        return [
            f"Consider a situation involving {topic}. Analyze the situation and explain the most appropriate response.",
            f"A case involves the concepts represented by {topic}. What conclusion can be drawn from the available information?",
            f"Examine the following scenario involving {topic} and justify the most appropriate course of action."
        ]

    if question_type == "Practical / Application":

        return [
            f"Demonstrate how the principles of {topic} can be applied in a practical situation.",
            f"Develop a practical procedure that applies the key principles associated with {topic}.",
            f"Apply the relevant concepts of {topic} to complete the given task and explain your approach."
        ]

    if question_type == "Essay":

        return [
            f"Write a structured essay explaining the major concepts and implications of {topic}.",
            f"Critically discuss the key ideas associated with {topic} and support your response with relevant evidence.",
            f"Evaluate the major issues related to {topic} and develop a reasoned conclusion."
        ]

    if question_type == "Long Answer":

        return [
            f"Explain the major concepts associated with {topic} and illustrate their significance.",
            f"Analyze the important aspects of {topic} and explain the relationships among them.",
            f"Discuss {topic} using relevant examples and explain how the concepts can be applied."
        ]

    if question_type == "Short Answer":

        return [
            f"Briefly explain the main concept associated with {topic}.",
            f"Identify and briefly describe the key idea represented by {topic}.",
            f"State the main principle associated with {topic} and give a relevant example."
        ]

    return [
        f"Explain the key concepts associated with {topic} and demonstrate their relevance.",
        f"Analyze the important elements of {topic} and explain their relationship.",
        f"Apply the relevant principles of {topic} to an appropriate situation."
    ]


# ============================================================
# SESSION STATE
# ============================================================

if "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""

if "extraction_method" not in st.session_state:
    st.session_state.extraction_method = ""

if "questions" not in st.session_state:
    st.session_state.questions = []

if "results" not in st.session_state:
    st.session_state.results = []

if "clos" not in st.session_state:
    st.session_state.clos = []

if "plos" not in st.session_state:
    st.session_state.plos = []


# ============================================================
# HEADER
# ============================================================

st.title(
    "🎓 OBE Assessment Alignment Checker"
)

st.write(
    "Evaluate assessments across different subjects and question "
    "formats using CLO/PLO alignment, Bloom's Taxonomy, relevance, "
    "clarity, specificity, measurability, cognitive demand, and "
    "assessment-format appropriateness."
)


# ============================================================
# COURSE INFORMATION
# ============================================================

st.header("1. Assessment Information")

col1, col2 = st.columns(2)

with col1:

    course_name = st.text_input(
        "Course / Subject",
        placeholder=(
            "e.g., Chemistry, English, Mathematics, "
            "Physics, Computer Science"
        )
    )

with col2:

    assessment_name = st.text_input(
        "Assessment Name",
        placeholder=(
            "e.g., Quiz 1, Midterm, Assignment, Final Exam"
        )
    )

intended_bloom = st.selectbox(
    "Target / Intended Bloom's Level",
    BLOOM_LEVELS
)


# ============================================================
# CLO
# ============================================================

st.header("2. Course Learning Outcomes")

clo_input = st.text_area(
    "Enter CLOs",
    height=150,
    placeholder=(
        "CLO1: Explain the fundamental concepts of chemistry.\n"
        "CLO2: Apply chemical principles to solve numerical problems.\n"
        "CLO3: Analyze experimental results."
    )
)

manual_clos = parse_outcomes(
    clo_input,
    "CLO"
)

if manual_clos:

    st.success(
        f"{len(manual_clos)} CLO(s) detected."
    )

    st.dataframe(
        pd.DataFrame(manual_clos),
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# PLO
# ============================================================

st.header("3. Program Learning Outcomes")

plo_input = st.text_area(
    "Enter PLOs",
    height=150,
    placeholder=(
        "PLO1: Apply knowledge of the discipline.\n"
        "PLO2: Analyze problems using appropriate methods.\n"
        "PLO3: Communicate solutions effectively."
    )
)

manual_plos = parse_outcomes(
    plo_input,
    "PLO"
)

if manual_plos:

    st.success(
        f"{len(manual_plos)} PLO(s) detected."
    )

    st.dataframe(
        pd.DataFrame(manual_plos),
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# FILE UPLOAD
# ============================================================

st.header("4. Upload Assessment File")

uploaded_file = st.file_uploader(
    "Upload your complete assessment",
    type=[
        "pdf",
        "docx",
        "xlsx",
        "xls",
        "csv",
        "txt",
        "md"
    ],
    help=(
        "Supported formats: PDF, DOCX, XLSX, XLS, CSV, TXT and MD."
    )
)


if uploaded_file:

    if st.button(
        "📖 Read Assessment File",
        use_container_width=True
    ):

        with st.spinner(
            "Reading the uploaded assessment..."
        ):

            text, method = extract_uploaded_file(
                uploaded_file
            )

        st.session_state.extracted_text = text
        st.session_state.extraction_method = method

        if text:

            st.success(
                f"File successfully read using {method}."
            )

            st.info(
                f"Approximately {len(text.split())} words extracted."
            )

        else:

            st.error(
                "The file could not be read. "
                "For scanned PDFs, OCR dependencies are required."
            )


# ============================================================
# PREVIEW
# ============================================================

if st.session_state.extracted_text:

    with st.expander(
        "🔎 Preview Extracted Assessment",
        expanded=False
    ):

        st.text_area(
            "Extracted text",
            st.session_state.extracted_text,
            height=300
        )


# ============================================================
# ANALYSIS
# ============================================================

if st.session_state.extracted_text:

    st.header(
        "5. Analyze Assessment"
    )

    if st.button(
        "🔍 Analyze Complete Assessment",
        type="primary",
        use_container_width=True
    ):

        document_text = (
            st.session_state.extracted_text
        )

        # ----------------------------------------------------
        # Detect outcomes from document if user did not enter
        # them manually.
        # ----------------------------------------------------

        detected_clos = parse_outcomes(
            document_text,
            "CLO"
        )

        detected_plos = parse_outcomes(
            document_text,
            "PLO"
        )

        final_clos = (
            manual_clos
            if manual_clos
            else detected_clos
        )

        final_plos = (
            manual_plos
            if manual_plos
            else detected_plos
        )

        # ----------------------------------------------------
        # CLO requirement
        # ----------------------------------------------------

        if not final_clos:

            st.error(
                "No CLOs were detected. "
                "Please enter the CLOs manually above."
            )

            st.stop()

        # ----------------------------------------------------
        # PLO requirement
        # ----------------------------------------------------

        if not final_plos:

            st.error(
                "No PLOs were detected. "
                "Please enter the PLOs manually above."
            )

            st.stop()

        # ----------------------------------------------------
        # Extract questions
        # ----------------------------------------------------

        questions = extract_questions(
            document_text
        )

        if not questions:

            st.error(
                "No assessment questions were detected. "
                "Please check the extracted text or use a clearly "
                "numbered assessment format."
            )

            st.stop()

        st.session_state.clos = final_clos
        st.session_state.plos = final_plos
        st.session_state.questions = questions

        results = []

        progress = st.progress(0)

        for index, question in enumerate(
            questions
        ):

            result = evaluate_question(
                question,
                final_clos,
                final_plos,
                intended_bloom
            )

            results.append(
                result
            )

            progress.progress(
                (index + 1) / len(questions)
            )

        st.session_state.results = results

        st.success(
            f"Analysis completed for {len(results)} assessment question(s)."
        )


# ============================================================
# RESULTS
# ============================================================

results = st.session_state.results


if results:

    st.divider()

    st.header(
        "6. Assessment-Level Evaluation"
    )

    df = pd.DataFrame(
        results
    )

    # --------------------------------------------------------
    # AVERAGES
    # --------------------------------------------------------

    average_clo = round(
        df["clo_alignment"].mean(),
        1
    )

    average_plo = round(
        df["plo_alignment"].mean(),
        1
    )

    average_bloom = round(
        df["bloom_alignment"].mean(),
        1
    )

    average_relevance = round(
        df["relevance"].mean(),
        1
    )

    average_clarity = round(
        df["clarity"].mean(),
        1
    )

    average_specificity = round(
        df["specificity"].mean(),
        1
    )

    average_measurability = round(
        df["measurability"].mean(),
        1
    )

    average_cognitive = round(
        df["cognitive_demand"].mean(),
        1
    )

    average_format = round(
        df["format_appropriateness"].mean(),
        1
    )

    overall = round(
        df["overall"].mean(),
        1
    )

    # --------------------------------------------------------
    # OVERALL GRAPH
    # --------------------------------------------------------

    st.subheader(
        "📊 Assessment Quality Profile"
    )

    graph_data = pd.DataFrame(
        {
            "Area": [
                "CLO Alignment",
                "PLO Alignment",
                "Bloom Alignment",
                "Relevance",
                "Clarity",
                "Specificity",
                "Measurability",
                "Cognitive Demand",
                "Format Appropriateness",
                "Overall Quality"
            ],
            "Score": [
                average_clo,
                average_plo,
                average_bloom,
                average_relevance,
                average_clarity,
                average_specificity,
                average_measurability,
                average_cognitive,
                average_format,
                overall
            ]
        }
    )

    st.bar_chart(
        graph_data.set_index(
            "Area"
        ),
        use_container_width=True
    )

    st.caption(
        "The scores are automated rubric-based indicators. "
        "They are intended to support instructor/OBE review, "
        "not replace academic judgment."
    )

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.metric(
            "CLO",
            f"{average_clo}%"
        )

    with c2:
        st.metric(
            "PLO",
            f"{average_plo}%"
        )

    with c3:
        st.metric(
            "Bloom",
            f"{average_bloom}%"
        )

    with c4:
        st.metric(
            "Relevance",
            f"{average_relevance}%"
        )

    with c5:
        st.metric(
            "Overall",
            f"{overall}%"
        )


    # ========================================================
    # ASSESSMENT TYPE DISTRIBUTION
    # ========================================================

    st.divider()

    st.header(
        "7. Assessment Question-Type Distribution"
    )

    type_counts = (
        df["type"]
        .value_counts()
        .reset_index()
    )

    type_counts.columns = [
        "Question Type",
        "Number of Questions"
    ]

    st.dataframe(
        type_counts,
        use_container_width=True,
        hide_index=True
    )

    st.bar_chart(
        type_counts.set_index(
            "Question Type"
        ),
        use_container_width=True
    )

    st.info(
        "The evaluator does not require an assessment to be MCQ-based. "
        "Different question formats are analyzed according to their "
        "own characteristics."
    )


    # ========================================================
    # CLO ANALYSIS
    # ========================================================

    st.divider()

    st.header(
        "8. CLO Alignment Tracker"
    )

    selected_clo_label = st.selectbox(
        "Select one CLO",
        [
            item["label"]
            for item in st.session_state.clos
        ]
    )

    selected_clo = next(
        item
        for item in st.session_state.clos
        if item["label"] == selected_clo_label
    )

    st.info(
        f"{selected_clo['label']}: "
        f"{selected_clo['description']}"
    )

    clo_results = [
        item
        for item in results
        if item["clo"] == selected_clo_label
    ]

    if clo_results:

        clo_score = round(
            sum(
                item["clo_alignment"]
                for item in clo_results
            ) / len(clo_results),
            1
        )

        st.metric(
            f"{selected_clo_label} Average Alignment",
            f"{clo_score}%"
        )

        clo_chart = pd.DataFrame(
            {
                "Question": [
                    f"Q{item['number']}"
                    for item in clo_results
                ],
                "Alignment": [
                    item["clo_alignment"]
                    for item in clo_results
                ]
            }
        )

        st.bar_chart(
            clo_chart.set_index(
                "Question"
            ),
            use_container_width=True
        )

    else:

        st.warning(
            "No question was mapped strongly enough to this CLO."
        )


    # ========================================================
    # PLO ANALYSIS
    # ========================================================

    st.divider()

    st.header(
        "9. PLO Alignment Tracker"
    )

    selected_plo_label = st.selectbox(
        "Select one PLO",
        [
            item["label"]
            for item in st.session_state.plos
        ]
    )

    selected_plo = next(
        item
        for item in st.session_state.plos
        if item["label"] == selected_plo_label
    )

    st.info(
        f"{selected_plo['label']}: "
        f"{selected_plo['description']}"
    )

    plo_results = [
        item
        for item in results
        if item["plo"] == selected_plo_label
    ]

    if plo_results:

        plo_score = round(
            sum(
                item["plo_alignment"]
                for item in plo_results
            ) / len(plo_results),
            1
        )

        st.metric(
            f"{selected_plo_label} Average Alignment",
            f"{plo_score}%"
        )

        plo_chart = pd.DataFrame(
            {
                "Question": [
                    f"Q{item['number']}"
                    for item in plo_results
                ],
                "Alignment": [
                    item["plo_alignment"]
                    for item in plo_results
                ]
            }
        )

        st.bar_chart(
            plo_chart.set_index(
                "Question"
            ),
            use_container_width=True
        )

    else:

        st.warning(
            "No question was mapped strongly enough to this PLO."
        )


    # ========================================================
    # BLOOM DISTRIBUTION
    # ========================================================

    st.divider()

    st.header(
        "10. Bloom's Taxonomy Distribution"
    )

    bloom_counts = (
        df["detected_bloom"]
        .value_counts()
    )

    bloom_data = []

    for level in BLOOM_LEVELS:

        count = int(
            bloom_counts.get(
                level,
                0
            )
        )

        bloom_data.append(
            {
                "Bloom Level": level,
                "Questions": count
            }
        )

    bloom_df = pd.DataFrame(
        bloom_data
    )

    st.bar_chart(
        bloom_df.set_index(
            "Bloom Level"
        ),
        use_container_width=True
    )

    st.dataframe(
        bloom_df,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # NO QUESTION-BY-QUESTION QUALITY TABLE
    # ========================================================
    #
    # IMPORTANT:
    # The previous "Question-by-Question Quality Evaluation"
    # section has deliberately been removed.
    #
    # A detailed review is available only when the instructor
    # selects a question below.
    #
    # ========================================================


    # ========================================================
    # SELECTED QUESTION DETAIL
    # ========================================================

    st.divider()

    st.header(
        "11. Review a Selected Question"
    )

    question_options = [
        f"Q{item['number']}: {item['question'][:120]}"
        for item in results
    ]

    selected_question_label = st.selectbox(
        "Select a question to inspect",
        question_options
    )

    selected_index = question_options.index(
        selected_question_label
    )

    selected = results[
        selected_index
    ]

    st.subheader(
        f"Question {selected['number']}"
    )

    st.write(
        selected["question"]
    )

    st.write(
        f"**Detected Assessment Type:** "
        f"{selected['type']}"
    )

    st.write(
        f"**Mapped CLO:** "
        f"{selected['clo']}"
    )

    if selected["clo_description"]:

        st.caption(
            selected["clo_description"]
        )

    st.write(
        f"**Mapped PLO:** "
        f"{selected['plo']}"
    )

    if selected["plo_description"]:

        st.caption(
            selected["plo_description"]
        )

    st.write(
        f"**Detected Bloom Level:** "
        f"{selected['detected_bloom']}"
    )

    st.write(
        f"**Intended Bloom Level:** "
        f"{intended_bloom}"
    )

    # --------------------------------------------------------
    # Selected question metrics
    # --------------------------------------------------------

    a, b, c, d = st.columns(4)

    with a:
        st.metric(
            "CLO Alignment",
            f"{selected['clo_alignment']}%"
        )

    with b:
        st.metric(
            "PLO Alignment",
            f"{selected['plo_alignment']}%"
        )

    with c:
        st.metric(
            "Bloom Alignment",
            f"{selected['bloom_alignment']}%"
        )

    with d:
        st.metric(
            "Overall",
            f"{selected['overall']}%"
        )

    # --------------------------------------------------------
    # Additional dimensions
    # --------------------------------------------------------

    detail_df = pd.DataFrame(
        {
            "Evaluation Area": [
                "CLO Alignment",
                "PLO Alignment",
                "Bloom Alignment",
                "Relevance",
                "Clarity",
                "Specificity",
                "Measurability",
                "Cognitive Demand",
                "Format Appropriateness"
            ],
            "Score": [
                selected["clo_alignment"],
                selected["plo_alignment"],
                selected["bloom_alignment"],
                selected["relevance"],
                selected["clarity"],
                selected["specificity"],
                selected["measurability"],
                selected["cognitive_demand"],
                selected["format_appropriateness"]
            ]
        }
    )

    st.bar_chart(
        detail_df.set_index(
            "Evaluation Area"
        ),
        use_container_width=True
    )

    st.write(
        f"**Status:** {selected['status']}"
    )

    st.subheader(
        "Automated Feedback"
    )

    for issue in selected["issues"]:

        if issue.startswith(
            "No major issue"
        ):
            st.success(
                issue
            )
        else:
            st.warning(
                issue
            )


    # ========================================================
    # THREE ALTERNATIVES
    # ========================================================

    st.divider()

    st.header(
        "12. Three Improved Alternatives"
    )

    st.write(
        "The alternatives preserve the intended learning outcome "
        "and Bloom level while respecting the detected assessment type."
    )

    selected_clo_obj = next(
        (
            item
            for item in st.session_state.clos
            if item["label"] == selected["clo"]
        ),
        None
    )

    selected_plo_obj = next(
        (
            item
            for item in st.session_state.plos
            if item["label"] == selected["plo"]
        ),
        None
    )

    clo_text = (
        selected_clo_obj["description"]
        if selected_clo_obj
        else ""
    )

    plo_text = (
        selected_plo_obj["description"]
        if selected_plo_obj
        else ""
    )

    alternatives = generate_alternatives(
        selected["question"],
        clo_text,
        plo_text,
        intended_bloom,
        selected["type"]
    )

    for number, alternative in enumerate(
        alternatives,
        start=1
    ):

        st.markdown(
            f"### Alternative {number}"
        )

        st.write(
            alternative
        )

        alternative_question = {
            "number": number,
            "question": alternative,
            "options": [],
            "type": selected["type"]
        }

        alternative_result = evaluate_question(
            alternative_question,
            [selected_clo_obj]
            if selected_clo_obj
            else [],
            [selected_plo_obj]
            if selected_plo_obj
            else [],
            intended_bloom
        )

        st.caption(
            f"Estimated alignment: "
            f"{alternative_result['overall']}%"
        )


    # ========================================================
    # WEAK ASSESSMENT AREAS
    # ========================================================

    st.divider()

    st.header(
        "13. Areas Requiring Attention"
    )

    weak = []

    if average_clo < 70:
        weak.append(
            "CLO alignment"
        )

    if average_plo < 70:
        weak.append(
            "PLO alignment"
        )

    if average_bloom < 70:
        weak.append(
            "Bloom alignment"
        )

    if average_relevance < 70:
        weak.append(
            "Relevance"
        )

    if average_clarity < 70:
        weak.append(
            "Clarity"
        )

    if average_specificity < 70:
        weak.append(
            "Specificity"
        )

    if average_measurability < 70:
        weak.append(
            "Measurability"
        )

    if average_cognitive < 70:
        weak.append(
            "Cognitive demand"
        )

    if weak:

        st.warning(
            "The following assessment areas may need review:"
        )

        for item in weak:

            st.write(
                f"• {item}"
            )

    else:

        st.success(
            "The assessment meets the defined automated "
            "thresholds across the major evaluation dimensions."
        )


    # ========================================================
    # EXPORT
    # ========================================================

    st.divider()

    st.header(
        "14. Export Results"
    )

    export_df = df[
        [
            "number",
            "question",
            "type",
            "clo",
            "clo_alignment",
            "plo",
            "plo_alignment",
            "detected_bloom",
            "bloom_alignment",
            "relevance",
            "clarity",
            "specificity",
            "measurability",
            "cognitive_demand",
            "format_appropriateness",
            "overall",
            "status"
        ]
    ].copy()

    export_df.columns = [
        "Question Number",
        "Question",
        "Assessment Type",
        "CLO",
        "CLO Alignment",
        "PLO",
        "PLO Alignment",
        "Detected Bloom",
        "Bloom Alignment",
        "Relevance",
        "Clarity",
        "Specificity",
        "Measurability",
        "Cognitive Demand",
        "Format Appropriateness",
        "Overall Score",
        "Status"
    ]

    csv = export_df.to_csv(
        index=False
    ).encode(
        "utf-8"
    )

    st.download_button(
        "⬇️ Download Assessment Evaluation",
        data=csv,
        file_name="assessment_alignment_evaluation.csv",
        mime="text/csv",
        use_container_width=True
    )


    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    st.divider()

    st.header(
        "15. Final Summary"
    )

    strong = int(
        (df["status"] == "Strong").sum()
    )

    good = int(
        (df["status"] == "Good").sum()
    )

    improvement = int(
        (
            df["status"]
            == "Needs Improvement"
        ).sum()
    )

    weak_count = int(
        (df["status"] == "Weak").sum()
    )

    summary_col1, summary_col2 = st.columns(2)

    with summary_col1:

        st.write(
            f"**Course / Subject:** "
            f"{course_name or 'Not specified'}"
        )

        st.write(
            f"**Assessment:** "
            f"{assessment_name or 'Not specified'}"
        )

        st.write(
            f"**Total questions:** "
            f"{len(results)}"
        )

        st.write(
            f"**Strong:** "
            f"{strong}"
        )

        st.write(
            f"**Good:** "
            f"{good}"
        )

    with summary_col2:

        st.write(
            f"**Needs Improvement:** "
            f"{improvement}"
        )

        st.write(
            f"**Weak:** "
            f"{weak_count}"
        )

        st.write(
            f"**Overall assessment score:** "
            f"{overall}%"
        )

        st.write(
            f"**Target Bloom level:** "
            f"{intended_bloom}"
        )

    st.info(
        "This tool provides an automated OBE screening of an "
        "assessment. Final CLO/PLO mapping and assessment quality "
        "should be confirmed by the course instructor or OBE reviewer."
    )


# ============================================================
# START-UP MESSAGE
# ============================================================

else:

    st.info(
        "Enter your CLOs and PLOs, select the intended Bloom level, "
        "upload the complete assessment file, and click "
        "'Analyze Complete Assessment'."
    )
