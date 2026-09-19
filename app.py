import streamlit as st
import pandas as pd
import re
import io
import os
import math
import textwrap
from difflib import SequenceMatcher
from collections import Counter

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Checker",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "questions": [],
    "results": [],
    "analysis_done": False,
    "assessment_text": "",
    "file_name": "",
    "revisions": {},
    "generated_questions": {},
    "clo_text": "",
    "plo_text": "",
    "subject": "",
    "course": "",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
    }

    .subtitle {
        color: #666;
        font-size: 1rem;
        margin-bottom: 1.2rem;
    }

    .metric-card {
        border: 1px solid #ddd;
        border-radius: 12px;
        padding: 16px;
        background: white;
        min-height: 120px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    }

    .metric-title {
        font-size: 0.9rem;
        color: #555;
        font-weight: 600;
    }

    .metric-score {
        font-size: 2rem;
        font-weight: 800;
        margin-top: 4px;
    }

    .metric-status {
        font-size: 0.85rem;
        margin-top: 4px;
    }

    .attained-box {
        padding: 16px;
        border-radius: 10px;
        background: #e9f8ef;
        border: 1px solid #75c991;
        color: #176b35;
        font-weight: 700;
    }

    .revision-box {
        padding: 16px;
        border-radius: 10px;
        background: #fff7e6;
        border: 1px solid #f0bd65;
        color: #875900;
        font-weight: 700;
    }

    .question-box {
        border: 1px solid #ddd;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 12px;
        background: #fff;
    }

    .weak-box {
        background: #fff7e6;
        border-left: 5px solid #f0ad4e;
        padding: 12px;
        border-radius: 6px;
        margin: 8px 0;
    }

    .strong-box {
        background: #eaf8ef;
        border-left: 5px solid #45a865;
        padding: 12px;
        border-radius: 6px;
        margin: 8px 0;
    }

    .generated-box {
        background: #f3f7ff;
        border: 1px solid #9db8ee;
        border-radius: 10px;
        padding: 15px;
        margin-top: 10px;
    }

    .revision-result {
        background: #f8f8ff;
        border: 1px solid #b6b6df;
        border-radius: 10px;
        padding: 15px;
        margin-top: 10px;
    }

    .section-title {
        margin-top: 20px;
        margin-bottom: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# BASIC TEXT UTILITIES
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\x00", " ")
    text = text.replace("\r", "\n")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


def normalize(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def words(text):
    return set(normalize(text).split())


def similarity(a, b):
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def keyword_tokens(text):
    stop_words = {
        "the", "a", "an", "and", "or", "of", "to", "in", "on",
        "for", "with", "by", "is", "are", "was", "were", "be",
        "as", "at", "from", "that", "this", "these", "those",
        "into", "using", "use", "used", "can", "may", "will",
        "students", "student", "question", "explain", "describe",
        "discuss", "identify", "define", "what", "how", "why",
        "which", "following"
    }

    return [
        w for w in re.findall(r"[A-Za-z]{3,}", normalize(text))
        if w not in stop_words
    ]


def keyword_overlap(a, b):
    wa = set(keyword_tokens(a))
    wb = set(keyword_tokens(b))

    if not wa or not wb:
        return 0.0

    return len(wa & wb) / max(1, min(len(wa), len(wb)))


# ============================================================
# FILE READING
# ============================================================

def read_pdf(uploaded_file):
    data = uploaded_file.getvalue()

    # PyMuPDF
    try:
        import fitz

        doc = fitz.open(stream=data, filetype="pdf")
        pages = []

        for page in doc:
            pages.append(page.get_text("text"))

        text = "\n".join(pages)

        if text.strip():
            return clean_text(text)

    except Exception:
        pass

    # pypdf
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = []

        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pass

        text = "\n".join(pages)

        if text.strip():
            return clean_text(text)

    except Exception:
        pass

    # pdfplumber
    try:
        import pdfplumber

        pages = []

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                try:
                    pages.append(page.extract_text() or "")
                except Exception:
                    pass

        text = "\n".join(pages)

        if text.strip():
            return clean_text(text)

    except Exception:
        pass

    # OCR fallback
    try:
        import fitz
        import pytesseract
        from PIL import Image

        doc = fitz.open(stream=data, filetype="pdf")
        pages = []

        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            pages.append(pytesseract.image_to_string(img))

        text = "\n".join(pages)

        if text.strip():
            return clean_text(text)

    except Exception:
        pass

    return ""


def read_docx(uploaded_file):
    try:
        from docx import Document

        doc = Document(io.BytesIO(uploaded_file.getvalue()))
        parts = []

        for p in doc.paragraphs:
            if p.text.strip():
                parts.append(p.text)

        for table in doc.tables:
            for row in table.rows:
                parts.append(" ".join(cell.text for cell in row.cells))

        return clean_text("\n".join(parts))

    except Exception:
        return ""


def read_pptx(uploaded_file):
    try:
        from pptx import Presentation

        prs = Presentation(io.BytesIO(uploaded_file.getvalue()))
        parts = []

        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    parts.append(shape.text)

        return clean_text("\n".join(parts))

    except Exception:
        return ""


def read_excel(uploaded_file):
    try:
        data = uploaded_file.getvalue()

        excel = pd.ExcelFile(io.BytesIO(data))
        parts = []

        for sheet in excel.sheet_names:
            df = pd.read_excel(io.BytesIO(data), sheet_name=sheet)

            parts.append(f"Sheet: {sheet}")

            for row in df.fillna("").astype(str).values.tolist():
                parts.append(" ".join(row))

        return clean_text("\n".join(parts))

    except Exception:
        return ""


def read_csv(uploaded_file):
    try:
        df = pd.read_csv(io.BytesIO(uploaded_file.getvalue()))

        parts = []

        for row in df.fillna("").astype(str).values.tolist():
            parts.append(" ".join(row))

        return clean_text("\n".join(parts))

    except Exception:
        return ""


def read_image(uploaded_file):
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(uploaded_file.getvalue()))
        return clean_text(pytesseract.image_to_string(image))

    except Exception:
        return ""


def read_text_file(uploaded_file):
    try:
        return clean_text(
            uploaded_file.getvalue().decode("utf-8", errors="ignore")
        )
    except Exception:
        return ""


def read_uploaded_file(uploaded_file):
    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        return read_pdf(uploaded_file)

    if name.endswith(".docx"):
        return read_docx(uploaded_file)

    if name.endswith(".pptx"):
        return read_pptx(uploaded_file)

    if name.endswith((".xlsx", ".xls", ".xlsm")):
        return read_excel(uploaded_file)

    if name.endswith(".csv"):
        return read_csv(uploaded_file)

    if name.endswith((".txt", ".md", ".rtf")):
        return read_text_file(uploaded_file)

    if name.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
        return read_image(uploaded_file)

    return ""


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def clean_question_candidate(block):
    block = clean_text(block)

    # Remove common answer-key material.
    block = re.split(
        r"\n\s*(?:Answer\s*Key|Answers?|Marking\s*Scheme|Rubric)\s*:?",
        block,
        maxsplit=1,
        flags=re.I,
    )[0]

    # Remove trailing marks.
    block = re.sub(
        r"\s*\(\s*\d+\s*(?:marks?|points?)\s*\)\s*$",
        "",
        block,
        flags=re.I,
    )

    block = re.sub(
        r"\s*\[\s*\d+\s*(?:marks?|points?)\s*\]\s*$",
        "",
        block,
        flags=re.I,
    )

    return block.strip()


def extract_questions(text):
    """
    Conservative extraction.

    If numbered questions are present, those numbered
    questions are authoritative.
    """

    text = clean_text(text)

    if not text:
        return []

    questions = []

    numbered_pattern = re.compile(
        r"(?im)^\s*"
        r"(?:Q(?:uestion)?\s*)?"
        r"(\d{1,3})"
        r"\s*[\.\):\-]\s+"
    )

    matches = list(numbered_pattern.finditer(text))

    if matches:
        for index, match in enumerate(matches):

            start = match.end()

            if index + 1 < len(matches):
                end = matches[index + 1].start()
            else:
                end = len(text)

            block = clean_text(text[start:end])

            block = re.split(
                r"\n\s*(?:OR|EITHER|CHOICE)\s*\n",
                block,
                maxsplit=1,
                flags=re.I,
            )[0]

            block = clean_question_candidate(block)

            if block and len(block.split()) >= 3:
                questions.append(block)

        unique_questions = []

        for question in questions:
            if not any(
                similarity(question, old) >= 0.92
                for old in unique_questions
            ):
                unique_questions.append(question)

        return unique_questions

    # --------------------------------------------------------
    # Fallback only when NO numbered questions exist.
    # --------------------------------------------------------

    blocks = re.split(r"\n\s*\n+", text)

    for block in blocks:

        block = clean_question_candidate(block)

        if len(block.split()) < 5:
            continue

        if re.search(
            r"\b(define|explain|describe|discuss|calculate|compare|"
            r"analyze|evaluate|design|identify|write|solve|"
            r"determine|what|why|how)\b",
            block,
            flags=re.I,
        ):
            questions.append(block)

    unique_questions = []

    for question in questions:
        if not any(
            similarity(question, old) >= 0.90
            for old in unique_questions
        ):
            unique_questions.append(question)

    return unique_questions


# ============================================================
# BLOOM TAXONOMY
# ============================================================

BLOOM_VERBS = {
    "Remember": [
        "define", "identify", "list", "name", "state",
        "recall", "recognize", "label", "select"
    ],

    "Understand": [
        "explain", "describe", "summarize", "interpret",
        "classify", "discuss", "illustrate", "paraphrase"
    ],

    "Apply": [
        "apply", "calculate", "solve", "demonstrate",
        "use", "implement", "execute", "perform"
    ],

    "Analyze": [
        "analyze", "analyse", "compare", "contrast",
        "differentiate", "examine", "investigate",
        "categorize", "deconstruct"
    ],

    "Evaluate": [
        "evaluate", "assess", "justify", "critique",
        "judge", "defend", "appraise", "recommend"
    ],

    "Create": [
        "design", "create", "develop", "construct",
        "formulate", "produce", "plan", "propose"
    ],
}


def detect_bloom(question):
    q = normalize(question)

    detected = []

    for level, verbs in BLOOM_VERBS.items():
        for verb in verbs:
            if re.search(r"\b" + re.escape(verb) + r"\b", q):
                detected.append(level)
                break

    if not detected:
        return "Understand"

    # Prefer highest-level explicit verb.
    priority = [
        "Create",
        "Evaluate",
        "Analyze",
        "Apply",
        "Understand",
        "Remember",
    ]

    for level in priority:
        if level in detected:
            return level

    return detected[0]


def bloom_level_number(level):
    levels = {
        "Remember": 1,
        "Understand": 2,
        "Apply": 3,
        "Analyze": 4,
        "Evaluate": 5,
        "Create": 6,
    }

    return levels.get(level, 2)


# ============================================================
# QUESTION TYPE DETECTION
# ============================================================

def detect_question_type(question):
    q = normalize(question)

    if re.search(
        r"\b(true or false|true false|t/f)\b",
        q
    ):
        return "True / False"

    if re.search(
        r"\b(fill in the blank|fill the blank|complete the sentence)\b",
        q
    ):
        return "Fill in the Blank"

    if re.search(
        r"\b(match|matching|column a|column b)\b",
        q
    ):
        return "Matching"

    if re.search(
        r"\b(case study|scenario|situation|given case)\b",
        q
    ):
        return "Case / Scenario"

    if re.search(
        r"\b(write code|program|programming|code|algorithm)\b",
        q
    ):
        return "Coding / Practical"

    if re.search(
        r"\b(calculate|compute|solve|numerical|find the value)\b",
        q
    ):
        return "Numerical"

    if re.search(
        r"\b(design|implement|perform|demonstrate|develop|construct)\b",
        q
    ):
        return "Practical / Application"

    if len(question.split()) > 45:
        return "Essay / Long Answer"

    return "Short Answer"


QUESTION_TYPES = [
    "MCQ",
    "True / False",
    "Fill in the Blank",
    "Matching",
    "Short Answer",
    "Essay / Long Answer",
    "Case / Scenario",
    "Numerical",
    "Practical / Application",
    "Coding / Practical",
]


# ============================================================
# SCORING
# ============================================================

def score_clo(question, clo):
    if not clo.strip():
        return None

    overlap = keyword_overlap(question, clo)

    if overlap >= 0.60:
        return 96
    if overlap >= 0.45:
        return 90
    if overlap >= 0.32:
        return 84
    if overlap >= 0.22:
        return 76
    if overlap >= 0.12:
        return 64

    return 45


def score_plo(question, plo):
    if not plo.strip():
        return None

    overlap = keyword_overlap(question, plo)

    if overlap >= 0.55:
        return 96
    if overlap >= 0.42:
        return 90
    if overlap >= 0.30:
        return 84
    if overlap >= 0.20:
        return 76
    if overlap >= 0.10:
        return 64

    return 45


def score_bloom(question, clo, plo):
    level = detect_bloom(question)

    qwords = keyword_tokens(question)

    if not qwords:
        return 50

    explicit = any(
        re.search(
            r"\b" + re.escape(verb) + r"\b",
            normalize(question)
        )
        for verbs in BLOOM_VERBS.values()
        for verb in verbs
    )

    if explicit:
        return 94

    if len(qwords) >= 8:
        return 82

    if len(qwords) >= 5:
        return 75

    return 60


def subject_relevance_score(question, subject, course):
    reference = " ".join(
        x for x in [subject, course]
        if x and x.strip()
    )

    if not reference.strip():
        return 75

    overlap = keyword_overlap(question, reference)

    if overlap >= 0.60:
        return 98
    if overlap >= 0.45:
        return 92
    if overlap >= 0.30:
        return 85
    if overlap >= 0.20:
        return 78
    if overlap >= 0.10:
        return 65

    return 48


def clarity_score(question):
    q = clean_text(question)

    if not q:
        return 0

    score = 100

    if len(q.split()) < 5:
        score -= 20

    if len(q.split()) > 120:
        score -= 10

    if q.count("?") > 2:
        score -= 8

    if re.search(r"\b(etc|and so on)\b", q, re.I):
        score -= 8

    if re.search(r"\s{2,}", q):
        score -= 5

    if not re.search(
        r"\b(what|why|how|explain|describe|identify|"
        r"calculate|analyze|analyse|compare|evaluate|"
        r"design|develop|solve|discuss|write|determine)\b",
        q,
        re.I,
    ):
        score -= 12

    return max(0, min(100, score))


def measurability_score(question):
    q = normalize(question)

    measurable_verbs = [
        "define", "identify", "list", "explain", "describe",
        "calculate", "solve", "apply", "compare", "contrast",
        "analyze", "analyse", "evaluate", "justify", "design",
        "develop", "construct", "implement", "write", "determine",
        "classify", "demonstrate", "interpret", "recommend",
    ]

    hits = sum(
        1 for verb in measurable_verbs
        if re.search(r"\b" + re.escape(verb) + r"\b", q)
    )

    if hits >= 2:
        return 96

    if hits == 1:
        return 88

    if len(q.split()) >= 8:
        return 74

    return 58


def evaluate_question(
    question,
    clo,
    plo,
    subject,
    course,
    target_bloom=None,
):
    bloom_actual = detect_bloom(question)

    clo_score = score_clo(question, clo)
    plo_score = score_plo(question, plo)
    bloom_score = score_bloom(question, clo, plo)
    subject_score = subject_relevance_score(
        question, subject, course
    )
    clarity = clarity_score(question)
    measurable = measurability_score(question)

    metrics = {
        "CLO Alignment": clo_score,
        "PLO Alignment": plo_score,
        "Bloom Alignment": bloom_score,
        "Subject Relevance": subject_score,
        "Clarity": clarity,
        "Measurability": measurable,
    }

    values = [
        value
        for value in metrics.values()
        if value is not None
    ]

    overall = round(sum(values) / len(values)) if values else 0

    if target_bloom:
        if bloom_actual == target_bloom:
            bloom_score = max(bloom_score, 92)
        else:
            target_number = bloom_level_number(target_bloom)
            actual_number = bloom_level_number(bloom_actual)

            difference = abs(target_number - actual_number)

            if difference == 1:
                bloom_score = min(bloom_score, 78)
            elif difference >= 2:
                bloom_score = min(bloom_score, 60)

            metrics["Bloom Alignment"] = bloom_score
            values = [
                value
                for value in metrics.values()
                if value is not None
            ]
            overall = round(sum(values) / len(values))

    return {
        "question": question,
        "overall": overall,
        "metrics": metrics,
        "actual_bloom": bloom_actual,
        "target_bloom": target_bloom,
        "question_type": detect_question_type(question),
    }


# ============================================================
# STATUS
# ============================================================

def get_status(score):
    if score is None:
        return "Not Available"

    if score >= 85:
        return "Strong"

    if score >= 80:
        return "Attained"

    if score >= 60:
        return "Needs Attention"

    if score >= 40:
        return "Weak"

    return "Poor"


def get_weak_metrics(result):
    weak = []

    for metric, value in result["metrics"].items():

        if value is None:
            continue

        if value < 80:
            weak.append(
                {
                    "metric": metric,
                    "score": value,
                    "status": get_status(value),
                }
            )

    weak.sort(key=lambda x: x["score"])

    return weak


# ============================================================
# GENERATION HELPERS
# ============================================================

def extract_topic(question, subject):
    qwords = keyword_tokens(question)

    if subject:
        subject_words = set(keyword_tokens(subject))
        qwords = [
            w for w in qwords
            if w not in subject_words
        ]

    if not qwords:
        return subject or "the selected topic"

    return " ".join(qwords[:8])


def get_focus_terms(clo, plo, question):
    terms = []

    for source in [clo, plo, question]:
        for word in keyword_tokens(source):
            if word not in terms:
                terms.append(word)

    return terms[:10]


def bloom_instruction(level):
    instructions = {
        "Remember":
            "require recall, identification, naming, or listing",
        "Understand":
            "require explanation, interpretation, or description",
        "Apply":
            "require the learner to use knowledge in a specific situation or problem",
        "Analyze":
            "require comparison, examination of components, relationships, or evidence",
        "Evaluate":
            "require a justified judgment using criteria or evidence",
        "Create":
            "require the learner to design, develop, formulate, or construct an original solution",
    }

    return instructions.get(
        level,
        instructions["Understand"]
    )


def generate_mcq(topic, clo, plo, bloom):
    return (
        f"In the context of {topic}, which option best demonstrates "
        f"the ability to {bloom_instruction(bloom)} while addressing "
        f"the intended learning outcome?"
        "\n\n"
        "A. Apply the relevant concept to the given context\n"
        "B. State an unrelated definition\n"
        "C. List terms without applying them\n"
        "D. Repeat a memorized statement"
    )


def generate_true_false(topic, clo, plo, bloom):
    return (
        f"True or False: A learner addressing the learning outcome on "
        f"{topic} should be able to {bloom_instruction(bloom)} "
        f"rather than only recall an isolated fact."
    )


def generate_fill_blank(topic, clo, plo, bloom):
    return (
        f"Complete the statement: To demonstrate the learning outcome "
        f"related to {topic}, a student should be able to "
        f"__________ the relevant concept in an appropriate context."
    )


def generate_matching(topic, clo, plo, bloom):
    return (
        f"Match each concept related to {topic} with the description, "
        f"application, or outcome that best demonstrates the learner's "
        f"ability to {bloom_instruction(bloom)}."
    )


def generate_short_answer(topic, clo, plo, bloom):
    return (
        f"Explain how you would {bloom_instruction(bloom)} in relation "
        f"to {topic}. Use relevant concepts and evidence to support "
        f"your response."
    )


def generate_essay(topic, clo, plo, bloom):
    return (
        f"Discuss {topic} in detail and demonstrate how a learner can "
        f"{bloom_instruction(bloom)}. Support the response with relevant "
        f"concepts, examples, evidence, or justification."
    )


def generate_case(topic, clo, plo, bloom):
    return (
        f"Case/Scenario: A situation has arisen involving {topic}. "
        f"Using the concepts covered in the course, determine how you "
        f"would {bloom_instruction(bloom)}. Explain the reasoning behind "
        f"your response and relate it to the intended learning outcome."
    )


def generate_numerical(topic, clo, plo, bloom):
    return (
        f"Numerical/Application Problem: Consider a problem involving "
        f"{topic}. Use the relevant formula, method, or procedure to "
        f"solve the problem and explain how your result demonstrates "
        f"the intended learning outcome."
    )


def generate_practical(topic, clo, plo, bloom):
    return (
        f"Practical Task: Using a realistic situation involving {topic}, "
        f"demonstrate how you would {bloom_instruction(bloom)}. "
        f"State the steps, decisions, or evidence that would be used "
        f"to complete the task."
    )


def generate_coding(topic, clo, plo, bloom):
    return (
        f"Coding/Practical Task: Develop a solution related to {topic} "
        f"that requires you to {bloom_instruction(bloom)}. "
        f"Explain the logic of your solution and identify the expected "
        f"result."
    )


def generate_question_by_type(
    question_type,
    topic,
    clo,
    plo,
    bloom,
):
    generators = {
        "MCQ": generate_mcq,
        "True / False": generate_true_false,
        "Fill in the Blank": generate_fill_blank,
        "Matching": generate_matching,
        "Short Answer": generate_short_answer,
        "Essay / Long Answer": generate_essay,
        "Case / Scenario": generate_case,
        "Numerical": generate_numerical,
        "Practical / Application": generate_practical,
        "Coding / Practical": generate_coding,
    }

    generator = generators.get(
        question_type,
        generate_short_answer
    )

    return generator(
        topic,
        clo,
        plo,
        bloom,
    )


# ============================================================
# REVISION
# ============================================================

def improve_existing_question(
    question,
    weak_metrics,
    clo,
    plo,
    subject,
    course,
    bloom,
    question_type,
):
    topic = extract_topic(question, subject)

    weak_names = [
        item["metric"]
        for item in weak_metrics
    ]

    # Specific transformations based on the actual weak metrics.
    revised = question.strip()

    if "Bloom Alignment" in weak_names:
        revised = (
            f"{bloom_instruction(bloom).capitalize()} "
            f"the following task in relation to {topic}: "
            f"{revised}"
        )

    if "CLO Alignment" in weak_names:
        revised += (
            f"\n\nYour response must explicitly demonstrate the "
            f"learning outcome: {clo}"
        )

    if "PLO Alignment" in weak_names:
        revised += (
            f"\n\nRelate your answer to the broader programme outcome: "
            f"{plo}"
        )

    if "Measurability" in weak_names:
        revised += (
            "\n\nSupport your response with a specific example, "
            "calculation, comparison, justification, design, or other "
            "observable evidence appropriate to the task."
        )

    if "Clarity" in weak_names:
        revised = (
            f"Using {topic}, {bloom_instruction(bloom)}. "
            f"Clearly state the relevant concepts, evidence, "
            f"steps, or reasoning in your response."
        )

    if "Subject Relevance" in weak_names:
        revised = (
            f"In the subject area of {subject or course or topic}, "
            f"{bloom_instruction(bloom)} using the concepts related "
            f"to {topic}. "
            f"Explain your response with subject-specific evidence."
        )

    # If the original question is extremely short,
    # create a fuller version.
    if len(revised.split()) < 10:
        revised = generate_question_by_type(
            question_type,
            topic,
            clo,
            plo,
            bloom,
        )

    return revised


# ============================================================
# CANDIDATE GENERATION
# ============================================================

def create_candidate_set(
    original_question,
    clo,
    plo,
    subject,
    course,
    target_bloom,
    question_type,
):
    candidates = []

    topic = extract_topic(
        original_question,
        subject
    )

    # Candidate 1: new question
    candidates.append(
        generate_question_by_type(
            question_type,
            topic,
            clo,
            plo,
            target_bloom,
        )
    )

    # Candidate 2: focus on CLO
    candidates.append(
        (
            f"Using the concepts related to {topic}, "
            f"{bloom_instruction(target_bloom)} "
            f"to demonstrate the following CLO: {clo}. "
            f"Relate your response to the relevant PLO: {plo}."
        )
    )

    # Candidate 3: application-focused
    candidates.append(
        (
            f"Consider a realistic situation involving {topic}. "
            f"Apply the relevant knowledge to {bloom_instruction(target_bloom)}. "
            f"Your response should demonstrate this CLO: {clo}."
        )
    )

    # Candidate 4: analytical
    candidates.append(
        (
            f"Analyze the key issue associated with {topic} and "
            f"provide evidence-based reasoning that demonstrates "
            f"the intended learning outcome: {clo}."
        )
    )

    # Candidate 5: explicit measurable task
    candidates.append(
        (
            f"For {topic}, complete a measurable task that requires you "
            f"to {bloom_instruction(target_bloom)}. "
            f"State the evidence or result that would demonstrate "
            f"achievement of the CLO: {clo}."
        )
    )

    # Remove candidates too similar to original.
    filtered = []

    for candidate in candidates:
        if similarity(candidate, original_question) < 0.78:
            if not any(
                similarity(candidate, old) >= 0.88
                for old in filtered
            ):
                filtered.append(candidate)

    return filtered


def generate_best_candidate(
    original_question,
    clo,
    plo,
    subject,
    course,
    target_bloom,
    question_type,
):
    candidates = create_candidate_set(
        original_question,
        clo,
        plo,
        subject,
        course,
        target_bloom,
        question_type,
    )

    if not candidates:
        candidates = [
            generate_question_by_type(
                question_type,
                extract_topic(original_question, subject),
                clo,
                plo,
                target_bloom,
            )
        ]

    evaluated = []

    for candidate in candidates:

        result = evaluate_question(
            candidate,
            clo,
            plo,
            subject,
            course,
            target_bloom=target_bloom,
        )

        evaluated.append(
            (candidate, result)
        )

    evaluated.sort(
        key=lambda item: item[1]["overall"],
        reverse=True,
    )

    return evaluated[0]


# ============================================================
# OVERALL METRICS
# ============================================================

def calculate_metric_averages(results):
    metric_values = {}

    for result in results:

        for metric, value in result["metrics"].items():

            if value is None:
                continue

            metric_values.setdefault(
                metric,
                []
            ).append(value)

    averages = {}

    for metric, values in metric_values.items():
        if values:
            averages[metric] = round(
                sum(values) / len(values)
            )

    return averages


def overall_score(results):
    if not results:
        return 0

    values = [
        result["overall"]
        for result in results
        if result.get("overall") is not None
    ]

    if not values:
        return 0

    return round(sum(values) / len(values))


def collect_overall_weak_areas(results):
    averages = calculate_metric_averages(results)

    weak = []

    for metric, value in averages.items():
        if value < 80:
            weak.append(
                {
                    "metric": metric,
                    "score": value,
                    "status": get_status(value),
                }
            )

    weak.sort(
        key=lambda x: x["score"]
    )

    return weak


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## 🎓 OBE Quiz Checker")

    st.markdown(
        "Evaluate assessment questions against CLO, PLO, "
        "Bloom's Taxonomy and assessment-quality indicators."
    )

    st.divider()

    st.markdown("### 1. Course Information")

    subject = st.text_input(
        "Subject",
        value=st.session_state.subject,
        placeholder="e.g. Chemistry, English, Computer Science",
    )

    course = st.text_input(
        "Course",
        value=st.session_state.course,
        placeholder="e.g. General Chemistry",
    )

    st.markdown("### 2. Learning Outcomes")

    clo = st.text_area(
        "CLO",
        value=st.session_state.clo_text,
        height=120,
        placeholder="Enter the Course Learning Outcome...",
    )

    plo = st.text_area(
        "PLO",
        value=st.session_state.plo_text,
        height=120,
        placeholder="Enter the Programme Learning Outcome...",
    )

    st.markdown("### 3. Assessment")

    uploaded_file = st.file_uploader(
        "Upload complete assessment",
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
        ],
    )

    analyze_button = st.button(
        "🔍 Analyze Assessment",
        type="primary",
        use_container_width=True,
    )

    if st.button(
        "🗑️ Reset",
        use_container_width=True,
    ):
        for key, value in DEFAULT_STATE.items():
            st.session_state[key] = value

        st.rerun()


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🎓 OBE Quiz Checker</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    "Assessment alignment and question improvement tool"
    "</div>",
    unsafe_allow_html=True,
)


# ============================================================
# ANALYZE
# ============================================================

if analyze_button:

    if not clo.strip():
        st.error("Please enter a CLO before analyzing.")

    elif not plo.strip():
        st.error("Please enter a PLO before analyzing.")

    elif not uploaded_file:
        st.error("Please upload an assessment file.")

    else:

        with st.spinner("Reading and analyzing the assessment..."):

            assessment_text = read_uploaded_file(
                uploaded_file
            )

            if not assessment_text:
                st.error(
                    "The assessment file could not be read. "
                    "For scanned PDFs/images, make sure OCR support "
                    "is installed."
                )

                st.stop()

            extracted_questions = extract_questions(
                assessment_text
            )

            if not extracted_questions:

                st.error(
                    "No assessment questions could be extracted. "
                    "Please check the file format and question numbering."
                )

                st.stop()

            st.session_state.questions = extracted_questions
            st.session_state.results = []
            st.session_state.revisions = {}
            st.session_state.generated_questions = {}
            st.session_state.assessment_text = assessment_text
            st.session_state.file_name = uploaded_file.name
            st.session_state.clo_text = clo
            st.session_state.plo_text = plo
            st.session_state.subject = subject
            st.session_state.course = course

            for question in extracted_questions:

                result = evaluate_question(
                    question,
                    clo,
                    plo,
                    subject,
                    course,
                )

                st.session_state.results.append(
                    result
                )

            st.session_state.analysis_done = True

        st.success(
            f"Assessment analyzed successfully. "
            f"{len(extracted_questions)} question(s) detected."
        )


# ============================================================
# BEFORE ANALYSIS
# ============================================================

if not st.session_state.analysis_done:

    st.info(
        "⏳ Upload an assessment, enter the CLO and PLO, "
        "then click **Analyze Assessment**."
    )

    st.stop()


# ============================================================
# TOP INFORMATION
# ============================================================

st.info(
    f"📄 **{st.session_state.file_name}** — "
    f"{len(st.session_state.questions)} question(s) detected."
)


# ============================================================
# OVERALL DASHBOARD — TOP
# ============================================================

st.markdown("## 📊 Overall Alignment Dashboard")

total_score = overall_score(
    st.session_state.results
)

averages = calculate_metric_averages(
    st.session_state.results
)

overall_status = get_status(
    total_score
)

if total_score >= 80:
    st.markdown(
        f'<div class="attained-box">'
        f"🟢 Alignment Attained — Overall Score: "
        f"{total_score}/100"
        f"</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f'<div class="revision-box">'
        f"🟠 Revision Required — Overall Score: "
        f"{total_score}/100"
        f"</div>",
        unsafe_allow_html=True,
    )


st.markdown("### Overall Metrics")


metric_order = [
    "CLO Alignment",
    "PLO Alignment",
    "Bloom Alignment",
    "Subject Relevance",
    "Clarity",
    "Measurability",
]


metric_columns = st.columns(3)

for index, metric in enumerate(metric_order):

    value = averages.get(metric)

    with metric_columns[index % 3]:

        if value is None:
            display_score = "N/A"
            status = "Not Available"
        else:
            display_score = f"{value}/100"
            status = get_status(value)

        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">{metric}</div>
                <div class="metric-score">{display_score}</div>
                <div class="metric-status">{status}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# OVERALL WEAK AREAS
# ============================================================

st.markdown("### Overall Areas Requiring Attention")

overall_weak = collect_overall_weak_areas(
    st.session_state.results
)

if overall_weak:

    weak_text = []

    for item in overall_weak:
        weak_text.append(
            f"**{item['metric']} — {item['score']}/100 "
            f"({item['status']})**"
        )

    st.markdown(
        '<div class="weak-box">'
        "The following metrics are below the 80/100 attainment threshold:"
        "<br><br>"
        + "<br>".join(weak_text)
        + "</div>",
        unsafe_allow_html=True,
    )

else:

    st.markdown(
        '<div class="strong-box">'
        "🟢 All overall alignment metrics have reached at least 80/100."
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# ONE GRAPH ONLY
# ============================================================

st.markdown("### Alignment Overview")

chart_data = pd.DataFrame(
    {
        "Metric": metric_order,
        "Score": [
            averages.get(metric, 0)
            for metric in metric_order
        ],
    }
)

st.bar_chart(
    chart_data.set_index("Metric"),
    y="Score",
    height=350,
)


# ============================================================
# QUESTION SUMMARY
# ============================================================

st.markdown("## 📋 Question Summary")

summary_rows = []

for index, result in enumerate(
    st.session_state.results,
    start=1,
):

    summary_rows.append(
        {
            "Question": f"Q{index}",
            "Type": result["question_type"],
            "Bloom": result["actual_bloom"],
            "CLO": (
                result["metrics"]["CLO Alignment"]
                if result["metrics"]["CLO Alignment"] is not None
                else "-"
            ),
            "PLO": (
                result["metrics"]["PLO Alignment"]
                if result["metrics"]["PLO Alignment"] is not None
                else "-"
            ),
            "Bloom Score": result["metrics"]["Bloom Alignment"],
            "Subject": result["metrics"]["Subject Relevance"],
            "Clarity": result["metrics"]["Clarity"],
            "Measurability": result["metrics"]["Measurability"],
            "Overall": result["overall"],
            "Status": get_status(result["overall"]),
        }
    )

summary_df = pd.DataFrame(summary_rows)

st.dataframe(
    summary_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# QUESTIONS REVIEW — AT THE END
# ============================================================

st.markdown("---")
st.markdown("## 🔎 Questions Review")

st.caption(
    "Detailed question analysis and improvement tools are placed here "
    "after the overall assessment metrics."
)


for index, result in enumerate(
    st.session_state.results,
    start=1,
):

    number = index
    question = result["question"]

    st.markdown(
        f"### Question {number}"
    )

    st.markdown(
        '<div class="question-box">'
        f"<strong>Original Question</strong><br><br>"
        f"{question}"
        "</div>",
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # Current score
    # --------------------------------------------------------

    current_score = result["overall"]

    if current_score >= 80:
        st.success(
            f"Current Score: {current_score}/100 — "
            f"{get_status(current_score)}"
        )
    else:
        st.warning(
            f"Current Score: {current_score}/100 — "
            f"{get_status(current_score)}"
        )

    # --------------------------------------------------------
    # Individual metrics
    # --------------------------------------------------------

    st.markdown("#### Current Question Metrics")

    qmetric_cols = st.columns(3)

    for metric_index, metric in enumerate(metric_order):

        value = result["metrics"].get(metric)

        with qmetric_cols[metric_index % 3]:

            if value is None:
                st.metric(
                    metric,
                    "N/A"
                )
            else:
                st.metric(
                    metric,
                    f"{value}/100"
                )

    # --------------------------------------------------------
    # Bloom and question type
    # --------------------------------------------------------

    info_col1, info_col2 = st.columns(2)

    with info_col1:
        st.write(
            f"**Actual Bloom Level:** "
            f"{result['actual_bloom']}"
        )

    with info_col2:
        st.write(
            f"**Detected Question Type:** "
            f"{result['question_type']}"
        )

    # --------------------------------------------------------
    # Specific weak areas
    # --------------------------------------------------------

    weak_metrics = get_weak_metrics(
        result
    )

    st.markdown("#### Specific Weak Areas")

    if weak_metrics:

        for item in weak_metrics:

            st.markdown(
                f"""
                <div class="weak-box">
                <strong>{item['metric']}</strong>:
                {item['score']}/100 —
                {item['status']}
                </div>
                """,
                unsafe_allow_html=True,
            )

    else:

        st.markdown(
            '<div class="strong-box">'
            "🟢 No individual metric is below 80/100."
            "</div>",
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # Improvement controls
    # --------------------------------------------------------

    st.markdown("### 🛠️ Improve This Question")

    control_col1, control_col2 = st.columns(2)

    with control_col1:

        selected_bloom = st.selectbox(
            "Target Bloom Level",
            list(BLOOM_VERBS.keys()),
            index=list(BLOOM_VERBS.keys()).index(
                result["actual_bloom"]
            ),
            key=f"bloom_{number}",
        )

    with control_col2:

        detected_type = result["question_type"]

        default_type_index = (
            QUESTION_TYPES.index(detected_type)
            if detected_type in QUESTION_TYPES
            else QUESTION_TYPES.index("Short Answer")
        )

        selected_type = st.selectbox(
            "Question Type",
            QUESTION_TYPES,
            index=default_type_index,
            key=f"type_{number}",
        )

    # --------------------------------------------------------
    # PROMINENT GENERATE / REVISE BUTTONS
    # --------------------------------------------------------

    st.markdown("#### ✨ Create an Improved Assessment Item")

    generate_col, revise_col = st.columns(2)

    with generate_col:

        generate_clicked = st.button(
            "✨ GENERATE NEW QUESTION",
            key=f"generate_{number}",
            type="primary",
            use_container_width=True,
        )

    with revise_col:

        revise_clicked = st.button(
            "🔄 REVISE CURRENT QUESTION",
            key=f"revise_{number}",
            use_container_width=True,
        )

    # --------------------------------------------------------
    # GENERATE NEW QUESTION
    # --------------------------------------------------------

    if generate_clicked:

        with st.spinner(
            f"Generating a new question for Question {number}..."
        ):

            new_question, new_result = generate_best_candidate(
                question,
                clo,
                plo,
                subject,
                course,
                selected_bloom,
                selected_type,
            )

            st.session_state.generated_questions[
                number
            ] = {
                "question": new_question,
                "result": new_result,
                "target_bloom": selected_bloom,
                "question_type": selected_type,
            }

    # --------------------------------------------------------
    # REVISE CURRENT QUESTION
    # --------------------------------------------------------

    if revise_clicked:

        with st.spinner(
            f"Revising Question {number}..."
        ):

            revised_question = improve_existing_question(
                question,
                weak_metrics,
                clo,
                plo,
                subject,
                course,
                selected_bloom,
                selected_type,
            )

            revised_result = evaluate_question(
                revised_question,
                clo,
                plo,
                subject,
                course,
                target_bloom=selected_bloom,
            )

            st.session_state.revisions[
                number
            ] = {
                "question": revised_question,
                "result": revised_result,
                "target_bloom": selected_bloom,
                "question_type": selected_type,
            }

    # --------------------------------------------------------
    # DISPLAY GENERATED QUESTION
    # --------------------------------------------------------

    generated = st.session_state.generated_questions.get(
        number
    )

    if generated:

        generated_result = generated["result"]

        st.markdown("#### ✨ Generated New Question")

        st.markdown(
            f"""
            <div class="generated-box">
            {generated["question"]}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.write(
            f"**Target Bloom:** "
            f"{generated['target_bloom']}  |  "
            f"**Question Type:** "
            f"{generated['question_type']}"
        )

        generated_score = generated_result["overall"]

        if generated_score >= 80:

            st.success(
                f"🟢 Alignment Attained — "
                f"Generated Question Score: "
                f"{generated_score}/100"
            )

        else:

            st.warning(
                f"Generated Question Score: "
                f"{generated_score}/100 — "
                f"{get_status(generated_score)}. "
                f"Still below 80/100."
            )

        generated_metric_cols = st.columns(3)

        for metric_index, metric in enumerate(metric_order):

            value = generated_result["metrics"].get(
                metric
            )

            with generated_metric_cols[
                metric_index % 3
            ]:

                if value is not None:
                    st.metric(
                        metric,
                        f"{value}/100"
                    )

        generated_weak = get_weak_metrics(
            generated_result
        )

        if generated_weak:

            st.markdown("**Remaining Weak Areas:**")

            for item in generated_weak:

                st.write(
                    f"- {item['metric']}: "
                    f"{item['score']}/100 "
                    f"({item['status']})"
                )

        else:

            st.success(
                "All individual metrics for the generated "
                "question are at least 80/100."
            )

    # --------------------------------------------------------
    # DISPLAY REVISED QUESTION
    # --------------------------------------------------------

    revised = st.session_state.revisions.get(
        number
    )

    if revised:

        revised_result = revised["result"]

        st.markdown("#### 🔄 Revised Question")

        st.markdown(
            f"""
            <div class="revision-result">
            {revised["question"]}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.write(
            f"**Target Bloom:** "
            f"{revised['target_bloom']}  |  "
            f"**Question Type:** "
            f"{revised['question_type']}"
        )

        revised_score = revised_result["overall"]

        if revised_score >= 80:

            st.success(
                f"🟢 Alignment Attained — "
                f"Revised Question Score: "
                f"{revised_score}/100"
            )

        else:

            st.warning(
                f"Revised Question Score: "
                f"{revised_score}/100 — "
                f"{get_status(revised_score)}. "
                f"Still below 80/100."
            )

        revised_metric_cols = st.columns(3)

        for metric_index, metric in enumerate(metric_order):

            value = revised_result["metrics"].get(
                metric
            )

            with revised_metric_cols[
                metric_index % 3
            ]:

                if value is not None:
                    st.metric(
                        metric,
                        f"{value}/100"
                    )

        revised_weak = get_weak_metrics(
            revised_result
        )

        if revised_weak:

            st.markdown("**Remaining Weak Areas:**")

            for item in revised_weak:

                st.write(
                    f"- {item['metric']}: "
                    f"{item['score']}/100 "
                    f"({item['status']})"
                )

        else:

            st.success(
                "All individual metrics for the revised "
                "question are at least 80/100."
            )

    st.divider()


# ============================================================
# FOOTER
# ============================================================

st.caption(
    "OBE Quiz Checker • Independent CLO, PLO, Bloom, "
    "Subject Relevance, Clarity and Measurability analysis"
)
