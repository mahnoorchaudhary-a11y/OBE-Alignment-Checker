import io
import re
import html
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
    import docx
except Exception:
    docx = None

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
# PAGE
# ============================================================

st.set_page_config(
    page_title="OBE Alignment Checker",
    page_icon="🎓",
    layout="wide"
)


# ============================================================
# CONSTANTS
# ============================================================

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
        "recall", "recognize", "mention", "label", "select"
    ],
    "Understand": [
        "describe", "explain", "summarize", "discuss",
        "interpret", "classify", "compare", "paraphrase",
        "illustrate", "outline"
    ],
    "Apply": [
        "apply", "calculate", "solve", "demonstrate",
        "use", "implement", "execute", "compute",
        "perform", "construct"
    ],
    "Analyze": [
        "analyze", "differentiate", "examine", "compare",
        "contrast", "categorize", "investigate",
        "distinguish", "relate"
    ],
    "Evaluate": [
        "evaluate", "justify", "assess", "critique",
        "judge", "defend", "appraise", "recommend",
        "validate", "argue"
    ],
    "Create": [
        "create", "design", "develop", "formulate",
        "produce", "construct", "plan", "propose",
        "generate", "compose"
    ]
}


# ============================================================
# SESSION STATE
# ============================================================

if "assessment_text" not in st.session_state:
    st.session_state.assessment_text = ""

if "questions" not in st.session_state:
    st.session_state.questions = []

if "results" not in st.session_state:
    st.session_state.results = []

if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

if "selected_question" not in st.session_state:
    st.session_state.selected_question = 0

if "last_improvement" not in st.session_state:
    st.session_state.last_improvement = None


# ============================================================
# TEXT FUNCTIONS
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\x00", " ")
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_text(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def meaningful_words(text):
    stop_words = {
        "the", "a", "an", "and", "or", "but", "of", "to", "in",
        "on", "for", "with", "from", "by", "at", "as", "is",
        "are", "was", "were", "be", "been", "being", "this",
        "that", "these", "those", "it", "its", "their", "they",
        "them", "you", "your", "we", "our", "what", "which",
        "who", "how", "why", "when", "where", "can", "could",
        "would", "should", "will", "may", "might", "do",
        "does", "did", "has", "have", "had"
    }

    words = normalize_text(text).split()

    return {
        w for w in words
        if len(w) >= 3 and w not in stop_words
    }


def shorten_text(text, width=120):
    text = clean_text(text)

    if len(text) <= width:
        return text

    return text[:width - 3].rstrip() + "..."


# ============================================================
# SIMILARITY
# ============================================================

def keyword_similarity(text_a, text_b):

    words_a = meaningful_words(text_a)
    words_b = meaningful_words(text_b)

    if not words_a or not words_b:
        return 0.0

    intersection = words_a.intersection(words_b)

    if not intersection:
        return 0.0

    coverage_a = len(intersection) / len(words_a)
    coverage_b = len(intersection) / len(words_b)

    union = len(words_a.union(words_b))

    if union == 0:
        return 0.0

    jaccard = len(intersection) / union

    score = (
        coverage_a * 50
        + coverage_b * 25
        + jaccard * 25
    )

    return min(100.0, score)


# ============================================================
# BLOOM
# ============================================================

def detect_bloom(text):

    normalized = normalize_text(text)
    detected = []

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                normalized
            ):
                detected.append(level)
                break

    if not detected:
        return None

    detected.sort(
        key=lambda x: BLOOM_LEVELS[x]
    )

    return detected[-1]


def bloom_score(question_bloom, outcome_bloom=None):

    if not question_bloom:
        return 72.0

    if not outcome_bloom:
        return 80.0

    difference = abs(
        BLOOM_LEVELS[question_bloom]
        - BLOOM_LEVELS[outcome_bloom]
    )

    if difference == 0:
        return 100.0

    if difference == 1:
        return 85.0

    if difference == 2:
        return 72.0

    return 60.0


# ============================================================
# FILE EXTRACTION
# ============================================================

def extract_pdf_text(uploaded_file):

    if fitz is None:
        return "", "PyMuPDF is not installed."

    try:

        data = uploaded_file.getvalue()

        document = fitz.open(
            stream=data,
            filetype="pdf"
        )

        pages = []

        for number, page in enumerate(
            document,
            start=1
        ):

            text = page.get_text("text")

            if text.strip():

                pages.append(
                    f"--- Page {number} ---\n{text}"
                )

        document.close()

        result = clean_text(
            "\n\n".join(pages)
        )

        if result:
            return result, ""

        return "", "The PDF appears to be scanned."

    except Exception as exc:

        return "", f"Could not read PDF: {exc}"


def extract_pdf_ocr(uploaded_file):

    if fitz is None:
        return "", "PyMuPDF is not installed."

    if pytesseract is None:
        return "", "OCR is not installed."

    if Image is None:
        return "", "Pillow is not installed."

    try:

        data = uploaded_file.getvalue()

        document = fitz.open(
            stream=data,
            filetype="pdf"
        )

        pages = []

        for number, page in enumerate(
            document,
            start=1
        ):

            pix = page.get_pixmap(
                matrix=fitz.Matrix(2, 2),
                alpha=False
            )

            image = Image.frombytes(
                "RGB",
                [pix.width, pix.height],
                pix.samples
            )

            text = pytesseract.image_to_string(
                image
            )

            if text.strip():

                pages.append(
                    f"--- Page {number} ---\n{text}"
                )

        document.close()

        return clean_text(
            "\n\n".join(pages)
        ), ""

    except Exception as exc:

        return "", f"OCR failed: {exc}"


def extract_docx_text(uploaded_file):

    if docx is None:
        return "", "python-docx is not installed."

    try:

        document = docx.Document(
            io.BytesIO(
                uploaded_file.getvalue()
            )
        )

        parts = []

        for paragraph in document.paragraphs:

            if paragraph.text.strip():
                parts.append(
                    paragraph.text
                )

        for table in document.tables:

            for row in table.rows:

                row_text = " | ".join(
                    cell.text.strip()
                    for cell in row.cells
                )

                if row_text.strip():
                    parts.append(row_text)

        return clean_text(
            "\n".join(parts)
        ), ""

    except Exception as exc:

        return "", f"Could not read DOCX: {exc}"


def extract_pptx_text(uploaded_file):

    if Presentation is None:
        return "", "python-pptx is not installed."

    try:

        presentation = Presentation(
            io.BytesIO(
                uploaded_file.getvalue()
            )
        )

        slides = []

        for number, slide in enumerate(
            presentation.slides,
            start=1
        ):

            parts = []

            for shape in slide.shapes:

                if hasattr(shape, "text"):

                    if shape.text.strip():
                        parts.append(
                            shape.text
                        )

            if parts:

                slides.append(
                    f"--- Slide {number} ---\n"
                    + "\n".join(parts)
                )

        return clean_text(
            "\n\n".join(slides)
        ), ""

    except Exception as exc:

        return "", f"Could not read PPTX: {exc}"


def extract_excel_text(uploaded_file):

    try:

        data = pd.read_excel(
            io.BytesIO(
                uploaded_file.getvalue()
            ),
            sheet_name=None
        )

        parts = []

        for sheet, dataframe in data.items():

            parts.append(
                f"--- Sheet: {sheet} ---"
            )

            dataframe = dataframe.fillna("")

            for row in dataframe.astype(
                str
            ).values.tolist():

                row_text = " | ".join(
                    value.strip()
                    for value in row
                    if value.strip()
                )

                if row_text:
                    parts.append(row_text)

        return clean_text(
            "\n".join(parts)
        ), ""

    except Exception as exc:

        return "", f"Could not read Excel: {exc}"


def extract_csv_text(uploaded_file):

    try:

        dataframe = pd.read_csv(
            io.BytesIO(
                uploaded_file.getvalue()
            )
        )

        dataframe = dataframe.fillna("")

        parts = []

        for row in dataframe.astype(
            str
        ).values.tolist():

            row_text = " | ".join(
                value.strip()
                for value in row
                if value.strip()
            )

            if row_text:
                parts.append(row_text)

        return clean_text(
            "\n".join(parts)
        ), ""

    except Exception as exc:

        return "", f"Could not read CSV: {exc}"


def extract_text_file(uploaded_file):

    try:

        data = uploaded_file.getvalue()

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode(
                "latin-1",
                errors="ignore"
            )

        return clean_text(text), ""

    except Exception as exc:

        return "", f"Could not read text: {exc}"


def extract_svg_text(uploaded_file):

    try:

        data = uploaded_file.getvalue()

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode(
                "latin-1",
                errors="ignore"
            )

        text = re.sub(
            r"<script.*?</script>",
            " ",
            text,
            flags=re.I | re.S
        )

        text = re.sub(
            r"<style.*?</style>",
            " ",
            text,
            flags=re.I | re.S
        )

        text = re.sub(
            r"<[^>]+>",
            " ",
            text
        )

        text = html.unescape(text)

        return clean_text(text), ""

    except Exception as exc:

        return "", f"Could not read SVG: {exc}"


def extract_image_text(uploaded_file):

    if Image is None:
        return "", "Pillow is not installed."

    if pytesseract is None:
        return "", "OCR is not installed."

    try:

        image = Image.open(
            uploaded_file
        )

        text = pytesseract.image_to_string(
            image
        )

        return clean_text(text), ""

    except Exception as exc:

        return "", f"Could not read image: {exc}"


def extract_file_text(uploaded_file):

    suffix = Path(
        uploaded_file.name
    ).suffix.lower()

    if suffix == ".pdf":

        text, error = extract_pdf_text(
            uploaded_file
        )

        if text:
            return text, ""

        ocr_text, ocr_error = extract_pdf_ocr(
            uploaded_file
        )

        if ocr_text:
            return ocr_text, ""

        return "", error or ocr_error

    if suffix == ".docx":
        return extract_docx_text(
            uploaded_file
        )

    if suffix == ".pptx":
        return extract_pptx_text(
            uploaded_file
        )

    if suffix in [".xlsx", ".xls"]:
        return extract_excel_text(
            uploaded_file
        )

    if suffix == ".csv":
        return extract_csv_text(
            uploaded_file
        )

    if suffix in [".txt", ".md"]:
        return extract_text_file(
            uploaded_file
        )

    if suffix == ".svg":
        return extract_svg_text(
            uploaded_file
        )

    if suffix in [
        ".png",
        ".jpg",
        ".jpeg",
        ".webp"
    ]:
        return extract_image_text(
            uploaded_file
        )

    return "", "Unsupported file type."


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text, prefix):

    if not text:
        return []

    outcomes = []

    pattern = re.compile(
        rf"^\s*({prefix}\s*\d+)"
        r"\s*[:.\-)]?\s*(.+)$",
        re.I
    )

    for line in text.splitlines():

        line = clean_text(line)

        if not line:
            continue

        match = pattern.match(line)

        if match:

            label = (
                match.group(1)
                .upper()
                .replace(" ", "")
            )

            description = clean_text(
                match.group(2)
            )

            if description:

                outcomes.append(
                    {
                        "label": label,
                        "description": description
                    }
                )

    return outcomes


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def looks_like_question(text):

    text = clean_text(text)

    if len(text) < 8:
        return False

    if text.endswith("?"):
        return True

    starts = (
        "what ",
        "why ",
        "how ",
        "which ",
        "who ",
        "when ",
        "where ",
        "explain ",
        "describe ",
        "discuss ",
        "analyze ",
        "evaluate ",
        "compare ",
        "define ",
        "calculate ",
        "solve ",
        "identify ",
        "list ",
        "design ",
        "develop ",
        "create ",
        "state ",
        "write ",
        "justify ",
        "differentiate "
    )

    return normalize_text(
        text
    ).startswith(starts)


def extract_questions(text):

    lines = [
        clean_text(x)
        for x in text.splitlines()
        if clean_text(x)
    ]

    pattern = re.compile(
        r"^\s*(?:Q(?:uestion)?\s*)?"
        r"(\d{1,3})"
        r"\s*[\.\):\-]\s*(.+)$",
        re.I
    )

    questions = []

    current_number = None
    current_parts = []

    for line in lines:

        match = pattern.match(line)

        if match:

            if current_parts:

                question_text = clean_text(
                    " ".join(current_parts)
                )

                if len(question_text) >= 8:

                    questions.append(
                        {
                            "number": current_number,
                            "question": question_text
                        }
                    )

            current_number = int(
                match.group(1)
            )

            current_parts = [
                match.group(2)
            ]

        else:

            if current_parts:
                current_parts.append(line)

    if current_parts:

        question_text = clean_text(
            " ".join(current_parts)
        )

        if len(question_text) >= 8:

            questions.append(
                {
                    "number": current_number,
                    "question": question_text
                }
            )

    if not questions:

        parts = re.split(
            r"(?<=[?])\s+",
            text
        )

        number = 1

        for part in parts:

            part = clean_text(part)

            if looks_like_question(part):

                questions.append(
                    {
                        "number": number,
                        "question": part
                    }
                )

                number += 1

    unique = []
    seen = set()

    for item in questions:

        key = normalize_text(
            item["question"]
        )

        if key and key not in seen:

            seen.add(key)
            unique.append(item)

    for i, item in enumerate(
        unique,
        start=1
    ):
        item["number"] = i

    return unique


# ============================================================
# QUESTION TYPE
# ============================================================

def detect_question_type(question):

    q = normalize_text(question)

    if re.search(
        r"\btrue or false\b|\btrue false\b",
        q
    ):
        return "True / False"

    if re.search(
        r"\bfill in the blank\b|\bfill the blank\b",
        q
    ):
        return "Fill in the Blank"

    if re.search(
        r"\bmatch the following\b|\bmatching\b",
        q
    ):
        return "Matching"

    if re.search(
        r"\ba\)\b|\bb\)\b|\bc\)\b|\bd\)\b"
        r"|\bmultiple choice\b",
        q
    ):
        return "Multiple Choice"

    if re.search(
        r"\bcase study\b|\bscenario\b|\bsituation\b",
        q
    ):
        return "Case Study / Scenario"

    if re.search(
        r"\bcalculate\b|\bcompute\b|\bsolve\b"
        r"|\bnumerical\b|\bfind the value\b",
        q
    ):
        return "Numerical / Problem Solving"

    if re.search(
        r"\bdesign\b|\bimplement\b|\bdevelop\b"
        r"|\bperform\b|\bdemonstrate\b"
        r"|\bconstruct\b",
        q
    ):
        return "Practical / Application"

    word_count = len(
        q.split()
    )

    if word_count >= 45:
        return "Essay"

    if word_count >= 25:
        return "Long Answer"

    return "Short Answer"


# ============================================================
# SCORING
# ============================================================

def outcome_match_score(
    question,
    outcome
):

    if not question or not outcome:
        return 50.0

    similarity = keyword_similarity(
        question,
        outcome["description"]
    )

    score = 45 + (
        similarity * 0.55
    )

    q_bloom = detect_bloom(
        question
    )

    o_bloom = detect_bloom(
        outcome["description"]
    )

    if q_bloom and o_bloom:

        difference = abs(
            BLOOM_LEVELS[q_bloom]
            - BLOOM_LEVELS[o_bloom]
        )

        if difference == 0:
            score += 8

        elif difference == 1:
            score += 5

        elif difference == 2:
            score += 2

    if meaningful_words(
        question
    ).intersection(
        meaningful_words(
            outcome["description"]
        )
    ):
        score += 3

    return round(
        min(100, score),
        1
    )


def clarity_score(question):

    words = normalize_text(
        question
    ).split()

    if not words:
        return 50.0

    score = 92.0

    if len(words) < 5:
        score -= 12

    if len(words) > 100:
        score -= 5

    vague_phrases = [
        "write something",
        "discuss something",
        "explain something",
        "do the needful",
        "etc",
        "and so on",
        "whatever"
    ]

    normalized = normalize_text(
        question
    )

    for phrase in vague_phrases:

        if phrase in normalized:
            score -= 8

    if question.count("?") > 2:
        score -= 5

    return round(
        max(55, min(100, score)),
        1
    )


def measurability_score(question):

    bloom = detect_bloom(
        question
    )

    if bloom:
        return 95.0

    normalized = normalize_text(
        question
    )

    verbs = []

    for values in BLOOM_VERBS.values():
        verbs.extend(values)

    for verb in verbs:

        if re.search(
            r"\b" + re.escape(verb) + r"\b",
            normalized
        ):
            return 92.0

    if "?" in question:
        return 85.0

    return 78.0


def relevance_score(
    clo_score,
    plo_score
):

    return round(
        clo_score * 0.6
        + plo_score * 0.4,
        1
    )


def status(score):

    if score >= 75:
        return "Aligned"

    if score >= 50:
        return "Review"

    return "Needs Revision"


def icon(score):

    if score >= 75:
        return "🟢"

    if score >= 50:
        return "🟡"

    return "🔴"


# ============================================================
# EVALUATE QUESTION
# ============================================================

def evaluate_question(
    question_number,
    question_text,
    clos,
    plos
):

    clo_results = []

    for clo in clos:

        score = outcome_match_score(
            question_text,
            clo
        )

        clo_results.append(
            {
                "label": clo["label"],
                "description": clo["description"],
                "score": score
            }
        )

    clo_results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    best_clo = clo_results[0]

    plo_results = []

    for plo in plos:

        score = outcome_match_score(
            question_text,
            plo
        )

        plo_results.append(
            {
                "label": plo["label"],
                "description": plo["description"],
                "score": score
            }
        )

    plo_results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    best_plo = plo_results[0]

    q_bloom = detect_bloom(
        question_text
    )

    outcome_bloom = detect_bloom(
        best_clo["description"]
    )

    bloom = bloom_score(
        q_bloom,
        outcome_bloom
    )

    relevance = relevance_score(
        best_clo["score"],
        best_plo["score"]
    )

    clarity = clarity_score(
        question_text
    )

    measurability = measurability_score(
        question_text
    )

    overall = (
        best_clo["score"] * 0.20
        + best_plo["score"] * 0.15
        + bloom * 0.20
        + relevance * 0.15
        + clarity * 0.15
        + measurability * 0.15
    )

    return {
        "number": question_number,
        "question": question_text,
        "question_type": detect_question_type(
            question_text
        ),
        "clo": best_clo["label"],
        "clo_description": best_clo["description"],
        "clo_score": best_clo["score"],
        "plo": best_plo["label"],
        "plo_description": best_plo["description"],
        "plo_score": best_plo["score"],
        "bloom": q_bloom or "Not Detected",
        "bloom_score": round(bloom, 1),
        "relevance": relevance,
        "clarity": clarity,
        "measurability": measurability,
        "overall": round(overall, 1),
        "status": status(overall)
    }


# ============================================================
# STRUCTURAL RECOMMENDATION ENGINE
# ============================================================

def get_topic_words(text):

    words = list(
        meaningful_words(text)
    )

    if not words:
        return "the topic"

    return " ".join(
        words[:8]
    )


def recommendation_templates(
    question,
    result
):

    qtype = result["question_type"]
    bloom = result["bloom"]

    topic = get_topic_words(
        result["clo_description"]
    )

    # --------------------------------------------------------
    # REMEMBER
    # --------------------------------------------------------

    if bloom == "Remember":

        if qtype == "Multiple Choice":

            return [
                f"Which of the following correctly identifies a key concept related to {topic}?",
                f"Which statement correctly defines the central concept related to {topic}?",
                f"Which of the following is a characteristic of {topic}?"
            ]

        return [
            f"Define {topic} and state its main characteristic.",
            f"Identify the key concept related to {topic} and state its meaning.",
            f"List the main characteristics of {topic}."
        ]

    # --------------------------------------------------------
    # UNDERSTAND
    # --------------------------------------------------------

    if bloom == "Understand":

        if qtype == "Multiple Choice":

            return [
                f"Which statement best explains {topic}?",
                f"Which of the following best describes the relationship between the main ideas in {topic}?",
                f"Which example best illustrates the concept of {topic}?"
            ]

        return [
            f"Explain {topic} in your own words and provide one relevant example.",
            f"Describe the main features of {topic} and explain why they are important.",
            f"Compare the main ideas related to {topic} and illustrate your explanation with an example."
        ]

    # --------------------------------------------------------
    # APPLY
    # --------------------------------------------------------

    if bloom == "Apply":

        if qtype == "Numerical / Problem Solving":

            return [
                f"Apply the appropriate method related to {topic} to solve the following problem. Show your working.",
                f"Using the principles of {topic}, calculate the required result and show the steps.",
                f"Use the appropriate procedure related to {topic} to solve the given problem and explain your result."
            ]

        if qtype == "Case Study / Scenario":

            return [
                f"Given the situation below, apply the principles of {topic} to determine an appropriate solution.",
                f"Apply your knowledge of {topic} to the following situation and explain the action you would take.",
                f"Using the principles of {topic}, solve the problem presented in the following scenario."
            ]

        return [
            f"Apply the principles of {topic} to the given situation and explain your solution.",
            f"Use your knowledge of {topic} to solve the following practical problem.",
            f"Demonstrate how {topic} can be applied to the following situation."
        ]

    # --------------------------------------------------------
    # ANALYZE
    # --------------------------------------------------------

    if bloom == "Analyze":

        if qtype == "Case Study / Scenario":

            return [
                f"Analyze the following situation using the principles of {topic}. Identify the main factors and explain their relationships.",
                f"Examine the following case and analyze the factors related to {topic}. Support your analysis with relevant evidence.",
                f"Analyze the problem presented in the case using {topic} and distinguish the major contributing factors."
            ]

        return [
            f"Analyze the main components of {topic} and explain how they are related.",
            f"Examine the following information and analyze it using the principles of {topic}.",
            f"Differentiate the major elements of {topic} and explain the relationship between them."
        ]

    # --------------------------------------------------------
    # EVALUATE
    # --------------------------------------------------------

    if bloom == "Evaluate":

        if qtype == "Case Study / Scenario":

            return [
                f"Evaluate the situation using appropriate criteria related to {topic} and justify your conclusion.",
                f"Assess the following case using the principles of {topic}. Support your judgment with relevant evidence.",
                f"Evaluate the possible approaches to the problem using {topic} and justify the approach you consider appropriate."
            ]

        return [
            f"Evaluate the effectiveness of the approach used for {topic} and justify your response with relevant evidence.",
            f"Assess the given situation using appropriate criteria related to {topic} and justify your conclusion.",
            f"Critically evaluate the main approach related to {topic} and support your judgment with evidence."
        ]

    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------

    if qtype == "Practical / Application":

        return [
            f"Design a practical solution based on the principles of {topic}. Clearly describe the main steps.",
            f"Develop a suitable approach for addressing a problem related to {topic} and explain your design choices.",
            f"Create a practical plan that applies the principles of {topic} to the given situation."
        ]

    return [
        f"Design a suitable solution based on the principles of {topic} and explain the main steps.",
        f"Develop a practical approach for addressing a problem related to {topic}.",
        f"Create a suitable plan that demonstrates your understanding of {topic} and explain how it would work."
    ]


def generate_recommendations(
    question,
    result
):

    recommendations = recommendation_templates(
        question,
        result
    )

    final = []

    seen = set()

    for recommendation in recommendations:

        recommendation = clean_text(
            recommendation
        )

        key = normalize_text(
            recommendation
        )

        if key not in seen:

            seen.add(key)

            final.append(
                recommendation
            )

    return final[:3]


# ============================================================
# AUTOMATIC RESCORING
# ============================================================

def apply_suggestion(
    question_index,
    new_question,
    clos,
    plos
):

    if question_index >= len(
        st.session_state.questions
    ):
        return

    old_question = st.session_state.questions[
        question_index
    ]["question"]

    old_result = st.session_state.results[
        question_index
    ]

    question_number = st.session_state.questions[
        question_index
    ]["number"]

    # Replace question.
    st.session_state.questions[
        question_index
    ]["question"] = new_question

    # Recalculate.
    new_result = evaluate_question(
        question_number,
        new_question,
        clos,
        plos
    )

    # Replace result.
    st.session_state.results[
        question_index
    ] = new_result

    st.session_state.last_improvement = {
        "old_question": old_question,
        "new_question": new_question,
        "old_score": old_result["overall"],
        "new_score": new_result["overall"]
    }


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("🎓 OBE Alignment Checker")

    st.write(
        "Evaluate and improve assessment questions "
        "against CLOs and PLOs."
    )

    st.divider()

    st.subheader("Score Guide")

    st.success(
        "🟢 75–100% — Aligned"
    )

    st.warning(
        "🟡 50–74% — Review"
    )

    st.error(
        "🔴 0–49% — Needs Revision"
    )

    st.divider()

    st.caption(
        "When a question needs improvement, select a "
        "structural recommendation and the application "
        "will automatically recalculate its score."
    )


# ============================================================
# HEADER
# ============================================================

st.title("🎓 OBE Alignment Checker")

st.write(
    "Upload an assessment, enter the learning outcomes, "
    "and review the alignment of the questions."
)


# ============================================================
# ASSESSMENT DETAILS
# ============================================================

st.subheader("1. Assessment Information")

c1, c2, c3 = st.columns(3)

with c1:

    course_name = st.text_input(
        "Course / Subject",
        placeholder="e.g. Chemistry"
    )

with c2:

    assessment_name = st.text_input(
        "Assessment",
        placeholder="e.g. Quiz 1"
    )

with c3:

    instructor_name = st.text_input(
        "Instructor",
        placeholder="Optional"
    )


# ============================================================
# CLO / PLO
# ============================================================

st.subheader("2. Learning Outcomes")

clo_col, plo_col = st.columns(2)

with clo_col:

    st.markdown("### CLOs")

    clo_text = st.text_area(
        "Enter CLOs",
        height=220,
        placeholder=(
            "CLO1: Explain fundamental concepts.\n"
            "CLO2: Apply principles to solve problems.\n"
            "CLO3: Analyze experimental results."
        )
    )

with plo_col:

    st.markdown("### PLOs")

    plo_text = st.text_area(
        "Enter PLOs",
        height=220,
        placeholder=(
            "PLO1: Apply knowledge of science.\n"
            "PLO2: Analyze problems and develop solutions.\n"
            "PLO3: Communicate effectively."
        )
    )


clos = parse_outcomes(
    clo_text,
    "CLO"
)

plos = parse_outcomes(
    plo_text,
    "PLO"
)


# ============================================================
# SHOW OUTCOMES
# ============================================================

if clos:

    with st.expander(
        f"View CLOs ({len(clos)})"
    ):

        dataframe = pd.DataFrame(
            clos
        )

        dataframe.columns = [
            "CLO",
            "Description"
        ]

        st.dataframe(
            dataframe,
            use_container_width=True,
            hide_index=True
        )


if plos:

    with st.expander(
        f"View PLOs ({len(plos)})"
    ):

        dataframe = pd.DataFrame(
            plos
        )

        dataframe.columns = [
            "PLO",
            "Description"
        ]

        st.dataframe(
            dataframe,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# UPLOAD
# ============================================================

st.subheader("3. Upload Complete Assessment")

uploaded_file = st.file_uploader(
    "Upload assessment",
    type=[
        "pdf",
        "docx",
        "pptx",
        "xlsx",
        "xls",
        "csv",
        "txt",
        "md",
        "svg",
        "png",
        "jpg",
        "jpeg",
        "webp"
    ]
)


if uploaded_file is not None:

    st.info(
        f"Selected file: {uploaded_file.name}"
    )

    if st.button(
        "📖 Read Assessment",
        use_container_width=True
    ):

        with st.spinner(
            "Reading assessment..."
        ):

            text, error = extract_file_text(
                uploaded_file
            )

        if text:

            st.session_state.assessment_text = text

            st.session_state.questions = (
                extract_questions(text)
            )

            st.session_state.results = []

            st.session_state.analyzed = False

            st.session_state.last_improvement = None

            st.success(
                f"Assessment read successfully. "
                f"{len(st.session_state.questions)} "
                f"questions detected."
            )

        else:

            st.error(
                error or
                "No readable text was found."
            )


# ============================================================
# PREVIEW
# ============================================================

if st.session_state.assessment_text:

    with st.expander(
        "📄 View Extracted Assessment"
    ):

        st.text_area(
            "Assessment text",
            value=st.session_state.assessment_text[
                :30000
            ],
            height=350,
            disabled=True
        )

    st.info(
        f"Detected questions: "
        f"**{len(st.session_state.questions)}**"
    )


# ============================================================
# ANALYZE
# ============================================================

st.subheader("4. Analyze")

if st.button(
    "🔎 Analyze Assessment",
    type="primary",
    use_container_width=True
):

    if not clos:

        st.error(
            "Please enter at least one CLO."
        )

        st.stop()

    if not plos:

        st.error(
            "Please enter at least one PLO."
        )

        st.stop()

    if not st.session_state.assessment_text:

        st.error(
            "Please upload and read an assessment first."
        )

        st.stop()

    if not st.session_state.questions:

        st.error(
            "No questions were detected."
        )

        st.stop()

    with st.spinner(
        "Analyzing assessment..."
    ):

        results = []

        for item in st.session_state.questions:

            results.append(
                evaluate_question(
                    item["number"],
                    item["question"],
                    clos,
                    plos
                )
            )

        st.session_state.results = results

        st.session_state.analyzed = True

        st.session_state.last_improvement = None

    st.success(
        "Analysis completed."
    )


# ============================================================
# RESULTS
# ============================================================

if (
    st.session_state.analyzed
    and st.session_state.results
):

    results = st.session_state.results

    results_df = pd.DataFrame(
        results
    )

    # ========================================================
    # OVERALL SCORE
    # ========================================================

    st.divider()

    st.header(
        "🌟 Assessment Alignment Score"
    )

    overall = round(
        results_df["overall"].mean(),
        1
    )

    overall_status = status(
        overall
    )

    if overall_status == "Aligned":

        st.success(
            f"🟢 OVERALL OBE ALIGNMENT: "
            f"{overall:.1f}% — ALIGNED"
        )

    elif overall_status == "Review":

        st.warning(
            f"🟡 OVERALL OBE ALIGNMENT: "
            f"{overall:.1f}% — REVIEW"
        )

    else:

        st.error(
            f"🔴 OVERALL OBE ALIGNMENT: "
            f"{overall:.1f}% — NEEDS REVISION"
        )

    st.progress(
        int(max(0, min(100, overall)))
    )

    # ========================================================
    # AVERAGES
    # ========================================================

    avg_clo = round(
        results_df["clo_score"].mean(),
        1
    )

    avg_plo = round(
        results_df["plo_score"].mean(),
        1
    )

    avg_bloom = round(
        results_df["bloom_score"].mean(),
        1
    )

    avg_relevance = round(
        results_df["relevance"].mean(),
        1
    )

    avg_clarity = round(
        results_df["clarity"].mean(),
        1
    )

    avg_measurability = round(
        results_df["measurability"].mean(),
        1
    )

    # ========================================================
    # SCORE CARDS
    # ========================================================

    score_columns = st.columns(6)

    metrics = [
        ("CLO Match", avg_clo),
        ("PLO Match", avg_plo),
        ("Bloom Level", avg_bloom),
        ("Relevance", avg_relevance),
        ("Clarity", avg_clarity),
        ("Measurability", avg_measurability)
    ]

    for column, (
        label,
        score
    ) in zip(
        score_columns,
        metrics
    ):

        with column:

            st.metric(
                f"{icon(score)} {label}",
                f"{score:.0f}%"
            )

            if score >= 75:

                st.success(
                    "Aligned"
                )

            elif score >= 50:

                st.warning(
                    "Review"
                )

            else:

                st.error(
                    "Needs Revision"
                )

    # ========================================================
    # IMPROVEMENT NOTICE
    # ========================================================

    if st.session_state.last_improvement:

        improvement = (
            st.session_state.last_improvement
        )

        old_score = improvement[
            "old_score"
        ]

        new_score = improvement[
            "new_score"
        ]

        difference = round(
            new_score - old_score,
            1
        )

        if difference > 0:

            st.success(
                f"🎉 Question improved: "
                f"{old_score:.1f}% → "
                f"{new_score:.1f}% "
                f"(+{difference:.1f} points)"
            )

        elif difference == 0:

            st.info(
                f"The structural change produced "
                f"the same score: {new_score:.1f}%."
            )

        else:

            st.warning(
                f"The new version scored "
                f"{new_score:.1f}% compared with "
                f"{old_score:.1f}%."
            )

    # ========================================================
    # GRAPH
    # ========================================================

    st.subheader(
        "📈 Alignment Profile"
    )

    chart_data = pd.DataFrame(
        {
            "Metric": [
                "CLO Match",
                "PLO Match",
                "Bloom Level",
                "Relevance",
                "Clarity",
                "Measurability",
                "Overall"
            ],
            "Score": [
                avg_clo,
                avg_plo,
                avg_bloom,
                avg_relevance,
                avg_clarity,
                avg_measurability,
                overall
            ]
        }
    )

    chart_data = chart_data.set_index(
        "Metric"
    )

    st.bar_chart(
        chart_data,
        y="Score"
    )

    # ========================================================
    # STATUS COUNTS
    # ========================================================

    st.subheader(
        "📌 Assessment Status"
    )

    aligned = int(
        (results_df["overall"] >= 75).sum()
    )

    review = int(
        (
            (results_df["overall"] >= 50)
            & (results_df["overall"] < 75)
        ).sum()
    )

    revision = int(
        (results_df["overall"] < 50).sum()
    )

    status_cols = st.columns(3)

    with status_cols[0]:

        st.success(
            f"🟢 Aligned\n\n{aligned} questions"
        )

    with status_cols[1]:

        st.warning(
            f"🟡 Review\n\n{review} questions"
        )

    with status_cols[2]:

        st.error(
            f"🔴 Needs Revision\n\n{revision} questions"
        )

    # ========================================================
    # QUESTION REVIEW
    # ========================================================

    st.divider()

    st.header(
        "🔍 Improve an Assessment Question"
    )

    question_labels = []

    for item in results:

        question_labels.append(
            f"Q{item['number']} "
            f"{icon(item['overall'])} "
            f"{item['overall']:.0f}% — "
            f"{shorten_text(item['question'], 90)}"
        )

    selected_index = st.selectbox(
        "Select a question",
        range(len(question_labels)),
        format_func=lambda x:
            question_labels[x],
        key="question_selector"
    )

    st.session_state.selected_question = (
        selected_index
    )

    selected = st.session_state.results[
        selected_index
    ]

    # ========================================================
    # CURRENT QUESTION
    # ========================================================

    st.markdown(
        f"### Question {selected['number']}"
    )

    st.info(
        selected["question"]
    )

    selected_score = selected[
        "overall"
    ]

    if selected_score >= 75:

        st.success(
            f"🟢 Current Score: "
            f"{selected_score:.1f}% — Aligned"
        )

    elif selected_score >= 50:

        st.warning(
            f"🟡 Current Score: "
            f"{selected_score:.1f}% — Review"
        )

    else:

        st.error(
            f"🔴 Current Score: "
            f"{selected_score:.1f}% — Needs Revision"
        )

    # ========================================================
    # CURRENT METRICS
    # ========================================================

    selected_metrics = st.columns(6)

    selected_values = [
        (
            "CLO Match",
            selected["clo_score"]
        ),
        (
            "PLO Match",
            selected["plo_score"]
        ),
        (
            "Bloom",
            selected["bloom_score"]
        ),
        (
            "Relevance",
            selected["relevance"]
        ),
        (
            "Clarity",
            selected["clarity"]
        ),
        (
            "Measurability",
            selected["measurability"]
        )
    ]

    for column, (
        label,
        score
    ) in zip(
        selected_metrics,
        selected_values
    ):

        with column:

            st.metric(
                f"{icon(score)} {label}",
                f"{score:.0f}%"
            )

    # ========================================================
    # CURRENT MAPPING
    # ========================================================

    mapping_col1, mapping_col2 = st.columns(2)

    with mapping_col1:

        st.markdown(
            "#### 🎯 CLO Mapping"
        )

        st.write(
            f"**{selected['clo']}**"
        )

        st.write(
            selected["clo_description"]
        )

    with mapping_col2:

        st.markdown(
            "#### 🎯 PLO Mapping"
        )

        st.write(
            f"**{selected['plo']}**"
        )

        st.write(
            selected["plo_description"]
        )

    st.write(
        f"**Detected Question Type:** "
        f"{selected['question_type']}"
    )

    st.write(
        f"**Detected Bloom Level:** "
        f"{selected['bloom']}"
    )

    # ========================================================
    # RECOMMENDATIONS
    # ========================================================

    st.markdown(
        "### ✨ Structural Recommendations"
    )

    st.write(
        "Choose a recommendation below. "
        "The question will be replaced and "
        "automatically rescored."
    )

    recommendations = generate_recommendations(
        selected["question"],
        selected
    )

    for index, recommendation in enumerate(
        recommendations
    ):

        recommendation_box = st.container(
            border=True
        )

        with recommendation_box:

            st.markdown(
                f"**Recommendation {index + 1}**"
            )

            st.write(
                recommendation
            )

            button_key = (
                f"use_suggestion_"
                f"{selected_index}_"
                f"{index}"
            )

            if st.button(
                "✅ Use This Suggestion",
                key=button_key,
                use_container_width=True
            ):

                old_score = selected[
                    "overall"
                ]

                apply_suggestion(
                    selected_index,
                    recommendation,
                    clos,
                    plos
                )

                new_score = (
                    st.session_state.results[
                        selected_index
                    ]["overall"]
                )

                difference = round(
                    new_score - old_score,
                    1
                )

                if difference > 0:

                    st.success(
                        f"🎉 Updated automatically: "
                        f"{old_score:.1f}% → "
                        f"{new_score:.1f}% "
                        f"(+{difference:.1f})"
                    )

                else:

                    st.info(
                        f"Question updated. "
                        f"New score: {new_score:.1f}%"
                    )

                st.rerun()

    # ========================================================
    # MANUAL EDIT
    # ========================================================

    with st.expander(
        "✏️ Or manually improve this question"
    ):

        manual_question = st.text_area(
            "Edit question",
            value=selected["question"],
            height=140,
            key=f"manual_edit_{selected_index}"
        )

        if st.button(
            "🔄 Replace and Recalculate",
            key=f"manual_button_{selected_index}",
            use_container_width=True
        ):

            old_score = selected[
                "overall"
            ]

            apply_suggestion(
                selected_index,
                manual_question,
                clos,
                plos
            )

            new_score = (
                st.session_state.results[
                    selected_index
                ]["overall"]
            )

            difference = round(
                new_score - old_score,
                1
            )

            if difference > 0:

                st.success(
                    f"Updated: "
                    f"{old_score:.1f}% → "
                    f"{new_score:.1f}% "
                    f"(+{difference:.1f})"
                )

            else:

                st.info(
                    f"Updated score: "
                    f"{new_score:.1f}%"
                )

            st.rerun()

    # ========================================================
    # QUESTION TYPE DISTRIBUTION
    # ========================================================

    st.divider()

    st.header(
        "📝 Question-Type Distribution"
    )

    type_counts = (
        results_df[
            "question_type"
        ]
        .value_counts()
        .rename_axis(
            "Question Type"
        )
        .reset_index(
            name="Questions"
        )
    )

    st.dataframe(
        type_counts,
        use_container_width=True,
        hide_index=True
    )

    st.bar_chart(
        type_counts.set_index(
            "Question Type"
        ),
        y="Questions"
    )

    # ========================================================
    # CLO MAPPING
    # ========================================================

    st.header(
        "🎯 CLO Mapping"
    )

    clo_summary = (
        results_df.groupby(
            "clo"
        )
        .agg(
            Questions=(
                "number",
                "count"
            ),
            CLO_Match=(
                "clo_score",
                "mean"
            ),
            Overall=(
                "overall",
                "mean"
            )
        )
        .reset_index()
    )

    clo_summary[
        "CLO_Match"
    ] = clo_summary[
        "CLO_Match"
    ].round(1)

    clo_summary[
        "Overall"
    ] = clo_summary[
        "Overall"
    ].round(1)

    clo_summary.columns = [
        "CLO",
        "Questions",
        "CLO Match %",
        "Overall Alignment %"
    ]

    st.dataframe(
        clo_summary,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # PLO MAPPING
    # ========================================================

    st.header(
        "🎯 PLO Mapping"
    )

    plo_summary = (
        results_df.groupby(
            "plo"
        )
        .agg(
            Questions=(
                "number",
                "count"
            ),
            PLO_Match=(
                "plo_score",
                "mean"
            ),
            Overall=(
                "overall",
                "mean"
            )
        )
        .reset_index()
    )

    plo_summary[
        "PLO_Match"
    ] = plo_summary[
        "PLO_Match"
    ].round(1)

    plo_summary[
        "Overall"
    ] = plo_summary[
        "Overall"
    ].round(1)

    plo_summary.columns = [
        "PLO",
        "Questions",
        "PLO Match %",
        "Overall Alignment %"
    ]

    st.dataframe(
        plo_summary,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # BLOOM DISTRIBUTION
    # ========================================================

    st.header(
        "🧠 Bloom Level Distribution"
    )

    bloom_counts = (
        results_df[
            "bloom"
        ]
        .value_counts()
        .rename_axis(
            "Bloom Level"
        )
        .reset_index(
            name="Questions"
        )
    )

    st.dataframe(
        bloom_counts,
        use_container_width=True,
        hide_index=True
    )

    st.bar_chart(
        bloom_counts.set_index(
            "Bloom Level"
        ),
        y="Questions"
    )

    # ========================================================
    # FINAL QUESTION SUMMARY
    # ========================================================

    st.header(
        "📋 Question Summary"
    )

    summary = results_df[
        [
            "number",
            "question",
            "question_type",
            "clo",
            "plo",
            "bloom",
            "overall",
            "status"
        ]
    ].copy()

    summary.columns = [
        "Question",
        "Assessment Question",
        "Question Type",
        "CLO",
        "PLO",
        "Bloom",
        "Alignment %",
        "Status"
    ]

    summary[
        "Assessment Question"
    ] = summary[
        "Assessment Question"
    ].apply(
        lambda x: shorten_text(
            x,
            160
        )
    )

    summary[
        "Alignment %"
    ] = summary[
        "Alignment %"
    ].apply(
        lambda x: f"{x:.1f}%"
    )

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # EXPORT
    # ========================================================

    st.divider()

    st.header(
        "📥 Export"
    )

    export_df = results_df[
        [
            "number",
            "question",
            "question_type",
            "clo",
            "clo_score",
            "plo",
            "plo_score",
            "bloom",
            "bloom_score",
            "relevance",
            "clarity",
            "measurability",
            "overall",
            "status"
        ]
    ].copy()

    export_df.columns = [
        "Question",
        "Assessment Question",
        "Question Type",
        "CLO",
        "CLO Match",
        "PLO",
        "PLO Match",
        "Bloom Level",
        "Bloom Score",
        "Relevance",
        "Clarity",
        "Measurability",
        "Overall Alignment",
        "Status"
    ]

    csv_data = export_df.to_csv(
        index=False
    ).encode(
        "utf-8"
    )

    st.download_button(
        "⬇️ Download Alignment Report",
        data=csv_data,
        file_name="OBE_Alignment_Report.csv",
        mime="text/csv",
        use_container_width=True
    )

    # ========================================================
    # FINAL SCORE
    # ========================================================

    st.divider()

    st.header(
        "🏁 Final Score"
    )

    final_col1, final_col2 = st.columns(2)

    with final_col1:

        if overall >= 75:

            st.success(
                f"🟢 {overall:.1f}% — Aligned"
            )

        elif overall >= 50:

            st.warning(
                f"🟡 {overall:.1f}% — Review"
            )

        else:

            st.error(
                f"🔴 {overall:.1f}% — Needs Revision"
            )

    with final_col2:

        st.write(
            f"**Questions analyzed:** "
            f"{len(results)}"
        )

        st.write(
            f"**Aligned:** {aligned}"
        )

        st.write(
            f"**Review:** {review}"
        )

        st.write(
            f"**Needs Revision:** {revision}"
        )

else:

    st.info(
        "Upload an assessment, enter CLOs and PLOs, "
        "read the assessment, and click "
        "**Analyze Assessment**."
    )
