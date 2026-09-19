import streamlit as st
import pandas as pd
import io
import re
import random
from difflib import SequenceMatcher


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OBE Quiz Checker",
    page_icon="🎓",
    layout="wide",
)


# ============================================================
# CONSTANTS
# ============================================================

ATTAINMENT_THRESHOLD = 80

METRIC_ORDER = [
    "CLO Alignment",
    "PLO Alignment",
    "Bloom Alignment",
    "Subject Relevance",
    "Clarity",
    "Measurability",
]

BLOOM_LEVELS = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create",
]

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

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in",
    "on", "for", "with", "by", "is", "are", "was",
    "were", "be", "as", "at", "from", "that", "this",
    "these", "those", "into", "using", "use", "used",
    "can", "may", "will", "student", "students",
    "question", "questions", "following", "given",
    "following", "answer", "explain", "describe",
}


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "questions": [],
    "results": [],
    "analysis_done": False,
    "assessment_text": "",
    "file_name": "",
    "clo_text": "",
    "plo_text": "",
    "subject": "",
    "course": "",
    "revisions": {},
    "generated_questions": {},
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# PAGE STYLE
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 2.25rem;
        font-weight: 800;
        margin-bottom: 0.1rem;
    }

    .subtitle {
        color: #666666;
        margin-bottom: 1.2rem;
    }

    .metric-card {
        border: 1px solid #dddddd;
        border-radius: 12px;
        padding: 15px;
        background: white;
        min-height: 115px;
        margin-bottom: 10px;
    }

    .metric-title {
        font-size: 0.88rem;
        color: #555555;
        font-weight: 650;
    }

    .metric-score {
        font-size: 1.9rem;
        font-weight: 800;
    }

    .question-box {
        border: 1px solid #dddddd;
        border-radius: 12px;
        padding: 18px;
        background: white;
        margin-bottom: 12px;
    }

    .suggestion-box {
        border: 1px solid #b9c9e5;
        border-radius: 10px;
        padding: 16px;
        background: #f5f8fd;
        margin-bottom: 12px;
    }

    .generated-box {
        border: 1px solid #8eb1eb;
        border-radius: 10px;
        padding: 18px;
        background: #f4f8ff;
        margin-top: 10px;
    }

    .revised-box {
        border: 1px solid #a8a8d7;
        border-radius: 10px;
        padding: 18px;
        background: #f7f7ff;
        margin-top: 10px;
    }

    .weak-box {
        border-left: 5px solid #dfa642;
        background: #fff8e8;
        padding: 10px;
        border-radius: 5px;
        margin: 6px 0;
    }

    .strong-box {
        border-left: 5px solid #4da967;
        background: #eaf8ee;
        padding: 10px;
        border-radius: 5px;
        margin: 6px 0;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


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
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


def normalize(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def similarity(a, b):
    return SequenceMatcher(
        None,
        normalize(a),
        normalize(b)
    ).ratio()


def keyword_tokens(text):
    tokens = re.findall(
        r"[A-Za-z]{3,}",
        normalize(text)
    )

    return [
        word
        for word in tokens
        if word not in STOPWORDS
    ]


def keyword_overlap(a, b):
    first = set(keyword_tokens(a))
    second = set(keyword_tokens(b))

    if not first or not second:
        return 0

    return len(first & second) / max(
        1,
        min(len(first), len(second))
    )


# ============================================================
# FILE READERS
# ============================================================

def read_pdf(uploaded_file):

    raw = uploaded_file.getvalue()

    if not raw:
        return ""

    # PyMuPDF
    try:
        import fitz

        pdf = fitz.open(
            stream=raw,
            filetype="pdf"
        )

        pages = []

        for page in pdf:
            try:
                txt = page.get_text(
                    "text",
                    sort=True
                )

                if txt:
                    pages.append(txt)

            except Exception:
                pass

        pdf.close()

        combined = clean_text(
            "\n".join(pages)
        )

        if len(combined) >= 20:
            return combined

    except Exception:
        pass

    # pypdf
    try:
        from pypdf import PdfReader

        reader = PdfReader(
            io.BytesIO(raw)
        )

        pages = []

        for page in reader.pages:
            try:
                txt = page.extract_text()

                if txt:
                    pages.append(txt)

            except Exception:
                pass

        combined = clean_text(
            "\n".join(pages)
        )

        if len(combined) >= 20:
            return combined

    except Exception:
        pass

    # pdfplumber
    try:
        import pdfplumber

        pages = []

        with pdfplumber.open(
            io.BytesIO(raw)
        ) as pdf:

            for page in pdf.pages:
                try:
                    txt = page.extract_text(
                        x_tolerance=2,
                        y_tolerance=3
                    )

                    if txt:
                        pages.append(txt)

                except Exception:
                    pass

        combined = clean_text(
            "\n".join(pages)
        )

        if len(combined) >= 20:
            return combined

    except Exception:
        pass

    # OCR
    try:
        import fitz
        import pytesseract
        from PIL import Image

        pdf = fitz.open(
            stream=raw,
            filetype="pdf"
        )

        pages = []

        for page in pdf:
            try:
                pix = page.get_pixmap(
                    matrix=fitz.Matrix(
                        2,
                        2
                    ),
                    alpha=False
                )

                image = Image.open(
                    io.BytesIO(
                        pix.tobytes("png")
                    )
                )

                txt = pytesseract.image_to_string(
                    image,
                    config="--psm 6"
                )

                if txt:
                    pages.append(txt)

            except Exception:
                pass

        pdf.close()

        combined = clean_text(
            "\n".join(pages)
        )

        if len(combined) >= 20:
            return combined

    except Exception:
        pass

    return ""


def read_docx(uploaded_file):

    try:
        from docx import Document

        document = Document(
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

                cells = [
                    cell.text
                    for cell in row.cells
                ]

                parts.append(
                    " ".join(cells)
                )

        return clean_text(
            "\n".join(parts)
        )

    except Exception:
        return ""


def read_pptx(uploaded_file):

    try:
        from pptx import Presentation

        presentation = Presentation(
            io.BytesIO(
                uploaded_file.getvalue()
            )
        )

        parts = []

        for slide in presentation.slides:

            for shape in slide.shapes:

                if hasattr(shape, "text"):

                    if shape.text.strip():
                        parts.append(
                            shape.text
                        )

        return clean_text(
            "\n".join(parts)
        )

    except Exception:
        return ""


def read_excel(uploaded_file):

    try:
        raw = uploaded_file.getvalue()

        excel = pd.ExcelFile(
            io.BytesIO(raw)
        )

        parts = []

        for sheet in excel.sheet_names:

            dataframe = pd.read_excel(
                io.BytesIO(raw),
                sheet_name=sheet
            )

            dataframe = dataframe.fillna("")

            for row in dataframe.astype(
                str
            ).values.tolist():

                parts.append(
                    " ".join(row)
                )

        return clean_text(
            "\n".join(parts)
        )

    except Exception:
        return ""


def read_csv(uploaded_file):

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

            parts.append(
                " ".join(row)
            )

        return clean_text(
            "\n".join(parts)
        )

    except Exception:
        return ""


def read_text_file(uploaded_file):

    try:
        return clean_text(
            uploaded_file.getvalue().decode(
                "utf-8",
                errors="ignore"
            )
        )

    except Exception:
        return ""


def read_image(uploaded_file):

    try:
        import pytesseract
        from PIL import Image

        image = Image.open(
            io.BytesIO(
                uploaded_file.getvalue()
            )
        )

        return clean_text(
            pytesseract.image_to_string(
                image
            )
        )

    except Exception:
        return ""


def read_uploaded_file(uploaded_file):

    filename = uploaded_file.name.lower()

    if filename.endswith(".pdf"):
        return read_pdf(uploaded_file)

    if filename.endswith(".docx"):
        return read_docx(uploaded_file)

    if filename.endswith(".pptx"):
        return read_pptx(uploaded_file)

    if filename.endswith(
        (".xlsx", ".xls", ".xlsm")
    ):
        return read_excel(uploaded_file)

    if filename.endswith(".csv"):
        return read_csv(uploaded_file)

    if filename.endswith(
        (".txt", ".md", ".rtf")
    ):
        return read_text_file(uploaded_file)

    if filename.endswith(
        (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".bmp"
        )
    ):
        return read_image(uploaded_file)

    return ""


# ============================================================
# QUESTION EXTRACTION
# ============================================================

def is_heading_or_label(text):

    text = clean_text(text)

    if not text:
        return True

    normalized = normalize(text)

    patterns = [
        r"^section\s*[a-z0-9ivx\-]+$",
        r"^part\s*[a-z0-9ivx\-]+$",
        r"^unit\s*[a-z0-9ivx\-]+$",
        r"^chapter\s*[a-z0-9ivx\-]+$",
        r"^module\s*[a-z0-9ivx\-]+$",

        r"^instructions?\s*:?",
        r"^general\s+instructions?",
        r"^specific\s+instructions?",

        r"^mcqs?$",
        r"^mcq\s+section$",
        r"^multiple\s+choice\s+questions?$",

        r"^true\s*(?:/|or)\s*false$",
        r"^short\s+questions?$",
        r"^short\s+answers?$",
        r"^long\s+questions?$",
        r"^long\s+answers?$",
        r"^essay\s+questions?$",
        r"^descriptive\s+questions?$",
        r"^subjective\s+questions?$",
        r"^objective\s+questions?$",
        r"^case\s+stud(?:y|ies)$",
        r"^numerical\s+questions?$",
        r"^practical\s+questions?$",

        r"^answer\s+the\s+following$",
        r"^answer\s+all\s+questions?$",
        r"^attempt\s+all\s+questions?$",
        r"^attempt\s+any\s+questions?$",

        r"^assessment$",
        r"^quiz$",
        r"^test$",
        r"^exam$",
        r"^midterm$",
        r"^final\s+exam$",

        r"^course\s+learning\s+outcomes?$",
        r"^program(?:me)?\s+learning\s+outcomes?$",
        r"^clo[s]?$",
        r"^plo[s]?$",

        r"^rubric$",
        r"^marking\s+scheme$",
        r"^answer\s+key$",
        r"^answers?$",

        r"^name\s*:?",
        r"^roll\s*(?:no|number)\s*:?",
        r"^registration\s*(?:no|number)\s*:?",
        r"^date\s*:?",
        r"^time\s*:?",

        r"^total\s+marks?\s*:?",
        r"^marks?\s*:?",
        r"^points?\s*:?",
    ]

    for pattern in patterns:

        if re.search(
            pattern,
            normalized,
            flags=re.I
        ):
            return True

    if re.match(
        r"^(clo|plo|bloom|marks?|points?|"
        r"topic|section|part|course|subject|"
        r"date|time|name|roll\s*(?:no|number))"
        r"\s*[:=\-]",
        normalized,
        flags=re.I
    ):
        return True

    if re.fullmatch(
        r"[-_=*#.:| ]+",
        text
    ):
        return True

    return False


def looks_like_actual_question(text):

    text = clean_text(text)

    if not text:
        return False

    if is_heading_or_label(text):
        return False

    if "?" in text:
        return True

    command_words = [
        "define", "identify", "state", "list",
        "name", "explain", "describe", "discuss",
        "compare", "contrast", "analyze", "analyse",
        "evaluate", "assess", "justify",
        "calculate", "compute", "solve",
        "determine", "derive", "demonstrate",
        "apply", "design", "develop", "construct",
        "write", "interpret", "classify",
        "differentiate", "examine", "critique",
        "recommend", "prove"
    ]

    for word in command_words:

        if re.search(
            r"\b" + re.escape(word) + r"\b",
            normalize(text)
        ):
            return True

    if re.search(
        r"\b[A-D]\s*[\)\.\:]\s+",
        text,
        flags=re.I
    ):
        return True

    return False


def clean_question_candidate(block):

    block = clean_text(block)

    if not block:
        return ""

    block = re.split(
        r"\n\s*(?:Answer\s*Key|Answers?|"
        r"Marking\s*Scheme|Rubric)\s*:?",
        block,
        maxsplit=1,
        flags=re.I
    )[0]

    block = re.sub(
        r"\s*\(\s*\d+\s*(?:marks?|points?)\s*\)\s*$",
        "",
        block,
        flags=re.I
    )

    block = re.sub(
        r"\s*\[\s*\d+\s*(?:marks?|points?)\s*\]\s*$",
        "",
        block,
        flags=re.I
    )

    return block.strip()


def extract_questions(text):

    text = clean_text(text)

    if not text:
        return []

    questions = []

    pattern = re.compile(
        r"(?im)^\s*"
        r"(?:Q(?:uestion)?\s*)?"
        r"(\d{1,3})"
        r"\s*[\.\):\-]\s+"
    )

    matches = list(
        pattern.finditer(text)
    )

    # Numbered questions are authoritative.
    if matches:

        for index, match in enumerate(matches):

            start = match.end()

            end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(text)
            )

            block = text[start:end]

            lines = []

            for line in block.splitlines():

                line = clean_text(line)

                if not line:
                    continue

                if is_heading_or_label(line):
                    continue

                lines.append(line)

            block = clean_text(
                "\n".join(lines)
            )

            block = clean_question_candidate(
                block
            )

            if not block:
                continue

            if len(block.split()) < 3:
                continue

            if is_heading_or_label(block):
                continue

            if not looks_like_actual_question(block):
                if len(block.split()) < 10:
                    continue

            if not any(
                similarity(
                    block,
                    old
                ) >= 0.92
                for old in questions
            ):
                questions.append(block)

        return questions

    # Fallback for unnumbered assessment
    blocks = re.split(
        r"\n\s*\n+",
        text
    )

    for block in blocks:

        block = clean_question_candidate(
            block
        )

        if not block:
            continue

        if len(block.split()) < 3:
            continue

        if is_heading_or_label(block):
            continue

        if not looks_like_actual_question(block):
            continue

        if not any(
            similarity(
                block,
                old
            ) >= 0.90
            for old in questions
        ):
            questions.append(block)

    return questions


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
        r"\b(fill in the blank|fill the blank|"
        r"complete the sentence)\b",
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
        r"\b(write code|program|programming|"
        r"code|algorithm)\b",
        q
    ):
        return "Coding / Practical"

    if re.search(
        r"\b(calculate|compute|solve|numerical|"
        r"find the value)\b",
        q
    ):
        return "Numerical"

    if re.search(
        r"\b(design|implement|perform|demonstrate|"
        r"develop|construct)\b",
        q
    ):
        return "Practical / Application"

    if len(question.split()) > 45:
        return "Essay / Long Answer"

    return "Short Answer"


# ============================================================
# BLOOM DETECTION
# ============================================================

def detect_bloom(question):

    q = normalize(question)

    detected = []

    for level, verbs in BLOOM_VERBS.items():

        for verb in verbs:

            if re.search(
                r"\b" + re.escape(verb) + r"\b",
                q
            ):
                detected.append(level)
                break

    if not detected:
        return "Understand"

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


def bloom_number(level):

    return {
        "Remember": 1,
        "Understand": 2,
        "Apply": 3,
        "Analyze": 4,
        "Evaluate": 5,
        "Create": 6,
    }.get(
        level,
        2
    )


# ============================================================
# SCORING
# ============================================================

def score_clo(question, clo):

    if not clo.strip():
        return None

    overlap = keyword_overlap(
        question,
        clo
    )

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

    overlap = keyword_overlap(
        question,
        plo
    )

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


def score_bloom(
    question,
    target_bloom=None
):

    actual = detect_bloom(
        question
    )

    q = normalize(question)

    explicit = any(
        re.search(
            r"\b" + re.escape(verb) + r"\b",
            q
        )
        for verb in BLOOM_VERBS.get(
            actual,
            []
        )
    )

    score = 92 if explicit else 76

    if target_bloom:

        if actual == target_bloom:

            score = 96

        else:

            difference = abs(
                bloom_number(actual)
                -
                bloom_number(target_bloom)
            )

            if difference == 1:
                score = 76

            elif difference >= 2:
                score = 58

    return score


def subject_relevance_score(
    question,
    subject,
    course
):

    reference = " ".join(
        x
        for x in [subject, course]
        if x.strip()
    )

    if not reference:
        return 75

    overlap = keyword_overlap(
        question,
        reference
    )

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

    question = clean_text(
        question
    )

    if not question:
        return 0

    score = 100

    count = len(
        question.split()
    )

    if count < 5:
        score -= 20

    if count > 120:
        score -= 10

    if question.count("?") > 2:
        score -= 8

    if re.search(
        r"\b(etc|and so on)\b",
        question,
        flags=re.I
    ):
        score -= 8

    return max(
        0,
        min(
            100,
            score
        )
    )


def measurability_score(question):

    q = normalize(
        question
    )

    measurable_verbs = [
        "define",
        "identify",
        "list",
        "explain",
        "describe",
        "calculate",
        "solve",
        "apply",
        "compare",
        "contrast",
        "analyze",
        "analyse",
        "evaluate",
        "justify",
        "design",
        "develop",
        "construct",
        "implement",
        "write",
        "determine",
        "classify",
        "demonstrate",
        "interpret",
        "recommend",
    ]

    hits = sum(
        1
        for verb in measurable_verbs
        if re.search(
            r"\b" + re.escape(verb) + r"\b",
            q
        )
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

    metrics = {
        "CLO Alignment": score_clo(
            question,
            clo
        ),
        "PLO Alignment": score_plo(
            question,
            plo
        ),
        "Bloom Alignment": score_bloom(
            question,
            target_bloom
        ),
        "Subject Relevance": subject_relevance_score(
            question,
            subject,
            course
        ),
        "Clarity": clarity_score(
            question
        ),
        "Measurability": measurability_score(
            question
        ),
    }

    available = [
        score
        for score in metrics.values()
        if score is not None
    ]

    overall = round(
        sum(available) /
        len(available)
    ) if available else 0

    return {
        "question": question,
        "overall": overall,
        "metrics": metrics,
        "actual_bloom": detect_bloom(
            question
        ),
        "target_bloom": target_bloom,
        "question_type": detect_question_type(
            question
        ),
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

    for metric, score in result[
        "metrics"
    ].items():

        if score is not None and score < ATTAINMENT_THRESHOLD:

            weak.append(
                {
                    "metric": metric,
                    "score": score,
                    "status": get_status(score)
                }
            )

    weak.sort(
        key=lambda x: x["score"]
    )

    return weak


# ============================================================
# TOPIC EXTRACTION FOR GENERATION
# ============================================================

def extract_core_topic(
    question,
    subject,
    clo
):
    """
    Determines the content topic without copying the CLO/PLO
    into the generated question.
    """

    question_words = keyword_tokens(
        question
    )

    subject_words = set(
        keyword_tokens(
            subject
        )
    )

    clo_words = set(
        keyword_tokens(
            clo
        )
    )

    useful = []

    for word in question_words:

        if word in subject_words:
            continue

        if word in clo_words:
            continue

        useful.append(word)

    if useful:
        return " ".join(
            useful[:7]
        )

    clo_useful = [
        word
        for word in keyword_tokens(clo)
        if word not in subject_words
    ]

    if clo_useful:
        return " ".join(
            clo_useful[:7]
        )

    return subject or "the selected topic"


def get_topic_phrase(
    question,
    subject,
    clo
):
    topic = extract_core_topic(
        question,
        subject,
        clo
    )

    return topic.strip(
        " ,.;:"
    )


# ============================================================
# QUESTION GENERATION ENGINE
# ============================================================

def generate_mcq_variants(
    topic,
    subject,
    bloom
):

    return [
        (
            f"Which statement best explains the role of "
            f"{topic} in {subject or 'the subject'}?"
        ),
        (
            f"Which option represents the most appropriate "
            f"application of {topic}?"
        ),
        (
            f"Which of the following would provide the strongest "
            f"evidence for understanding {topic}?"
        ),
        (
            f"Which statement correctly describes an important "
            f"relationship involving {topic}?"
        ),
    ]


def generate_true_false_variants(
    topic,
    subject,
    bloom
):

    return [
        (
            f"{topic.capitalize()} directly influences the outcome "
            f"of the process being studied."
        ),
        (
            f"Understanding {topic} requires consideration of only "
            f"a single factor."
        ),
        (
            f"The application of {topic} can be explained using "
            f"the principles covered in the course."
        ),
        (
            f"A change in a relevant condition can affect the way "
            f"{topic} operates."
        ),
    ]


def generate_fill_blank_variants(
    topic,
    subject,
    bloom
):

    return [
        (
            f"The process or concept that explains the main role of "
            f"{topic} is __________."
        ),
        (
            f"A key principle associated with {topic} is __________."
        ),
        (
            f"The main factor used to explain {topic} is __________."
        ),
        (
            f"The term that best describes the relevant process in "
            f"{topic} is __________."
        ),
    ]


def generate_matching_variants(
    topic,
    subject,
    bloom
):

    return [
        (
            f"Match each concept associated with {topic} in Column A "
            f"with its most appropriate description or application "
            f"in Column B."
        ),
        (
            f"Match the major components of {topic} with their "
            f"corresponding functions or effects."
        ),
        (
            f"Match each principle related to {topic} with the "
            f"appropriate example or consequence."
        ),
    ]


def generate_short_answer_variants(
    topic,
    subject,
    bloom
):

    if bloom == "Remember":

        return [
            f"Define {topic} and identify two key features associated with it.",
            f"State the main characteristics of {topic} and name one relevant example.",
            f"Identify the major components of {topic} and briefly state their roles.",
        ]

    if bloom == "Understand":

        return [
            f"Explain the main concept of {topic} and illustrate it with a relevant example.",
            f"Describe how {topic} works and explain why it is important.",
            f"Explain the relationship between the main components involved in {topic}.",
        ]

    if bloom == "Apply":

        return [
            f"Apply the principles of {topic} to a relevant situation and explain your reasoning.",
            f"Given a practical situation involving {topic}, determine the appropriate course of action and justify your response.",
            f"Use your knowledge of {topic} to solve a realistic problem and explain the steps you followed.",
        ]

    if bloom == "Analyze":

        return [
            f"Analyze the major factors involved in {topic} and explain how they influence one another.",
            f"Compare the main components of {topic} and analyze their different effects.",
            f"Examine a problem involving {topic} and identify the relationships that explain the outcome.",
        ]

    if bloom == "Evaluate":

        return [
            f"Evaluate the effectiveness of a selected approach to {topic} and justify your conclusion.",
            f"Assess the advantages and limitations associated with {topic} and support your judgment with evidence.",
            f"Critically evaluate a claim about {topic} and provide reasons for your conclusion.",
        ]

    return [
        f"Develop a suitable approach for addressing a problem involving {topic}. Explain the reasoning behind your design.",
        f"Propose a practical solution to a problem related to {topic} and explain how it would work.",
        f"Design an approach that could be used to investigate or improve an aspect of {topic}.",
    ]


def generate_essay_variants(
    topic,
    subject,
    bloom
):

    if bloom == "Analyze":

        return [
            f"Analyze the major factors influencing {topic}. Explain the relationships among these factors and discuss their effects.",
            f"Compare the different dimensions of {topic} and analyze how they contribute to the overall outcome.",
            f"Analyze a significant issue associated with {topic} using relevant concepts and evidence.",
        ]

    if bloom == "Evaluate":

        return [
            f"Evaluate the effectiveness of different approaches to {topic}. Support your judgment with relevant evidence.",
            f"Critically assess the significance of {topic} and discuss its advantages, limitations, and implications.",
            f"Evaluate a commonly held claim about {topic} and construct a reasoned argument for your conclusion.",
        ]

    if bloom == "Create":

        return [
            f"Develop a comprehensive approach for addressing a significant issue related to {topic}. Justify the choices made in your approach.",
            f"Design a framework for improving or investigating {topic}. Explain the components and rationale of your proposed framework.",
            f"Propose an innovative solution to a problem involving {topic} and explain how it could be implemented.",
        ]

    if bloom == "Apply":

        return [
            f"Discuss how the principles of {topic} can be applied to a realistic professional or practical situation.",
            f"Explain how knowledge of {topic} can be used to address a real-world problem.",
        ]

    return [
        f"Discuss the major concepts associated with {topic} and explain their significance.",
        f"Explain {topic} in detail, using relevant examples to demonstrate your understanding.",
    ]


def generate_case_variants(
    topic,
    subject,
    bloom
):

    if bloom == "Apply":

        return [
            (
                f"A realistic situation has arisen in which a problem involving "
                f"{topic} must be addressed. Apply the relevant principles to "
                f"determine an appropriate response and explain your reasoning."
            ),
            (
                f"A professional is faced with a decision related to {topic}. "
                f"Using the concepts studied in the course, determine what "
                f"should be done and justify the proposed action."
            ),
        ]

    if bloom == "Analyze":

        return [
            (
                f"A case involving {topic} produces an unexpected outcome. "
                f"Analyze the case, identify the factors responsible for the "
                f"outcome, and explain the relationships among them."
            ),
            (
                f"A practical situation involving {topic} has resulted in "
                f"conflicting outcomes. Analyze the available information "
                f"and determine the most important contributing factors."
            ),
        ]

    if bloom == "Evaluate":

        return [
            (
                f"A decision must be made in a case involving {topic}. "
                f"Evaluate the available options and recommend the most "
                f"appropriate course of action with justification."
            ),
            (
                f"A proposed solution to a problem involving {topic} has "
                f"received mixed results. Evaluate the solution and determine "
                f"whether it should be retained, modified, or replaced."
            ),
        ]

    if bloom == "Create":

        return [
            (
                f"A new problem involving {topic} has emerged in a realistic "
                f"professional setting. Design a suitable solution and explain "
                f"how it could be implemented."
            ),
            (
                f"You have been asked to develop an intervention for a problem "
                f"related to {topic}. Design the intervention and identify how "
                f"its effectiveness would be evaluated."
            ),
        ]

    return [
        (
            f"A practical situation involving {topic} is presented to you. "
            f"Explain how the relevant concepts would be used to understand "
            f"or address the situation."
        ),
    ]


def generate_numerical_variants(
    topic,
    subject,
    bloom
):

    return [
        (
            f"A measurement related to {topic} changes from 20 units to "
            f"35 units after an intervention. Calculate the percentage "
            f"change and interpret what the result indicates."
        ),
        (
            f"A system associated with {topic} produces 240 units of output "
            f"in 8 minutes. Calculate the average output per minute and "
            f"interpret the result."
        ),
        (
            f"An experiment involving {topic} records values of 12, 18, "
            f"24, and 30 units under four conditions. Calculate the mean "
            f"value and identify the condition producing the highest result."
        ),
        (
            f"A process related to {topic} has an initial value of 80 units "
            f"and a final value of 100 units. Calculate the percentage "
            f"increase and explain its significance."
        ),
    ]


def generate_practical_variants(
    topic,
    subject,
    bloom
):

    if bloom == "Create":

        return [
            (
                f"Design a practical investigation to examine an important "
                f"factor associated with {topic}. Identify the variables, "
                f"procedure, data to be collected, and expected outcome."
            ),
            (
                f"Develop a practical procedure for investigating {topic}. "
                f"Specify the resources, steps, variables, and method you "
                f"would use to evaluate the result."
            ),
        ]

    if bloom == "Analyze":

        return [
            (
                f"Conduct a practical analysis of {topic} using an appropriate "
                f"procedure. Identify the observations or evidence that would "
                f"help you explain the outcome."
            ),
            (
                f"Examine a practical demonstration involving {topic}. "
                f"Identify the important variables and explain how changes "
                f"in them could affect the result."
            ),
        ]

    return [
        (
            f"Demonstrate how you would apply the relevant procedure to a "
            f"practical task involving {topic}. Explain the important steps "
            f"and expected result."
        ),
        (
            f"Perform a practical task related to {topic}. Describe the "
            f"procedure you would follow and explain how you would determine "
            f"whether the task was completed successfully."
        ),
    ]


def generate_coding_variants(
    topic,
    subject,
    bloom
):

    if bloom == "Analyze":

        return [
            (
                f"Analyze a programming problem related to {topic}. "
                f"Identify the required inputs, processing steps, and outputs, "
                f"then describe an appropriate algorithm."
            ),
            (
                f"Given a computational problem involving {topic}, analyze "
                f"the requirements and determine an efficient algorithmic "
                f"approach."
            ),
        ]

    if bloom == "Create":

        return [
            (
                f"Develop a program that solves a practical problem related "
                f"to {topic}. Define the inputs and expected outputs and "
                f"explain the main logic of your solution."
            ),
            (
                f"Design and implement a program for a realistic application "
                f"of {topic}. Explain the algorithm and demonstrate the "
                f"expected output."
            ),
        ]

    return [
        (
            f"Write a program that applies the principles of {topic} to "
            f"solve a clearly defined problem. Explain the logic of your "
            f"solution and state the expected output."
        ),
        (
            f"Implement a simple computational solution involving {topic}. "
            f"Identify the inputs, processing steps, and expected result."
        ),
    ]


# ============================================================
# MCQ OPTION GENERATION
# ============================================================

def add_mcq_options(stem, topic, bloom):

    options = [
        f"It applies the relevant principles of {topic} to the given situation.",
        f"It identifies an unrelated concept without addressing the situation.",
        f"It repeats a definition without demonstrating the required understanding.",
        f"It gives a conclusion without using relevant evidence or reasoning.",
    ]

    random.shuffle(
        options
    )

    labels = ["A", "B", "C", "D"]

    return (
        stem
        + "\n\n"
        + "\n".join(
            f"{label}. {option}"
            for label, option in zip(
                labels,
                options
            )
        )
    )


# ============================================================
# STRUCTURED QUESTION GENERATOR
# ============================================================

def create_question_candidate(
    question_type,
    topic,
    subject,
    bloom,
    seed
):
    """
    Generates a question according to the selected type and Bloom
    level. CLO/PLO are NOT pasted into the question.
    """

    if question_type == "MCQ":

        stems = generate_mcq_variants(
            topic,
            subject,
            bloom
        )

        stem = stems[
            seed % len(stems)
        ]

        return add_mcq_options(
            stem,
            topic,
            bloom
        )

    if question_type == "True / False":

        variants = generate_true_false_variants(
            topic,
            subject,
            bloom
        )

        return (
            "True or False: "
            + variants[
                seed % len(variants)
            ]
        )

    if question_type == "Fill in the Blank":

        variants = generate_fill_blank_variants(
            topic,
            subject,
            bloom
        )

        return variants[
            seed % len(variants)
        ]

    if question_type == "Matching":

        variants = generate_matching_variants(
            topic,
            subject,
            bloom
        )

        return variants[
            seed % len(variants)
        ]

    if question_type == "Short Answer":

        variants = generate_short_answer_variants(
            topic,
            subject,
            bloom
        )

        return variants[
            seed % len(variants)
        ]

    if question_type == "Essay / Long Answer":

        variants = generate_essay_variants(
            topic,
            subject,
            bloom
        )

        return variants[
            seed % len(variants)
        ]

    if question_type == "Case / Scenario":

        variants = generate_case_variants(
            topic,
            subject,
            bloom
        )

        return variants[
            seed % len(variants)
        ]

    if question_type == "Numerical":

        variants = generate_numerical_variants(
            topic,
            subject,
            bloom
        )

        return variants[
            seed % len(variants)
        ]

    if question_type == "Practical / Application":

        variants = generate_practical_variants(
            topic,
            subject,
            bloom
        )

        return variants[
            seed % len(variants)
        ]

    if question_type == "Coding / Practical":

        variants = generate_coding_variants(
            topic,
            subject,
            bloom
        )

        return variants[
            seed % len(variants)
        ]

    return generate_short_answer_variants(
        topic,
        subject,
        bloom
    )[0]


# ============================================================
# QUALITY CHECK FOR GENERATED QUESTIONS
# ============================================================

def generation_quality_score(
    question,
    original_question,
    target_bloom,
    question_type,
    subject
):

    score = 0

    # Must be different from original.
    difference = 1 - similarity(
        question,
        original_question
    )

    if difference >= 0.35:
        score += 20
    elif difference >= 0.20:
        score += 10

    # Bloom verb.
    detected = detect_bloom(
        question
    )

    if detected == target_bloom:
        score += 25

    # Question type.
    detected_type = detect_question_type(
        question
    )

    if detected_type == question_type:
        score += 20

    # Clarity.
    clarity = clarity_score(
        question
    )

    score += round(
        clarity * 0.15
    )

    # Measurability.
    meas = measurability_score(
        question
    )

    score += round(
        meas * 0.20
    )

    return score


# ============================================================
# CANDIDATE SET
# ============================================================

def create_candidate_set(
    original_question,
    subject,
    clo,
    target_bloom,
    question_type,
    count=12
):

    topic = get_topic_phrase(
        original_question,
        subject,
        clo
    )

    candidates = []

    # Add a variety of seed structures.
    for seed in range(count):

        candidate = create_question_candidate(
            question_type,
            topic,
            subject,
            target_bloom,
            seed
        )

        candidate = clean_text(
            candidate
        )

        if not candidate:
            continue

        # Reject if essentially identical.
        if similarity(
            candidate,
            original_question
        ) >= 0.78:
            continue

        # Reject duplicate candidates.
        if any(
            similarity(
                candidate,
                old
            ) >= 0.88
            for old in candidates
        ):
            continue

        candidates.append(
            candidate
        )

    return candidates


# ============================================================
# GENERATE BEST NEW QUESTION
# ============================================================

def generate_best_candidate(
    original_question,
    clo,
    plo,
    subject,
    course,
    target_bloom,
    question_type
):

    candidates = create_candidate_set(
        original_question,
        subject,
        clo,
        target_bloom,
        question_type,
        count=12
    )

    if not candidates:

        candidates = [
            create_question_candidate(
                question_type,
                get_topic_phrase(
                    original_question,
                    subject,
                    clo
                ),
                subject,
                target_bloom,
                0
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
            target_bloom
        )

        quality = generation_quality_score(
            candidate,
            original_question,
            target_bloom,
            question_type,
            subject
        )

        # Main priority: actual alignment score.
        # Secondary priority: structural quality.
        combined = (
            result["overall"] * 0.70
            + quality * 0.30
        )

        evaluated.append(
            (
                combined,
                candidate,
                result
            )
        )

    evaluated.sort(
        key=lambda x: x[0],
        reverse=True
    )

    best = evaluated[0]

    return best[1], best[2]


# ============================================================
# NATURAL REVISION ENGINE
# ============================================================

def revise_question_naturally(
    original_question,
    result,
    subject,
    clo,
    plo,
    target_bloom,
    question_type
):
    """
    Revision does not append CLO/PLO text.
    It creates a fresh question structure while retaining
    the original content/topic.
    """

    topic = get_topic_phrase(
        original_question,
        subject,
        clo
    )

    weak = get_weak_metrics(
        result
    )

    weak_names = [
        item["metric"]
        for item in weak
    ]

    # If Bloom is weak, generate a stronger cognitive task.
    if "Bloom Alignment" in weak_names:

        revised_candidates = create_candidate_set(
            original_question,
            subject,
            clo,
            target_bloom,
            question_type,
            count=12
        )

        if revised_candidates:

            ranked = []

            for candidate in revised_candidates:

                candidate_result = evaluate_question(
                    candidate,
                    clo,
                    plo,
                    subject,
                    "",
                    target_bloom
                )

                ranked.append(
                    (
                        candidate_result["overall"],
                        candidate,
                        candidate_result
                    )
                )

            ranked.sort(
                key=lambda x: x[0],
                reverse=True
            )

            return (
                ranked[0][1],
                ranked[0][2]
            )

    # Natural revision structures.
    if question_type == "Short Answer":

        if target_bloom == "Apply":

            revised = (
                f"Using the principles related to {topic}, "
                f"apply your knowledge to a realistic situation "
                f"and explain the steps you would take."
            )

        elif target_bloom == "Analyze":

            revised = (
                f"Analyze the major factors associated with "
                f"{topic} and explain how they influence the "
                f"outcome of the situation."
            )

        elif target_bloom == "Evaluate":

            revised = (
                f"Evaluate the effectiveness of the relevant "
                f"approach to {topic}. Support your conclusion "
                f"with appropriate evidence and reasoning."
            )

        elif target_bloom == "Create":

            revised = (
                f"Design an appropriate solution to a problem "
                f"involving {topic}. Explain the main decisions "
                f"and justify your proposed solution."
            )

        else:

            revised = (
                f"Explain {topic} clearly and illustrate the "
                f"concept with a relevant example."
            )

    elif question_type == "Case / Scenario":

        if target_bloom == "Analyze":

            revised = (
                f"A practical situation involving {topic} has "
                f"produced an unexpected result. Analyze the case, "
                f"identify the main contributing factors, and "
                f"explain the relationships among them."
            )

        elif target_bloom == "Evaluate":

            revised = (
                f"A decision must be made in a case involving "
                f"{topic}. Evaluate the available alternatives "
                f"and recommend the most appropriate course of action."
            )

        elif target_bloom == "Create":

            revised = (
                f"A new problem involving {topic} has emerged "
                f"in a professional setting. Design a suitable "
                f"solution and explain how its effectiveness "
                f"would be evaluated."
            )

        else:

            revised = (
                f"A realistic situation involving {topic} is "
                f"presented. Apply the relevant concepts to "
                f"determine an appropriate response and explain "
                f"your reasoning."
            )

    elif question_type == "Essay / Long Answer":

        if target_bloom == "Evaluate":

            revised = (
                f"Critically evaluate the major issues associated "
                f"with {topic}. Support your position with relevant "
                f"evidence and discuss the implications of your conclusion."
            )

        elif target_bloom == "Create":

            revised = (
                f"Develop a comprehensive approach for addressing "
                f"a significant issue related to {topic}. Explain "
                f"and justify the components of your proposed approach."
            )

        elif target_bloom == "Analyze":

            revised = (
                f"Analyze the major dimensions of {topic}, explain "
                f"the relationships among them, and discuss their "
                f"effects on the overall outcome."
            )

        else:

            revised = (
                f"Discuss {topic} in detail and use relevant "
                f"examples to demonstrate your understanding."
            )

    elif question_type == "Practical / Application":

        if target_bloom == "Create":

            revised = (
                f"Design a practical investigation related to "
                f"{topic}. Identify the variables, procedure, "
                f"evidence to be collected, and expected outcome."
            )

        else:

            revised = (
                f"Demonstrate how you would apply the relevant "
                f"principles of {topic} to complete a practical task. "
                f"Explain the procedure and expected result."
            )

    elif question_type == "Numerical":

        revised = (
            f"A quantitative problem related to {topic} is given. "
            f"Use the appropriate method to calculate the required "
            f"result and interpret what the result means."
        )

    elif question_type == "Coding / Practical":

        revised = (
            f"Develop a program that solves a practical problem "
            f"related to {topic}. Define the inputs and outputs, "
            f"explain the algorithm, and state the expected result."
        )

    elif question_type == "MCQ":

        revised = add_mcq_options(
            (
                f"Which option best demonstrates the application "
                f"of {topic} in the given context?"
            ),
            topic,
            target_bloom
        )

    elif question_type == "True / False":

        revised = (
            f"True or False: A change in a relevant factor can "
            f"affect the outcome associated with {topic}."
        )

    elif question_type == "Fill in the Blank":

        revised = (
            f"The principle that best explains the relevant "
            f"process associated with {topic} is __________."
        )

    elif question_type == "Matching":

        revised = (
            f"Match the major components of {topic} with their "
            f"corresponding functions, characteristics, or effects."
        )

    else:

        revised = (
            f"Explain how the principles associated with "
            f"{topic} can be applied to a relevant situation."
        )

    revised = clean_text(
        revised
    )

    revised_result = evaluate_question(
        revised,
        clo,
        plo,
        subject,
        "",
        target_bloom
    )

    return (
        revised,
        revised_result
    )


# ============================================================
# QUESTION-SPECIFIC SUGGESTION
# ============================================================

def generate_question_specific_suggestion(
    question,
    result,
    clo,
    plo,
    subject,
    course
):

    original = clean_text(
        question
    )

    weak_metrics = get_weak_metrics(
        result
    )

    if not weak_metrics:

        return (
            "**Original Question**\n\n"
            f"> {original}\n\n"
            "**Specific Suggestion**\n\n"
            "This question has reached the 80/100 attainment "
            "threshold across the evaluated metrics. It can be "
            "retained, with minor wording refinement if needed."
        )

    lines = []

    for item in weak_metrics:

        lines.append(
            f"- **{item['metric']}: "
            f"{item['score']}/100** — "
            f"{item['status']}"
        )

    suggestions = []

    weak_names = [
        item["metric"]
        for item in weak_metrics
    ]

    if "CLO Alignment" in weak_names:

        suggestions.append(
            "Connect the task directly to the knowledge or skill "
            "described in the CLO. The student's answer should "
            "provide observable evidence of that learning outcome."
        )

    if "PLO Alignment" in weak_names:

        suggestions.append(
            "Make the task require a broader capability represented "
            "by the PLO, such as analysis, problem solving, evaluation, "
            "communication, design, or application."
        )

    if "Bloom Alignment" in weak_names:

        suggestions.append(
            f"The detected Bloom level is **{result['actual_bloom']}**. "
            "Change the cognitive operation so that the student "
            "actually performs the intended Bloom-level task."
        )

    if "Subject Relevance" in weak_names:

        suggestions.append(
            f"Ground the question more explicitly in "
            f"**{subject or course or 'the selected subject'}** "
            "by using subject-specific concepts, data, terminology, "
            "or a realistic context."
        )

    if "Clarity" in weak_names:

        suggestions.append(
            "Use one clearly defined task and specify exactly what "
            "the student is expected to produce."
        )

    if "Measurability" in weak_names:

        suggestions.append(
            "Use an observable action such as define, calculate, "
            "apply, analyze, evaluate, justify, design, or develop "
            "so that the response can be assessed consistently."
        )

    return (
        "**Original Question**\n\n"
        f"> {original}\n\n"
        "**Actual Weak Areas**\n\n"
        + "\n".join(lines)
        + "\n\n"
        "**Specific Suggestion**\n\n"
        + "\n\n".join(
            f"{i + 1}. {item}"
            for i, item in enumerate(
                suggestions
            )
        )
        + "\n\n"
        "**Revision Direction**\n\n"
        "Keep the underlying topic and intended content, but "
        "rewrite the assessment task naturally. Do not add the "
        "CLO or PLO as sentences inside the question. Instead, "
        "let the question itself demonstrate the intended "
        "learning outcome."
    )


# ============================================================
# OVERALL METRICS
# ============================================================

def calculate_metric_averages(
    results
):

    values = {}

    for result in results:

        for metric, score in result[
            "metrics"
        ].items():

            if score is not None:

                values.setdefault(
                    metric,
                    []
                ).append(score)

    return {
        metric: round(
            sum(scores) / len(scores)
        )
        for metric, scores in values.items()
        if scores
    }


def calculate_overall_score(
    results
):

    scores = [
        result["overall"]
        for result in results
    ]

    if not scores:
        return 0

    return round(
        sum(scores) /
        len(scores)
    )


def overall_weak_areas(
    results
):

    averages = calculate_metric_averages(
        results
    )

    weak = []

    for metric, score in averages.items():

        if score < ATTAINMENT_THRESHOLD:

            weak.append(
                {
                    "metric": metric,
                    "score": score,
                    "status": get_status(score)
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

    st.markdown(
        "## 🎓 OBE Quiz Checker"
    )

    st.caption(
        "Assessment alignment and question improvement"
    )

    st.divider()

    st.markdown(
        "### 1. Course Information"
    )

    subject = st.text_input(
        "Subject",
        value=st.session_state.subject,
        placeholder="e.g. Chemistry"
    )

    course = st.text_input(
        "Course",
        value=st.session_state.course,
        placeholder="e.g. General Chemistry"
    )

    st.markdown(
        "### 2. Learning Outcomes"
    )

    clo = st.text_area(
        "CLO",
        value=st.session_state.clo_text,
        height=120,
        placeholder="Enter the Course Learning Outcome..."
    )

    plo = st.text_area(
        "PLO",
        value=st.session_state.plo_text,
        height=120,
        placeholder="Enter the Programme Learning Outcome..."
    )

    st.markdown(
        "### 3. Assessment"
    )

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
        ]
    )

    analyze_button = st.button(
        "🔍 Analyze Assessment",
        type="primary",
        use_container_width=True
    )

    reset_button = st.button(
        "🗑️ Reset",
        use_container_width=True
    )

    if reset_button:

        for key, value in DEFAULT_STATE.items():
            st.session_state[key] = value

        st.rerun()


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🎓 OBE Quiz Checker</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    "Evaluate assessment questions and generate properly structured "
    "OBE-aligned alternatives."
    "</div>",
    unsafe_allow_html=True
)


# ============================================================
# ANALYSIS
# ============================================================

if analyze_button:

    if not clo.strip():

        st.error(
            "Please enter a CLO before analyzing."
        )
        st.stop()

    if not plo.strip():

        st.error(
            "Please enter a PLO before analyzing."
        )
        st.stop()

    if not uploaded_file:

        st.error(
            "Please upload an assessment file."
        )
        st.stop()

    with st.spinner(
        "Reading and analyzing the assessment..."
    ):

        assessment_text = read_uploaded_file(
            uploaded_file
        )

        if not assessment_text:

            st.error(
                "The assessment file could not be read. "
                "Please check the file or OCR/dependencies."
            )
            st.stop()

        questions = extract_questions(
            assessment_text
        )

        if not questions:

            st.error(
                "No actual assessment questions could be extracted. "
                "Headings, section titles, instructions and labels "
                "are excluded."
            )
            st.stop()

        st.session_state.questions = questions

        st.session_state.results = []

        st.session_state.assessment_text = (
            assessment_text
        )

        st.session_state.file_name = (
            uploaded_file.name
        )

        st.session_state.clo_text = clo
        st.session_state.plo_text = plo
        st.session_state.subject = subject
        st.session_state.course = course

        st.session_state.revisions = {}
        st.session_state.generated_questions = {}

        for question in questions:

            result = evaluate_question(
                question,
                clo,
                plo,
                subject,
                course
            )

            st.session_state.results.append(
                result
            )

        st.session_state.analysis_done = True

    st.success(
        f"Analysis complete. {len(questions)} actual "
        f"assessment question(s) detected."
    )


# ============================================================
# INITIAL STATE
# ============================================================

if not st.session_state.analysis_done:

    st.info(
        "⏳ Enter the CLO and PLO, upload the assessment, "
        "and click **Analyze Assessment**."
    )

    st.stop()


# ============================================================
# FILE INFORMATION
# ============================================================

st.info(
    f"📄 **{st.session_state.file_name}** — "
    f"{len(st.session_state.questions)} actual assessment "
    f"question(s) detected. Headings, labels and instructions "
    f"are excluded."
)


# ============================================================
# OVERALL DASHBOARD
# ============================================================

st.markdown(
    "## 📊 Overall Alignment Dashboard"
)

overall_score = calculate_overall_score(
    st.session_state.results
)

averages = calculate_metric_averages(
    st.session_state.results
)

if overall_score >= ATTAINMENT_THRESHOLD:

    st.success(
        f"🟢 **Alignment Attained** — "
        f"Overall Score: {overall_score}/100"
    )

else:

    st.warning(
        f"🟠 **Revision Required** — "
        f"Overall Score: {overall_score}/100"
    )


# ============================================================
# METRIC CARDS
# ============================================================

st.markdown(
    "### Overall Metrics"
)

cols = st.columns(3)

for i, metric in enumerate(
    METRIC_ORDER
):

    score = averages.get(
        metric
    )

    with cols[i % 3]:

        if score is None:

            display = "N/A"
            status = "Not Available"

        else:

            display = f"{score}/100"
            status = get_status(score)

        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">{metric}</div>
                <div class="metric-score">{display}</div>
                <div>{status}</div>
            </div>
            """,
            unsafe_allow_html=True
        )


# ============================================================
# OVERALL WEAK AREAS
# ============================================================

st.markdown(
    "### Overall Areas Requiring Attention"
)

overall_weak = overall_weak_areas(
    st.session_state.results
)

if overall_weak:

    for item in overall_weak:

        st.markdown(
            f"""
            <div class="weak-box">
            <strong>{item['metric']}</strong>:
            {item['score']}/100 — {item['status']}
            </div>
            """,
            unsafe_allow_html=True
        )

else:

    st.markdown(
        '<div class="strong-box">'
        "🟢 All overall metrics have reached 80/100."
        "</div>",
        unsafe_allow_html=True
    )


# ============================================================
# SINGLE GRAPH
# ============================================================

st.markdown(
    "### Alignment Overview"
)

chart_df = pd.DataFrame(
    {
        "Metric": METRIC_ORDER,
        "Score": [
            averages.get(
                metric,
                0
            )
            for metric in METRIC_ORDER
        ],
    }
)

st.bar_chart(
    chart_df.set_index(
        "Metric"
    ),
    y="Score",
    height=350
)


# ============================================================
# QUESTION SUMMARY
# ============================================================

st.markdown(
    "## 📋 Question Summary"
)

rows = []

for i, result in enumerate(
    st.session_state.results,
    1
):

    rows.append(
        {
            "Question": f"Q{i}",
            "Type": result[
                "question_type"
            ],
            "Bloom": result[
                "actual_bloom"
            ],
            "CLO": result[
                "metrics"
            ]["CLO Alignment"],
            "PLO": result[
                "metrics"
            ]["PLO Alignment"],
            "Bloom Score": result[
                "metrics"
            ]["Bloom Alignment"],
            "Subject": result[
                "metrics"
            ]["Subject Relevance"],
            "Clarity": result[
                "metrics"
            ]["Clarity"],
            "Measurability": result[
                "metrics"
            ]["Measurability"],
            "Overall": result[
                "overall"
            ],
            "Status": get_status(
                result["overall"]
            ),
        }
    )

summary_df = pd.DataFrame(
    rows
)

st.dataframe(
    summary_df,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# QUESTION REVIEW
# ============================================================

st.markdown("---")

st.markdown(
    "## 🔎 Questions Review"
)

st.caption(
    "The original question is shown first, followed by its "
    "actual weak areas, a specific suggestion, and structured "
    "alternative questions."
)


for index, result in enumerate(
    st.session_state.results,
    1
):

    question = result[
        "question"
    ]

    st.markdown(
        f"### Question {index}"
    )

    # --------------------------------------------------------
    # ORIGINAL
    # --------------------------------------------------------

    st.markdown(
        f"""
        <div class="question-box">
        <strong>Original Question</strong><br><br>
        {question}
        </div>
        """,
        unsafe_allow_html=True
    )

    # --------------------------------------------------------
    # CURRENT SCORE
    # --------------------------------------------------------

    score = result[
        "overall"
    ]

    if score >= ATTAINMENT_THRESHOLD:

        st.success(
            f"🟢 Current Score: {score}/100 — "
            f"{get_status(score)}"
        )

    else:

        st.warning(
            f"🟠 Current Score: {score}/100 — "
            f"{get_status(score)}"
        )


    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    st.markdown(
        "#### Current Metrics"
    )

    metric_cols = st.columns(3)

    for i, metric in enumerate(
        METRIC_ORDER
    ):

        value = result[
            "metrics"
        ].get(metric)

        with metric_cols[
            i % 3
        ]:

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


    st.write(
        f"**Detected Bloom:** "
        f"{result['actual_bloom']}   |   "
        f"**Detected Type:** "
        f"{result['question_type']}"
    )


    # --------------------------------------------------------
    # WEAK AREAS
    # --------------------------------------------------------

    weak = get_weak_metrics(
        result
    )

    st.markdown(
        "#### Weak Areas"
    )

    if weak:

        for item in weak:

            st.markdown(
                f"""
                <div class="weak-box">
                <strong>{item['metric']}</strong>:
                {item['score']}/100 —
                {item['status']}
                </div>
                """,
                unsafe_allow_html=True
            )

    else:

        st.markdown(
            '<div class="strong-box">'
            "🟢 All individual metrics are at least 80/100."
            "</div>",
            unsafe_allow_html=True
        )


    # --------------------------------------------------------
    # QUESTION-SPECIFIC SUGGESTION
    # --------------------------------------------------------

    st.markdown(
        "#### 💡 Question-Specific Suggestion"
    )

    suggestion = generate_question_specific_suggestion(
        question,
        result,
        clo,
        plo,
        subject,
        course
    )

    st.markdown(
        f"""
        <div class="suggestion-box">
        {suggestion.replace(chr(10), "<br>")}
        </div>
        """,
        unsafe_allow_html=True
    )


    # --------------------------------------------------------
    # TARGET SETTINGS
    # --------------------------------------------------------

    st.markdown(
        "### 🛠️ Generate a Better Assessment Question"
    )

    col1, col2 = st.columns(2)

    with col1:

        selected_bloom = st.selectbox(
            "Target Bloom Level",
            BLOOM_LEVELS,
            index=BLOOM_LEVELS.index(
                result["actual_bloom"]
            )
            if result["actual_bloom"] in BLOOM_LEVELS
            else 1,
            key=f"target_bloom_{index}"
        )

    with col2:

        selected_type = st.selectbox(
            "Question Type",
            QUESTION_TYPES,
            index=QUESTION_TYPES.index(
                result["question_type"]
            )
            if result["question_type"] in QUESTION_TYPES
            else 4,
            key=f"target_type_{index}"
        )


    # --------------------------------------------------------
    # ACTION BUTTONS
    # --------------------------------------------------------

    action1, action2 = st.columns(2)

    with action1:

        generate_new = st.button(
            "✨ GENERATE NEW QUESTION",
            type="primary",
            use_container_width=True,
            key=f"new_{index}"
        )

    with action2:

        revise_current = st.button(
            "🔄 REVISE CURRENT QUESTION",
            use_container_width=True,
            key=f"revise_{index}"
        )


    # ========================================================
    # GENERATE NEW QUESTION
    # ========================================================

    if generate_new:

        with st.spinner(
            "Creating a new structured question..."
        ):

            new_question, new_result = (
                generate_best_candidate(
                    question,
                    clo,
                    plo,
                    subject,
                    course,
                    selected_bloom,
                    selected_type
                )
            )

            st.session_state.generated_questions[
                index
            ] = {
                "question": new_question,
                "result": new_result,
                "bloom": selected_bloom,
                "type": selected_type,
            }


    # ========================================================
    # REVISE CURRENT QUESTION
    # ========================================================

    if revise_current:

        with st.spinner(
            "Naturally revising the current question..."
        ):

            revised_question, revised_result = (
                revise_question_naturally(
                    question,
                    result,
                    subject,
                    clo,
                    plo,
                    selected_bloom,
                    selected_type
                )
            )

            st.session_state.revisions[
                index
            ] = {
                "question": revised_question,
                "result": revised_result,
                "bloom": selected_bloom,
                "type": selected_type,
            }


    # ========================================================
    # GENERATED NEW QUESTION DISPLAY
    # ========================================================

    generated = (
        st.session_state.generated_questions.get(
            index
        )
    )

    if generated:

        new_result = generated[
            "result"
        ]

        st.markdown(
            "#### ✨ Generated New Question"
        )

        st.markdown(
            f"""
            <div class="generated-box">
            <strong>New Question</strong><br><br>
            {generated['question']}
            </div>
            """,
            unsafe_allow_html=True
        )

        st.write(
            f"**Bloom:** {generated['bloom']}   |   "
            f"**Type:** {generated['type']}"
        )

        new_score = new_result[
            "overall"
        ]

        if new_score >= ATTAINMENT_THRESHOLD:

            st.success(
                f"🟢 Alignment Attained — "
                f"{new_score}/100"
            )

        else:

            st.warning(
                f"🟠 Generated Question Score: "
                f"{new_score}/100 — "
                f"{get_status(new_score)}"
            )

        generated_cols = st.columns(3)

        for i, metric in enumerate(
            METRIC_ORDER
        ):

            value = new_result[
                "metrics"
            ].get(metric)

            with generated_cols[
                i % 3
            ]:

                if value is not None:

                    st.metric(
                        metric,
                        f"{value}/100"
                    )

        remaining = get_weak_metrics(
            new_result
        )

        if remaining:

            st.markdown(
                "**Remaining Weak Areas:**"
            )

            for item in remaining:

                st.write(
                    f"- {item['metric']}: "
                    f"{item['score']}/100"
                )

        else:

            st.success(
                "🟢 All individual metrics have reached 80/100."
            )


    # ========================================================
    # REVISED QUESTION DISPLAY
    # ========================================================

    revised = (
        st.session_state.revisions.get(
            index
        )
    )

    if revised:

        revised_result = revised[
            "result"
        ]

        st.markdown(
            "#### 🔄 Revised Current Question"
        )

        st.markdown(
            f"""
            <div class="revised-box">
            <strong>Revised Question</strong><br><br>
            {revised['question']}
            </div>
            """,
            unsafe_allow_html=True
        )

        st.write(
            f"**Bloom:** {revised['bloom']}   |   "
            f"**Type:** {revised['type']}"
        )

        revised_score = revised_result[
            "overall"
        ]

        if revised_score >= ATTAINMENT_THRESHOLD:

            st.success(
                f"🟢 Alignment Attained — "
                f"Revised Question Score: "
                f"{revised_score}/100"
            )

        else:

            st.warning(
                f"🟠 Revised Question Score: "
                f"{revised_score}/100 — "
                f"{get_status(revised_score)}"
            )

        revised_cols = st.columns(3)

        for i, metric in enumerate(
            METRIC_ORDER
        ):

            value = revised_result[
                "metrics"
            ].get(metric)

            with revised_cols[
                i % 3
            ]:

                if value is not None:

                    st.metric(
                        metric,
                        f"{value}/100"
                    )

        remaining = get_weak_metrics(
            revised_result
        )

        if remaining:

            st.markdown(
                "**Remaining Weak Areas:**"
            )

            for item in remaining:

                st.write(
                    f"- {item['metric']}: "
                    f"{item['score']}/100"
                )

        else:

            st.success(
                "🟢 All individual metrics have reached 80/100."
            )

    st.divider()


# ============================================================
# FOOTER
# ============================================================

st.caption(
    "OBE Quiz Checker • Structured question generation "
    "based on subject, learning outcomes, Bloom level and assessment type."
)
