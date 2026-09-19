import streamlit as st
import pandas as pd
import io
import re
from difflib import SequenceMatcher


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
        "define",
        "identify",
        "list",
        "name",
        "state",
        "recall",
        "recognize",
        "label",
        "select",
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
    ],
    "Apply": [
        "apply",
        "calculate",
        "solve",
        "demonstrate",
        "use",
        "implement",
        "execute",
        "perform",
    ],
    "Analyze": [
        "analyze",
        "analyse",
        "compare",
        "contrast",
        "differentiate",
        "examine",
        "investigate",
        "categorize",
        "deconstruct",
    ],
    "Evaluate": [
        "evaluate",
        "assess",
        "justify",
        "critique",
        "judge",
        "defend",
        "appraise",
        "recommend",
    ],
    "Create": [
        "design",
        "create",
        "develop",
        "construct",
        "formulate",
        "produce",
        "plan",
        "propose",
    ],
}

STOPWORDS = {
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
    "is",
    "are",
    "was",
    "were",
    "be",
    "as",
    "at",
    "from",
    "that",
    "this",
    "these",
    "those",
    "into",
    "using",
    "use",
    "used",
    "can",
    "may",
    "will",
    "student",
    "students",
    "question",
    "questions",
    "following",
    "given",
    "following",
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
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 2.25rem;
        font-weight: 800;
        margin-bottom: 0.15rem;
    }

    .subtitle {
        color: #666666;
        font-size: 1rem;
        margin-bottom: 1.25rem;
    }

    .metric-card {
        border: 1px solid #dddddd;
        border-radius: 12px;
        padding: 16px;
        background: #ffffff;
        min-height: 120px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
        margin-bottom: 10px;
    }

    .metric-title {
        font-size: 0.9rem;
        color: #555555;
        font-weight: 650;
    }

    .metric-score {
        font-size: 2rem;
        font-weight: 800;
        margin-top: 5px;
    }

    .metric-status {
        font-size: 0.85rem;
        margin-top: 4px;
        color: #555555;
    }

    .attained-box {
        padding: 17px;
        border-radius: 10px;
        background: #eaf8ef;
        border: 1px solid #70c98a;
        color: #176b35;
        font-weight: 700;
        margin-bottom: 15px;
    }

    .revision-box {
        padding: 17px;
        border-radius: 10px;
        background: #fff7e6;
        border: 1px solid #efbd67;
        color: #875900;
        font-weight: 700;
        margin-bottom: 15px;
    }

    .question-box {
        border: 1px solid #dddddd;
        border-radius: 12px;
        padding: 18px;
        margin: 8px 0 15px 0;
        background: #ffffff;
    }

    .weak-box {
        background: #fff7e6;
        border-left: 5px solid #e3a43d;
        padding: 12px;
        border-radius: 6px;
        margin: 7px 0;
    }

    .strong-box {
        background: #eaf8ef;
        border-left: 5px solid #4da966;
        padding: 12px;
        border-radius: 6px;
        margin: 7px 0;
    }

    .suggestion-box {
        background: #f4f7fc;
        border: 1px solid #b7c8e5;
        border-radius: 10px;
        padding: 16px;
        margin: 8px 0 15px 0;
    }

    .generated-box {
        background: #f3f7ff;
        border: 1px solid #9db8ee;
        border-radius: 10px;
        padding: 16px;
        margin-top: 10px;
    }

    .revision-result {
        background: #f8f8ff;
        border: 1px solid #b6b6df;
        border-radius: 10px;
        padding: 16px;
        margin-top: 10px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# TEXT FUNCTIONS
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
    result = []

    for word in re.findall(
        r"[A-Za-z]{3,}",
        normalize(text)
    ):
        if word not in STOPWORDS:
            result.append(word)

    return result


def keyword_overlap(a, b):
    first = set(keyword_tokens(a))
    second = set(keyword_tokens(b))

    if not first or not second:
        return 0.0

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
                page_text = page.get_text(
                    "text",
                    sort=True
                )

                if page_text:
                    pages.append(page_text)

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
                page_text = page.extract_text()

                if page_text:
                    pages.append(page_text)

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
                    page_text = page.extract_text(
                        x_tolerance=2,
                        y_tolerance=3
                    )

                    if page_text:
                        pages.append(page_text)

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
                        2.0,
                        2.0
                    ),
                    alpha=False
                )

                image = Image.open(
                    io.BytesIO(
                        pix.tobytes("png")
                    )
                )

                page_text = pytesseract.image_to_string(
                    image,
                    config="--psm 6"
                )

                if page_text:
                    pages.append(page_text)

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

                row_text = []

                for cell in row.cells:
                    row_text.append(
                        cell.text
                    )

                if row_text:
                    parts.append(
                        " ".join(row_text)
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

            parts.append(
                f"Sheet: {sheet}"
            )

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
            ".bmp",
        )
    ):
        return read_image(uploaded_file)

    return ""


# ============================================================
# QUESTION FILTERING
# ============================================================

def is_heading_or_label(text):
    """
    Excludes section headings, labels, instructions,
    metadata and other non-question text.
    """

    text = clean_text(text)

    if not text:
        return True

    normalized = normalize(text)

    heading_patterns = [
        r"^section\s*[a-z0-9ivx\-]+$",
        r"^part\s*[a-z0-9ivx\-]+$",
        r"^unit\s*[a-z0-9ivx\-]+$",
        r"^chapter\s*[a-z0-9ivx\-]+$",
        r"^module\s*[a-z0-9ivx\-]+$",

        r"^section\s*[a-z0-9ivx\-]+\s*[:\-].*$",
        r"^part\s*[a-z0-9ivx\-]+\s*[:\-].*$",

        r"^instructions?\s*[:\-]?",
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
        r"^theory\s+questions?$",

        r"^answer\s+the\s+following$",
        r"^answer\s+all\s+questions?$",
        r"^attempt\s+all\s+questions?$",
        r"^attempt\s+any\s+questions?$",
        r"^choose\s+the\s+correct\s+answer$",
        r"^choose\s+one$",
        r"^select\s+the\s+correct\s+answer$",

        r"^following\s+questions?$",
        r"^following\s+items?$",
        r"^questions?$",

        r"^assessment$",
        r"^quiz$",
        r"^test$",
        r"^exam$",
        r"^midterm$",
        r"^mid\s*term$",
        r"^final\s+exam$",

        r"^course\s+learning\s+outcome[s]?$",
        r"^program(?:me)?\s+learning\s+outcome[s]?$",
        r"^clo[s]?$",
        r"^plo[s]?$",

        r"^rubric$",
        r"^marking\s+scheme$",
        r"^answer\s+key$",
        r"^answers?$",

        r"^name\s*[:\-]?$",
        r"^roll\s*(?:no|number)\s*[:\-]?$",
        r"^registration\s*(?:no|number)\s*[:\-]?$",
        r"^date\s*[:\-]?$",
        r"^time\s*[:\-]?$",

        r"^total\s+marks?\s*[:\-]?",
        r"^marks?\s*[:\-]?",
        r"^points?\s*[:\-]?",
    ]

    for pattern in heading_patterns:

        if re.search(
            pattern,
            normalized,
            flags=re.I
        ):
            return True

    # Metadata labels such as:
    # CLO: ...
    # PLO: ...
    # Marks: ...
    # Topic: ...
    if re.match(
        r"^(clo|plo|bloom|marks?|points?|"
        r"topic|section|part|course|subject|"
        r"date|time|name|roll\s*(?:no|number))"
        r"\s*[:=\-]",
        normalized,
        flags=re.I,
    ):
        return True

    # Very short non-question headings.
    if len(text.split()) <= 5:

        if "?" not in text:

            command_words = [
                "define",
                "identify",
                "state",
                "list",
                "explain",
                "describe",
                "calculate",
                "compare",
                "analyze",
                "analyse",
                "evaluate",
                "discuss",
                "solve",
                "determine",
            ]

            if not any(
                re.search(
                    r"\b" + re.escape(word) + r"\b",
                    normalized,
                    flags=re.I
                )
                for word in command_words
            ):
                return True

    # Separator-only lines.
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

    normalized = normalize(text)

    # Question mark.
    if "?" in text:
        return True

    command_words = [
        "define",
        "identify",
        "state",
        "list",
        "name",
        "explain",
        "describe",
        "discuss",
        "compare",
        "contrast",
        "analyze",
        "analyse",
        "evaluate",
        "assess",
        "justify",
        "calculate",
        "compute",
        "solve",
        "determine",
        "derive",
        "demonstrate",
        "apply",
        "design",
        "develop",
        "construct",
        "write",
        "interpret",
        "classify",
        "differentiate",
        "examine",
        "critique",
        "recommend",
        "prove",
    ]

    for word in command_words:

        if re.search(
            r"\b" + re.escape(word) + r"\b",
            normalized
        ):
            return True

    # MCQ options.
    if re.search(
        r"\b[A-D]\s*[\)\.\:]\s+",
        text,
        flags=re.I
    ):
        return True

    # True/False.
    if re.search(
        r"\btrue\s+or\s+false\b",
        normalized
    ):
        return True

    return False


def clean_question_candidate(block):
    block = clean_text(block)

    if not block:
        return ""

    # Remove answer key/rubric after a question.
    block = re.split(
        r"\n\s*(?:Answer\s*Key|Answers?|"
        r"Marking\s*Scheme|Rubric)\s*:?",
        block,
        maxsplit=1,
        flags=re.I,
    )[0]

    # Remove marks.
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

    block = re.sub(
        r"\s+(?:Marks?|Points?)\s*[:\-]\s*\d+\s*$",
        "",
        block,
        flags=re.I,
    )

    return block.strip()


def extract_questions(text):
    """
    Conservative extraction.

    If numbered questions exist, only actual numbered
    question blocks are considered.

    Headings and labels are filtered out.
    """

    text = clean_text(text)

    if not text:
        return []

    questions = []

    # --------------------------------------------------------
    # NUMBERED QUESTIONS
    # --------------------------------------------------------

    numbered_pattern = re.compile(
        r"(?im)^\s*"
        r"(?:Q(?:uestion)?\s*)?"
        r"(\d{1,3})"
        r"\s*[\.\):\-]\s+"
    )

    matches = list(
        numbered_pattern.finditer(text)
    )

    if matches:

        for index, match in enumerate(matches):

            start = match.end()

            if index + 1 < len(matches):
                end = matches[index + 1].start()
            else:
                end = len(text)

            block = text[start:end]

            block = clean_text(block)

            # Remove heading-like lines at beginning/end.
            lines = block.splitlines()
            cleaned_lines = []

            for line in lines:

                line = clean_text(line)

                if not line:
                    continue

                if is_heading_or_label(line):
                    continue

                cleaned_lines.append(line)

            block = clean_text(
                "\n".join(cleaned_lines)
            )

            # Remove standalone OR/CHOICE markers.
            block = re.split(
                r"\n\s*(?:OR|EITHER|CHOICE)"
                r"\s*:?\s*\n",
                block,
                maxsplit=1,
                flags=re.I,
            )[0]

            block = clean_question_candidate(
                block
            )

            if not block:
                continue

            if is_heading_or_label(block):
                continue

            if len(block.split()) < 3:
                continue

            # If it does not look like a question and is short,
            # discard it.
            if not looks_like_actual_question(block):

                if len(block.split()) < 10:
                    continue

            questions.append(block)

        # Remove duplicates.
        unique_questions = []

        for question in questions:

            duplicate = False

            for old_question in unique_questions:

                if similarity(
                    question,
                    old_question
                ) >= 0.92:

                    duplicate = True
                    break

            if not duplicate:
                unique_questions.append(
                    question
                )

        return unique_questions

    # --------------------------------------------------------
    # FALLBACK WHEN NO NUMBERING EXISTS
    # --------------------------------------------------------

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

        if is_heading_or_label(block):
            continue

        if not looks_like_actual_question(block):
            continue

        if len(block.split()) < 3:
            continue

        questions.append(block)

    unique_questions = []

    for question in questions:

        if not any(
            similarity(
                question,
                old_question
            ) >= 0.90
            for old_question in unique_questions
        ):
            unique_questions.append(
                question
            )

    return unique_questions


# ============================================================
# QUESTION TYPE
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
# BLOOM
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

    score = 60

    q = normalize(question)

    explicit = False

    for verb in BLOOM_VERBS.get(
        actual,
        []
    ):

        if re.search(
            r"\b" + re.escape(verb) + r"\b",
            q
        ):
            explicit = True
            break

    if explicit:
        score = 92

    elif len(q.split()) >= 10:
        score = 78

    if target_bloom:

        if actual == target_bloom:
            score = max(
                score,
                94
            )

        else:

            difference = abs(
                bloom_number(actual)
                - bloom_number(target_bloom)
            )

            if difference == 1:
                score = min(
                    score,
                    76
                )

            elif difference >= 2:
                score = min(
                    score,
                    58
                )

    return score


def subject_relevance_score(
    question,
    subject,
    course
):
    reference = " ".join(
        x
        for x in [
            subject,
            course
        ]
        if x and x.strip()
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

    word_count = len(
        question.split()
    )

    if word_count < 5:
        score -= 20

    if word_count > 120:
        score -= 10

    if question.count("?") > 2:
        score -= 8

    if re.search(
        r"\b(etc|and so on)\b",
        question,
        flags=re.I
    ):
        score -= 8

    if not re.search(
        r"\b(what|why|how|explain|describe|"
        r"identify|calculate|analyze|analyse|"
        r"compare|evaluate|design|develop|"
        r"solve|discuss|write|determine|"
        r"define|state|list)\b",
        question,
        flags=re.I
    ):
        score -= 12

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

    values = [
        value
        for value in metrics.values()
        if value is not None
    ]

    overall = (
        round(
            sum(values) / len(values)
        )
        if values
        else 0
    )

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

        if score is None:
            continue

        if score < ATTAINMENT_THRESHOLD:

            weak.append(
                {
                    "metric": metric,
                    "score": score,
                    "status": get_status(
                        score
                    ),
                }
            )

    weak.sort(
        key=lambda item: item["score"]
    )

    return weak


# ============================================================
# QUESTION-SPECIFIC SUGGESTION
# ============================================================

def generate_question_specific_suggestion(
    question,
    result,
    clo,
    plo,
    subject,
    course,
):
    """
    Creates a suggestion that explicitly restates the original
    question and then explains the actual weaknesses.
    """

    original = clean_text(
        question
    )

    weak_metrics = get_weak_metrics(
        result
    )

    if not weak_metrics:

        return (
            f"**Original Question:**\n\n"
            f"{original}\n\n"
            f"**Suggestion:**\n\n"
            f"This question has reached the {ATTAINMENT_THRESHOLD}/100 "
            f"attainment threshold across the evaluated metrics. "
            f"It can be retained. You may make minor wording or "
            f"contextual refinements if greater specificity is required."
        )

    weak_names = [
        item["metric"]
        for item in weak_metrics
    ]

    weak_scores = [
        f"{item['metric']}: {item['score']}/100 "
        f"({item['status']})"
        for item in weak_metrics
    ]

    suggestions = []

    # CLO
    if "CLO Alignment" in weak_names:

        suggestions.append(
            "CLO Alignment: connect the question more directly "
            "to the knowledge, skill, or action stated in the CLO. "
            "The student's response should provide observable evidence "
            "of achieving that CLO."
        )

    # PLO
    if "PLO Alignment" in weak_names:

        suggestions.append(
            "PLO Alignment: require the student to demonstrate the "
            "broader programme-level capability represented by the PLO, "
            "rather than testing only an isolated fact."
        )

    # Bloom
    if "Bloom Alignment" in weak_names:

        actual_bloom = result.get(
            "actual_bloom",
            "Understand"
        )

        suggestions.append(
            f"Bloom Alignment: the current question operates mainly "
            f"at the {actual_bloom} level. Revise the task so that "
            f"the learner performs the intended cognitive operation "
            f"explicitly, such as applying, analyzing, evaluating, "
            f"or creating, where appropriate."
        )

    # Subject
    if "Subject Relevance" in weak_names:

        subject_name = (
            subject
            or course
            or "the selected subject"
        )

        suggestions.append(
            f"Subject Relevance: make the question explicitly "
            f"grounded in {subject_name} by using relevant concepts, "
            f"terminology, data, examples, or a realistic subject-specific "
            f"context."
        )

    # Clarity
    if "Clarity" in weak_names:

        suggestions.append(
            "Clarity: replace vague or broad wording with one clearly "
            "defined task. Tell the student exactly what must be "
            "explained, calculated, compared, analyzed, justified, "
            "or produced."
        )

    # Measurability
    if "Measurability" in weak_names:

        suggestions.append(
            "Measurability: use an observable action and a specific "
            "expected response so that the answer can be assessed "
            "consistently with a marking scheme or rubric."
        )

    context = ""

    if clo.strip():

        context += (
            f"\n\n**Relevant CLO:** {clo}"
        )

    if plo.strip():

        context += (
            f"\n\n**Relevant PLO:** {plo}"
        )

    suggestion_body = "\n\n".join(
        suggestions
    )

    return (
        f"**Original Question:**\n\n"
        f"{original}\n\n"

        f"**Actual Weak Areas:**\n\n"
        + "\n".join(
            f"- {item}"
            for item in weak_scores
        )
        + "\n\n"

        f"**Specific Suggestion:**\n\n"
        f"{suggestion_body}"

        f"{context}\n\n"

        "**Recommended Revision:**\n\n"
        "Keep the original topic and intended content, but rewrite "
        "the question so that the weak alignment areas are directly "
        "addressed. The revised question should make the expected "
        "student action and evidence of learning explicit."
    )


# ============================================================
# GENERATION
# ============================================================

def extract_topic(
    question,
    subject
):
    tokens = keyword_tokens(
        question
    )

    if subject:

        subject_words = set(
            keyword_tokens(
                subject
            )
        )

        tokens = [
            word
            for word in tokens
            if word not in subject_words
        ]

    if not tokens:

        return (
            subject
            or "the selected topic"
        )

    return " ".join(
        tokens[:8]
    )


def bloom_instruction(level):

    instructions = {
        "Remember":
            "identify or state the relevant knowledge",
        "Understand":
            "explain the relevant concept clearly",
        "Apply":
            "apply the relevant concept to the given situation",
        "Analyze":
            "analyze the components, relationships, or evidence",
        "Evaluate":
            "evaluate the issue using relevant criteria and evidence",
        "Create":
            "design or develop an appropriate solution",
    }

    return instructions.get(
        level,
        instructions["Understand"]
    )


def generate_mcq(
    topic,
    clo,
    plo,
    bloom
):
    return (
        f"In the context of {topic}, which option best demonstrates "
        f"the learner's ability to {bloom_instruction(bloom)} "
        f"while addressing the intended learning outcome?\n\n"
        "A. Apply the relevant concept to the given context\n"
        "B. State an unrelated definition\n"
        "C. List terms without applying them\n"
        "D. Repeat a memorized statement"
    )


def generate_true_false(
    topic,
    clo,
    plo,
    bloom
):
    return (
        f"True or False: In relation to {topic}, a learner who can "
        f"{bloom_instruction(bloom)} is demonstrating the intended "
        f"learning outcome rather than merely recalling an isolated fact."
    )


def generate_fill_blank(
    topic,
    clo,
    plo,
    bloom
):
    return (
        f"Complete the statement: To demonstrate the learning outcome "
        f"related to {topic}, a student should be able to "
        f"__________ the relevant concept in an appropriate context."
    )


def generate_matching(
    topic,
    clo,
    plo,
    bloom
):
    return (
        f"Match each concept related to {topic} with the description "
        f"or application that best demonstrates the learner's ability "
        f"to {bloom_instruction(bloom)}."
    )


def generate_short_answer(
    topic,
    clo,
    plo,
    bloom
):
    return (
        f"Explain how you would {bloom_instruction(bloom)} in relation "
        f"to {topic}. Use relevant concepts, reasoning, or evidence "
        f"to support your response."
    )


def generate_essay(
    topic,
    clo,
    plo,
    bloom
):
    return (
        f"Discuss {topic} in detail and demonstrate how a learner can "
        f"{bloom_instruction(bloom)}. Support your response with "
        f"relevant concepts, examples, evidence, or justification."
    )


def generate_case(
    topic,
    clo,
    plo,
    bloom
):
    return (
        f"Case/Scenario: A situation has arisen involving {topic}. "
        f"Using the concepts covered in the course, determine how "
        f"you would {bloom_instruction(bloom)}. Explain the reasoning "
        f"behind your response and relate it to the intended "
        f"learning outcome."
    )


def generate_numerical(
    topic,
    clo,
    plo,
    bloom
):
    return (
        f"Numerical/Application Problem: Consider a problem involving "
        f"{topic}. Use the relevant formula, method, or procedure to "
        f"solve the problem and explain how the result demonstrates "
        f"the intended learning outcome."
    )


def generate_practical(
    topic,
    clo,
    plo,
    bloom
):
    return (
        f"Practical Task: Using a realistic situation involving "
        f"{topic}, demonstrate how you would "
        f"{bloom_instruction(bloom)}. State the steps, decisions, "
        f"or evidence that would be used to complete the task."
    )


def generate_coding(
    topic,
    clo,
    plo,
    bloom
):
    return (
        f"Coding/Practical Task: Develop a solution related to "
        f"{topic} that requires you to "
        f"{bloom_instruction(bloom)}. Explain the logic of your "
        f"solution and identify the expected result."
    )


def generate_question_by_type(
    question_type,
    topic,
    clo,
    plo,
    bloom
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
        bloom
    )


# ============================================================
# REVISION
# ============================================================

def improve_existing_question(
    question,
    result,
    clo,
    plo,
    subject,
    course,
    bloom,
    question_type
):
    """
    Revises the actual question according to its specific
    weak areas.
    """

    weak_metrics = get_weak_metrics(
        result
    )

    topic = extract_topic(
        question,
        subject
    )

    weak_names = [
        item["metric"]
        for item in weak_metrics
    ]

    revised = clean_text(
        question
    )

    # Bloom weakness
    if "Bloom Alignment" in weak_names:

        revised = (
            f"Using the concepts related to {topic}, "
            f"{bloom_instruction(bloom)}. "
            f"{revised}"
        )

    # CLO weakness
    if "CLO Alignment" in weak_names:

        revised += (
            f"\n\nYour response should demonstrate the following "
            f"course learning outcome: {clo}"
        )

    # PLO weakness
    if "PLO Alignment" in weak_names:

        revised += (
            f"\n\nRelate your response to the broader programme "
            f"learning outcome: {plo}"
        )

    # Measurability weakness
    if "Measurability" in weak_names:

        revised += (
            "\n\nSupport your answer with specific evidence, "
            "reasoning, calculation, comparison, justification, "
            "design, or another observable outcome appropriate "
            "to the task."
        )

    # Clarity weakness
    if "Clarity" in weak_names:

        revised = (
            f"In relation to {topic}, "
            f"{bloom_instruction(bloom)}. "
            f"Clearly state the relevant concepts, evidence, "
            f"steps, reasoning, or result required in your response."
        )

    # Subject weakness
    if "Subject Relevance" in weak_names:

        revised = (
            f"In the subject area of "
            f"{subject or course or topic}, "
            f"{bloom_instruction(bloom)} using the relevant "
            f"concepts related to {topic}. "
            f"Explain your response using subject-specific evidence."
        )

    # If result is too short, use structured generation.
    if len(revised.split()) < 10:

        revised = generate_question_by_type(
            question_type,
            topic,
            clo,
            plo,
            bloom
        )

    return revised


# ============================================================
# BEST GENERATED QUESTION
# ============================================================

def generate_candidate_questions(
    original_question,
    clo,
    plo,
    subject,
    course,
    target_bloom,
    question_type
):
    topic = extract_topic(
        original_question,
        subject
    )

    candidates = []

    candidates.append(
        generate_question_by_type(
            question_type,
            topic,
            clo,
            plo,
            target_bloom
        )
    )

    candidates.append(
        (
            f"Using the concepts related to {topic}, "
            f"{bloom_instruction(target_bloom)} "
            f"to demonstrate the following CLO: {clo}. "
            f"Relate your response to the relevant PLO: {plo}."
        )
    )

    candidates.append(
        (
            f"Consider a realistic situation involving {topic}. "
            f"{bloom_instruction(target_bloom).capitalize()} "
            f"and provide evidence that demonstrates achievement "
            f"of the CLO: {clo}."
        )
    )

    candidates.append(
        (
            f"Analyze the key issue associated with {topic} and "
            f"provide evidence-based reasoning that demonstrates "
            f"the intended learning outcome: {clo}."
        )
    )

    candidates.append(
        (
            f"For {topic}, complete a measurable task that requires "
            f"you to {bloom_instruction(target_bloom)}. "
            f"State the evidence or result that would demonstrate "
            f"achievement of the CLO: {clo}."
        )
    )

    filtered = []

    for candidate in candidates:

        if similarity(
            candidate,
            original_question
        ) >= 0.78:
            continue

        if any(
            similarity(
                candidate,
                old
            ) >= 0.88
            for old in filtered
        ):
            continue

        filtered.append(
            candidate
        )

    return filtered


def generate_best_candidate(
    original_question,
    clo,
    plo,
    subject,
    course,
    target_bloom,
    question_type
):
    candidates = generate_candidate_questions(
        original_question,
        clo,
        plo,
        subject,
        course,
        target_bloom,
        question_type
    )

    if not candidates:

        candidates = [
            generate_question_by_type(
                question_type,
                extract_topic(
                    original_question,
                    subject
                ),
                clo,
                plo,
                target_bloom
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

        evaluated.append(
            (
                candidate,
                result
            )
        )

    evaluated.sort(
        key=lambda item: item[1]["overall"],
        reverse=True
    )

    return evaluated[0]


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

            if score is None:
                continue

            values.setdefault(
                metric,
                []
            ).append(score)

    averages = {}

    for metric, scores in values.items():

        if scores:

            averages[metric] = round(
                sum(scores) / len(scores)
            )

    return averages


def calculate_overall_score(
    results
):
    scores = [
        result["overall"]
        for result in results
        if result.get("overall") is not None
    ]

    if not scores:
        return 0

    return round(
        sum(scores) / len(scores)
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
                    "status": get_status(
                        score
                    )
                }
            )

    weak.sort(
        key=lambda item: item["score"]
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
        "Assessment alignment and improvement tool"
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
    "Evaluate assessment questions against CLO, PLO, "
    "Bloom's Taxonomy, subject relevance, clarity and measurability."
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
                "Please check the file or OCR/dependency setup."
            )
            st.stop()

        extracted_questions = extract_questions(
            assessment_text
        )

        if not extracted_questions:

            st.error(
                "No actual assessment questions could be extracted. "
                "Headings, labels and instructions are excluded. "
                "Please check that the assessment contains recognizable "
                "question text."
            )
            st.stop()

        st.session_state.questions = (
            extracted_questions
        )

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

        for question in extracted_questions:

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
        f"Analysis complete. "
        f"{len(extracted_questions)} actual assessment "
        f"question(s) detected. "
        f"Headings and labels were excluded."
    )


# ============================================================
# WAITING STATE
# ============================================================

if not st.session_state.analysis_done:

    st.info(
        "⏳ Enter the CLO and PLO, upload the complete assessment, "
        "and click **Analyze Assessment**."
    )

    st.stop()


# ============================================================
# FILE INFORMATION
# ============================================================

st.info(
    f"📄 **{st.session_state.file_name}** — "
    f"{len(st.session_state.questions)} actual "
    f"assessment question(s) detected. "
    f"Headings, labels and instructions are excluded."
)


# ============================================================
# OVERALL DASHBOARD — FIRST
# ============================================================

st.markdown(
    "## 📊 Overall Alignment Dashboard"
)

total_score = calculate_overall_score(
    st.session_state.results
)

averages = calculate_metric_averages(
    st.session_state.results
)

if total_score >= ATTAINMENT_THRESHOLD:

    st.markdown(
        f'<div class="attained-box">'
        f"🟢 Alignment Attained — Overall Score: "
        f"{total_score}/100"
        f"</div>",
        unsafe_allow_html=True
    )

else:

    st.markdown(
        f'<div class="revision-box">'
        f"🟠 Revision Required — Overall Score: "
        f"{total_score}/100"
        f"</div>",
        unsafe_allow_html=True
    )


# ============================================================
# OVERALL METRIC CARDS
# ============================================================

st.markdown(
    "### Overall Metrics"
)

metric_columns = st.columns(3)

for index, metric in enumerate(
    METRIC_ORDER
):

    score = averages.get(
        metric
    )

    if score is None:
        display_score = "N/A"
        status = "Not Available"

    else:
        display_score = (
            f"{score}/100"
        )
        status = get_status(
            score
        )

    with metric_columns[
        index % 3
    ]:

        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">{metric}</div>
                <div class="metric-score">{display_score}</div>
                <div class="metric-status">{status}</div>
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

weak_overall = overall_weak_areas(
    st.session_state.results
)

if weak_overall:

    for item in weak_overall:

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
        "🟢 All overall metrics have reached "
        "the 80/100 attainment threshold."
        "</div>",
        unsafe_allow_html=True
    )


# ============================================================
# ONE GRAPH
# ============================================================

st.markdown(
    "### Alignment Overview"
)

chart_data = pd.DataFrame(
    {
        "Metric": METRIC_ORDER,
        "Score": [
            averages.get(
                metric,
                0
            )
            for metric in METRIC_ORDER
        ]
    }
)

st.bar_chart(
    chart_data.set_index(
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

summary_rows = []

for index, result in enumerate(
    st.session_state.results,
    start=1
):

    summary_rows.append(
        {
            "Question": f"Q{index}",
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
    summary_rows
)

st.dataframe(
    summary_df,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# QUESTIONS REVIEW — LAST
# ============================================================

st.markdown("---")

st.markdown(
    "## 🔎 Questions Review"
)

st.caption(
    "Detailed review, question-specific suggestions, "
    "revision and new-question generation."
)


for index, result in enumerate(
    st.session_state.results,
    start=1
):

    question_number = index
    question = result[
        "question"
    ]

    st.markdown(
        f"### Question {question_number}"
    )

    # --------------------------------------------------------
    # ORIGINAL QUESTION
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

    current_score = result[
        "overall"
    ]

    if current_score >= ATTAINMENT_THRESHOLD:

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
    # METRICS
    # --------------------------------------------------------

    st.markdown(
        "#### Current Question Metrics"
    )

    qmetric_columns = st.columns(3)

    for metric_index, metric in enumerate(
        METRIC_ORDER
    ):

        score = result[
            "metrics"
        ].get(metric)

        with qmetric_columns[
            metric_index % 3
        ]:

            if score is None:

                st.metric(
                    metric,
                    "N/A"
                )

            else:

                st.metric(
                    metric,
                    f"{score}/100"
                )


    # --------------------------------------------------------
    # BLOOM AND TYPE
    # --------------------------------------------------------

    info1, info2 = st.columns(2)

    with info1:

        st.write(
            f"**Actual Bloom Level:** "
            f"{result['actual_bloom']}"
        )

    with info2:

        st.write(
            f"**Detected Question Type:** "
            f"{result['question_type']}"
        )


    # --------------------------------------------------------
    # SPECIFIC WEAK AREAS
    # --------------------------------------------------------

    weak_metrics = get_weak_metrics(
        result
    )

    st.markdown(
        "#### Specific Weak Areas"
    )

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
                unsafe_allow_html=True
            )

    else:

        st.markdown(
            '<div class="strong-box">'
            "🟢 No individual metric is below 80/100."
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
    # IMPROVEMENT CONTROLS
    # --------------------------------------------------------

    st.markdown(
        "### 🛠️ Improve This Question"
    )

    control1, control2 = st.columns(2)

    with control1:

        current_bloom = result[
            "actual_bloom"
        ]

        if current_bloom not in BLOOM_LEVELS:
            current_bloom = "Understand"

        selected_bloom = st.selectbox(
            "Target Bloom Level",
            BLOOM_LEVELS,
            index=BLOOM_LEVELS.index(
                current_bloom
            ),
            key=f"bloom_target_{question_number}"
        )

    with control2:

        current_type = result[
            "question_type"
        ]

        if current_type not in QUESTION_TYPES:
            current_type = "Short Answer"

        selected_type = st.selectbox(
            "Question Type",
            QUESTION_TYPES,
            index=QUESTION_TYPES.index(
                current_type
            ),
            key=f"type_target_{question_number}"
        )


    # --------------------------------------------------------
    # PROMINENT ACTION BUTTONS
    # --------------------------------------------------------

    st.markdown(
        "#### ✨ Assessment Improvement Actions"
    )

    generate_col, revise_col = st.columns(2)

    with generate_col:

        generate_clicked = st.button(
            "✨ GENERATE NEW QUESTION",
            key=f"generate_question_{question_number}",
            type="primary",
            use_container_width=True
        )

    with revise_col:

        revise_clicked = st.button(
            "🔄 REVISE CURRENT QUESTION",
            key=f"revise_question_{question_number}",
            use_container_width=True
        )


    # ========================================================
    # GENERATE NEW QUESTION
    # ========================================================

    if generate_clicked:

        with st.spinner(
            f"Generating a new question for Question "
            f"{question_number}..."
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
                question_number
            ] = {
                "question": new_question,
                "result": new_result,
                "target_bloom": selected_bloom,
                "question_type": selected_type,
            }


    # ========================================================
    # REVISE CURRENT QUESTION
    # ========================================================

    if revise_clicked:

        with st.spinner(
            f"Revising Question "
            f"{question_number}..."
        ):

            revised_question = (
                improve_existing_question(
                    question,
                    result,
                    clo,
                    plo,
                    subject,
                    course,
                    selected_bloom,
                    selected_type
                )
            )

            revised_result = evaluate_question(
                revised_question,
                clo,
                plo,
                subject,
                course,
                selected_bloom
            )

            st.session_state.revisions[
                question_number
            ] = {
                "question": revised_question,
                "result": revised_result,
                "target_bloom": selected_bloom,
                "question_type": selected_type,
            }


    # ========================================================
    # GENERATED QUESTION RESULT
    # ========================================================

    generated = (
        st.session_state.generated_questions.get(
            question_number
        )
    )

    if generated:

        generated_result = generated[
            "result"
        ]

        st.markdown(
            "#### ✨ Generated New Question"
        )

        st.markdown(
            f"""
            <div class="generated-box">
            <strong>New Question</strong><br><br>
            {generated["question"]}
            </div>
            """,
            unsafe_allow_html=True
        )

        st.write(
            f"**Target Bloom:** "
            f"{generated['target_bloom']}  |  "
            f"**Question Type:** "
            f"{generated['question_type']}"
        )

        generated_score = (
            generated_result["overall"]
        )

        if generated_score >= ATTAINMENT_THRESHOLD:

            st.success(
                f"🟢 Alignment Attained — "
                f"Generated Question Score: "
                f"{generated_score}/100"
            )

        else:

            st.warning(
                f"Generated Question Score: "
                f"{generated_score}/100 — "
                f"{get_status(generated_score)}"
            )

        st.markdown(
            "**Generated Question Metrics**"
        )

        generated_columns = st.columns(3)

        for metric_index, metric in enumerate(
            METRIC_ORDER
        ):

            score = generated_result[
                "metrics"
            ].get(metric)

            with generated_columns[
                metric_index % 3
            ]:

                if score is not None:

                    st.metric(
                        metric,
                        f"{score}/100"
                    )

        generated_weak = get_weak_metrics(
            generated_result
        )

        if generated_weak:

            st.markdown(
                "**Remaining Weak Areas:**"
            )

            for item in generated_weak:

                st.write(
                    f"- {item['metric']}: "
                    f"{item['score']}/100 "
                    f"({item['status']})"
                )

        else:

            st.success(
                "🟢 All individual metrics for the "
                "generated question have reached 80/100."
            )


    # ========================================================
    # REVISED QUESTION RESULT
    # ========================================================

    revised = (
        st.session_state.revisions.get(
            question_number
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
            <div class="revision-result">
            <strong>Revised Question</strong><br><br>
            {revised["question"]}
            </div>
            """,
            unsafe_allow_html=True
        )

        st.write(
            f"**Target Bloom:** "
            f"{revised['target_bloom']}  |  "
            f"**Question Type:** "
            f"{revised['question_type']}"
        )

        revised_score = (
            revised_result["overall"]
        )

        if revised_score >= ATTAINMENT_THRESHOLD:

            st.success(
                f"🟢 Alignment Attained — "
                f"Revised Question Score: "
                f"{revised_score}/100"
            )

        else:

            st.warning(
                f"Revised Question Score: "
                f"{revised_score}/100 — "
                f"{get_status(revised_score)}"
            )

        st.markdown(
            "**Revised Question Metrics**"
        )

        revised_columns = st.columns(3)

        for metric_index, metric in enumerate(
            METRIC_ORDER
        ):

            score = revised_result[
                "metrics"
            ].get(metric)

            with revised_columns[
                metric_index % 3
            ]:

                if score is not None:

                    st.metric(
                        metric,
                        f"{score}/100"
                    )

        revised_weak = get_weak_metrics(
            revised_result
        )

        if revised_weak:

            st.markdown(
                "**Remaining Weak Areas:**"
            )

            for item in revised_weak:

                st.write(
                    f"- {item['metric']}: "
                    f"{item['score']}/100 "
                    f"({item['status']})"
                )

        else:

            st.success(
                "🟢 All individual metrics for the "
                "revised question have reached 80/100."
            )

    st.divider()


# ============================================================
# FOOTER
# ============================================================

st.caption(
    "OBE Quiz Checker • Independent assessment alignment analysis"
)
