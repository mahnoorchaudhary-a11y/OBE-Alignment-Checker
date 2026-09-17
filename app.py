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
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Alignment Checker",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
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
    "Create": 6,
}

BLOOM_VERBS = {
    "Remember": [
        "define", "identify", "list", "name", "state", "recall",
        "recognize", "mention", "label", "select", "match"
    ],
    "Understand": [
        "describe", "explain", "summarize", "discuss", "interpret",
        "classify", "compare", "paraphrase", "illustrate", "outline"
    ],
    "Apply": [
        "apply", "calculate", "solve", "demonstrate", "use",
        "implement", "execute", "compute", "perform", "construct"
    ],
    "Analyze": [
        "analyze", "differentiate", "examine", "compare", "contrast",
        "categorize", "investigate", "break down", "distinguish",
        "relate"
    ],
    "Evaluate": [
        "evaluate", "justify", "assess", "critique", "judge",
        "defend", "appraise", "recommend", "validate", "argue"
    ],
    "Create": [
        "create", "design", "develop", "formulate", "produce",
        "construct", "plan", "propose", "generate", "compose"
    ],
}

QUESTION_TYPES = [
    "Multiple Choice",
    "True / False",
    "Short Answer",
    "Long Answer",
    "Essay",
    "Numerical / Problem Solving",
    "Fill in the Blank",
    "Matching",
    "Case Study / Scenario",
    "Practical / Application",
    "Other",
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
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_text(text):
    text = clean_text(text).lower()

    # Keep letters, numbers and spaces.
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def meaningful_words(text):
    stop_words = {
        "the", "a", "an", "and", "or", "but", "of", "to", "in",
        "on", "for", "with", "from", "by", "at", "as", "is", "are",
        "was", "were", "be", "been", "being", "this", "that", "these",
        "those", "it", "its", "their", "they", "them", "you", "your",
        "we", "our", "what", "which", "who", "how", "why", "when",
        "where", "can", "could", "would", "should", "will", "may",
        "might", "do", "does", "did", "has", "have", "had"
    }

    words = normalize_text(text).split()

    return {
        word for word in words
        if len(word) >= 3 and word not in stop_words
    }


def keyword_similarity(text_a, text_b):
    words_a = meaningful_words(text_a)
    words_b = meaningful_words(text_b)

    if not words_a or not words_b:
        return 0.0

    intersection = words_a.intersection(words_b)

    # Coverage is useful because an assessment question normally
    # contains only part of the wording used in an outcome.
    coverage_a = len(intersection) / len(words_a)
    coverage_b = len(intersection) / len(words_b)

    union = len(words_a.union(words_b))

    if union == 0:
        return 0.0

    jaccard = len(intersection) / union

    score = (
        (coverage_a * 50)
        + (coverage_b * 25)
        + (jaccard * 25)
    )

    return min(100.0, score)


def shorten_text(text, width=120):
    text = clean_text(text)

    if len(text) <= width:
        return text

    return text[: width - 3].rstrip() + "..."


# ============================================================
# BLOOM FUNCTIONS
# ============================================================

def detect_bloom(text):
    normalized = normalize_text(text)

    detected = []

    for level, verbs in BLOOM_VERBS.items():
        for verb in verbs:
            pattern = r"\b" + re.escape(verb) + r"\b"

            if re.search(pattern, normalized):
                detected.append(level)
                break

    if not detected:
        return None

    # If multiple levels are found, use the highest level.
    detected.sort(key=lambda x: BLOOM_LEVELS[x])

    return detected[-1]


def bloom_score(question_bloom, outcome_bloom=None):
    if not question_bloom:
        return 72.0

    if not outcome_bloom:
        return 80.0

    q_level = BLOOM_LEVELS[question_bloom]
    o_level = BLOOM_LEVELS[outcome_bloom]

    difference = abs(q_level - o_level)

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
        file_bytes = uploaded_file.getvalue()
        document = fitz.open(stream=file_bytes, filetype="pdf")

        pages = []

        for page_number, page in enumerate(document):
            text = page.get_text("text")

            if text and text.strip():
                pages.append(
                    f"--- Page {page_number + 1} ---\n{text}"
                )

        document.close()

        combined = "\n\n".join(pages)

        if combined.strip():
            return clean_text(combined), ""

        return "", "The PDF appears to contain scanned/image-based pages."

    except Exception as exc:
        return "", f"Could not read PDF: {exc}"


def extract_pdf_ocr(uploaded_file):
    if fitz is None:
        return "", "PyMuPDF is not installed."

    if pytesseract is None:
        return "", "OCR library is not installed."

    if Image is None:
        return "", "Pillow is not installed."

    try:
        file_bytes = uploaded_file.getvalue()
        document = fitz.open(stream=file_bytes, filetype="pdf")

        pages = []

        for page_number, page in enumerate(document):
            pix = page.get_pixmap(
                matrix=fitz.Matrix(2, 2),
                alpha=False
            )

            image = Image.frombytes(
                "RGB",
                [pix.width, pix.height],
                pix.samples
            )

            text = pytesseract.image_to_string(image)

            if text.strip():
                pages.append(
                    f"--- Page {page_number + 1} ---\n{text}"
                )

        document.close()

        return clean_text("\n\n".join(pages)), ""

    except Exception as exc:
        return "", f"OCR could not process the PDF: {exc}"


def extract_docx_text(uploaded_file):
    if docx is None:
        return "", "python-docx is not installed."

    try:
        file_bytes = uploaded_file.getvalue()
        document = docx.Document(io.BytesIO(file_bytes))

        parts = []

        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                parts.append(paragraph.text)

        for table in document.tables:
            for row in table.rows:
                row_text = " | ".join(
                    cell.text.strip()
                    for cell in row.cells
                )

                if row_text.strip():
                    parts.append(row_text)

        return clean_text("\n".join(parts)), ""

    except Exception as exc:
        return "", f"Could not read DOCX: {exc}"


def extract_pptx_text(uploaded_file):
    if Presentation is None:
        return "", "python-pptx is not installed."

    try:
        file_bytes = uploaded_file.getvalue()
        presentation = Presentation(io.BytesIO(file_bytes))

        slides = []

        for slide_number, slide in enumerate(
            presentation.slides,
            start=1
        ):
            slide_parts = []

            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    if shape.text.strip():
                        slide_parts.append(shape.text)

            if slide_parts:
                slides.append(
                    f"--- Slide {slide_number} ---\n"
                    + "\n".join(slide_parts)
                )

        return clean_text("\n\n".join(slides)), ""

    except Exception as exc:
        return "", f"Could not read PPTX: {exc}"


def extract_excel_text(uploaded_file):
    try:
        file_bytes = uploaded_file.getvalue()

        excel_data = pd.read_excel(
            io.BytesIO(file_bytes),
            sheet_name=None
        )

        parts = []

        for sheet_name, dataframe in excel_data.items():
            parts.append(f"--- Sheet: {sheet_name} ---")

            dataframe = dataframe.fillna("")

            for row in dataframe.astype(str).values.tolist():
                row_text = " | ".join(
                    value.strip()
                    for value in row
                    if value.strip()
                )

                if row_text:
                    parts.append(row_text)

        return clean_text("\n".join(parts)), ""

    except Exception as exc:
        return "", f"Could not read Excel file: {exc}"


def extract_csv_text(uploaded_file):
    try:
        file_bytes = uploaded_file.getvalue()

        dataframe = pd.read_csv(
            io.BytesIO(file_bytes)
        )

        dataframe = dataframe.fillna("")

        parts = []

        for row in dataframe.astype(str).values.tolist():
            row_text = " | ".join(
                value.strip()
                for value in row
                if value.strip()
            )

            if row_text:
                parts.append(row_text)

        return clean_text("\n".join(parts)), ""

    except Exception as exc:
        return "", f"Could not read CSV file: {exc}"


def extract_text_file(uploaded_file):
    try:
        raw = uploaded_file.getvalue()

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="ignore")

        return clean_text(text), ""

    except Exception as exc:
        return "", f"Could not read text file: {exc}"


def extract_svg_text(uploaded_file):
    try:
        raw = uploaded_file.getvalue()

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="ignore")

        text = re.sub(
            r"<script.*?</script>",
            " ",
            text,
            flags=re.IGNORECASE | re.DOTALL
        )

        text = re.sub(
            r"<style.*?</style>",
            " ",
            text,
            flags=re.IGNORECASE | re.DOTALL
        )

        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)

        return clean_text(text), ""

    except Exception as exc:
        return "", f"Could not read SVG file: {exc}"


def extract_image_text(uploaded_file):
    if Image is None:
        return "", "Pillow is not installed."

    if pytesseract is None:
        return "", "OCR is not installed."

    try:
        image = Image.open(uploaded_file)
        text = pytesseract.image_to_string(image)

        return clean_text(text), ""

    except Exception as exc:
        return "", f"Could not read image: {exc}"


def extract_file_text(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()

    if suffix == ".pdf":
        text, error = extract_pdf_text(uploaded_file)

        if text.strip():
            return text, error

        # Automatic OCR fallback.
        ocr_text, ocr_error = extract_pdf_ocr(uploaded_file)

        if ocr_text.strip():
            return ocr_text, ""

        if error:
            return "", error

        return "", ocr_error

    if suffix == ".docx":
        return extract_docx_text(uploaded_file)

    if suffix == ".pptx":
        return extract_pptx_text(uploaded_file)

    if suffix in [".xlsx", ".xls"]:
        return extract_excel_text(uploaded_file)

    if suffix == ".csv":
        return extract_csv_text(uploaded_file)

    if suffix in [".txt", ".md"]:
        return extract_text_file(uploaded_file)

    if suffix == ".svg":
        return extract_svg_text(uploaded_file)

    if suffix in [".png", ".jpg", ".jpeg", ".webp"]:
        return extract_image_text(uploaded_file)

    return "", f"Unsupported file type: {suffix}"


# ============================================================
# OUTCOME PARSING
# ============================================================

def parse_outcomes(text, outcome_name):
    if not text:
        return []

    lines = [
        clean_text(line)
        for line in text.splitlines()
        if clean_text(line)
    ]

    outcomes = []

    pattern = re.compile(
        rf"^\s*({outcome_name}\s*\d+)\s*[:.\-)]?\s*(.+)$",
        flags=re.IGNORECASE
    )

    for line in lines:
        match = pattern.match(line)

        if match:
            label = match.group(1).upper().replace(" ", "")
            description = clean_text(match.group(2))

            if description:
                outcomes.append(
                    {
                        "label": label,
                        "description": description,
                    }
                )

    # Also support comma/semicolon-separated outcomes.
    if not outcomes:
        chunks = re.split(r"[\n;]+", text)

        for chunk in chunks:
            chunk = clean_text(chunk)

            match = pattern.match(chunk)

            if match:
                label = match.group(1).upper().replace(" ", "")
                description = clean_text(match.group(2))

                if description:
                    outcomes.append(
                        {
                            "label": label,
                            "description": description,
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

    question_starts = (
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
        "differentiate ",
    )

    normalized = normalize_text(text)

    return normalized.startswith(question_starts)


def extract_questions(text):
    text = clean_text(text)

    lines = [
        clean_text(line)
        for line in text.splitlines()
        if clean_text(line)
    ]

    questions = []

    # --------------------------------------------------------
    # Numbered questions
    # --------------------------------------------------------

    question_pattern = re.compile(
        r"^\s*(?:Q(?:uestion)?\s*)?"
        r"(\d{1,3})"
        r"\s*[\.\):\-]\s*(.+)$",
        flags=re.IGNORECASE
    )

    current_number = None
    current_parts = []

    for line in lines:
        match = question_pattern.match(line)

        if match:
            if current_parts:
                question_text = clean_text(
                    " ".join(current_parts)
                )

                if len(question_text) >= 8:
                    questions.append(
                        {
                            "number": current_number,
                            "question": question_text,
                        }
                    )

            current_number = int(match.group(1))
            current_parts = [match.group(2)]

        else:
            if current_parts:
                # Ignore obvious answer-choice lines as separate
                # questions, but retain them as part of the question.
                current_parts.append(line)

    if current_parts:
        question_text = clean_text(
            " ".join(current_parts)
        )

        if len(question_text) >= 8:
            questions.append(
                {
                    "number": current_number,
                    "question": question_text,
                }
            )

    # --------------------------------------------------------
    # If numbered extraction did not work, use question marks
    # --------------------------------------------------------

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
                        "question": part,
                    }
                )

                number += 1

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    unique_questions = []
    seen = set()

    for item in questions:
        normalized = normalize_text(item["question"])

        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_questions.append(item)

    # --------------------------------------------------------
    # Final numbering
    # --------------------------------------------------------

    for index, item in enumerate(unique_questions, start=1):
        item["number"] = index

    return unique_questions


# ============================================================
# QUESTION TYPE DETECTION
# ============================================================

def detect_question_type(question):
    q = normalize_text(question)

    if re.search(
        r"\b(true or false|true false|t f)\b",
        q
    ):
        return "True / False"

    if re.search(
        r"\b(fill in the blank|fill the blank|complete the blank)\b",
        q
    ):
        return "Fill in the Blank"

    if re.search(
        r"\b(match the following|match column|matching)\b",
        q
    ):
        return "Matching"

    if re.search(
        r"\b(a\)|b\)|c\)|d\)|option a|option b|multiple choice)\b",
        q
    ):
        return "Multiple Choice"

    if re.search(
        r"\b(case study|scenario|situation|given case)\b",
        q
    ):
        return "Case Study / Scenario"

    if re.search(
        r"\b(calculate|solve|compute|find the value|determine the value|numerical)\b",
        q
    ):
        return "Numerical / Problem Solving"

    if re.search(
        r"\b(design|implement|develop|perform|demonstrate|construct|create a program|build)\b",
        q
    ):
        return "Practical / Application"

    words = q.split()

    if len(words) >= 45:
        return "Essay"

    if len(words) >= 25:
        return "Long Answer"

    return "Short Answer"


# ============================================================
# FORGIVING SCORING
# ============================================================

def outcome_match_score(question, outcome):
    """
    A forgiving, transparent mapping score.

    The previous strict similarity approach could make many
    normal questions appear weak. This version provides a
    reasonable baseline and increases the score when there is
    meaningful wording/action alignment.
    """

    if not question or not outcome:
        return 50.0

    raw_similarity = keyword_similarity(
        question,
        outcome["description"]
    )

    score = 45.0 + (raw_similarity * 0.55)

    question_bloom = detect_bloom(question)
    outcome_bloom = detect_bloom(outcome["description"])

    if question_bloom and outcome_bloom:
        q_level = BLOOM_LEVELS[question_bloom]
        o_level = BLOOM_LEVELS[outcome_bloom]

        difference = abs(q_level - o_level)

        if difference == 0:
            score += 8

        elif difference == 1:
            score += 5

        elif difference == 2:
            score += 2

    # Any meaningful shared content gives a small additional
    # confidence boost.
    question_words = meaningful_words(question)
    outcome_words = meaningful_words(outcome["description"])

    if question_words.intersection(outcome_words):
        score += 3

    return round(min(100.0, score), 1)


def clarity_score(question):
    words = normalize_text(question).split()

    if not words:
        return 50.0

    score = 92.0

    if len(words) < 5:
        score -= 10

    if len(words) > 100:
        score -= 5

    vague_phrases = [
        "write something",
        "discuss something",
        "explain something",
        "do the needful",
        "etc",
        "and so on",
        "as appropriate",
        "whatever",
    ]

    normalized = normalize_text(question)

    for phrase in vague_phrases:
        if phrase in normalized:
            score -= 8

    if question.count("?") > 2:
        score -= 5

    return round(max(55.0, min(100.0, score)), 1)


def measurability_score(question):
    bloom = detect_bloom(question)

    if bloom:
        return 95.0

    normalized = normalize_text(question)

    measurable_words = [
        "calculate",
        "identify",
        "define",
        "explain",
        "describe",
        "compare",
        "analyze",
        "evaluate",
        "design",
        "develop",
        "list",
        "state",
        "solve",
        "justify",
        "classify",
        "demonstrate",
        "construct",
        "apply",
    ]

    for word in measurable_words:
        if re.search(r"\b" + re.escape(word) + r"\b", normalized):
            return 92.0

    if "?" in question:
        return 85.0

    return 78.0


def relevance_score(clo_score, plo_score):
    return round(
        (clo_score * 0.6) + (plo_score * 0.4),
        1
    )


def metric_status(score):
    if score >= 75:
        return "Aligned"

    if score >= 50:
        return "Review"

    return "Needs Revision"


def status_icon(score):
    status = metric_status(score)

    if status == "Aligned":
        return "🟢"

    if status == "Review":
        return "🟡"

    return "🔴"


# ============================================================
# QUESTION EVALUATION
# ============================================================

def evaluate_question(question_item, clos, plos):
    question = question_item["question"]

    # Best CLO
    clo_results = []

    for clo in clos:
        score = outcome_match_score(
            question,
            clo
        )

        clo_results.append(
            {
                "label": clo["label"],
                "description": clo["description"],
                "score": score,
            }
        )

    clo_results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    best_clo = clo_results[0]

    # Best PLO
    plo_results = []

    for plo in plos:
        score = outcome_match_score(
            question,
            plo
        )

        plo_results.append(
            {
                "label": plo["label"],
                "description": plo["description"],
                "score": score,
            }
        )

    plo_results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    best_plo = plo_results[0]

    question_bloom = detect_bloom(question)

    outcome_bloom = detect_bloom(
        best_clo["description"]
    )

    bloom = bloom_score(
        question_bloom,
        outcome_bloom
    )

    relevance = relevance_score(
        best_clo["score"],
        best_plo["score"]
    )

    clarity = clarity_score(question)

    measurability = measurability_score(question)

    # Simple six-metric weighting.
    overall = (
        best_clo["score"] * 0.20
        + best_plo["score"] * 0.15
        + bloom * 0.20
        + relevance * 0.15
        + clarity * 0.15
        + measurability * 0.15
    )

    overall = round(overall, 1)

    return {
        "number": question_item["number"],
        "question": question,
        "question_type": detect_question_type(question),
        "clo": best_clo["label"],
        "clo_description": best_clo["description"],
        "clo_score": best_clo["score"],
        "plo": best_plo["label"],
        "plo_description": best_plo["description"],
        "plo_score": best_plo["score"],
        "bloom": question_bloom or "Not Detected",
        "bloom_score": bloom,
        "relevance": relevance,
        "clarity": clarity,
        "measurability": measurability,
        "overall": overall,
        "status": metric_status(overall),
    }


# ============================================================
# ALTERNATIVE QUESTION GENERATION
# ============================================================

def outcome_topic(description):
    words = meaningful_words(description)

    if not words:
        return "the topic"

    # Keep a short list of meaningful content words.
    selected = list(words)[:7]

    return " ".join(selected)


def generate_alternatives(result):
    topic = outcome_topic(
        result["clo_description"]
    )

    bloom = result["bloom"]
    qtype = result["question_type"]

    if bloom == "Remember":
        templates = [
            f"Define the key concepts related to {topic}.",
            f"Identify the main elements of {topic}.",
            f"List the important characteristics of {topic}.",
        ]

    elif bloom == "Understand":
        templates = [
            f"Explain {topic} in your own words and provide a relevant example.",
            f"Describe the main features of {topic} and explain their importance.",
            f"Compare the key ideas related to {topic} using a suitable example.",
        ]

    elif bloom == "Apply":
        templates = [
            f"Apply the principles of {topic} to the given situation and explain your solution.",
            f"Use your knowledge of {topic} to solve the given problem.",
            f"Demonstrate how {topic} can be applied in a practical situation.",
        ]

    elif bloom == "Analyze":
        templates = [
            f"Analyze the main components of {topic} and explain how they are related.",
            f"Differentiate between the major elements of {topic} using relevant evidence.",
            f"Examine the given situation and analyze it using the principles of {topic}.",
        ]

    elif bloom == "Evaluate":
        templates = [
            f"Evaluate the effectiveness of the approach used for {topic} and justify your response.",
            f"Assess the given situation using appropriate criteria related to {topic}.",
            f"Justify your position about {topic} using relevant evidence.",
        ]

    else:
        templates = [
            f"Design a suitable solution based on the principles of {topic}.",
            f"Develop a practical approach for addressing a problem related to {topic}.",
            f"Create a suitable plan that demonstrates your understanding of {topic}.",
        ]

    # Slightly adapt the alternatives for numerical questions.
    if qtype == "Numerical / Problem Solving":
        templates = [
            f"Calculate the required result using the principles of {topic} and show your working.",
            f"Solve the given problem using an appropriate method related to {topic}.",
            f"Apply the relevant formula or procedure to determine the solution for {topic}.",
        ]

    return templates


# ============================================================
# SCORE TABLE
# ============================================================

def build_metric_table(result):
    rows = [
        {
            "Metric": "CLO Match",
            "Score": result["clo_score"],
            "Status": metric_status(result["clo_score"]),
        },
        {
            "Metric": "PLO Match",
            "Score": result["plo_score"],
            "Status": metric_status(result["plo_score"]),
        },
        {
            "Metric": "Bloom Level",
            "Score": result["bloom_score"],
            "Status": metric_status(result["bloom_score"]),
        },
        {
            "Metric": "Relevance",
            "Score": result["relevance"],
            "Status": metric_status(result["relevance"]),
        },
        {
            "Metric": "Clarity",
            "Score": result["clarity"],
            "Status": metric_status(result["clarity"]),
        },
        {
            "Metric": "Measurability",
            "Score": result["measurability"],
            "Status": metric_status(result["measurability"]),
        },
        {
            "Metric": "Overall Alignment",
            "Score": result["overall"],
            "Status": metric_status(result["overall"]),
        },
    ]

    return pd.DataFrame(rows)


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


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.title("🎓 OBE Alignment Checker")

    st.markdown(
        "Upload an assessment and enter its CLOs and PLOs "
        "to review alignment using simple, easy-to-read metrics."
    )

    st.divider()

    st.subheader("Score Guide")

    st.success("🟢 75–100%  Aligned")
    st.warning("🟡 50–74%  Review")
    st.error("🔴 0–49%  Needs Revision")

    st.divider()

    st.caption(
        "The evaluation uses transparent alignment indicators "
        "rather than treating every question as a single format."
    )


# ============================================================
# MAIN HEADER
# ============================================================

st.title("🎓 OBE Alignment Checker")

st.write(
    "Evaluate an assessment against its CLOs and PLOs using "
    "simple alignment metrics."
)


# ============================================================
# ASSESSMENT INFORMATION
# ============================================================

st.subheader("1. Assessment Information")

col1, col2, col3 = st.columns(3)

with col1:
    course_name = st.text_input(
        "Course / Subject",
        placeholder="e.g., Chemistry, English I, Mathematics"
    )

with col2:
    assessment_name = st.text_input(
        "Assessment Name",
        placeholder="e.g., Quiz 1, Assignment, Midterm"
    )

with col3:
    instructor_name = st.text_input(
        "Instructor",
        placeholder="Optional"
    )


# ============================================================
# CLO / PLO INPUT
# ============================================================

st.subheader("2. Learning Outcomes")

clo_col, plo_col = st.columns(2)

with clo_col:
    st.markdown("### CLOs")

    clo_text = st.text_area(
        "Enter CLOs",
        height=220,
        placeholder=(
            "CLO1: Explain the fundamental concepts of chemistry.\n"
            "CLO2: Apply chemical principles to solve problems.\n"
            "CLO3: Analyze experimental results."
        ),
        help="Use CLO1, CLO2, CLO3 etc."
    )

with plo_col:
    st.markdown("### PLOs")

    plo_text = st.text_area(
        "Enter PLOs",
        height=220,
        placeholder=(
            "PLO1: Apply knowledge of mathematics and science.\n"
            "PLO2: Analyze problems and develop appropriate solutions.\n"
            "PLO3: Communicate effectively."
        ),
        help="Use PLO1, PLO2, PLO3 etc."
    )


clos = parse_outcomes(clo_text, "CLO")
plos = parse_outcomes(plo_text, "PLO")


# ============================================================
# SHOW OUTCOMES
# ============================================================

if clos:
    with st.expander(
        f"View CLOs ({len(clos)})",
        expanded=False
    ):
        clo_df = pd.DataFrame(clos)
        clo_df.columns = ["CLO", "Description"]
        st.dataframe(
            clo_df,
            use_container_width=True,
            hide_index=True
        )

if plos:
    with st.expander(
        f"View PLOs ({len(plos)})",
        expanded=False
    ):
        plo_df = pd.DataFrame(plos)
        plo_df.columns = ["PLO", "Description"]
        st.dataframe(
            plo_df,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# FILE UPLOAD
# ============================================================

st.subheader("3. Upload Assessment")

uploaded_file = st.file_uploader(
    "Upload the complete assessment file",
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
        "webp",
    ],
    help="The tool will extract the assessment text and identify questions automatically."
)


# ============================================================
# READ FILE
# ============================================================

if uploaded_file is not None:

    st.info(
        f"File selected: **{uploaded_file.name}**"
    )

    if st.button(
        "📖 Read Assessment",
        use_container_width=True
    ):

        with st.spinner("Reading the complete assessment..."):

            text, error = extract_file_text(
                uploaded_file
            )

        if text.strip():

            st.session_state.assessment_text = text
            st.session_state.questions = extract_questions(text)
            st.session_state.results = []
            st.session_state.analyzed = False

            st.success(
                f"Assessment read successfully. "
                f"Extracted approximately {len(text.split())} words."
            )

        else:
            st.error(
                error or
                "No readable assessment text was found."
            )


# ============================================================
# TEXT PREVIEW
# ============================================================

if st.session_state.assessment_text:

    with st.expander(
        "📄 Preview Extracted Assessment",
        expanded=False
    ):
        st.text_area(
            "Extracted text",
            value=st.session_state.assessment_text[:30000],
            height=350,
            disabled=True
        )

    st.info(
        f"Detected questions: **{len(st.session_state.questions)}**"
    )


# ============================================================
# ANALYZE BUTTON
# ============================================================

st.subheader("4. Analyze Alignment")

if st.button(
    "🔎 Analyze Assessment",
    type="primary",
    use_container_width=True
):

    if not clos:
        st.error(
            "Please enter at least one CLO using labels such as CLO1, CLO2, CLO3."
        )
        st.stop()

    if not plos:
        st.error(
            "Please enter at least one PLO using labels such as PLO1, PLO2, PLO3."
        )
        st.stop()

    if not st.session_state.assessment_text:
        st.error(
            "Please upload and read an assessment first."
        )
        st.stop()

    if not st.session_state.questions:
        st.error(
            "No questions could be detected. Please check the extracted text."
        )
        st.stop()

    with st.spinner(
        "Analyzing CLO, PLO, Bloom, relevance, clarity and measurability..."
    ):

        results = []

        for question in st.session_state.questions:
            results.append(
                evaluate_question(
                    question,
                    clos,
                    plos
                )
            )

        st.session_state.results = results
        st.session_state.analyzed = True

    st.success(
        f"Analysis completed for {len(results)} questions."
    )


# ============================================================
# RESULTS
# ============================================================

if st.session_state.analyzed and st.session_state.results:

    results = st.session_state.results

    results_df = pd.DataFrame(results)

    # ========================================================
    # TOP SCORE
    # ========================================================

    st.divider()

    st.header("🌟 Assessment Alignment Score")

    overall_score = round(
        results_df["overall"].mean(),
        1
    )

    overall_status = metric_status(
        overall_score
    )

    # --------------------------------------------------------
    # Large visible score
    # --------------------------------------------------------

    if overall_status == "Aligned":

        st.success(
            f"🟢 OVERALL OBE ALIGNMENT: {overall_score:.1f}% — ALIGNED"
        )

    elif overall_status == "Review":

        st.warning(
            f"🟡 OVERALL OBE ALIGNMENT: {overall_score:.1f}% — REVIEW"
        )

    else:

        st.error(
            f"🔴 OVERALL OBE ALIGNMENT: {overall_score:.1f}% — NEEDS REVISION"
        )

    # --------------------------------------------------------
    # Metric cards
    # --------------------------------------------------------

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

    metric_values = [
        ("CLO Match", avg_clo),
        ("PLO Match", avg_plo),
        ("Bloom Level", avg_bloom),
        ("Relevance", avg_relevance),
        ("Clarity", avg_clarity),
        ("Measurability", avg_measurability),
    ]

    metric_columns = st.columns(6)

    for column, (label, score) in zip(
        metric_columns,
        metric_values
    ):

        with column:

            icon = status_icon(score)

            st.metric(
                label=f"{icon} {label}",
                value=f"{score:.0f}%"
            )

            status = metric_status(score)

            if status == "Aligned":
                st.success(
                    "Aligned",
                    icon="🟢"
                )

            elif status == "Review":
                st.warning(
                    "Review",
                    icon="🟡"
                )

            else:
                st.error(
                    "Needs Revision",
                    icon="🔴"
                )

    # ========================================================
    # SIMPLE SCORE TABLE
    # ========================================================

    st.subheader("📊 Alignment Summary")

    summary_df = pd.DataFrame(
        {
            "Metric": [
                "CLO Match",
                "PLO Match",
                "Bloom Level",
                "Relevance",
                "Clarity",
                "Measurability",
                "Overall Alignment",
            ],
            "Score": [
                avg_clo,
                avg_plo,
                avg_bloom,
                avg_relevance,
                avg_clarity,
                avg_measurability,
                overall_score,
            ],
        }
    )

    summary_df["Status"] = summary_df["Score"].apply(
        metric_status
    )

    summary_df["Score"] = summary_df["Score"].map(
        lambda x: f"{x:.1f}%"
    )

    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # SCORE GRAPH
    # ========================================================

    st.subheader("📈 Alignment Profile")

    chart_df = pd.DataFrame(
        {
            "Metric": [
                "CLO Match",
                "PLO Match",
                "Bloom Level",
                "Relevance",
                "Clarity",
                "Measurability",
                "Overall Alignment",
            ],
            "Score": [
                avg_clo,
                avg_plo,
                avg_bloom,
                avg_relevance,
                avg_clarity,
                avg_measurability,
                overall_score,
            ],
        }
    )

    chart_df = chart_df.set_index(
        "Metric"
    )

    st.bar_chart(
        chart_df,
        y="Score"
    )

    # ========================================================
    # STATUS COUNTS
    # ========================================================

    st.subheader("📌 Assessment Status")

    aligned_count = int(
        (results_df["overall"] >= 75).sum()
    )

    review_count = int(
        (
            (results_df["overall"] >= 50)
            & (results_df["overall"] < 75)
        ).sum()
    )

    revision_count = int(
        (results_df["overall"] < 50).sum()
    )

    status_cols = st.columns(3)

    with status_cols[0]:
        st.success(
            f"🟢 Aligned\n\n{aligned_count} questions"
        )

    with status_cols[1]:
        st.warning(
            f"🟡 Review\n\n{review_count} questions"
        )

    with status_cols[2]:
        st.error(
            f"🔴 Needs Revision\n\n{revision_count} questions"
        )

    # ========================================================
    # QUESTION TYPE DISTRIBUTION
    # ========================================================

    st.subheader("📝 Question-Type Distribution")

    type_counts = (
        results_df["question_type"]
        .value_counts()
        .rename_axis("Question Type")
        .reset_index(name="Questions")
    )

    type_cols = st.columns(2)

    with type_cols[0]:
        st.dataframe(
            type_counts,
            use_container_width=True,
            hide_index=True
        )

    with type_cols[1]:

        type_chart = type_counts.set_index(
            "Question Type"
        )

        st.bar_chart(
            type_chart,
            y="Questions"
        )

    # ========================================================
    # CLO MAPPING
    # ========================================================

    st.subheader("🎯 CLO Mapping")

    clo_summary = (
        results_df.groupby("clo")
        .agg(
            Questions=("number", "count"),
            Average_Match=("clo_score", "mean"),
            Average_Alignment=("overall", "mean"),
        )
        .reset_index()
    )

    clo_summary["Average_Match"] = (
        clo_summary["Average_Match"]
        .round(1)
    )

    clo_summary["Average_Alignment"] = (
        clo_summary["Average_Alignment"]
        .round(1)
    )

    clo_summary.columns = [
        "CLO",
        "Questions",
        "CLO Match %",
        "Overall Alignment %",
    ]

    st.dataframe(
        clo_summary,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # PLO MAPPING
    # ========================================================

    st.subheader("🎯 PLO Mapping")

    plo_summary = (
        results_df.groupby("plo")
        .agg(
            Questions=("number", "count"),
            Average_Match=("plo_score", "mean"),
            Average_Alignment=("overall", "mean"),
        )
        .reset_index()
    )

    plo_summary["Average_Match"] = (
        plo_summary["Average_Match"]
        .round(1)
    )

    plo_summary["Average_Alignment"] = (
        plo_summary["Average_Alignment"]
        .round(1)
    )

    plo_summary.columns = [
        "PLO",
        "Questions",
        "PLO Match %",
        "Overall Alignment %",
    ]

    st.dataframe(
        plo_summary,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # BLOOM DISTRIBUTION
    # ========================================================

    st.subheader("🧠 Bloom Level Distribution")

    bloom_counts = (
        results_df["bloom"]
        .value_counts()
        .rename_axis("Bloom Level")
        .reset_index(name="Questions")
    )

    st.dataframe(
        bloom_counts,
        use_container_width=True,
        hide_index=True
    )

    bloom_chart = bloom_counts.set_index(
        "Bloom Level"
    )

    st.bar_chart(
        bloom_chart,
        y="Questions"
    )

    # ========================================================
    # SELECTED QUESTION REVIEW
    # ========================================================

    st.divider()

    st.header("🔍 Selected Question Review")

    question_labels = [
        f"Q{row['number']}: {shorten_text(row['question'], 100)}"
        for row in results
    ]

    selected_index = st.selectbox(
        "Select a question to review",
        range(len(question_labels)),
        format_func=lambda i: question_labels[i]
    )

    selected = results[selected_index]

    st.markdown(
        f"### Question {selected['number']}"
    )

    st.info(
        selected["question"]
    )

    review_cols = st.columns(3)

    with review_cols[0]:
        st.write("**Question Type**")
        st.write(selected["question_type"])

    with review_cols[1]:
        st.write("**Mapped CLO**")
        st.write(selected["clo"])

    with review_cols[2]:
        st.write("**Mapped PLO**")
        st.write(selected["plo"])

    # --------------------------------------------------------
    # Selected question score
    # --------------------------------------------------------

    selected_status = metric_status(
        selected["overall"]
    )

    if selected_status == "Aligned":

        st.success(
            f"🟢 Question Alignment: "
            f"{selected['overall']:.1f}% — Aligned"
        )

    elif selected_status == "Review":

        st.warning(
            f"🟡 Question Alignment: "
            f"{selected['overall']:.1f}% — Review"
        )

    else:

        st.error(
            f"🔴 Question Alignment: "
            f"{selected['overall']:.1f}% — Needs Revision"
        )

    # --------------------------------------------------------
    # Selected question metrics
    # --------------------------------------------------------

    selected_metric_values = [
        ("CLO Match", selected["clo_score"]),
        ("PLO Match", selected["plo_score"]),
        ("Bloom Level", selected["bloom_score"]),
        ("Relevance", selected["relevance"]),
        ("Clarity", selected["clarity"]),
        ("Measurability", selected["measurability"]),
    ]

    selected_cols = st.columns(6)

    for column, (label, score) in zip(
        selected_cols,
        selected_metric_values
    ):

        with column:

            st.metric(
                label=f"{status_icon(score)} {label}",
                value=f"{score:.0f}%"
            )

    # --------------------------------------------------------
    # Selected question details
    # --------------------------------------------------------

    detail_cols = st.columns(2)

    with detail_cols[0]:

        st.markdown("#### CLO Mapping")

        st.write(
            f"**{selected['clo']}**"
        )

        st.write(
            selected["clo_description"]
        )

        st.caption(
            f"Match: {selected['clo_score']:.1f}%"
        )

    with detail_cols[1]:

        st.markdown("#### PLO Mapping")

        st.write(
            f"**{selected['plo']}**"
        )

        st.write(
            selected["plo_description"]
        )

        st.caption(
            f"Match: {selected['plo_score']:.1f}%"
        )

    bloom_cols = st.columns(2)

    with bloom_cols[0]:

        st.markdown("#### Bloom Level")

        st.write(
            selected["bloom"]
        )

    with bloom_cols[1]:

        st.markdown("#### Overall Alignment")

        st.write(
            f"{selected['overall']:.1f}%"
        )

    # ========================================================
    # IMPROVED ALTERNATIVES
    # ========================================================

    st.subheader("✨ Improved Question Alternatives")

    alternatives = generate_alternatives(
        selected
    )

    for index, alternative in enumerate(
        alternatives,
        start=1
    ):

        st.markdown(
            f"**Alternative {index}**"
        )

        st.info(
            alternative
        )

    # ========================================================
    # FULL QUESTION SUMMARY
    # ========================================================

    st.divider()

    st.header("📋 Assessment Question Summary")

    display_df = results_df[
        [
            "number",
            "question",
            "question_type",
            "clo",
            "plo",
            "bloom",
            "overall",
            "status",
        ]
    ].copy()

    display_df.columns = [
        "Question",
        "Assessment Question",
        "Question Type",
        "CLO",
        "PLO",
        "Bloom Level",
        "Alignment %",
        "Status",
    ]

    display_df["Assessment Question"] = (
        display_df["Assessment Question"]
        .apply(lambda x: shorten_text(x, 150))
    )

    display_df["Alignment %"] = (
        display_df["Alignment %"]
        .map(lambda x: f"{x:.1f}%")
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # EXPORT
    # ========================================================

    st.divider()

    st.header("📥 Export Results")

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
            "status",
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
        "Status",
    ]

    csv_data = export_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="⬇️ Download Alignment Report (CSV)",
        data=csv_data,
        file_name="OBE_Alignment_Report.csv",
        mime="text/csv",
        use_container_width=True
    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    st.divider()

    st.header("📌 Final Assessment Summary")

    final_col1, final_col2 = st.columns(2)

    with final_col1:

        st.metric(
            "Overall OBE Alignment",
            f"{overall_score:.1f}%"
        )

        st.write(
            f"**Status:** {status_icon(overall_score)} "
            f"{overall_status}"
        )

        st.write(
            f"**Questions analyzed:** {len(results)}"
        )

    with final_col2:

        st.write("**Key alignment indicators**")

        st.write(
            f"• CLO Match: {avg_clo:.1f}%"
        )

        st.write(
            f"• PLO Match: {avg_plo:.1f}%"
        )

        st.write(
            f"• Bloom Level: {avg_bloom:.1f}%"
        )

        st.write(
            f"• Relevance: {avg_relevance:.1f}%"
        )

        st.write(
            f"• Clarity: {avg_clarity:.1f}%"
        )

        st.write(
            f"• Measurability: {avg_measurability:.1f}%"
        )

else:

    st.info(
        "Upload your assessment, enter the CLOs and PLOs, "
        "read the file, and click **Analyze Assessment** "
        "to see the alignment score."
    )
